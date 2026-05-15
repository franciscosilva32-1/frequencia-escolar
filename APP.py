import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import execute_batch, execute_values
import os
import io
import base64
import json
import unicodedata
import streamlit.components.v1 as components
from streamlit_cookies_manager import CookieManager
import tempfile

# BIBLIOTECAS PARA O ENVIO DE E-MAIL E TEMPO
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import threading
import time

# BIBLIOTECAS PARA O DESEMPENHO ACADÊMICO E GRÁFICOS
import re
import matplotlib.pyplot as plt
import matplotlib.style as mplstyle
from matplotlib.ticker import MaxNLocator
import plotly.express as px
import plotly.graph_objects as go
mplstyle.use('seaborn-v0_8-whitegrid')

try:
    from fpdf import FPDF
except ImportError:
    FPDF = None

# ------------------------------------------------------------
# 1. CONFIGURAÇÃO GERAL E CHAVES DE E-MAIL
# ------------------------------------------------------------
st.set_page_config(page_title="Centro Educa Mais Jansen Veloso", page_icon="🏫", layout="wide", initial_sidebar_state="collapsed")

if 'fila_offline' not in st.session_state: st.session_state.fila_offline = []
if 'boletim_aluno_avs' not in st.session_state: st.session_state.boletim_aluno_avs = None

cookies = CookieManager()
if not cookies.ready(): st.stop()

