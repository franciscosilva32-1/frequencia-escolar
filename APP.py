import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import psycopg2
import os
from PIL import Image
import base64

# ------------------------------------------------------------
# CONFIGURAÇÃO DA PÁGINA (DEVE SER O PRIMEIRO COMANDO)
# ------------------------------------------------------------
st.set_page_config(
    page_title="Centro Educa Mais Jansen Veloso",
    page_icon="🏫",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ------------------------------------------------------------
# CSS PERSONALIZADO - DESIGN MODERNO E PROFISSIONAL
# ------------------------------------------------------------
st.markdown("""
<style>
    /* Importar fontes */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
    
    /* Variáveis de cores */
    :root {
        --primary: #1a3a5c;
        --primary-light: #2c5f8a;
        --accent: #f0a500;
        --accent-light: #ffc940;
        --success: #10b981;
        --warning: #f59e0b;
        --danger: #ef4444;
        --bg-light: #f8fafc;
        --text-dark: #1e293b;
        --text-light: #64748b;
    }
    
    /* Estilo global */
    .stApp {
        background: linear-gradient(135deg, #f0f4f8 0%, #e2e8f0 100%);
    }
    
    /* Esconder menu padrão */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Título principal */
    .main-title {
        font-family: 'Inter', sans-serif;
        font-size: 2.5rem;
        font-weight: 800;
        color: #1a3a5c;
        text-align: center;
        padding: 1rem;
        margin-bottom: 0.5rem;
        background: linear-gradient(135deg, #1a3a5c 0%, #2c5f8a 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }
    
    .sub-title {
        font-family: 'Inter', sans-serif;
        font-size: 1rem;
        color: #64748b;
        text-align: center;
        margin-bottom: 2rem;
    }
    
    /* Cards */
    .card {
        background: white;
        border-radius: 16px;
        padding: 1.5rem;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1);
        border: 1px solid #e2e8f0;
        transition: all 0.3s ease;
    }
    
    .card:hover {
        box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1);
        transform: translateY(-2px);
    }
    
    /* Botões personalizados */
    .stButton > button {
        font-family: 'Inter', sans-serif;
        font-weight: 600;
        font-size: 1rem;
        padding: 0.75rem 2rem;
        border-radius: 12px;
        border: none;
        background: linear-gradient(135deg, #1a3a5c 0%, #2c5f8a 100%);
        color: white;
        transition: all 0.3s ease;
        box-shadow: 0 4px 6px -1px rgba(26, 58, 92, 0.3);
    }
    
    .stButton > button:hover {
        background: linear-gradient(135deg, #2c5f8a 0%, #1a3a5c 100%);
        box-shadow: 0 10px 15px -3px rgba(26, 58, 92, 0.4);
        transform: translateY(-2px);
    }
    
    .stButton > button:active {
        transform: translateY(0);
    }
    
    /* Abas personalizadas */
    .stTabs [data-baseweb="tab-list"] {
        gap: 12px;
        background-color: #f1f5f9;
        padding: 8px;
        border-radius: 16px;
    }
    
    .stTabs [data-baseweb="tab"] {
        font-family: 'Inter', sans-serif;
        font-weight: 600;
        font-size: 1rem;
        padding: 12px 24px;
        border-radius: 12px;
        transition: all 0.3s ease;
    }
    
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #1a3a5c 0%, #2c5f8a 100%) !important;
        color: white !important;
        box-shadow: 0 4px 6px -1px rgba(26, 58, 92, 0.3);
    }
    
    /* Métricas */
    .metric-card {
        background: white;
        border-radius: 16px;
        padding: 1.5rem;
        text-align: center;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        border-left: 4px solid #f0a500;
    }
    
    .metric-value {
        font-family: 'Inter', sans-serif;
        font-size: 2.5rem;
        font-weight: 800;
        color: #1a3a5c;
    }
    
    .metric-label {
        font-family: 'Inter', sans-serif;
        font-size: 0.9rem;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    
    /* Inputs */
    .stTextInput > div > div > input {
        border-radius: 12px;
        border: 2px solid #e2e8f0;
        padding: 0.75rem 1rem;
        font-family: 'Inter', sans-serif;
        transition: all 0.3s ease;
    }
    
    .stTextInput > div > div > input:focus {
        border-color: #2c5f8a;
        box-shadow: 0 0 0 3px rgba(44, 95, 138, 0.1);
    }
    
    /* Select box */
    .stSelectbox > div > div {
        border-radius: 12px;
    }
    
    /* Dataframe */
    .stDataFrame {
        border-radius: 16px;
        overflow: hidden;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    
    /* Alertas personalizados */
    .stSuccess {
        background: linear-gradient(135deg, #d1fae5 0%, #a7f3d0 100%);
        border: none;
        border-radius: 12px;
        color: #065f46;
    }
    
    .stWarning {
        background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
        border: none;
        border-radius: 12px;
        color: #92400e;
    }
    
    .stError {
        background: linear-gradient(135deg, #fee2e2 0%, #fecaca 100%);
        border: none;
        border-radius: 12px;
        color: #991b1b;
    }
    
    /* Login card */
    .login-card {
        max-width: 450px;
        margin: 100px auto;
        background: white;
        border-radius: 24px;
        padding: 3rem;
        box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
    }
    
    .login-icon {
        font-size: 4rem;
        text-align: center;
        margin-bottom: 1rem;
    }
    
    .login-title {
        font-family: 'Inter', sans-serif;
        font-size: 1.8rem;
        font-weight: 700;
        color: #1a3a5c;
        text-align: center;
        margin-bottom: 2rem;
    }
    
    /* Cabeçalho após login */
    .header-bar {
        background: white;
        padding: 1rem 2rem;
        border-radius: 16px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        margin-bottom: 2rem;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    
    .header-school {
        font-family: 'Inter', sans-serif;
        font-size: 1.2rem;
        font-weight: 700;
        color: #1a3a5c;
    }
    
    .header-date {
        font-family: 'Inter', sans-serif;
        font-size: 0.9rem;
        color: #64748b;
    }
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------
# CONEXÃO COM O SUPABASE
# ------------------------------------------------------------
DATABASE_URL = st.secrets.get("DATABASE_URL", os.environ.get("DATABASE_URL"))
SENHA_OPERADOR = st.secrets.get("SENHA_OPERADOR", "admin123")

if not DATABASE_URL:
    st.error("⚠️ DATABASE_URL não configurada.")
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
            tipo_registro TEXT,
            UNIQUE(nome_aluno, data, tipo_registro)
        )
    ''')
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
    try:
        try:
            df = pd.read_csv(arquivo_csv, sep=';', encoding='utf-8')
        except UnicodeDecodeError:
            df = pd.read_csv(arquivo_csv, sep=';', encoding='latin1')
    except Exception as e:
        st.error(f"Erro ao ler o ficheiro: {e}")
        return False

    df.columns = [col.strip().upper() for col in df.columns]
    if 'NOME' not in df.columns or 'TURMA' not in df.columns:
        st.error("O ficheiro CSV deve conter as colunas 'NOME' e 'TURMA'.")
        return False

    conn = conectar_bd()
    cur = conn.cursor()
    inseridos = 0
    for _, row in df.iterrows():
        nome = str(row['NOME']).strip().upper()
        turma = str(row['TURMA']).strip().upper()
        try:
            cur.execute("INSERT INTO alunos (nome, turma) VALUES (%s, %s)", (nome, turma))
            inseridos += 1
        except psycopg2.errors.UniqueViolation:
            conn.rollback()
        except Exception as e:
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

    cur.execute("""
        SELECT * FROM registros 
        WHERE nome_aluno = %s AND data = %s AND tipo_registro = 'PRESENCA'
    """, (nome_estudante, data_hoje))
    if cur.fetchone():
        st.warning(f"⚠️ {nome_estudante} já registou entrada hoje.")
        conn.close()
        return

    cur.execute("DELETE FROM registros WHERE nome_aluno = %s AND data = %s AND tipo_registro = 'FALTA'", (nome_estudante, data_hoje))
    conn.commit()

    try:
        cur.execute("""
            INSERT INTO registros (nome_aluno, data, hora_entrada, status_entrada, tipo_registro)
            VALUES (%s, %s, %s, %s, 'PRESENCA')
        """, (nome_estudante, data_hoje, hora_atual, status))
        conn.commit()
        if status == "PRESENTE":
            st.success(f"✅ Entrada registada: {nome_estudante} às {hora_atual}")
        else:
            st.warning(f"⏰ Entrada com Atraso: {nome_estudante} às {hora_atual}")
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        st.warning("Já existe um registo de presença para este aluno hoje.")
    finally:
        conn.close()

def registrar_saida(nome, motivo, hora_saida):
    data_hoje = datetime.now().strftime("%Y-%m-%d")
    conn = conectar_bd()
    cur = conn.cursor()
    cur.execute("""
        UPDATE registros 
        SET hora_saida = %s, motivo_saida = %s 
        WHERE nome_aluno = %s AND data = %s AND tipo_registro = 'PRESENCA'
    """, (hora_saida, motivo, nome, data_hoje))
    if cur.rowcount > 0:
        st.success(f"✅ Saída antecipada registada para {nome}.")
    else:
        st.error(f"❌ Erro: não há registo de entrada para {nome} hoje.")
    conn.commit()
    conn.close()

def gerar_faltas_para_dia(data_str):
    conn = conectar_bd()
    cur = conn.cursor()
    cur.execute("SELECT nome FROM alunos")
    alunos = [row[0] for row in cur.fetchall()]
    for aluno in alunos:
        cur.execute("""
            SELECT tipo_registro FROM registros 
            WHERE nome_aluno = %s AND data = %s AND tipo_registro IN ('PRESENCA', 'FALTA')
        """, (aluno, data_str))
        if not cur.fetchone():
            try:
                cur.execute("""
                    INSERT INTO registros (nome_aluno, data, tipo_registro)
                    VALUES (%s, %s, 'FALTA')
                """, (aluno, data_str))
            except psycopg2.errors.UniqueViolation:
                conn.rollback()
    conn.commit()
    conn.close()

# ------------------------------------------------------------
# TELA DE LOGIN
# ------------------------------------------------------------
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.markdown('<div class="login-card">', unsafe_allow_html=True)
    st.markdown('<div class="login-icon">🏫</div>', unsafe_allow_html=True)
    st.markdown('<div class="login-title">Centro Educa Mais<br>Jansen Veloso</div>', unsafe_allow_html=True)
    
    senha_digitada = st.text_input("🔐 Senha de Operador", type="password", placeholder="Digite a senha...")
    
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        if st.button("🔓 Entrar", use_container_width=True):
            if senha_digitada == SENHA_OPERADOR:
                st.session_state.autenticado = True
                st.rerun()
            else:
                st.error("Senha incorreta!")
    
    st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# ------------------------------------------------------------
# SISTEMA PRINCIPAL (APÓS LOGIN)
# ------------------------------------------------------------

# Cabeçalho
hoje_formatado = datetime.now().strftime("%d de %B de %Y")
col_h1, col_h2 = st.columns([3, 1])
with col_h1:
    st.markdown('<p class="main-title">🏫 Sistema de Frequência</p>', unsafe_allow_html=True)
    st.markdown(f'<p class="sub-title">Centro Educa Mais Jansen Veloso • {hoje_formatado}</p>', unsafe_allow_html=True)
with col_h2:
    if st.button("🚪 Sair", key="logout"):
        st.session_state.autenticado = False
        st.rerun()

# Verificar se existem alunos
df_alunos = carregar_alunos()
if df_alunos.empty:
    st.warning("⚠️ Nenhum aluno encontrado. Faça o upload do ficheiro BASE DE DADOS.CSV.")
    uploaded = st.file_uploader("Escolha o ficheiro CSV (separado por ';')", type=["csv"])
    if uploaded is not None:
        if importar_csv_para_bd(uploaded):
            st.success("✅ Alunos importados com sucesso! Recarregue a página (F5) para continuar.")
            st.stop()
    else:
        st.info("Assim que carregar o ficheiro, a página será recarregada automaticamente.")
        st.stop()

# Métricas rápidas
hoje_str = datetime.now().strftime("%Y-%m-%d")
conn = conectar_bd()
total_alunos = len(df_alunos)
presentes_hoje = pd.read_sql_query("SELECT COUNT(*) as c FROM registros WHERE data = %s AND tipo_registro = 'PRESENCA'", conn, params=[hoje_str]).iloc[0,0]
faltas_hoje = pd.read_sql_query("SELECT COUNT(*) as c FROM registros WHERE data = %s AND tipo_registro = 'FALTA'", conn, params=[hoje_str]).iloc[0,0]
atrasos_hoje = pd.read_sql_query("SELECT COUNT(*) as c FROM registros WHERE data = %s AND tipo_registro = 'PRESENCA' AND status_entrada = 'ATRASO'", conn, params=[hoje_str]).iloc[0,0]
conn.close()

col_m1, col_m2, col_m3, col_m4 = st.columns(4)
with col_m1:
    st.markdown(f'<div class="metric-card"><div class="metric-value">{total_alunos}</div><div class="metric-label">📋 Total de Alunos</div></div>', unsafe_allow_html=True)
with col_m2:
    st.markdown(f'<div class="metric-card" style="border-left-color: #10b981;"><div class="metric-value">{presentes_hoje}</div><div class="metric-label">✅ Presentes Hoje</div></div>', unsafe_allow_html=True)
with col_m3:
    st.markdown(f'<div class="metric-card" style="border-left-color: #ef4444;"><div class="metric-value">{faltas_hoje}</div><div class="metric-label">❌ Faltas Hoje</div></div>', unsafe_allow_html=True)
with col_m4:
    st.markdown(f'<div class="metric-card" style="border-left-color: #f59e0b;"><div class="metric-value">{atrasos_hoje}</div><div class="metric-label">⏰ Atrasos Hoje</div></div>', unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# Abas
aba_checkin, aba_gestao, aba_alertas, aba_pontualidade = st.tabs([
    "📸 CHECK-IN", 
    "📊 GESTÃO E FILTROS", 
    "🚨 ALERTAS", 
    "⭐ PONTUALIDADE"
])

# --------------------------- ABA CHECK-IN ---------------------------
with aba_checkin:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("📸 Registo de Entrada")
    st.write("Digite o nome do aluno ou use o leitor de QR Code.")
    
    col_q1, col_q2 = st.columns(2)
    with col_q1:
        nome = st.text_input("✏️ Nome do aluno:", key="manual", placeholder="Digite o nome completo...")
        if nome:
            registrar_presenca(nome.strip().upper())
    with col_q2:
        qr = st.text_input("📱 Leitor QR Code:", key="qr", placeholder="Cursor aqui para leitura do cartão...")
        if qr:
            registrar_presenca(qr.strip().upper())
    st.markdown('</div>', unsafe_allow_html=True)

# --------------------------- ABA GESTÃO ---------------------------
with aba_gestao:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("📊 Consulta de Frequência e Saídas")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        data_filtro = st.date_input("📅 Data", datetime.now())
    with col2:
        turmas = ["Todas"] + sorted(df_alunos['turma'].unique().tolist())
        turma_filtro = st.selectbox("🏫 Turma", turmas)
    with col3:
        busca = st.text_input("🔍 Buscar aluno", placeholder="Nome do aluno...")

    data_str = data_filtro.strftime("%Y-%m-%d")
    conn = conectar_bd()
    params = [data_str]
    query = """
        SELECT r.data, a.turma, r.nome_aluno, r.hora_entrada, r.status_entrada, 
               r.hora_saida, r.motivo_saida, r.tipo_registro
        FROM registros r
        JOIN alunos a ON r.nome_aluno = a.nome
        WHERE r.data = %s
    """
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

    col_b1, col_b2 = st.columns([1, 3])
    with col_b1:
        if st.button("🔄 Gerar Faltas"):
            gerar_faltas_para_dia(data_str)
            st.success(f"✅ Faltas geradas para {data_str}.")
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("🚪 Registar Saída Antecipada (Hoje)")
    hoje_str = datetime.now().strftime("%Y-%m-%d")
    conn = conectar_bd()
    presentes = pd.read_sql_query("""
        SELECT nome_aluno FROM registros 
        WHERE data = %s AND tipo_registro = 'PRESENCA' AND hora_saida IS NULL
    """, conn, params=[hoje_str])
    conn.close()
    if not presentes.empty:
        col_s1, col_s2, col_s3, col_s4 = st.columns([2, 2, 2, 1])
        with col_s1:
            aluno_saida = st.selectbox("👤 Aluno", presentes['nome_aluno'])
        with col_s2:
            motivo = st.text_input("📝 Motivo", placeholder="Ex: Consulta médica...")
        with col_s3:
            hora = st.time_input("🕐 Hora da saída", datetime.now().time())
        with col_s4:
            st.write("")
            st.write("")
            if st.button("✅ Confirmar", use_container_width=True):
                if aluno_saida and motivo:
                    registrar_saida(aluno_saida, motivo, hora.strftime("%H:%M:%S"))
                else:
                    st.warning("Preencha todos os campos.")
    else:
        st.info("ℹ️ Nenhum aluno presente hoje sem saída registada.")
    st.markdown('</div>', unsafe_allow_html=True)

# --------------------------- ABA ALERTAS ---------------------------
with aba_alertas:
    hoje = datetime.now()
    dias_uteis = [(hoje - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7) if (hoje - timedelta(days=i)).weekday() < 5][:5]
    dias_uteis.sort()

    conn = conectar_bd()
    
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("🚨 Risco de Abandono")
    if dias_uteis:
        query_faltas = """
            SELECT a.nome, a.turma
            FROM alunos a
            WHERE a.nome NOT IN (
                SELECT DISTINCT nome_aluno FROM registros 
                WHERE data IN %s AND tipo_registro = 'PRESENCA'
            )
        """
        df_faltas = pd.read_sql_query(query_faltas, conn, params=[tuple(dias_uteis)])
    else:
        df_faltas = pd.DataFrame()
    if not df_faltas.empty:
        st.error(f"⚠️ {len(df_faltas)} alunos sem presença nos últimos 5 dias úteis:")
        st.dataframe(df_faltas, hide_index=True, use_container_width=True)
    else:
        st.success("✅ Nenhum aluno em risco de abandono.")
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("⚠️ Saídas Antecipadas Frequentes")
    if dias_uteis:
        query_saidas = """
            SELECT nome_aluno, COUNT(DISTINCT data) as dias_saindo_cedo
            FROM registros
            WHERE data IN %s
              AND tipo_registro = 'PRESENCA'
              AND hora_saida IS NOT NULL
              AND hora_saida < '17:00:00'
            GROUP BY nome_aluno
            HAVING COUNT(DISTINCT data) = 5
        """
        df_saidas = pd.read_sql_query(query_saidas, conn, params=[tuple(dias_uteis)])
    else:
        df_saidas = pd.DataFrame()
    if not df_saidas.empty:
        st.warning(f"⚠️ {len(df_saidas)} alunos com saídas antecipadas em todos os 5 dias:")
        st.dataframe(df_saidas, hide_index=True, use_container_width=True)
    else:
        st.info("ℹ️ Nenhum aluno com saídas antecipadas excessivas.")
    st.markdown('</div>', unsafe_allow_html=True)
    
    conn.close()

# --------------------------- ABA PONTUALIDADE ---------------------------
with aba_pontualidade:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("⭐ Destaques de Pontualidade")
    hoje_str = datetime.now().strftime("%Y-%m-%d")
    conn = conectar_bd()
    df_pont = pd.read_sql_query("""
        SELECT r.nome_aluno, a.turma, r.hora_entrada
        FROM registros r
        JOIN alunos a ON r.nome_aluno = a.nome
        WHERE r.data = %s AND r.tipo_registro = 'PRESENCA' AND r.hora_entrada <= '07:15:00'
        ORDER BY r.hora_entrada ASC
    """, conn, params=[hoje_str])
    conn.close()
    if not df_pont.empty:
        st.balloons()
        st.success(f"🌟 {len(df_pont)} alunos chegaram antes das 07:15 hoje!")
        st.dataframe(df_pont, use_container_width=True, hide_index=True)
    else:
        st.info("ℹ️ Ainda não há registos de entrada antes das 07:15 hoje.")
    st.markdown('</div>', unsafe_allow_html=True)
