import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import psycopg2
import os

# ------------------------------------------------------------
# CONFIGURAÇÃO DA PÁGINA
# ------------------------------------------------------------
st.set_page_config(page_title="Gestão de Presença Escolar", page_icon="🏫", layout="wide")

# ------------------------------------------------------------
# CONEXÃO COM O SUPABASE (PostgreSQL)
# ------------------------------------------------------------
DATABASE_URL = st.secrets.get("DATABASE_URL", os.environ.get("DATABASE_URL"))

if not DATABASE_URL:
    st.error("⚠️ DATABASE_URL não configurada. Adicione nos Secrets do Streamlit Cloud ou defina a variável de ambiente.")
    st.stop()

def conectar_bd():
    return psycopg2.connect(DATABASE_URL)

# ------------------------------------------------------------
# INICIALIZAÇÃO DAS TABELAS
# ------------------------------------------------------------
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
    """Lê o CSV e insere os alunos na base de dados do Supabase."""
    try:
        try:
            df = pd.read_csv(arquivo_csv, sep=';', encoding='utf-8')
        except UnicodeDecodeError:
            df = pd.read_csv(arquivo_csv, sep=';', encoding='latin1')
    except Exception as e:
        st.error(f"Erro ao ler o ficheiro: {e}")
        return False

    # Padronizar nomes das colunas
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
            st.warning(f"Erro ao inserir {nome}: {e}")
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

    # Verificar se o aluno existe
    cur.execute("SELECT nome FROM alunos WHERE nome = %s", (nome_estudante,))
    if not cur.fetchone():
        st.error(f"❌ Aluno não encontrado: {nome_estudante}")
        conn.close()
        return

    # Verificar se já tem presença hoje
    cur.execute("""
        SELECT * FROM registros 
        WHERE nome_aluno = %s AND data = %s AND tipo_registro = 'PRESENCA'
    """, (nome_estudante, data_hoje))
    if cur.fetchone():
        st.warning(f"⚠️ {nome_estudante} já registou entrada hoje.")
        conn.close()
        return

    # Se existir FALTA hoje, remove
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
        st.success(f"Saída antecipada registada para {nome}.")
    else:
        st.error(f"Erro: não há registo de entrada para {nome} hoje.")
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
# INTERFACE PRINCIPAL
# ------------------------------------------------------------
st.title("🏫 Sistema Inteligente de Frequência (Online Permanente)")

# Verificar se existem alunos
df_alunos = carregar_alunos()
if df_alunos.empty:
    st.warning("⚠️ Nenhum aluno encontrado. Faça o upload do ficheiro BASE DE DADOS.CSV.")
    uploaded = st.file_uploader("Escolha o ficheiro CSV (separado por ';')", type=["csv"])
    if uploaded is not None:
        if importar_csv_para_bd(uploaded):
            st.success("Alunos importados com sucesso! Recarregue a página (F5) para continuar.")
            st.stop()
    else:
        st.info("Assim que carregar o ficheiro, a página será recarregada automaticamente.")
        st.stop()

# Abas
aba_checkin, aba_gestao, aba_alertas, aba_pontualidade = st.tabs([
    "📸 Check-in", 
    "📊 Gestão e Filtros", 
    "🚨 Alertas", 
    "⭐ Pontualidade"
])

# --------------------------- ABA CHECK-IN ---------------------------
with aba_checkin:
    st.header("Entrada de Estudantes")
    nome = st.text_input("Nome do aluno (como no cartão):", key="manual")
    if nome:
        registrar_presenca(nome.strip().upper())
    qr = st.text_input("QR Code:", key="qr")
    if qr:
        registrar_presenca(qr.strip().upper())

# --------------------------- ABA GESTÃO ---------------------------
with aba_gestao:
    st.header("Consulta de Frequência e Saídas")
    col1, col2, col3 = st.columns(3)
    with col1:
        data_filtro = st.date_input("Data", datetime.now())
    with col2:
        turmas = ["Todas"] + sorted(df_alunos['turma'].unique().tolist())
        turma_filtro = st.selectbox("Turma", turmas)
    with col3:
        busca = st.text_input("Buscar aluno")

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
    st.dataframe(df, use_container_width=True)

    if st.button("Gerar faltas para o dia selecionado"):
        gerar_faltas_para_dia(data_str)
        st.success(f"Faltas geradas para {data_str}.")
        st.rerun()

    st.divider()
    st.subheader("Registar saída antecipada (hoje)")
    hoje_str = datetime.now().strftime("%Y-%m-%d")
    conn = conectar_bd()
    presentes = pd.read_sql_query("""
        SELECT nome_aluno FROM registros 
        WHERE data = %s AND tipo_registro = 'PRESENCA' AND hora_saida IS NULL
    """, conn, params=[hoje_str])
    conn.close()
    if not presentes.empty:
        aluno_saida = st.selectbox("Aluno", presentes['nome_aluno'])
        motivo = st.text_input("Motivo")
        hora = st.time_input("Hora da saída", datetime.now().time())
        if st.button("Confirmar saída"):
            if aluno_saida and motivo:
                registrar_saida(aluno_saida, motivo, hora.strftime("%H:%M:%S"))
            else:
                st.warning("Preencha o aluno e o motivo.")
    else:
        st.info("Nenhum aluno presente hoje sem saída registada.")

# --------------------------- ABA ALERTAS ---------------------------
with aba_alertas:
    st.header("Alertas de Abandono e Saídas Antecipadas")
    hoje = datetime.now()
    dias_uteis = [(hoje - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7) if (hoje - timedelta(days=i)).weekday() < 5][:5]
    dias_uteis.sort()

    conn = conectar_bd()
    # Alunos sem presença nos últimos 5 dias úteis
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

    st.subheader("🚨 Sem qualquer presença nos últimos 5 dias úteis")
    if not df_faltas.empty:
        st.error("Alunos em risco de abandono:")
        st.dataframe(df_faltas, hide_index=True)
    else:
        st.success("Nenhum aluno nesta situação.")

    # Saídas antecipadas em todos os 5 dias
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
    st.subheader("⚠️ Saídas antes das 17h em todos os 5 dias")
    if not df_saidas.empty:
        st.warning("Alunos com saídas antecipadas constantes:")
        st.dataframe(df_saidas, hide_index=True)
    else:
        st.info("Nenhum aluno com esse comportamento.")
    conn.close()

# --------------------------- ABA PONTUALIDADE ---------------------------
with aba_pontualidade:
    st.header("⭐ Pontualidade de Hoje")
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
        st.success(f"{len(df_pont)} alunos chegaram antes das 07:15!")
        st.dataframe(df_pont, use_container_width=True, hide_index=True)
    else:
        st.info("Ainda não há registos de entrada antes das 07:15 hoje.")