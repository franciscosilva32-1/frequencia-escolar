import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import psycopg2
import os
import io
import base64
import json
import unicodedata
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
# 2. CSS MODERNO, RESPONSIVO E CHAMATIVO (NOVO DESIGN)
# ------------------------------------------------------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
    
    :root { 
        --primary: #0f2b4a; 
        --accent: #e67e22; 
        --success: #27ae60; 
        --danger: #e74c3c; 
        --bg-color: #f0f4f8;
    }
    
    .stApp { background: var(--bg-color); }
    #MainMenu, footer, header {visibility: hidden;}
    
    /* Títulos */
    .main-title { font-family: 'Inter', sans-serif; font-weight: 800; font-size: clamp(2rem, 6vw, 2.8rem); color: var(--primary); text-align: center; margin:0;}
    .sub-title { font-family: 'Inter', sans-serif; font-size: 1rem; color: #34495e; text-align: center; margin-bottom: 1.5rem; font-weight: 600;}
    
    /* Cards e Métricas */
    .card { background: white; border-radius: 20px; padding: 1.5rem; margin-bottom: 1rem; box-shadow: 0 10px 25px rgba(0,0,0,0.08); border: 2px solid #e1e8ed; }
    .metric-item { background: #ffffff; border-radius: 16px; padding: 1rem; text-align: center; border-bottom: 5px solid var(--accent); box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
    .metric-value { font-family: 'Inter', sans-serif; font-weight: 800; font-size: 2rem; color: var(--primary); }
    .metric-label { font-size: 0.85rem; font-weight: 600; text-transform: uppercase; color: #5f6b7a; }
    
    /* CAMPOS DE DIGITAÇÃO E SENHAS MAIS VISÍVEIS */
    .stTextInput > div > div > input, .stSelectbox > div > div > div {
        border: 2px solid var(--primary) !important;
        border-radius: 12px !important;
        background-color: #ffffff !important;
        color: #000000 !important;
        font-weight: 600 !important;
        font-size: 1.1rem !important;
        padding: 0.6rem 1rem !important;
        box-shadow: 0 4px 6px rgba(15, 43, 74, 0.1) !important;
    }
    
    /* Efeito ao clicar no campo */
    .stTextInput > div > div > input:focus, .stSelectbox > div > div > div:focus {
        border-color: var(--accent) !important;
        box-shadow: 0 0 0 4px rgba(230, 126, 34, 0.3) !important;
    }

    /* Botões mais chamativos */
    .stButton > button {
        border-radius: 12px !important;
        font-weight: 800 !important;
        font-size: 1.1rem !important;
        padding: 0.6rem 1.5rem !important;
        transition: all 0.3s ease !important;
        border: 2px solid transparent !important;
    }
    
    /* Botão de Submit do Form (Processar) */
    [data-testid="stFormSubmitButton"] > button {
        background: linear-gradient(135deg, var(--primary), #1a4b82) !important;
        color: white !important;
        box-shadow: 0 6px 15px rgba(15, 43, 74, 0.3) !important;
    }
    [data-testid="stFormSubmitButton"] > button:hover {
        background: linear-gradient(135deg, #1a4b82, var(--primary)) !important;
        transform: translateY(-2px);
    }

    /* Tela de Login */
    .login-card { max-width: 400px; margin: 8vh auto; background: white; border-radius: 28px; padding: 2.5rem 2rem; text-align: center; box-shadow: 0 25px 50px rgba(0,0,0,0.15); border: 3px solid var(--primary); }
    .login-title { font-family: 'Inter', sans-serif; font-weight: 800; font-size: 1.6rem; color: var(--primary); margin-bottom: 1.5rem; }
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------
# 3. CONEXÃO BANCO DE DADOS (SUPABASE)
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
    cur.execute('''CREATE TABLE IF NOT EXISTS alunos_v2 (codigo TEXT PRIMARY KEY, nome TEXT, turma TEXT)''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS registros_v2 (
            id SERIAL PRIMARY KEY, codigo_aluno TEXT REFERENCES alunos_v2(codigo), data DATE, hora_entrada TIME,
            status_entrada TEXT, hora_saida TIME, motivo_saida TEXT, pais_informados BOOLEAN, tipo_registro TEXT,
            UNIQUE(codigo_aluno, data, tipo_registro)
        )
    ''')
    conn.commit()
    conn.close()

inicializar_tabelas()

# ------------------------------------------------------------
# 4. FUNÇÕES DE NEGÓCIO
# ------------------------------------------------------------
def carregar_alunos():
    conn = conectar_bd()
    df = pd.read_sql_query("SELECT codigo, nome, turma FROM alunos_v2 ORDER BY turma, nome", conn)
    conn.close()
    return df

def importar_csv_para_bd(arquivo_csv):
    conteudo = arquivo_csv.read()
    try: texto = conteudo.decode('utf-8-sig')
    except: texto = conteudo.decode('latin-1')
        
    df = pd.read_csv(io.StringIO(texto), sep=';')
    
    def normalizar_coluna(nome_col):
        s = ''.join(c for c in unicodedata.normalize('NFD', str(nome_col)) if unicodedata.category(c) != 'Mn')
        return s.strip().upper()
    
    df.columns = [normalizar_coluna(col) for col in df.columns]
    if 'CODIGO' not in df.columns or 'NOME' not in df.columns or 'TURMA' not in df.columns:
        st.error(f"Erro: O CSV precisa conter CODIGO, NOME e TURMA.")
        return False
        
    conn = conectar_bd()
    cur = conn.cursor()
    for _, row in df.iterrows():
        codigo = str(row['CODIGO']).strip().upper()
        nome = str(row['NOME']).strip().upper()
        turma = str(row['TURMA']).strip().upper()
        if codigo == 'NAN' or nome == 'NAN': continue
        try: cur.execute("INSERT INTO alunos_v2 (codigo, nome, turma) VALUES (%s, %s, %s) ON CONFLICT (codigo) DO UPDATE SET nome = EXCLUDED.nome, turma = EXCLUDED.turma", (codigo, nome, turma))
        except: conn.rollback()
    conn.commit()
    conn.close()
    return True

def abrir_dia_letivo(data_str):
    conn = conectar_bd()
    cur = conn.cursor()
    cur.execute("SELECT codigo FROM alunos_v2")
    alunos = [row[0] for row in cur.fetchall()]
    
    faltas_geradas = 0
    for codigo in alunos:
        cur.execute("SELECT id FROM registros_v2 WHERE codigo_aluno = %s AND data = %s", (codigo, data_str))
        if not cur.fetchone():
            try:
                cur.execute("INSERT INTO registros_v2 (codigo_aluno, data, tipo_registro) VALUES (%s, %s, 'FALTA')", (codigo, data_str))
                faltas_geradas += 1
            except: conn.rollback()
    conn.commit()
    conn.close()
    return faltas_geradas

def registrar_presenca(codigo_estudante, data_registro, hora_limite_entrada):
    agora = datetime.now()
    hora_atual = agora.strftime("%H:%M:%S")
    status = "PRESENTE" if agora.time() <= hora_limite_entrada else "ATRASO"
    
    conn = conectar_bd()
    cur = conn.cursor()
    cur.execute("SELECT nome FROM alunos_v2 WHERE codigo = %s", (codigo_estudante,))
    resultado = cur.fetchone()
    if not resultado:
        st.error(f"❌ Código não cadastrado: {codigo_estudante}")
        conn.close()
        return False
        
    nome_aluno = resultado[0]
    cur.execute("SELECT * FROM registros_v2 WHERE codigo_aluno = %s AND data = %s AND tipo_registro = 'PRESENCA'", (codigo_estudante, data_registro))
    if cur.fetchone():
        st.warning(f"⚠️ {nome_aluno} já passou na catraca hoje.")
        conn.close()
        return False
        
    cur.execute("DELETE FROM registros_v2 WHERE codigo_aluno = %s AND data = %s AND tipo_registro = 'FALTA'", (codigo_estudante, data_registro))
    
    try:
        cur.execute("INSERT INTO registros_v2 (codigo_aluno, data, hora_entrada, status_entrada, tipo_registro) VALUES (%s, %s, %s, %s, 'PRESENCA')",
                    (codigo_estudante, data_registro, hora_atual, status))
        conn.commit()
        if status == "PRESENTE": st.success(f"✅ {nome_aluno} - PRESENTE")
        else: st.warning(f"⏰ {nome_aluno} - ATRASO ({hora_atual})")
        return True
    except: conn.rollback(); return False
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
            st.success(f"✅ Saída autorizada: {nome_aluno}")
            conn.commit()
            conn.close()
            return True
        else: st.error("Erro: Aluno não tem registro de entrada hoje.")
    else: st.info("Saída no horário normal.")
    conn.close()
    return False

def limpar_todos_registros():
    conn = conectar_bd()
    cur = conn.cursor()
    cur.execute("DELETE FROM registros_v2")
    conn.commit()
    conn.close()

# ------------------------------------------------------------
# 5. COMPONENTE DA CÂMERA BLINDADO (Não trava mais)
# ------------------------------------------------------------
def gerar_componente_camera(label_alvo, botao_alvo, id_camera):
    html_code = f"""
    <div id="box-camera" style="width:100%; max-width:350px; margin:auto; border-radius:12px; overflow:hidden; border: 4px solid #e67e22; background: #000; display:none; box-shadow: 0 10px 20px rgba(0,0,0,0.2);">
        <div id="reader-qr-{id_camera}" style="width:100%;"></div>
    </div>
    
    <div style="text-align: center; margin-top: 15px; display: flex; gap: 10px; justify-content: center;">
        <button id="btn-start" style="padding: 12px 20px; background: #27ae60; color: white; border: none; border-radius: 10px; cursor: pointer; font-weight: bold; width: 100%; max-width: 170px; font-size: 1rem; box-shadow: 0 4px 6px rgba(39, 174, 96, 0.3);">
            📷 Ligar Câmera
        </button>
        <button id="btn-stop" style="display:none; padding: 12px 20px; background: #e74c3c; color: white; border: none; border-radius: 10px; cursor: pointer; font-weight: bold; width: 100%; max-width: 170px; font-size: 1rem; box-shadow: 0 4px 6px rgba(231, 76, 60, 0.3);">
            🛑 Parar
        </button>
    </div>

    <script src="https://unpkg.com/html5-qrcode"></script>
    <script>
        const html5QrCode = new Html5Qrcode("reader-qr-{id_camera}");
        const btnStart = document.getElementById("btn-start");
        const btnStop = document.getElementById("btn-stop");
        const boxCamera = document.getElementById("box-camera");
        
        let isProcessing = false;
        let audioCtx = null;
        
        function unlockAudio() {{
            if (!audioCtx) {{ audioCtx = new (window.AudioContext || window.webkitAudioContext)(); }}
            if (audioCtx.state === 'suspended') {{ audioCtx.resume(); }}
            try {{
                const osc = audioCtx.createOscillator();
                osc.connect(audioCtx.destination);
                osc.start(0);
                osc.stop(0.001);
            }} catch(e) {{}}
        }}

        function playBeep() {{
            if(!audioCtx) return;
            try {{
                const oscillator = audioCtx.createOscillator();
                const gainNode = audioCtx.createGain();
                oscillator.connect(gainNode);
                gainNode.connect(audioCtx.destination);
                oscillator.type = 'sine';
                oscillator.frequency.value = 900; 
                oscillator.start();
                gainNode.gain.exponentialRampToValueAtTime(0.00001, audioCtx.currentTime + 0.15); 
                oscillator.stop(audioCtx.currentTime + 0.15);
            }} catch(e) {{ console.log("Erro no beep", e); }}
        }}

        const ligarCamera = () => {{
            unlockAudio(); 
            btnStart.style.display = 'none';
            btnStop.style.display = 'inline-block';
            boxCamera.style.display = 'block';
            
            // Reseta a trava de segurança forçadamente caso tenha ficado presa
            isProcessing = false;
            
            html5QrCode.start(
                {{ facingMode: "environment" }},
                {{ fps: 15, qrbox: {{ width: 250, height: 250 }} }},
                (decodedText) => {{
                    if (!isProcessing) {{
                        isProcessing = true;
                        playBeep(); 
                        
                        let enviou = false;
                        const inputs = window.parent.document.querySelectorAll('input[type="text"]');
                        for (let i = 0; i < inputs.length; i++) {{
                            if (inputs[i].getAttribute('aria-label') && inputs[i].getAttribute('aria-label').includes('{label_alvo}')) {{
                                
                                let nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
                                nativeSetter.call(inputs[i], decodedText);
                                inputs[i].dispatchEvent(new Event('input', {{ bubbles: true}}));
                                
                                const buttons = window.parent.document.querySelectorAll('button');
                                for (let j = 0; j < buttons.length; j++) {{
                                    if (buttons[j].innerText.includes('{botao_alvo}')) {{
                                        buttons[j].click();
                                        enviou = true;
                                        break;
                                    }}
                                }}
                                break;
                            }}
                        }}
                        
                        // Failsafe: Libera a câmera para a próxima leitura após 2.5 segundos de qualquer forma
                        setTimeout(() => {{ isProcessing = false; }}, 2500);
                    }}
                }},
                (errorMessage) => {{}}
            ).then(() => {{
                sessionStorage.setItem('camera_{id_camera}', 'on');
            }}).catch(err => {{
                alert("Erro ao ligar a câmera. Tente recarregar a página.");
                desligarCamera();
            }});
        }};

        const desligarCamera = () => {{
            html5QrCode.stop().then(() => {{
                btnStart.style.display = 'inline-block';
                btnStop.style.display = 'none';
                boxCamera.style.display = 'none';
                sessionStorage.setItem('camera_{id_camera}', 'off');
                isProcessing = false;
            }}).catch(err => console.log(err));
        }};

        btnStart.onclick = ligarCamera;
        btnStop.onclick = desligarCamera;

        if (sessionStorage.getItem('camera_{id_camera}') === 'on') {{
            setTimeout(ligarCamera, 500);
        }}
    </script>
    """
    components.html(html_code, height=480)

# ------------------------------------------------------------
# 6. AUTENTICAÇÃO PERSISTENTE
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
    if os.path.exists("logo.png"): st.image("logo.png", width=160)
    st.markdown('<div class="login-title">Jansen Veloso</div>', unsafe_allow_html=True)
    senha = st.text_input("Digite sua Senha:", type="password")
    if st.button("ACESSAR SISTEMA", use_container_width=True):
        if senha == SENHA_ADMIN: st.session_state.autenticado = True; st.session_state.eh_admin = True; set_auth_cookie(True); st.rerun()
        elif senha == SENHA_OPERADOR: st.session_state.autenticado = True; st.session_state.eh_admin = False; set_auth_cookie(False); st.rerun()
        else: st.error("Senha incorreta!")
    st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# ------------------------------------------------------------
# 7. INTERFACE PRINCIPAL
# ------------------------------------------------------------
if os.path.exists("logo.png"):
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2: st.image("logo.png", use_column_width=True)

st.markdown('<p class="main-title">Sistema de Frequência</p>', unsafe_allow_html=True)
st.markdown(f'<p class="sub-title">Centro Educa Mais Jansen Veloso • {datetime.now().strftime("%d de %B de %Y")}</p>', unsafe_allow_html=True)

col_logout1, col_logout2 = st.columns([5, 1])
with col_logout2:
    if st.button("Sair do Sistema", key="logout"):
        cookies["auth_token"] = ""; cookies.save(); st.session_state.autenticado = False; st.rerun()

df_alunos = carregar_alunos()
if df_alunos.empty:
    if st.session_state.eh_admin: st.warning("Acesse a aba MANUTENÇÃO para importar a Base de Dados.")
    else: st.error("Sistema sem dados."); st.stop()

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
    
    st.info("Passo 1: Clique abaixo para gerar a lista de faltas do dia. Depois, use a câmera para dar presença.")
    if st.button("📍 Abrir Dia Letivo (Gerar Faltas)", use_container_width=True):
        faltas = abrir_dia_letivo(data_str_config)
        st.success(f"Dia Iniciado! {faltas} alunos marcados como Ausentes.")
        
    st.markdown("---")

    tab_entrada, tab_saida = st.tabs(["✅ Entrada", "🚪 Saída Antecipada"])

    # ---------- ENTRADA ----------
    with tab_entrada:
        label_in = "Código (Entrada)"
        botao_in = "Registrar Entrada"
        
        gerar_componente_camera(label_in, botao_in, "entrada")
        
        with st.form("form_in", clear_on_submit=True):
            st.markdown("<br>", unsafe_allow_html=True)
            codigo_recebido = st.text_input(label_in, placeholder="Clique aqui e use o leitor de mão, ou aguarde a câmera...")
            btn_submit_entrada = st.form_submit_button(botao_in)
            
        if btn_submit_entrada and codigo_recebido.strip():
            aluno_codigo = codigo_recebido.strip().upper()
            registrar_presenca(aluno_codigo, data_str_config, hora_entrada)
            st.rerun()

    # ---------- SAÍDA ----------
    with tab_saida:
        motivo = st.selectbox("Motivo", ["Consulta médica", "Mal-estar", "Outro"], key="motivo_saida_val")
        if motivo == "Outro": motivo = st.text_input("Especifique", key="motivo_outro_val")
        pais = st.radio("Pais informados?", ["Sim", "Não"], horizontal=True, key="pais_saida_val")
        
        label_out = "Código (Saída)"
        botao_out = "Registrar Saída"
        
        gerar_componente_camera(label_out, botao_out, "saida")
        
        with st.form("form_out", clear_on_submit=True):
            st.markdown("<br>", unsafe_allow_html=True)
            codigo_saida_recebido = st.text_input(label_out, placeholder="Aguarde a câmera ou digite...")
            btn_submit_saida = st.form_submit_button(botao_out)
            
        if btn_submit_saida and codigo_saida_recebido.strip():
            aluno_saida_codigo = codigo_saida_recebido.strip().upper()
            registrar_saida(aluno_saida_codigo, motivo, pais == "Sim", data_str_config, datetime.now().strftime("%H:%M:%S"), hora_saida)
            st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)

# ============================ ABA 1: GESTÃO ============================
with tabs[1]:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("📊 Relatório Diário")
    c1, c2, c3, c4 = st.columns(4)
    with c1: data_filtro = st.date_input("Data", datetime.now(), key="data_filtro")
    with c2: turma_filtro = st.selectbox("Turma", ["Todas"] + sorted(df_alunos['turma'].unique()) if not df_alunos.empty else ["Todas"], key="turma_filtro")
    with c3: status_filtro = st.selectbox("Status", ["Todos", "Presentes", "Ausentes"], key="status_filtro")
    with c4: busca = st.text_input("Buscar por Nome", key="busca")
    
    conn = conectar_bd()
    query = "SELECT a.codigo, a.nome, a.turma, r.tipo_registro, r.hora_entrada, r.status_entrada, r.hora_saida FROM registros_v2 r JOIN alunos_v2 a ON r.codigo_aluno = a.codigo WHERE r.data = %s"
    params = [data_filtro.strftime("%Y-%m-%d")]
    
    if turma_filtro != "Todas": query += " AND a.turma = %s"; params.append(turma_filtro)
    if status_filtro == "Presentes": query += " AND r.tipo_registro = 'PRESENCA'"
    elif status_filtro == "Ausentes": query += " AND r.tipo_registro = 'FALTA'"
    if busca: query += " AND a.nome ILIKE %s"; params.append(f"%{busca}%")
    
    query += " ORDER BY a.turma, a.nome"
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
    lista_selecao = [f"{row['codigo']} - {row['nome']}" for _, row in df_alunos.iterrows()] if not df_alunos.empty else []
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
        st.subheader("⚙️ Importação de Dados da Escola")
        st.write("Faça o upload do arquivo CSV com **ESCOLA**, **TURMA**, **CÓDIGO** e **NOME**.")
        up_admin = st.file_uploader("Arquivo CSV", type=["csv"], key="admin_csv")
        if up_admin:
            if importar_csv_para_bd(up_admin): st.success("Lista atualizada!"); st.rerun()
            
        st.subheader("🗑️ Limpeza de Base")
        senha_conf = st.text_input("Senha Admin", type="password", key="senha_limpar")
        if st.button("Apagar Histórico") and senha_conf == SENHA_ADMIN:
            limpar_todos_registros(); st.success("Registos apagados.")
