import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import psycopg2
from psycopg2 import pool
from psycopg2.extras import execute_values
import os
import io
import base64
import json
import unicodedata
import streamlit.components.v1 as components
from streamlit_cookies_manager import CookieManager
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import threading
import time
import re
import plotly.express as px
import tempfile
import numpy as np
import zipfile

try:
    from fpdf import FPDF
except ImportError:
    FPDF = None

try:
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

# ------------------------------------------------------------
# 1. CONFIGURAÇÃO INICIAL E COOKIES
# ------------------------------------------------------------
st.set_page_config(page_title="Centro Educa Mais Jansen Veloso", page_icon="🏫", layout="wide", initial_sidebar_state="collapsed")

if 'fila_offline' not in st.session_state: st.session_state.fila_offline = []
if 'pesquisa_enviada' not in st.session_state: st.session_state.pesquisa_enviada = False

from streamlit_cookies_manager import CookieManager
cookies = CookieManager()

# === CORREÇÃO DO ERRO DE SESSIONINFO AQUI ===
if not cookies.ready(): 
    st.warning("⏳ A inicializar as configurações de segurança. Por favor, aguarde um segundo...")
    st.stop() # Pára a execução até que a sessão esteja 100% pronta, evitando conflitos.

# ------------------------------------------------------------
# 2. BANCO DE DADOS (CONNECTION POOLING OTIMIZADO)
# ------------------------------------------------------------
DATABASE_URL = st.secrets.get("DATABASE_URL")
SENHA_OPERADOR = st.secrets.get("SENHA_OPERADOR", "admin123")
SENHA_ADMIN = st.secrets.get("SENHA_ADMIN", "admin123")

@st.cache_resource
def get_connection_pool():
    return pool.ThreadedConnectionPool(
        1, 
        20, 
        DATABASE_URL,
        connect_timeout=3,
        options="-c statement_timeout=5000"
    )

def conectar_bd():
    pool_bd = get_connection_pool()
    tentativas = 3
    
    # O sistema tenta até 3 vezes encontrar uma conexão viva no pool
    for _ in range(tentativas):
        conn = None
        try:
            # Puxa uma conexão disponível
            conn = pool_bd.getconn()
            if conn:
                # Health check: testa se a conexão está realmente viva
                cur = conn.cursor()
                cur.execute("SELECT 1")
                cur.close()
                return conn # Se chegou aqui, a conexão está perfeita!
        except Exception:
            # Se a conexão falhar (caiu ou expirou), descarta-a adequadamente
            if conn:
                pool_bd.putconn(conn, close=True)
                
    # Se falhar 3 vezes consecutivas, assume que a rede está indisponível
    return None

def liberar_conn(conn):
    if conn:
        try:
            # Devolve a conexão saudável ao pool para ser reutilizada
            get_connection_pool().putconn(conn)
        except Exception:
            pass # Previne travamentos caso o pool já tenha sido encerrado

# ------------------------------------------------------------
# 3. FUNÇÕES DE SUPORTE (TEMPO, E-MAIL E CORES)
# ------------------------------------------------------------
def obter_hora_atual(): 
    return datetime.utcnow() - timedelta(hours=3)

