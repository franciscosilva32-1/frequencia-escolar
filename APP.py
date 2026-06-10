import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import psycopg2
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
# 2. FUNÇÕES DE SUPORTE (TEMPO, E-MAIL E CORES)
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
    # Disciplinas
    "LP": "#2563eb", "MAT": "#dc2626", "MTM": "#dc2626", "BIO": "#16a34a",
    "ART": "#d97706", "EDF": "#7c3aed", "ESP": "#db2777", "FIL": "#4f46e5",
    "FIS": "#0d9488", "GGF": "#ea580c", "HST": "#9333ea", "ING": "#0891b2",
    "QUI": "#65a30d", "SOC": "#ca8a04",
    # Áreas
    "LÍNGUA PORTUGUESA": "#2563eb", "MATEMÁTICA": "#dc2626",
    "LINGUAGENS": "#d97706", "HUMANAS": "#7c3aed", "NATUREZA": "#16a34a"
}

def disparar_email_background(email_destino, nome_aluno, evento, horario, data):
    try: data_f = datetime.strptime(data, "%Y-%m-%d").strftime("%d/%m/%Y")
    except: data_f = data
    
    if evento.startswith("ENTRADA"):
        assunto = f"🏫 Aviso de Entrada - Jansen Veloso"
        if "ATRASO" in evento:
            texto = f"Olá, família!\n\nInformamos que o estudante {nome_aluno} registrou ENTRADA COM ATRASO na escola hoje ({data_f}) às {horario}.\n\nAtenciosamente,\nEquipe Jansen Veloso."
        else:
            texto = f"Olá, família!\n\nInformamos que o estudante {nome_aluno} registrou ENTRADA na escola hoje ({data_f}) às {horario} (Dentro do horário regular).\n\nAtenciosamente,\nEquipe Jansen Veloso."
            
    elif evento == "SAÍDA REGULAR":
        assunto = f"🏫 Aviso de Saída - Jansen Veloso"
        texto = f"Olá, família!\n\nInformamos que o estudante {nome_aluno} registrou SAÍDA REGULAR da escola hoje ({data_f}) às {horario}.\n\nAtenciosamente,\nEquipe Jansen Veloso."
        
    else: # SAÍDA ANTECIPADA
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

@st.cache_data
def carregar_logo_base64():
    if os.path.exists("logo.png"):
        try:
            with open("logo.png", "rb") as image_file:
                return base64.b64encode(image_file.read()).decode()
        except: return None
    return None

def renderizar_logo_central():
    encoded_string = carregar_logo_base64()
    if encoded_string:
        st.markdown(f'<div style="display: flex; justify-content: center; margin-bottom: 10px;"><img src="data:image/png;base64,{encoded_string}" width="170"></div>', unsafe_allow_html=True)

