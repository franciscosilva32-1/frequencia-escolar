import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import psycopg2
import os
import io
import base64
import json
import streamlit.components.v1 as components
import plotly.express as px
from streamlit_cookies_manager import CookieManager

# ------------------------------------------------------------
# 1. CONFIGURAÇÃO DA PÁGINA
# ------------------------------------------------------------
st.set_page_config(
    page_title="Centro Educa Mais Jansen Veloso",
    page_icon="🏫",
    layout="wide",
    initial_sidebar_state="collapsed"
)

cookies = CookieManager()
if not cookies.ready():
    st.stop()

# ------------------------------------------------------------
# 2. CSS MODERNO E RESPONSIVO
# ------------------------------------------------------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
    :root { --primary: #0f2b4a; --accent: #e67e22; --success: #27ae60; --danger: #e74c3c; }
    .stApp { background: linear-gradient(180deg, #f8fafc 0%, #e9edf2 100%); }
    #MainMenu, footer, header {visibility: hidden;}
    .main-title { font-family: 'Inter', sans-serif; font-weight: 800; font-size: clamp(1.8rem, 6vw, 2.5rem); color: var(--primary); text-align: center; margin:0;}
    .sub-title { font-family: 'Inter', sans-serif; font-size: 0.9rem; color: #5f6b7a; text-align: center; margin-bottom: 1.5rem;}
    .card { background: rgba(255,255,255,0.7); backdrop-filter: blur(10px); border-radius: 20px; padding: 1.2rem; margin-bottom: 1rem; box-shadow: 0 8px 20px rgba(0,0,0,0.04); }
    .metric-item { background: white; border-radius: 16px; padding: 0.8rem; text-align: center; border-bottom: 4px solid var(--accent); }
    .metric-value { font-family: 'Inter', sans-serif; font-weight: 800; font-size: 1.8rem; color: var(--primary); }
    .metric-label { font-size: 0.8rem; text-transform: uppercase; color: #5f6b7a; }
    .login-card { max-width: 380px; margin: 10vh auto; background: white; border-radius: 28px; padding: 2rem; text-align: center; box-shadow: 0 25px 40px rgba(0,0,0,0.1); }
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------
# 3. GESTÃO DO BIPE (AVISO SONORO)
# ------------------------------------------------------------
def emitir_som_beep():
    html_beep = """
    <script>
        const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        const oscillator = audioCtx.createOscillator();
        const gainNode = audioCtx.createGain();
        oscillator.connect(gainNode);
        gainNode.connect(audioCtx.destination);
        oscillator.type = 'sine';
        oscillator.frequency.value = 850; // Som agudo e claro
        oscillator.start();
        gainNode.gain.exponentialRampToValueAtTime(0.00001, audioCtx.currentTime + 0.2);
        oscillator.stop(audioCtx.currentTime + 0.2);
    </script>
    """
    components.html(html_beep, height=0, width=0)

if "tocar_som" not in st.session_state:
    st.session_state.tocar_som = False

if st.session_state.tocar_som:
    emitir_som_beep()
    st.session_state.tocar_som = False

# ------------------------------------------------------------
# 4. CONEXÃO BANCO DE DADOS (SUPABASE) - TABELAS V2 (CÓDIGO)
# ------------------------------------------------------------
DATABASE_URL = st.secrets.get("DATABASE_URL", os.environ.get("DATABASE_URL"))
SENHA_OPERADOR = st.secrets.get("SENHA_OPERADOR", "admin123")
SENHA_ADMIN = st.secrets.get("SENHA_ADMIN", "admin123")

if not DATABASE_URL:
    st.error("DATABASE_URL não configurada.")
    st.stop()

def conectar_bd():
    return psycopg2.connect(DATABASE_URL)

def inicializar_tabelas():
    conn = conectar_bd()
    cur = conn.cursor()
    # Criando tabelas V2 para suportar CÓDIGO como identificador principal
    cur.execute('''
        CREATE TABLE IF NOT EXISTS alunos_v2 (
            codigo TEXT PRIMARY KEY,
            nome TEXT,
            turma TEXT
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS registros_v2 (
            id SERIAL PRIMARY KEY,
            codigo_aluno TEXT REFERENCES alunos_v2(codigo),
            data DATE,
            hora_entrada TIME,
            status_entrada TEXT,
            hora_saida TIME,
            motivo_saida TEXT,
            pais_informados BOOLEAN,
            tipo_registro TEXT,
            UNIQUE(codigo_aluno, data, tipo_registro)
        )
    ''')
    conn.commit()
    conn.close()

inicializar_tabelas()

# ------------------------------------------------------------
# 5. FUNÇÕES DE NEGÓCIO (LÓGICA)
# ------------------------------------------------------------
def carregar_alunos():
    conn = conectar_bd()
    df = pd.read_sql_query("SELECT codigo, nome, turma FROM alunos_v2 ORDER BY turma, nome", conn)
    conn.close()
    return df

def importar_csv_para_bd(arquivo_csv):
    conteudo = arquivo_csv.read()
    if conteudo.startswith(b'\xef\xbb\xbf'): conteudo = conteudo[3:]
    try:
        df = pd.read_csv(io.BytesIO(conteudo), sep=';', encoding='utf-8')
    except:
        df = pd.read_csv(io.BytesIO(conteudo), sep=None, engine='python')
    
    # Padroniza nomes das colunas removendo acentos
    df.columns = [col.strip().upper().replace('Ó', 'O') for col in df.columns]
    
    if 'CODIGO' not in df.columns or 'NOME' not in df.columns or 'TURMA' not in df.columns:
        st.error("O CSV precisa conter as colunas: CODIGO, NOME e TURMA.")
        return False
        
    conn = conectar_bd()
    cur = conn.cursor()
    for _, row in df.iterrows():
        codigo = str(row['CODIGO']).strip().upper()
        nome = str(row['NOME']).strip().upper()
        turma = str(row['TURMA']).strip().upper()
        try:
            cur.execute("INSERT INTO alunos_v2 (codigo, nome, turma) VALUES (%s, %s, %s) ON CONFLICT (codigo) DO UPDATE SET nome = EXCLUDED.nome, turma = EXCLUDED.turma", 
                        (codigo, nome, turma))
        except Exception as e:
            conn.rollback()
    conn.commit()
    conn.close()
    return True

def registrar_presenca(codigo_estudante, data_registro, hora_limite_entrada):
    agora = datetime.now()
    hora_atual = agora.strftime("%H:%M:%S")
    status = "PRESENTE" if agora.time() <= hora_limite_entrada else "ATRASO"
    
    conn = conectar_bd()
    cur = conn.cursor()
    
    # Busca o nome pelo código para feedback visual
    cur.execute("SELECT nome FROM alunos_v2 WHERE codigo = %s", (codigo_estudante,))
    resultado = cur.fetchone()
    
    if not resultado:
        st.error(f"❌ Código não encontrado: {codigo_estudante}")
        conn.close()
        return False
        
    nome_aluno = resultado[0]
        
    cur.execute("SELECT * FROM registros_v2 WHERE codigo_aluno = %s AND data = %s AND tipo_registro = 'PRESENCA'", (codigo_estudante, data_registro))
    if cur.fetchone():
        st.warning(f"⚠️ {nome_aluno} já registou entrada hoje.")
        conn.close()
        return False
        
    cur.execute("DELETE FROM registros_v2 WHERE codigo_aluno = %s AND data = %s AND tipo_registro = 'FALTA'", (codigo_estudante, data_registro))
    try:
        cur.execute("INSERT INTO registros_v2 (codigo_aluno, data, hora_entrada, status_entrada, tipo_registro) VALUES (%s, %s, %s, %s, 'PRESENCA')",
                    (codigo_estudante, data_registro, hora_atual, status))
        conn.commit()
        if status == "PRESENTE": st.success(f"✅ {nome_aluno} registado às {hora_atual}")
        else: st.warning(f"⏰ Atraso: {nome_aluno} às {hora_atual}")
        return True # Retorna True para acionar o Bip!
    except:
        conn.rollback()
        return False
    finally: conn.close()

def registrar_saida(codigo_estudante, motivo, pais_informados, data_registro, hora_saida, hora_limite_saida):
    conn = conectar_bd()
    cur = conn.cursor()
    
    cur.execute("SELECT nome FROM alunos_v2 WHERE codigo = %s", (codigo_estudante,))
    resultado = cur.fetchone()
    if not resultado:
        st.error(f"❌ Código não encontrado.")
        conn.close()
        return False
    nome_aluno = resultado[0]

    hora_atual = datetime.now().time()
    if hora_atual < hora_limite_saida:
        cur.execute("UPDATE registros_v2 SET hora_saida = %s, motivo_saida = %s, pais_informados = %s WHERE codigo_aluno = %s AND data = %s AND tipo_registro = 'PRESENCA'", 
                    (hora_saida, motivo, pais_informados, codigo_estudante, data_registro))
        if cur.rowcount > 0:
            st.success(f"✅ Saída de {nome_aluno} registada")
            conn.commit()
            conn.close()
            return True
        else: st.error("Erro: sem registo de entrada hoje para efetuar saída.")
    else: st.info("Saída dentro do horário normal.")
    conn.close()
    return False

def limpar_todos_registros():
    conn = conectar_bd()
    cur = conn.cursor()
    cur.execute("DELETE FROM registros_v2")
    conn.commit()
    conn.close()

# ------------------------------------------------------------
# 6. COMPONENTE LEITOR QR INTELIGENTE (Câmera c/ Auto-Submit)
# ------------------------------------------------------------
def qr_scanner_auto(label_alvo, botao_alvo):
    html_code = f"""
    <div id="reader-qr" style="width:100%; max-width:350px; margin:auto; border-radius:10px; overflow:hidden; border: 2px solid #0f2b4a; display:none;"></div>
    
    <div style="text-align: center; margin-top: 15px; display: flex; flex-direction: column; gap: 10px; align-items: center;">
        <button id="btn-start" style="padding: 12px 24px; background: #0f2b4a; color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: bold; width: 100%; max-width: 350px;">
            📷 Ligar Câmera
        </button>
        <button id="btn-stop" style="display:none; padding: 12px 24px; background: #e74c3c; color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: bold; width: 100%; max-width: 350px;">
            🛑 Desligar Câmera
        </button>
    </div>

    <script src="https://unpkg.com/html5-qrcode"></script>
    <script>
        const html5QrCode = new Html5Qrcode("reader-qr");
        const btnStart = document.getElementById("btn-start");
        const btnStop = document.getElementById("btn-stop");
        const readerDiv = document.getElementById("reader-qr");
        
        const preencherEEnviar = (text) => {{
            const inputs = window.parent.document.querySelectorAll('input[type="text"]');
            for (let i = 0; i < inputs.length; i++) {{
                if (inputs[i].getAttribute('aria-label') === '{label_alvo}') {{
                    // Preenche o campo de texto
                    let nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
                    nativeInputValueSetter.call(inputs[i], text);
                    inputs[i].dispatchEvent(new Event('input', {{ bubbles: true}}));
                    
                    // Encontra e clica no botão oculto de submissão do Streamlit
                    setTimeout(() => {{
                        const buttons = window.parent.document.querySelectorAll('button');
                        for (let j = 0; j < buttons.length; j++) {{
                            if (buttons[j].innerText.includes('{botao_alvo}')) {{
                                buttons[j].click();
                                break;
                            }}
                        }}
                    }}, 50); // Delay mínimo para garantir o preenchimento
                    break;
                }}
            }}
        }};

        btnStart.onclick = () => {{
            btnStart.style.display = 'none';
            btnStop.style.display = 'inline-block';
            readerDiv.style.display = 'block';
            
            html5QrCode.start(
                {{ facingMode: "environment" }},
                {{ fps: 15, qrbox: {{ width: 250, height: 250 }} }},
                (decodedText) => {{
                    preencherEEnviar(decodedText);
                    // Deixa a câmera ligada para ler o próximo da fila!
                }},
                (errorMessage) => {{}}
            ).catch(err => {{
                alert("Permissão de câmera negada ou erro.");
                btnStart.style.display = 'inline-block';
                btnStop.style.display = 'none';
                readerDiv.style.display = 'none';
            }});
        }};

        btnStop.onclick = () => {{
            html5QrCode.stop().then(() => {{
                btnStart.style.display = 'inline-block';
                btnStop.style.display = 'none';
                readerDiv.style.display = 'none';
            }});
        }};
    </script>
    """
    components.html(html_code, height=450)

# ------------------------------------------------------------
# 7. AUTENTICAÇÃO PERSISTENTE
# ------------------------------------------------------------
def check_auth():
    if "autenticado" not in st.session_state:
        auth_cookie = cookies.get("auth_token")
        if auth_cookie:
            try:
                data = json.loads(base64.b64decode(auth_cookie).decode())
                if data.get("valido"):
                    st.session_state.autenticado = True
                    st.session_state.eh_admin = data.get("eh_admin", False)
                    return
            except: pass
        st.session_state.autenticado = False
        st.session_state.eh_admin = False

def set_auth_cookie(eh_admin):
    token = base64.b64encode(json.dumps({"valido": True, "eh_admin": eh_admin}).encode()).decode()
    cookies["auth_token"] = token
    cookies.save()

check_auth()

if not st.session_state.autenticado:
    st.markdown('<div class="login-card">', unsafe_allow_html=True)
    if os.path.exists("logo.png"): st.image("logo.png", width=150)
    st.markdown('<div class="login-title">Centro Educa Mais Jansen Veloso</div>', unsafe_allow_html=True)
    senha = st.text_input("Senha", type="password")
    if st.button("Entrar", use_container_width=True):
        if senha == SENHA_ADMIN: st.session_state.autenticado = True; st.session_state.eh_admin = True; set_auth_cookie(True); st.rerun()
        elif senha == SENHA_OPERADOR: st.session_state.autenticado = True; st.session_state.eh_admin = False; set_auth_cookie(False); st.rerun()
        else: st.error("Senha incorreta!")
    st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# ------------------------------------------------------------
# 8. INTERFACE PRINCIPAL DO SISTEMA
# ------------------------------------------------------------
if os.path.exists("logo.png"):
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2: st.image("logo.png", use_column_width=True)

st.markdown('<p class="main-title">Sistema de Frequência</p>', unsafe_allow_html=True)
st.markdown(f'<p class="sub-title">Centro Educa Mais Jansen Veloso • {datetime.now().strftime("%d de %B de %Y")}</p>', unsafe_allow_html=True)

col_logout1, col_logout2 = st.columns([4, 1])
with col_logout2:
    if st.button("Sair", key="logout"):
        cookies["auth_token"] = ""; cookies.save(); st.session_state.autenticado = False; st.rerun()

df_alunos = carregar_alunos()
if df_alunos.empty:
    if st.session_state.eh_admin:
        st.warning("Banco de dados V2 vazio. Importe o CSV contendo CODIGO, NOME e TURMA.")
        up = st.file_uploader("Subir CSV", type=["csv"])
        if up and importar_csv_para_bd(up): st.success("Sucesso!"); st.rerun()
    else: st.error("Sistema sem dados."); st.stop()
if df_alunos.empty: st.stop()

hoje_str = datetime.now().strftime("%Y-%m-%d")
conn = conectar_bd()
total = len(df_alunos)
presentes_hoje = pd.read_sql_query("SELECT COUNT(*) FROM registros_v2 WHERE data=%s AND tipo_registro='PRESENCA'", conn, params=[hoje_str]).iloc[0,0]
faltas_hoje = pd.read_sql_query("SELECT COUNT(*) FROM registros_v2 WHERE data=%s AND tipo_registro='FALTA'", conn, params=[hoje_str]).iloc[0,0]
atrasos_hoje = pd.read_sql_query("SELECT COUNT(*) FROM registros_v2 WHERE data=%s AND tipo_registro='PRESENCA' AND status_entrada='ATRASO'", conn, params=[hoje_str]).iloc[0,0]
conn.close()

st.markdown('<div class="metric-grid">', unsafe_allow_html=True)
st.markdown(f'<div class="metric-item"><div class="metric-value">{total}</div><div class="metric-label">📋 Alunos</div></div>', unsafe_allow_html=True)
st.markdown(f'<div class="metric-item" style="border-bottom-color: #27ae60;"><div class="metric-value">{presentes_hoje}</div><div class="metric-label">✅ Presentes</div></div>', unsafe_allow_html=True)
st.markdown(f'<div class="metric-item" style="border-bottom-color: #e74c3c;"><div class="metric-value">{faltas_hoje}</div><div class="metric-label">❌ Faltas</div></div>', unsafe_allow_html=True)
st.markdown(f'<div class="metric-item" style="border-bottom-color: #f39c12;"><div class="metric-value">{atrasos_hoje}</div><div class="metric-label">⏰ Atrasos</div></div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

abas = ["📝 Registro do Dia", "📊 Gestão", "🚨 Alertas", "📈 Histórico", "⚙️ Manutenção"] if st.session_state.eh_admin else ["📝 Registro do Dia", "📊 Gestão", "🚨 Alertas", "📈 Histórico"]
tabs = st.tabs(abas)

# ============================ ABA 0: REGISTRO DO DIA ============================
with tabs[0]:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    with col1: data_registro = st.date_input("Data do registro", datetime.now(), key="data_registro")
    data_str_config = data_registro.strftime("%Y-%m-%d")
    
    if "config_dia" not in st.session_state: st.session_state.config_dia = {}
    if data_str_config not in st.session_state.config_dia:
        st.session_state.config_dia[data_str_config] = {"hora_entrada": datetime.strptime("07:30", "%H:%M").time(), "hora_saida": datetime.strptime("17:00", "%H:%M").time()}
        
    with col2: hora_entrada = st.time_input("Horário limite", st.session_state.config_dia[data_str_config]["hora_entrada"], key="hora_entrada")
    with col3: hora_saida = st.time_input("Horário normal saída", st.session_state.config_dia[data_str_config]["hora_saida"], key="hora_saida")
    
    st.session_state.config_dia[data_str_config]["hora_entrada"] = hora_entrada
    st.session_state.config_dia[data_str_config]["hora_saida"] = hora_saida

    st.markdown("---")
    tab_entrada, tab_saida = st.tabs(["✅ Entrada", "🚪 Saída Antecipada"])

    # ---------- ENTRADA ----------
    with tab_entrada:
        label_entrada = "Insira o Código do Aluno"
        botao_entrada = "Processar Entrada"
        
        # Estrutura com colunas para alinhar input e botão
        c_in, c_btn = st.columns([3, 1])
        with c_in:
            codigo_recebido = st.text_input(label_entrada, key="input_entrada_real")
        with c_btn:
            st.markdown("<br>", unsafe_allow_html=True) # Espaçamento
            btn_submit_entrada = st.button(botao_entrada, use_container_width=True)
            
        qr_scanner_auto(label_entrada, botao_entrada)
        
        if btn_submit_entrada and codigo_recebido.strip():
            aluno_codigo = codigo_recebido.strip().upper()
            if registrar_presenca(aluno_codigo, data_str_config, hora_entrada):
                st.session_state.tocar_som = True
            del st.session_state["input_entrada_real"]
            st.rerun()

    # ---------- SAÍDA ----------
    with tab_saida:
        motivo = st.selectbox("Motivo", ["Consulta médica", "Mal-estar", "Outro"], key="motivo_saida")
        if motivo == "Outro": motivo = st.text_input("Especifique", key="motivo_outro")
        pais = st.radio("Pais informados?", ["Sim", "Não"], horizontal=True, key="pais_saida")
        
        label_saida = "Insira o Código para Saída"
        botao_saida = "Processar Saída"
        
        cs_in, cs_btn = st.columns([3, 1])
        with cs_in:
            codigo_saida_recebido = st.text_input(label_saida, key="input_saida_real")
        with cs_btn:
            st.markdown("<br>", unsafe_allow_html=True)
            btn_submit_saida = st.button(botao_saida, use_container_width=True)
            
        qr_scanner_auto(label_saida, botao_saida)
        
        if btn_submit_saida and codigo_saida_recebido.strip():
            aluno_saida_codigo = codigo_saida_recebido.strip().upper()
            if registrar_saida(aluno_saida_codigo, motivo, pais == "Sim", data_str_config, datetime.now().strftime("%H:%M:%S"), hora_saida):
                st.session_state.tocar_som = True
            del st.session_state["input_saida_real"]
            st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)

# ============================ ABA 1: GESTÃO ============================
with tabs[1]:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1: data_filtro = st.date_input("Data", datetime.now(), key="data_filtro")
    with c2: turma_filtro = st.selectbox("Turma", ["Todas"] + sorted(df_alunos['turma'].unique()), key="turma_filtro")
    with c3: busca = st.text_input("Buscar por Nome", key="busca")
    
    conn = conectar_bd()
    query = """
        SELECT r.data, a.turma, a.nome, r.hora_entrada, r.status_entrada, r.hora_saida 
        FROM registros_v2 r 
        JOIN alunos_v2 a ON r.codigo_aluno = a.codigo 
        WHERE r.data = %s
    """
    params = [data_filtro.strftime("%Y-%m-%d")]
    if turma_filtro != "Todas": query += " AND a.turma = %s"; params.append(turma_filtro)
    if busca: query += " AND a.nome ILIKE %s"; params.append(f"%{busca}%")
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.markdown('</div>', unsafe_allow_html=True)

# ============================ ABA 2: ALERTAS ============================
with tabs[2]:
    hoje = datetime.now()
    dias_uteis = [(hoje - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7) if (hoje - timedelta(days=i)).weekday() < 5][:5]
    conn = conectar_bd()
    if dias_uteis:
        df_risco = pd.read_sql_query("SELECT a.codigo, a.nome, a.turma FROM alunos_v2 a WHERE a.codigo NOT IN (SELECT DISTINCT codigo_aluno FROM registros_v2 WHERE data IN %s AND tipo_registro='PRESENCA')", conn, params=[tuple(dias_uteis)])
        st.subheader("🚨 Alunos sem presença nos últimos 5 dias úteis")
        if not df_risco.empty: st.error(f"{len(df_risco)} alunos em risco"); st.dataframe(df_risco, hide_index=True)
        else: st.success("Nenhum aluno nesta situação.")
    conn.close()

# ============================ ABA 3: HISTÓRICO ============================
with tabs[3]:
    st.subheader("📈 Histórico Individual do Aluno")
    
    # Cria uma lista formatada "CÓDIGO - NOME" para facilitar a seleção
    lista_selecao = [f"{row['codigo']} - {row['nome']}" for _, row in df_alunos.iterrows()]
    aluno_sel = st.selectbox("Selecione o aluno para análise", [""] + lista_selecao, key="hist_aluno")
    
    if aluno_sel:
        codigo_extraid = aluno_sel.split(" - ")[0]
        conn = conectar_bd()
        df_hist = pd.read_sql_query("SELECT data, tipo_registro, hora_entrada, status_entrada, hora_saida, motivo_saida FROM registros_v2 WHERE codigo_aluno = %s ORDER BY data DESC, hora_entrada DESC", conn, params=[codigo_extraid])
        conn.close()
        if not df_hist.empty: st.dataframe(df_hist, hide_index=True)

# ============================ ABA 4: MANUTENÇÃO ============================
if st.session_state.eh_admin:
    with tabs[4]:
        st.subheader("⚙️ Importação de Dados V2")
        st.write("Atualize a base enviando um CSV com as colunas **CODIGO**, **NOME** e **TURMA**.")
        up_admin = st.file_uploader("Arquivo CSV", type=["csv"], key="admin_csv")
        if up_admin and importar_csv_para_bd(up_admin):
            st.success("Lista atualizada com sucesso!"); st.rerun()
            
        st.subheader("🗑️ Limpeza de Base")
        senha_conf = st.text_input("Senha Admin", type="password", key="senha_limpar")
        if st.button("Apagar Histórico") and senha_conf == SENHA_ADMIN:
            limpar_todos_registros(); st.success("Registos apagados.")
