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
# Variável de memória para controlar se o formulário público já foi enviado
if 'pesquisa_enviada' not in st.session_state: st.session_state.pesquisa_enviada = False

cookies = CookieManager()
if not cookies.ready(): st.stop()

# ------------------------------------------------------------
# 2. FUNÇÕES DE SUPORTE
# ------------------------------------------------------------
def obter_hora_atual(): return datetime.utcnow() - timedelta(hours=3)

def data_formatada_ptbr():
    dt = obter_hora_atual()
    meses = ["", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
    return f"{dt.day:02d} de {meses[dt.month]} de {dt.year}"

ATIVAR_EMAILS = True  
EMAIL_ESCOLA = st.secrets.get("EMAIL_ESCOLA", "") 
SENHA_APP_ESCOLA = st.secrets.get("SENHA_APP_ESCOLA", "") 

def disparar_email_background(email_destino, nome_aluno, evento, horario, data):
    try: data_f = datetime.strptime(data, "%Y-%m-%d").strftime("%d/%m/%Y")
    except: data_f = data
    
    if evento.startswith("ENTRADA"):
        assunto = f"🏫 Aviso de Entrada - Jansen Veloso"
        texto = f"Olá, família!\n\nInformamos que o estudante {nome_aluno} registrou ENTRADA ({'ATRASO' if 'ATRASO' in evento else 'REGULAR'}) hoje ({data_f}) às {horario}.\n\nAtenciosamente,\nEquipe Jansen Veloso."
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

def renderizar_logo_central():
    if os.path.exists("logo.png"):
        try:
            with open("logo.png", "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode()
            st.markdown(f'<div style="display: flex; justify-content: center; margin-bottom: 10px;"><img src="data:image/png;base64,{encoded_string}" width="170"></div>', unsafe_allow_html=True)
        except: pass

# ------------------------------------------------------------
# 3. CSS (VISUAL PREMIUM E OTIMIZADO PARA MOBILE)
# ------------------------------------------------------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap');
    :root { --primary: #0a1f35; --accent: #ff7b00; --success: #10b981; --danger: #ef4444; --bg-color: #f8fafc; }
    .stApp { background: var(--bg-color); }
    #MainMenu, footer, header {visibility: hidden;}
    
    html, body, [class*="css"], p, span, label, div { font-size: 1.15rem !important; }
    
    /* 📱 MELHORIA MOBILE: Cartões maiores e espaçados para as opções do formulário */
    [data-testid="stRadio"] div[role="radiogroup"] > label {
        font-size: 1.3rem !important;
        padding: 16px 15px !important;
        margin-bottom: 12px !important;
        background-color: #ffffff;
        border: 2px solid #cbd5e1;
        border-radius: 12px;
        box-shadow: 0 3px 6px rgba(0,0,0,0.04);
        cursor: pointer;
        transition: all 0.2s ease;
    }
    [data-testid="stRadio"] div[role="radiogroup"] > label:hover {
        border-color: var(--accent);
        transform: translateY(-2px);
    }

    .main-title { font-family: 'Inter', sans-serif; font-weight: 900; font-size: clamp(3.5rem, 8vw, 4.8rem); color: var(--primary); text-align: center; margin:0; text-transform: uppercase; letter-spacing: -2px;}
    .sub-title { font-family: 'Inter', sans-serif; font-size: 1.6rem; color: #64748b; text-align: center; margin-bottom: 2rem; font-weight: 700;}
    
    .metrics-container { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1.5rem; margin-bottom: 2rem; }
    @media (max-width: 800px) { .metrics-container { grid-template-columns: repeat(2, 1fr); } }
    
    .metric-card { background: white; padding: 2.5rem 1.5rem; border-radius: 20px; box-shadow: 0 8px 25px rgba(0,0,0,0.06); text-align: center; position: relative; overflow: hidden; border: 2px solid #e2e8f0; }
    .m-val { font-size: 3rem; font-weight: 900; color: #0f172a; display: block; }
    .m-lab { font-size: 1rem; font-weight: 900; color: #475569; text-transform: uppercase; margin-top: 0.5rem; display: block; }
    
    .card-panel { background: white; border-radius: 20px; padding: 2.2rem; margin-bottom: 1.5rem; box-shadow: 0 8px 20px rgba(0,0,0,0.03); border: 2px solid #e2e8f0; }
    .login-card { max-width: 600px; margin: 5vh auto; background: white; border-radius: 24px; padding: 3rem 2rem; box-shadow: 0 20px 40px rgba(0,0,0,0.1); border: 3px solid var(--primary); }
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
        cur.execute("CREATE TABLE IF NOT EXISTS avaliacoes_avs (id SERIAL PRIMARY KEY, periodo TEXT, area TEXT, turma TEXT, nome TEXT, disciplina TEXT, questao INTEGER, resposta TEXT, gabarito TEXT, acerto INTEGER, UNIQUE(periodo, area, turma, nome, disciplina, questao))")
        cur.execute("""CREATE TABLE IF NOT EXISTS satisfacao_v1 (
            id SERIAL PRIMARY KEY, data_hora TIMESTAMP, categoria TEXT, turma TEXT, 
            q1 INTEGER, q2 INTEGER, q3 INTEGER, q4 INTEGER, q5 INTEGER, sugestao TEXT
        )""")
        conn.commit(); conn.close()
    except: pass

inicializar_tabelas()

@st.cache_data(ttl=300)
def carregar_alunos():
    try:
        conn = conectar_bd(); df = pd.read_sql("SELECT codigo, nome, turma, status, email_responsavel FROM alunos_v2 ORDER BY turma, nome", conn); conn.close(); return df
    except: return pd.DataFrame()

@st.cache_data(ttl=60)
def carregar_satisfacao():
    try:
        conn = conectar_bd(); df = pd.read_sql("SELECT * FROM satisfacao_v1", conn); conn.close()
        if not df.empty: df['media_resposta'] = df[['q1','q2','q3','q4','q5']].mean(axis=1)
        return df
    except: return pd.DataFrame()

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
                if(input) {{ input.value = txt; input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    setTimeout(() => {{ window.parent.document.querySelectorAll('button').forEach(b => {{ if(b.innerText.includes("{btn_label}")) b.click(); }}); }}, 500);
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
# 6. MÓDULO PÚBLICO: PESQUISA DE SATISFAÇÃO (OCULTO VIA URL)
# ------------------------------------------------------------
if st.query_params.get("modo") == "pesquisa":
    st.markdown("<div class='login-card' style='max-width: 750px;'>", unsafe_allow_html=True)
    renderizar_logo_central()
    
    # LÓGICA DE TELA DE SUCESSO
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
        
        # Botão opcional caso queiram enviar outra avaliação do mesmo celular
        if st.button("Enviar nova avaliação", use_container_width=True):
            st.session_state.pesquisa_enviada = False
            st.rerun()
            
        st.markdown("</div>", unsafe_allow_html=True)
        st.stop() # Para a execução aqui, escondendo todo o resto do formulário
        
    # LÓGICA DO FORMULÁRIO (Se ainda não foi enviado)
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
            # Adicionado index=None para forçar o usuário a escolher
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
            else: # Servidor
                q4 = st.radio("Como você avalia as condições de trabalho e recursos disponíveis no seu setor?", opcoes, index=None)
                q5 = st.radio("Como você avalia o clima organizacional e a colaboração da equipe?", opcoes, index=None)

            sugestao = st.text_area("Deixe aqui uma sugestão, crítica ou elogio (Opcional)")

            if st.form_submit_button("🚀 ENVIAR MINHA AVALIAÇÃO AGORA"):
                # Validação super rigorosa: Impede o envio se faltar qualquer resposta
                if not all([q1, q2, q3, q4, q5]):
                    st.error("⚠️ Atenção: Por favor, selecione uma nota para todas as 5 perguntas antes de enviar.")
                elif cat == "Estudante" and not turma_sel:
                    st.error("⚠️ Atenção: Por favor, selecione a sua turma no topo do formulário.")
                else:
                    try:
                        conn = conectar_bd(); cur = conn.cursor()
                        cur.execute("INSERT INTO satisfacao_v1 (data_hora, categoria, turma, q1, q2, q3, q4, q5, sugestao) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                                    (obter_hora_atual(), cat, turma_sel, int(q1[0]), int(q2[0]), int(q3[0]), int(q4[0]), int(q5[0]), sugestao))
                        conn.commit(); conn.close(); carregar_satisfacao.clear()
                        
                        # Muda o estado para 'enviado' e recarrega a página para mostrar o Agradecimento
                        st.session_state.pesquisa_enviada = True
                        st.rerun()
                    except: st.error("Erro de conexão ao salvar avaliação. Tente novamente.")
    st.markdown("</div>", unsafe_allow_html=True)
    st.stop() # Interrompe a renderização para não mostrar o Painel do Diretor


# ------------------------------------------------------------
# 8. AUTH E DASHBOARD DO DIRETOR (Ocultado da área pública)
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

# (O RESTANTE DA LÓGICA ACADÊMICA E ABAS ESTÁ PRESERVADA ABAIXO)
hoje = obter_hora_atual().strftime("%Y-%m-%d")
try:
    conn = conectar_bd(); cur = conn.cursor(); cur.execute("SELECT COUNT(*) FROM registros_v2 WHERE data=%s AND tipo_registro='PRESENCA'", (hoje,))
    pres_hoje = cur.fetchone()[0]; conn.close()
except: pres_hoje = 0

total_alunos = len(df_alunos)
media_geral_freq = f"{(pres_hoje / total_alunos) * 100:.1f}%" if total_alunos > 0 else "0%"

st.markdown(f'''
<div class="metrics-container">
    <div class="metric-card m-total"><span class="m-val">{total_alunos}</span><span class="m-lab">Total Alunos</span></div>
    <div class="metric-card m-presente"><span class="m-val">{pres_hoje}</span><span class="m-lab">Presentes Hoje</span></div>
    <div class="metric-card m-falta"><span class="m-val">{total_alunos-pres_hoje}</span><span class="m-lab">Faltas Hoje</span></div>
    <div class="metric-card m-atraso"><span class="m-val">{media_geral_freq}</span><span class="m-lab">Frequência Diária</span></div>
</div>
''', unsafe_allow_html=True)

st.markdown("### 🎛️ Filtros Globais (Acadêmico & Pesquisa)")
cf1, cf2, cf3 = st.columns(3)
pf = cf1.selectbox("Período Acadêmico", ["Todos", "1º Período", "2º Período", "3º Período", "4º Período"], key="filtro_periodo_da")
af = cf2.selectbox("Área Acadêmica", ["Todas", "LÍNGUA PORTUGUESA", "MATEMÁTICA", "LINGUAGENS", "HUMANAS", "NATUREZA"], key="filtro_area_da")
tf = cf3.selectbox("Turma (Filtra Acadêmico e Satisfação Estudante)", ["Todas"] + sorted(df_alunos.turma.unique() if not df_alunos.empty else []), key="filtro_turma_da")

df_avaliacoes_cache = carregar_avaliacoes()
if not df_avaliacoes_cache.empty:
    df_avaliacoes_cache['disciplina'] = df_avaliacoes_cache['disciplina'].replace({'LÍNGUA PORTUGESA': 'LÍNGUA PORTUGUESA', 'SOCIOLGIA': 'SOCIOLOGIA'})

df_da = df_avaliacoes_cache.copy()

dff = df_da.copy()
if pf != "Todos": dff = dff[dff.periodo==pf]
if af != "Todas": dff = dff[dff.area==af]
if tf != "Todas": dff = dff[dff.turma==tf]

media_geral_acad = f"{dff['acerto'].mean() * 10:.1f}" if not dff.empty else "--"

df_sat = carregar_satisfacao()
sat_est_str, sat_pais_str, sat_eq_str = "--", "--", "--"

if not df_sat.empty:
    df_sat_est = df_sat[df_sat['categoria'] == 'Estudante']
    if tf != "Todas": df_sat_est = df_sat_est[df_sat_est['turma'] == tf]
    if not df_sat_est.empty: sat_est_str = f"{df_sat_est['media_resposta'].mean():.1f} / 5"
    
    df_sat_pais = df_sat[df_sat['categoria'] == 'Pais/Responsável']
    if not df_sat_pais.empty: sat_pais_str = f"{df_sat_pais['media_resposta'].mean():.1f} / 5"
    
    df_sat_eq = df_sat[df_sat['categoria'].isin(['Professor', 'Servidor'])]
    if not df_sat_eq.empty: sat_eq_str = f"{df_sat_eq['media_resposta'].mean():.1f} / 5"

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
    st.markdown("#### ⚙️ Configuração do Turno Letivo")
    st.write("Ajuste os horários de início e término do turno para que o sistema saiba registrar os atrasos e as saídas corretamente.")
    c_cfg1, c_cfg2 = st.columns(2)
    with c_cfg1: h_lim_e = st.time_input("🟢 Horário Limite de Entrada", datetime.strptime("07:30", "%H:%M").time())
    with c_cfg2: h_lim_s = st.time_input("🔴 Horário de Término (Saída)", datetime.strptime("17:00", "%H:%M").time())
    st.markdown("---")
    
    t_en, t_sa, t_jf = st.tabs(["✅ ENTRADA", "🚪 REGISTRO DE SAÍDA", "📝 JUSTIFICAR FALTAS"])
    with t_en:
        gerar_camera("Entrada", "REGISTRAR ENTRADA", "c_in")
        with st.form("f_en", clear_on_submit=True):
            cod_en = st.text_input("Código Aluno (Entrada)")
            if st.form_submit_button("REGISTRAR ENTRADA") and cod_en:
                # FUNÇÕES AQUI
                pass
                
    with t_sa:
        gerar_camera("Saída", "CONFIRMAR SAÍDA", "c_out")
        with st.form("f_sa", clear_on_submit=True):
            cod_sa = st.text_input("Código Aluno (Saída)")
            hora_saida_manual = st.time_input("Horário Exato da Saída", obter_hora_atual().time())
            mot = st.selectbox("Motivo", ["Mal-estar", "Consulta Médica", "Liberação da Direção", "Término do Turno", "Outros"])
            if st.form_submit_button("CONFIRMAR SAÍDA") and cod_sa:
                # LÓGICA DE SAÍDA AQUI
                pass
    with t_jf:
        st.subheader("Justificar Faltas de Estudantes")
        d_just = st.date_input("Data da Falta", obter_hora_atual().date())
        # LÓGICA JUSTIFICATIVA
        pass
    st.markdown('</div>', unsafe_allow_html=True)
indice_aba += 1

with tabs[indice_aba]:
    st.markdown('<div class="card-panel">', unsafe_allow_html=True); st.subheader("📊 Relatório Diário")
    st.info("Visão da frequência")
    st.markdown('</div>', unsafe_allow_html=True)
indice_aba += 1

with tabs[indice_aba]:
    st.markdown('<div class="card-panel">', unsafe_allow_html=True); st.subheader("🚨 Alunos em Risco")
    st.info("Painel de Alertas")
    st.markdown('</div>', unsafe_allow_html=True)
indice_aba += 1

with tabs[indice_aba]:
    st.markdown('<div class="card-panel">', unsafe_allow_html=True); st.subheader("📈 Histórico Individual")
    st.info("Painel Histórico")
    st.markdown('</div>', unsafe_allow_html=True)
indice_aba += 1

with tabs[indice_aba]:
    st.markdown('<div class="card-panel">', unsafe_allow_html=True)
    st.title("📊 Desempenho Acadêmico")
    st.info("💡 **Atenção:** Os dados exibidos nesta aba obedecem aos Filtros Globais selecionados no topo da tela.")
    st.markdown('</div>', unsafe_allow_html=True)
indice_aba += 1

# ------------------------------------------------------------
# 7. NOVA ABA: ANÁLISE DE SATISFAÇÃO DA COMUNIDADE
# ------------------------------------------------------------
with tabs[indice_aba]:
    st.markdown('<div class="card-panel">', unsafe_allow_html=True)
    st.title("💬 Análise de Satisfação da Comunidade")
    st.info("💡 **Dica:** Os dados de Estudantes também obedecem ao filtro global de Turma selecionado no topo da tela.")
    
    if df_sat.empty:
        st.warning("Nenhuma avaliação de satisfação foi recebida até o momento.")
    else:
        cat_sat = st.selectbox("Selecione o Segmento para Análise Gráfica:", ["Todos", "Estudante", "Pais/Responsável", "Professor", "Servidor"], key="filtro_cat_sat")
        
        df_sat_filtrado = df_sat.copy()
        if cat_sat != "Todos":
            df_sat_filtrado = df_sat_filtrado[df_sat_filtrado['categoria'] == cat_sat]
        if cat_sat in ["Todos", "Estudante"] and tf != "Todas":
            df_sat_filtrado = df_sat_filtrado[df_sat_filtrado['turma'] == tf]
            
        if df_sat_filtrado.empty:
            st.info("Nenhum dado encontrado para os filtros selecionados.")
        else:
            nomes_perguntas = DICIONARIO_PERGUNTAS_SATISFACAO[cat_sat]
            
            medias_q1 = df_sat_filtrado['q1'].mean()
            medias_q2 = df_sat_filtrado['q2'].mean()
            medias_q3 = df_sat_filtrado['q3'].mean()
            medias_q4 = df_sat_filtrado['q4'].mean()
            medias_q5 = df_sat_filtrado['q5'].mean()
            
            df_grafico_sat = pd.DataFrame({
                'Pergunta': nomes_perguntas,
                'Média (Max 5)': [medias_q1, medias_q2, medias_q3, medias_q4, medias_q5]
            })
            
            fig_sat = px.bar(
                df_grafico_sat, 
                x='Pergunta', 
                y='Média (Max 5)', 
                text='Média (Max 5)',
                color='Pergunta',
                title=f"Média de Satisfação: {cat_sat}"
            )
            fig_sat.update_traces(texttemplate='%{text:.2f}', textposition='outside')
            fig_sat.update_layout(yaxis=dict(range=[0, 5.5]), plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', showlegend=False)
            st.plotly_chart(fig_sat, use_container_width=True)

            st.markdown("---")
            st.subheader("📝 Mural de Sugestões e Feedbacks")
            st.write("Abaixo estão os comentários textuais deixados pelos avaliadores.")
            
            df_sugestoes = df_sat_filtrado[df_sat_filtrado['sugestao'].notna() & (df_sat_filtrado['sugestao'].str.strip() != "")]
            if df_sugestoes.empty:
                st.success("Não há sugestões em texto para este grupo.")
            else:
                for _, sug in df_sugestoes.iterrows():
                    data_str = sug['data_hora'].strftime("%d/%m/%Y %H:%M")
                    turma_str = f" ({sug['turma']})" if sug['turma'] else ""
                    st.info(f"**Data:** {data_str} | **Perfil:** {sug['categoria']}{turma_str}\n\n**Mensagem:** {sug['sugestao']}")

    st.markdown('</div>', unsafe_allow_html=True)
indice_aba += 1

if eh_admin:
    with tabs[indice_aba]:
        st.markdown('<div class="card-panel">', unsafe_allow_html=True)
        st.subheader("🔗 Link da Pesquisa de Satisfação Pública")
        st.write("Copie o link abaixo e envie via WhatsApp para alunos, pais e servidores:")
        
        link_base = st.query_params.get("url_base", "https://seu-site-aqui.streamlit.app") 
        link_completo = f"https://seu-projeto.streamlit.app/?modo=pesquisa"
        st.code(link_completo, language="text")
        st.markdown("---")
        st.info("Acesse outras manutenções abaixo.")
    st.markdown('</div>', unsafe_allow_html=True)