# ------------------------------------------------------------
# 3. CSS (VISUAL PREMIUM E CENTRALIZADO)
# ------------------------------------------------------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap');
    :root { --primary: #0a1f35; --accent: #ff7b00; --success: #10b981; --danger: #ef4444; --bg-color: #f8fafc; }
    .stApp { background: var(--bg-color); }
    #MainMenu, footer, header {visibility: hidden;}
    
    html, body, [class*="css"], p, span, label, div { font-size: 1.15rem !important; }

    [data-testid="stRadio"] div[role="radiogroup"] > label {
        font-size: 1.3rem !important; padding: 16px 15px !important; margin-bottom: 12px !important;
        background-color: #ffffff; border: 2px solid #cbd5e1; border-radius: 12px;
        box-shadow: 0 3px 6px rgba(0,0,0,0.04); cursor: pointer; transition: all 0.2s ease;
    }
    [data-testid="stRadio"] div[role="radiogroup"] > label:hover { border-color: var(--accent); transform: translateY(-2px); }

    .main-title { font-family: 'Inter', sans-serif; font-weight: 900; font-size: clamp(3.5rem, 8vw, 4.8rem); color: var(--primary); text-align: center; margin:0; text-transform: uppercase; letter-spacing: -2px;}
    .sub-title { font-family: 'Inter', sans-serif; font-size: 1.6rem; color: #64748b; text-align: center; margin-bottom: 2rem; font-weight: 700;}
    
    .metrics-container { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1.5rem; margin-bottom: 2rem; }
    @media (max-width: 1200px) { .metrics-container { grid-template-columns: repeat(2, 1fr); } }
    @media (max-width: 800px) { .metrics-container { grid-template-columns: 1fr; } }
    
    .metric-card { background: white; padding: 2.5rem 1.5rem; border-radius: 20px; box-shadow: 0 8px 25px rgba(0,0,0,0.06); text-align: center; position: relative; overflow: hidden; border: 2px solid #e2e8f0; transition: transform 0.2s ease;}
    .metric-card:hover { transform: translateY(-5px); }
    .metric-card::before { content: ''; position: absolute; top: 0; left: 0; right: 0; height: 10px; }
    
    .m-total::before { background: #0ea5e9; } 
    .m-presente::before { background: var(--success); } 
    .m-falta::before { background: var(--danger); } 
    .m-atraso::before { background: #f59e0b; } 
    .m-acad::before { background: #8b5cf6; }
    .m-satest::before { background: #10b981; }
    .m-satpais::before { background: #f59e0b; }
    .m-sateq::before { background: #3b82f6; }
    
    .m-val { font-size: 4rem; font-weight: 900; color: #0f172a; display: block; line-height: 1.1; letter-spacing: -2px; text-shadow: 2px 2px 4px rgba(0,0,0,0.05); }
    .m-lab { font-size: 1.2rem; font-weight: 900; color: #475569; text-transform: uppercase; letter-spacing: 1px; margin-top: 1rem; display: block; }
    
    .stTabs [data-baseweb="tab-list"] { gap: 10px; padding-bottom: 0px; flex-wrap: wrap; }
    .stTabs [data-baseweb="tab"] { background-color: #f1f5f9 !important; border: 3px solid #cbd5e1 !important; border-bottom: none !important; border-radius: 18px 18px 0 0 !important; padding: 15px 25px !important; font-size: 1.5rem !important; font-weight: 900 !important; color: #64748b !important; transition: all 0.3s ease !important; }
    .stTabs [data-baseweb="tab"]:hover { background-color: #e2e8f0 !important; color: var(--primary) !important; }
    .stTabs [aria-selected="true"] { background-color: var(--primary) !important; color: #ffffff !important; border: 5px solid var(--accent) !important; border-bottom: none !important; transform: translateY(-4px); box-shadow: 0 -8px 25px rgba(255, 123, 0, 0.35) !important; }
    
    .card-panel { background: white; border-radius: 20px; padding: 2.2rem; margin-bottom: 1.5rem; box-shadow: 0 8px 20px rgba(0,0,0,0.03); border: 2px solid #e2e8f0; }
    
    div[data-baseweb="input"] { border: 2px solid #cbd5e1 !important; border-radius: 12px !important; background-color: #ffffff !important; }
    div[data-baseweb="input"] input { color: #000000 !important; -webkit-text-fill-color: #000000 !important; font-weight: 900 !important; font-size: 1.5rem !important; padding: 1rem 1.2rem !important; }
    div[data-baseweb="input"]:focus-within { border-color: var(--accent) !important; box-shadow: 0 0 0 4px rgba(255, 123, 0, 0.2) !important; }
    
    [data-baseweb="select"] > div { background-color: #ffffff !important; border: 2.5px solid #0a1f35 !important; border-radius: 12px !important; height: 55px !important; }
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
# 4. BANCO DE DADOS E DICIONÁRIO
# ------------------------------------------------------------
DATABASE_URL = st.secrets.get("DATABASE_URL")
SENHA_OPERADOR = st.secrets.get("SENHA_OPERADOR", "admin123")
SENHA_ADMIN = st.secrets.get("SENHA_ADMIN", "admin123")

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

def conectar_bd(): return psycopg2.connect(DATABASE_URL)

def inicializar_tabelas():
    try:
        conn = conectar_bd(); cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS alunos_v2 (codigo TEXT PRIMARY KEY, nome TEXT, turma TEXT, status TEXT DEFAULT 'ATIVO', email_responsavel TEXT)")
        cur.execute("CREATE TABLE IF NOT EXISTS registros_v2 (id SERIAL PRIMARY KEY, codigo_aluno TEXT REFERENCES alunos_v2(codigo), data DATE, hora_entrada TIME, status_entrada TEXT, hora_saida TIME, motivo_saida TEXT, pais_informados BOOLEAN, tipo_registro TEXT, UNIQUE(codigo_aluno, data, tipo_registro))")
        
        # TABELA AVALIAÇÕES COM NOVA COLUNA 'ANO'
        cur.execute("CREATE TABLE IF NOT EXISTS avaliacoes_avs (id SERIAL PRIMARY KEY, ano TEXT, periodo TEXT, area TEXT, turma TEXT, nome TEXT, disciplina TEXT, questao INTEGER, resposta TEXT, gabarito TEXT, acerto INTEGER, UNIQUE(ano, periodo, area, turma, nome, disciplina, questao))")
        
        # Script Seguro para atualizar banco antigo (Adiciona coluna ano e refaz Unique)
        try:
            cur.execute("ALTER TABLE avaliacoes_avs ADD COLUMN ano TEXT DEFAULT '2026'")
            conn.commit()
        except Exception:
            conn.rollback()

        try:
            cur.execute("SELECT constraint_name FROM information_schema.table_constraints WHERE table_name='avaliacoes_avs' AND constraint_type='UNIQUE'")
            constraints = cur.fetchall()
            for c in constraints: cur.execute(f"ALTER TABLE avaliacoes_avs DROP CONSTRAINT {c[0]}")
            cur.execute("ALTER TABLE avaliacoes_avs ADD UNIQUE (ano, periodo, area, turma, nome, disciplina, questao)")
            conn.commit()
        except Exception:
            conn.rollback()

        cur.execute("""CREATE TABLE IF NOT EXISTS satisfacao_v1 (
            id SERIAL PRIMARY KEY, data_hora TIMESTAMP, categoria TEXT, turma TEXT, 
            q1 INTEGER, q2 INTEGER, q3 INTEGER, q4 INTEGER, q5 INTEGER, sugestao TEXT
        )""")
        cur.execute("CREATE TABLE IF NOT EXISTS calendario_letivo (data DATE PRIMARY KEY, dia_letivo BOOLEAN DEFAULT TRUE)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_reg_data ON registros_v2(data)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_avs_geral ON avaliacoes_avs(ano, periodo, area, turma)")
        conn.commit(); conn.close()
    except: pass

inicializar_tabelas()

@st.cache_data(ttl=300)
def verificar_dia_letivo(data_atual):
    try:
        conn = conectar_bd()
        cur = conn.cursor()
        cur.execute("SELECT dia_letivo FROM calendario_letivo WHERE data = %s", (data_atual,))
        res = cur.fetchone()
        conn.close()
        if res: return res[0]
        return False
    except: return False

# ------------------------------------------------------------
# 5. LÓGICA DE NEGÓCIO E CACHES OTIMIZADOS
# ------------------------------------------------------------
@st.cache_data(ttl=60)
def contar_presencas_hoje(data_str):
    try:
        conn = conectar_bd(); cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM registros_v2 WHERE data=%s AND tipo_registro='PRESENCA'", (data_str,))
        count = cur.fetchone()[0]
        conn.close()
        return count
    except: return 0

@st.cache_data(ttl=60)
def carregar_faltas(data_str):
    try:
        conn = conectar_bd()
        df = pd.read_sql("SELECT r.codigo_aluno, a.nome, a.turma, r.motivo_saida FROM registros_v2 r JOIN alunos_v2 a ON r.codigo_aluno = a.codigo WHERE r.data = %s AND r.tipo_registro = 'FALTA'", conn, params=[data_str])
        conn.close()
        return df
    except: return pd.DataFrame()

@st.cache_data(ttl=300)
def carregar_alunos():
    try:
        conn = conectar_bd(); df = pd.read_sql("SELECT codigo, nome, turma, status, email_responsavel FROM alunos_v2 ORDER BY turma, nome", conn); conn.close(); return df
    except: return pd.DataFrame(columns=['codigo','nome','turma','status','email_responsavel'])

@st.cache_data(ttl=300)
def carregar_avaliacoes():
    try:
        conn = conectar_bd(); df = pd.read_sql("SELECT * FROM avaliacoes_avs", conn); conn.close()
        if not df.empty and 'disciplina' in df.columns:
            df['disciplina'] = df['disciplina'].replace({'LÍNGUA PORTUGESA': 'LÍNGUA PORTUGUESA', 'SOCIOLGIA': 'SOCIOLOGIA'})
        return df
    except: return pd.DataFrame()

@st.cache_data(ttl=300)
def carregar_satisfacao():
    try:
        conn = conectar_bd()
        df = pd.read_sql("SELECT * FROM satisfacao_v1", conn)
        conn.close()
        if not df.empty:
            df['media_resposta'] = df[['q1','q2','q3','q4','q5']].mean(axis=1)
        return df
    except: return pd.DataFrame()

# 🚀 MÓDULO DE CACHE OTIMIZADO (AGORA INCLUI ANO)
@st.cache_data(ttl=300)
def obter_dados_acad_filtrados(ano, p, a, t):
    df = carregar_avaliacoes()
    if not df.empty and 'ano' in df.columns: df = df[df.ano == str(ano)]
    if p != "Todos": df = df[df.periodo==p]
    if a != "Todas": df = df[df.area==a]
    if t != "Todas": df = df[df.turma==t]
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
    erros_n = dff[dff.resposta.isin(['BRANCO','DUPLA'])].nome.unique()
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
def calcular_satisfacao_global_cached(ano, tf):
    df_sat = carregar_satisfacao()
    sat_est_str, sat_pais_str, sat_eq_str = "--", "--", "--"
    if not df_sat.empty:
        df_sat['ano_registro'] = pd.to_datetime(df_sat['data_hora']).dt.year
        df_sat = df_sat[df_sat['ano_registro'] == int(ano)]
        
        df_sat_est = df_sat[df_sat['categoria'] == 'Estudante']
        if tf
