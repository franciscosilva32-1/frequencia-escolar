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
# CONFIGURAÇÃO DA PÁGINA
# ------------------------------------------------------------
st.set_page_config(
    page_title="Centro Educa Mais Jansen Veloso",
    page_icon="🏫",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ------------------------------------------------------------
# GESTOR DE COOKIES (sessão persistente)
# ------------------------------------------------------------
cookies = CookieManager()
if not cookies.ready():
    st.stop()

# ------------------------------------------------------------
# CSS PROFISSIONAL (logo centralizada, cores renovadas)
# ------------------------------------------------------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Montserrat:wght@600;700;800&display=swap');

    :root {
        --primary: #0a2a44;
        --secondary: #1e4a6b;
        --accent: #e6b422;
        --accent2: #00a896;
    }

    .stApp {
        background: linear-gradient(165deg, #e9f0f5 0%, #d9e4ed 100%);
    }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    /* Cabeçalho centralizado */
    .header-container {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 2rem 0 0.5rem;
        text-align: center;
    }
    .logo-img {
        display: block;
        margin: 0 auto 0.8rem;
        width: 180px;
        filter: drop-shadow(0 4px 8px rgba(0,0,0,0.15));
    }
    @media (max-width: 768px) {
        .logo-img {
            width: 150px;
        }
    }

    .main-title {
        font-family: 'Montserrat', sans-serif;
        font-size: clamp(2rem, 7vw, 3rem);
        font-weight: 800;
        background: linear-gradient(135deg, var(--primary), var(--secondary));
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        margin: 0 0 0.2rem;
    }
    .sub-title {
        font-family: 'Inter', sans-serif;
        font-size: 1rem;
        color: #5b6e85;
        text-align: center;
        margin-bottom: 2rem;
    }

    .card {
        background: rgba(255,255,255,0.75);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border-radius: 24px;
        padding: 1.8rem;
        margin-bottom: 1.5rem;
        box-shadow: 0 12px 35px rgba(0,0,0,0.05);
        border: 1px solid rgba(255,255,255,0.7);
    }

    .metric-card {
        background: white;
        border-radius: 20px;
        padding: 1.4rem 1rem;
        text-align: center;
        box-shadow: 0 6px 18px rgba(0,0,0,0.04);
        border-left: 5px solid var(--accent);
        transition: all 0.2s;
    }
    .metric-value {
        font-family: 'Montserrat', sans-serif;
        font-size: 2.2rem;
        font-weight: 800;
        color: var(--primary);
    }
    .metric-label {
        font-family: 'Inter', sans-serif;
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #64748b;
    }

    .stButton > button {
        font-family: 'Inter', sans-serif;
        font-weight: 600;
        border-radius: 14px;
        background: linear-gradient(135deg, var(--secondary), var(--primary));
        color: white;
        border: none;
        padding: 0.7rem 2rem;
        box-shadow: 0 4px 12px rgba(10,42,68,0.2);
        transition: all 0.3s;
    }
    .stButton > button:hover {
        background: linear-gradient(135deg, var(--primary), var(--secondary));
        box-shadow: 0 6px 18px rgba(10,42,68,0.3);
        transform: translateY(-1px);
    }

    .stTabs [data-baseweb="tab-list"] {
        background: rgba(255,255,255,0.4);
        padding: 6px;
        border-radius: 18px;
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        font-family: 'Inter', sans-serif;
        font-weight: 600;
        border-radius: 14px;
        padding: 12px 24px;
    }
    .stTabs [aria-selected="true"] {
        background: var(--primary) !important;
        color: white !important;
    }

    .stTextInput > div > div > input {
        border-radius: 14px;
        border: 2px solid #e2e8f0;
        padding: 0.7rem 1rem;
        background: white;
    }

    .login-card {
        max-width: 420px;
        margin: 8vh auto;
        background: rgba(255,255,255,0.8);
        backdrop-filter: blur(16px);
        border-radius: 32px;
        padding: 2.5rem 2rem;
        box-shadow: 0 30px 50px rgba(0,0,0,0.1);
        text-align: center;
    }
    .login-title {
        font-family: 'Montserrat', sans-serif;
        font-size: 1.6rem;
        font-weight: 700;
        color: var(--primary);
        margin: 1rem 0 2rem;
    }
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------
# CONEXÃO SUPABASE
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
    cur.execute('''
        CREATE TABLE IF NOT EXISTS alunos (
            nome TEXT PRIMARY KEY,
            turma TEXT
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS registros (
            id SERIAL PRIMARY KEY,
            nome_aluno TEXT REFERENCES alunos(nome),
            data DATE,
            hora_entrada TIME,
            status_entrada TEXT,
            hora_saida TIME,
            motivo_saida TEXT,
            pais_informados BOOLEAN,
            tipo_registro TEXT,
            UNIQUE(nome_aluno, data, tipo_registro)
        )
    ''')
    # Adiciona colunas ausentes (caso a tabela já exista)
    cur.execute("ALTER TABLE registros ADD COLUMN IF NOT EXISTS pais_informados BOOLEAN")
    conn.commit()
    conn.close()

inicializar_tabelas()

# ------------------------------------------------------------
# FUNÇÕES DE NEGÓCIO
# ------------------------------------------------------------
def carregar_alunos():
    conn = conectar_bd()
    df = pd.read_sql_query("SELECT nome, turma FROM alunos ORDER BY turma, nome", conn)
    conn.close()
    return df

def importar_csv_para_bd(arquivo_csv):
    conteudo = arquivo_csv.read()
    if conteudo.startswith(b'\xef\xbb\xbf'):
        conteudo = conteudo[3:]
    try:
        for enc in ['utf-8', 'latin1', 'cp1252', 'iso-8859-1']:
            try:
                df = pd.read_csv(io.BytesIO(conteudo), sep=';', encoding=enc)
                break
            except UnicodeDecodeError:
                continue
        else:
            df = pd.read_csv(io.BytesIO(conteudo), sep=None, engine='python')
    except Exception as e:
        st.error(f"Erro ao ler ficheiro: {e}")
        return False
    df.columns = [col.strip().upper() for col in df.columns]
    if 'NOME' not in df.columns or 'TURMA' not in df.columns:
        st.error("CSV precisa conter colunas NOME e TURMA.")
        return False
    conn = conectar_bd()
    cur = conn.cursor()
    for _, row in df.iterrows():
        nome = str(row['NOME']).strip().upper()
        turma = str(row['TURMA']).strip().upper()
        try:
            cur.execute("INSERT INTO alunos (nome, turma) VALUES (%s, %s)", (nome, turma))
        except psycopg2.errors.UniqueViolation:
            conn.rollback()
    conn.commit()
    conn.close()
    return True

def registrar_presenca(nome_estudante):
    agora = datetime.now()
    data_hoje = agora.strftime("%Y-%m-%d")
    hora_atual = agora.strftime("%H:%M:%S")
    limite = agora.replace(hour=7, minute=30, second=0)
    status = "PRESENTE" if agora <= limite else "ATRASO"
    conn = conectar_bd()
    cur = conn.cursor()
    cur.execute("SELECT nome FROM alunos WHERE nome = %s", (nome_estudante,))
    if not cur.fetchone():
        st.error(f"❌ Aluno não encontrado: {nome_estudante}")
        conn.close()
        return
    cur.execute("SELECT * FROM registros WHERE nome_aluno = %s AND data = %s AND tipo_registro = 'PRESENCA'", (nome_estudante, data_hoje))
    if cur.fetchone():
        st.warning(f"⚠️ {nome_estudante} já registou entrada hoje.")
        conn.close()
        return
    cur.execute("DELETE FROM registros WHERE nome_aluno = %s AND data = %s AND tipo_registro = 'FALTA'", (nome_estudante, data_hoje))
    conn.commit()
    try:
        cur.execute("INSERT INTO registros (nome_aluno, data, hora_entrada, status_entrada, tipo_registro) VALUES (%s, %s, %s, %s, 'PRESENCA')", (nome_estudante, data_hoje, hora_atual, status))
        conn.commit()
        if status == "PRESENTE":
            st.success(f"✅ Entrada registada: {nome_estudante} às {hora_atual}")
        else:
            st.warning(f"⏰ Atraso: {nome_estudante} às {hora_atual}")
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        st.warning("Registo duplicado.")
    conn.close()

def registrar_saida(nome, motivo, pais_informados, hora_saida):
    data_hoje = datetime.now().strftime("%Y-%m-%d")
    conn = conectar_bd()
    cur = conn.cursor()
    cur.execute("""
        UPDATE registros 
        SET hora_saida = %s, motivo_saida = %s, pais_informados = %s 
        WHERE nome_aluno = %s AND data = %s AND tipo_registro = 'PRESENCA'
    """, (hora_saida, motivo, pais_informados, nome, data_hoje))
    if cur.rowcount > 0:
        st.success(f"✅ Saída registada: {nome} ({motivo})")
    else:
        st.error("Erro: sem registo de entrada hoje.")
    conn.commit()
    conn.close()

def gerar_faltas_para_dia(data_str):
    conn = conectar_bd()
    cur = conn.cursor()
    cur.execute("SELECT nome FROM alunos")
    alunos = [row[0] for row in cur.fetchall()]
    for aluno in alunos:
        cur.execute("SELECT tipo_registro FROM registros WHERE nome_aluno = %s AND data = %s AND tipo_registro IN ('PRESENCA','FALTA')", (aluno, data_str))
        if not cur.fetchone():
            try:
                cur.execute("INSERT INTO registros (nome_aluno, data, tipo_registro) VALUES (%s, %s, 'FALTA')", (aluno, data_str))
            except psycopg2.errors.UniqueViolation:
                conn.rollback()
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
    df = pd.read_sql_query("""
        SELECT data, tipo_registro, hora_entrada, status_entrada, hora_saida, motivo_saida, pais_informados
        FROM registros
        WHERE nome_aluno = %s
        ORDER BY data DESC, hora_entrada DESC
    """, conn, params=[nome_aluno])
    conn.close()
    return df

# ------------------------------------------------------------
# COMPONENTE QR VIA CÂMERA (funcional em qualquer dispositivo)
# ------------------------------------------------------------
def qr_camera_component():
    html_code = """
    <div id="qr-container" style="text-align:center;">
        <button id="start-btn" style="margin:8px; padding:10px 20px; background:#1e4a6b; color:white; border:none; border-radius:10px; font-weight:bold;" onclick="startScanner()">📷 Abrir Câmera</button>
        <button id="stop-btn" style="display:none; margin:8px; padding:10px 20px; background:#b91c1c; color:white; border:none; border-radius:10px; font-weight:bold;" onclick="stopScanner()">🛑 Parar Câmera</button>
        <div id="reader" style="width:100%; max-width:350px; margin:auto;"></div>
        <script src="https://unpkg.com/html5-qrcode"></script>
        <script>
            let html5QrCode;
            function startScanner() {
                document.getElementById('start-btn').style.display = 'none';
                document.getElementById('stop-btn').style.display = 'inline-block';
                html5QrCode = new Html5Qrcode("reader");
                html5QrCode.start(
                    { facingMode: "environment" },
                    { fps: 10, qrbox: { width: 250, height: 250 } },
                    (decodedText) => {
                        // Envia para o Streamlit via postMessage
                        window.parent.postMessage({
                            type: "qr_result",
                            text: decodedText
                        }, "*");
                        stopScanner();
                    },
                    (error) => {}
                ).catch(err => {
                    console.error(err);
                    stopScanner();
                });
            }
            function stopScanner() {
                if (html5QrCode) {
                    html5QrCode.stop().then(() => {
                        document.getElementById('reader').innerHTML = '';
                        document.getElementById('start-btn').style.display = 'inline-block';
                        document.getElementById('stop-btn').style.display = 'none';
                    }).catch(err => console.error(err));
                }
            }
        </script>
    </div>
    """
    components.html(html_code, height=200)

# ------------------------------------------------------------
# AUTENTICAÇÃO PERSISTENTE
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
            except:
                pass
        st.session_state.autenticado = False
        st.session_state.eh_admin = False

def set_auth_cookie(eh_admin):
    token = base64.b64encode(json.dumps({"valido": True, "eh_admin": eh_admin}).encode()).decode()
    cookies["auth_token"] = token
    cookies.save()

def clear_auth():
    cookies["auth_token"] = ""
    cookies.save()
    st.session_state.autenticado = False
    st.session_state.eh_admin = False

check_auth()

if not st.session_state.autenticado:
    st.markdown('<div class="login-card">', unsafe_allow_html=True)
    if os.path.exists("logo.png"):
        st.image("logo.png", width=160)
    else:
        st.markdown("### 🏫 Centro Educa Mais Jansen Veloso")
    st.markdown('<div class="login-title">Sistema de Frequência</div>', unsafe_allow_html=True)
    senha = st.text_input("🔐 Senha de acesso", type="password")
    if st.button("🔓 Entrar", use_container_width=True):
        if senha == SENHA_ADMIN:
            st.session_state.autenticado = True
            st.session_state.eh_admin = True
            set_auth_cookie(True)
            st.rerun()
        elif senha == SENHA_OPERADOR:
            st.session_state.autenticado = True
            st.session_state.eh_admin = False
            set_auth_cookie(False)
            st.rerun()
        else:
            st.error("Senha incorreta!")
    st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# ------------------------------------------------------------
# SISTEMA PRINCIPAL
# ------------------------------------------------------------
# Cabeçalho centralizado
st.markdown('<div class="header-container">', unsafe_allow_html=True)
if os.path.exists("logo.png"):
    st.markdown('<img src="logo.png" class="logo-img">', unsafe_allow_html=True)
else:
    st.markdown("### 🏫 Centro Educa Mais Jansen Veloso")
st.markdown('<p class="main-title">Sistema de Frequência</p>', unsafe_allow_html=True)
st.markdown(f'<p class="sub-title">Centro Educa Mais Jansen Veloso • {datetime.now().strftime("%d de %B de %Y")}</p>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

col_h1, col_h2 = st.columns([4, 1])
with col_h2:
    if st.button("🚪 Sair"):
        clear_auth()
        st.rerun()

# Verificar alunos
df_alunos = carregar_alunos()
if df_alunos.empty:
    if st.session_state.eh_admin:
        st.warning("⚠️ Base de dados vazia. Como administrador, faça o upload do CSV.")
        uploaded = st.file_uploader("Escolha o ficheiro CSV", type=["csv"])
        if uploaded is not None:
            if importar_csv_para_bd(uploaded):
                st.success("Alunos importados! Recarregue a página.")
                st.stop()
    else:
        st.error("🚫 Sistema indisponível. Contacte o administrador.")
        st.stop()

if df_alunos.empty:
    st.stop()

# Métricas
hoje_str = datetime.now().strftime("%Y-%m-%d")
conn = conectar_bd()
total = len(df_alunos)
presentes = pd.read_sql_query("SELECT COUNT(*) FROM registros WHERE data=%s AND tipo_registro='PRESENCA'", conn, params=[hoje_str]).iloc[0,0]
faltas = pd.read_sql_query("SELECT COUNT(*) FROM registros WHERE data=%s AND tipo_registro='FALTA'", conn, params=[hoje_str]).iloc[0,0]
atrasos = pd.read_sql_query("SELECT COUNT(*) FROM registros WHERE data=%s AND tipo_registro='PRESENCA' AND status_entrada='ATRASO'", conn, params=[hoje_str]).iloc[0,0]
conn.close()

col_m1, col_m2, col_m3, col_m4 = st.columns(4)
col_m1.markdown(f'<div class="metric-card"><div class="metric-value">{total}</div><div class="metric-label">📋 Alunos</div></div>', unsafe_allow_html=True)
col_m2.markdown(f'<div class="metric-card" style="border-left-color:#10b981;"><div class="metric-value">{presentes}</div><div class="metric-label">✅ Presentes</div></div>', unsafe_allow_html=True)
col_m3.markdown(f'<div class="metric-card" style="border-left-color:#ef4444;"><div class="metric-value">{faltas}</div><div class="metric-label">❌ Faltas</div></div>', unsafe_allow_html=True)
col_m4.markdown(f'<div class="metric-card" style="border-left-color:#f59e0b;"><div class="metric-value">{atrasos}</div><div class="metric-label">⏰ Atrasos</div></div>', unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# Abas (incluindo nova aba Histórico)
abas = ["📸 CHECK-IN", "📊 GESTÃO", "🚨 ALERTAS", "⭐ PONTUALIDADE", "📈 HISTÓRICO"]
if st.session_state.eh_admin:
    abas.append("⚙️ MANUTENÇÃO")
tabs = st.tabs(abas)

# --------------------------- ABA CHECK-IN ---------------------------
with tabs[0]:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("📸 Registo de Entrada / Saída Antecipada")
    
    tab_entrada, tab_saida = st.tabs(["✅ Entrada", "🚪 Saída Antecipada"])
    
    with tab_entrada:
        st.write("**Entrada de estudantes**")
        # Leitor QR via câmera
        qr_camera_component()
        # Campo manual
        nome = st.text_input("✏️ Nome do aluno (ou cole o QR code lido)", key="entrada_nome")
        qr_manual = st.text_input("📱 Código QR (se disponível)", key="entrada_qr")
        if nome:
            registrar_presenca(nome.strip().upper())
        if qr_manual:
            registrar_presenca(qr_manual.strip().upper())
    
    with tab_saida:
        st.write("**Registar saída antecipada**")
        # Motivos comuns para ensino médio (pesquisados)
        motivos_saida = [
            "Consulta médica/odontológica",
            "Mal-estar ou sintomas de doença",
            "Compromisso familiar urgente",
            "Problemas pessoais/emocionais",
            "Atividade escolar externa autorizada",
            "Entrevista de emprego/estágio",
            "Problemas de transporte",
            "Outro (especificar)"
        ]
        motivo = st.selectbox("Motivo da saída", motivos_saida)
        if motivo == "Outro (especificar)":
            motivo_outro = st.text_input("Descreva o motivo")
            motivo_final = motivo_outro if motivo_outro else "Outro"
        else:
            motivo_final = motivo
        
        pais_informados = st.radio("Os pais/responsáveis foram informados?", ["Sim", "Não"], horizontal=True)
        pais_bool = (pais_informados == "Sim")
        
        # Leitura QR para saída
        st.write("**Leia o QR Code do aluno para registrar a saída**")
        qr_camera_component_saida = components.html("""
        <div id="qr-container-saida" style="text-align:center;">
            <button id="start-btn-saida" style="margin:8px; padding:10px 20px; background:#1e4a6b; color:white; border:none; border-radius:10px; font-weight:bold;" onclick="startScannerSaida()">📷 Abrir Câmera</button>
            <button id="stop-btn-saida" style="display:none; margin:8px; padding:10px 20px; background:#b91c1c; color:white; border:none; border-radius:10px; font-weight:bold;" onclick="stopScannerSaida()">🛑 Parar Câmera</button>
            <div id="reader-saida" style="width:100%; max-width:350px; margin:auto;"></div>
            <script src="https://unpkg.com/html5-qrcode"></script>
            <script>
                let html5QrCodeSaida;
                function startScannerSaida() {
                    document.getElementById('start-btn-saida').style.display = 'none';
                    document.getElementById('stop-btn-saida').style.display = 'inline-block';
                    html5QrCodeSaida = new Html5Qrcode("reader-saida");
                    html5QrCodeSaida.start(
                        { facingMode: "environment" },
                        { fps: 10, qrbox: { width: 250, height: 250 } },
                        (decodedText) => {
                            window.parent.postMessage({
                                type: "qr_saida",
                                text: decodedText
                            }, "*");
                            stopScannerSaida();
                        },
                        (error) => {}
                    ).catch(err => {
                        console.error(err);
                        stopScannerSaida();
                    });
                }
                function stopScannerSaida() {
                    if (html5QrCodeSaida) {
                        html5QrCodeSaida.stop().then(() => {
                            document.getElementById('reader-saida').innerHTML = '';
                            document.getElementById('start-btn-saida').style.display = 'inline-block';
                            document.getElementById('stop-btn-saida').style.display = 'none';
                        }).catch(err => console.error(err));
                    }
                }
            </script>
        </div>
        """, height=200)
        
        nome_saida = st.text_input("Nome do aluno (ou cole o QR code)", key="saida_nome")
        if st.button("Confirmar Saída", key="confirmar_saida"):
            if nome_saida and motivo_final:
                registrar_saida(nome_saida.strip().upper(), motivo_final, pais_bool, datetime.now().strftime("%H:%M:%S"))
            else:
                st.warning("Preencha o nome e o motivo.")
    st.markdown('</div>', unsafe_allow_html=True)

# --------------------------- ABA GESTÃO ---------------------------
with tabs[1]:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("📊 Frequência e Saídas")
    c1, c2, c3 = st.columns(3)
    with c1:
        data_filtro = st.date_input("📅 Data", datetime.now())
    with c2:
        turmas = ["Todas"] + sorted(df_alunos['turma'].unique())
        turma_filtro = st.selectbox("🏫 Turma", turmas)
    with c3:
        busca = st.text_input("🔍 Buscar aluno")
    data_str = data_filtro.strftime("%Y-%m-%d")
    conn = conectar_bd()
    params = [data_str]
    query = """SELECT r.data, a.turma, r.nome_aluno, r.hora_entrada, r.status_entrada, r.hora_saida, r.motivo_saida, r.pais_informados, r.tipo_registro
               FROM registros r JOIN alunos a ON r.nome_aluno = a.nome WHERE r.data = %s"""
    if turma_filtro != "Todas":
        query += " AND a.turma = %s"
        params.append(turma_filtro)
    if busca:
        query += " AND r.nome_aluno ILIKE %s"
        params.append(f"%{busca}%")
    query += " ORDER BY a.turma, r.nome_aluno"
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    st.dataframe(df, use_container_width=True, hide_index=True)
    if st.button("🔄 Gerar Faltas para o dia"):
        gerar_faltas_para_dia(data_str)
        st.success("Faltas geradas!")
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# --------------------------- ABA ALERTAS ---------------------------
with tabs[2]:
    hoje = datetime.now()
    dias_uteis = [(hoje - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7) if (hoje - timedelta(days=i)).weekday() < 5][:5]
    dias_uteis.sort()
    conn = conectar_bd()
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("🚨 Risco de Abandono (sem presença 5 dias)")
    if dias_uteis:
        df_faltas_alerta = pd.read_sql_query("SELECT a.nome, a.turma FROM alunos a WHERE a.nome NOT IN (SELECT DISTINCT nome_aluno FROM registros WHERE data IN %s AND tipo_registro='PRESENCA')", conn, params=[tuple(dias_uteis)])
        if not df_faltas_alerta.empty:
            st.error(f"{len(df_faltas_alerta)} alunos em risco")
            st.dataframe(df_faltas_alerta, hide_index=True)
        else:
            st.success("Nenhum aluno nesta situação.")
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("⚠️ Saídas Antecipadas (5 dias)")
    if dias_uteis:
        df_saidas_alerta = pd.read_sql_query("SELECT nome_aluno, COUNT(DISTINCT data) as dias FROM registros WHERE data IN %s AND tipo_registro='PRESENCA' AND hora_saida IS NOT NULL AND hora_saida < '17:00:00' GROUP BY nome_aluno HAVING COUNT(DISTINCT data) = 5", conn, params=[tuple(dias_uteis)])
        if not df_saidas_alerta.empty:
            st.warning(f"{len(df_saidas_alerta)} alunos com saídas antes das 17h")
            st.dataframe(df_saidas_alerta, hide_index=True)
        else:
            st.info("Nenhum.")
    st.markdown('</div>', unsafe_allow_html=True)
    conn.close()

# --------------------------- ABA PONTUALIDADE ---------------------------
with tabs[3]:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("⭐ Pontualidade (entrada antes das 07:15)")
    conn = conectar_bd()
    df_pont = pd.read_sql_query("SELECT r.nome_aluno, a.turma, r.hora_entrada FROM registros r JOIN alunos a ON r.nome_aluno=a.nome WHERE r.data=%s AND r.tipo_registro='PRESENCA' AND r.hora_entrada<='07:15:00' ORDER BY r.hora_entrada", conn, params=[hoje_str])
    conn.close()
    if not df_pont.empty:
        st.balloons()
        st.success(f"{len(df_pont)} alunos chegaram cedo!")
        st.dataframe(df_pont, hide_index=True, use_container_width=True)
    else:
        st.info("Ainda não há registos de entrada antes das 07:15.")
    st.markdown('</div>', unsafe_allow_html=True)

# --------------------------- ABA HISTÓRICO (NOVA) ---------------------------
with tabs[4]:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("📈 Histórico Individual do Aluno")
    todos_alunos = sorted(df_alunos['nome'].tolist())
    aluno_selecionado = st.selectbox("Selecione o aluno", todos_alunos)
    if aluno_selecionado:
        df_hist = obter_historico_aluno(aluno_selecionado)
        if not df_hist.empty:
            st.write(f"**Registos de {aluno_selecionado}**")
            st.dataframe(df_hist, use_container_width=True, hide_index=True)
            
            # Estatísticas resumidas
            total_faltas = len(df_hist[df_hist['tipo_registro'] == 'FALTA'])
            total_atrasos = len(df_hist[(df_hist['tipo_registro'] == 'PRESENCA') & (df_hist['status_entrada'] == 'ATRASO')])
            total_saidas = len(df_hist[df_hist['hora_saida'].notna()])
            
            col_e1, col_e2, col_e3 = st.columns(3)
            col_e1.metric("Total de Faltas", total_faltas)
            col_e2.metric("Total de Atrasos", total_atrasos)
            col_e3.metric("Saídas Antecipadas", total_saidas)
            
            # Gráfico de presenças/faltas ao longo do tempo (mensal)
            if len(df_hist) > 0:
                df_hist['data'] = pd.to_datetime(df_hist['data'])
                df_hist['mês'] = df_hist['data'].dt.to_period('M')
                # Contar presenças e faltas por mês
                presencas_mes = df_hist[df_hist['tipo_registro'] == 'PRESENCA'].groupby('mês').size().reset_index(name='Presenças')
                faltas_mes = df_hist[df_hist['tipo_registro'] == 'FALTA'].groupby('mês').size().reset_index(name='Faltas')
                if not presencas_mes.empty or not faltas_mes.empty:
                    # Mesclar
                    df_mensal = pd.merge(presencas_mes, faltas_mes, on='mês', how='outer').fillna(0)
                    df_mensal['mês'] = df_mensal['mês'].astype(str)
                    fig = px.bar(df_mensal, x='mês', y=['Presenças', 'Faltas'], 
                                 title=f"Presenças e Faltas por Mês - {aluno_selecionado}",
                                 labels={'value': 'Quantidade', 'mês': 'Mês'},
                                 barmode='group', color_discrete_sequence=['#10b981', '#ef4444'])
                    st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Sem dados históricos suficientes.")
        else:
            st.info("Nenhum registo encontrado para este aluno.")
    st.markdown('</div>', unsafe_allow_html=True)

# --------------------------- MANUTENÇÃO (admin) ---------------------------
if st.session_state.eh_admin:
    with tabs[5 if len(abas) > 5 else 4]:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("⚙️ Importar CSV")
        uploaded_admin = st.file_uploader("Escolha o ficheiro CSV", type=["csv"], key="admin_csv")
        if uploaded_admin is not None:
            if importar_csv_para_bd(uploaded_admin):
                st.success("Alunos atualizados!")
        st.subheader("🗑️ Limpar registos")
        senha_conf = st.text_input("Confirme com a senha de administrador", type="password")
        if st.button("Apagar todos os registos"):
            if senha_conf == SENHA_ADMIN:
                limpar_todos_registros()
                st.success("Registos apagados.")
                st.balloons()
            else:
                st.error("Senha incorreta!")
        st.markdown('</div>', unsafe_allow_html=True)