def data_formatada_ptbr():
    dt = obter_hora_atual()
    meses = ["", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
    return f"{dt.day:02d} de {meses[dt.month]} de {dt.year}"

ATIVAR_EMAILS = True  
EMAIL_ESCOLA = st.secrets.get("EMAIL_ESCOLA", "") 
SENHA_APP_ESCOLA = st.secrets.get("SENHA_APP_ESCOLA", "") 

DICIONARIO_CORES = {
    "LP": "#2563eb", "MAT": "#dc2626", "MTM": "#dc2626", "BIO": "#16a34a",
    "ART": "#d97706", "EDF": "#7c3aed", "ESP": "#db2777", "FIL": "#4f46e5",
    "FIS": "#0d9488", "GGF": "#ea580c", "HST": "#9333ea", "ING": "#0891b2",
    "QUI": "#65a30d", "SOC": "#ca8a04",
    "LÍNGUA PORTUGUESA": "#2563eb", "MATEMÁTICA": "#dc2626",
    "LINGUAGENS": "#d97706", "HUMANAS": "#7c3aed", "NATUREZA": "#16a34a"
}

DICIONARIO_ABREVIACAO = {
    "BIOLOGIA": "BIO", "ARTE": "ART", "EDUCAÇÃO FÍSICA": "EDF",
    "LÍNGUA ESPANHOLA": "ESP", "FILOSOFIA": "FIL", "FÍSICA": "FIS",
    "GEOGRAFIA": "GGF", "MATEMÁTICA": "MTM", "HISTÓRIA": "HST",
    "LÍNGUA INGLESA": "ING", "LÍNGUA PORTUGUESA": "LP", "LÍNGUA PORTUGESA": "LP",
    "QUÍMICA": "QUI", "SOCIOLOGIA": "SOC", "SOCIOLGIA": "SOC"
}

DICIONARIO_PERGUNTAS_SATISFACAO = {
    "Todos": ["Conservação/Limpeza", "Acolhimento/Atenção", "Satisfação Geral", "Específica 1", "Específica 2"],
    "Estudante": ["Conservação/Limpeza", "Acolhimento/Atenção", "Satisfação Geral", "Qualidade das Aulas", "Organização Eventos"],
    "Pais/Responsável": ["Conservação/Limpeza", "Acolhimento/Atenção", "Satisfação Geral", "Facilidade Certificados", "Comunicação Escola"],
    "Professor": ["Conservação/Limpeza", "Acolhimento/Atenção", "Satisfação Geral", "Recursos Pedagógicos", "Engajamento Alunos"],
    "Servidor": ["Conservação/Limpeza", "Acolhimento/Atenção", "Satisfação Geral", "Condições de Trabalho", "Clima Organizacional"]
}

def disparar_email_background(email_destino, nome_aluno, evento, horario, data):
    try: 
        data_f = datetime.strptime(data, "%Y-%m-%d").strftime("%d/%m/%Y")
    except: 
        data_f = data
    
    if evento.startswith("ENTRADA"):
        assunto = f"🏫 Aviso de Entrada - Jansen Veloso"
        if "ATRASO" in evento: 
            texto = f"Olá, família!\n\nInformamos que o estudante {nome_aluno} registrou ENTRADA COM ATRASO na escola hoje ({data_f}) às {horario}.\n\nAtenciosamente,\nEquipe Jansen Veloso."
        else: 
            texto = f"Olá, família!\n\nInformamos que o estudante {nome_aluno} registrou ENTRADA na escola hoje ({data_f}) às {horario} (Dentro do horário regular).\n\nAtenciosamente,\nEquipe Jansen Veloso."
    elif evento == "SAÍDA REGULAR":
        assunto = f"🏫 Aviso de Saída - Jansen Veloso"
        texto = f"Olá, família!\n\nInformamos que o estudante {nome_aluno} registrou SAÍDA REGULAR da escola hoje ({data_f}) às {horario}.\n\nAtenciosamente,\nEquipe Jansen Veloso."
    else:
        assunto = f"🏫 Aviso de SAÍDA ANTECIPADA - Jansen Veloso"
        texto = f"⚠️ ATENÇÃO!\n\nInformamos que o estudante {nome_aluno} registrou uma SAÍDA ANTECIPADA hoje ({data_f}) às {horario}.\n\nAtenciosamente,\nEquipe Jansen Veloso."
    
    msg = MIMEMultipart()
    msg['From'] = EMAIL_ESCOLA
    msg['To'] = email_destino
    msg['Subject'] = assunto
    msg.attach(MIMEText(texto, 'plain'))
    
    def enviar():
        if ATIVAR_EMAILS and EMAIL_ESCOLA and SENHA_APP_ESCOLA:
            try:
                server = smtplib.SMTP('smtp.gmail.com', 587)
                server.starttls()
                server.login(EMAIL_ESCOLA, SENHA_APP_ESCOLA)
                server.send_message(msg)
                server.quit()
            except: 
                pass
                
    threading.Thread(target=enviar).start()

@st.cache_resource 
def carregar_logo_base64():
    if os.path.exists("logo.png"):
        try:
            with open("logo.png", "rb") as image_file: 
                return base64.b64encode(image_file.read()).decode()
        except: 
            return None
    return None

def renderizar_logo_central():
    encoded_string = carregar_logo_base64()
    if encoded_string:
        st.markdown(f'<div style="display: flex; justify-content: center; margin-bottom: 10px;"><img src="data:image/png;base64,{encoded_string}" width="170"></div>', unsafe_allow_html=True)

# ------------------------------------------------------------
# 4. INICIALIZAÇÃO DE TABELAS (CACHE RESOURCE)
# ------------------------------------------------------------
@st.cache_resource
def inicializar_tabelas():
    conn = conectar_bd()
    if not conn: 
        return
        
    try:
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS alunos_v2 (codigo TEXT PRIMARY KEY, nome TEXT, turma TEXT, status TEXT DEFAULT 'ATIVO', email_responsavel TEXT)")
        cur.execute("CREATE TABLE IF NOT EXISTS registros_v2 (id SERIAL PRIMARY KEY, codigo_aluno TEXT REFERENCES alunos_v2(codigo), data DATE, hora_entrada TIME, status_entrada TEXT, hora_saida TIME, motivo_saida TEXT, pais_informados BOOLEAN, tipo_registro TEXT, UNIQUE(codigo_aluno, data, tipo_registro))")
        cur.execute("CREATE TABLE IF NOT EXISTS avaliacoes_avs (id SERIAL PRIMARY KEY, ano TEXT, periodo TEXT, area TEXT, turma TEXT, nome TEXT, disciplina TEXT, questao INTEGER, resposta TEXT, gabarito TEXT, acerto INTEGER, UNIQUE(ano, periodo, area, turma, nome, disciplina, questao))")
        cur.execute("""CREATE TABLE IF NOT EXISTS faltas_primeira_chamada (
            id SERIAL PRIMARY KEY, codigo_aluno TEXT REFERENCES alunos_v2(codigo), ano TEXT, periodo TEXT, area TEXT, motivo TEXT, data_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP, UNIQUE(codigo_aluno, ano, periodo, area)
        )""")
        conn.commit() 
        
        try: 
            cur.execute("ALTER TABLE faltas_primeira_chamada ADD COLUMN area TEXT DEFAULT 'GERAL'")
            conn.commit()
        except Exception: 
            conn.rollback() 
            
        try:
            cur.execute("SELECT constraint_name FROM information_schema.table_constraints WHERE table_name='faltas_primeira_chamada' AND constraint_type='UNIQUE'")
            constraints = cur.fetchall()
            for c in constraints: 
                cur.execute(f"ALTER TABLE faltas_primeira_chamada DROP CONSTRAINT {c[0]}")
            cur.execute("ALTER TABLE faltas_primeira_chamada ADD UNIQUE (codigo_aluno, ano, periodo, area)")
            conn.commit()
        except Exception: 
            conn.rollback()
            
        try: 
            cur.execute("ALTER TABLE avaliacoes_avs ADD COLUMN ano TEXT DEFAULT '2026'")
            conn.commit()
        except Exception: 
            conn.rollback()
            
        try:
            cur.execute("SELECT constraint_name FROM information_schema.table_constraints WHERE table_name='avaliacoes_avs' AND constraint_type='UNIQUE'")
            constraints = cur.fetchall()
            for c in constraints: 
                cur.execute(f"ALTER TABLE avaliacoes_avs DROP CONSTRAINT {c[0]}")
            cur.execute("ALTER TABLE avaliacoes_avs ADD UNIQUE (ano, periodo, area, turma, nome, disciplina, questao)")
            conn.commit()
        except Exception: 
            conn.rollback()
            
        cur.execute("""CREATE TABLE IF NOT EXISTS satisfacao_v1 (
            id SERIAL PRIMARY KEY, data_hora TIMESTAMP, categoria TEXT, turma TEXT, q1 INTEGER, q2 INTEGER, q3 INTEGER, q4 INTEGER, q5 INTEGER, sugestao TEXT
        )""")
        cur.execute("CREATE TABLE IF NOT EXISTS calendario_letivo (data DATE PRIMARY KEY, dia_letivo BOOLEAN DEFAULT TRUE)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_reg_data ON registros_v2(data)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_avs_geral ON avaliacoes_avs(ano, periodo, area, turma)")
        conn.commit()
        
        for tb in ['alunos_v2', 'registros_v2', 'avaliacoes_avs', 'faltas_primeira_chamada', 'satisfacao_v1', 'calendario_letivo']:
            try: 
                cur.execute(f"ALTER TABLE {tb} ENABLE ROW LEVEL SECURITY;")
                conn.commit()
            except Exception: 
                conn.rollback() 
                
    except Exception as e: 
        print(f"Erro inicialização: {e}")
    finally: 
        liberar_conn(conn)

inicializar_tabelas()

# ------------------------------------------------------------
# 5. CSS (Limpo de conflitos com classes removidas)
# ------------------------------------------------------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap');
    :root { --primary: #0a1f35; --accent: #ff7b00; --success: #10b981; --danger: #ef4444; --bg-color: #f8fafc; }
    .stApp { background: var(--bg-color); }
    #MainMenu, footer, header {visibility: hidden;}
    html, body, [class*="css"], p, span, label, div { font-size: 1.15rem !important; }
    [data-testid="stRadio"] div[role="radiogroup"] > label { font-size: 1.3rem !important; padding: 16px 15px !important; margin-bottom: 12px !important; background-color: #ffffff !important; color: #000000 !important; border: 2px solid #cbd5e1 !important; border-radius: 12px; box-shadow: 0 3px 6px rgba(0,0,0,0.04); cursor: pointer; transition: all 0.2s ease; }
    [data-testid="stRadio"] div[role="radiogroup"] > label * { color: #000000 !important; -webkit-text-fill-color: #000000 !important; }
    [data-testid="stRadio"] div[role="radiogroup"] > label:hover { border-color: var(--accent) !important; transform: translateY(-2px); }
    .main-title { font-family: 'Inter', sans-serif; font-weight: 900; font-size: clamp(3.5rem, 8vw, 4.8rem); color: var(--primary); text-align: center; margin:0; text-transform: uppercase; letter-spacing: -2px;}
    .sub-title { font-family: 'Inter', sans-serif; font-size: 1.6rem; color: #64748b; text-align: center; margin-bottom: 2rem; font-weight: 700;}
    .metrics-container { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1.5rem; margin-bottom: 2rem; }
    @media (max-width: 1200px) { .metrics-container { grid-template-columns: repeat(2, 1fr); } }
    @media (max-width: 800px) { .metrics-container { grid-template-columns: 1fr; } }
    .metric-card { background: white; padding: 2.5rem 1.5rem; border-radius: 20px; box-shadow: 0 8px 25px rgba(0,0,0,0.06); text-align: center; position: relative; overflow: hidden; border: 2px solid #e2e8f0; transition: transform 0.2s ease;}
    .metric-card:hover { transform: translateY(-5px); }
    .metric-card::before { content: ''; position: absolute; top: 0; left: 0; right: 0; height: 10px; }
    .m-total::before { background: #0ea5e9; } .m-presente::before { background: var(--success); } .m-falta::before { background: var(--danger); } .m-atraso::before { background: #f59e0b; } .m-acad::before { background: #8b5cf6; } .m-satest::before { background: #10b981; } .m-satpais::before { background: #f59e0b; } .m-sateq::before { background: #3b82f6; }
    .m-val { font-size: 4rem; font-weight: 900; color: #0f172a; display: block; line-height: 1.1; letter-spacing: -2px; text-shadow: 2px 2px 4px rgba(0,0,0,0.05); }
    .m-lab { font-size: 1.2rem; font-weight: 900; color: #475569; text-transform: uppercase; letter-spacing: 1px; margin-top: 1rem; display: block; }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; padding-bottom: 0px; flex-wrap: wrap; }
    .stTabs [data-baseweb="tab"] { background-color: #f1f5f9 !important; border: 3px solid #cbd5e1 !important; border-bottom: none !important; border-radius: 18px 18px 0 0 !important; padding: 15px 25px !important; font-size: 1.5rem !important; font-weight: 900 !important; color: #64748b !important; transition: all 0.3s ease !important; }
    .stTabs [data-baseweb="tab"]:hover { background-color: #e2e8f0 !important; color: var(--primary) !important; }
    .stTabs [aria-selected="true"] { background-color: var(--primary) !important; color: #ffffff !important; border: 5px solid var(--accent) !important; border-bottom: none !important; transform: translateY(-4px); box-shadow: 0 -8px 25px rgba(255, 123, 0, 0.35) !important; }
    div[data-baseweb="input"] { border: 2px solid #cbd5e1 !important; border-radius: 12px !important; background-color: #ffffff !important; }
    div[data-baseweb="input"] input { color: #000000 !important; -webkit-text-fill-color: #000000 !important; font-weight: 900 !important; font-size: 1.5rem !important; padding: 1rem 1.2rem !important; }
    div[data-baseweb="input"]:focus-within { border-color: var(--accent) !important; box-shadow: 0 0 0 4px rgba(255, 123, 0, 0.2) !important; }
    [data-baseweb="select"] > div { background-color: #ffffff !important; border: 2.5px solid #0a1f35 !important; border-radius: 12px !important; height: 55px !important; color: #000000 !important; }
    [data-baseweb="select"] span { color: #000000 !important; -webkit-text-fill-color: #000000 !important; font-weight: 900 !important; font-size: 1.4rem !important;}
    ul[data-baseweb="menu"] { background-color: #ffffff !important; }
    ul[data-baseweb="menu"] li { color: #000000 !important; -webkit-text-fill-color: #000000 !important; }
    .stButton > button { border-radius: 12px !important; font-weight: 800 !important; font-size: 1.3rem !important; padding: 0.8rem 2rem !important; border: none !important; transition: all 0.2s ease !important; }
    [data-testid="stFormSubmitButton"] > button { background: linear-gradient(135deg, var(--primary), #1a4b82) !important; color: white !important; box-shadow: 0 6px 15px rgba(10, 31, 53, 0.3) !important; width: 100% !important; text-transform: uppercase !important; font-size: 1.4rem !important;}
    [data-testid="stFormSubmitButton"] > button:active { transform: scale(0.95); }
    .login-title { font-size: 2.2rem; font-weight: 900; color: var(--primary); margin-bottom: 1.5rem; text-align: center; }
    [data-testid="stDataFrame"] { font-size: 1.2rem !important; }
    .streamlit-expanderHeader { font-size: 1.3rem !important; font-weight: bold !important; }
    .top7-card { background: linear-gradient(135deg, #ffffff, #f8fafc); border-left: 12px solid var(--accent); padding: 3rem 1.5rem; border-radius: 20px; margin-bottom: 1.5rem; box-shadow: 0 10px 30px rgba(0,0,0,0.08); text-align: center;}
    .top7-medal { font-size: 3.8rem !important; font-weight: 900; color: var(--primary); margin-bottom: 0.5rem; letter-spacing: -1px;}
    .top7-name { font-size: 4.5rem !important; font-weight: 900; color: var(--primary); letter-spacing: -2px; margin: 1.5rem 0; line-height: 1.1; text-transform: uppercase;}
    .top7-name-hidden { font-size: 4.5rem !important; font-weight: 900; color: #94a3b8; filter: blur(12px); user-select: none; margin: 1.5rem 0; line-height: 1.1;}
    .top7-details { font-size: 1.8rem !important; color: #64748b; font-weight: 800; background: #e2e8f0; display: inline-block; padding: 0.5rem 1.5rem; border-radius: 30px;}
    div[data-testid="stExpander"]:nth-child(even) { background-color: #f8fafc; border-radius: 12px; border: 1px solid #cbd5e1; margin-bottom: 10px;}
    div[data-testid="stExpander"]:nth-child(odd) { background-color: #e2e8f0; border-radius: 12px; border: 1px solid #94a3b8; margin-bottom: 10px;}
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------
# 6. LÓGICA DE NEGÓCIO E CACHES BLINDADOS COM FALLBACK
# ------------------------------------------------------------

# === Módulo de Resiliência: Verificação de Dia Letivo ===
def _fetch_dia_letivo_db(data_atual):
    conn = conectar_bd()
    if not conn: 
        raise ConnectionError("Sem conexão com o banco de dados")
    try:
        cur = conn.cursor()
        cur.execute("SELECT dia_letivo FROM calendario_letivo WHERE data = %s", (data_atual,))
        res = cur.fetchone()
        if res: 
            return res[0]
        return False
    finally:
        liberar_conn(conn)

@st.cache_data(ttl=300)
def _verificar_dia_letivo_cache(data_atual):
    return _fetch_dia_letivo_db(data_atual)

def verificar_dia_letivo(data_atual):
    if 'cache_dias_letivos' not in st.session_state:
        st.session_state['cache_dias_letivos'] = {}
        
    try:
        # Se a rede cair, esta função vai estourar um erro, impedindo o envenenamento do cache.
        resultado = _verificar_dia_letivo_cache(data_atual)
        st.session_state['cache_dias_letivos'][data_atual] = resultado
        return resultado
    except Exception:
        # Puxa o cofre de segurança como plano B.
        return st.session_state['cache_dias_letivos'].get(data_atual, False)

# === Módulo de Resiliência: Carregamento de Alunos ===
def _fetch_alunos_db():
    conn = conectar_bd()
    if not conn: 
        raise ConnectionError("Sem conexão com o banco de dados")
    try:
        return pd.read_sql("SELECT codigo, nome, turma, status, email_responsavel FROM alunos_v2 ORDER BY turma, nome", conn)
    finally:
        liberar_conn(conn)

@st.cache_data(ttl=3600)
def _carregar_alunos_cache():
    return _fetch_alunos_db()

def carregar_alunos():
    try:
        # Se a rede cair, esta função vai estourar um erro, impedindo o envenenamento do cache.
        df = _carregar_alunos_cache()
        st.session_state['ultimo_df_alunos_ok'] = df
        return df
    except Exception:
        # Puxa o cofre de segurança como plano B.
        if 'ultimo_df_alunos_ok' in st.session_state:
            return st.session_state['ultimo_df_alunos_ok']
        return pd.DataFrame(columns=['codigo','nome','turma','status','email_responsavel'])

@st.cache_data(ttl=60)
def contar_presencas_data(data_str, turma="Todas"):
    try:
        conn = conectar_bd()
        if not conn: 
            return 0
            
        cur = conn.cursor()
        if turma == "Todas":
            cur.execute("SELECT COUNT(*) FROM registros_v2 WHERE data=%s AND tipo_registro='PRESENCA'", (data_str,))
        else:
            cur.execute("SELECT COUNT(r.id) FROM registros_v2 r JOIN alunos_v2 a ON r.codigo_aluno = a.codigo WHERE r.data=%s AND r.tipo_registro='PRESENCA' AND a.turma=%s", (data_str, turma))
            
        count = cur.fetchone()[0]
        liberar_conn(conn)
        return count
    except: 
        return 0

@st.cache_data(ttl=60)
def carregar_faltas(data_str):
    try:
        conn = conectar_bd()
        if not conn: 
            return pd.DataFrame()
            
        query = """
            SELECT a.codigo as codigo_aluno, a.nome, a.turma, r.motivo_saida 
            FROM alunos_v2 a 
            LEFT JOIN registros_v2 r ON a.codigo = r.codigo_aluno AND r.data = %s AND r.tipo_registro = 'FALTA'
            WHERE a.status = 'ATIVO' 
            AND a.codigo NOT IN (
                SELECT codigo_aluno FROM registros_v2 WHERE data = %s AND tipo_registro = 'PRESENCA'
            )
            ORDER BY a.turma, a.nome
        """
        df = pd.read_sql(query, conn, params=[data_str, data_str])
        liberar_conn(conn)
        return df
    except Exception as e: 
        print(f"Erro ao carregar faltas: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=60)
def carregar_faltas_primeira_chamada(ano):
    query = """
        SELECT a.nome, a.turma, f.periodo, f.area, f.motivo, TO_CHAR(f.data_registro, 'DD/MM/YYYY') as data_registro 
        FROM faltas_primeira_chamada f JOIN alunos_v2 a ON f.codigo_aluno = a.codigo WHERE f.ano = %s ORDER BY f.periodo, f.area, a.turma, a.nome
    """
    conn = conectar_bd()
    if not conn: 
        return pd.DataFrame()
        
    try:
        df = pd.read_sql(query, conn, params=[str(ano)])
        return df
    except Exception: 
        return pd.DataFrame()
    finally: 
        liberar_conn(conn)

@st.cache_data(ttl=300)
def obter_dados_acad_filtrados(ano, p, a, t):
    conditions = ["avs.ano = %s"]
    params = [str(ano)]
    
    if p != "Todos": 
        conditions.append("avs.periodo = %s")
        params.append(p)
        
    if a != "Todas": 
        conditions.append("avs.area = %s")
        params.append(a)
        
    if t != "Todas": 
        conditions.append("COALESCE(al.turma, avs.turma) = %s")
        params.append(t)
        
    where_clause = " AND ".join(conditions)
    query = f"SELECT avs.id, avs.ano, avs.periodo, avs.area, COALESCE(al.turma, avs.turma) as turma, avs.nome, avs.disciplina, avs.questao, avs.resposta, avs.gabarito, avs.acerto FROM avaliacoes_avs avs LEFT JOIN alunos_v2 al ON avs.nome = al.nome WHERE {where_clause}"
    
    conn = conectar_bd()
    if not conn: 
        return pd.DataFrame()
        
    try: 
        df = pd.read_sql(query, conn, params=params)
    except Exception: 
        df = pd.DataFrame()
    finally: 
        liberar_conn(conn)
        
    if not df.empty and 'disciplina' in df.columns:
        df['disciplina'] = df['disciplina'].replace({'LÍNGUA PORTUGESA': 'LÍNGUA PORTUGUESA', 'SOCIOLGIA': 'SOCIOLOGIA'})
        
    return df

@st.cache_data(ttl=300)
def obter_estatisticas_areas_cached(ano, p, a, t):
    df_filtrado = obter_dados_acad_filtrados(ano, p, a, t)
    alertas_estudante = {}
    area_stats = pd.DataFrame()
    
    if not df_filtrado.empty:
        area_stats = df_filtrado.groupby(['nome', 'turma', 'periodo', 'area']).agg(Total=('questao', 'count'), Brancos=('resposta', lambda x: (x == 'BRANCO').sum()), Duplas=('resposta', lambda x: (x == 'DUPLA').sum())).reset_index()
        area_stats['Faltou'] = area_stats['Total'] == area_stats['Brancos']
        
        for nome, group in area_stats.groupby('nome'):
            alertas = []
            faltas = group[group['Faltou']]
            
            if not faltas.empty:
                for _, r_f in faltas.iterrows(): 
                    alertas.append(f"FALTOU {r_f['area']} ({r_f['periodo']})")
                    
            if group['Duplas'].sum() > 0: 
                alertas.append("MARCAÇÃO DUPLA")
                
            presentes = group[~group['Faltou']]
            if presentes['Brancos'].sum() > 0: 
                alertas.append("EM BRANCO")
                
            if alertas: 
                alertas_estudante[nome] = " | ".join(alertas)
                
    return alertas_estudante, area_stats

@st.cache_data(ttl=300)
def obter_top7_cached(ano, p, a, t):
    dff = obter_dados_acad_filtrados(ano, p, a, t)
    if dff.empty: 
        return pd.DataFrame()
    return dff.groupby(['nome','turma']).acerto.mean().reset_index().sort_values('acerto', ascending=False).head(7)

@st.cache_data(ttl=300)
def obter_resumo_estudantes_cached(ano, p, a, t):
    dff = obter_dados_acad_filtrados(ano, p, a, t)
    if dff.empty: 
        return pd.DataFrame(), []
        
    res_al = dff.groupby(['nome','turma']).acerto.mean().reset_index()
    erros_n = dff[dff['resposta'].isin(['BRANCO','DUPLA'])]['nome'].unique()
    return res_al, erros_n

@st.cache_data(ttl=300)
def obter_top3_erros_cached(ano, p, a, t):
    dff = obter_dados_acad_filtrados(ano, p, a, t)
    if dff.empty: 
        return pd.DataFrame()
        
    q_err = dff.groupby(['turma', 'periodo', 'disciplina', 'questao']).agg(Total=('questao', 'count'), Acertos=('acerto', 'sum')).reset_index()
    q_err['Taxa de Erro (%)'] = ((q_err['Total'] - q_err['Acertos']) / q_err['Total']) * 100
    q_err_top3 = q_err[q_err['Taxa de Erro (%)'] > 0].sort_values(['turma', 'periodo', 'disciplina', 'Taxa de Erro (%)'], ascending=[True, True, True, False]).groupby(['turma', 'periodo', 'disciplina']).head(3)
    return q_err_top3

@st.cache_data(ttl=300)
def carregar_satisfacao_por_ano(ano):
    query = "SELECT * FROM satisfacao_v1 WHERE EXTRACT(YEAR FROM data_hora) = %s"
    conn = conectar_bd()
    if not conn: 
        return pd.DataFrame()
        
    try:
        df = pd.read_sql(query, conn, params=[int(ano)])
        if not df.empty: 
            df['media_resposta'] = df[['q1','q2','q3','q4','q5']].mean(axis=1)
        return df
    except Exception: 
        return pd.DataFrame()
    finally: 
        liberar_conn(conn)

@st.cache_data(ttl=300)
def calcular_satisfacao_global_cached(ano, tf):
    df_sat = carregar_satisfacao_por_ano(ano)
    sat_est_str = "--"
    sat_pais_str = "--"
    sat_eq_str = "--"
    
    if not df_sat.empty:
        df_sat_est = df_sat[df_sat['categoria'] == 'Estudante']
        if tf != "Todas": 
            df_sat_est = df_sat_est[df_sat_est['turma'] == tf]
            
        if not df_sat_est.empty: 
            sat_est_str = f"{df_sat_est['media_resposta'].mean():.1f} / 5"
        
        df_sat_pais = df_sat[df_sat['categoria'] == 'Pais/Responsável']
        if not df_sat_pais.empty: 
            sat_pais_str = f"{df_sat_pais['media_resposta'].mean():.1f} / 5"
        
        df_sat_eq = df_sat[df_sat['categoria'].isin(['Professor', 'Servidor'])]
        if not df_sat_eq.empty: 
            sat_eq_str = f"{df_sat_eq['media_resposta'].mean():.1f} / 5"
            
    return sat_est_str, sat_pais_str, sat_eq_str

def importar_csv_alunos(file):
    conteudo_bytes = file.read()
    try: 
        conteudo_str = conteudo_bytes.decode('utf-8-sig')
    except: 
        conteudo_str = conteudo_bytes.decode('latin-1')
        
    df = pd.read_csv(io.StringIO(conteudo_str), sep=';')
    
    def norm(c): 
        return ''.join(x for x in unicodedata.normalize('NFD', str(c)) if unicodedata.category(x) != 'Mn').strip().upper()
        
    df.columns = [norm(col) for col in df.columns]
    dados = [(str(r['CODIGO']).upper(), str(r['NOME']).upper(), str(r['TURMA']).upper(), 'ATIVO') for _, r in df.iterrows()]
    
    conn = conectar_bd()
    if not conn: 
        return False
        
    try:
        cur = conn.cursor()
        execute_values(cur, "INSERT INTO alunos_v2 (codigo, nome, turma, status) VALUES %s ON CONFLICT (codigo) DO UPDATE SET nome=EXCLUDED.nome, turma=EXCLUDED.turma", dados)
        conn.commit()
        _carregar_alunos_cache.clear()
        return True
    finally: 
        liberar_conn(conn)

def ir_para_fila_offline(cod, data, h_at, status):
    registro_pendente = {"codigo": cod, "data": data, "hora": h_at, "status": status}
    st.session_state.fila_offline.append(registro_pendente)
    return f"FILA OFFLINE ({cod})"

def registrar_saida(cod, motivo, pais, data, h_saida, h_limite_saida):
    conn = conectar_bd()
    if not conn: 
        return False
        
    try:
        cur = conn.cursor()
        cur.execute("SELECT nome, email_responsavel FROM alunos_v2 WHERE codigo = %s", (cod,))
        res = cur.fetchone()
        
        if not res: 
            return False
            
        cur.execute("UPDATE registros_v2 SET hora_saida=%s, motivo_saida=%s, pais_informados=%s WHERE codigo_aluno=%s AND data=%s AND tipo_registro='PRESENCA'", (h_saida, motivo, pais, cod, data))
        
        if cur.rowcount > 0:
            if res[1]: 
                h_s_obj = datetime.strptime(h_saida, "%H:%M:%S").time()
                
                if h_s_obj < h_limite_saida:
                    evento_email = "SAÍDA ANTECIPADA"
                else:
                    evento_email = "SAÍDA REGULAR"
                    
                disparar_email_background(res[1], res[0], evento_email, h_saida, data)
                
            conn.commit()
            contar_presencas_data.clear()
            carregar_faltas.clear()
            return res[0]
            
        return False
    except Exception: 
        return False
    finally: 
        liberar_conn(conn)

def importar_csv_desempenho(file, ano, periodo, area, turma):
    conteudo_bytes = file.read()
    try: 
        conteudo_str = conteudo_bytes.decode('utf-8-sig')
    except: 
        conteudo_str = conteudo_bytes.decode('latin-1')
        
    temp_df = pd.read_csv(io.StringIO(conteudo_str), sep=';')
    temp_df.columns = [str(c).strip() for c in temp_df.columns]
    col_qs = [c for c in temp_df.columns if re.search(r'^Q\s*\d+\s*Options', c, re.IGNORECASE)]
    
    idx_not = next((i for i, c in enumerate(temp_df.columns) if 'Not attempted' in c), -1)
    idx_f = temp_df.columns.get_loc(col_qs[0])
    
    if idx_not != -1:
        discs = [str(c).strip().upper() for c in temp_df.columns[idx_not+1:idx_f] if 'AV' not in str(c).upper()]
    else:
        discs = [area.upper()]
        
    q_p_d = len(col_qs) // len(discs)
    dados_l = []
    nomes = temp_df.get('Nome', pd.Series(dtype=str)).astype(str).str.strip().tolist()
    col_keys = [cq.replace('Options', 'Key') for cq in col_qs]
    
    for ck in col_keys:
        if ck not in temp_df.columns: 
            temp_df[ck] = ''
            
    options_matrix = temp_df[col_qs].fillna('').astype(str).values
    keys_matrix = temp_df[col_keys].fillna('').astype(str).values

    for r_idx, n in enumerate(nomes):
        if not n or n.lower() == 'nan': 
            continue
            
        for i in range(len(col_qs)):
            d_i = min(i // q_p_d, len(discs)-1)
            rb = options_matrix[r_idx, i].strip()
            g = keys_matrix[r_idx, i].strip().upper()
            
            if not rb:
                r = 'BRANCO'
            elif len(rb) == 1:
                r = rb.upper()
            else:
                r = 'DUPLA'
                
            if r == g and r != 'BRANCO':
                acerto = 1
            else:
                acerto = 0
                
            dados_l.append((str(ano), periodo, area, turma, n, discs[d_i], i+1, r, g, acerto))
            
    conn = conectar_bd()
    if not conn: 
        return False, "Erro de conexão ao banco de dados."
        
    try:
        cur = conn.cursor()
        execute_values(cur, "INSERT INTO avaliacoes_avs (ano, periodo, area, turma, nome, disciplina, questao, resposta, gabarito, acerto) VALUES %s ON CONFLICT (ano, periodo, area, turma, nome, disciplina, questao) DO UPDATE SET resposta=EXCLUDED.resposta, acerto=EXCLUDED.acerto", dados_l)
        conn.commit()
        obter_dados_acad_filtrados.clear()
        return True, f"{len(dados_l)} registros salvos."
    except Exception as e: 
        return False, str(e)
    finally: 
        liberar_conn(conn)

def gerar_pdf_boletim(aluno, turma, nota_g, df_b, df_historico_aluno=None):
    if not FPDF: 
        return None
        
    pdf = FPDF()
    pdf.add_page()
    pdf.set_fill_color(10, 31, 53)
    pdf.rect(0, 0, 210, 35, 'F')
    
    pdf.set_font("Arial", "B", 18)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 15, "BOLETIM DE DESEMPENHO", 0, 1, "C")
    
    pdf.ln(20)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", "B", 14)
    
    pdf.cell(0, 10, f"ESTUDANTE: {aluno} ({turma})", 0, 1)
    pdf.cell(0, 10, f"MÉDIA (Filtro): {nota_g:.2f}", 0, 1)
    
    pdf.set_font("Arial", "B", 8)
    pdf.cell(0, 6, "LEGENDA: VERDE = ACERTO | VERMELHO = ERRO | LARANJA = BRANCO | ROXO = DUPLA", 0, 1)
    pdf.ln(2)
    
    for p in sorted(df_b['periodo'].unique()):
        pdf.set_fill_color(230, 230, 230)
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 10, f"  {p}", 0, 1, fill=True)
        
        for d in sorted(df_b[df_b['periodo']==p]['disciplina'].unique()):
            df_d = df_b[(df_b['periodo']==p) & (df_b['disciplina']==d)]
            
            pdf.set_font("Arial", "B", 11)
            pdf.cell(0, 8, f"{d} - Nota: {(df_d['acerto'].mean()*10):.2f}", 0, 1)
            
            x = 10
            y = pdf.get_y()
            col = 0
            
            for q in df_d.sort_values('questao').to_dict('records'):
                if y > 265: 
                    pdf.add_page()
                    y = 20
                    
                if q['acerto'] == 1:
                    c = (16, 185, 129)
                elif q['resposta'] == 'BRANCO':
                    c = (245, 158, 11)
                elif q['resposta'] == 'DUPLA':
                    c = (139, 92, 246)
                else:
                    c = (239, 68, 68)
                    
                pdf.set_fill_color(*c)
                pdf.rect(x + (col * 22), y, 20, 12, 'F')
                pdf.set_text_color(255, 255, 255)
                pdf.set_font("Arial", "B", 8)
                
                pdf.text(x + (col * 22) + 2, y + 5, f"Q{q['questao']}")
                pdf.text(x + (col * 22) + 2, y + 10, f"R:{q['resposta']}")
                
                col += 1
                if col > 7: 
                    col = 0
                    y += 15
                    
            if col > 0:
                y = y + 15 
            else:
                y = y
                
            pdf.set_y(y + 5)
            pdf.set_text_color(0, 0, 0)
            
    if df_historico_aluno is not None and not df_historico_aluno.empty and MATPLOTLIB_AVAILABLE:
        progresso = df_historico_aluno.groupby(['periodo', 'disciplina']).agg(Acertos=('acerto', 'sum'), Total=('questao', 'count')).reset_index()
        progresso['Nota'] = (progresso['Acertos'] / progresso['Total']) * 10
        progresso_pivot = progresso.pivot(index='periodo', columns='disciplina', values='Nota')
        
        fig, ax = plt.subplots(figsize=(10, 6))
        for col_name in progresso_pivot.columns:
            abreviacao = DICIONARIO_ABREVIACAO.get(col_name, col_name[:4].upper())
            cor = DICIONARIO_CORES.get(abreviacao, DICIONARIO_CORES.get(col_name, "#000000"))
            ax.plot(progresso_pivot.index, progresso_pivot[col_name], marker='o', linewidth=5, markersize=12, label=col_name, color=cor)
            for x_val, y_val in zip(progresso_pivot.index, progresso_pivot[col_name]):
                if pd.notna(y_val): 
                    ax.text(x_val, y_val + 0.3, abreviacao, color=cor, fontsize=10, fontweight='bold', ha='center', va='bottom')
                    
        ax.set_title("Evolucao Geral ao Longo do Ano", fontweight='bold', fontsize=18)
        ax.set_ylabel("Nota", fontweight='bold', fontsize=14)
        ax.set_xlabel("Periodo", fontweight='bold', fontsize=14)
        ax.set_ylim(0, 11) 
        ax.grid(True, linestyle='--', alpha=0.7)
        ax.legend(loc='center left', bbox_to_anchor=(1, 0.5), fontsize=12)
        plt.tight_layout()
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp: 
            plt.savefig(tmp.name, format='png', dpi=300, bbox_inches='tight')
            tmp_img_name = tmp.name
            
        plt.close(fig)
        
        pdf.add_page()
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, "EVOLUCAO AO LONGO DO ANO (HISTORICO COMPLETO)", 0, 1, "C")
        pdf.ln(5)
        pdf.image(tmp_img_name, x=10, w=190)
        
        try: 
            os.remove(tmp_img_name)
        except: 
            pass
            
    out = pdf.output(dest='S')
    
    if isinstance(out, str):
        return out.encode('latin-1')
    return bytes(out)

def gerar_pdf_relatorio_critico(df_critico):
    if not FPDF: 
        return None
        
    pdf = FPDF()
    pdf.add_page()
    pdf.set_fill_color(10, 31, 53)
    pdf.rect(0, 0, 210, 35, 'F')
    
    pdf.set_font("Arial", "B", 16)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 15, "QUESTOES CRITICAS (TOP 3 ERROS)", 0, 1, "C")
    
    pdf.ln(20)
    pdf.set_text_color(0, 0, 0)
    
    for t in sorted(df_critico['turma'].unique()):
        pdf.set_fill_color(230, 230, 230)
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, f" Turma: {t}", 0, 1, fill=True)
        
        df_t = df_critico[df_critico['turma'] == t]
        for p in sorted(df_t['periodo'].unique()):
            pdf.set_font("Arial", "B", 12)
            pdf.cell(0, 8, f"   Periodo: {p}", 0, 1)
            
            df_p = df_t[df_t['periodo'] == p]
            for d in sorted(df_p['disciplina'].unique()):
                pdf.set_font("Arial", "B", 11)
                pdf.cell(0, 6, f"      Disciplinas: {d}", 0, 1)
                
                df_d = df_p[df_p['disciplina'] == d]
                pdf.set_font("Arial", "", 10)
                
                for _, r in df_d.iterrows():
                    if pdf.get_y() > 270: 
                        pdf.add_page()
                        
                    pdf.cell(15)
                    pdf.cell(0, 5, f"- Questao {r['questao']}: {r['Taxa de Erro (%)']:.1f}% de erro", 0, 1)
                pdf.ln(2)
        pdf.ln(5)
        
    out = pdf.output(dest='S')
    
    if isinstance(out, str):
        return out.encode('latin-1')
    return bytes(out)

# ====================== FUNÇÃO DE CÂMERA OTIMIZADA ======================
def gerar_camera(label, btn_label, cam_id):
    components.html(f"""
    <div style="text-align:center; max-width:450px; margin: 0 auto; padding:15px; border-radius:15px; background:white; border: 2px solid #e2e8f0; box-shadow: 0 4px 10px rgba(0,0,0,0.05);">
        <div style="display:flex; gap:10px; margin-bottom:15px;">
            <button id="start-{cam_id}" style="flex:1; padding:12px; background:#10b981; color:white; border:none; border-radius:8px; font-weight:900; font-size:1rem; cursor:pointer;">🟢 LIGAR CÂMARA (Contínuo)</button>
            <button id="stop-{cam_id}" style="flex:1; padding:12px; background:#ef4444; color:white; border:none; border-radius:8px; font-weight:900; font-size:1rem; cursor:pointer;">🔴 DESLIGAR</button>
        </div>
        <div id="reader-{cam_id}" style="width:100%; display:none; border-radius:10px; overflow:hidden; border: 3px solid #0a1f35; background: #000;"></div>
    </div>
    <script src="https://unpkg.com/html5-qrcode"></script>
    <script>
        let scanner_{cam_id};
        document.getElementById("start-{cam_id}").onclick = () => {{
            const container = document.getElementById("reader-{cam_id}");
            container.style.display = "block";
            if(!scanner_{cam_id}) {{
                scanner_{cam_id} = new Html5Qrcode("reader-{cam_id}");
            }}
            const configuracao = {{ fps: 20, qrbox: {{ width: 260, height: 260 }} }};
            const aoLerCodigo = (txt) => {{
                const input = window.parent.document.querySelectorAll('input[aria-label*="{label}"]')[0];
                if(input) {{ 
                    let nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
                    nativeInputValueSetter.call(input, txt);
                    input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    setTimeout(() => {{ 
                        window.parent.document.querySelectorAll('button').forEach(b => {{ 
                            if(b.innerText.includes("{btn_label}")) {{
                                b.click();
                            }}
                        }}); 
                    }}, 100);
                }}
            }};
            scanner_{cam_id}.start({{ facingMode: "environment" }}, configuracao, aoLerCodigo)
            .catch(erroTraseira => {{
                scanner_{cam_id}.start({{ facingMode: "user" }}, configuracao, aoLerCodigo)
                .catch(erroFrontal => {{
                    alert("⚠️ Erro ao acessar a câmera: Verifique permissões.");
                    container.style.display = "none";
                }});
            }});
        }};
        document.getElementById("stop-{cam_id}").onclick = () => {{
            if(scanner_{cam_id}) {{ 
                scanner_{cam_id}.stop().then(() => {{ 
                    document.getElementById("reader-{cam_id}").style.display = "none"; 
                }}) 
            }}
        }};
    </script>
    """, height=450)
# ========================================================================

# ------------------------------------------------------------
# 7. MÓDULO PÚBLICO: PESQUISA DE SATISFAÇÃO (OCULTO VIA URL)
# ------------------------------------------------------------
if st.query_params.get("modo") == "pesquisa":
    renderizar_logo_central()
    
    if st.session_state.pesquisa_enviada:
        st.markdown("<div style='text-align: center; padding: 40px 10px;'><h1 style='font-size: 5rem; margin-bottom: 0;'>🎉</h1><h2 style='color: #10b981; font-weight: 900;'>Avaliação Recebida!</h2><p style='font-size: 1.4rem; color: #64748b; margin-top: 15px;'>Muito obrigado por contribuir com a melhoria da nossa escola.<br>Sua opinião faz toda a diferença!</p></div>", unsafe_allow_html=True)
        if st.button("Enviar nova avaliação", use_container_width=True):
            st.session_state.pesquisa_enviada = False
            st.rerun()
        st.stop()
        
    st.markdown("<h2 style='color: var(--primary); text-align: center; margin-bottom: 5px;'>Pesquisa de Satisfação Escolar</h2><p style='text-align: center; color: #64748b; font-weight: bold; margin-bottom: 25px;'>Sua opinião é 100% anônima e essencial para melhorarmos nossa escola.</p>", unsafe_allow_html=True)
    cat = st.selectbox("1. Identifique seu perfil para iniciarmos:", ["", "Estudante", "Pais/Responsável", "Professor", "Servidor"])

    if cat:
        with st.form("form_sat", clear_on_submit=True):
            turma_sel = ""
            if cat == "Estudante":
                df_al = carregar_alunos()
                if not df_al.empty:
                    lista_t = sorted(df_al['turma'].unique()) 
                else:
                    lista_t = []
                turma_sel = st.selectbox("Qual é a sua Turma?", [""] + lista_t)
                st.markdown("---")

            opcoes = ["1 - 😡 Muito Insatisfeito", "2 - 😟 Insatisfeito", "3 - 😐 Neutro", "4 - 😊 Satisfeito", "5 - 🤩 Muito Satisfeito"]
            st.markdown("#### 🔹 Avaliação Geral")
            q1 = st.radio("Como você avalia a conservação e limpeza da escola?", opcoes, index=None)
            q2 = st.radio("Como você avalia o acolhimento e a atenção recebida pelos funcionários?", opcoes, index=None)
            q3 = st.radio("Qual a sua satisfação geral com a nossa escola?", opcoes, index=None)
            
            st.markdown(f"#### 🔹 Avaliação Específica ({cat})")
            if cat == "Estudante":
                q4 = st.radio("Como você avalia a qualidade das aulas e o engajamento dos professores?", opcoes, index=None)
                q5 = st.radio("Como você avalia a organização dos eventos e atividades da escola?", opcoes, index=None)
            elif cat == "Pais/Responsável":
                q4 = st.radio("Como você avalia a facilidade para solicitar certificados e declarações?", opcoes, index=None)
                q5 = st.radio("Como você avalia a comunicação da escola sobre notas e faltas do estudante?", opcoes, index=None)
            elif cat == "Professor":
                q4 = st.radio("Como você avalia os recursos pedagógicos e o suporte da gestão escolar?", opcoes, index=None)
                q5 = st.radio("Como você avalia o engajamento e a disciplina geral dos estudantes?", opcoes, index=None)
            else: 
                q4 = st.radio("Como você avalia as condições de trabalho e recursos disponíveis no seu setor?", opcoes, index=None)
                q5 = st.radio("Como você avalia o clima organizacional e a colaboração da equipe?", opcoes, index=None)

            sugestao = st.text_area("Deixe aqui uma sugestão, crítica ou elogio (Opcional)")

            if st.form_submit_button("🚀 ENVIAR MINHA AVALIAÇÃO AGORA"):
                if not all([q1, q2, q3, q4, q5]): 
                    st.error("⚠️ Atenção: Por favor, selecione uma nota para todas as 5 perguntas antes de enviar.")
                elif cat == "Estudante" and not turma_sel: 
                    st.error("⚠️ Atenção: Por favor, selecione a sua turma no topo do formulário.")
                else:
                    conn = conectar_bd()
                    if conn:
                        try:
                            cur = conn.cursor()
                            cur.execute("INSERT INTO satisfacao_v1 (data_hora, categoria, turma, q1, q2, q3, q4, q5, sugestao) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)", (obter_hora_atual(), cat, turma_sel, int(q1[0]), int(q2[0]), int(q3[0]), int(q4[0]), int(q5[0]), sugestao))
                            conn.commit()
                            st.session_state.pesquisa_enviada = True
                            st.rerun()
                        except: 
                            st.error("Erro de conexão ao salvar avaliação. Tente novamente.")
                        finally: 
                            liberar_conn(conn)
                    else: 
                        st.error("Não foi possível conectar ao banco de dados no momento.")
    st.stop() 

# ------------------------------------------------------------
# 8. AUTH E DASHBOARD DO DIRETOR
# ------------------------------------------------------------
auth_cookie = cookies.get("auth_token")
if not auth_cookie:
    if os.path.exists("logo.png"): 
        st.image("logo.png", width=120)
    st.markdown('<div class="login-title">LOGIN ESCOLAR</div>', unsafe_allow_html=True)
    passw = st.text_input("SENHA", type="password")
    
    if st.button("ENTRAR", use_container_width=True):
        if passw in [SENHA_ADMIN, SENHA_OPERADOR]:
            cookies["auth_token"] = base64.b64encode(json.dumps({"admin": passw==SENHA_ADMIN}).encode()).decode()
            cookies.save()
            st.rerun()
        else: 
            st.error("Incorreta")
    st.stop()

try:
    user = json.loads(base64.b64decode(auth_cookie).decode())
    eh_admin = user.get('admin', user.get('eh_admin', False)) 
except Exception: 
    cookies["auth_token"] = ""
    cookies.save()
    st.rerun()

df_alunos = carregar_alunos()

c_out1, c_out2 = st.columns([10, 1])
with c_out2:
    if st.button("SAIR"): 
        cookies["auth_token"] = ""
        cookies.save()
        st.rerun()

renderizar_logo_central()
st.markdown('<p class="main-title">PAINEL INTEGRADO</p>', unsafe_allow_html=True)
st.markdown(f'<p class="sub-title">Gestão Escolar • {data_formatada_ptbr()}</p>', unsafe_allow_html=True)

# --- FILTROS GLOBAIS ---
st.markdown("### 🎛️ Filtros Globais do Painel")
c_data, c_ano, cf1, cf2, cf3 = st.columns([1.5, 1, 1.5, 1.5, 2])

anos_disponiveis = [str(y) for y in range(2024, 2035)]
ano_atual = str(obter_hora_atual().year)

if ano_atual not in anos_disponiveis: 
    anos_disponiveis.append(ano_atual)

data_f_global = c_data.date_input("Data (Frequência)", obter_hora_atual().date(), key="filtro_data_global")
ano_f = c_ano.selectbox("Ano Letivo", anos_disponiveis, index=anos_disponiveis.index(ano_atual), key="filtro_ano_da")
pf = cf1.selectbox("Período Acadêmico", ["Todos", "1º Período", "2º Período", "3º Período", "4º Período"], key="filtro_periodo_da")
af = cf2.selectbox("Área Acadêmica", ["Todas", "LÍNGUA PORTUGUESA", "MATEMÁTICA", "LINGUAGENS", "HUMANAS", "NATUREZA"], key="filtro_area_da")

lista_turmas_filtro = []
if not df_alunos.empty:
    lista_turmas_filtro = sorted(df_alunos['turma'].unique())
tf = cf3.selectbox("Turma (Filtra TUDO)", ["Todas"] + lista_turmas_filtro, key="filtro_turma_da")


hoje_real = obter_hora_atual().strftime("%Y-%m-%d")
data_selecionada_str = data_f_global.strftime("%Y-%m-%d")

if tf == "Todas":
    df_alunos_filtrado = df_alunos 
else:
    df_alunos_filtrado = df_alunos[df_alunos['turma'] == tf]
    
total_alunos = len(df_alunos_filtrado)
pres_data = contar_presencas_data(data_selecionada_str, tf)

if total_alunos > 0:
    media_geral_freq = f"{(pres_data / total_alunos) * 100:.1f}%" 
else:
    media_geral_freq = "0%"

with st.spinner("Sincronizando dados..."):
    dff = obter_dados_acad_filtrados(ano_f, pf, af, tf)

if not dff.empty:
    media_geral_acad = f"{dff['acerto'].mean() * 10:.1f}" 
else:
    media_geral_acad = "--"
    
sat_est_str, sat_pais_str, sat_eq_str = calcular_satisfacao_global_cached(ano_f, tf)

st.markdown(f'''
<div class="metrics-container">
    <div class="metric-card m-total"><span class="m-val">{total_alunos}</span><span class="m-lab">Total Alunos</span></div>
    <div class="metric-card m-presente"><span class="m-val">{pres_data}</span><span class="m-lab">Presentes (Dia)</span></div>
    <div class="metric-card m-falta"><span class="m-val">{total_alunos-pres_data}</span><span class="m-lab">Faltas (Dia)</span></div>
    <div class="metric-card m-atraso"><span class="m-val">{media_geral_freq}</span><span class="m-lab">Frequência (Dia)</span></div>
</div>
<div class="metrics-container" style="margin-top: 15px;">
    <div class="metric-card m-acad"><span class="m-val">{media_geral_acad}</span><span class="m-lab">Média Acad. (Filtrada)</span></div>
    <div class="metric-card m-satest"><span class="m-val">{sat_est_str}</span><span class="m-lab">Satisfação Estudante</span></div>
    <div class="metric-card m-satpais"><span class="m-val">{sat_pais_str}</span><span class="m-lab">Satisfação Pais</span></div>
    <div class="metric-card m-sateq"><span class="m-val">{sat_eq_str}</span><span class="m-lab">Satisfação Equipe</span></div>
</div>
''', unsafe_allow_html=True)


abas_do_sistema = ["📝 Registro", "📊 Gestão Frequência", "🚨 Alertas", "📈 Histórico", "📑 Desempenho Acadêmico", "💬 Satisfação Pública"]
if eh_admin: 
    abas_do_sistema.append("⚙️ Manutenção do Sistema")
    
tabs = st.tabs(abas_do_sistema)
indice_aba = 0

# =====================================================================
# NOVO: MODAL POP-UP DE ENTRADA RÁPIDA (100% OFFLINE)
# =====================================================================
@st.dialog("🚀 MODO DE ENTRADA RÁPIDA (100% OFFLINE)", width="large")
def popup_entrada_rapida(data_hoje, hora_limite):
    st.markdown("<p style='text-align:center; color:#64748b;'>Bipe os cartões ou digite manualmente. O sistema guardará tudo na memória instantaneamente sem tocar na rede.</p>", unsafe_allow_html=True)
    
    gerar_camera("Entrada", "REGISTRAR", "cam_popup")
    
    with st.form("f_popup", clear_on_submit=True):
        cod_en = st.text_input("Código do Estudante", placeholder="Bipe o cartão ou digite manualmente...")
        
        if st.form_submit_button("REGISTRAR", use_container_width=True) and cod_en:
            cod_limpo = cod_en.strip().upper()
            agora = obter_hora_atual()
            h_at = agora.strftime("%H:%M:%S")
            
            # Decide presente ou atraso baseado na hora exata do bipe local
            status = "PRESENTE" if agora.time() <= hora_limite else "ATRASO"
            
            st.session_state.fila_offline.append({
                "codigo": cod_limpo, 
                "data": str(data_hoje), 
                "hora": h_at, 
                "status": status
            })
            st.success(f"✅ Registrado na fila: {cod_limpo} às {h_at}")
    
    st.info(f"📦 Estudantes aguardando sincronização: **{len(st.session_state.fila_offline)}**")
# =====================================================================

with tabs[indice_aba]:
    st.markdown("#### ⚙️ Configuração do Turno e Dia Letivo")
    c_cfg1, c_cfg2 = st.columns(2)
    with c_cfg1: 
        h_lim_e = st.time_input("🟢 Horário Limite de Entrada", datetime.strptime("07:30", "%H:%M").time())
    with c_cfg2: 
        h_lim_s = st.time_input("🔴 Horário de Término (Saída)", datetime.strptime("17:00", "%H:%M").time())
    
    with st.form("form_controle_dias"):
        st.markdown("📅 **Ativação do Calendário:**")
        col_d1, col_d2 = st.columns(2)
        with col_d1: 
            data_selecionada = st.date_input("Selecione a Data no Calendário", value=obter_hora_atual().date())
        with col_d2: 
            st.write("")
            st.write("")
            is_ativo = st.checkbox("Ativar como Dia Letivo?", value=True)
            
        if st.form_submit_button("💾 Salvar Configuração do Dia"):
            conn = conectar_bd()
            if conn:
                try:
                    cur = conn.cursor()
                    cur.execute("INSERT INTO calendario_letivo (data, dia_letivo) VALUES (%s, %s) ON CONFLICT (data) DO UPDATE SET dia_letivo = EXCLUDED.dia_letivo", (data_selecionada, is_ativo))
                    conn.commit()
                    _verificar_dia_letivo_cache.clear()
                    st.success(f"Pronto! A data {data_selecionada.strftime('%d/%m/%Y')} foi configurada.")
                except Exception as e: 
                    st.error(f"Erro ao salvar: {e}")
                finally: 
                    liberar_conn(conn)
            else: 
                st.error("Sem conexão com o banco de dados.")

    st.markdown("---")
    
    t_en, t_sa, t_jf = st.tabs(["✅ ENTRADA", "🚪 REGISTRO DE SAÍDA", "📝 JUSTIFICAR FALTAS"])
    
    with t_en:
        if not verificar_dia_letivo(hoje_real): 
            st.error("⚠️ REGISTRO BLOQUEADO: A data de HOJE não foi ativada como Dia Letivo no painel logo acima.")
        else:
            st.markdown("### 🏃‍♂️ Controle de Entrada")
            st.write("Use o Modo Rápido durante o horário de pico. Ele funciona instantaneamente sem internet e você sincroniza tudo com o banco de dados no final.")
            
            if st.button("🟢 ABRIR JANELA DE ENTRADA RÁPIDA", type="primary", use_container_width=True):
                popup_entrada_rapida(hoje_real, h_lim_e)
            
            if len(st.session_state.fila_offline) > 0:
                st.markdown("---")
                st.warning(f"⚠️ **SINCRONIZAÇÃO PENDENTE**")
                st.write(f"Tem **{len(st.session_state.fila_offline)}** estudante(s) na fila da memória aguardando envio para o banco.")
                
                if st.button("🔄 SINCRONIZAR AGORA COM O BANCO", type="primary"):
                    with st.spinner("A ligar ao banco de dados e a processar todos os registos em lote..."):
                        if st.session_state.fila_offline:
                            conn_sync = conectar_bd()
                            if conn_sync:
                                try:
                                    cur = conn_sync.cursor()
                                    
                                    # 1. Puxar todos os códigos válidos para evitar erro fatal (Foreign Key)
                                    cur.execute("SELECT codigo FROM alunos_v2")
                                    codigos_validos = {row[0] for row in cur.fetchall()}
                                    
                                    registros_validos = []
                                    codigos_invalidos = set()
                                    
                                    # 2. Filtrar a fila
                                    for p in st.session_state.fila_offline:
                                        if p["codigo"] in codigos_validos:
                                            registros_validos.append(p)
                                        else:
                                            codigos_invalidos.add(p["codigo"])
                                            
                                    if registros_validos:
                                        # Apaga faltas anteriores para não duplicar/conflitar
                                        dados_delete = [(p["codigo"], p["data"]) for p in registros_validos]
                                        execute_values(
                                            cur,
                                            "DELETE FROM registros_v2 r USING (VALUES %s) AS v(cod, dt) WHERE r.codigo_aluno = v.cod AND r.data = v.dt::DATE AND r.tipo_registro = 'FALTA'",
                                            dados_delete
                                        )
                                        
                                        # Insere as presenças em lote
                                        dados_insercao = [(p["codigo"], p["data"], p["hora"], p["status"], 'PRESENCA') for p in registros_validos]
                                        execute_values(
                                            cur, 
                                            "INSERT INTO registros_v2 (codigo_aluno, data, hora_entrada, status_entrada, tipo_registro) VALUES %s ON CONFLICT DO NOTHING", 
                                            dados_insercao
                                        )
                                        
                                    conn_sync.commit()
                                    
                                    # Limpa a fila e os caches
                                    st.session_state.fila_offline = [] 
                                    contar_presencas_data.clear()
                                    
                                    if codigos_invalidos:
                                        st.warning(f"Sincronização feita ({len(registros_validos)} salvos). ATENÇÃO: Os seguintes códigos não existem no banco e foram ignorados: {', '.join(codigos_invalidos)}")
                                    else:
                                        st.success(f"Excelente! Todos os {len(registros_validos)} registos foram sincronizados de forma segura e perfeita.")
                                        
                                    time.sleep(3)
                                    st.rerun()
                                except Exception as e:
                                    conn_sync.rollback()
                                    st.error(f"Falha técnica durante a sincronização em lote: {e}")
                                finally:
                                    liberar_conn(conn_sync)
                            else:
                                st.error("Sem ligação à internet no momento. Tente novamente mais tarde, os dados continuam salvos na fila.")

    with t_sa:
        if not verificar_dia_letivo(hoje_real): 
            st.error("⚠️ REGISTRO BLOQUEADO: A data de HOJE não foi ativada como Dia Letivo no painel logo acima.")
        else:
            gerar_camera("Saída", "CONFIRMAR SAÍDA", "c_out")
            
            with st.form("f_sa", clear_on_submit=True):
                st.markdown("##### Identifique o estudante:")
                
                c_sa1, c_sa2 = st.columns(2)
                with c_sa1: 
                    cod_sa = st.text_input("Por Código (Bipe o Cartão)")
                with c_sa2: 
                    lista_alunos_saida = [""] + [f"{r['codigo']} - {r['nome']} ({r['turma']})" for _, r in df_alunos.iterrows()]
                    nome_sa = st.selectbox("Ou busque pelo Nome / Turma", lista_alunos_saida)
                
                hora_saida_manual = st.time_input("Horário Exato da Saída", obter_hora_atual().time())
                mot = st.selectbox("Motivo", ["Mal-estar", "Consulta Médica", "Liberação da Direção", "Término do Turno", "Outros"])
                
                if st.form_submit_button("CONFIRMAR SAÍDA"):
                    if cod_sa:
                        aluno_identificado = cod_sa.upper()
                    elif nome_sa:
                        aluno_identificado = nome_sa.split(" - ")[0]
                    else:
                        aluno_identificado = None
                    
                    if aluno_identificado:
                        res = registrar_saida(aluno_identificado, mot, True, hoje_real, hora_saida_manual.strftime("%H:%M:%S"), h_lim_s)
                        if res: 
                            st.success(f"Saída de {res} registrada às {hora_saida_manual.strftime('%H:%M')}!")
                            st.rerun()
                        else: 
                            st.error("Erro: Aluno sem registro de entrada hoje.")
                    else:
                        st.warning("⚠️ Por favor, informe o código do cartão ou selecione o nome na lista antes de confirmar.")

    with t_jf:
        st.subheader("Justificar Faltas de Estudantes")
        d_just = st.date_input("Data da Falta", value=data_f_global)
        df_faltas = carregar_faltas(d_just.strftime("%Y-%m-%d"))
        
        if not df_faltas.empty:
            turmas_disponiveis = ["Todas"] + sorted(df_faltas['turma'].unique())
            turma_just = st.selectbox("Filtrar por Turma", turmas_disponiveis)
            
            if turma_just == "Todas":
                df_faltas_filtrado = df_faltas
            else:
                df_faltas_filtrado = df_faltas[df_faltas['turma'] == turma_just]
                
            df_pendentes = df_faltas_filtrado[df_faltas_filtrado['motivo_saida'].isnull()]
            
            if not df_pendentes.empty:
                with st.form("form_justificar"):
                    al_falta_sel = st.selectbox(
                        "Selecione o Estudante Faltoso", 
                        [""] + [f"{r['codigo_aluno']} - {r['nome']} ({r['turma']})" for _, r in df_pendentes.iterrows()]
                    )
                    motivo_falta = st.selectbox(
                        "Justificativa Oficial", 
                        ["DOENTE", "VIAGEM", "ACOMPANHAR PARENTE", "CONSULTA", "EXAME", "OUTROS"]
                    )
                    
                    if st.form_submit_button("SALVAR JUSTIFICATIVA") and al_falta_sel:
                        cod_f = al_falta_sel.split(" - ")[0]
                        conn = conectar_bd()
                        if conn:
                            try:
                                cur = conn.cursor()
                                cur.execute("""
                                    INSERT INTO registros_v2 (codigo_aluno, data, tipo_registro, motivo_saida) 
                                    VALUES (%s, %s, 'FALTA', %s)
                                    ON CONFLICT (codigo_aluno, data, tipo_registro) 
                                    DO UPDATE SET motivo_saida = EXCLUDED.motivo_saida
                                """, (cod_f, d_just.strftime("%Y-%m-%d"), motivo_falta))
                                conn.commit()
                                carregar_faltas.clear()
                                st.success("Justificativa salva com sucesso!")
                                time.sleep(1)
                                st.rerun()
                            finally: 
                                liberar_conn(conn)
            else:
                st.info(f"Todos os alunos faltosos da turma {turma_just} já foram justificados.")

            st.markdown("---")
            st.write("**Faltas já justificadas nesta data:**")
            faltas_justificadas = df_faltas[df_faltas['motivo_saida'].notna()]
            
            if not faltas_justificadas.empty:
                for _, f in faltas_justificadas.iterrows(): 
                    st.info(f"👤 {f['nome']} ({f['turma']}) - Justificativa: **{f['motivo_saida']}**")
            else: 
                st.write("Nenhuma falta justificada ainda.")
        else: 
            st.success("Nenhum aluno faltou nesta data! Todos os alunos ativos estão com 'PRESENCA'.")
indice_aba += 1

with tabs[indice_aba]:
    st.subheader("📊 Relatório Diário")
    c1, c2, c3, c4 = st.columns(4)
    with c1: 
        dt_f = st.date_input("Data", value=data_f_global, key="data_relatorio")
    with c2: 
        lista_turmas_gestao = ["Todas"]
        if not df_alunos.empty:
            lista_turmas_gestao += sorted(df_alunos['turma'].unique())
            
        index_turma = 0
        if tf != "Todas" and tf in lista_turmas_gestao:
            index_turma = lista_turmas_gestao.index(tf)
            
        t_f_gestao = st.selectbox("Turma (Frequência)", lista_turmas_gestao, index=index_turma, key="filtro_turma_gestao")
    with c3: 
        s_f = st.selectbox("Status", ["Todos", "Presentes", "Ausentes"], key="filtro_status_gestao")
    with c4: 
        b_f = st.text_input("Buscar Nome", key="busca_nome_gestao")
    
    params = [dt_f.strftime("%Y-%m-%d")]
    query = "SELECT a.codigo, a.nome, a.turma, COALESCE(r.tipo_registro, 'NÃO REGISTRADO (AUSENTE)') as tipo_registro, r.hora_entrada, r.status_entrada, r.hora_saida, r.motivo_saida FROM alunos_v2 a LEFT JOIN registros_v2 r ON a.codigo = r.codigo_aluno AND r.data = %s WHERE a.status = 'ATIVO'"
    
    if t_f_gestao != "Todas": 
        query += " AND a.turma = %s"
        params.append(t_f_gestao)
        
    if s_f == "Presentes": 
        query += " AND r.tipo_registro = 'PRESENCA'"
    elif s_f == "Ausentes": 
        query += " AND (r.tipo_registro = 'FALTA' OR r.tipo_registro IS NULL)"
        
    if b_f: 
        query += " AND a.nome ILIKE %s"
        params.append(f"%{b_f}%")
        
    query += " ORDER BY a.turma, a.nome"
    
    conn = conectar_bd()
    if conn:
        try:
            df_relatorio = pd.read_sql_query(query, conn, params=params)
            st.dataframe(df_relatorio, use_container_width=True, hide_index=True)
        except: 
            st.info("Sem dados para exibir no momento.")
        finally: 
            liberar_conn(conn)
    else: 
        st.error("Sem conexão com o banco de dados.")
indice_aba += 1

with tabs[indice_aba]:
    st.subheader("🚨 Alunos em Risco (5 dias ausentes)")
    dias_u = [(obter_hora_atual() - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7) if (obter_hora_atual() - timedelta(days=i)).weekday() < 5][:5]
    
    if dias_u:
        conn = conectar_bd()
        if conn:
            try:
                df_risco = pd.read_sql_query("SELECT a.codigo, a.nome, a.turma FROM alunos_v2 a WHERE a.status = 'ATIVO' AND a.codigo NOT IN (SELECT DISTINCT codigo_aluno FROM registros_v2 WHERE data IN %s AND tipo_registro='PRESENCA')", conn, params=[tuple(dias_u)])
                if not df_risco.empty: 
                    st.error(f"{len(df_risco)} alunos em risco")
                    st.dataframe(df_risco, hide_index=True)
                else: 
                    st.success("Nenhum aluno ativo nesta situação.")
            except: 
                st.info("Aguardando...")
            finally: 
                liberar_conn(conn)
indice_aba += 1

with tabs[indice_aba]:
    st.subheader("📈 Histórico Individual")
    
    lista_historico = [""]
    if not df_alunos.empty:
        lista_historico += [f"{r['codigo']} - {r['nome']} ({r['turma']}) - {r['status']}" for _, r in df_alunos.iterrows()]
        
    aluno_sel = st.selectbox("Selecione o aluno", lista_historico, key="historico_aluno")
    
    if aluno_sel:
        conn = conectar_bd()
        if conn:
            try:
                df_hist = pd.read_sql_query("SELECT data, tipo_registro, hora_entrada, status_entrada, hora_saida, motivo_saida FROM registros_v2 WHERE codigo_aluno = %s ORDER BY data DESC, hora_entrada DESC", conn, params=[aluno_sel.split(" - ")[0]])
                st.dataframe(df_hist, hide_index=True)
            except: 
                st.warning("Erro ao carregar histórico.")
            finally: 
                liberar_conn(conn)
indice_aba += 1

with tabs[indice_aba]:
    st.title("📊 Desempenho Acadêmico")
    st.info("💡 **Atenção:** Os dados exibidos nesta aba obedecem aos Filtros Globais selecionados no topo da tela (Ano, Período, Área e Turma).")
    
    sub_da = ["🏆 Destaques", "🧑‍🎓 Estudantes", "🚫 Faltosos na Prova", "📈 Gráficos", "📋 Questões Críticas", "📝 Faltou 1ª Chamada"]
    stabs = st.tabs(sub_da)
    
    alertas_estudante, area_stats = obter_estatisticas_areas_cached(ano_f, pf, af, tf)
    
    with stabs[0]:
        if not dff.empty:
            top7 = obter_top7_cached(ano_f, pf, af, tf)
            for idx, r in enumerate(top7.to_dict('records')):
                if eh_admin: 
                    rev = st.toggle("Revelar", key=f"rev_{idx}")
                else: 
                    rev = False
                    
                if idx == 0:
                    medalha = "🥇 1º LUGAR"
                elif idx == 1:
                    medalha = "🥈 2º LUGAR"
                elif idx == 2:
                    medalha = "🥉 3º LUGAR"
                else:
                    medalha = f"⭐ {idx+1}º LUGAR"
                    
                if rev:
                    classe_nome = "top7-name"
                    texto_nome = f"{r['nome']} ({r['turma']})"
                else:
                    classe_nome = "top7-name-hidden"
                    texto_nome = "OCULTO"
                    
                st.markdown(f'<div class="top7-card"><div class="top7-medal">{medalha}</div><div class="{classe_nome}">{texto_nome}</div><div class="top7-details">NOTA (FILTRADA): {r["acerto"]*10:.2f} | {r["turma"]}</div></div>', unsafe_allow_html=True)
    
    with stabs[1]:
        if not dff.empty:
            st.markdown("#### ⚙️ Filtros do Boletim do Estudante")
            c_est1, c_est2, c_est3, c_est4 = st.columns([2, 1, 1, 1])
            with c_est1: 
                bus_al = st.text_input("Buscar Nome:", key="busca_nome_est")
            with c_est2: 
                filtro_desempenho = st.selectbox("Desempenho:", ["Todos", "INSUFICIENTE", "BOM", "ÓTIMO"], key="filtro_desempenho_est")
            with c_est3: 
                ordenar_por = st.selectbox("Ordenar por:", ["Alfabética", "Maior Nota", "Menor Nota"], key="ordenar_est")
            with c_est4: 
                st.markdown("<br>", unsafe_allow_html=True)
                filtro_erros = st.checkbox("Somente c/ erros", key="filtro_erros_est")

            res_al, erros_n = obter_resumo_estudantes_cached(ano_f, pf, af, tf)
            
            if bus_al: 
                res_al = res_al[res_al['nome'].str.contains(bus_al.upper())]
            if filtro_erros: 
                res_al = res_al[res_al['nome'].isin(erros_n)]
                
            if filtro_desempenho == "INSUFICIENTE": 
                res_al = res_al[res_al['acerto']*10 < 6.0]
            elif filtro_desempenho == "BOM": 
                res_al = res_al[(res_al['acerto']*10 >= 6.0) & (res_al['acerto']*10 <= 7.5)]
            elif filtro_desempenho == "ÓTIMO": 
                res_al = res_al[res_al['acerto']*10 > 7.5]

            if ordenar_por == "Maior Nota": 
                res_al = res_al.sort_values(by=['acerto', 'nome'], ascending=[False, True])
            elif ordenar_por == "Menor Nota": 
                res_al = res_al.sort_values(by=['acerto', 'nome'], ascending=[True, True])
            else: 
                res_al = res_al.sort_values(by='nome')

            total_estudantes_avaliados = len(res_al)
            filtros_ativos = (tf != "Todas") or (pf != "Todos") or (af != "Todas") or bool(bus_al) or filtro_erros or (filtro_desempenho != "Todos") or (ordenar_por != "Alfabética")
            
            lista_completa = res_al.to_dict('records')
            
            if filtros_ativos:
                lista_visualizacao = lista_completa
            else:
                lista_visualizacao = res_al.head(20).to_dict('records')
            
            st.markdown("---")
            gerar_em_lote = st.checkbox("📦 Gerar todos os boletins listados acima em lote (Arquivo ZIP)", key="chk_lote")
            
            if gerar_em_lote:
                st.warning(f"Você está prestes a gerar **{len(lista_completa)} boletins** de uma só vez.")
                zip_key = f"zip_{ano_f}_{pf}_{af}_{tf}_{bus_al}_{filtro_desempenho}_{filtro_erros}_{ordenar_por}"
                
                if st.button("⚙️ PROCESSAR BOLETINS EM LOTE", type="primary"):
                    with st.spinner(f"Gerando {len(lista_completa)} boletins. Por favor, aguarde..."):
                        zip_buffer = io.BytesIO()
                        df_historico_base = obter_dados_acad_filtrados(ano_f, "Todos", "Todas", "Todas")
                        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                            for a in lista_completa:
                                df_bol_ind = dff[dff['nome'] == a['nome']]
                                df_historico_aluno = df_historico_base[df_historico_base['nome'] == a['nome']]
                                pdf_bytes = gerar_pdf_boletim(a['nome'], a['turma'], a['acerto']*10, df_bol_ind, df_historico_aluno)
                                
                                if pdf_bytes:
                                    safe_name = "".join([c for c in a['nome'] if c.isalpha() or c.isdigit() or c==' ']).rstrip()
                                    zip_file.writestr(f"Boletim_{a['turma']}_{safe_name}.pdf", pdf_bytes)
                                    
                        st.session_state[zip_key] = zip_buffer.getvalue()
                        
                if zip_key in st.session_state:
                    st.success("✅ Arquivo ZIP gerado com sucesso!")
                    st.download_button("📥 BAIXAR ARQUIVO ZIP COM OS BOLETINS", data=st.session_state[zip_key], file_name=f"Boletins_{tf.replace(' ', '_')}_{ano_f}.zip", mime="application/zip")
            else:
                if not filtros_ativos: 
                    st.info(f"📊 **Total de estudantes avaliados:** {total_estudantes_avaliados} (Exibindo os 20 primeiros).")
                else: 
                    st.info(f"📊 **Total de estudantes encontrados:** {len(lista_visualizacao)}.")
                
                df_historico_base = obter_dados_acad_filtrados(ano_f, "Todos", "Todas", "Todas")
                
                if not dff.empty:
                    medias_gerais_turma = dff.groupby(['nome', 'disciplina', 'periodo']).agg(Nota=('acerto', lambda x: (sum(x)/len(x))*10)).reset_index()
                    piores_por_aluno = medias_gerais_turma.sort_values(['nome', 'Nota']).groupby('nome').head(3)
                else:
                    piores_por_aluno = pd.DataFrame(columns=['nome', 'disciplina', 'periodo', 'Nota'])
                
                for idx, a in enumerate(lista_visualizacao, start=1):
                    alerta_str = alertas_estudante.get(a['nome'], "")
                    if alerta_str:
                        tag = f" &nbsp; 🚨 [{alerta_str}]"
                    else:
                        tag = ""
                        
                    with st.expander(f"👤 {idx}º | {a['nome']} ({a['turma']}) | Nota: {a['acerto']*10:.2f} {tag}"):
                        
                        df_bol_ind = dff[dff['nome'] == a['nome']]
                        df_historico_aluno = df_historico_base[df_historico_base['nome'] == a['nome']]
                        
                        piores_3 = piores_por_aluno[piores_por_aluno['nome'] == a['nome']]
                        piores_str = " &nbsp;&nbsp;|&nbsp;&nbsp; ".join([f"📉 <span style='color:#ef4444; font-weight:900;'>{r['disciplina']} ({r['Nota']:.1f})</span>" for _, r in piores_3.iterrows()])
                        
                        if not piores_3.empty: 
                            st.markdown(f"<div style='margin-bottom: 15px; padding: 10px; background-color: #fef2f2; border-left: 5px solid #ef4444; border-radius: 5px; font-size: 1.1rem;'><b>Atenção - Menores Notas:</b> {piores_str}</div>", unsafe_allow_html=True)
                        
                        if st.button("GERAR PDF (PERÍODO SELECIONADO)", key=f"pdf_{idx}_{a['nome']}"):
                            b_pdf = gerar_pdf_boletim(a['nome'], a['turma'], a['acerto']*10, df_bol_ind, df_historico_aluno)
                            if b_pdf: 
                                st.download_button("BAIXAR BOLETIM", b_pdf, f"Boletim_{a['nome']}.pdf")
                            else: 
                                st.error("Erro ao gerar PDF.")
                            
                        st.markdown(f"#### 📈 Evolução ao Longo do Ano ({ano_f})")
                        progresso = df_historico_aluno.groupby(['periodo', 'disciplina']).agg(Acertos=('acerto', 'sum'), Total=('questao', 'count')).reset_index()
                        progresso['Nota'] = (progresso['Acertos'] / progresso['Total']) * 10
                        try: 
                            st.line_chart(progresso.pivot(index='periodo', columns='disciplina', values='Nota'), height=250)
                        except: 
                            pass
                        
                        st.markdown("#### 📊 Médias por Disciplina (Filtros Atuais)")
                        medias_b = df_bol_ind.groupby(['disciplina', 'periodo']).agg(Nota=('acerto', lambda x: (sum(x)/len(x))*10)).reset_index()
                        for _, mb in medias_b.iterrows(): 
                            st.write(f"{mb['disciplina'].upper()} - {mb['periodo']} (Nota: {mb['Nota']:.1f})")
                            st.progress(min(mb['Nota'] / 10, 1.0))
                        
                        st.markdown("#### 📋 Mapa de Questões (Filtros Atuais)")
                        for p_m in sorted(df_bol_ind['periodo'].unique()):
                            for d_m in sorted(df_bol_ind[df_bol_ind['periodo']==p_m]['disciplina'].unique()):
                                st.markdown(f"**{d_m} - {p_m}**")
                                q_df = df_bol_ind[(df_bol_ind['periodo']==p_m) & (df_bol_ind['disciplina']==d_m)].sort_values("questao")
                                grid = '<div style="display: flex; flex-wrap: wrap; gap: 8px;">'
                                
                                for _, q in q_df.iterrows():
                                    if q['acerto'] == 1:
                                        cor = "#10b981"
                                    elif q['resposta'] == 'BRANCO':
                                        cor = "#f59e0b"
                                    elif q['resposta'] == 'DUPLA':
                                        cor = "#8b5cf6"
                                    else:
                                        cor = "#ef4444"
                                        
                                    grid += f'<div style="background:{cor}; color:white; padding:8px; border-radius:6px; width:75px; text-align:center; font-size:11px;">Q{q["questao"]}<br>R:{q["resposta"]} G:{q["gabarito"]}</div>'
                                    
                                st.markdown(grid+'</div><br>', unsafe_allow_html=True)
                            
    with stabs[2]:
        if not dff.empty and not area_stats.empty:
            estudantes_faltosos = area_stats[area_stats['Faltou']]
            
            if not estudantes_faltosos.empty:
                st.error(f"⚠️ **REGISTO DE FALTAS NA PROVA ({len(estudantes_faltosos)})**")
                cols_f = st.columns(3)
                for i, r_f in enumerate(estudantes_faltosos.to_dict('records')): 
                    cols_f[i % 3].markdown(f"🚫 **{r_f['nome']}** ({r_f['turma']}) <br> <span style='color:#ef4444;'>Falta em: **{r_f['area']}** ({r_f['periodo']})</span>", unsafe_allow_html=True)
            else: 
                st.success("✨ Nenhum estudante faltou na avaliação selecionada.")

    with stabs[3]:
        if not dff.empty:
            tipo_grafico = st.radio("Agrupar por:", ["Área", "Disciplina"], horizontal=True)
            if tipo_grafico == "Área":
                col_agrup = 'area'
            else:
                col_agrup = 'disciplina'
                
            for p in sorted(dff['periodo'].unique()):
                st.markdown(f"#### 📊 Desempenho: {p}")
                resumo_graf = dff[dff['periodo'] == p].groupby(col_agrup).agg(Acertos=('acerto', 'sum'), Total=('questao', 'count')).reset_index()
                resumo_graf['Nota'] = (resumo_graf['Acertos'] / resumo_graf['Total']) * 10
                
                if tipo_grafico == "Área":
                    resumo_graf['Abreviacao'] = resumo_graf['area'].str.upper()
                else:
                    resumo_graf['Abreviacao'] = resumo_graf['disciplina'].apply(lambda x: DICIONARIO_ABREVIACAO.get(x.upper(), x[:4].upper()))
                    
                resumo_graf['Nome Completo'] = resumo_graf[col_agrup].str.upper()
                
                fig_g = px.bar(
                    resumo_graf.sort_values('Nota'), 
                    x='Abreviacao', y='Nota', color='Abreviacao', 
                    text='Nota', hover_data={'Nome Completo': True, 'Nota': ':.2f', 'Abreviacao': False},
                    color_discrete_map=DICIONARIO_CORES
                )
                fig_g.update_traces(texttemplate='%{text:.1f}', textposition='outside')
                fig_g.update_layout(yaxis=dict(range=[0, 11]), plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', showlegend=False)
                st.plotly_chart(fig_g, use_container_width=True, key=f"grafico_{p}_{tipo_grafico}")

    with stabs[4]:
        if not dff.empty:
            st.subheader("❌ Top 3 Erros (Por Matéria e Turma)")
            q_err_top3 = obter_top3_erros_cached(ano_f, pf, af, tf)
            
            if not q_err_top3.empty:
                pdf_data = gerar_pdf_relatorio_critico(q_err_top3)
                if pdf_data: 
                    st.download_button("📥 BAIXAR RELATÓRIO EM PDF", data=pdf_data, file_name="Questoes_Criticas.pdf", mime="application/pdf")
                    
                st.markdown("---")
                for t in sorted(q_err_top3['turma'].unique()):
                    st.markdown(f"### 🏫 Turma: **{t}**")
                    df_t = q_err_top3[q_err_top3['turma'] == t]
                    
                    for p in sorted(df_t['periodo'].unique()):
                        st.markdown(f"#### 📅 Período: **{p}**")
                        df_p = df_t[df_t['periodo'] == p]
                        
                        for d in sorted(df_p['disciplina'].unique()):
                            st.markdown(f"- **{d}**")
                            for _, r in df_p[df_p['disciplina'] == d].iterrows(): 
                                st.write(f"  - Questão {r['questao']} (Erro: **{r['Taxa de Erro (%)']:.1f}%**)")
                                
                        st.markdown("<br>", unsafe_allow_html=True)
                    st.markdown("---")
            else: 
                st.success("Não foram detectados erros de marcação para estes filtros!")
            
    with stabs[5]:
        st.markdown("#### 📝 Histórico de Faltas na 1ª Chamada")
        st.write(f"Visualizando dados do Ano Letivo: **{ano_f}**")
        df_faltas_1a = carregar_faltas_primeira_chamada(ano_f)
        
        if pf != "Todos" and not df_faltas_1a.empty:
            df_faltas_1a = df_faltas_1a[df_faltas_1a['periodo'] == pf]
            
        if af != "Todas" and not df_faltas_1a.empty:
            df_faltas_1a = df_faltas_1a[df_faltas_1a['area'] == af]
            
        if tf != "Todas" and not df_faltas_1a.empty:
            df_faltas_1a = df_faltas_1a[df_faltas_1a['turma'] == tf]
        
        if df_faltas_1a.empty:
            st.success(f"🎉 Nenhum registro de falta na 1ª chamada encontrado para os filtros atuais!")
        else:
            st.dataframe(df_faltas_1a, use_container_width=True, hide_index=True)
indice_aba += 1

# ------------------------------------------------------------
# 7. NOVA ABA: ANÁLISE DE SATISFAÇÃO DA COMUNIDADE
# ------------------------------------------------------------
with tabs[indice_aba]:
    st.title("💬 Análise de Satisfação da Comunidade")
    st.info(f"💡 **Dica:** Os dados exibidos obedecem ao Ano Global selecionado no topo ({ano_f}) e à Turma (para Estudantes).")
    
    df_sat_ano = carregar_satisfacao_por_ano(ano_f)
    
    if df_sat_ano.empty:
        st.warning(f"Nenhuma avaliação registrada para o ano de {ano_f}.")
    else:
        cat_sat = st.selectbox("Selecione o Segmento para Análise Gráfica:", ["Todos", "Estudante", "Pais/Responsável", "Professor", "Servidor"], key="filtro_cat_sat")
        
        df_sat_filtrado = df_sat_ano.copy()
        if cat_sat != "Todos": 
            df_sat_filtrado = df_sat_filtrado[df_sat_filtrado['categoria'] == cat_sat]
            
        if cat_sat in ["Todos", "Estudante"] and tf != "Todas": 
            df_sat_filtrado = df_sat_filtrado[df_sat_filtrado['turma'] == tf]
            
        if df_sat_filtrado.empty:
            st.info("Nenhum dado encontrado para os filtros selecionados.")
        else:
            nomes_perguntas = DICIONARIO_PERGUNTAS_SATISFACAO[cat_sat]
            df_grafico_sat = pd.DataFrame({
                'Pergunta': nomes_perguntas,
                'Média (Max 5)': [df_sat_filtrado['q1'].mean(), df_sat_filtrado['q2'].mean(), df_sat_filtrado['q3'].mean(), df_sat_filtrado['q4'].mean(), df_sat_filtrado['q5'].mean()]
            })
            
            fig_sat = px.bar(df_grafico_sat, x='Pergunta', y='Média (Max 5)', text='Média (Max 5)', color='Pergunta', title=f"Média de Satisfação: {cat_sat}")
            fig_sat.update_traces(texttemplate='%{text:.2f}', textposition='outside')
            fig_sat.update_layout(yaxis=dict(range=[0, 5.5]), plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', showlegend=False)
            st.plotly_chart(fig_sat, use_container_width=True)

            st.markdown("---")
            st.subheader("📝 Mural de Sugestões e Feedbacks")
            df_sugestoes = df_sat_filtrado[df_sat_filtrado['sugestao'].notna() & (df_sat_filtrado['sugestao'].str.strip() != "")]
            
            if df_sugestoes.empty: 
                st.success("Não há sugestões em texto para este grupo.")
            else:
                for _, sug in df_sugestoes.iterrows():
                    data_str = sug['data_hora'].strftime("%d/%m/%Y %H:%M")
                    if sug['turma']:
                        turma_str = f" ({sug['turma']})"
                    else:
                        turma_str = ""
                        
                    st.info(f"**Data:** {data_str} | **Perfil:** {sug['categoria']}{turma_str}\n\n**Mensagem:** {sug['sugestao']}")
indice_aba += 1

if eh_admin:
    with tabs[indice_aba]:
        st.subheader("📝 Registrar Falta na 1ª Chamada de Avaliação")
        with st.form("form_falta_1a", clear_on_submit=True):
            c_f1, c_f2, c_f3 = st.columns([1, 1, 2])
            with c_f1: 
                f1_ano = st.selectbox("Ano Letivo", anos_disponiveis, index=anos_disponiveis.index(ano_atual))
            with c_f2: 
                f1_per = st.selectbox("Período Acadêmico", ["1º Período", "2º Período", "3º Período", "4º Período"])
            with c_f3: 
                f1_area = st.selectbox("Área Acadêmica", ["LÍNGUA PORTUGUESA", "MATEMÁTICA", "LINGUAGENS", "HUMANAS", "NATUREZA"])
            
            lista_alunos_falta = [""]
            if not df_alunos.empty:
                lista_alunos_falta += [f"{r['codigo']} - {r['nome']} ({r['turma']})" for _, r in df_alunos.iterrows()]
                
            f1_aluno = st.selectbox("Selecione o Estudante", lista_alunos_falta)
            f1_motivo = st.selectbox("Motivo da Falta", ["Doença", "Viagem", "Acompanhar parente", "Sem justificativa", "Outros"])
            
            if st.form_submit_button("💾 SALVAR REGISTRO DE FALTA"):
                if f1_aluno:
                    cod_aluno = f1_aluno.split(" - ")[0]
                    conn_f1 = conectar_bd()
                    if conn_f1:
                        try:
                            cur_f1 = conn_f1.cursor()
                            cur_f1.execute("""
                                INSERT INTO faltas_primeira_chamada (codigo_aluno, ano, periodo, area, motivo) 
                                VALUES (%s, %s, %s, %s, %s) 
                                ON CONFLICT (codigo_aluno, ano, periodo, area) 
                                DO UPDATE SET motivo = EXCLUDED.motivo, data_registro = CURRENT_TIMESTAMP
                            """, (cod_aluno, f1_ano, f1_per, f1_area, f1_motivo))
                            conn_f1.commit()
                            carregar_faltas_primeira_chamada.clear()
                            st.success(f"Falta na 1ª chamada de {f1_area} registrada com sucesso para {f1_aluno.split(' - ')[1]}!")
                        except Exception as e: 
                            st.error(f"Erro ao salvar: {e}")
                        finally: 
                            liberar_conn(conn_f1)
                    else: 
                        st.error("Sem conexão com o banco de dados.")
                else: 
                    st.error("Por favor, selecione um estudante na lista.")
                    
        st.markdown("---")
        
        st.subheader("🔗 Link da Pesquisa de Satisfação Pública")
        link_completo = f"https://seu-projeto.streamlit.app/?modo=pesquisa"
        st.code(link_completo, language="text")
        st.markdown("---")

        st.subheader("📧 Gerir E-mails e Alunos")
        col1, col2 = st.columns(2)
        
        with col1:
            lista_emails_aluno = [""]
            if not df_alunos.empty:
                lista_emails_aluno += [f"{r['codigo']} - {r['nome']} ({r['turma']})" for _, r in df_alunos.iterrows()]
                
            al_email = st.selectbox("Selecione o Aluno", lista_emails_aluno)
            novo_e = st.text_input("Novo E-mail do Responsável")
            
            if st.button("SALVAR E-MAIL") and al_email and novo_e:
                conn = conectar_bd()
                if conn:
                    try:
                        cur = conn.cursor()
                        cur.execute("UPDATE alunos_v2 SET email_responsavel=%s WHERE codigo=%s", (novo_e.lower(), al_email.split(" - ")[0]))
                        conn.commit()
                        _carregar_alunos_cache.clear()
                        st.success("Atualizado com sucesso!")
                    except Exception as e: 
                        conn.rollback()
                        st.error(f"Erro ao salvar: {e}")
                    finally: 
                        liberar_conn(conn)
        
        with col2:
            st.write("Adição Manual de Aluno")
            m_cod = st.text_input("Matrícula")
            m_nom = st.text_input("Nome Completo")
            
            if not df_alunos.empty:
                lista_turmas = sorted(df_alunos['turma'].unique()) 
            else:
                lista_turmas = []
                
            m_tur_sel = st.selectbox("Selecione a Turma", ["Selecione..."] + lista_turmas + ["+ Criar Nova Turma"])
            
            if m_tur_sel == "+ Criar Nova Turma": 
                m_tur = st.text_input("Digite o nome da nova turma")
            else: 
                m_tur = m_tur_sel

            if st.button("CADASTRAR ALUNO"):
                if m_cod and m_nom and m_tur and m_tur != "Selecione...":
                    conn = conectar_bd()
                    if conn:
                        try:
                            cur = conn.cursor()
                            cur.execute("INSERT INTO alunos_v2 (codigo, nome, turma) VALUES (%s, %s, %s)", (m_cod.upper(), m_nom.upper(), m_tur.upper()))
                            conn.commit()
                            _carregar_alunos_cache.clear()
                            st.success("Cadastrado com sucesso!")
                        except Exception as e:
                            conn.rollback()
                            if "UniqueViolation" in str(type(e).__name__): 
                                st.error("⚠️ Atenção: Já existe um aluno cadastrado no sistema com esta mesma Matrícula!")
                            else: 
                                st.error(f"Erro inesperado: {e}")
                        finally: 
                            liberar_conn(conn)
                else: 
                    st.warning("Preencha todos os campos antes de cadastrar.")

        st.divider()

        st.markdown("#### 🗑️ Excluir Registro de Aluno")
        st.warning("⚠️ **ATENÇÃO:** A exclusão apagará o aluno e todo o seu histórico (frequência/notas) para evitar conflitos no banco.")
        
        c_del1, c_del2 = st.columns([3, 1])
        with c_del1: 
            lista_excluir = [""]
            if not df_alunos.empty:
                lista_excluir += [f"{r['codigo']} - {r['nome']} ({r['turma']})" for _, r in df_alunos.iterrows()]
            aluno_excluir = st.selectbox("Selecione o Aluno para exclusão definitiva", lista_excluir, key="sel_del_aluno")
            
        with c_del2: 
            st.write("")
            st.write("")
            btn_excluir = st.button("🚨 EXCLUIR ALUNO", type="primary", use_container_width=True)

        if btn_excluir and aluno_excluir:
            cod_del = aluno_excluir.split(" - ")[0]
            conn = conectar_bd()
            if conn:
                try:
                    cur = conn.cursor()
                    cur.execute("DELETE FROM registros_v2 WHERE codigo_aluno = %s", (cod_del,))
                    cur.execute("DELETE FROM faltas_primeira_chamada WHERE codigo_aluno = %s", (cod_del,))
                    cur.execute("DELETE FROM alunos_v2 WHERE codigo = %s", (cod_del,))
                    conn.commit()
                    _carregar_alunos_cache.clear() 
                    st.success(f"O registro {cod_del} foi completamente excluído!")
                    time.sleep(2)
                    st.rerun()
                except Exception as e: 
                    conn.rollback()
                    st.error(f"Erro ao tentar excluir aluno: {e}")
                finally: 
                    liberar_conn(conn)

        st.divider()
        up_al = st.file_uploader("Importar Lista de Alunos (CSV)", type="csv")
        
        if st.button("PROCESSAR LISTA") and up_al:
            if importar_csv_alunos(up_al): 
                st.success("Base de Alunos Sincronizada!")
                st.rerun()

        st.markdown("---")
        st.subheader("☁️ Gerenciamento do Banco de Dados AVS")
        c_up0, c_up1, c_up2, c_up3 = st.columns(4)
        with c_up0: 
            ano_up = st.selectbox("Ano de Lançamento:", anos_disponiveis, index=anos_disponiveis.index(ano_atual), key="anoup")
        with c_up1: 
            p_up = st.selectbox("Período:", ["1º Período", "2º Período", "3º Período", "4º Período"], key="pup")
        with c_up2: 
            a_up = st.selectbox("Área:", ["LÍNGUA PORTUGUESA", "MATEMÁTICA", "LINGUAGENS", "HUMANAS", "NATUREZA"], key="aup")
        with c_up3: 
            lista_turmas_up = ["Todas"]
            if not df_alunos.empty:
                lista_turmas_up = sorted(df_alunos['turma'].unique())
            t_up = st.selectbox("Turma:", lista_turmas_up, key="tup")
        
        arquivo_avs = st.file_uploader("Arquivo CSV da Avaliação", type=["csv"], key="csv_avs_up")
        if st.button("PROCESSAR E SALVAR AGORA", type="primary", key="btn_salvar_avs") and arquivo_avs:
            with st.spinner("Processando e injetando dados em lote..."):
                sucesso, msg = importar_csv_desempenho(arquivo_avs, ano_up, p_up, a_up, t_up)
                if sucesso: 
                    st.success(msg)
                    st.rerun()
                else: 
                    st.error(msg)
            
        st.markdown("---")
        st.subheader("🗑️ Limpeza Seletiva de Banco")
        
        conn_limpeza = conectar_bd()
        try: 
            blocos_df = pd.read_sql("SELECT DISTINCT ano, periodo, area, turma FROM avaliacoes_avs", conn_limpeza)
        except: 
            blocos_df = pd.DataFrame()
        finally: 
            liberar_conn(conn_limpeza)
        
        if not blocos_df.empty:
            lista_blocos = [f"{r['ano']} | {r['periodo']} | {r['area']} | {r['turma']}" for _, r in blocos_df.iterrows()]
            bloco_del = st.selectbox("Blocos importados (Acadêmico):", lista_blocos, key="bloco_excluir_avs")
            
            if st.button("EXCLUIR BLOCO SELECIONADO", key="btn_excluir_avs_db"):
                ano_del, p_del, a_del, t_del = bloco_del.split(" | ")
                conn_del = conectar_bd()
                if conn_del:
                    try:
                        cur = conn_del.cursor()
                        cur.execute("DELETE FROM avaliacoes_avs WHERE ano=%s AND periodo=%s AND area=%s AND turma=%s", (ano_del, p_del, a_del, t_del))
                        conn_del.commit()
                        st.success("Bloco removido do servidor!")
                        st.rerun()
                    finally: 
                        liberar_conn(conn_del)
        else: 
            st.info("O banco de dados de desempenho está vazio.")

        st.markdown("---")
        if st.button("🗑️ EXCLUIR TODAS AS RESPOSTAS DE SATISFAÇÃO"):
            conn_sat = conectar_bd()
            if conn_sat:
                try:
                    cur = conn_sat.cursor()
                    cur.execute("DELETE FROM satisfacao_v1")
                    conn_sat.commit()
                    carregar_satisfacao_por_ano.clear()
                    st.success("Respostas apagadas.")
                    st.rerun()
                finally: 
                    liberar_conn(conn_sat)
