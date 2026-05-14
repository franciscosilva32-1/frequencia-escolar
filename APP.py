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

# ------------------------------------------------------------
# 2. COOKIES – SESSÃO PERSISTENTE
# ------------------------------------------------------------
cookies = CookieManager()
if not cookies.ready():
    st.stop()

# ------------------------------------------------------------
# 3. CSS MODERNO E RESPONSIVO
# ------------------------------------------------------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

    :root {
        --primary: #0f2b4a;
        --primary-light: #1e4a6b;
        --accent: #e67e22;
        --success: #27ae60;
        --danger: #e74c3c;
    }

    .stApp { background: linear-gradient(180deg, #f8fafc 0%, #e9edf2 100%); }
    #MainMenu, footer, header {visibility: hidden;}

    .header-container { display: flex; flex-direction: column; align-items: center; padding: 1rem 0 0.5rem; }
    .main-title { font-family: 'Inter', sans-serif; font-weight: 800; font-size: clamp(1.8rem, 6vw, 2.5rem); color: var(--primary); margin: 0; text-align: center; }
    .sub-title { font-family: 'Inter', sans-serif; font-size: 0.9rem; color: #5f6b7a; margin-bottom: 1.5rem; text-align: center; }

    .card { background: rgba(255,255,255,0.7); backdrop-filter: blur(10px); border-radius: 20px; padding: 1.2rem; margin-bottom: 1rem; box-shadow: 0 8px 20px rgba(0,0,0,0.04); border: 1px solid rgba(255,255,255,0.8); }

    .metric-grid { display: flex; flex-wrap: wrap; gap: 0.8rem; margin-bottom: 1.2rem; }
    .metric-item { flex: 1 1 100px; background: white; border-radius: 16px; padding: 0.8rem 0.5rem; text-align: center; border-bottom: 4px solid var(--accent); }
    .metric-value { font-family: 'Inter', sans-serif; font-weight: 800; font-size: 1.8rem; color: var(--primary); }
    .metric-label { font-family: 'Inter', sans-serif; font-size: 0.8rem; text-transform: uppercase; color: #5f6b7a; }

    .login-card { max-width: 380px; margin: 10vh auto; background: rgba(255,255,255,0.8); backdrop-filter: blur(16px); border-radius: 28px; padding: 2rem 1.5rem; text-align: center; }
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------
# 4. GESTÃO DO BIPE (AVISO SONORO)
# Esta função cria um pequeno gerador de áudio no navegador
# sem precisar de arquivos MP3 externos.
# ------------------------------------------------------------
def emitir_som_beep():
    html_beep = """
    <script>
        // Cria o contexto de áudio usando recursos nativos do navegador
        const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        const oscillator = audioCtx.createOscillator();
        const gainNode = audioCtx.createGain();
        
        // Conecta o som ao alto-falante
        oscillator.connect(gainNode);
        gainNode.connect(audioCtx.destination);
        
        // Define a frequência (800Hz é um bipe agudo agradável) e o volume
        oscillator.type = 'sine';
        oscillator.frequency.value = 800;
        
        // Inicia o som e reduz o volume rapidamente em 0.3 segundos
        oscillator.start();
        gainNode.gain.exponentialRampToValueAtTime(0.00001, audioCtx.currentTime + 0.3);
        oscillator.stop(audioCtx.currentTime + 0.3);
    </script>
    """
    # Injeta o código invisível na tela
    components.html(html_beep, height=0, width=0)

# Checa se o sistema foi instruído a tocar o bipe nesta atualização de tela
if "tocar_som" not in st.session_state:
    st.session_state.tocar_som = False

if st.session_state.tocar_som:
    emitir_som_beep()
    # Desliga a variável para não tocar novamente até o próximo registro
    st.session_state.tocar_som = False

# ------------------------------------------------------------
# 5. CONEXÃO BANCO DE DADOS (SUPABASE)
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
    cur.execute('''CREATE TABLE IF NOT EXISTS alunos (nome TEXT PRIMARY KEY, turma TEXT)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS registros (id SERIAL PRIMARY KEY, nome_aluno TEXT REFERENCES alunos(nome), data DATE, hora_entrada TIME, status_entrada TEXT, hora_saida TIME, motivo_saida TEXT, pais_informados BOOLEAN, tipo_registro TEXT, UNIQUE(nome_aluno, data, tipo_registro))''')
    conn.commit()
    conn.close()

inicializar_tabelas()

# ------------------------------------------------------------
# 6. FUNÇÕES DE NEGÓCIO (LÓGICA)
# ------------------------------------------------------------
def carregar_alunos():
    conn = conectar_bd()
    df = pd.read_sql_query("SELECT nome, turma FROM alunos ORDER BY turma, nome", conn)
    conn.close()
    return df

def importar_csv_para_bd(arquivo_csv):
    # Lógica de importação simplificada para poupar espaço visual
    conteudo = arquivo_csv.read()
    if conteudo.startswith(b'\xef\xbb\xbf'): conteudo = conteudo[3:]
    try:
        df = pd.read_csv(io.BytesIO(conteudo), sep=';', encoding='utf-8')
    except:
        df = pd.read_csv(io.BytesIO(conteudo), sep=None, engine='python')
    df.columns = [col.strip().upper() for col in df.columns]
    
    conn = conectar_bd()
    cur = conn.cursor()
    for _, row in df.iterrows():
        try: cur.execute("INSERT INTO alunos (nome, turma) VALUES (%s, %s)", (str(row['NOME']).strip().upper(), str(row['TURMA']).strip().upper()))
        except psycopg2.errors.UniqueViolation: conn.rollback()
    conn.commit()
    conn.close()
    return True

def registrar_presenca(nome_estudante, data_registro, hora_limite_entrada):
    agora = datetime.now()
    hora_atual = agora.strftime("%H:%M:%S")
    status = "PRESENTE" if agora.time() <= hora_limite_entrada else "ATRASO"
    
    conn = conectar_bd()
    cur = conn.cursor()
    cur.execute("SELECT nome FROM alunos WHERE nome = %s", (nome_estudante,))
    if not cur.fetchone():
        st.error(f"❌ Aluno não encontrado: {nome_estudante}")
        conn.close()
        return False
        
    cur.execute("SELECT * FROM registros WHERE nome_aluno = %s AND data = %s AND tipo_registro = 'PRESENCA'", (nome_estudante, data_registro))
    if cur.fetchone():
        st.warning(f"⚠️ {nome_estudante} já registou entrada neste dia.")
        conn.close()
        return False
        
    cur.execute("DELETE FROM registros WHERE nome_aluno = %s AND data = %s AND tipo_registro = 'FALTA'", (nome_estudante, data_registro))
    try:
        cur.execute("INSERT INTO registros (nome_aluno, data, hora_entrada, status_entrada, tipo_registro) VALUES (%s, %s, %s, %s, 'PRESENCA')",
                    (nome_estudante, data_registro, hora_atual, status))
        conn.commit()
        if status == "PRESENTE": st.success(f"✅ {nome_estudante} registado às {hora_atual}")
        else: st.warning(f"⏰ Atraso: {nome_estudante} às {hora_atual}")
        return True # Retorna True para acionar o Bip!
    except:
        conn.rollback()
        return False
    finally: conn.close()

def registrar_saida(nome, motivo, pais_informados, data_registro, hora_saida, hora_limite_saida):
    conn = conectar_bd()
    cur = conn.cursor()
    hora_atual = datetime.now().time()
    if hora_atual < hora_limite_saida:
        cur.execute("UPDATE registros SET hora_saida = %s, motivo_saida = %s, pais_informados = %s WHERE nome_aluno = %s AND data = %s AND tipo_registro = 'PRESENCA'", 
                    (hora_saida, motivo, pais_informados, nome, data_registro))
        if cur.rowcount > 0:
            st.success(f"✅ Saída de {nome} registada")
            conn.commit()
            conn.close()
            return True # Retorna True para acionar o Bip!
        else: st.error("Erro: sem registo de entrada hoje para efetuar saída.")
    else: st.info("Saída dentro do horário normal – não é considerada antecipada.")
    conn.close()
    return False

def gerar_faltas_para_dia(data_str):
    conn = conectar_bd()
    cur = conn.cursor()
    cur.execute("SELECT nome FROM alunos")
    for aluno in [row[0] for row in cur.fetchall()]:
        cur.execute("SELECT tipo_registro FROM registros WHERE nome_aluno = %s AND data = %s AND tipo_registro IN ('PRESENCA','FALTA')", (aluno, data_str))
        if not cur.fetchone():
            try: cur.execute("INSERT INTO registros (nome_aluno, data, tipo_registro) VALUES (%s, %s, 'FALTA')", (aluno, data_str))
            except: conn.rollback()
    conn.commit()
    conn.close()

def limpar_todos_registros():
    conn = conectar_bd()
    cur = conn.cursor()
    cur.execute("DELETE FROM registros")
    conn.commit()
    conn.close()

def obter_historico_aluno(nome_aluno):
    conn = conectar_bd()
    df = pd.read_sql_query("SELECT data, tipo_registro, hora_entrada, status_entrada, hora_saida, motivo_saida, pais_informados FROM registros WHERE nome_aluno = %s ORDER BY data DESC, hora_entrada DESC", conn, params=[nome_aluno])
    conn.close()
    return df

# ------------------------------------------------------------
# 7. COMPONENTE LEITOR QR INTELIGENTE (Câmera)
# Inclui botão explícito para parar a câmera.
# ------------------------------------------------------------
def qr_scanner_inteligente(label_alvo):
    html_code = f"""
    <div id="reader-qr" style="width:100%; max-width:350px; margin:auto; border-radius:10px; overflow:hidden;"></div>
    <div style="text-align: center; margin-top: 15px; display: flex; justify-content: center; gap: 10px;">
        <button id="btn-start" style="padding: 12px 24px; background: #0f2b4a; color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: bold; width: 100%;">
            📷 Iniciar Leitor
        </button>
        <button id="btn-stop" style="display:none; padding: 12px 24px; background: #e74c3c; color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: bold; width: 100%;">
            🛑 Parar Leitor
        </button>
    </div>

    <script src="https://unpkg.com/html5-qrcode"></script>
    <script>
        const html5QrCode = new Html5Qrcode("reader-qr");
        const btnStart = document.getElementById("btn-start");
        const btnStop = document.getElementById("btn-stop");
        
        const setInputValue = (text) => {{
            const inputs = window.parent.document.querySelectorAll('input[type="text"]');
            for (let i = 0; i < inputs.length; i++) {{
                if (inputs[i].getAttribute('aria-label') === '{label_alvo}') {{
                    let nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
                    nativeInputValueSetter.call(inputs[i], text);
                    let ev = new Event('input', {{ bubbles: true}});
                    inputs[i].dispatchEvent(ev);
                    
                    let enterEvent = new KeyboardEvent('keydown', {{ bubbles: true, cancelable: true, key: 'Enter', code: 'Enter', keyCode: 13 }});
                    inputs[i].dispatchEvent(enterEvent);
                    break;
                }}
            }}
        }};

        btnStart.onclick = () => {{
            btnStart.style.display = 'none';
            btnStop.style.display = 'inline-block';
            html5QrCode.start(
                {{ facingMode: "environment" }},
                {{ fps: 15, qrbox: {{ width: 250, height: 250 }} }},
                (decodedText) => {{
                    setInputValue(decodedText);
                    // Opcional: Parar após 1 leitura (Comentado para manter câmera ligada lendo vários)
                    // html5QrCode.stop().then(() => {{ btnStart.style.display = 'inline-block'; btnStop.style.display = 'none'; }});
                }},
                (errorMessage) => {{}}
            ).catch(err => {{
                alert("Erro ao acessar a câmera.");
                btnStart.style.display = 'inline-block';
                btnStop.style.display = 'none';
            }});
        }};

        // Botão manual de parada
        btnStop.onclick = () => {{
            html5QrCode.stop().then(() => {{
                btnStart.style.display = 'inline-block';
                btnStop.style.display = 'none';
            }}).catch(err => console.error("Falha ao parar: ", err));
        }};
    </script>
    """
    components.html(html_code, height=350)

# ------------------------------------------------------------
# 8. AUTENTICAÇÃO PERSISTENTE
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
    if os.path.exists("logo.png"):
        col_l1, col_l2, col_l3 = st.columns([1, 1, 1])
        with col_l2: st.image("logo.png", use_column_width=True)
    st.markdown('<div class="login-title">Centro Educa Mais Jansen Veloso</div>', unsafe_allow_html=True)
    senha = st.text_input("Senha", type="password")
    if st.button("Entrar", use_container_width=True):
        if senha == SENHA_ADMIN:
            st.session_state.autenticado = True; st.session_state.eh_admin = True; set_auth_cookie(True); st.rerun()
        elif senha == SENHA_OPERADOR:
            st.session_state.autenticado = True; st.session_state.eh_admin = False; set_auth_cookie(False); st.rerun()
        else: st.error("Senha incorreta!")
    st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# ------------------------------------------------------------
# 9. INTERFACE PRINCIPAL DO SISTEMA
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
        st.warning("Banco de dados vazio. Importe o CSV.")
        up = st.file_uploader("Subir CSV", type=["csv"])
        if up and importar_csv_para_bd(up): st.success("Sucesso!"); st.stop()
    else: st.error("Sistema sem dados."); st.stop()
if df_alunos.empty: st.stop()

hoje_str = datetime.now().strftime("%Y-%m-%d")
conn = conectar_bd()
total = len(df_alunos)
presentes_hoje = pd.read_sql_query("SELECT COUNT(*) FROM registros WHERE data=%s AND tipo_registro='PRESENCA'", conn, params=[hoje_str]).iloc[0,0]
faltas_hoje = pd.read_sql_query("SELECT COUNT(*) FROM registros WHERE data=%s AND tipo_registro='FALTA'", conn, params=[hoje_str]).iloc[0,0]
atrasos_hoje = pd.read_sql_query("SELECT COUNT(*) FROM registros WHERE data=%s AND tipo_registro='PRESENCA' AND status_entrada='ATRASO'", conn, params=[hoje_str]).iloc[0,0]
conn.close()

st.markdown('<div class="metric-grid">', unsafe_allow_html=True)
st.markdown(f'<div class="metric-item"><div class="metric-value">{total}</div><div class="metric-label">📋 Alunos</div></div>', unsafe_allow_html=True)
st.markdown(f'<div class="metric-item" style="border-bottom-color: #27ae60;"><div class="metric-value">{presentes_hoje}</div><div class="metric-label">✅ Presentes</div></div>', unsafe_allow_html=True)
st.markdown(f'<div class="metric-item" style="border-bottom-color: #e74c3c;"><div class="metric-value">{faltas_hoje}</div><div class="metric-label">❌ Faltas</div></div>', unsafe_allow_html=True)
st.markdown(f'<div class="metric-item" style="border-bottom-color: #f39c12;"><div class="metric-value">{atrasos_hoje}</div><div class="metric-label">⏰ Atrasos</div></div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

abas = ["📝 Registro do Dia", "📊 Gestão", "🚨 Alertas", "⭐ Pontualidade", "📈 Histórico"]
if st.session_state.eh_admin: abas.append("⚙️ Manutenção")
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

    with tab_entrada:
        label_entrada = "Código QR / Leitura Entrada"
        codigo_recebido = st.text_input(label_entrada, key="input_entrada_real")
        
        qr_scanner_inteligente(label_entrada)
        
        if codigo_recebido and codigo_recebido.strip():
            aluno = codigo_recebido.strip().upper()
            sucesso = registrar_presenca(aluno, data_str_config, hora_entrada)
            
            if sucesso:
                # Aciona a variável para o som tocar na próxima renderização de tela!
                st.session_state.tocar_som = True
                
            del st.session_state["input_entrada_real"]
            st.rerun()

    with tab_saida:
        motivo = st.selectbox("Motivo", ["Consulta médica", "Mal-estar", "Outro"], key="motivo_saida")
        if motivo == "Outro": motivo = st.text_input("Especifique", key="motivo_outro")
        pais = st.radio("Pais informados?", ["Sim", "Não"], horizontal=True, key="pais_saida")
        
        label_saida = "Código QR / Leitura Saída"
        codigo_saida_recebido = st.text_input(label_saida, key="input_saida_real")
        
        qr_scanner_inteligente(label_saida)
        
        if codigo_saida_recebido and codigo_saida_recebido.strip():
            aluno_saida = codigo_saida_recebido.strip().upper()
            sucesso_saida = registrar_saida(aluno_saida, motivo, pais == "Sim", data_str_config, datetime.now().strftime("%H:%M:%S"), hora_saida)
            
            if sucesso_saida:
                # Aciona o bip sonoro!
                st.session_state.tocar_som = True
                
            del st.session_state["input_saida_real"]
            st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)

# ============================ ABA 1 A 5 MANTIDAS INTEGRALMENTE ============================
with tabs[1]:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1: data_filtro = st.date_input("Data", datetime.now(), key="data_filtro")
    with c2: turma_filtro = st.selectbox("Turma", ["Todas"] + sorted(df_alunos['turma'].unique()), key="turma_filtro")
    with c3: busca = st.text_input("Buscar aluno", key="busca")
    
    conn = conectar_bd()
    query = "SELECT r.data, a.turma, r.nome_aluno, r.hora_entrada, r.status_entrada, r.hora_saida FROM registros r JOIN alunos a ON r.nome_aluno = a.nome WHERE r.data = %s"
    params = [data_filtro.strftime("%Y-%m-%d")]
    if turma_filtro != "Todas": query += " AND a.turma = %s"; params.append(turma_filtro)
    if busca: query += " AND r.nome_aluno ILIKE %s"; params.append(f"%{busca}%")
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    
    st.dataframe(df, use_container_width=True, hide_index=True)
    if st.button("🔄 Gerar faltas para o dia"): gerar_faltas_para_dia(data_filtro.strftime("%Y-%m-%d")); st.success("Faltas geradas!"); st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

with tabs[2]:
    hoje = datetime.now()
    dias_uteis = [(hoje - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7) if (hoje - timedelta(days=i)).weekday() < 5][:5]
    conn = conectar_bd()
    if dias_uteis:
        df_risco = pd.read_sql_query("SELECT a.nome, a.turma FROM alunos a WHERE a.nome NOT IN (SELECT DISTINCT nome_aluno FROM registros WHERE data IN %s AND tipo_registro='PRESENCA')", conn, params=[tuple(dias_uteis)])
        st.subheader("🚨 Alunos sem presença nos últimos 5 dias úteis")
        if not df_risco.empty: st.error(f"{len(df_risco)} alunos em risco de abandono escolar"); st.dataframe(df_risco, hide_index=True)
        else: st.success("Nenhum aluno nesta situação.")
    conn.close()

with tabs[3]:
    st.subheader("⭐ Destaques de Pontualidade (Hoje antes das 07:15)")
    conn = conectar_bd()
    df_pontuais = pd.read_sql_query("SELECT r.nome_aluno, a.turma, r.hora_entrada FROM registros r JOIN alunos a ON r.nome_aluno=a.nome WHERE r.data=%s AND r.tipo_registro='PRESENCA' AND r.hora_entrada <= '07:15:00' ORDER BY r.hora_entrada", conn, params=[hoje_str])
    conn.close()
    if not df_pontuais.empty: st.success(f"{len(df_pontuais)} alunos chegaram com antecedência."); st.dataframe(df_pontuais, hide_index=True)

with tabs[4]:
    st.subheader("📈 Histórico Individual do Aluno")
    aluno_sel = st.selectbox("Selecione o aluno para análise", sorted(df_alunos['nome'].tolist()), key="hist_aluno")
    if aluno_sel:
        df_hist = obter_historico_aluno(aluno_sel)
        if not df_hist.empty: st.dataframe(df_hist, hide_index=True)

if st.session_state.eh_admin:
    with tabs[5]:
        st.subheader("🗑️ Limpeza de Base")
        senha_conf = st.text_input("Senha Admin", type="password", key="senha_limpar")
        if st.button("Apagar Histórico") and senha_conf == SENHA_ADMIN:
            limpar_todos_registros(); st.success("Registos apagados.")
