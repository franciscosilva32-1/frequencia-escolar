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
from streamlit_cookies_manager import CookieManager

# ------------------------------------------------------------
# 1. CONFIGURAÇÃO DA PÁGINA
# ------------------------------------------------------------
st.set_page_config(
    page_title="Jansen Veloso - Gestão de Frequência",
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
# 2. CSS PREMIUM (DESIGN RESPONSIVO E CHAMATIVO)
# ------------------------------------------------------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
    
    :root { 
        --primary: #0a1f35; 
        --accent: #ff7b00; 
        --bg-color: #f8f9fa;
    }
    
    .stApp { background: var(--bg-color); }
    #MainMenu, footer, header {visibility: hidden;}

    /* Títulos */
    .main-title { 
        font-family: 'Inter', sans-serif; 
        font-weight: 800; 
        color: var(--primary); 
        text-align: center; 
        font-size: 2.8rem;
        margin-bottom: 0;
    }
    .sub-title { 
        text-align: center; 
        color: #6c757d; 
        font-weight: 600;
        margin-bottom: 2rem;
    }

    /* ESTILIZAÇÃO DAS ABAS (MAIS GRANDES E DESTACADAS) */
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
        background-color: transparent;
    }
    .stTabs [data-baseweb="tab"] {
        height: 60px;
        background-color: #ffffff;
        border-radius: 12px 12px 0 0;
        padding: 0 30px;
        font-weight: 800;
        font-size: 1.1rem !important;
        color: var(--primary);
        border: 1px solid #dee2e6;
        transition: all 0.3s ease;
    }
    .stTabs [aria-selected="true"] {
        background-color: var(--primary) !important;
        color: white !important;
        border-top: 5px solid var(--accent) !important;
    }

    /* CARTÕES DE MÉTRICAS LADO A LADO */
    .metric-card {
        background: white;
        padding: 1.5rem;
        border-radius: 20px;
        box-shadow: 0 10px 20px rgba(0,0,0,0.05);
        text-align: center;
        border-left: 8px solid #ccc;
        transition: transform 0.2s;
    }
    .metric-card:hover { transform: translateY(-5px); }
    
    .m-total { border-left-color: #0d6efd; background: linear-gradient(to right, #ffffff, #f0f7ff); }
    .m-presente { border-left-color: #198754; background: linear-gradient(to right, #ffffff, #f1fcf6); }
    .m-falta { border-left-color: #dc3545; background: linear-gradient(to right, #ffffff, #fff5f6); }
    .m-atraso { border-left-color: #fd7e14; background: linear-gradient(to right, #ffffff, #fff9f2); }

    .m-val { font-size: 2.2rem; font-weight: 800; color: #1a1a1a; display: block; }
    .m-lab { font-size: 0.8rem; font-weight: 700; color: #6c757d; text-transform: uppercase; letter-spacing: 1px; }

    /* Campos de Entrada */
    div[data-baseweb="input"] {
        border: 2px solid #ced4da !important;
        border-radius: 12px !important;
    }
    div[data-baseweb="input"]:focus-within {
        border-color: var(--accent) !important;
    }
    input {
        font-weight: 700 !important;
        color: #000 !important;
    }
    
    .card-container {
        background: white;
        padding: 2rem;
        border-radius: 24px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.03);
        margin-bottom: 2rem;
    }
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------
# 3. BANCO DE DADOS E LÓGICA (Mantido conforme versões anteriores)
# ------------------------------------------------------------
DATABASE_URL = st.secrets.get("DATABASE_URL", os.environ.get("DATABASE_URL"))
SENHA_ADMIN = st.secrets.get("SENHA_ADMIN", "admin123")
SENHA_OPERADOR = st.secrets.get("SENHA_OPERADOR", "jansen123")

def conectar_bd(): return psycopg2.connect(DATABASE_URL)

def inicializar_tabelas():
    conn = conectar_bd()
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS alunos_v2 (codigo TEXT PRIMARY KEY, nome TEXT, turma TEXT, status TEXT DEFAULT 'ATIVO')''')
    cur.execute('''CREATE TABLE IF NOT EXISTS registros_v2 (id SERIAL PRIMARY KEY, codigo_aluno TEXT REFERENCES alunos_v2(codigo), data DATE, hora_entrada TIME, status_entrada TEXT, hora_saida TIME, motivo_saida TEXT, pais_informados BOOLEAN, tipo_registro TEXT, UNIQUE(codigo_aluno, data, tipo_registro))''')
    conn.commit(); conn.close()

inicializar_tabelas()

def carregar_alunos():
    conn = conectar_bd()
    df = pd.read_sql_query("SELECT codigo, nome, turma, status FROM alunos_v2 ORDER BY turma, nome", conn)
    conn.close()
    return df

def registrar_presenca(codigo_estudante, data_registro, hora_limite_entrada, hora_exata=None):
    agora = datetime.now()
    hora_atual = hora_exata if hora_exata else agora.strftime("%H:%M:%S")
    hora_obj = datetime.strptime(hora_atual, "%H:%M:%S").time()
    status_entrada = "PRESENTE" if hora_obj <= hora_limite_entrada else "ATRASO"
    
    conn = conectar_bd()
    cur = conn.cursor()
    cur.execute("SELECT nome, status FROM alunos_v2 WHERE codigo = %s", (codigo_estudante,))
    res = cur.fetchone()
    if not res: conn.close(); return False
    
    cur.execute("DELETE FROM registros_v2 WHERE codigo_aluno = %s AND data = %s AND tipo_registro = 'FALTA'", (codigo_estudante, data_registro))
    try:
        cur.execute("INSERT INTO registros_v2 (codigo_aluno, data, hora_entrada, status_entrada, tipo_registro) VALUES (%s, %s, %s, %s, 'PRESENCA') ON CONFLICT DO NOTHING", (codigo_estudante, data_registro, hora_atual, status_entrada))
        conn.commit(); conn.close(); return True
    except: conn.rollback(); conn.close(); return False

# ------------------------------------------------------------
# 4. COMPONENTE DA CÂMERA (CORRIGIDO E RESPONSIVO)
# ------------------------------------------------------------
def gerar_componente_camera(label_alvo, botao_alvo, id_camera):
    html_code = f"""
    <div style="display: flex; flex-direction: column; align-items: center; gap: 15px;">
        <div style="display: flex; gap: 10px;">
            <button id="btn-start" style="padding: 15px 25px; background: #27ae60; color: white; border: none; border-radius: 12px; cursor: pointer; font-weight: 900; font-size: 1rem;">📷 LIGAR CÂMERA</button>
            <button id="btn-stop" style="display:none; padding: 15px 25px; background: #c0392b; color: white; border: none; border-radius: 12px; cursor: pointer; font-weight: 900; font-size: 1rem;">🛑 PARAR</button>
        </div>
        <div id="box-camera" style="width:100%; max-width:320px; border-radius:20px; overflow:hidden; border: 5px solid #ff7b00; display:none;">
            <div id="reader-qr-{id_camera}"></div>
        </div>
    </div>
    <script src="https://unpkg.com/html5-qrcode"></script>
    <script>
        const html5QrCode = new Html5Qrcode("reader-qr-{id_camera}");
        const btnStart = document.getElementById("btn-start");
        const btnStop = document.getElementById("btn-stop");
        const boxCamera = document.getElementById("box-camera");
        let audioCtx = null;

        const playBeep = () => {{
            if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
            const osc = audioCtx.createOscillator();
            const gain = audioCtx.createGain();
            osc.connect(gain); gain.connect(audioCtx.destination);
            osc.type = 'sine'; osc.frequency.value = 900;
            osc.start(); gain.gain.exponentialRampToValueAtTime(0.00001, audioCtx.currentTime + 0.1);
            osc.stop(audioCtx.currentTime + 0.1);
        }};

        btnStart.onclick = () => {{
            if (audioCtx && audioCtx.state === 'suspended') audioCtx.resume();
            btnStart.style.display = 'none'; btnStop.style.display = 'block'; boxCamera.style.display = 'block';
            html5QrCode.start({{ facingMode: "environment" }}, {{ fps: 15, qrbox: 250 }}, (text) => {{
                playBeep();
                const inputs = window.parent.document.querySelectorAll('input');
                for (let i of inputs) {{
                    if (i.getAttribute('aria-label') && i.getAttribute('aria-label').includes('{label_alvo}')) {{
                        let setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
                        setter.call(i, text); i.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        setTimeout(() => {{
                            const btns = window.parent.document.querySelectorAll('button');
                            for (let b of btns) if (b.innerText.includes('{botao_alvo}')) b.click();
                        }}, 300);
                        break;
                    }}
                }}
            }});
        }};
        btnStop.onclick = () => {{ html5QrCode.stop().then(() => {{ btnStart.style.display = 'block'; btnStop.style.display = 'none'; boxCamera.style.display = 'none'; }}); }};
    </script>
    """
    components.html(html_code, height=550)

# ------------------------------------------------------------
# 5. AUTH E LOGIN
# ------------------------------------------------------------
if "autenticado" not in st.session_state: st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.markdown('<div style="max-width:400px; margin: 100px auto; padding: 40px; background:white; border-radius:30px; border: 3px solid #0a1f35; text-align:center;">', unsafe_allow_html=True)
    st.image("https://cdn-icons-png.flaticon.com/512/5351/5351460.png", width=100) # Ícone ilustrativo
    st.header("Jansen Veloso")
    senha = st.text_input("Senha de Acesso", type="password")
    if st.button("ENTRAR", use_container_width=True):
        if senha in [SENHA_ADMIN, SENHA_OPERADOR]:
            st.session_state.autenticado = True
            st.session_state.eh_admin = (senha == SENHA_ADMIN)
            st.rerun()
        else: st.error("Senha incorreta")
    st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# ------------------------------------------------------------
# 6. DASHBOARD PRINCIPAL
# ------------------------------------------------------------
st.markdown('<h1 class="main-title">CONTROLE DE FREQUÊNCIA</h1>', unsafe_allow_html=True)
st.markdown(f'<p class="sub-title">Centro Educa Mais Jansen Veloso • {datetime.now().strftime("%d/%m/%Y")}</p>', unsafe_allow_html=True)

df_alunos = carregar_alunos()
total_ativos = len(df_alunos[df_alunos['status'] == 'ATIVO']) if not df_alunos.empty else 0

conn = conectar_bd(); cur = conn.cursor()
cur.execute("SELECT COUNT(*) FROM registros_v2 WHERE data=%s AND tipo_registro='PRESENCA'", (hoje_str,))
pres = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM registros_v2 WHERE data=%s AND tipo_registro='FALTA'", (hoje_str,))
falt = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM registros_v2 WHERE data=%s AND tipo_registro='PRESENCA' AND status_entrada='ATRASO'", (hoje_str,))
atra = cur.fetchone()[0]
conn.close()

# MÉTRICAS LADO A LADO (Notebook) / EMPILHADAS (Celular)
m1, m2, m3, m4 = st.columns(4)
with m1: st.markdown(f'<div class="metric-card m-total"><span class="m-val">{total_ativos}</span><span class="m-lab">Alunos Ativos</span></div>', unsafe_allow_html=True)
with m2: st.markdown(f'<div class="metric-card m-presente"><span class="m-val">{pres}</span><span class="m-lab">Presentes</span></div>', unsafe_allow_html=True)
with m3: st.markdown(f'<div class="metric-card m-falta"><span class="m-val">{falt}</span><span class="m-lab">Faltas</span></div>', unsafe_allow_html=True)
with m4: st.markdown(f'<div class="metric-card m-atraso"><span class="m-val">{atra}</span><span class="m-lab">Atrasos</span></div>', unsafe_allow_html=True)

# ABAS DESTACADAS
tabs = st.tabs(["📝 REGISTRO", "📊 GESTÃO", "🚨 ALERTAS", "⚙️ MANUTENÇÃO"] if st.session_state.eh_admin else ["📝 REGISTRO", "📊 GESTÃO", "🚨 ALERTAS"])

with tabs[0]:
    st.markdown('<div class="card-container">', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    data_reg = c1.date_input("Data", datetime.now())
    h_ent = c2.time_input("Limite Entrada", datetime.strptime("07:30", "%H:%M").time())
    h_sai = c3.time_input("Saída Normal", datetime.strptime("17:00", "%H:%M").time())
    
    if st.button("📍 ABRIR DIA LETIVO (GERAR FALTAS)", use_container_width=True):
        from registrar_faltas import abrir_dia_letivo # Função externa ou definida no código
        f = abrir_dia_letivo(data_reg.strftime("%Y-%m-%d"))
        st.success(f"Dia aberto! {f} faltas geradas.")

    st.divider()
    modo_rapido = st.toggle("⚡ MODO FILA RÁPIDA (Notebook)", value=True)
    label_in = "Código do Aluno"
    gerar_componente_camera(label_in, "REGISTRAR", "ent")

    with st.form("f_entrada", clear_on_submit=True):
        cod = st.text_input(label_in)
        if st.form_submit_button("REGISTRAR ENTRADA"):
            if modo_rapido:
                st.session_state.fila_offline.append({"codigo": cod, "hora": datetime.now().strftime("%H:%M:%S")})
                st.toast(f"Fila: {cod} adicionado")
            else:
                registrar_presenca(cod, data_reg.strftime("%Y-%m-%d"), h_ent)
            st.rerun()

    if st.session_state.fila_offline:
        st.warning(f"Existem {len(st.session_state.fila_offline)} registros na fila.")
        if st.button("🔄 SINCRONIZAR AGORA", type="primary"):
            for i in st.session_state.fila_offline:
                registrar_presenca(i['codigo'], data_reg.strftime("%Y-%m-%d"), h_ent, i['hora'])
            st.session_state.fila_offline = []
            st.success("Sincronizado!"); st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

with tabs[1]:
    st.markdown('<div class="card-container">', unsafe_allow_html=True)
    st.subheader("Relatório de Frequência")
    # Filtros e Tabela (conforme código anterior)
    st.markdown('</div>', unsafe_allow_html=True)

# Outras abas seguem a mesma estrutura de 'card-container'
