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

cookies = CookieManager()
if not cookies.ready(): st.stop()

# ------------------------------------------------------------
# 2. BANCO DE DADOS (CONNECTION POOLING)
# ------------------------------------------------------------
DATABASE_URL = st.secrets.get("DATABASE_URL")
SENHA_OPERADOR = st.secrets.get("SENHA_OPERADOR", "admin123")
SENHA_ADMIN = st.secrets.get("SENHA_ADMIN", "admin123")

@st.cache_resource
def get_connection_pool():
    # ThreadedConnectionPool é o mais seguro para Streamlit
    return pool.ThreadedConnectionPool(1, 20, DATABASE_URL)

def conectar_bd():
    return get_connection_pool().getconn()

def liberar_conn(conn):
    if conn:
        get_connection_pool().putconn(conn)

# ------------------------------------------------------------
# 3. FUNÇÕES DE SUPORTE (TEMPO, E-MAIL E CORES)
# ------------------------------------------------------------
def obter_hora_atual(): return datetime.utcnow() - timedelta(hours=3)

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
    try: data_f = datetime.strptime(data, "%Y-%m-%d").strftime("%d/%m/%Y")
    except: data_f = data
    
    if evento.startswith("ENTRADA"):
        assunto = f"🏫 Aviso de Entrada - Jansen Veloso"
        if "ATRASO" in evento: texto = f"Olá, família!\n\nInformamos que o estudante {nome_aluno} registrou ENTRADA COM ATRASO na escola hoje ({data_f}) às {horario}.\n\nAtenciosamente,\nEquipe Jansen Veloso."
        else: texto = f"Olá, família!\n\nInformamos que o estudante {nome_aluno} registrou ENTRADA na escola hoje ({data_f}) às {horario} (Dentro do horário regular).\n\nAtenciosamente,\nEquipe Jansen Veloso."
    elif evento == "SAÍDA REGULAR":
        assunto = f"🏫 Aviso de Saída - Jansen Veloso"
        texto = f"Olá, família!\n\nInformamos que o estudante {nome_aluno} registrou SAÍDA REGULAR da escola hoje ({data_f}) às {horario}.\n\nAtenciosamente,\nEquipe Jansen Veloso."
    else:
        assunto = f"🏫 Aviso de SAÍDA ANTECIPADA - Jansen Veloso"
        texto = f"⚠️ ATENÇÃO!\n\nInformamos que o estudante {nome_aluno} registrou uma SAÍDA ANTECIPADA hoje ({data_f}) às {horario}.\n\nAtenciosamente,\nEquipe Jansen Veloso."
    
    msg = MIMEMultipart(); msg['From'] = EMAIL_ESCOLA; msg['To'] = email_destino; msg['Subject'] = assunto
    msg.attach(MIMEText(texto, 'plain'))
    def enviar():
        if ATIVAR_EMAILS and EMAIL_ESCOLA and SENHA_APP_ESCOLA:
            try:
                server = smtplib.SMTP('smtp.gmail.com', 587); server.starttls(); server.login(EMAIL_ESCOLA, SENHA_APP_ESCOLA)
                server.send_message(msg); server.quit()
            except: pass
    threading.Thread(target=enviar).start()

@st.cache_resource 
def carregar_logo_base64():
    if os.path.exists("logo.png"):
        try:
            with open("logo.png", "rb") as image_file: return base64.b64encode(image_file.read()).decode()
        except: return None
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
    try:
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS alunos_v2 (codigo TEXT PRIMARY KEY, nome TEXT, turma TEXT, status TEXT DEFAULT 'ATIVO', email_responsavel TEXT)")
        cur.execute("CREATE TABLE IF NOT EXISTS registros_v2 (id SERIAL PRIMARY KEY, codigo_aluno TEXT REFERENCES alunos_v2(codigo), data DATE, hora_entrada TIME, status_entrada TEXT, hora_saida TIME, motivo_saida TEXT, pais_informados BOOLEAN, tipo_registro TEXT, UNIQUE(codigo_aluno, data, tipo_registro))")
        cur.execute("CREATE TABLE IF NOT EXISTS avaliacoes_avs (id SERIAL PRIMARY KEY, ano TEXT, periodo TEXT, area TEXT, turma TEXT, nome TEXT, disciplina TEXT, questao INTEGER, resposta TEXT, gabarito TEXT, acerto INTEGER, UNIQUE(ano, periodo, area, turma, nome, disciplina, questao))")
        
        # TABELA PARA HISTÓRICO DE FALTAS NA 1ª CHAMADA (COM COLUNA ÁREA)
        cur.execute("""CREATE TABLE IF NOT EXISTS faltas_primeira_chamada (
            id SERIAL PRIMARY KEY,
            codigo_aluno TEXT REFERENCES alunos_v2(codigo),
            ano TEXT,
            periodo TEXT,
            area TEXT,
            motivo TEXT,
            data_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(codigo_aluno, ano, periodo, area)
        )""")
        
        # Script de Atualização: Caso a tabela já exista do código anterior, adiciona a coluna e atualiza a regra
        try:
            cur.execute("ALTER TABLE faltas_primeira_chamada ADD COLUMN area TEXT DEFAULT 'GERAL'")
            cur.execute("SELECT constraint_name FROM information_schema.table_constraints WHERE table_name='faltas_primeira_chamada' AND constraint_type='UNIQUE'")
            for c in cur.fetchall():
                cur.execute(f"ALTER TABLE faltas_primeira_chamada DROP CONSTRAINT {c[0]}")
            cur.execute("ALTER TABLE faltas_primeira_chamada ADD UNIQUE (codigo_aluno, ano, periodo, area)")
            conn.commit()
        except Exception: conn.rollback() # Ignora se a coluna e regras já estiverem perfeitamente configuradas
        
        try:
            cur.execute("ALTER TABLE avaliacoes_avs ADD COLUMN ano TEXT DEFAULT '2026'")
            conn.commit()
        except Exception: conn.rollback()

        try:
            cur.execute("SELECT constraint_name FROM information_schema.table_constraints WHERE table_name='avaliacoes_avs' AND constraint_type='UNIQUE'")
            constraints = cur.fetchall()
            for c in constraints: cur.execute(f"ALTER TABLE avaliacoes_avs DROP CONSTRAINT {c[0]}")
            cur.execute("ALTER TABLE avaliacoes_avs ADD UNIQUE (ano, periodo, area, turma, nome, disciplina, questao)")
            conn.commit()
        except Exception: conn.rollback()

        cur.execute("""CREATE TABLE IF NOT EXISTS satisfacao_v1 (
            id SERIAL PRIMARY KEY, data_hora TIMESTAMP, categoria TEXT, turma TEXT, 
            q1 INTEGER, q2 INTEGER, q3 INTEGER, q4 INTEGER, q5 INTEGER, sugestao TEXT
        )""")
        cur.execute("CREATE TABLE IF NOT EXISTS calendario_letivo (data DATE PRIMARY KEY, dia_letivo BOOLEAN DEFAULT TRUE)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_reg_data ON registros_v2(data)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_avs_geral ON avaliacoes_avs(ano, periodo, area, turma)")
        conn.commit()
    except Exception as e: print(f"Erro inicialização: {e}")
    finally: liberar_conn(conn)