# =========================================================
# ⌚ FUNÇÕES DE TEMPO E E-MAIL
# =========================================================
def obter_hora_atual(): return datetime.utcnow() - timedelta(hours=3)
def data_formatada_ptbr():
    dt = obter_hora_atual()
    meses = ["", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
    return f"{dt.day:02d} de {meses[dt.month]} de {dt.year}"

ATIVAR_EMAILS = True  
EMAIL_ESCOLA = "cejv.cema@gmail.com" 
SENHA_APP_ESCOLA = "jetkkkridsefalvd" 

def disparar_email_background(email_destino, nome_aluno, evento, horario, data):
    try: data_formatada = datetime.strptime(data, "%Y-%m-%d").strftime("%d/%m/%Y")
    except: data_formatada = data
    assunto = f"🏫 Aviso de {evento} - Centro Educa Mais Jansen Veloso"
    if evento == "ENTRADA": texto = f"Olá, família!\n\nInformamos que o estudante {nome_aluno} registrou sua ENTRADA na escola hoje ({data_formatada}) no horário exato de: {horario}.\n\nAtenciosamente,\nEquipe Jansen Veloso."
    else: texto = f"⚠️ ATENÇÃO, família!\n\nInformamos que o estudante {nome_aluno} registrou uma SAÍDA ANTECIPADA hoje ({data_formatada}) no horário exato de: {horario}.\n\nAtenciosamente,\nEquipe Jansen Veloso."
    msg = MIMEMultipart()
    msg['From'] = EMAIL_ESCOLA; msg['To'] = email_destino; msg['Subject'] = assunto
    msg.attach(MIMEText(texto, 'plain'))
    def enviar():
        if ATIVAR_EMAILS:
            try:
                server = smtplib.SMTP('smtp.gmail.com', 587); server.starttls(); server.login(EMAIL_ESCOLA, SENHA_APP_ESCOLA)
                server.send_message(msg); server.quit()
            except Exception as e: print(f"[ERRO] Falha ao enviar e-mail: {e}")
    threading.Thread(target=enviar).start()

# ------------------------------------------------------------
# 2. CSS PREMIUM (FILTROS DESTACADOS E TÍTULOS GIGANTES)
# ------------------------------------------------------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap');
    :root { --primary: #0a1f35; --accent: #ff7b00; --success: #10b981; --danger: #ef4444; --bg-color: #f8fafc; }
    .stApp { background: var(--bg-color); }
    #MainMenu, footer, header {visibility: hidden;}
    
    html, body, [class*="css"], p, span, label, div { font-size: 1.15rem !important; }

    .main-title { font-family: 'Inter', sans-serif; font-weight: 900; font-size: clamp(3.5rem, 8vw, 4.8rem); color: var(--primary); text-align: center; margin:0; text-transform: uppercase; letter-spacing: -2px;}
    .sub-title { font-family: 'Inter', sans-serif; font-size: 1.6rem; color: #64748b; text-align: center; margin-bottom: 2rem; font-weight: 700;}
    
    .metrics-container { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1.5rem; margin-bottom: 2.5rem; }
    @media (max-width: 800px) { .metrics-container { grid-template-columns: 1fr; } }
    .metric-card { background: white; padding: 2.2rem 1rem; border-radius: 16px; box-shadow: 0 4px 10px rgba(0,0,0,0.04); text-align: center; position: relative; overflow: hidden; border: 1px solid #e2e8f0; }
    .metric-card::before { content: ''; position: absolute; top: 0; left: 0; right: 0; height: 8px; }
    .m-total::before { background: #0ea5e9; } .m-presente::before { background: var(--success); } .m-falta::before { background: var(--danger); } .m-atraso::before { background: #f59e0b; } 
    .m-val { font-size: 3.8rem; font-weight: 900; color: #1e293b; display: block; line-height: 1.2; }
    .m-lab { font-size: 1.2rem; font-weight: 800; color: #64748b; text-transform: uppercase; letter-spacing: 1px; margin-top: 0.5rem; display: block; }
    
    .stTabs [data-baseweb="tab-list"] { gap: 10px; padding-bottom: 0px; flex-wrap: wrap; }
    .stTabs [data-baseweb="tab"] { background-color: #f1f5f9 !important; border: 3px solid #cbd5e1 !important; border-bottom: none !important; border-radius: 18px 18px 0 0 !important; padding: 15px 25px !important; font-size: 1.4rem !important; font-weight: 900 !important; color: #64748b !important; transition: all 0.3s ease !important; }
    .stTabs [data-baseweb="tab"]:hover { background-color: #e2e8f0 !important; color: var(--primary) !important; }
    .stTabs [aria-selected="true"] { background-color: var(--primary) !important; color: #ffffff !important; border: 5px solid var(--accent) !important; border-bottom: none !important; transform: translateY(-4px); box-shadow: 0 -8px 25px rgba(255, 123, 0, 0.35) !important; }
    
    .card-panel { background: white; border-radius: 20px; padding: 2.2rem; margin-bottom: 1.5rem; box-shadow: 0 8px 20px rgba(0,0,0,0.03); border: 2px solid #e2e8f0; }
    
    div[data-baseweb="input"] { border: 2px solid #cbd5e1 !important; border-radius: 12px !important; background-color: #ffffff !important; }
    div[data-baseweb="input"] input { color: #000000 !important; -webkit-text-fill-color: #000000 !important; font-weight: 900 !important; font-size: 1.5rem !important; padding: 1rem 1.2rem !important; }
    
    /* === FILTROS COM FONTE DESTACADA (ATENDENDO PEDIDO) === */
    [data-baseweb="select"] > div { 
        background-color: #ffffff !important; 
        border: 2.5px solid #0a1f35 !important; /* Borda mais escura para destacar */
        border-radius: 12px !important;
        height: 55px !important;
    }
    [data-baseweb="select"] span { 
        color: #000000 !important; 
        -webkit-text-fill-color: #000000 !important; 
        font-weight: 900 !important;
        font-size: 1.3rem !important; /* Fonte maior e mais grossa */
    }
    
    .stButton > button { border-radius: 12px !important; font-weight: 800 !important; font-size: 1.3rem !important; padding: 0.8rem 2rem !important; border: none !important; }
    [data-testid="stFormSubmitButton"] > button { background: linear-gradient(135deg, var(--primary), #1a4b82) !important; color: white !important; width: 100% !important; text-transform: uppercase !important; font-size: 1.4rem !important;}
    
    .top7-card { background: linear-gradient(135deg, #ffffff, #f8fafc); border-left: 12px solid var(--accent); padding: 3rem 1.5rem; border-radius: 20px; margin-bottom: 1.5rem; box-shadow: 0 10px 30px rgba(0,0,0,0.08); text-align: center;}
    .top7-medal { font-size: 3.8rem !important; font-weight: 900; color: var(--primary); margin-bottom: 0.5rem; }
    .top7-name { font-size: 4.5rem !important; font-weight: 900; color: var(--primary); letter-spacing: -2px; margin: 1.5rem 0; text-transform: uppercase;}
    .top7-name-hidden { font-size: 4.5rem !important; font-weight: 900; color: #94a3b8; filter: blur(12px); margin: 1.5rem 0;}
    .top7-details { font-size: 1.8rem !important; color: #64748b; font-weight: 800; background: #e2e8f0; display: inline-block; padding: 0.5rem 1.5rem; border-radius: 30px;}
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------
# 3. BANCO DE DADOS E OTIMIZAÇÃO (ÍNDICES)
# ------------------------------------------------------------
DATABASE_URL = st.secrets.get("DATABASE_URL", os.environ.get("DATABASE_URL"))
SENHA_OPERADOR = st.secrets.get("SENHA_OPERADOR", "admin123")
SENHA_ADMIN = st.secrets.get("SENHA_ADMIN", "admin123")

def conectar_bd():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True 
    return conn

def inicializar_tabelas():
    try:
        conn = conectar_bd(); cur = conn.cursor()
        cur.execute('''CREATE TABLE IF NOT EXISTS alunos_v2 (codigo TEXT PRIMARY KEY, nome TEXT, turma TEXT, status TEXT DEFAULT 'ATIVO', email_responsavel TEXT)''')
        cur.execute('''CREATE TABLE IF NOT EXISTS registros_v2 (id SERIAL PRIMARY KEY, codigo_aluno TEXT REFERENCES alunos_v2(codigo), data DATE, hora_entrada TIME, status_entrada TEXT, hora_saida TIME, motivo_saida TEXT, pais_informados BOOLEAN, tipo_registro TEXT, UNIQUE(codigo_aluno, data, tipo_registro))''')
        cur.execute('''CREATE TABLE IF NOT EXISTS avaliacoes_avs (id SERIAL PRIMARY KEY, periodo TEXT, area TEXT, turma TEXT, nome TEXT, disciplina TEXT, questao INTEGER, resposta TEXT, gabarito TEXT, acerto INTEGER, UNIQUE(periodo, area, turma, nome, disciplina, questao))''')
        cur.execute("CREATE INDEX IF NOT EXISTS idx_reg_data ON registros_v2(data)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_avs_busca ON avaliacoes_avs(periodo, area, turma)")
        conn.close()
    except: pass 

inicializar_tabelas()

# ------------------------------------------------------------
# 4. FUNÇÕES DE NEGÓCIO OTIMIZADAS (VETORIZAÇÃO)
# ------------------------------------------------------------
@st.cache_data(ttl=300)
def carregar_alunos():
    try:
        conn = conectar_bd()
        df = pd.read_sql_query("SELECT codigo, nome, turma, status, email_responsavel FROM alunos_v2 ORDER BY turma, nome", conn)
        conn.close(); return df
    except: return pd.DataFrame(columns=['codigo', 'nome', 'turma', 'status', 'email_responsavel'])

def importar_csv_para_bd(arquivo_csv):
    conteudo = arquivo_csv.read()
    try: texto = conteudo.decode('utf-8-sig')
    except: texto = conteudo.decode('latin-1')
    df = pd.read_csv(io.StringIO(texto), sep=';')
    def norm(c): return ''.join(x for x in unicodedata.normalize('NFD', str(c)) if unicodedata.category(x) != 'Mn').strip().upper()
    df.columns = [norm(col) for col in df.columns]
    if 'CODIGO' not in df.columns or 'NOME' not in df.columns: return False
    dados = [(str(r['CODIGO']).strip().upper(), str(r['NOME']).strip().upper(), str(r['TURMA']).strip().upper(), 'ATIVO') for _, r in df.iterrows()]
    try:
        conn = conectar_bd(); cur = conn.cursor()
        execute_values(cur, "INSERT INTO alunos_v2 (codigo, nome, turma, status) VALUES %s ON CONFLICT (codigo) DO UPDATE SET nome=EXCLUDED.nome, turma=EXCLUDED.turma", dados)
        conn.close(); st.cache_data.clear(); return True
    except: return False

def abrir_dia_letivo(data_str):
    try:
        conn = conectar_bd(); cur = conn.cursor()
        cur.execute("SELECT codigo FROM alunos_v2 WHERE status = 'ATIVO'")
        alunos = [row[0] for row in cur.fetchall()]; faltas = 0
        for cod in alunos:
            cur.execute("SELECT id FROM registros_v2 WHERE codigo_aluno=%s AND data=%s", (cod, data_str))
            if not cur.fetchone():
                cur.execute("INSERT INTO registros_v2 (codigo_aluno, data, tipo_registro) VALUES (%s, %s, 'FALTA')", (cod, data_str)); faltas += 1
        conn.close(); return faltas
    except: return 0

def registrar_presenca(cod, data, h_limite, h_exata=None):
    agora = obter_hora_atual()
    h_at = h_exata if h_exata else agora.strftime("%H:%M:%S")
    status = "PRESENTE" if datetime.strptime(h_at, "%H:%M:%S").time() <= h_limite else "ATRASO"
    try:
        conn = conectar_bd(); cur = conn.cursor()
        cur.execute("SELECT nome, email_responsavel FROM alunos_v2 WHERE codigo = %s", (cod,))
        res = cur.fetchone()
        if not res: conn.close(); return False
        cur.execute("DELETE FROM registros_v2 WHERE codigo_aluno=%s AND data=%s AND tipo_registro='FALTA'", (cod, data))
        cur.execute("INSERT INTO registros_v2 (codigo_aluno, data, hora_entrada, status_entrada, tipo_registro) VALUES (%s, %s, %s, %s, 'PRESENCA') ON CONFLICT DO NOTHING", (cod, data, h_at, status))
        if res[1]: disparar_email_background(res[1], res[0], "ENTRADA", h_at, data)
        conn.close(); return True
    except: return False

# =========================================================
# 🧠 DESEMPENHO ACADÊMICO (PRO)
# =========================================================
@st.cache_data(ttl=120)
def carregar_dados_desempenho():
    try:
        conn = conectar_bd()
        df = pd.read_sql_query("SELECT periodo, area, turma, nome, disciplina, questao, resposta, gabarito, acerto FROM avaliacoes_avs", conn)
        conn.close(); return df
    except: return pd.DataFrame()

def importar_csv_desempenho(arquivo_csv, periodo, area, turma):
    conteudo = arquivo_csv.read()
    try: texto = conteudo.decode('utf-8-sig')
    except: texto = conteudo.decode('latin-1')
    temp_df = pd.read_csv(io.StringIO(texto), sep=';')
    temp_df.columns = [str(c).strip() for c in temp_df.columns]
    col_qs = [c for c in temp_df.columns if re.search(r'^Q\s*\d+\s*Options', c, re.IGNORECASE)]
    if not col_qs: return False, "Colunas de questões não encontradas."
    idx_not = next((i for i, c in enumerate(temp_df.columns) if 'Not attempted' in c), -1)
    idx_f = temp_df.columns.get_loc(col_qs[0])
    discs = [str(c).strip().upper() for c in temp_df.columns[idx_not+1:idx_f] if 'AV' not in str(c).upper()] if idx_not != -1 else [area.upper()]
    q_p_d = len(col_qs) // len(discs); dados_l = []
    for row in temp_df.to_dict('records'):
        n = str(row.get('Nome', '')).strip()
        if not n or n.lower() == 'nan': continue
        for i, cq in enumerate(col_qs):
            d_i = min(i // q_p_d, len(discs)-1); rb = row.get(cq)
            r = 'BRANCO' if pd.isna(rb) or str(rb).strip() == '' else (str(rb).strip().upper() if len(str(rb).strip())==1 else 'DUPLA')
            g = str(row.get(cq.replace('Options', 'Key'), '')).strip().upper()
            dados_l.append((periodo, area, turma, n, discs[d_i], i+1, r, g, 1 if r==g and r!='BRANCO' else 0))
    try:
        conn = conectar_bd(); cur = conn.cursor()
        execute_values(cur, "INSERT INTO avaliacoes_avs (periodo, area, turma, nome, disciplina, questao, resposta, gabarito, acerto) VALUES %s ON CONFLICT (periodo, area, turma, nome, disciplina, questao) DO UPDATE SET resposta=EXCLUDED.resposta, acerto=EXCLUDED.acerto", dados_l)
        conn.close(); st.cache_data.clear(); return True, f"{len(dados_l)} registros importados."
    except: return False, "Erro no banco."

@st.cache_data(show_spinner=False)
def gerar_pdf_boletim(aluno, turma, nota_g, df_b):
    if not FPDF: return None
    pdf = FPDF(); pdf.add_page()
    pdf.set_fill_color(10, 31, 53); pdf.rect(0, 0, 210, 35, 'F')
    pdf.set_font("Arial", "B", 20); pdf.set_text_color(255, 255, 255); pdf.cell(0, 15, "BOLETIM DE DESEMPENHO", 0, 1, "C")
    pdf.set_font("Arial", "", 12); pdf.cell(0, 5, f"Jansen Veloso | {datetime.now().strftime('%d/%m/%Y')}", 0, 1, "C")
    pdf.ln(12); pdf.set_text_color(0, 0, 0); pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 8, f"ESTUDANTE: {aluno}", 0, 1); pdf.cell(0, 8, f"TURMA: {turma} | MEDIA: {nota_g:.2f}", 0, 1); pdf.ln(5)
    for p in sorted(df_b['periodo'].unique()):
        pdf.set_fill_color(230, 230, 230); pdf.set_font("Arial", "B", 14); pdf.cell(0, 10, f"  {p.upper()}", 0, 1, 'L', fill=True); pdf.ln(3)
        for d in sorted(df_b[df_b['periodo']==p]['disciplina'].unique()):
            df_d = df_b[(df_b['periodo']==p) & (df_b['disciplina']==d)]
            pdf.set_font("Arial", "B", 12); pdf.cell(0, 8, f"{d.upper()} - Nota: {(df_d['acerto'].mean()*10):.2f}", 0, 1)
            x, y, col = 10, pdf.get_y(), 0
            for q in df_d.sort_values('questao').to_dict('records'):
                if y > 265: pdf.add_page(); y = 20
                c = (16,185,129) if q['acerto']==1 else ((245,158,11) if q['resposta']=='BRANCO' else (239,68,68))
                pdf.set_fill_color(*c); pdf.set_text_color(255,255,255); pdf.set_font("Arial","B",8)
                pdf.rect(x+(col*22), y, 20, 12, 'F'); pdf.text(x+(col*22)+2, y+5, f"Q{q['questao']}"); pdf.text(x+(col*22)+2, y+10, f"R:{q['resposta']}")
                col += 1
                if col > 7: col, y = 0, y+15
            y = y+15 if col>0 else y; pdf.set_y(y+5); pdf.set_text_color(0,0,0)
    return pdf.output(dest='S').encode('latin-1')

# ------------------------------------------------------------
# 6. INTERFACE E AUTH
# ------------------------------------------------------------
check_auth = cookies.get("auth_token")
if not check_auth:
    st.markdown('<div class="login-card">', unsafe_allow_html=True)
    if os.path.exists("logo.png"): st.columns([1.5,1,1.5])[1].image("logo.png", use_container_width=True)
    st.markdown('<div class="login-title">JANSEN VELOSO</div>', unsafe_allow_html=True)
    senha = st.text_input("SENHA:", type="password")
    if st.button("ACESSAR"):
        if senha in [SENHA_ADMIN, SENHA_OPERADOR]:
            cookies["auth_token"] = base64.b64encode(json.dumps({"eh_admin": senha==SENHA_ADMIN}).encode()).decode(); cookies.save(); st.rerun()
        else: st.error("Senha Incorreta!")
    st.stop()

auth_data = json.loads(base64.b64decode(check_auth).decode()); eh_admin = auth_data['eh_admin']

if os.path.exists("logo.png"): st.columns([1.5,1,1.5])[1].image("logo.png", use_container_width=True)
st.markdown('<p class="main-title">SISTEMA DE FREQUÊNCIA</p>', unsafe_allow_html=True)
st.markdown(f'<p class="sub-title">Jansen Veloso • {data_formatada_ptbr()}</p>', unsafe_allow_html=True)
if st.button("SAIR"): cookies["auth_token"] = ""; cookies.save(); st.rerun()

df_alunos = carregar_alunos(); hoje = obter_hora_atual().strftime("%Y-%m-%d")
try:
    conn = conectar_bd(); cur = conn.cursor()
    cur.execute("SELECT COUNT(CASE WHEN tipo_registro='PRESENCA' THEN 1 END), COUNT(CASE WHEN tipo_registro='FALTA' THEN 1 END) FROM registros_v2 WHERE data=%s", (hoje,))
    pres, falt = cur.fetchone(); conn.close()
except: pres, falt = 0, 0

st.markdown(f'''<div class="metrics-container">
    <div class="metric-card m-total"><span class="m-val">{len(df_alunos[df_alunos['status']=='ATIVO'])}</span><span class="m-lab">Ativos</span></div>
    <div class="metric-card m-presente"><span class="m-val">{pres or 0}</span><span class="m-lab">Presentes</span></div>
    <div class="metric-card m-falta"><span class="m-val">{falt or 0}</span><span class="m-lab">Faltas</span></div>
    <div class="metric-card m-atraso"><span class="m-val">--</span><span class="m-lab">Média Escolar</span></div>
</div>''', unsafe_allow_html=True)

tabs = st.tabs(["📝 Registro", "📊 Gestão", "🚨 Alertas", "📈 Histórico", "⚙️ Manutenção", "📑 Desempenho Acadêmico"])

# ABA REGISTRO, GESTÃO, ETC (Mantidas conforme versões anteriores)
with tabs[0]:
    st.markdown('<div class="card-panel">', unsafe_allow_html=True)
    d_reg = st.date_input("Data", obter_hora_atual())
    h_lim = st.time_input("Limite Entrada", datetime.strptime("07:30", "%H:%M").time())
    if st.button("📍 ABRIR DIA"):
        n = abrir_dia_letivo(d_reg.strftime("%Y-%m-%d")); st.success(f"{n} faltas geradas.")
    c_in = st.text_input("Código Aluno", key="reg_in")
    if st.button("REGISTRAR") and c_in:
        if registrar_presenca(c_in.upper(), d_reg.strftime("%Y-%m-%d"), h_lim): st.success("Registrado!"); st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# =================================================================================
# 📑 ABA: DESEMPENHO ACADÊMICO (ACESSO OPERADOR + ADMIN)
# =================================================================================
with tabs[5]:
    st.markdown('<div class="card-panel">', unsafe_allow_html=True)
    st.title("📊 Desempenho Acadêmico")
    df_da = carregar_dados_desempenho()
    
    # Filtros Globais com Destaque CSS
    c1, c2, c3 = st.columns(3)
    with c1: p_f = st.selectbox("Período", ["Todos", "1º Período", "2º Período", "3º Período", "4º Período"])
    with c2: a_f = st.selectbox("Área", ["Todas", "LÍNGUA PORTUGUESA", "MATEMÁTICA", "LINGUAGENS", "HUMANAS", "NATUREZA"])
    with c3: t_f = st.selectbox("Turma", ["Todas"] + sorted(df_alunos['turma'].unique()))
    
    dff = df_da.copy()
    if p_f != "Todos": dff = dff[dff['periodo']==p_f]
    if a_f != "Todas": dff = dff[dff['area']==a_f]
    if t_f != "Todas": dff = dff[dff['turma']==t_f]

    sub_tabs = ["🏆 Destaques", "🧑‍🎓 Estudantes", "📈 Gráficos", "📋 Questões"]
    if eh_admin: sub_tabs.append("⚙️ Gerenciar Dados")
    
    stabs = st.tabs(sub_tabs)
    
    with stabs[0]: # DESTAQUES
        if dff.empty: st.info("Sem dados.")
        else:
            res = dff.groupby(['nome','turma']).agg(T=('questao','count'), A=('acerto','sum')).reset_index()
            res['Nota'] = (res['A']/res['T'])*10
            for idx, r in enumerate(res.sort_values('Nota', ascending=False).head(7).to_dict('records')):
                st.markdown(f'<div class="top7-card"><div class="top7-medal">{"🥇🥈🥉⭐"[min(idx,3)]} {idx+1}º</div><div class="top7-name">{r["nome"]}</div><div class="top7-details">NOTA: {r["Nota"]:.2f} | {r["turma"]}</div></div>', unsafe_allow_html=True)

    with stabs[1]: # ESTUDANTES
        if dff.empty: st.info("Sem dados.")
        else:
            busca = st.text_input("Buscar Aluno:")
            res_e = dff.groupby(['nome','turma']).agg(T=('questao','count'), A=('acerto', 'sum')).reset_index()
            res_e['Nota'] = (res_e['A']/res_e['T'])*10
            if busca: res_e = res_e[res_e['nome'].str.contains(busca.upper())]
            
            # Exibição: Se selecionou turma ou buscou, mostra todos. Senão, mostra 20.
            lista = res_e.to_dict('records') if (t_f != "Todas" or busca) else res_e.head(20).to_dict('records')
            
            for al in lista:
                with st.expander(f"👤 {al['nome']} | Nota: {al['Nota']:.2f}"):
                    st.write(f"Turma: {al['turma']}")
                    if st.button("Gerar PDF", key=f"pdf_{al['nome']}"):
                        b_pdf = gerar_pdf_boletim(al['nome'], al['turma'], al['Nota'], df_da[df_da['nome']==al['nome']])
                        st.download_button("Baixar PDF", b_pdf, f"Boletim_{al['nome']}.pdf")

    with stabs[2]: # GRÁFICOS
        if not dff.empty:
            g_disc = dff.groupby('disciplina').acerto.mean()*10
            st.plotly_chart(px.bar(g_disc, title="Média por Disciplina"), use_container_width=True)

    with stabs[3]: # QUESTÕES
        if not dff.empty:
            st.write("Questões com maior índice de erro:")
            q_err = dff.groupby(['disciplina','questao']).acerto.mean().reset_index()
            st.dataframe(q_err[q_err.acerto < 0.5].sort_values('acerto'))

    if eh_admin:
        with stabs[4]: # GERENCIAR (SÓ ADMIN)
            st.subheader("Upload de Dados Acadêmicos")
            up = st.file_uploader("CSV de Desempenho", type="csv")
            if st.button("IMPORTAR") and up:
                s, m = importar_csv_desempenho(up, p_f, a_f, t_f)
                if s: st.success(m); st.rerun()
                else: st.error(m)
            if st.button("Limpar Dados Selecionados (Período/Área/Turma)"):
                excluir_dados_avs(p_f, a_f, t_f); st.success("Limpo!"); st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# Finalização da aba Manutenção (Apenas Admin)
with tabs[4]:
    if not eh_admin: st.warning("Acesso restrito ao Administrador.")
    else:
        st.subheader("Importar Alunos")
        up_a = st.file_uploader("CSV Alunos", type="csv", key="up_alunos")
        if st.button("Processar Alunos") and up_a:
            if importar_csv_para_bd(up_a): st.success("Alunos Importados!"); st.rerun()
