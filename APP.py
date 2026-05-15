import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import execute_batch
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

# NOVAS BIBLIOTECAS PARA O ANALISADOR AVS E GRÁFICOS
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
# 1. CONFIGURAÇÃO GERAL
# ------------------------------------------------------------
st.set_page_config(page_title="Centro Educa Mais Jansen Veloso", page_icon="🏫", layout="wide", initial_sidebar_state="collapsed")

if 'fila_offline' not in st.session_state: st.session_state.fila_offline = []
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
    texto = f"Olá, família!\n\nInformamos que o estudante {nome_aluno} registrou sua {evento} na escola hoje ({data_formatada}) no horário de: {horario}.\n\nAtenciosamente,\nEquipe Jansen Veloso."
    msg = MIMEMultipart()
    msg['From'] = EMAIL_ESCOLA; msg['To'] = email_destino; msg['Subject'] = assunto
    msg.attach(MIMEText(texto, 'plain'))
    def enviar():
        if ATIVAR_EMAILS:
            try:
                server = smtplib.SMTP('smtp.gmail.com', 587); server.starttls(); server.login(EMAIL_ESCOLA, SENHA_APP_ESCOLA)
                server.send_message(msg); server.quit()
            except Exception as e: print(f"[ERRO] E-mail: {e}")
    threading.Thread(target=enviar).start()

