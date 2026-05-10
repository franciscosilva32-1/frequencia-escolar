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
# COOKIES PARA SESSÃO PERSISTENTE
# ------------------------------------------------------------
cookies = CookieManager()
if not cookies.ready():
    st.stop()

# ------------------------------------------------------------
# CSS MODERNO E RESPONSIVO
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
        --warning: #f1c40f;
        --bg: #f0f4f8;
    }

    .stApp {
        background: linear-gradient(180deg, #f8fafc 0%, #e9edf2 100%);
    }
    #MainMenu, footer, header {visibility: hidden;}

    /* Cabeçalho com logo centralizada */
    .header-container {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 1rem 0 0.5rem;
    }
    .logo-img {
        max-width: 150px;
        width: 30%;
        min-width: 120px;
        margin-bottom: 0.5rem;
    }

    .main-title {
        font-family: 'Inter', sans-serif;
        font-weight: 800;
        font-size: clamp(1.8rem, 6vw, 2.8rem);
        color: var(--primary);
        text-align: center;
        margin: 0;
        letter-spacing: -0.5px;
    }
    .sub-title {
        font-family: 'Inter', sans-serif;
        font-size: 0.9rem;
        color: #5f6b7a;
        text-align: center;
        margin-bottom: 1.5rem;
    }

    /* Cards com vidro */
    .card {
        background: rgba(255,255,255,0.7);
        backdrop-filter: blur(10px);
        border-radius: 20px;
        padding: 1.2rem;
        margin-bottom: 1rem;
        box-shadow: 0 8px 20px rgba(0,0,0,0.04);
        border: 1px solid rgba(255,255,255,0.8);
    }

    /* Métricas */
    .metric-grid {
        display: flex;
        flex-wrap: wrap;
        gap: 0.8rem;
        margin-bottom: 1.2rem;
    }
    .metric-item {
        flex: 1 1 100px;
        background: white;
        border-radius: 16px;
        padding: 0.8rem 0.5rem;
        text-align: center;
        box-shadow: 0 4px 12px rgba(0,0,0,0.04);
        border-bottom: 4px solid var(--accent);
        transition: transform 0.2s;
    }
    .metric-item:hover {
        transform: translateY(-2px);
    }
    .metric-value {
        font-family: 'Inter', sans-serif;
        font-weight: 800;
        font-size: 1.8rem;
        color: var(--primary);
        line-height: 1.2;
    }
    .metric-label {
        font-family: 'Inter', sans-serif;
        font-size: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #5f6b7a;
        margin-top: 0.2rem;
    }

    /* Botões */
    .stButton > button {
        font-family: 'Inter', sans-serif;
        font-weight: 600;
        border-radius: 12px;
        background: linear-gradient(135deg, var(--primary-light), var(--primary));
        color: white;
        border: none;
        padding: 0.6rem 1.5rem;
        box-shadow: 0 4px 10px rgba(31, 74, 107, 0.2);
        transition: all 0.3s;
        letter-spacing: 0.3px;
    }
    .stButton > button:hover {
        background: linear-gradient(135deg, var(--primary), var(--primary-light));
        box-shadow: 0 6px 15px rgba(31, 74, 107, 0.3);
        transform: translateY(-1px);
    }

    /* Abas */
    .stTabs [data-baseweb="tab-list"] {
        background: rgba(255,255,255,0.5);
        padding: 4px;
        border-radius: 16px;
        gap: 4px;
    }
    .stTabs [data-baseweb="tab"] {
        font-family: 'Inter', sans-serif;
        font-weight: 600;
        font-size: 0.9rem;
        border-radius: 14px;
        padding: 8px 16px;
        transition: all 0.2s;
    }
    .stTabs [aria-selected="true"] {
        background: var(--primary) !important;
        color: white !important;
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
    }

    /* Inputs */
    .stTextInput > div > div > input {
        border-radius: 12px;
        border: 2px solid #d1d9e0;
        padding: 0.5rem 0.8rem;
        background: white;
        font-family: 'Inter', sans-serif;
    }

    /* QR code scanner container */
    .qr-scanner {
        background: #f8fafc;
        border-radius: 16px;
        padding: 0.5rem;
        margin: 0.5rem 0;
        border: 2px dashed #cbd5e1;
        text-align: center;
    }
    .qr-scanner button {
        margin: 5px !important;
        font-size: 0.9rem;
        padding: 8px 16px;
    }

    /* Login */
    .login-card {
        max-width: 380px;
        margin: 10vh auto;
        background: rgba(255,255,255,0.8);
        backdrop-filter: blur(16px);
        border-radius: 28px;
        padding: 2rem 1.5rem;
        box-shadow: 0 25px 40px rgba(0,0,0,0.1);
        text-align: center;
    }
    .login-title {
        font-family: 'Inter', sans-serif;
        font-weight: 700;
        font-size: 1.5rem;
        color: var(--primary);
        margin-bottom: 1.5rem;
    }

    /* Responsividade */
    @media (max-width: 768px) {
        .metric-value { font-size: 1.5rem; }
        .stButton > button { width: 100%; }
        .stTabs [data-baseweb="tab"] { padding: 6px 12px; font-size: 0.8rem; }
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
            st.success(f"✅ {nome_estudante} registado às {hora_atual}")
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
        st.success(f"✅ Saída de {nome} registada")
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
# COMPONENTE QR (leitor via câmera, discreto)
# ------------------------------------------------------------
def qr_reader_component(placeholder_id, button_label="📷 Ler QR Code"):
    html = f"""
    <div id="qr-{placeholder_id}" class="qr-scanner">
        <button id="start-{placeholder_id}" onclick="startQr_{placeholder_id}()">{button_label}</button>
        <button id="stop-{placeholder_id}" style="display:none;" onclick="stopQr_{placeholder_id}()">🛑 Parar</button>
        <div id="reader-{placeholder_id}" style="width:100%; max-width:300px; margin:auto;"></div>
    </div>
    <script src="https://unpkg.com/html5-qrcode"></script>
    <script>
        let scanner_{placeholder_id};
        function startQr_{placeholder_id}() {{
            document.getElementById('start-{placeholder_id}').style.display = 'none';
            document.getElementById('stop-{placeholder_id}').style.display = 'inline-block';
            scanner_{placeholder_id} = new Html5Qrcode("reader-{placeholder_id}");
            scanner_{placeholder_id}.start(
                {{ facingMode: "environment" }},
                {{ fps: 10, qrbox: {{ width: 200, height: 200 }} }},
                (decodedText) => {{
                    window.parent.postMessage({{
                        type: "qr_result",
                        source: "{placeholder_id}",
                        text: decodedText
                    }}, "*");
                    stopQr_{placeholder_id}();
                }},
                (error) => {{}}
            ).catch(err => {{
                alert("Erro ao acessar a câmera. Verifique se as permissões estão habilitadas.");
                stopQr_{placeholder_id}();
            }});
        }}
        function stopQr_{placeholder_id}() {{
            if (scanner_{placeholder_id}) {{
                scanner_{placeholder_id}.stop().then(() => {{
                    document.getElementById('reader-{placeholder_id}').innerHTML = '';
                    document.getElementById('start-{placeholder_id}').style.display = 'inline-block';
                    document.getElementById('stop-{placeholder_id}').style.display = 'none';
                }}).catch(err => console.error(err));
            }}
        }}
    </script>
    """
    return components.html(html, height=160)

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
        st.image("logo.png", width=130)
    else:
        st.markdown("### 🏫")
    st.markdown('<div class="login-title">Centro Educa Mais Jansen Veloso</div>', unsafe_allow_html=True)
    senha = st.text_input("Senha", type="password")
    if st.button("Entrar", use_container_width=True):
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
# INTERFACE PRINCIPAL
# ------------------------------------------------------------
# Cabeçalho com logo
st.markdown('<div class="header-container">', unsafe_allow_html=True)
if os.path.exists("logo.png"):
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.image("logo.png", width=200, output_format="PNG")
else:
    st.markdown("### 🏫")
st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<p class="main-title">Sistema de Frequência</p>', unsafe_allow_html=True)
st.markdown(f'<p class="sub-title">Centro Educa Mais Jansen Veloso • {datetime.now().strftime("%d de %B de %Y")}</p>', unsafe_allow_html=True)

col_logout1, col_logout2 = st.columns([4, 1])
with col_logout2:
    if st.button("Sair", key="logout"):
        clear_auth()
        st.rerun()

# Verificar dados
df_alunos = carregar_alunos()
if df_alunos.empty:
    if st.session_state.eh_admin:
        st.warning("Banco vazio. Importe o CSV.")
        up = st.file_uploader("CSV", type=["csv"])
        if up:
            if importar_csv_para_bd(up):
                st.success("Importado!")
                st.stop()
    else:
        st.error("Sistema indisponível.")
        st.stop()

if df_alunos.empty:
    st.stop()

# Métricas (cards modernos)
hoje_str = datetime.now().strftime("%Y-%m-%d")
conn = conectar_bd()
total = len(df_alunos)
presentes = pd.read_sql_query("SELECT COUNT(*) FROM registros WHERE data=%s AND tipo_registro='PRESENCA'", conn, params=[hoje_str]).iloc[0,0]
faltas = pd.read_sql_query("SELECT COUNT(*) FROM registros WHERE data=%s AND tipo_registro='FALTA'", conn, params=[hoje_str]).iloc[0,0]
atrasos = pd.read_sql_query("SELECT COUNT(*) FROM registros WHERE data=%s AND tipo_registro='PRESENCA' AND status_entrada='ATRASO'", conn, params=[hoje_str]).iloc[0,0]
conn.close()

st.markdown('<div class="metric-grid">', unsafe_allow_html=True)
st.markdown(f'<div class="metric-item"><div class="metric-value">{total}</div><div class="metric-label">📋 Alunos</div></div>', unsafe_allow_html=True)
st.markdown(f'<div class="metric-item" style="border-bottom-color: #27ae60;"><div class="metric-value">{presentes}</div><div class="metric-label">✅ Presentes</div></div>', unsafe_allow_html=True)
st.markdown(f'<div class="metric-item" style="border-bottom-color: #e74c3c;"><div class="metric-value">{faltas}</div><div class="metric-label">❌ Faltas</div></div>', unsafe_allow_html=True)
st.markdown(f'<div class="metric-item" style="border-bottom-color: #f39c12;"><div class="metric-value">{atrasos}</div><div class="metric-label">⏰ Atrasos</div></div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# Abas
abas = ["📸 Check-in", "📊 Gestão", "🚨 Alertas", "⭐ Pontualidade", "📈 Histórico"]
if st.session_state.eh_admin:
    abas.append("⚙️ Manutenção")
tabs = st.tabs(abas)

# CHECK-IN
with tabs[0]:
    tab1, tab2 = st.tabs(["Entrada", "Saída Antecipada"])
    with tab1:
        st.write("**Entrada de estudante**")
        # QR reader
        qr_reader_component("entrada", "📷 Abrir câmera")
        colA, colB = st.columns(2)
        with colA:
            nome_entrada = st.text_input("Nome do aluno", key="in_nome", placeholder="Digite ou leia QR code")
        with colB:
            qr_entrada = st.text_input("QR code manual", key="in_qr", placeholder="Código lido")
        if nome_entrada:
            registrar_presenca(nome_entrada.strip().upper())
        if qr_entrada:
            registrar_presenca(qr_entrada.strip().upper())

    with tab2:
        st.write("**Saída antecipada**")
        motivos = [
            "Consulta médica/odontológica",
            "Mal-estar/sintomas de doença",
            "Compromisso familiar urgente",
            "Problemas pessoais/emocionais",
            "Atividade escolar externa autorizada",
            "Entrevista de emprego/estágio",
            "Problemas de transporte",
            "Outro"
        ]
        motivo = st.selectbox("Motivo", motivos)
        if motivo == "Outro":
            motivo = st.text_input("Especifique", key="motivo_outro")
        pais = st.radio("Pais informados?", ["Sim", "Não"], horizontal=True)
        qr_reader_component("saida", "📷 Ler QR para saída")
        nome_saida = st.text_input("Nome do aluno", key="out_nome", placeholder="Nome ou QR code")
        if st.button("Registrar Saída", key="btn_saida"):
            if nome_saida and motivo:
                registrar_saida(nome_saida.strip().upper(), motivo, pais == "Sim", datetime.now().strftime("%H:%M:%S"))
            else:
                st.warning("Preencha o nome e o motivo.")

# GESTÃO
with tabs[1]:
    c1, c2, c3 = st.columns(3)
    with c1:
        data_filtro = st.date_input("Data", datetime.now())
    with c2:
        turmas = ["Todas"] + sorted(df_alunos['turma'].unique())
        turma_filtro = st.selectbox("Turma", turmas)
    with c3:
        busca = st.text_input("Buscar aluno")
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
    if st.button("Gerar faltas para o dia"):
        gerar_faltas_para_dia(data_str)
        st.success("Faltas geradas.")
        st.rerun()

# ALERTAS
with tabs[2]:
    hoje = datetime.now()
    dias_uteis = [(hoje - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7) if (hoje - timedelta(days=i)).weekday() < 5][:5]
    dias_uteis.sort()
    conn = conectar_bd()
    st.subheader("Alunos sem presença (5 dias)")
    if dias_uteis:
        df_faltas_alerta = pd.read_sql_query("SELECT a.nome, a.turma FROM alunos a WHERE a.nome NOT IN (SELECT DISTINCT nome_aluno FROM registros WHERE data IN %s AND tipo_registro='PRESENCA')", conn, params=[tuple(dias_uteis)])
        if not df_faltas_alerta.empty:
            st.error(f"{len(df_faltas_alerta)} alunos")
            st.dataframe(df_faltas_alerta, hide_index=True)
        else:
            st.success("Nenhum.")
    st.subheader("Saídas antecipadas (5 dias)")
    if dias_uteis:
        df_saidas_alerta = pd.read_sql_query("SELECT nome_aluno, COUNT(DISTINCT data) as dias FROM registros WHERE data IN %s AND tipo_registro='PRESENCA' AND hora_saida IS NOT NULL AND hora_saida < '17:00:00' GROUP BY nome_aluno HAVING COUNT(DISTINCT data) = 5", conn, params=[tuple(dias_uteis)])
        if not df_saidas_alerta.empty:
            st.warning(f"{len(df_saidas_alerta)} alunos")
            st.dataframe(df_saidas_alerta, hide_index=True)
        else:
            st.info("Nenhum.")
    conn.close()

# PONTUALIDADE
with tabs[3]:
    conn = conectar_bd()
    df_pont = pd.read_sql_query("SELECT r.nome_aluno, a.turma, r.hora_entrada FROM registros r JOIN alunos a ON r.nome_aluno=a.nome WHERE r.data=%s AND r.tipo_registro='PRESENCA' AND r.hora_entrada<='07:15:00' ORDER BY r.hora_entrada", conn, params=[hoje_str])
    conn.close()
    if not df_pont.empty:
        st.balloons()
        st.success(f"{len(df_pont)} alunos antes das 07:15")
        st.dataframe(df_pont, hide_index=True)
    else:
        st.info("Nada ainda.")

# HISTÓRICO (com plotly)
with tabs[4]:
    aluno = st.selectbox("Aluno", sorted(df_alunos['nome'].tolist()))
    if aluno:
        df_hist = obter_historico_aluno(aluno)
        if not df_hist.empty:
            st.dataframe(df_hist, hide_index=True)
            faltas_n = len(df_hist[df_hist['tipo_registro'] == 'FALTA'])
            atrasos_n = len(df_hist[(df_hist['tipo_registro'] == 'PRESENCA') & (df_hist['status_entrada'] == 'ATRASO')])
            saidas_n = len(df_hist[df_hist['hora_saida'].notna()])
            c1, c2, c3 = st.columns(3)
            c1.metric("Faltas", faltas_n)
            c2.metric("Atrasos", atrasos_n)
            c3.metric("Saídas", saidas_n)
            # Gráfico mensal
            df_hist['data'] = pd.to_datetime(df_hist['data'])
            df_hist['mês'] = df_hist['data'].dt.to_period('M').astype(str)
            pres = df_hist[df_hist['tipo_registro'] == 'PRESENCA'].groupby('mês').size().reset_index(name='Presenças')
            fal = df_hist[df_hist['tipo_registro'] == 'FALTA'].groupby('mês').size().reset_index(name='Faltas')
            if not pres.empty or not fal.empty:
                df_mes = pd.merge(pres, fal, on='mês', how='outer').fillna(0)
                fig = px.bar(df_mes, x='mês', y=['Presenças', 'Faltas'], barmode='group',
                             color_discrete_sequence=['#27ae60', '#e74c3c'])
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Sem dados suficientes.")
        else:
            st.info("Sem registros.")

# MANUTENÇÃO (admin)
if st.session_state.eh_admin:
    with tabs[5 if len(abas) > 5 else 4]:
        st.subheader("Importar CSV")
        up_admin = st.file_uploader("Arquivo", type=["csv"])
        if up_admin and importar_csv_para_bd(up_admin):
            st.success("Alunos atualizados.")
        st.subheader("Limpar frequência")
        senha = st.text_input("Senha admin", type="password")
        if st.button("Limpar tudo"):
            if senha == SENHA_ADMIN:
                limpar_todos_registros()
                st.success("Registros apagados.")
            else:
                st.error("Senha incorreta.")
