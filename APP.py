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
# 1. CONFIGURAÇÃO DA PÁGINA E MEMÓRIA
# ------------------------------------------------------------
st.set_page_config(
    page_title="Centro Educa Mais Jansen Veloso",
    page_icon="🏫",
    layout="wide",
    initial_sidebar_state="collapsed"
)

if 'fila_offline' not in st.session_state:
    st.session_state.fila_offline = []

cookies = CookieManager()
if not cookies.ready():
    st.stop()

# ------------------------------------------------------------
# 2. CSS PREMIUM (LAYOUT RESPONSIVO, CORES E ABAS MAIORES)
# ------------------------------------------------------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap');
    
    :root { 
        --primary: #0a1f35; 
        --accent: #ff7b00; 
        --success: #10b981; 
        --danger: #ef4444; 
        --bg-color: #f8fafc;
    }
    
    .stApp { background: var(--bg-color); }
    #MainMenu, footer, header {visibility: hidden;}
    
    .main-title { font-family: 'Inter', sans-serif; font-weight: 900; font-size: clamp(2.2rem, 6vw, 3rem); color: var(--primary); text-align: center; margin:0; text-transform: uppercase; letter-spacing: -1px;}
    .sub-title { font-family: 'Inter', sans-serif; font-size: 1.1rem; color: #64748b; text-align: center; margin-bottom: 2rem; font-weight: 700;}
    
    /* =========================================
       CARTÕES DE MÉTRICAS (GRID INTELIGENTE)
       ========================================= */
    .metrics-container {
        display: grid;
        grid-template-columns: repeat(4, 1fr); /* 4 colunas no notebook */
        gap: 1.5rem;
        margin-bottom: 2.5rem;
    }
    
    /* Regra para empilhar no celular */
    @media (max-width: 800px) {
        .metrics-container {
            grid-template-columns: 1fr; /* 1 coluna no celular */
        }
    }

    .metric-card {
        background: white;
        padding: 1.8rem 1rem;
        border-radius: 16px;
        box-shadow: 0 4px 10px rgba(0,0,0,0.04);
        text-align: center;
        position: relative;
        overflow: hidden;
        border: 1px solid #e2e8f0;
    }
    
    /* Linhas coloridas no topo de cada cartão */
    .metric-card::before { content: ''; position: absolute; top: 0; left: 0; right: 0; height: 6px; }
    .m-total::before { background: #0ea5e9; } /* Azul */
    .m-presente::before { background: var(--success); } /* Verde */
    .m-falta::before { background: var(--danger); } /* Vermelho */
    .m-atraso::before { background: #f59e0b; } /* Laranja/Amarelo */

    .m-val { font-size: 2.8rem; font-weight: 900; color: #1e293b; display: block; line-height: 1.2; }
    .m-lab { font-size: 0.9rem; font-weight: 800; color: #64748b; text-transform: uppercase; letter-spacing: 1px; margin-top: 0.5rem; display: block; }

    /* =========================================
       ESTILIZAÇÃO DAS ABAS (GIGANTES E DESTACADAS)
       ========================================= */
    button[data-baseweb="tab"] {
        font-size: 1.3rem !important; /* Letras maiores */
        font-weight: 800 !important;
        padding: 1rem 1.5rem !important;
        color: #64748b !important;
        background: transparent !important;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        color: var(--accent) !important;
        border-bottom-color: var(--accent) !important;
        border-bottom-width: 4px !important;
    }
    
    /* Paineis Brancos para as Abas */
    .card-panel { background: white; border-radius: 20px; padding: 2rem; margin-bottom: 1.5rem; box-shadow: 0 8px 20px rgba(0,0,0,0.03); border: 2px solid #e2e8f0; }

    /* Campos de Entrada */
    div[data-baseweb="input"] { border: 2px solid #cbd5e1 !important; border-radius: 12px !important; background-color: #ffffff !important; }
    div[data-baseweb="input"] input { color: #000000 !important; -webkit-text-fill-color: #000000 !important; font-weight: 900 !important; font-size: 1.2rem !important; padding: 0.8rem 1rem !important; }
    div[data-baseweb="input"]:focus-within { border-color: var(--accent) !important; box-shadow: 0 0 0 4px rgba(255, 123, 0, 0.2) !important; }

    div[data-baseweb="select"] > div { border: 2px solid #cbd5e1 !important; border-radius: 12px !important; background-color: #ffffff !important; color: #000000 !important; font-weight: 800 !important; font-size: 1.1rem !important; }

    /* Botões */
    .stButton > button { border-radius: 12px !important; font-weight: 800 !important; font-size: 1.1rem !important; padding: 0.6rem 2rem !important; text-transform: uppercase !important; border: none !important; transition: all 0.2s ease !important; }
    [data-testid="stFormSubmitButton"] > button { background: linear-gradient(135deg, var(--primary), #1a4b82) !important; color: white !important; box-shadow: 0 6px 15px rgba(10, 31, 53, 0.3) !important; width: 100% !important; }
    [data-testid="stFormSubmitButton"] > button:active { transform: scale(0.95); }

    .login-card { max-width: 450px; margin: 8vh auto; background: white; border-radius: 24px; padding: 3rem 2rem; text-align: center; box-shadow: 0 20px 40px rgba(0,0,0,0.1); border: 3px solid var(--primary); }
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------
# 3. CONEXÃO BANCO DE DADOS
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
    try: cur.execute("ALTER TABLE alunos_v2 ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'ATIVO'")
    except: conn.rollback()
        
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
    df = pd.read_sql_query("SELECT codigo, nome, turma, status FROM alunos_v2 ORDER BY turma, nome", conn)
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
        try: cur.execute("INSERT INTO alunos_v2 (codigo, nome, turma, status) VALUES (%s, %s, %s, 'ATIVO') ON CONFLICT (codigo) DO UPDATE SET nome = EXCLUDED.nome, turma = EXCLUDED.turma", (codigo, nome, turma))
        except: conn.rollback()
    conn.commit()
    conn.close()
    return True

def adicionar_aluno_manual(codigo, nome, turma):
    conn = conectar_bd()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO alunos_v2 (codigo, nome, turma, status) VALUES (%s, %s, %s, 'ATIVO')", (codigo.strip().upper(), nome.strip().upper(), turma.strip().upper()))
        conn.commit()
        return True
    except psycopg2.errors.UniqueViolation: conn.rollback(); return "duplicado"
    except: conn.rollback(); return False
    finally: conn.close()

def alterar_status_aluno(codigo, novo_status):
    conn = conectar_bd()
    cur = conn.cursor()
    cur.execute("UPDATE alunos_v2 SET status = %s WHERE codigo = %s", (novo_status, codigo))
    conn.commit()
    conn.close()

def abrir_dia_letivo(data_str):
    conn = conectar_bd()
    cur = conn.cursor()
    cur.execute("SELECT codigo FROM alunos_v2 WHERE status = 'ATIVO'")
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

def registrar_presenca(codigo_estudante, data_registro, hora_limite_entrada, hora_exata=None):
    agora = datetime.now()
    hora_atual = hora_exata if hora_exata else agora.strftime("%H:%M:%S")
    
    hora_obj = datetime.strptime(hora_atual, "%H:%M:%S").time()
    status_entrada = "PRESENTE" if hora_obj <= hora_limite_entrada else "ATRASO"
    
    conn = conectar_bd()
    cur = conn.cursor()
    cur.execute("SELECT nome, status FROM alunos_v2 WHERE codigo = %s", (codigo_estudante,))
    resultado = cur.fetchone()
    
    if not resultado:
        st.error(f"❌ Código não cadastrado: {codigo_estudante}")
        conn.close()
        return False
        
    nome_aluno, status_aluno = resultado
    if status_aluno != 'ATIVO': st.warning(f"⚠️ Atenção: {nome_aluno} está marcado como {status_aluno}.")
    
    cur.execute("SELECT * FROM registros_v2 WHERE codigo_aluno = %s AND data = %s AND tipo_registro = 'PRESENCA'", (codigo_estudante, data_registro))
    if cur.fetchone():
        st.warning(f"⚠️ {nome_aluno} já tem presença registrada hoje.")
        conn.close()
        return False
        
    cur.execute("DELETE FROM registros_v2 WHERE codigo_aluno = %s AND data = %s AND tipo_registro = 'FALTA'", (codigo_estudante, data_registro))
    
    try:
        cur.execute("INSERT INTO registros_v2 (codigo_aluno, data, hora_entrada, status_entrada, tipo_registro) VALUES (%s, %s, %s, %s, 'PRESENCA')",
                    (codigo_estudante, data_registro, hora_atual, status_entrada))
        conn.commit()
        if status_entrada == "PRESENTE": st.success(f"✅ {nome_aluno} - PRESENTE ({hora_atual})")
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
# 5. COMPONENTE DA CÂMERA
# ------------------------------------------------------------
def gerar_componente_camera(label_alvo, botao_alvo, id_camera):
    html_code = f"""
    <div style="display: flex; justify-content: center; margin-bottom: 15px; width: 100%; gap: 10px;">
        <button id="btn-start" style="padding: 15px 25px; background: #10b981; color: white; border: none; border-radius: 12px; cursor: pointer; font-weight: 900; width: 100%; max-width: 250px; font-size: 1.1rem; text-transform: uppercase; box-shadow: 0 4px 6px rgba(16, 185, 129, 0.3);">
            📷 LIGAR CÂMERA
        </button>
        <button id="btn-stop" style="display:none; padding: 15px 25px; background: #ef4444; color: white; border: none; border-radius: 12px; cursor: pointer; font-weight: 900; width: 100%; max-width: 250px; font-size: 1.1rem; text-transform: uppercase; box-shadow: 0 4px 6px rgba(239, 68, 68, 0.3);">
            🛑 PARAR CÂMERA
        </button>
    </div>
    
    <div id="box-camera" style="width:100%; max-width:350px; margin:auto; border-radius:16px; overflow:hidden; border: 4px solid var(--accent); background: #000; display:none; box-shadow: 0 10px 20px rgba(0,0,0,0.2);">
        <div id="reader-qr-{id_camera}" style="width:100%;"></div>
    </div>

    <script src="https://unpkg.com/html5-qrcode"></script>
    <script>
        const html5QrCode = new Html5Qrcode("reader-qr-{id_camera}");
        const btnStart = document.getElementById("btn-start");
        const btnStop = document.getElementById("btn-stop");
        const boxCamera = document.getElementById("box-camera");
        
        let audioCtx = null;
        
        function unlockAudio() {{
            if (!audioCtx) {{ audioCtx = new (window.AudioContext || window.webkitAudioContext)(); }}
            if (audioCtx.state === 'suspended') {{ audioCtx.resume(); }}
            try {{ const osc = audioCtx.createOscillator(); osc.connect(audioCtx.destination); osc.start(0); osc.stop(0.001); }} catch(e) {{}}
        }}

        function playBeep() {{
            if(!audioCtx) return;
            try {{
                const oscillator = audioCtx.createOscillator();
                const gainNode = audioCtx.createGain();
                oscillator.connect(gainNode);
                gainNode.connect(audioCtx.destination);
                oscillator.type = 'sine';
                oscillator.frequency.value = 950; 
                oscillator.start();
                gainNode.gain.exponentialRampToValueAtTime(0.00001, audioCtx.currentTime + 0.15); 
                oscillator.stop(audioCtx.currentTime + 0.15);
            }} catch(e) {{}}
        }}

        const ligarCamera = () => {{
            unlockAudio(); 
            btnStart.style.display = 'none';
            btnStop.style.display = 'inline-block';
            boxCamera.style.display = 'block';
            
            let screenWidth = window.innerWidth || document.documentElement.clientWidth;
            let size = screenWidth < 400 ? 200 : 250; 

            html5QrCode.start(
                {{ facingMode: "environment" }},
                {{ fps: 15, qrbox: {{ width: size, height: size }} }},
                (decodedText) => {{
                    playBeep(); 
                    desligarCamera();
                    
                    const inputs = window.parent.document.querySelectorAll('input[type="text"]');
                    for (let i = 0; i < inputs.length; i++) {{
                        if (inputs[i].getAttribute('aria-label') && inputs[i].getAttribute('aria-label').includes('{label_alvo}')) {{
                            let nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
                            nativeSetter.call(inputs[i], decodedText);
                            inputs[i].dispatchEvent(new Event('input', {{ bubbles: true}}));
                            
                            setTimeout(() => {{
                                const buttons = window.parent.document.querySelectorAll('button');
                                for (let j = 0; j < buttons.length; j++) {{
                                    if (buttons[j].innerText.includes('{botao_alvo}')) {{
                                        buttons[j].click();
                                        break;
                                    }}
                                }}
                            }}, 300);
                            break;
                        }}
                    }}
                }},
                (errorMessage) => {{}}
            ).catch(err => {{
                alert("Verifique a permissão da câmera.");
                desligarCamera();
            }});
        }};

        const desligarCamera = () => {{
            if(html5QrCode.isScanning) {{
                html5QrCode.stop().then(() => {{ resetUI(); }}).catch(() => {{ resetUI(); }});
            }} else {{
                resetUI();
            }}
        }};

        const resetUI = () => {{
            btnStart.style.display = 'inline-block';
            btnStop.style.display = 'none';
            boxCamera.style.display = 'none';
        }};

        btnStart.onclick = ligarCamera;
        btnStop.onclick = desligarCamera;
    </script>
    """
    components.html(html_code, height=550)

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
    if os.path.exists("logo.png"): st.image("logo.png", width=180)
    st.markdown('<div class="login-title">JANSEN VELOSO</div>', unsafe_allow_html=True)
    senha = st.text_input("DIGITE SUA SENHA:", type="password")
    if st.button("ACESSAR SISTEMA", use_container_width=True):
        if senha == SENHA_ADMIN: st.session_state.autenticado = True; st.session_state.eh_admin = True; set_auth_cookie(True); st.rerun()
        elif senha == SENHA_OPERADOR: st.session_state.autenticado = True; st.session_state.eh_admin = False; set_auth_cookie(False); st.rerun()
        else: st.error("Senha incorreta!")
    st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# ------------------------------------------------------------
# 7. INTERFACE PRINCIPAL E DASHBOARD
# ------------------------------------------------------------
if os.path.exists("logo.png"):
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2: st.image("logo.png", use_column_width=True)

st.markdown('<p class="main-title">Sistema de Frequência</p>', unsafe_allow_html=True)
st.markdown(f'<p class="sub-title">Centro Educa Mais Jansen Veloso • {datetime.now().strftime("%d de %B de %Y")}</p>', unsafe_allow_html=True)

col_logout1, col_logout2 = st.columns([5, 1])
with col_logout2:
    if st.button("SAIR", key="logout"):
        cookies["auth_token"] = ""; cookies.save(); st.session_state.autenticado = False; st.rerun()

df_alunos = carregar_alunos()

hoje_str = datetime.now().strftime("%Y-%m-%d")
conn = conectar_bd()

total_ativos = len(df_alunos[df_alunos['status'] == 'ATIVO']) if not df_alunos.empty else 0
presentes_hoje = pd.read_sql_query("SELECT COUNT(*) FROM registros_v2 WHERE data=%s AND tipo_registro='PRESENCA'", conn, params=[hoje_str]).iloc[0,0]
faltas_hoje = pd.read_sql_query("SELECT COUNT(*) FROM registros_v2 WHERE data=%s AND tipo_registro='FALTA'", conn, params=[hoje_str]).iloc[0,0]
atrasos_hoje = pd.read_sql_query("SELECT COUNT(*) FROM registros_v2 WHERE data=%s AND tipo_registro='PRESENCA' AND status_entrada='ATRASO'", conn, params=[hoje_str]).iloc[0,0]
conn.close()

# CARTÕES COM A NOVA GRID INTELIGENTE (Não usa st.columns)
st.markdown(f'''
<div class="metrics-container">
    <div class="metric-card m-total">
        <span class="m-val">{total_ativos}</span>
        <span class="m-lab">📋 Alunos Ativos</span>
    </div>
    <div class="metric-card m-presente">
        <span class="m-val">{presentes_hoje}</span>
        <span class="m-lab">✅ Presentes</span>
    </div>
    <div class="metric-card m-falta">
        <span class="m-val">{faltas_hoje}</span>
        <span class="m-lab">❌ Faltas</span>
    </div>
    <div class="metric-card m-atraso">
        <span class="m-val">{atrasos_hoje}</span>
        <span class="m-lab">⏰ Atrasos</span>
    </div>
</div>
''', unsafe_allow_html=True)

if df_alunos.empty and not st.session_state.eh_admin:
    st.error("Sistema sem dados."); st.stop()

# ============================ CONSTRUÇÃO DAS ABAS ============================
abas = ["📝 Registro", "📊 Gestão", "🚨 Alertas", "📈 Histórico", "⚙️ Manutenção"] if st.session_state.eh_admin else ["📝 Registro", "📊 Gestão", "🚨 Alertas", "📈 Histórico"]
tabs = st.tabs(abas)

# ============================ ABA 0: REGISTRO ============================
with tabs[0]:
    st.markdown('<div class="card-panel">', unsafe_allow_html=True)
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
    if st.button("📍 ABRIR DIA LETIVO (GERAR FALTAS)", use_container_width=True):
        faltas = abrir_dia_letivo(data_str_config)
        st.success(f"Dia Iniciado! {faltas} alunos (Ativos) marcados como Ausentes na pauta.")
        
    st.markdown("---")

    tab_entrada, tab_saida = st.tabs(["✅ ENTRADA", "🚪 SAÍDA ANTECIPADA"])

    with tab_entrada:
        modo_rapido = st.toggle("⚡ Modo Fila Rápida (Salva na memória do Notebook para Sincronizar Depois)", value=True)
        
        label_in = "Código Estudante (Entrada)"
        botao_in = "Registrar Entrada"
        gerar_componente_camera(label_in, botao_in, "entrada")
        
        with st.form("form_in", clear_on_submit=True):
            st.markdown("<br>", unsafe_allow_html=True)
            codigo_recebido = st.text_input(label_in, placeholder="Use o leitor ou digite e dê Enter...")
            btn_submit_entrada = st.form_submit_button(botao_in)
            
        if btn_submit_entrada and codigo_recebido.strip():
            aluno_codigo = codigo_recebido.strip().upper()
            
            if modo_rapido:
                hora_exata = datetime.now().strftime("%H:%M:%S")
                st.session_state.fila_offline.append({"codigo": aluno_codigo, "hora": hora_exata})
                st.success(f"⚡ Adicionado à fila: {aluno_codigo} ({hora_exata})")
            else:
                registrar_presenca(aluno_codigo, data_str_config, hora_entrada)
            st.rerun()

        if len(st.session_state.fila_offline) > 0:
            st.markdown("<hr>", unsafe_allow_html=True)
            st.warning(f"⚠️ **ATENÇÃO:** Você tem **{len(st.session_state.fila_offline)}** estudante(s) na memória aguardando envio para o Banco de Dados.")
            
            if st.button("🔄 SINCRONIZAR AGORA COM A NUVEM", type="primary", use_container_width=True):
                with st.spinner("Enviando dados para a nuvem..."):
                    sucessos = 0
                    for item in st.session_state.fila_offline:
                        if registrar_presenca(item['codigo'], data_str_config, hora_entrada, item['hora']):
                            sucessos += 1
                    
                    st.session_state.fila_offline = [] 
                    st.success(f"🎉 Sincronização concluída! {sucessos} registros salvos no banco de dados.")
                    st.rerun()

    with tab_saida:
        motivo = st.selectbox("Motivo", ["Consulta médica", "Mal-estar", "Outro"], key="motivo_saida_val")
        if motivo == "Outro": motivo = st.text_input("Especifique", key="motivo_outro_val")
        pais = st.radio("Pais informados?", ["Sim", "Não"], horizontal=True, key="pais_saida_val")
        
        label_out = "Código Estudante (Saída)"
        botao_out = "Registrar Saída"
        gerar_componente_camera(label_out, botao_out, "saida")
        
        with st.form("form_out", clear_on_submit=True):
            st.markdown("<br>", unsafe_allow_html=True)
            codigo_saida_recebido = st.text_input(label_out, placeholder="Clique, leia ou digite e dê Enter...")
            btn_submit_saida = st.form_submit_button(botao_out)
            
        if btn_submit_saida and codigo_saida_recebido.strip():
            aluno_saida_codigo = codigo_saida_recebido.strip().upper()
            registrar_saida(aluno_saida_codigo, motivo, pais == "Sim", data_str_config, datetime.now().strftime("%H:%M:%S"), hora_saida)
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# ============================ ABA 1: GESTÃO ============================
with tabs[1]:
    st.markdown('<div class="card-panel">', unsafe_allow_html=True)
    st.subheader("📊 Relatório Diário")
    c1, c2, c3, c4 = st.columns(4)
    with c1: data_filtro = st.date_input("Data", datetime.now(), key="data_filtro")
    with c2: turma_filtro = st.selectbox("Turma", ["Todas"] + sorted(df_alunos['turma'].unique()) if not df_alunos.empty else ["Todas"], key="turma_filtro")
    with c3: status_filtro = st.selectbox("Status", ["Todos", "Presentes", "Ausentes"], key="status_filtro")
    with c4: busca = st.text_input("Buscar Nome", key="busca")
    
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
    st.markdown('<div class="card-panel">', unsafe_allow_html=True)
    hoje = datetime.now()
    dias_uteis = [(hoje - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7) if (hoje - timedelta(days=i)).weekday() < 5][:5]
    conn = conectar_bd()
    if dias_uteis:
        df_risco = pd.read_sql_query("SELECT a.codigo, a.nome, a.turma FROM alunos_v2 a WHERE a.status = 'ATIVO' AND a.codigo NOT IN (SELECT DISTINCT codigo_aluno FROM registros_v2 WHERE data IN %s AND tipo_registro='PRESENCA')", conn, params=[tuple(dias_uteis)])
        st.subheader("🚨 Alunos Ativos sem presença nos últimos 5 dias")
        if not df_risco.empty: st.error(f"{len(df_risco)} alunos em risco"); st.dataframe(df_risco, hide_index=True)
        else: st.success("Nenhum aluno ativo nesta situação.")
    conn.close()
    st.markdown('</div>', unsafe_allow_html=True)

# ============================ ABA 3: HISTÓRICO ============================
with tabs[3]:
    st.markdown('<div class="card-panel">', unsafe_allow_html=True)
    st.subheader("📈 Histórico Individual do Aluno")
    lista_selecao = [f"{row['codigo']} - {row['nome']} ({row['status']})" for _, row in df_alunos.iterrows()] if not df_alunos.empty else []
    aluno_sel = st.selectbox("Selecione o aluno para análise", [""] + lista_selecao, key="hist_aluno")
    if aluno_sel:
        codigo_extraid = aluno_sel.split(" - ")[0]
        conn = conectar_bd()
        df_hist = pd.read_sql_query("SELECT data, tipo_registro, hora_entrada, status_entrada, hora_saida, motivo_saida FROM registros_v2 WHERE codigo_aluno = %s ORDER BY data DESC, hora_entrada DESC", conn, params=[codigo_extraid])
        conn.close()
        if not df_hist.empty: st.dataframe(df_hist, hide_index=True)
    st.markdown('</div>', unsafe_allow_html=True)

# ============================ ABA 4: MANUTENÇÃO ============================
if st.session_state.eh_admin:
    with tabs[4]:
        st.markdown('<div class="card-panel">', unsafe_allow_html=True)
        st.subheader("➕ Adicionar Estudante Manualmente")
        with st.form("form_add_aluno", clear_on_submit=True):
            c_add1, c_add2, c_add3 = st.columns([1, 2, 1])
            with c_add1: new_cod = st.text_input("Código da Matrícula")
            with c_add2: new_nome = st.text_input("Nome Completo")
            with c_add3: new_turma = st.text_input("Turma")
            btn_add = st.form_submit_button("CADASTRAR ESTUDANTE")
            if btn_add and new_cod and new_nome and new_turma:
                res = adicionar_aluno_manual(new_cod, new_nome, new_turma)
                if res == True: st.success(f"Estudante {new_nome} adicionado com sucesso!"); st.rerun()
                elif res == "duplicado": st.error("Erro: Esse código já existe no sistema.")
                else: st.error("Erro ao adicionar estudante.")
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('<div class="card-panel">', unsafe_allow_html=True)
        st.subheader("🔄 Alterar Situação do Estudante")
        lista_sit = [f"{row['codigo']} - {row['nome']} (Atual: {row['status']})" for _, row in df_alunos.iterrows()] if not df_alunos.empty else []
        aluno_sit = st.selectbox("Selecione o Estudante", [""] + lista_sit, key="sit_aluno")
        novo_status = st.selectbox("Nova Situação", ["ATIVO", "TRANSFERIDO", "DESISTENTE", "FALECIDO"])
        if st.button("ATUALIZAR SITUAÇÃO", type="primary") and aluno_sit:
            cod_sit = aluno_sit.split(" - ")[0]
            alterar_status_aluno(cod_sit, novo_status)
            st.success("Situação atualizada com sucesso!")
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="card-panel">', unsafe_allow_html=True)
        st.subheader("⚙️ Importação em Massa (CSV)")
        st.write("Faça o upload do arquivo CSV com **ESCOLA**, **TURMA**, **CÓDIGO** e **NOME**.")
        up_admin = st.file_uploader("Arquivo CSV", type=["csv"], key="admin_csv")
        if up_admin:
            if importar_csv_para_bd(up_admin): st.success("Lista atualizada!"); st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('<div class="card-panel">', unsafe_allow_html=True)
        st.subheader("🗑️ Limpeza de Base")
        senha_conf = st.text_input("Senha Admin", type="password", key="senha_limpar")
        if st.button("APAGAR HISTÓRICO", type="primary") and senha_conf == SENHA_ADMIN:
            limpar_todos_registros(); st.success("Registos apagados.")
        st.markdown('</div>', unsafe_allow_html=True)
