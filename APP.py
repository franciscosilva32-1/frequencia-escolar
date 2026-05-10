import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import psycopg2
import os

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
# CSS PROFISSIONAL
# ------------------------------------------------------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Montserrat:wght@600;700;800&display=swap');

    .stApp {
        background: linear-gradient(160deg, #f8fafc 0%, #eef2f6 50%, #e2e8f0 100%);
    }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    .card {
        background: rgba(255,255,255,0.9);
        backdrop-filter: blur(10px);
        border-radius: 20px;
        padding: 1.8rem;
        margin-bottom: 1.5rem;
        box-shadow: 0 8px 32px rgba(0,0,0,0.08);
        border: 1px solid rgba(255,255,255,0.6);
        transition: all 0.3s ease;
    }
    .card:hover {
        box-shadow: 0 12px 40px rgba(0,0,0,0.12);
    }

    .main-title {
        font-family: 'Montserrat', sans-serif;
        font-size: 2.8rem;
        font-weight: 800;
        background: linear-gradient(135deg, #0f2b4a, #1a4972);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        font-family: 'Inter', sans-serif;
        font-size: 1.05rem;
        color: #64748b;
        text-align: center;
        margin-bottom: 1.5rem;
    }

    .metric-card {
        background: white;
        border-radius: 18px;
        padding: 1.5rem 1rem;
        text-align: center;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        border-left: 5px solid #f0a500;
        transition: all 0.3s;
    }
    .metric-value {
        font-family: 'Montserrat', sans-serif;
        font-size: 2.5rem;
        font-weight: 800;
        color: #0f2b4a;
    }
    .metric-label {
        font-family: 'Inter', sans-serif;
        font-size: 0.9rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #64748b;
    }

    .stButton > button {
        font-family: 'Inter', sans-serif;
        font-weight: 600;
        font-size: 1rem;
        padding: 0.7rem 2rem;
        border-radius: 14px;
        border: none;
        background: linear-gradient(135deg, #1a3a5c, #2c5f8a);
        color: white;
        transition: all 0.3s ease;
        box-shadow: 0 4px 14px rgba(26,58,92,0.3);
    }
    .stButton > button:hover {
        background: linear-gradient(135deg, #2c5f8a, #1a3a5c);
        box-shadow: 0 6px 20px rgba(26,58,92,0.4);
        transform: translateY(-2px);
    }

    .danger-button > button {
        background: linear-gradient(135deg, #b91c1c, #dc2626) !important;
        box-shadow: 0 4px 14px rgba(220,38,38,0.3) !important;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 12px;
        background: rgba(241,245,249,0.8);
        padding: 8px;
        border-radius: 16px;
    }
    .stTabs [data-baseweb="tab"] {
        font-family: 'Inter', sans-serif;
        font-weight: 600;
        padding: 12px 22px;
        border-radius: 12px;
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #0f2b4a, #1a4972) !important;
        color: white !important;
    }

    .stTextInput > div > div > input {
        border-radius: 12px;
        border: 2px solid #e2e8f0;
        padding: 0.7rem 1rem;
        font-family: 'Inter', sans-serif;
    }

    .login-card {
        max-width: 440px;
        margin: 80px auto;
        background: white;
        border-radius: 28px;
        padding: 2.5rem 2rem;
        box-shadow: 0 30px 60px rgba(0,0,0,0.15);
        text-align: center;
    }
    .login-title {
        font-family: 'Montserrat', sans-serif;
        font-size: 1.6rem;
        font-weight: 700;
        color: #0f2b4a;
        margin: 1rem 0 1.5rem;
    }
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------
# CONEXÃO SUPABASE
# ------------------------------------------------------------
DATABASE_URL = st.secrets.get("DATABASE_URL", os.environ.get("DATABASE_URL"))
SENHA_OPERADOR = st.secrets.get("SENHA_OPERADOR", "admin123")
SENHA_ADMIN = st.secrets.get("SENHA_ADMIN", "admin123")  # Nova senha mestra

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
            tipo_registro TEXT,
            UNIQUE(nome_aluno, data, tipo_registro)
        )
    ''')
    conn.commit()
    conn.close()

inicializar_tabelas()

# ------------------------------------------------------------
# FUNÇÕES DE NEGÓCIO (inalteradas, exceto a de limpar)
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
        st.error("O CSV precisa das colunas NOME e TURMA.")
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
            st.success(f"✅ Entrada: {nome_estudante} às {hora_atual}")
        else:
            st.warning(f"⏰ Atraso: {nome_estudante} às {hora_atual}")
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        st.warning("Registo duplicado.")
    conn.close()

def registrar_saida(nome, motivo, hora_saida):
    data_hoje = datetime.now().strftime("%Y-%m-%d")
    conn = conectar_bd()
    cur = conn.cursor()
    cur.execute("UPDATE registros SET hora_saida = %s, motivo_saida = %s WHERE nome_aluno = %s AND data = %s AND tipo_registro = 'PRESENCA'", (hora_saida, motivo, nome, data_hoje))
    if cur.rowcount > 0:
        st.success(f"✅ Saída registada: {nome}")
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

# ------------------------------------------------------------
# TELA DE LOGIN (comum a todos)
# ------------------------------------------------------------
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
    st.session_state.eh_admin = False

if not st.session_state.autenticado:
    st.markdown('<div class="login-card">', unsafe_allow_html=True)
    if os.path.exists("logo.png"):
        st.image("logo.png", width=140)
    else:
        st.markdown("🏫")
    st.markdown('<div class="login-title">Centro Educa Mais<br>Jansen Veloso</div>', unsafe_allow_html=True)
    senha = st.text_input("🔐 Senha de acesso", type="password")
    if st.button("🔓 Entrar", use_container_width=True):
        if senha == SENHA_ADMIN:
            st.session_state.autenticado = True
            st.session_state.eh_admin = True
            st.rerun()
        elif senha == SENHA_OPERADOR:
            st.session_state.autenticado = True
            st.session_state.eh_admin = False
            st.rerun()
        else:
            st.error("Senha incorreta!")
    st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# ------------------------------------------------------------
# SISTEMA PRINCIPAL (após login)
# ------------------------------------------------------------
# Cabeçalho
col_logo, col_tit = st.columns([1, 5])
with col_logo:
    if os.path.exists("logo.png"):
        st.image("logo.png", width=130)
with col_tit:
    st.markdown('<p class="main-title">Sistema de Frequência</p>', unsafe_allow_html=True)
    st.markdown(f'<p class="sub-title">Centro Educa Mais Jansen Veloso • {datetime.now().strftime("%d de %B de %Y")}</p>', unsafe_allow_html=True)

col_h1, col_h2 = st.columns([4, 1])
with col_h2:
    if st.button("🚪 Sair"):
        st.session_state.autenticado = False
        st.session_state.eh_admin = False
        st.rerun()

# Verificar se há alunos
df_alunos = carregar_alunos()
if df_alunos.empty:
    if st.session_state.eh_admin:
        st.warning("⚠️ Base de dados vazia. Como administrador, pode importar o CSV agora.")
        uploaded = st.file_uploader("Escolha o ficheiro CSV", type=["csv"])
        if uploaded is not None:
            if importar_csv_para_bd(uploaded):
                st.success("Alunos importados com sucesso! Recarregue a página.")
                st.stop()
    else:
        st.error("🚫 Sistema indisponível. Contacte o administrador.")
        st.stop()
else:
    # Se há alunos, o admin ainda pode reimportar? Vamos deixar apenas na aba Manutenção.
    pass

# Se não há alunos e é admin, já tratamos; se há alunos, continua normal.
if df_alunos.empty:
    st.stop()  # impede o resto se ainda estiver vazio e for admin (após upload, recarrega)

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

# Abas – a aba Manutenção só aparece para admin
abas = ["📸 CHECK-IN", "📊 GESTÃO", "🚨 ALERTAS", "⭐ PONTUALIDADE"]
if st.session_state.eh_admin:
    abas.append("⚙️ MANUTENÇÃO")

tabs = st.tabs(abas)

# CHECK-IN
with tabs[0]:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("📸 Registo de Entrada")
    c1, c2 = st.columns(2)
    with c1:
        nome = st.text_input("✏️ Nome do aluno", placeholder="Nome completo...")
        if nome:
            registrar_presenca(nome.strip().upper())
    with c2:
        qr = st.text_input("📱 Leitor QR Code", placeholder="Cursor aqui...")
        if qr:
            registrar_presenca(qr.strip().upper())
    st.markdown('</div>', unsafe_allow_html=True)

# GESTÃO
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
    query = """SELECT r.data, a.turma, r.nome_aluno, r.hora_entrada, r.status_entrada, r.hora_saida, r.motivo_saida, r.tipo_registro
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

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("🚪 Saída Antecipada (Hoje)")
    conn = conectar_bd()
    presentes_df = pd.read_sql_query("SELECT nome_aluno FROM registros WHERE data=%s AND tipo_registro='PRESENCA' AND hora_saida IS NULL", conn, params=[hoje_str])
    conn.close()
    if not presentes_df.empty:
        c1, c2, c3, c4 = st.columns([2,2,2,1])
        with c1:
            aluno_s = st.selectbox("Aluno", presentes_df['nome_aluno'])
        with c2:
            motivo = st.text_input("Motivo")
        with c3:
            hora_s = st.time_input("Hora", datetime.now().time())
        with c4:
            st.write(""); st.write("")
            if st.button("✅", use_container_width=True):
                if motivo:
                    registrar_saida(aluno_s, motivo, hora_s.strftime("%H:%M:%S"))
                else:
                    st.warning("Informe o motivo.")
    else:
        st.info("Nenhum aluno presente sem saída.")
    st.markdown('</div>', unsafe_allow_html=True)

# ALERTAS
with tabs[2]:
    hoje = datetime.now()
    dias_uteis = [(hoje - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7) if (hoje - timedelta(days=i)).weekday() < 5][:5]
    dias_uteis.sort()
    conn = conectar_bd()
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("🚨 Abandono (sem presença 5 dias)")
    if dias_uteis:
        df_faltas = pd.read_sql_query("SELECT a.nome, a.turma FROM alunos a WHERE a.nome NOT IN (SELECT DISTINCT nome_aluno FROM registros WHERE data IN %s AND tipo_registro='PRESENCA')", conn, params=[tuple(dias_uteis)])
        if not df_faltas.empty:
            st.error(f"{len(df_faltas)} alunos em risco")
            st.dataframe(df_faltas, hide_index=True)
        else:
            st.success("Nenhum aluno nesta situação.")
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("⚠️ Saídas antecipadas (5 dias)")
    if dias_uteis:
        df_saidas = pd.read_sql_query("SELECT nome_aluno, COUNT(DISTINCT data) FROM registros WHERE data IN %s AND tipo_registro='PRESENCA' AND hora_saida<'17:00:00' GROUP BY nome_aluno HAVING COUNT(DISTINCT data)=5", conn, params=[tuple(dias_uteis)])
        if not df_saidas.empty:
            st.warning(f"{len(df_saidas)} alunos")
            st.dataframe(df_saidas, hide_index=True)
        else:
            st.info("Nenhum.")
    st.markdown('</div>', unsafe_allow_html=True)
    conn.close()

# PONTUALIDADE
with tabs[3]:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("⭐ Pontualidade (antes 07:15)")
    conn = conectar_bd()
    df_pont = pd.read_sql_query("SELECT r.nome_aluno, a.turma, r.hora_entrada FROM registros r JOIN alunos a ON r.nome_aluno=a.nome WHERE r.data=%s AND r.tipo_registro='PRESENCA' AND r.hora_entrada<='07:15:00' ORDER BY r.hora_entrada", conn, params=[hoje_str])
    conn.close()
    if not df_pont.empty:
        st.balloons()
        st.success(f"{len(df_pont)} alunos chegaram cedo!")
        st.dataframe(df_pont, hide_index=True, use_container_width=True)
    else:
        st.info("Nenhum registo.")
    st.markdown('</div>', unsafe_allow_html=True)

# MANUTENÇÃO (só admin)
if st.session_state.eh_admin:
    with tabs[4]:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("⚙️ Importar CSV (admin)")
        uploaded_admin = st.file_uploader("Substituir lista de alunos", type=["csv"])
        if uploaded_admin is not None:
            if importar_csv_para_bd(uploaded_admin):
                st.success("Alunos atualizados!")
        st.subheader("🗑️ Limpar todos os registos de frequência")
        senha_conf = st.text_input("Confirme com a senha de administrador", type="password")
        if st.button("Apagar todos os registos"):
            if senha_conf == SENHA_ADMIN:
                limpar_todos_registros()
                st.success("Registos apagados. Pode recomeçar os testes.")
                st.balloons()
            else:
                st.error("Senha incorreta!")
        st.markdown('</div>', unsafe_allow_html=True)