# ------------------------------------------------------------
# 2. CSS PREMIUM (CORREÇÃO DE VISIBILIDADE DOS FILTROS)
# ------------------------------------------------------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap');
    :root { --primary: #0a1f35; --accent: #ff7b00; --success: #10b981; --danger: #ef4444; --bg-color: #f8fafc; }
    .stApp { background: var(--bg-color); }
    #MainMenu, footer, header {visibility: hidden;}
    
    html, body, p, span, label, div { font-size: 1.15rem !important; }

    .main-title { font-family: 'Inter', sans-serif; font-weight: 900; font-size: clamp(2.8rem, 7vw, 3.8rem); color: var(--primary); text-align: center; margin:0; text-transform: uppercase; letter-spacing: -1px;}
    .sub-title { font-family: 'Inter', sans-serif; font-size: 1.4rem; color: #64748b; text-align: center; margin-bottom: 2rem; font-weight: 700;}
    
    /* CORREÇÃO FILTROS: Fundo branco e texto preto */
    div[data-baseweb="select"] > div { 
        background-color: #ffffff !important; 
        border: 2px solid #cbd5e1 !important;
    }
    div[data-baseweb="select"] * { 
        color: #000000 !important; 
        font-weight: 800 !important;
    }
    
    .metric-card { background: white; padding: 2.2rem 1rem; border-radius: 16px; box-shadow: 0 4px 10px rgba(0,0,0,0.04); text-align: center; position: relative; overflow: hidden; border: 1px solid #e2e8f0; }
    .m-val { font-size: 3.8rem; font-weight: 900; color: #1e293b; display: block; line-height: 1.2; }
    
    .stTabs [data-baseweb="tab"] { background-color: #f1f5f9 !important; border-radius: 18px 18px 0 0 !important; padding: 15px 25px !important; font-size: 1.4rem !important; font-weight: 900 !important; }
    .stTabs [aria-selected="true"] { background-color: var(--primary) !important; color: #ffffff !important; border: 4px solid var(--accent) !important; }
    
    .top7-card { background: linear-gradient(135deg, #ffffff, #f1f5f9); border-left: 10px solid var(--accent); padding: 2rem; border-radius: 15px; margin-bottom: 1.2rem; box-shadow: 0 10px 25px rgba(0,0,0,0.08); text-align: center;}
    .top7-name { font-size: 2.8rem; font-weight: 900; color: var(--primary); }
    .top7-name-hidden { font-size: 2.8rem; font-weight: 900; color: #94a3b8; filter: blur(6px); }

    /* Cores Alternadas nos Estudantes */
    div[data-testid="stExpander"]:nth-child(even) { background-color: #ffffff; border: 1px solid #cbd5e1; }
    div[data-testid="stExpander"]:nth-child(odd) { background-color: #f1f5f9; border: 1px solid #94a3b8; }
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------
# 3. BANCO DE DADOS
# ------------------------------------------------------------
DATABASE_URL = st.secrets.get("DATABASE_URL", os.environ.get("DATABASE_URL"))
def conectar_bd():
    conn = psycopg2.connect(DATABASE_URL); conn.autocommit = True; return conn

@st.cache_data(ttl=300)
def carregar_alunos():
    try:
        conn = conectar_bd(); df = pd.read_sql_query("SELECT * FROM alunos_v2 ORDER BY turma, nome", conn); conn.close()
        return df
    except: return pd.DataFrame()

# ------------------------------------------------------------
# 4. EXPORTAÇÃO DE BOLETIM PDF COLORIDO
# ------------------------------------------------------------
def gerar_pdf_boletim(aluno_nome, turma, nota, df_bol):
    if FPDF is None: return None
    pdf = FPDF()
    pdf.add_page()
    
    # Cabeçalho
    pdf.set_fill_color(10, 31, 53) # Azul Escuro
    pdf.rect(0, 0, 210, 40, 'F')
    pdf.set_font("Arial", "B", 22); pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 15, "BOLETIM DE DESEMPENHO - AVS", 0, 1, "C")
    pdf.set_font("Arial", "", 12)
    pdf.cell(0, 10, f"Centro Educa Mais Jansen Veloso | Data: {datetime.now().strftime('%d/%m/%Y')}", 0, 1, "C")
    
    pdf.ln(20)
    pdf.set_text_color(0, 0, 0); pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, f"ESTUDANTE: {aluno_nome}", 0, 1)
    pdf.cell(0, 10, f"TURMA: {turma} | NOTA MÉDIA: {nota:.2f}", 0, 1)
    pdf.ln(10)
    
    # Mapa de Questões
    pdf.set_font("Arial", "B", 12); pdf.cell(0, 10, "MAPA DE QUESTOES (LEGENDA: VERDE=ACERTO | VERMELHO=ERRO | LARANJA=BRANCO)", 0, 1)
    
    x_start = 10; y_start = pdf.get_y(); col = 0
    for _, q in df_bol.sort_values(['periodo', 'disciplina', 'questao']).iterrows():
        # Define cor do box
        if q['acerto'] == 1: pdf.set_fill_color(16, 185, 129) # Verde
        elif q['resposta'] == 'BRANCO': pdf.set_fill_color(245, 158, 11) # Laranja
        else: pdf.set_fill_color(239, 68, 68) # Vermelho
        
        pdf.set_text_color(255, 255, 255); pdf.set_font("Arial", "B", 8)
        pdf.rect(x_start + (col * 22), y_start, 20, 12, 'F')
        pdf.text(x_start + (col * 22) + 2, y_start + 5, f"Q{q['questao']}")
        pdf.text(x_start + (col * 22) + 2, y_start + 10, f"R:{q['resposta']}")
        
        col += 1
        if col > 7: col = 0; y_start += 15
        if y_start > 260: pdf.add_page(); y_start = 20
        
    return pdf.output(dest='S').encode('latin-1')

# ------------------------------------------------------------
# 5. IMPORTAÇÃO CSV ACELERADA (VELOCIDADE MÁXIMA)
# ------------------------------------------------------------
def importar_csv_avs_nuvem(arquivo_csv, periodo, area, turma):
    temp_df = pd.read_csv(arquivo_csv, sep=';')
    col_options = [c for c in temp_df.columns if 'Options' in str(c)]
    disciplinas = [area.upper()] # Simplificado para velocidade
    questoes_por_disc = len(col_options)
    
    dados_longos = []
    for _, row in temp_df.iterrows():
        nome = str(row.get('Nome', '')).strip().upper()
        if not nome or nome == 'NAN': continue
        for i, col_opt in enumerate(col_options):
            resp = str(row.get(col_opt, 'BRANCO')).strip().upper()
            if resp == '' or resp == 'NAN': resp = 'BRANCO'
            gab = str(row.get(col_opt.replace('Options', 'Key'), '')).strip().upper()
            acerto = 1 if resp == gab and resp != 'BRANCO' else 0
            dados_longos.append((periodo, area, turma, nome, area, i+1, resp, gab, acerto))
            
    try:
        conn = conectar_bd(); cur = conn.cursor()
        query = "INSERT INTO avaliacoes_avs (periodo, area, turma, nome, disciplina, questao, resposta, gabarito, acerto) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT DO UPDATE SET acerto=EXCLUDED.acerto"
        execute_batch(cur, query, dados_longos) # AQUI ESTÁ A VELOCIDADE!
        conn.close(); st.cache_data.clear(); return True, f"Sucesso! {len(dados_longos)} registros processados."
    except Exception as e: return False, f"Erro: {e}"

# ------------------------------------------------------------
# 6. INTERFACE PRINCIPAL
# ------------------------------------------------------------
# LOGO CENTRALIZADO
if os.path.exists("logo.png"):
    c1, c2, c3 = st.columns([1,1,1]); c2.image("logo.png", use_container_width=True)

st.markdown('<p class="main-title">Jansen Veloso AVS</p>', unsafe_allow_html=True)
st.markdown(f'<p class="sub-title">{data_formatada_ptbr()}</p>', unsafe_allow_html=True)

df_alunos = carregar_alunos()
df_avs = pd.read_sql_query("SELECT * FROM avaliacoes_avs", conectar_bd()) if st.session_state.get('autenticado') else pd.DataFrame()

tabs = st.tabs(["📝 Frequência", "📊 Analisador AVS", "⚙️ Sistema"])

# --- ABA ANALISADOR (MELHORADA) ---
with tabs[1]:
    if df_avs.empty: st.info("Importe dados em 'Sistema' para começar.")
    else:
        st.subheader("🔍 Filtros de Análise")
        f1, f2, f3 = st.columns(3)
        p_sel = f1.selectbox("Período", ["Todos"] + list(df_avs['periodo'].unique()), key="f_p")
        a_sel = f2.selectbox("Área", ["Todas"] + list(df_avs['area'].unique()), key="f_a")
        t_sel = f3.selectbox("Turma", ["Todas"] + list(df_avs['turma'].unique()), key="f_t")
        
        df_f = df_avs.copy()
        if p_sel != "Todos": df_f = df_f[df_f['periodo'] == p_sel]
        if a_sel != "Todas": df_f = df_f[df_f['area'] == a_sel]
        if t_sel != "Todas": df_f = df_f[df_f['turma'] == t_sel]
        
        sub_avs = st.tabs(["🏆 Top 7", "🧑‍🎓 Estudantes", "📈 Gráficos"])
        
        with sub_avs[0]: # TOP 7 COM REVELAÇÃO
            top7 = df_f.groupby(['nome', 'turma'])['acerto'].mean().mul(10).nlargest(7).reset_index()
            for i, r in top7.iterrows():
                reveal = st.toggle(f"Revelar #{i+1}", key=f"rev_{i}")
                nome_txt = r['nome'] if reveal else "ESTUDANTE OCULTO"
                st.markdown(f'<div class="top7-card"><div class="top7-name">{nome_txt}</div>Nota: {r["acerto"]:.2f} | {r["turma"]}</div>', unsafe_allow_html=True)

        with sub_avs[1]: # ESTUDANTES COM PDF COLORIDO
            for i, (nome, dados) in enumerate(df_f.groupby('nome')):
                nota = dados['acerto'].mean() * 10
                brancos = (dados['resposta'] == 'BRANCO').sum()
                with st.expander(f"👤 {nome} | Nota: {nota:.2f} | Brancos: {brancos}"):
                    # BOTÃO DE PDF
                    pdf_data = gerar_pdf_boletim(nome, dados['turma'].iloc[0], nota, dados)
                    if pdf_data:
                        st.download_button(f"📥 Baixar Boletim PDF - {nome}", pdf_data, f"Boletim_{nome}.pdf", "application/pdf", key=f"btn_pdf_{i}")
                    
                    # MAPA COLORIDO NA TELA
                    st.markdown("**Mapa de Questões:**")
                    cols = st.columns(8)
                    for idx, q in enumerate(dados.sort_values('questao').itertuples()):
                        cor = "#10b981" if q.acerto == 1 else ("#f59e0b" if q.resposta == 'BRANCO' else "#ef4444")
                        cols[idx % 8].markdown(f'<div style="background:{cor}; color:white; padding:5px; border-radius:5px; text-align:center; font-size:12px">Q{q.questao}<br>{q.resposta}</div>', unsafe_allow_html=True)

        with sub_avs[2]: # GRÁFICOS INTERATIVOS MODERNOS
            resumo = df_f.groupby('disciplina')['acerto'].mean().mul(10).reset_index()
            fig = px.bar(resumo, x='disciplina', y='acerto', color='acerto', color_continuous_scale='RdYlGn', title="Média por Disciplina")
            fig.update_layout(yaxis_range=[0,10], plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig, use_container_width=True)

# --- ABA SISTEMA (IMPORTAÇÃO RÁPIDA) ---
with tabs[2]:
    st.subheader("📥 Importação CSV AVS (Lotes de Alta Velocidade)")
    c1, c2, c3 = st.columns(3)
    p_up = c1.selectbox("Período", ["1º Período", "2º Período", "3º Período", "4º Período"])
    a_up = c2.selectbox("Área", ["LÍNGUA PORTUGUESA", "MATEMÁTICA", "NATUREZA", "HUMANAS", "LINGUAGENS"])
    t_up = c3.selectbox("Turma Alvo", sorted(df_alunos['turma'].unique()) if not df_alunos.empty else ["6º ANO A"])
    
    file = st.file_uploader("Arraste o CSV aqui", type="csv")
    if st.button("PROCESSAR AGORA") and file:
        with st.spinner("Injetando dados no banco..."):
            ok, msg = importar_csv_avs_nuvem(file, p_up, a_up, t_up)
            if ok: st.success(msg); st.rerun()
            else: st.error(msg)