inicializar_tabelas()

# ------------------------------------------------------------
# 5. CSS (VISUAL PREMIUM E CORREÇÃO DO MODO ESCURO)
# ------------------------------------------------------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap');
    :root { --primary: #0a1f35; --accent: #ff7b00; --success: #10b981; --danger: #ef4444; --bg-color: #f8fafc; }
    .stApp { background: var(--bg-color); }
    #MainMenu, footer, header {visibility: hidden;}
    html, body, [class*="css"], p, span, label, div { font-size: 1.15rem !important; }
    
    /* CORREÇÃO DO MODO ESCURO NOS RADIO BUTTONS (PESQUISA DE SATISFAÇÃO) */
    [data-testid="stRadio"] div[role="radiogroup"] > label { 
        font-size: 1.3rem !important; padding: 16px 15px !important; margin-bottom: 12px !important; 
        background-color: #ffffff !important; 
        color: #000000 !important; /* FORÇA TEXTO PRETO */
        border: 2px solid #cbd5e1 !important; border-radius: 12px; 
        box-shadow: 0 3px 6px rgba(0,0,0,0.04); cursor: pointer; transition: all 0.2s ease; 
    }
    [data-testid="stRadio"] div[role="radiogroup"] > label * {
        color: #000000 !important; /* FORÇA PRETO EM TODOS OS SUB-ELEMENTOS DO BOTÃO */
        -webkit-text-fill-color: #000000 !important;
    }
    [data-testid="stRadio"] div[role="radiogroup"] > label:hover { border-color: var(--accent) !important; transform: translateY(-2px); }
    
    /* GERAL */
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
    .card-panel { background: white; border-radius: 20px; padding: 2.2rem; margin-bottom: 1.5rem; box-shadow: 0 8px 20px rgba(0,0,0,0.03); border: 2px solid #e2e8f0; }
    
    /* CORREÇÃO DO MODO ESCURO NOS INPUTS E SELECTS */
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
    .login-card { max-width: 600px; margin: 5vh auto; background: white; border-radius: 24px; padding: 3rem 2rem; box-shadow: 0 20px 40px rgba(0,0,0,0.1); border: 3px solid var(--primary); }
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
# 6. LÓGICA DE NEGÓCIO E CACHES OTIMIZADOS SQL-FIRST
# ------------------------------------------------------------
@st.cache_data(ttl=300)
def verificar_dia_letivo(data_atual):
    try:
        conn = conectar_bd()
        cur = conn.cursor()
        cur.execute("SELECT dia_letivo FROM calendario_letivo WHERE data = %s", (data_atual,))
        res = cur.fetchone()
        liberar_conn(conn)
        if res: return res[0]
        return False
    except: return False

@st.cache_data(ttl=60)
def contar_presencas_hoje(data_str):
    try:
        conn = conectar_bd(); cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM registros_v2 WHERE data=%s AND tipo_registro='PRESENCA'", (data_str,))
        count = cur.fetchone()[0]
        liberar_conn(conn)
        return count
    except: return 0

@st.cache_data(ttl=60)
def carregar_faltas(data_str):
    try:
        conn = conectar_bd()
        df = pd.read_sql("SELECT r.codigo_aluno, a.nome, a.turma, r.motivo_saida FROM registros_v2 r JOIN alunos_v2 a ON r.codigo_aluno = a.codigo WHERE r.data = %s AND r.tipo_registro = 'FALTA'", conn, params=[data_str])
        liberar_conn(conn)
        return df
    except: return pd.DataFrame()

@st.cache_data(ttl=3600)  # TTL Aumentado para 1 hora
def carregar_alunos():
    try:
        conn = conectar_bd()
        df = pd.read_sql("SELECT codigo, nome, turma, status, email_responsavel FROM alunos_v2 ORDER BY turma, nome", conn)
        liberar_conn(conn)
        return df
    except: return pd.DataFrame(columns=['codigo','nome','turma','status','email_responsavel'])

# NOVA FUNÇÃO: CARREGAR HISTÓRICO DE FALTAS NA 1ª CHAMADA (AGORA INCLUI A ÁREA)
@st.cache_data(ttl=60)
def carregar_faltas_primeira_chamada(ano):
    query = """
        SELECT a.nome, a.turma, f.periodo, f.area, f.motivo, 
               TO_CHAR(f.data_registro, 'DD/MM/YYYY') as data_registro 
        FROM faltas_primeira_chamada f
        JOIN alunos_v2 a ON f.codigo_aluno = a.codigo
        WHERE f.ano = %s
        ORDER BY f.periodo, f.area, a.turma, a.nome
    """
    conn = conectar_bd()
    try:
        df = pd.read_sql(query, conn, params=[str(ano)])
        return df
    except Exception: return pd.DataFrame()
    finally: liberar_conn(conn)

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
    
    query = f"""
        SELECT avs.id, avs.ano, avs.periodo, avs.area, 
               COALESCE(al.turma, avs.turma) as turma, 
               avs.nome, avs.disciplina, avs.questao, avs.resposta, avs.gabarito, avs.acerto 
        FROM avaliacoes_avs avs
        LEFT JOIN alunos_v2 al ON avs.nome = al.nome
        WHERE {where_clause}
    """
    
    conn = conectar_bd()
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
                for _, r_f in faltas.iterrows(): alertas.append(f"FALTOU {r_f['area']} ({r_f['periodo']})")
            if group['Duplas'].sum() > 0: alertas.append("MARCAÇÃO DUPLA")
            presentes = group[~group['Faltou']]
            if presentes['Brancos'].sum() > 0: alertas.append("EM BRANCO")
            if alertas: alertas_estudante[nome] = " | ".join(alertas)
    return alertas_estudante, area_stats

@st.cache_data(ttl=300)
def obter_top7_cached(ano, p, a, t):
    dff = obter_dados_acad_filtrados(ano, p, a, t)
    if dff.empty: return pd.DataFrame()
    return dff.groupby(['nome','turma']).acerto.mean().reset_index().sort_values('acerto', ascending=False).head(7)

@st.cache_data(ttl=300)
def obter_resumo_estudantes_cached(ano, p, a, t):
    dff = obter_dados_acad_filtrados(ano, p, a, t)
    if dff.empty: return pd.DataFrame(), []
    res_al = dff.groupby(['nome','turma']).acerto.mean().reset_index()
    erros_n = dff[dff['resposta'].isin(['BRANCO','DUPLA'])]['nome'].unique()
    return res_al, erros_n

@st.cache_data(ttl=300)
def obter_top3_erros_cached(ano, p, a, t):
    dff = obter_dados_acad_filtrados(ano, p, a, t)
    if dff.empty: return pd.DataFrame()
    q_err = dff.groupby(['turma', 'periodo', 'disciplina', 'questao']).agg(Total=('questao', 'count'), Acertos=('acerto', 'sum')).reset_index()
    q_err['Taxa de Erro (%)'] = ((q_err['Total'] - q_err['Acertos']) / q_err['Total']) * 100
    q_err_top3 = q_err[q_err['Taxa de Erro (%)'] > 0].sort_values(['turma', 'periodo', 'disciplina', 'Taxa de Erro (%)'], ascending=[True, True, True, False]).groupby(['turma', 'periodo', 'disciplina']).head(3)
    return q_err_top3

@st.cache_data(ttl=300)
def carregar_satisfacao_por_ano(ano):
    query = "SELECT * FROM satisfacao_v1 WHERE EXTRACT(YEAR FROM data_hora) = %s"
    conn = conectar_bd()
    try:
        df = pd.read_sql(query, conn, params=[int(ano)])
        if not df.empty: df['media_resposta'] = df[['q1','q2','q3','q4','q5']].mean(axis=1)
        return df
    except Exception: return pd.DataFrame()
    finally: liberar_conn(conn)

@st.cache_data(ttl=300)
def calcular_satisfacao_global_cached(ano, tf):
    df_sat = carregar_satisfacao_por_ano(ano)
    sat_est_str, sat_pais_str, sat_eq_str = "--", "--", "--"
    if not df_sat.empty:
        df_sat_est = df_sat[df_sat['categoria'] == 'Estudante']
        if tf != "Todas": df_sat_est = df_sat_est[df_sat_est['turma'] == tf]
        if not df_sat_est.empty: sat_est_str = f"{df_sat_est['media_resposta'].mean():.1f} / 5"
        
        df_sat_pais = df_sat[df_sat['categoria'] == 'Pais/Responsável']
        if not df_sat_pais.empty: sat_pais_str = f"{df_sat_pais['media_resposta'].mean():.1f} / 5"
        
        df_sat_eq = df_sat[df_sat['categoria'].isin(['Professor', 'Servidor'])]
        if not df_sat_eq.empty: sat_eq_str = f"{df_sat_eq['media_resposta'].mean():.1f} / 5"
    return sat_est_str, sat_pais_str, sat_eq_str

def importar_csv_alunos(file):
    conteudo_bytes = file.read()
    try: conteudo_str = conteudo_bytes.decode('utf-8-sig')
    except: conteudo_str = conteudo_bytes.decode('latin-1')
    df = pd.read_csv(io.StringIO(conteudo_str), sep=';')
    def norm(c): return ''.join(x for x in unicodedata.normalize('NFD', str(c)) if unicodedata.category(x) != 'Mn').strip().upper()
    df.columns = [norm(col) for col in df.columns]
    dados = [(str(r['CODIGO']).upper(), str(r['NOME']).upper(), str(r['TURMA']).upper(), 'ATIVO') for _, r in df.iterrows()]
    conn = conectar_bd()
    try:
        cur = conn.cursor()
        execute_values(cur, "INSERT INTO alunos_v2 (codigo, nome, turma, status) VALUES %s ON CONFLICT (codigo) DO UPDATE SET nome=EXCLUDED.nome, turma=EXCLUDED.turma", dados)
        conn.commit(); carregar_alunos.clear()
        return True
    finally: liberar_conn(conn)

def registrar_presenca(cod, data, h_limite):
    agora = obter_hora_atual(); h_at = agora.strftime("%H:%M:%S"); status = "PRESENTE" if agora.time() <= h_limite else "ATRASO"
    conn = conectar_bd()
    try:
        cur = conn.cursor()
        cur.execute("SELECT nome, email_responsavel FROM alunos_v2 WHERE codigo = %s", (cod,))
        res = cur.fetchone()
        if not res: return "erro_cod"
        cur.execute("DELETE FROM registros_v2 WHERE codigo_aluno=%s AND data=%s AND tipo_registro='FALTA'", (cod, data))
        cur.execute("INSERT INTO registros_v2 (codigo_aluno, data, hora_entrada, status_entrada, tipo_registro) VALUES (%s, %s, %s, %s, 'PRESENCA') ON CONFLICT DO NOTHING", (cod, data, h_at, status))
        if res[1]: disparar_email_background(res[1], res[0], f"ENTRADA|{status}", h_at, data)
        conn.commit()
        contar_presencas_hoje.clear()
        carregar_faltas.clear()
        return res[0]
    except Exception: return False
    finally: liberar_conn(conn)

def registrar_saida(cod, motivo, pais, data, h_saida, h_limite_saida):
    conn = conectar_bd()
    try:
        cur = conn.cursor(); cur.execute("SELECT nome, email_responsavel FROM alunos_v2 WHERE codigo = %s", (cod,))
        res = cur.fetchone()
        if not res: return False
        cur.execute("UPDATE registros_v2 SET hora_saida=%s, motivo_saida=%s, pais_informados=%s WHERE codigo_aluno=%s AND data=%s AND tipo_registro='PRESENCA'", (h_saida, motivo, pais, cod, data))
        if cur.rowcount > 0:
            if res[1]: 
                h_s_obj = datetime.strptime(h_saida, "%H:%M:%S").time()
                evento_email = "SAÍDA ANTECIPADA" if h_s_obj < h_limite_saida else "SAÍDA REGULAR"
                disparar_email_background(res[1], res[0], evento_email, h_saida, data)
            conn.commit()
            contar_presencas_hoje.clear()
            carregar_faltas.clear()
            return res[0]
        return False
    except Exception: return False
    finally: liberar_conn(conn)

def importar_csv_desempenho(file, ano, periodo, area, turma):
    conteudo_bytes = file.read()
    try: conteudo_str = conteudo_bytes.decode('utf-8-sig')
    except: conteudo_str = conteudo_bytes.decode('latin-1')
    temp_df = pd.read_csv(io.StringIO(conteudo_str), sep=';')
    temp_df.columns = [str(c).strip() for c in temp_df.columns]
    
    col_qs = [c for c in temp_df.columns if re.search(r'^Q\s*\d+\s*Options', c, re.IGNORECASE)]
    idx_not = next((i for i, c in enumerate(temp_df.columns) if 'Not attempted' in c), -1)
    idx_f = temp_df.columns.get_loc(col_qs[0])
    discs = [str(c).strip().upper() for c in temp_df.columns[idx_not+1:idx_f] if 'AV' not in str(c).upper()] if idx_not != -1 else [area.upper()]
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
        if not n or n.lower() == 'nan': continue
        for i in range(len(col_qs)):
            d_i = min(i // q_p_d, len(discs)-1)
            rb = options_matrix[r_idx, i].strip()
            g = keys_matrix[r_idx, i].strip().upper()
            
            r = 'BRANCO' if not rb else (rb.upper() if len(rb)==1 else 'DUPLA')
            acerto = 1 if r == g and r != 'BRANCO' else 0
            
            dados_l.append((str(ano), periodo, area, turma, n, discs[d_i], i+1, r, g, acerto))
            
    conn = conectar_bd()
    try:
        cur = conn.cursor()
        execute_values(cur, "INSERT INTO avaliacoes_avs (ano, periodo, area, turma, nome, disciplina, questao, resposta, gabarito, acerto) VALUES %s ON CONFLICT (ano, periodo, area, turma, nome, disciplina, questao) DO UPDATE SET resposta=EXCLUDED.resposta, acerto=EXCLUDED.acerto", dados_l)
        conn.commit()
        obter_dados_acad_filtrados.clear()
        return True, f"{len(dados_l)} registros salvos."
    except Exception as e: return False, str(e)
    finally: liberar_conn(conn)

def gerar_pdf_boletim(aluno, turma, nota_g, df_b, df_historico_aluno=None):
    if not FPDF: return None
    pdf = FPDF(); pdf.add_page(); pdf.set_fill_color(10, 31, 53); pdf.rect(0, 0, 210, 35, 'F')
    pdf.set_font("Arial", "B", 18); pdf.set_text_color(255,255,255); pdf.cell(0, 15, "BOLETIM DE DESEMPENHO", 0, 1, "C")
    pdf.ln(20); pdf.set_text_color(0,0,0); pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, f"ESTUDANTE: {aluno} ({turma})", 0, 1); pdf.cell(0, 10, f"MÉDIA (Filtro): {nota_g:.2f}", 0, 1)
    pdf.set_font("Arial", "B", 8); pdf.cell(0, 6, "LEGENDA: VERDE = ACERTO | VERMELHO = ERRO | LARANJA = BRANCO | ROXO = DUPLA", 0, 1); pdf.ln(2)
    
    for p in sorted(df_b['periodo'].unique()):
        pdf.set_fill_color(230,230,230); pdf.set_font("Arial", "B", 12); pdf.cell(0, 10, f"  {p}", 0, 1, fill=True)
        for d in sorted(df_b[df_b['periodo']==p]['disciplina'].unique()):
            df_d = df_b[(df_b['periodo']==p) & (df_b['disciplina']==d)]
            pdf.set_font("Arial", "B", 11); pdf.cell(0, 8, f"{d} - Nota: {(df_d['acerto'].mean()*10):.2f}", 0, 1)
            x, y, col = 10, pdf.get_y(), 0
            for q in df_d.sort_values('questao').to_dict('records'):
                if y > 265: pdf.add_page(); y = 20
                c = (16,185,129) if q['acerto']==1 else ((245,158,11) if q['resposta']=='BRANCO' else ((139,92,246) if q['resposta']=='DUPLA' else (239,68,68)))
                pdf.set_fill_color(*c); pdf.rect(x+(col*22), y, 20, 12, 'F'); pdf.set_text_color(255,255,255); pdf.set_font("Arial","B",8)
                pdf.text(x+(col*22)+2, y+5, f"Q{q['questao']}"); pdf.text(x+(col*22)+2, y+10, f"R:{q['resposta']}")
                col += 1; 
                if col > 7: col, y = 0, y+15
            y = y+15 if col > 0 else y; pdf.set_y(y+5); pdf.set_text_color(0,0,0)

    if df_historico_aluno is not None and not df_historico_aluno.empty and MATPLOTLIB_AVAILABLE:
        progresso = df_historico_aluno.groupby(['periodo', 'disciplina']).agg(Acertos=('acerto', 'sum'), Total=('questao', 'count')).reset_index()
        progresso['Nota'] = (progresso['Acertos'] / progresso['Total']) * 10
        progresso_pivot = progresso.pivot(index='periodo', columns='disciplina', values='Nota')
        fig, ax = plt.subplots(figsize=(10, 6))
        for col in progresso_pivot.columns:
            abreviacao = DICIONARIO_ABREVIACAO.get(col, col[:4].upper())
            cor = DICIONARIO_CORES.get(abreviacao, DICIONARIO_CORES.get(col, "#000000"))
            ax.plot(progresso_pivot.index, progresso_pivot[col], marker='o', linewidth=5, markersize=12, label=col, color=cor)
            for x_val, y_val in zip(progresso_pivot.index, progresso_pivot[col]):
                if pd.notna(y_val): ax.text(x_val, y_val + 0.3, abreviacao, color=cor, fontsize=10, fontweight='bold', ha='center', va='bottom')
        ax.set_title("Evolucao Geral ao Longo do Ano", fontweight='bold', fontsize=18); ax.set_ylabel("Nota", fontweight='bold', fontsize=14); ax.set_xlabel("Periodo", fontweight='bold', fontsize=14); ax.set_ylim(0, 11) 
        ax.grid(True, linestyle='--', alpha=0.7); ax.legend(loc='center left', bbox_to_anchor=(1, 0.5), fontsize=12); plt.tight_layout()
        with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp: plt.savefig(tmp.name, format='png', dpi=300, bbox_inches='tight'); tmp_img_name = tmp.name
        plt.close(fig)
        pdf.add_page(); pdf.set_font("Arial", "B", 14); pdf.cell(0, 10, "EVOLUCAO AO LONGO DO ANO (HISTORICO COMPLETO)", 0, 1, "C"); pdf.ln(5); pdf.image(tmp_img_name, x=10, w=190)
        try: os.remove(tmp_img_name)
        except: pass
    out = pdf.output(dest='S')
    return out.encode('latin-1') if isinstance(out, str) else bytes(out)

def gerar_pdf_relatorio_critico(df_critico):
    if not FPDF: return None
    pdf = FPDF(); pdf.add_page(); pdf.set_fill_color(10, 31, 53); pdf.rect(0, 0, 210, 35, 'F')
    pdf.set_font("Arial", "B", 16); pdf.set_text_color(255, 255, 255); pdf.cell(0, 15, "QUESTOES CRITICAS (TOP 3 ERROS)", 0, 1, "C"); pdf.ln(20); pdf.set_text_color(0, 0, 0)
    for t in sorted(df_critico['turma'].unique()):
        pdf.set_fill_color(230, 230, 230); pdf.set_font("Arial", "B", 14); pdf.cell(0, 10, f" Turma: {t}", 0, 1, fill=True)
        df_t = df_critico[df_critico['turma'] == t]
        for p in sorted(df_t['periodo'].unique()):
            pdf.set_font("Arial", "B", 12); pdf.cell(0, 8, f"   Periodo: {p}", 0, 1)
            df_p = df_t[df_t['periodo'] == p]
            for d in sorted(df_p['disciplina'].unique()):
                pdf.set_font("Arial", "B", 11); pdf.cell(0, 6, f"      Disciplinas: {d}", 0, 1)
                df_d = df_p[df_p['disciplina'] == d]
                pdf.set_font("Arial", "", 10)
                for _, r in df_d.iterrows():
                    if pdf.get_y() > 270: pdf.add_page()
                    pdf.cell(15); pdf.cell(0, 5, f"- Questao {r['questao']}: {r['Taxa de Erro (%)']:.1f}% de erro", 0, 1)
                pdf.ln(2)
        pdf.ln(5)
    out = pdf.output(dest='S'); return out.encode('latin-1') if isinstance(out, str) else bytes(out)

def gerar_camera(label, btn_label, cam_id):
    components.html(f"""
    <div style="text-align:center; max-width:450px; margin: 0 auto; padding:15px; border-radius:15px; background:white; border: 2px solid #e2e8f0; box-shadow: 0 4px 10px rgba(0,0,0,0.05);">
        <div style="display:flex; gap:10px; margin-bottom:15px;">
            <button id="start-{cam_id}" style="flex:1; padding:12px; background:#10b981; color:white; border:none; border-radius:8px; font-weight:900; font-size:1rem; cursor:pointer;">🟢 LIGAR CÂMARA</button>
            <button id="stop-{cam_id}" style="flex:1; padding:12px; background:#ef4444; color:white; border:none; border-radius:8px; font-weight:900; font-size:1rem; cursor:pointer;">🔴 DESLIGAR</button>
        </div>
        <div id="reader-{cam_id}" style="width:100%; display:none; border-radius:10px; overflow:hidden; border: 3px solid #0a1f35; background: #000;"></div>
    </div>
    <script src="https://unpkg.com/html5-qrcode"></script>
    <script>
        let scanner_{cam_id};
        document.getElementById("start-{cam_id}").onclick = () => {{
            document.getElementById("reader-{cam_id}").style.display = "block";
            if(!scanner_{cam_id}) scanner_{cam_id} = new Html5Qrcode("reader-{cam_id}");
            scanner_{cam_id}.start({{ facingMode: "environment" }}, {{ fps: 15, qrbox: 250 }}, (txt) => {{
                
                const input = window.parent.document.querySelectorAll('input[aria-label*="{label}"]')[0];
                if(input) {{ 
                    // Truque avancado para forcar o Streamlit (React) a reconhecer a digitacao injetada
                    let nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
                    nativeInputValueSetter.call(input, txt);
                    input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    
                    // Aguarda o Streamlit registrar a variavel na memoria (800ms) e entao clica no botao sozinho
                    setTimeout(() => {{ 
                        window.parent.document.querySelectorAll('button').forEach(b => {{ 
                            if(b.innerText.includes("{btn_label}")) b.click(); 
                        }}); 
                    }}, 800);
                }}
                scanner_{cam_id}.stop().then(() => {{ document.getElementById("reader-{cam_id}").style.display = "none"; }});
                
            }}).catch(err => console.error(err));
        }};
        document.getElementById("stop-{cam_id}").onclick = () => {{
            if(scanner_{cam_id}) {{ scanner_{cam_id}.stop().then(() => {{ document.getElementById("reader-{cam_id}").style.display = "none"; }}).catch(err => console.error(err)); }}
        }};
    </script>
    """, height=450)

# ------------------------------------------------------------
# 7. MÓDULO PÚBLICO: PESQUISA DE SATISFAÇÃO (OCULTO VIA URL)
# ------------------------------------------------------------
if st.query_params.get("modo") == "pesquisa":
    st.markdown("<div class='login-card' style='max-width: 750px;'>", unsafe_allow_html=True)
    renderizar_logo_central()
    
    if st.session_state.pesquisa_enviada:
        st.markdown("""
        <div style='text-align: center; padding: 40px 10px;'>
            <h1 style='font-size: 5rem; margin-bottom: 0;'>🎉</h1>
            <h2 style='color: #10b981; font-weight: 900;'>Avaliação Recebida!</h2>
            <p style='font-size: 1.4rem; color: #64748b; margin-top: 15px;'>
                Muito obrigado por contribuir com a melhoria do <b>Centro Educa Mais Jansen Veloso</b>.<br>
                Sua opinião faz toda a diferença!
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        if st.button("Enviar nova avaliação", use_container_width=True):
            st.session_state.pesquisa_enviada = False
            st.rerun()
            
        st.markdown("</div>", unsafe_allow_html=True)
        st.stop()
        
    st.markdown("<h2 style='color: var(--primary); text-align: center; margin-bottom: 5px;'>Pesquisa de Satisfação Escolar</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #64748b; font-weight: bold; margin-bottom: 25px;'>Sua opinião é 100% anônima e essencial para melhorarmos nossa escola.</p>", unsafe_allow_html=True)

    cat = st.selectbox("1. Identifique seu perfil para iniciarmos:", ["", "Estudante", "Pais/Responsável", "Professor", "Servidor"])

    if cat:
        with st.form("form_sat", clear_on_submit=True):
            turma_sel = ""
            if cat == "Estudante":
                df_al = carregar_alunos()
                lista_t = sorted(df_al['turma'].unique()) if not df_al.empty else []
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
                q4 = radio("Como você avalia a facilidade para solicitar certificados e declarações?", opcoes, index=None)
                q5 = st.radio("Como você avalia a comunicação da escola sobre notas e faltas do estudante?", opcoes, index=None)
            elif cat == "Professor":
                q4 = st.radio("Como você avalia os recursos pedagógicos e o suporte da gestão escolar?", opcoes, index=None)
                q5 = st.radio("Como você avalia o engajamento e a disciplina geral dos estudantes?", opcoes, index=None)
            else: # Servidor
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
                    try:
                        cur = conn.cursor()
                        cur.execute("INSERT INTO satisfacao_v1 (data_hora, categoria, turma, q1, q2, q3, q4, q5, sugestao) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                                    (obter_hora_atual(), cat, turma_sel, int(q1[0]), int(q2[0]), int(q3[0]), int(q4[0]), int(q5[0]), sugestao))
                        conn.commit()
                        st.session_state.pesquisa_enviada = True
                        st.rerun()
                    except: st.error("Erro de conexão ao salvar avaliação. Tente novamente.")
                    finally: liberar_conn(conn)
    st.markdown("</div>", unsafe_allow_html=True)
    st.stop() 


# ------------------------------------------------------------
# 8. AUTH E DASHBOARD DO DIRETOR
# ------------------------------------------------------------
auth_cookie = cookies.get("auth_token")

if not auth_cookie:
    st.markdown('<div class="login-card">', unsafe_allow_html=True)
    if os.path.exists("logo.png"): st.image("logo.png", width=120)
    st.markdown('<div class="login-title">LOGIN ESCOLAR</div>', unsafe_allow_html=True)
    passw = st.text_input("SENHA", type="password")
    if st.button("ENTRAR", use_container_width=True):
        if passw in [SENHA_ADMIN, SENHA_OPERADOR]:
            cookies["auth_token"] = base64.b64encode(json.dumps({"admin": passw==SENHA_ADMIN}).encode()).decode(); cookies.save(); st.rerun()
        else: st.error("Incorreta")
    st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

try:
    user = json.loads(base64.b64decode(auth_cookie).decode())
    eh_admin = user.get('admin', user.get('eh_admin', False)) 
except Exception:
    cookies["auth_token"] = ""; cookies.save(); st.rerun()

df_alunos = carregar_alunos()

c_out1, c_out2 = st.columns([10, 1])
with c_out2:
    if st.button("SAIR"): cookies["auth_token"] = ""; cookies.save(); st.rerun()

renderizar_logo_central()
st.markdown('<p class="main-title">PAINEL INTEGRADO</p>', unsafe_allow_html=True)
st.markdown(f'<p class="sub-title">CEMA Jansen Veloso • {data_formatada_ptbr()}</p>', unsafe_allow_html=True)

# --- PROCESSAMENTO DE DADOS (GLOBAL) ---
hoje = obter_hora_atual().strftime("%Y-%m-%d")
pres_hoje = contar_presencas_hoje(hoje)

total_alunos = len(df_alunos)
media_geral_freq = f"{(pres_hoje / total_alunos) * 100:.1f}%" if total_alunos > 0 else "0%"

# --- LINHA 1: CARTÕES DE FREQUÊNCIA ---
st.markdown(f'''
<div class="metrics-container">
    <div class="metric-card m-total"><span class="m-val">{total_alunos}</span><span class="m-lab">Total Alunos</span></div>
    <div class="metric-card m-presente"><span class="m-val">{pres_hoje}</span><span class="m-lab">Presentes Hoje</span></div>
    <div class="metric-card m-falta"><span class="m-val">{total_alunos-pres_hoje}</span><span class="m-lab">Faltas Hoje</span></div>
    <div class="metric-card m-atraso"><span class="m-val">{media_geral_freq}</span><span class="m-lab">Frequência Diária</span></div>
</div>
''', unsafe_allow_html=True)

# --- FILTROS GLOBAIS (ANO, PERÍODO, ÁREA E TURMA) ---
st.markdown("### 🎛️ Filtros Globais (Acadêmico & Pesquisa)")
c_ano, cf1, cf2, cf3 = st.columns([1, 2, 2, 2])

anos_disponiveis = [str(y) for y in range(2024, 2035)]
ano_atual = str(obter_hora_atual().year)
if ano_atual not in anos_disponiveis: anos_disponiveis.append(ano_atual)

ano_f = c_ano.selectbox("Ano Letivo", anos_disponiveis, index=anos_disponiveis.index(ano_atual), key="filtro_ano_da")
pf = cf1.selectbox("Período Acadêmico", ["Todos", "1º Período", "2º Período", "3º Período", "4º Período"], key="filtro_periodo_da")
af = cf2.selectbox("Área Acadêmica", ["Todas", "LÍNGUA PORTUGUESA", "MATEMÁTICA", "LINGUAGENS", "HUMANAS", "NATUREZA"], key="filtro_area_da")
tf = cf3.selectbox("Turma (Filtra Acadêmico e Satisfação Estudante)", ["Todas"] + sorted(df_alunos['turma'].unique() if not df_alunos.empty else []), key="filtro_turma_da")

# Carregamento Otimizado com SQL + Spinner (UX)
with st.spinner("Sincronizando dados..."):
    dff = obter_dados_acad_filtrados(ano_f, pf, af, tf)

media_geral_acad = f"{dff['acerto'].mean() * 10:.1f}" if not dff.empty else "--"

# Cálculos de Satisfação via Cache e SQL
sat_est_str, sat_pais_str, sat_eq_str = calcular_satisfacao_global_cached(ano_f, tf)

# --- LINHA 2: CARTÕES DE DESEMPENHO E SATISFAÇÃO ---
st.markdown(f'''
<div class="metrics-container" style="margin-top: 15px;">
    <div class="metric-card m-acad"><span class="m-val">{media_geral_acad}</span><span class="m-lab">Média Acad. (Filtrada)</span></div>
    <div class="metric-card m-satest"><span class="m-val">{sat_est_str}</span><span class="m-lab">Satisfação Estudante</span></div>
    <div class="metric-card m-satpais"><span class="m-val">{sat_pais_str}</span><span class="m-lab">Satisfação Pais</span></div>
    <div class="metric-card m-sateq"><span class="m-val">{sat_eq_str}</span><span class="m-lab">Satisfação Equipe</span></div>
</div>
''', unsafe_allow_html=True)


abas_do_sistema = ["📝 Registro", "📊 Gestão Frequência", "🚨 Alertas", "📈 Histórico", "📑 Desempenho Acadêmico", "💬 Satisfação Pública"]
if eh_admin: abas_do_sistema.append("⚙️ Manutenção do Sistema")
tabs = st.tabs(abas_do_sistema)
indice_aba = 0

with tabs[indice_aba]:
    st.markdown('<div class="card-panel">', unsafe_allow_html=True)
    st.markdown("#### ⚙️ Configuração do Turno e Dia Letivo")
    st.write("Ajuste os horários e confirme se a data de hoje é um dia letivo para liberar o registro dos estudantes.")
    
    c_cfg1, c_cfg2 = st.columns(2)
    with c_cfg1: h_lim_e = st.time_input("🟢 Horário Limite de Entrada", datetime.strptime("07:30", "%H:%M").time())
    with c_cfg2: h_lim_s = st.time_input("🔴 Horário de Término (Saída)", datetime.strptime("17:00", "%H:%M").time())
    
    with st.form("form_controle_dias"):
        st.markdown("📅 **Ativação do Calendário:**")
        col_d1, col_d2 = st.columns(2)
        with col_d1: data_selecionada = st.date_input("Selecione a Data no Calendário", value=obter_hora_atual().date())
        with col_d2: st.write(""); st.write(""); is_ativo = st.checkbox("Ativar como Dia Letivo?", value=True)
        btn_salvar_dia = st.form_submit_button("💾 Salvar Configuração do Dia")
        
    if btn_salvar_dia:
        conn = conectar_bd()
        try:
            cur = conn.cursor()
            cur.execute("INSERT INTO calendario_letivo (data, dia_letivo) VALUES (%s, %s) ON CONFLICT (data) DO UPDATE SET dia_letivo = EXCLUDED.dia_letivo", (data_selecionada, is_ativo))
            conn.commit()
            verificar_dia_letivo.clear() 
            st.success(f"Pronto! A data {data_selecionada.strftime('%d/%m/%Y')} foi configurada no calendário escolar.")
        except Exception as e: st.error(f"Erro ao salvar: {e}")
        finally: liberar_conn(conn)

    st.markdown("---")
    
    t_en, t_sa, t_jf = st.tabs(["✅ ENTRADA", "🚪 REGISTRO DE SAÍDA", "📝 JUSTIFICAR FALTAS"])
    with t_en:
        if not verificar_dia_letivo(hoje): st.error("⚠️ REGISTRO BLOQUEADO: A data de hoje não foi ativada como Dia Letivo no painel logo acima.")
        else:
            gerar_camera("Entrada", "REGISTRAR ENTRADA", "c_in")
            with st.form("f_en", clear_on_submit=True):
                cod_en = st.text_input("Código Aluno (Entrada)")
                if st.form_submit_button("REGISTRAR ENTRADA") and cod_en:
                    res = registrar_presenca(cod_en.upper(), hoje, h_lim_e)
                    if res == "erro_cod": st.error("Código não encontrado.")
                    elif res: st.success(f"Bem-vindo, {res}!")
                
    with t_sa:
        if not verificar_dia_letivo(hoje): st.error("⚠️ REGISTRO BLOQUEADO: A data de hoje não foi ativada como Dia Letivo no painel logo acima.")
        else:
            gerar_camera("Saída", "CONFIRMAR SAÍDA", "c_out")
            with st.form("f_sa", clear_on_submit=True):
                cod_sa = st.text_input("Código Aluno (Saída)")
                hora_saida_manual = st.time_input("Horário Exato da Saída", obter_hora_atual().time())
                mot = st.selectbox("Motivo", ["Mal-estar", "Consulta Médica", "Liberação da Direção", "Término do Turno", "Outros"])
                if st.form_submit_button("CONFIRMAR SAÍDA") and cod_sa:
                    res = registrar_saida(cod_sa.upper(), mot, True, hoje, hora_saida_manual.strftime("%H:%M:%S"), h_lim_s)
                    if res: st.success(f"Saída de {res} registrada às {hora_saida_manual.strftime('%H:%M')}!"); st.rerun()
                    else: st.error("Erro: Aluno sem registro de entrada hoje.")
                
    with t_jf:
        st.subheader("Justificar Faltas de Estudantes")
        d_just = st.date_input("Data da Falta", obter_hora_atual().date())
        df_faltas = carregar_faltas(d_just.strftime("%Y-%m-%d"))
        
        if not df_faltas.empty:
            with st.form("form_justificar"):
                al_falta_sel = st.selectbox("Selecione o Estudante Faltoso", [""] + [f"{r['codigo_aluno']} - {r['nome']} ({r['turma']})" for _, r in df_faltas.iterrows()])
                motivo_falta = st.selectbox("Justificativa", ["Atestado Médico", "Problemas Familiares", "Problemas de Transporte", "Outros"])
                if st.form_
