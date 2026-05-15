import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import psycopg2
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
# 2. CSS PREMIUM (VISUALIZAÇÃO AMPLIADA E CORES ALTERNADAS)
# ------------------------------------------------------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap');
    :root { --primary: #0a1f35; --accent: #ff7b00; --success: #10b981; --danger: #ef4444; --bg-color: #f8fafc; }
    .stApp { background: var(--bg-color); }
    #MainMenu, footer, header {visibility: hidden;}
    
    html, body, [class*="css"], p, span, label, div { font-size: 1.15rem !important; }

    .main-title { font-family: 'Inter', sans-serif; font-weight: 900; font-size: clamp(2.8rem, 7vw, 3.8rem); color: var(--primary); text-align: center; margin:0; text-transform: uppercase; letter-spacing: -1px;}
    .sub-title { font-family: 'Inter', sans-serif; font-size: 1.4rem; color: #64748b; text-align: center; margin-bottom: 2rem; font-weight: 700;}
    .metrics-container { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1.5rem; margin-bottom: 2.5rem; }
    @media (max-width: 800px) { .metrics-container { grid-template-columns: 1fr; } }
    .metric-card { background: white; padding: 2.2rem 1rem; border-radius: 16px; box-shadow: 0 4px 10px rgba(0,0,0,0.04); text-align: center; position: relative; overflow: hidden; border: 1px solid #e2e8f0; }
    .metric-card::before { content: ''; position: absolute; top: 0; left: 0; right: 0; height: 8px; }
    .m-total::before { background: #0ea5e9; } .m-presente::before { background: var(--success); } .m-falta::before { background: var(--danger); } .m-atraso::before { background: #f59e0b; } 
    .m-val { font-size: 3.8rem; font-weight: 900; color: #1e293b; display: block; line-height: 1.2; }
    .m-lab { font-size: 1.2rem; font-weight: 800; color: #64748b; text-transform: uppercase; letter-spacing: 1px; margin-top: 0.5rem; display: block; }
    
    .stTabs [data-baseweb="tab-list"] { gap: 10px; padding-bottom: 0px; flex-wrap: wrap; }
    .stTabs [data-baseweb="tab"] { background-color: #f1f5f9 !important; border: 3px solid #cbd5e1 !important; border-bottom: none !important; border-radius: 18px 18px 0 0 !important; padding: 15px 25px !important; font-size: 1.5rem !important; font-weight: 900 !important; color: #64748b !important; transition: all 0.3s ease !important; }
    .stTabs [data-baseweb="tab"]:hover { background-color: #e2e8f0 !important; color: var(--primary) !important; }
    .stTabs [aria-selected="true"] { background-color: var(--primary) !important; color: #ffffff !important; border: 5px solid var(--accent) !important; border-bottom: none !important; transform: translateY(-4px); box-shadow: 0 -8px 25px rgba(255, 123, 0, 0.35) !important; }
    
    .card-panel { background: white; border-radius: 20px; padding: 2.2rem; margin-bottom: 1.5rem; box-shadow: 0 8px 20px rgba(0,0,0,0.03); border: 2px solid #e2e8f0; }
    
    div[data-baseweb="input"] { border: 2px solid #cbd5e1 !important; border-radius: 12px !important; background-color: #ffffff !important; }
    div[data-baseweb="input"] input { color: #000000 !important; -webkit-text-fill-color: #000000 !important; font-weight: 900 !important; font-size: 1.5rem !important; padding: 1rem 1.2rem !important; }
    div[data-baseweb="input"]:focus-within { border-color: var(--accent) !important; box-shadow: 0 0 0 4px rgba(255, 123, 0, 0.2) !important; }
    div[data-baseweb="select"] > div { border: 2px solid #cbd5e1 !important; border-radius: 12px !important; background-color: #ffffff !important; color: #000000 !important; font-weight: 800 !important; font-size: 1.4rem !important; padding: 0.5rem;}
    
    .stButton > button { border-radius: 12px !important; font-weight: 800 !important; font-size: 1.3rem !important; padding: 0.8rem 2rem !important; border: none !important; transition: all 0.2s ease !important; }
    [data-testid="stFormSubmitButton"] > button { background: linear-gradient(135deg, var(--primary), #1a4b82) !important; color: white !important; box-shadow: 0 6px 15px rgba(10, 31, 53, 0.3) !important; width: 100% !important; text-transform: uppercase !important; font-size: 1.4rem !important;}
    [data-testid="stFormSubmitButton"] > button:active { transform: scale(0.95); }
    
    .login-card { max-width: 500px; margin: 8vh auto; background: white; border-radius: 24px; padding: 3rem 2rem; text-align: center; box-shadow: 0 20px 40px rgba(0,0,0,0.1); border: 3px solid var(--primary); }
    .login-title { font-size: 2.2rem; font-weight: 900; color: var(--primary); margin-bottom: 1.5rem; }
    
    [data-testid="stDataFrame"] { font-size: 1.2rem !important; }
    .streamlit-expanderHeader { font-size: 1.3rem !important; font-weight: bold !important; }

    /* Estilo Especial para o Top 7 */
    .top7-card { background: linear-gradient(135deg, #f8fafc, #f1f5f9); border-left: 8px solid var(--accent); padding: 1.5rem; border-radius: 12px; margin-bottom: 1rem; box-shadow: 0 4px 10px rgba(0,0,0,0.05); text-align: center;}
    .top7-medal { font-size: 2rem; font-weight: 900; color: var(--primary); margin-bottom: 0.5rem;}
    .top7-name { font-size: 2.5rem; font-weight: 900; color: #1e293b; letter-spacing: -1px; margin: 0.5rem 0;}
    .top7-name-hidden { font-size: 2.5rem; font-weight: 900; color: #94a3b8; filter: blur(4px); user-select: none; margin: 0.5rem 0;}
    .top7-details { font-size: 1.3rem; color: #64748b; font-weight: 700;}
    
    /* Cores Alternadas nos Estudantes (Pula de 2 em 2 por causa do HTML gerado pelo Streamlit) */
    div[data-testid="stExpander"]:nth-child(even) { background-color: #f8fafc; border-radius: 12px; border: 1px solid #cbd5e1; }
    div[data-testid="stExpander"]:nth-child(odd) { background-color: #e2e8f0; border-radius: 12px; border: 1px solid #94a3b8; }
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------
# 3. CONEXÃO BANCO DE DADOS (VACINA CONTRA CONEXÃO SUJA)
# ------------------------------------------------------------
DATABASE_URL = st.secrets.get("DATABASE_URL", os.environ.get("DATABASE_URL"))
SENHA_OPERADOR = st.secrets.get("SENHA_OPERADOR", "admin123")
SENHA_ADMIN = st.secrets.get("SENHA_ADMIN", "admin123")

if not DATABASE_URL: st.error("DATABASE_URL não configurada."); st.stop()

def conectar_bd():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True 
    return conn

def inicializar_tabelas():
    try:
        conn = conectar_bd()
        cur = conn.cursor()
        cur.execute('''CREATE TABLE IF NOT EXISTS alunos_v2 (codigo TEXT PRIMARY KEY, nome TEXT, turma TEXT)''')
        cur.execute("ALTER TABLE alunos_v2 ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'ATIVO'")
        cur.execute("ALTER TABLE alunos_v2 ADD COLUMN IF NOT EXISTS email_responsavel TEXT")
        cur.execute('''CREATE TABLE IF NOT EXISTS registros_v2 (id SERIAL PRIMARY KEY, codigo_aluno TEXT REFERENCES alunos_v2(codigo), data DATE, hora_entrada TIME, status_entrada TEXT, hora_saida TIME, motivo_saida TEXT, pais_informados BOOLEAN, tipo_registro TEXT, UNIQUE(codigo_aluno, data, tipo_registro))''')
        cur.execute('''CREATE TABLE IF NOT EXISTS avaliacoes_avs (id SERIAL PRIMARY KEY, periodo TEXT, area TEXT, turma TEXT, nome TEXT, disciplina TEXT, questao INTEGER, resposta TEXT, gabarito TEXT, acerto INTEGER, UNIQUE(periodo, area, turma, nome, disciplina, questao))''')
        conn.close()
    except Exception as e:
        pass 

inicializar_tabelas()

# ------------------------------------------------------------
# 4. FUNÇÕES DE NEGÓCIO
# ------------------------------------------------------------
@st.cache_data(ttl=300)
def carregar_alunos():
    try:
        conn = conectar_bd()
        df = pd.read_sql_query("SELECT codigo, nome, turma, status, email_responsavel FROM alunos_v2 ORDER BY turma, nome", conn)
        conn.close()
        return df
    except Exception:
        return pd.DataFrame(columns=['codigo', 'nome', 'turma', 'status', 'email_responsavel'])

def importar_csv_para_bd(arquivo_csv):
    conteudo = arquivo_csv.read()
    try: texto = conteudo.decode('utf-8-sig')
    except: texto = conteudo.decode('latin-1')
    df = pd.read_csv(io.StringIO(texto), sep=';')
    def normalizar_coluna(nome_col): return ''.join(c for c in unicodedata.normalize('NFD', str(nome_col)) if unicodedata.category(c) != 'Mn').strip().upper()
    df.columns = [normalizar_coluna(col) for col in df.columns]
    if 'CODIGO' not in df.columns or 'NOME' not in df.columns or 'TURMA' not in df.columns: return False
    conn = conectar_bd(); cur = conn.cursor()
    for _, row in df.iterrows():
        codigo, nome, turma = str(row['CODIGO']).strip().upper(), str(row['NOME']).strip().upper(), str(row['TURMA']).strip().upper()
        if codigo == 'NAN' or nome == 'NAN': continue
        try: cur.execute("INSERT INTO alunos_v2 (codigo, nome, turma, status) VALUES (%s, %s, %s, 'ATIVO') ON CONFLICT (codigo) DO UPDATE SET nome = EXCLUDED.nome, turma = EXCLUDED.turma", (codigo, nome, turma))
        except: pass
    conn.close(); st.cache_data.clear(); return True

def adicionar_aluno_manual(codigo, nome, turma):
    conn = conectar_bd(); cur = conn.cursor()
    try:
        cur.execute("INSERT INTO alunos_v2 (codigo, nome, turma, status) VALUES (%s, %s, %s, 'ATIVO')", (codigo.strip().upper(), nome.strip().upper(), turma.strip().upper()))
        st.cache_data.clear(); return True
    except psycopg2.errors.UniqueViolation: return "duplicado"
    except: return False
    finally: conn.close()

def alterar_status_aluno(codigo, novo_status):
    try:
        conn = conectar_bd(); cur = conn.cursor()
        cur.execute("UPDATE alunos_v2 SET status = %s WHERE codigo = %s", (novo_status, codigo))
        conn.close(); st.cache_data.clear()
    except: pass

def atualizar_email_aluno(codigo, email):
    try:
        conn = conectar_bd(); cur = conn.cursor()
        cur.execute("UPDATE alunos_v2 SET email_responsavel = %s WHERE codigo = %s", (email.strip().lower(), codigo))
        st.cache_data.clear(); return True
    except: return False
    finally: conn.close()

def abrir_dia_letivo(data_str):
    try:
        conn = conectar_bd(); cur = conn.cursor()
        cur.execute("SELECT codigo FROM alunos_v2 WHERE status = 'ATIVO'")
        alunos = [row[0] for row in cur.fetchall()]; faltas_geradas = 0
        for codigo in alunos:
            cur.execute("SELECT id FROM registros_v2 WHERE codigo_aluno = %s AND data = %s", (codigo, data_str))
            if not cur.fetchone():
                try: cur.execute("INSERT INTO registros_v2 (codigo_aluno, data, tipo_registro) VALUES (%s, %s, 'FALTA')", (codigo, data_str)); faltas_geradas += 1
                except: pass
        conn.close(); return faltas_geradas
    except: return 0

def registrar_presenca(codigo_estudante, data_registro, hora_limite_entrada, hora_exata=None):
    agora = obter_hora_atual()
    hora_atual = hora_exata if hora_exata else agora.strftime("%H:%M:%S")
    hora_obj = datetime.strptime(hora_atual, "%H:%M:%S").time()
    status_entrada = "PRESENTE" if hora_obj <= hora_limite_entrada else "ATRASO"
    try:
        conn = conectar_bd(); cur = conn.cursor()
        cur.execute("SELECT nome, status, email_responsavel FROM alunos_v2 WHERE codigo = %s", (codigo_estudante,))
        resultado = cur.fetchone()
        if not resultado: st.error(f"❌ Código não cadastrado: {codigo_estudante}"); conn.close(); return False
        nome_aluno, status_aluno, email_resp = resultado
        if status_aluno != 'ATIVO': st.warning(f"⚠️ Atenção: {nome_aluno} está marcado como {status_aluno}.")
        cur.execute("SELECT * FROM registros_v2 WHERE codigo_aluno = %s AND data = %s AND tipo_registro = 'PRESENCA'", (codigo_estudante, data_registro))
        if cur.fetchone(): st.warning(f"⚠️ {nome_aluno} já tem presença registrada hoje."); conn.close(); return False
        cur.execute("DELETE FROM registros_v2 WHERE codigo_aluno = %s AND data = %s AND tipo_registro = 'FALTA'", (codigo_estudante, data_registro))
        
        cur.execute("INSERT INTO registros_v2 (codigo_aluno, data, hora_entrada, status_entrada, tipo_registro) VALUES (%s, %s, %s, %s, 'PRESENCA')", (codigo_estudante, data_registro, hora_atual, status_entrada))
        if status_entrada == "PRESENTE": st.success(f"✅ {nome_aluno} - PRESENTE ({hora_atual})")
        else: st.warning(f"⏰ {nome_aluno} - ATRASO ({hora_atual})")
        if email_resp: disparar_email_background(email_resp, nome_aluno, "ENTRADA", hora_atual, data_registro)
        return True
    except: return False
    finally: 
        try: conn.close()
        except: pass

def registrar_saida(codigo_estudante, motivo, pais_informados, data_registro, hora_saida, hora_limite_saida):
    try:
        conn = conectar_bd(); cur = conn.cursor()
        cur.execute("SELECT nome, email_responsavel FROM alunos_v2 WHERE codigo = %s", (codigo_estudante,))
        resultado = cur.fetchone()
        if not resultado: st.error(f"❌ Código não encontrado."); conn.close(); return False
        nome_aluno, email_resp = resultado
        hora_atual = obter_hora_atual().time()
        if hora_atual < hora_limite_saida:
            cur.execute("UPDATE registros_v2 SET hora_saida = %s, motivo_saida = %s, pais_informados = %s WHERE codigo_aluno = %s AND data = %s AND tipo_registro = 'PRESENCA'", (hora_saida, motivo, pais_informados, codigo_estudante, data_registro))
            if cur.rowcount > 0:
                st.success(f"✅ Saída autorizada: {nome_aluno}")
                if email_resp: disparar_email_background(email_resp, nome_aluno, "SAÍDA ANTECIPADA", hora_saida, data_registro)
                conn.close(); return True
            else: st.error("Erro: Aluno não tem registro de entrada hoje.")
        else: st.info("Saída no horário normal. (E-mail não acionado)")
        conn.close(); return False
    except: return False

def limpar_todos_registros():
    try: conn = conectar_bd(); cur = conn.cursor(); cur.execute("DELETE FROM registros_v2"); conn.close()
    except: pass

@st.cache_data(ttl=60)
def carregar_dados_avs():
    try:
        conn = conectar_bd()
        df = pd.read_sql_query("SELECT * FROM avaliacoes_avs", conn)
        conn.close()
        return df
    except Exception: 
        return pd.DataFrame() 

def importar_csv_avs_nuvem(arquivo_csv, periodo, area, turma):
    conteudo = arquivo_csv.read()
    try: texto = conteudo.decode('utf-8-sig')
    except: texto = conteudo.decode('latin-1')
    temp_df = pd.read_csv(io.StringIO(texto), sep=';')
    temp_df.columns = [str(c).strip() for c in temp_df.columns]
    col_options = [c for c in temp_df.columns if re.search(r'^Q\s*\d+\s*Options', c, re.IGNORECASE)]
    if not col_options: return False, "Nenhuma coluna de questão encontrada."
    idx_not_attempted = next((i for i, c in enumerate(temp_df.columns) if re.match(r'^Not\s+attempted', c, re.IGNORECASE)), -1)
    idx_first_q = temp_df.columns.get_loc(col_options[0])
    disciplinas = []
    if idx_not_attempted != -1 and idx_first_q > idx_not_attempted + 1:
        cols_disc = temp_df.columns[idx_not_attempted+1 : idx_first_q]
        disciplinas = [str(c).strip().upper() for c in cols_disc if c and not str(c).startswith('Unnamed') and 'AV' not in str(c).upper()]
    if not disciplinas: disciplinas = [area.upper()]
    questoes_por_disc = len(col_options) // len(disciplinas)

    dados_longos = []
    for _, row in temp_df.iterrows():
        nome = str(row.get('Nome', '')).strip()
        if pd.isna(row.get('Nome')) or not nome or nome == 'nan': continue
        for i, col_opt in enumerate(col_options):
            d_idx = min(i // questoes_por_disc, len(disciplinas) - 1)
            q_match = re.search(r'Q\s*(\d+)', col_opt, re.IGNORECASE)
            resp_bruta = row.get(col_opt)
            resp = 'BRANCO' if pd.isna(resp_bruta) or str(resp_bruta).strip().upper() in ['', 'NAN'] else str(resp_bruta).strip().upper()
            if len(resp) > 1 and resp != 'BRANCO': resp = 'DUPLA'
            gab_bruta = row.get(col_opt.replace('Options', 'Key')) if col_opt.replace('Options', 'Key') in temp_df.columns else None
            gabarito = '' if pd.isna(gab_bruta) else str(gab_bruta).strip().upper()
            acerto = 1 if resp == gabarito and resp != 'BRANCO' else 0
            dados_longos.append((periodo, area, turma, nome, disciplinas[d_idx], int(q_match.group(1)) if q_match else (i + 1), resp, gabarito, acerto))

    if not dados_longos: return False, "Nenhum dado processável."
    try:
        conn = conectar_bd(); cur = conn.cursor()
        inseridos = 0
        for linha in dados_longos:
            try:
                cur.execute('''INSERT INTO avaliacoes_avs (periodo, area, turma, nome, disciplina, questao, resposta, gabarito, acerto) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (periodo, area, turma, nome, disciplina, questao) DO UPDATE SET resposta=EXCLUDED.resposta, gabarito=EXCLUDED.gabarito, acerto=EXCLUDED.acerto''', linha)
                inseridos += 1
            except: pass
        conn.close(); st.cache_data.clear(); return True, f"Sucesso! {inseridos} respostas cadastradas no Banco."
    except Exception as e: return False, f"Erro ao injetar dados: {e}"

def excluir_dados_avs(periodo, area, turma):
    try:
        conn = conectar_bd(); cur = conn.cursor()
        cur.execute("DELETE FROM avaliacoes_avs WHERE periodo = %s AND area = %s AND turma = %s", (periodo, area, turma))
        linhas = cur.rowcount; conn.close(); st.cache_data.clear()
        return linhas
    except: return 0

# ------------------------------------------------------------
# 5. COMPONENTE DA CÂMERA
# ------------------------------------------------------------
def gerar_componente_camera(label_alvo, botao_alvo, id_camera):
    html_code = f"""
    <div style="display: flex; justify-content: center; margin-bottom: 15px; width: 100%; gap: 10px;">
        <button id="btn-start" style="padding: 15px 25px; background: #10b981; color: white; border: none; border-radius: 12px; cursor: pointer; font-weight: 900; width: 100%; max-width: 250px; font-size: 1.1rem; text-transform: uppercase;">📷 LIGAR CÂMERA</button>
        <button id="btn-stop" style="display:none; padding: 15px 25px; background: #ef4444; color: white; border: none; border-radius: 12px; cursor: pointer; font-weight: 900; width: 100%; max-width: 250px; font-size: 1.1rem; text-transform: uppercase;">🛑 PARAR CÂMERA</button>
    </div>
    <div id="box-camera" style="width:100%; max-width:350px; margin:auto; border-radius:16px; overflow:hidden; border: 4px solid var(--accent); background: #000; display:none;">
        <div id="reader-qr-{id_camera}" style="width:100%;"></div>
    </div>
    <script src="https://unpkg.com/html5-qrcode"></script>
    <script>
        const html5QrCode = new Html5Qrcode("reader-qr-{id_camera}"); const btnStart = document.getElementById("btn-start"); const btnStop = document.getElementById("btn-stop"); const boxCamera = document.getElementById("box-camera");
        const ligarCamera = () => {{ btnStart.style.display = 'none'; btnStop.style.display = 'inline-block'; boxCamera.style.display = 'block'; html5QrCode.start( {{ facingMode: "environment" }}, {{ fps: 15, qrbox: {{ width: 250, height: 250 }} }}, (decodedText) => {{ desligarCamera(); const inputs = window.parent.document.querySelectorAll('input[type="text"]'); for (let i = 0; i < inputs.length; i++) {{ if (inputs[i].getAttribute('aria-label') && inputs[i].getAttribute('aria-label').includes('{label_alvo}')) {{ let nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set; nativeSetter.call(inputs[i], decodedText); inputs[i].dispatchEvent(new Event('input', {{ bubbles: true}})); setTimeout(() => {{ const buttons = window.parent.document.querySelectorAll('button'); for (let j = 0; j < buttons.length; j++) {{ if (buttons[j].innerText.includes('{botao_alvo}')) {{ buttons[j].click(); break; }} }} }}, 300); break; }} }} }}, (errorMessage) => {{}} ).catch(err => {{ alert("Verifique a permissão da câmera."); desligarCamera(); }}); }};
        const desligarCamera = () => {{ if(html5QrCode.isScanning) {{ html5QrCode.stop().then(() => {{ resetUI(); }}); }} else {{ resetUI(); }} }};
        const resetUI = () => {{ btnStart.style.display = 'inline-block'; btnStop.style.display = 'none'; boxCamera.style.display = 'none'; }};
        btnStart.onclick = ligarCamera; btnStop.onclick = desligarCamera;
    </script>
    """
    components.html(html_code, height=550)

# ------------------------------------------------------------
# 6. AUTENTICAÇÃO E DASHBOARD
# ------------------------------------------------------------
def check_auth():
    if "autenticado" not in st.session_state:
        auth_cookie = cookies.get("auth_token")
        if auth_cookie:
            try:
                data = json.loads(base64.b64decode(auth_cookie).decode())
                if data.get("valido"): st.session_state.autenticado = True; st.session_state.eh_admin = data.get("eh_admin", False); return
            except: pass
        st.session_state.autenticado = False; st.session_state.eh_admin = False
def set_auth_cookie(eh_admin): token = base64.b64encode(json.dumps({"valido": True, "eh_admin": eh_admin}).encode()).decode(); cookies["auth_token"] = token; cookies.save()

check_auth()
if not st.session_state.autenticado:
    st.markdown('<div class="login-card">', unsafe_allow_html=True)
    if os.path.exists("logo.png"): 
        col_log1, col_log2, col_log3 = st.columns([1, 1, 1])
        with col_log2: st.image("logo.png", use_container_width=True)
    st.markdown('<div class="login-title">JANSEN VELOSO</div>', unsafe_allow_html=True)
    senha = st.text_input("DIGITE SUA SENHA:", type="password")
    if st.button("ACESSAR SISTEMA", use_container_width=True):
        if senha == SENHA_ADMIN: st.session_state.autenticado = True; st.session_state.eh_admin = True; set_auth_cookie(True); st.rerun()
        elif senha == SENHA_OPERADOR: st.session_state.autenticado = True; st.session_state.eh_admin = False; set_auth_cookie(False); st.rerun()
        else: st.error("Senha incorreta!")
    st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

if os.path.exists("logo.png"):
    col_main1, col_main2, col_main3 = st.columns([1, 1, 1])
    with col_main2: st.image("logo.png", use_container_width=True)

st.markdown('<p class="main-title">Sistema de Frequência</p>', unsafe_allow_html=True)
st.markdown(f'<p class="sub-title">Centro Educa Mais Jansen Veloso • {data_formatada_ptbr()}</p>', unsafe_allow_html=True)
c1, c2 = st.columns([8, 1]); c2.button("SAIR", on_click=lambda: (cookies.update({"auth_token": ""}), cookies.save(), st.rerun()))

df_alunos = carregar_alunos()
hoje_str = obter_hora_atual().strftime("%Y-%m-%d")

try:
    conn = conectar_bd(); cur = conn.cursor()
    cur.execute('''SELECT COUNT(CASE WHEN tipo_registro='PRESENCA' THEN 1 END), COUNT(CASE WHEN tipo_registro='FALTA' THEN 1 END), COUNT(CASE WHEN tipo_registro='PRESENCA' AND status_entrada='ATRASO' THEN 1 END) FROM registros_v2 WHERE data=%s''', (hoje_str,))
    pres_hoje, falt_hoje, atras_hoje = cur.fetchone(); conn.close()
except: pres_hoje, falt_hoje, atras_hoje = 0, 0, 0

total_ativos = len(df_alunos[df_alunos['status'] == 'ATIVO']) if not df_alunos.empty else 0

st.markdown(f'''
<div class="metrics-container">
    <div class="metric-card m-total"><span class="m-val">{total_ativos}</span><span class="m-lab">📋 Alunos Ativos</span></div>
    <div class="metric-card m-presente"><span class="m-val">{pres_hoje or 0}</span><span class="m-lab">✅ Presentes</span></div>
    <div class="metric-card m-falta"><span class="m-val">{falt_hoje or 0}</span><span class="m-lab">❌ Faltas</span></div>
    <div class="metric-card m-atraso"><span class="m-val">{atras_hoje or 0}</span><span class="m-lab">⏰ Atrasos</span></div>
</div>
''', unsafe_allow_html=True)

abas = ["📝 Registro", "📊 Gestão", "🚨 Alertas", "📈 Histórico", "⚙️ Manutenção", "📑 Analisador AVS"] if st.session_state.eh_admin else ["📝 Registro", "📊 Gestão", "🚨 Alertas", "📈 Histórico"]
tabs = st.tabs(abas)

# ============================ ABA 0: REGISTRO ============================
with tabs[0]:
    st.markdown('<div class="card-panel">', unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    with col1: data_registro = st.date_input("Data do registro", obter_hora_atual(), key="data_registro")
    data_str_config = data_registro.strftime("%Y-%m-%d")
    if "config_dia" not in st.session_state: st.session_state.config_dia = {}
    if data_str_config not in st.session_state.config_dia: st.session_state.config_dia[data_str_config] = {"hora_entrada": datetime.strptime("07:30", "%H:%M").time(), "hora_saida": datetime.strptime("17:00", "%H:%M").time()}
    with col2: hora_entrada = st.time_input("Horário limite", st.session_state.config_dia[data_str_config]["hora_entrada"], key="hora_entrada")
    with col3: hora_saida = st.time_input("Horário normal saída", st.session_state.config_dia[data_str_config]["hora_saida"], key="hora_saida")
    st.session_state.config_dia[data_str_config]["hora_entrada"] = hora_entrada; st.session_state.config_dia[data_str_config]["hora_saida"] = hora_saida

    if st.button("📍 ABRIR DIA LETIVO (GERAR FALTAS)", use_container_width=True):
        faltas = abrir_dia_letivo(data_str_config); st.success(f"Dia Iniciado! {faltas} alunos (Ativos) marcados como Ausentes.")
        
    tab_entrada, tab_saida = st.tabs(["✅ ENTRADA", "🚪 SAÍDA ANTECIPADA"])
    with tab_entrada:
        modo_rapido = st.toggle("⚡ Modo Fila Rápida", value=True)
        gerar_componente_camera("Código Estudante (Entrada)", "Registrar Entrada", "entrada")
        with st.form("form_in", clear_on_submit=True):
            codigo_recebido = st.text_input("Código Estudante (Entrada)", placeholder="Use o leitor ou digite...", key="input_cod_entrada")
            if st.form_submit_button("Registrar Entrada") and codigo_recebido.strip():
                aluno_codigo = codigo_recebido.strip().upper()
                if modo_rapido:
                    st.session_state.fila_offline.append({"codigo": aluno_codigo, "hora": obter_hora_atual().strftime("%H:%M:%S")})
                    st.success(f"⚡ Adicionado à fila: {aluno_codigo}")
                else: registrar_presenca(aluno_codigo, data_str_config, hora_entrada)
                st.rerun()

        components.html("""<script> const parentDoc = window.parent.document; function setFocus() { const inputs = parentDoc.querySelectorAll('input'); for (let input of inputs) { if (input.getAttribute('aria-label') && input.getAttribute('aria-label').includes('Código Estudante (Entrada)')) { input.focus(); return true; } } return false; } let attempts = 0; const intervalId = setInterval(() => { if (setFocus() || attempts > 10) clearInterval(intervalId); attempts++; }, 200); </script>""", height=0, width=0)

        if len(st.session_state.fila_offline) > 0:
            st.warning(f"⚠️ **ATENÇÃO:** Você tem **{len(st.session_state.fila_offline)}** estudante(s) na memória aguardando envio.")
            if st.button("🔄 SINCRONIZAR AGORA COM A NUVEM", type="primary", use_container_width=True):
                with st.spinner(f"Enviando dados..."):
                    sucessos = 0
                    for item in st.session_state.fila_offline:
                        if registrar_presenca(item['codigo'], data_str_config, hora_entrada, item['hora']): sucessos += 1
                        if ATIVAR_EMAILS: time.sleep(1.5)
                    st.session_state.fila_offline = []; st.success(f"🎉 Sincronização concluída! {sucessos} salvos."); st.rerun()

    with tab_saida:
        motivo = st.selectbox("Motivo", ["Consulta médica", "Mal-estar", "Outro"], key="motivo_saida")
        if motivo == "Outro": motivo = st.text_input("Especifique", key="motivo_outro")
        pais = st.radio("Pais informados?", ["Sim", "Não"], horizontal=True)
        gerar_componente_camera("Código Estudante (Saída)", "Registrar Saída", "saida")
        with st.form("form_out", clear_on_submit=True):
            codigo_saida_recebido = st.text_input("Código Estudante (Saída)", placeholder="Leia...", key="input_cod_saida")
            if st.form_submit_button("Registrar Saída") and codigo_saida_recebido.strip():
                registrar_saida(codigo_saida_recebido.strip().upper(), motivo, pais == "Sim", data_str_config, obter_hora_atual().strftime("%H:%M:%S"), hora_saida); st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# ============================ ABA 1 A 4: GESTÃO / ALERTAS / MANUTENÇÃO ============================
with tabs[1]:
    st.markdown('<div class="card-panel">', unsafe_allow_html=True); st.subheader("📊 Relatório Diário")
    c1, c2, c3, c4 = st.columns(4)
    with c1: dt_f = st.date_input("Data", obter_hora_atual(), key="data_relatorio")
    with c2: t_f = st.selectbox("Turma", ["Todas"] + sorted(df_alunos['turma'].unique()) if not df_alunos.empty else ["Todas"], key="filtro_turma_gestao")
    with c3: s_f = st.selectbox("Status", ["Todos", "Presentes", "Ausentes"], key="filtro_status_gestao")
    with c4: b_f = st.text_input("Buscar Nome", key="busca_nome_gestao")
    try:
        query = "SELECT a.codigo, a.nome, a.turma, r.tipo_registro, r.hora_entrada, r.status_entrada, r.hora_saida FROM registros_v2 r JOIN alunos_v2 a ON r.codigo_aluno = a.codigo WHERE r.data = %s"; params = [dt_f.strftime("%Y-%m-%d")]
        if t_f != "Todas": query += " AND a.turma = %s"; params.append(t_f)
        if s_f == "Presentes": query += " AND r.tipo_registro = 'PRESENCA'"
        elif s_f == "Ausentes": query += " AND r.tipo_registro = 'FALTA'"
        if b_f: query += " AND a.nome ILIKE %s"; params.append(f"%{b_f}%")
        conn = conectar_bd(); df_relatorio = pd.read_sql_query(query + " ORDER BY a.turma, a.nome", conn, params=params); conn.close()
        st.dataframe(df_relatorio, use_container_width=True, hide_index=True)
    except: st.info("Sem dados para exibir no momento.")
    st.markdown('</div>', unsafe_allow_html=True)

with tabs[2]:
    st.markdown('<div class="card-panel">', unsafe_allow_html=True); st.subheader("🚨 Alunos em Risco (5 dias ausentes)")
    dias_u = [(obter_hora_atual() - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7) if (obter_hora_atual() - timedelta(days=i)).weekday() < 5][:5]
    if dias_u:
        try:
            conn = conectar_bd(); df_risco = pd.read_sql_query("SELECT a.codigo, a.nome, a.turma FROM alunos_v2 a WHERE a.status = 'ATIVO' AND a.codigo NOT IN (SELECT DISTINCT codigo_aluno FROM registros_v2 WHERE data IN %s AND tipo_registro='PRESENCA')", conn, params=[tuple(dias_u)]); conn.close()
            if not df_risco.empty: st.error(f"{len(df_risco)} alunos em risco"); st.dataframe(df_risco, hide_index=True)
            else: st.success("Nenhum aluno ativo nesta situação.")
        except: st.info("Aguardando estabilização do banco de dados...")
    st.markdown('</div>', unsafe_allow_html=True)

with tabs[3]:
    st.markdown('<div class="card-panel">', unsafe_allow_html=True); st.subheader("📈 Histórico Individual")
    aluno_sel = st.selectbox("Selecione o aluno", [""] + [f"{r['codigo']} - {r['nome']} ({r['status']})" for _, r in df_alunos.iterrows()] if not df_alunos.empty else [], key="historico_aluno")
    if aluno_sel:
        try:
            conn = conectar_bd(); df_hist = pd.read_sql_query("SELECT data, tipo_registro, hora_entrada, status_entrada, hora_saida, motivo_saida FROM registros_v2 WHERE codigo_aluno = %s ORDER BY data DESC, hora_entrada DESC", conn, params=[aluno_sel.split(" - ")[0]]); conn.close(); st.dataframe(df_hist, hide_index=True)
        except: st.warning("Não foi possível carregar o histórico agora.")
    st.markdown('</div>', unsafe_allow_html=True)

if st.session_state.eh_admin:
    with tabs[4]:
        st.markdown('<div class="card-panel">', unsafe_allow_html=True); st.subheader("📧 Atualizar E-mail do Responsável")
        aluno_email_sel = st.selectbox("Busque pelo Aluno", [""] + [f"{r['codigo']} - {r['nome']} | {r.get('email_responsavel', 'Sem E-mail')}" for _, r in df_alunos.iterrows()], key="atualiza_email_aluno")
        novo_email = st.text_input("Digite o E-mail", key="novo_email_input")
        if st.button("SALVAR E-MAIL", type="primary") and aluno_email_sel and novo_email:
            if atualizar_email_aluno(aluno_email_sel.split(" - ")[0], novo_email): st.success("Salvo!"); st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="card-panel">', unsafe_allow_html=True); st.subheader("➕ Adicionar Estudante Manualmente")
        with st.form("form_add"):
            c1, c2, c3 = st.columns([1,2,1])
            with c1: cod = st.text_input("Matrícula", key="add_mat")
            with c2: nome = st.text_input("Nome", key="add_nome")
            with c3: turma = st.text_input("Turma", key="add_turma")
            if st.form_submit_button("CADASTRAR") and cod and nome and turma:
                adicionar_aluno_manual(cod, nome, turma); st.success("Adicionado!"); st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="card-panel">', unsafe_allow_html=True); st.subheader("⚙️ Importação em Massa (CSV)")
        up_admin = st.file_uploader("Arquivo CSV Alunos", type=["csv"], key="csv_alunos_up")
        if up_admin:
            if importar_csv_para_bd(up_admin): st.success("Atualizado!"); st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

# =================================================================================
# 📑 ABA 5: O SEU SUPER ANALISADOR AVS 100% RESTAURADO
# =================================================================================
if st.session_state.eh_admin:
    with tabs[5]:
        st.markdown('<div class="card-panel">', unsafe_allow_html=True)
        st.title("📊 AVS Analytics PRO")
        
        PERIODOS = ["1º Período", "2º Período", "3º Período", "4º Período"]
        AREAS = ["LÍNGUA PORTUGUESA", "MATEMÁTICA", "LINGUAGENS", "HUMANAS", "NATUREZA"]
        TURMAS_LISTA = sorted(df_alunos['turma'].unique()) if not df_alunos.empty else []
        DICIONARIO_ABREVIACAO = {"LÍNGUA PORTUGUESA": "L. PORT", "MATEMÁTICA": "MAT", "LINGUAGENS": "LING", "HUMANAS": "HUM", "NATUREZA": "NAT"}

        df_avs = carregar_dados_avs()
        
        # Filtros Globais
        st.markdown("##### 🔍 Filtros Globais")
        c_f1, c_f2, c_f3 = st.columns(3)
        with c_f1: p_filtro = st.selectbox("Período", ["Todos"] + PERIODOS, key="avs_periodo")
        with c_f2: a_filtro = st.selectbox("Área", ["Todas"] + AREAS, key="avs_area")
        with c_f3: t_filtro = st.selectbox("Turma", ["Todas"] + TURMAS_LISTA, key="avs_turma")
        
        df_filtrado = df_avs.copy()
        if p_filtro != "Todos" and not df_filtrado.empty: df_filtrado = df_filtrado[df_filtrado['periodo'] == p_filtro]
        if a_filtro != "Todas" and not df_filtrado.empty: df_filtrado = df_filtrado[df_filtrado['area'] == a_filtro]
        if t_filtro != "Todas" and not df_filtrado.empty: df_filtrado = df_filtrado[df_filtrado['turma'] == t_filtro]

        abas_avs = st.tabs(["🏆 Destaques", "🧑‍🎓 Estudantes", "📈 Gráficos", "📋 Questões", "📉 Críticas", "⚙️ Gerenciar Dados"])
        
        # -----------------------------------------------------------------
        # 🏆 DESTAQUES (CARD MAIOR COM REVELAÇÃO)
        # -----------------------------------------------------------------
        with abas_avs[0]:
            if df_filtrado.empty: st.info("Nenhum dado encontrado para os filtros selecionados.")
            else:
                st.subheader("🏆 Top 7 Melhores Médias")
                resumo = df_filtrado.groupby(['nome', 'turma']).agg(Total=('questao', 'count'), Acertos=('acerto', 'sum')).reset_index()
                resumo['Nota'] = (resumo['Acertos'] / resumo['Total']) * 10
                resumo = resumo.sort_values(by='Nota', ascending=False).head(7).reset_index(drop=True)
                
                status_stats = df_filtrado[df_filtrado['resposta'].isin(['BRANCO', 'DUPLA'])].groupby(['nome', 'resposta']).size().unstack(fill_value=0)
                
                for idx, row in resumo.iterrows():
                    if idx == 0: medalha = "🥇 1º Lugar"
                    elif idx == 1: medalha = "🥈 2º Lugar"
                    elif idx == 2: medalha = "🥉 3º Lugar"
                    else: medalha = f"⭐ {idx+1}º Lugar"
                    
                    nome = row['nome']
                    mostrar_nome = st.toggle("👀 Revelar Estudante", key=f"tgl_top_{idx}")
                    
                    classe_nome = "top7-name" if mostrar_nome else "top7-name-hidden"
                    texto_nome = nome if mostrar_nome else "🕵️‍♂️ ESTUDANTE OCULTO"
                    
                    st.markdown(f"""
                    <div class="top7-card">
                        <div class="top7-medal">{medalha}</div>
                        <div class="{classe_nome}">{texto_nome}</div>
                        <div class="top7-details">NOTA FINAL: {row['Nota']:.2f} &nbsp;|&nbsp; TURMA: {row['turma']}</div>
                    </div>
                    """, unsafe_allow_html=True)

        # -----------------------------------------------------------------
        # 🧑‍🎓 ESTUDANTES (COM FILTROS INTERNOS, DETALHES DE ERROS E CORES)
        # -----------------------------------------------------------------
        with abas_avs[1]:
            if df_filtrado.empty: st.info("Sem dados.")
            else:
                st.markdown("##### ⚙️ Filtros do Boletim do Estudante")
                c_est_filt1, c_est_filt2 = st.columns(2)
                with c_est_filt1: p_filtro_est = st.selectbox("Período (Boletim)", ["Todos"] + PERIODOS, key="bol_periodo")
                with c_est_filt2: a_filtro_est = st.selectbox("Área (Boletim)", ["Todas"] + AREAS, key="bol_area")
                
                st.markdown("---")
                c_est1, c_est2, c_est3 = st.columns([2, 1, 1])
                with c_est1: busca_aluno = st.text_input("Buscar por nome...", key="busca_nome_avs")
                with c_est2: filtro_desempenho = st.selectbox("Desempenho:", ["Todos", "INSUFICIENTE", "BOM", "ÓTIMO"], key="avs_desempenho")
                with c_est3: st.markdown("<br>", unsafe_allow_html=True); filtro_erros = st.checkbox("Somente c/ erros", key="avs_check_erros")

                resumo_est = df_filtrado.groupby(['nome', 'turma']).agg(Total=('questao', 'count'), Acertos=('acerto', 'sum')).reset_index()
                resumo_est['Nota'] = (resumo_est['Acertos'] / resumo_est['Total']) * 10
                status_stats_est = df_filtrado[df_filtrado['resposta'].isin(['BRANCO', 'DUPLA'])].groupby(['nome', 'resposta']).size().unstack(fill_value=0)
                
                alunos_filtrados = []
                for _, r in resumo_est.iterrows():
                    n = r['nome']
                    b = status_stats_est.at[n, 'BRANCO'] if (not status_stats_est.empty and n in status_stats_est.index and 'BRANCO' in status_stats_est.columns) else 0
                    d = status_stats_est.at[n, 'DUPLA'] if (not status_stats_est.empty and n in status_stats_est.index and 'DUPLA' in status_stats_est.columns) else 0
                    tem_erro = b > 0 or d > 0
                    
                    if busca_aluno and busca_aluno.lower() not in n.lower(): continue
                    if filtro_erros and not tem_erro: continue
                    if filtro_desempenho == "INSUFICIENTE" and r['Nota'] >= 6.0: continue
                    elif filtro_desempenho == "BOM" and (r['Nota'] < 6.0 or r['Nota'] > 7.5): continue
                    elif filtro_desempenho == "ÓTIMO" and r['Nota'] <= 7.5: continue
                    
                    alunos_filtrados.append({'nome': n, 'turma': r['turma'], 'nota': r['Nota'], 'brancos': b, 'duplas': d, 'total_q': r['Total']})

                st.write(f"**Encontrados:** {len(alunos_filtrados)} estudante(s)")
                
                for i, al in enumerate(alunos_filtrados[:50]): 
                    # CABEÇALHO SUPER INFORMATIVO NO EXPANDER
                    if al['brancos'] > 0 or al['duplas'] > 0:
                        header_info = f"👤 {al['nome']} | 🎯 Nota: {al['nota']:.2f} | ⚠️ Erros: (Brancos: {al['brancos']} | Duplas: {al['duplas']} | Tot. Questões: {al['total_q']})"
                    else:
                        header_info = f"👤 {al['nome']} | 🎯 Nota: {al['nota']:.2f} | ✅ Prova Perfeita"
                        
                    with st.expander(header_info):
                        # Aplica os filtros específicos do Boletim (Período e Área) ao abrir
                        df_boletim = df_avs[df_avs['nome'] == al['nome']]
                        if p_filtro_est != "Todos": df_boletim = df_boletim[df_boletim['periodo'] == p_filtro_est]
                        if a_filtro_est != "Todas": df_boletim = df_boletim[df_boletim['area'] == a_filtro_est]
                        
                        if df_boletim.empty:
                            st.warning("O aluno não possui registros para o Período/Área selecionados.")
                        else:
                            st.markdown("#### 📈 Evolução ao Longo do Ano")
                            progresso = df_boletim.groupby(['periodo', 'disciplina']).agg(Acertos=('acerto', 'sum'), Total=('questao', 'count')).reset_index()
                            progresso['Nota'] = (progresso['Acertos'] / progresso['Total']) * 10
                            
                            # Gráfico Interativo do Boletim (Plotly)
                            fig_b = px.line(progresso, x='periodo', y='Nota', color='disciplina', markers=True, title="Evolução por Período")
                            fig_b.update_layout(yaxis=dict(range=[-0.5, 11]), plot_bgcolor='rgba(0,0,0,0)', legend_title_text='Disciplina')
                            st.plotly_chart(fig_b, use_container_width=True)
                            
                            st.markdown("#### 📊 Médias por Disciplina (No Filtro Selecionado)")
                            medias_b = df_boletim.groupby(['disciplina', 'periodo']).agg(Nota=('acerto', lambda x: (sum(x)/len(x))*10)).reset_index()
                            for _, mb in medias_b.iterrows():
                                st.write(f"{mb['disciplina'].upper()} - {mb['periodo']} (Nota: {mb['Nota']:.1f})")
                                st.progress(mb['Nota'] / 10)
                            
                            st.markdown("#### 📋 Mapa de Questões (Visual)")
                            for disc in df_boletim['disciplina'].unique():
                                st.markdown(f"**{disc.upper()}**")
                                q_df = df_boletim[df_boletim['disciplina'] == disc].sort_values(["periodo", "questao"])
                                grid_html = '<div style="display: flex; flex-wrap: wrap; gap: 8px;">'
                                for _, q in q_df.iterrows():
                                    cor = "#10b981" if q['acerto'] == 1 else ("#f59e0b" if q['resposta'] == 'BRANCO' else "#ef4444")
                                    grid_html += f"""
                                    <div style="background-color: {cor}; color: white; padding: 8px; border-radius: 6px; width: 80px; text-align: center; font-size: 12px; font-weight: bold;">
                                        P{q['periodo'][:1]} Q{q['questao']}<br>R:{q['resposta']} G:{q['gabarito']}
                                    </div>"""
                                grid_html += '</div>'
                                st.markdown(grid_html, unsafe_allow_html=True)
                                st.markdown("<br>", unsafe_allow_html=True)

                if len(alunos_filtrados) > 50: st.info("Mostrando os 50 primeiros. Use a busca para encontrar estudantes específicos.")

        # -----------------------------------------------------------------
        # 📈 GRÁFICOS INTERATIVOS MODERNOS (PLOTLY)
        # -----------------------------------------------------------------
        with abas_avs[2]:
            if df_filtrado.empty: st.info("Sem dados.")
            else:
                st.subheader("📊 Desempenho Médio")
                tipo_grafico = st.radio("Agrupar por:", ["Área", "Disciplina"], horizontal=True, key="avs_agrupar_grafico")
                col_agrup = 'area' if tipo_grafico == "Área" else 'disciplina'
                
                resumo_graf = df_filtrado.groupby(col_agrup).agg(Acertos=('acerto', 'sum'), Total=('questao', 'count')).reset_index()
                resumo_graf['Nota'] = (resumo_graf['Acertos'] / resumo_graf['Total']) * 10
                resumo_graf = resumo_graf.sort_values('Nota')
                
                # ABREVIAÇÃO NO EIXO E NOME COMPLETO NO HOVER
                resumo_graf['Abreviacao'] = resumo_graf[col_agrup].apply(lambda x: DICIONARIO_ABREVIACAO.get(x.upper(), x[:4].upper()))
                resumo_graf['Nome Completo'] = resumo_graf[col_agrup].str.upper()
                
                media_geral = (df_filtrado['acerto'].sum() / len(df_filtrado)) * 10
                
                # PLOTLY BAR CHART
                fig_g = px.bar(resumo_graf, x='Abreviacao', y='Nota', color='Abreviacao', 
                               text='Nota', hover_data={'Nome Completo': True, 'Nota': ':.2f', 'Abreviacao': False})
                fig_g.update_traces(texttemplate='%{text:.1f}', textposition='outside', marker_line_width=1.5, opacity=0.9)
                fig_g.update_layout(
                    yaxis=dict(range=[0, 11]), 
                    plot_bgcolor='rgba(0,0,0,0)', 
                    paper_bgcolor='rgba(0,0,0,0)',
                    showlegend=False,
                    shapes=[dict(type='line', y0=media_geral, y1=media_geral, x0=-0.5, x1=len(resumo_graf)-0.5, 
                                 line=dict(color='Red', width=2, dash='dash'))]
                )
                fig_g.add_annotation(x=len(resumo_graf)-1, y=media_geral + 0.5, text=f"Média: {media_geral:.2f}", showarrow=False, font=dict(color="red", size=14))
                
                st.plotly_chart(fig_g, use_container_width=True)
                
                st.markdown("---")
                st.subheader("⚠️ Histórico de Faltas (Área inteira em branco)")
                area_stats = df_filtrado.groupby(['periodo', 'turma', 'nome', 'area']).agg(Total=('questao', 'count'), Brancos=('resposta', lambda x: (x == 'BRANCO').sum())).reset_index()
                area_stats['faltou'] = area_stats['Total'] == area_stats['Brancos']
                faltosos = area_stats[area_stats['faltou']]
                
                if faltosos.empty: st.success("Nenhuma ausência total por área encontrada.")
                else:
                    faltosos_resumo = faltosos.groupby('periodo')['nome'].nunique().reset_index(name='Total')
                    
                    fig_f = px.bar(faltosos_resumo, x='periodo', y='Total', text='Total', color_discrete_sequence=['#EF4444'])
                    fig_f.update_traces(texttemplate='%{text}', textposition='outside')
                    fig_f.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', yaxis=dict(dtick=1))
                    
                    st.plotly_chart(fig_f, use_container_width=True)
                    
                    st.write("**Lista de Alunos:**")
                    for _, f_row in faltosos.iterrows():
                        st.error(f"👤 {f_row['nome']} ({f_row['turma']}) - Deixou toda a área de **{f_row['area']}** em branco no {f_row['periodo']}.")

        # -----------------------------------------------------------------
        # 📋 QUESTÕES E PDF
        # -----------------------------------------------------------------
        with abas_avs[3]:
            if df_filtrado.empty: st.info("Sem dados.")
            else:
                col_q1, col_q2 = st.columns([3, 1])
                col_q1.subheader("📌 3 Questões mais erradas por Turma/Disciplina")
                
                if FPDF is not None:
                    if col_q2.button("📄 Exportar Relatório PDF", type="primary", key="btn_pdf_avs"):
                        pdf = FPDF()
                        pdf.add_page(); pdf.set_font("Arial", "B", 16)
                        pdf.cell(0, 10, "Relatorio de Questoes Criticas", 0, 1, "C")
                        for turma in sorted(df_filtrado['turma'].unique()):
                            t_df = df_filtrado[df_filtrado['turma'] == turma]
                            pdf.set_font("Arial", "B", 14); pdf.cell(0, 10, f"Turma: {turma}", 0, 1)
                            for disc in sorted(t_df['disciplina'].unique()):
                                d_df = t_df[t_df['disciplina'] == disc]
                                erro_q = d_df.groupby('questao').agg(Erros=('acerto', lambda x: 1 - x.mean())).reset_index()
                                erro_q['Pct_Erro'] = erro_q['Erros'] * 100
                                top3 = erro_q.nlargest(3, 'Pct_Erro')
                                if not top3.empty:
                                    pdf.set_font("Arial", "B", 12); pdf.cell(0, 8, f"Disciplina: {disc.upper()}", 0, 1)
                                    pdf.set_font("Arial", "", 10)
                                    for _, q in top3.iterrows():
                                        pdf.cell(0, 6, f"  Questao {int(q['questao'])} - {q['Pct_Erro']:.1f}% de erro", 0, 1)
                                    pdf.ln(2)
                        
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                            pdf.output(tmp.name)
                            with open(tmp.name, "rb") as f: pdf_bytes = f.read()
                        
                        st.download_button("⬇️ Baixar PDF", data=pdf_bytes, file_name="questoes_criticas.pdf", mime="application/pdf", key="dl_pdf_avs")
                else:
                    col_q2.warning("Módulo FPDF não instalado no Streamlit.")

                for turma in sorted(df_filtrado['turma'].unique()):
                    t_df = df_filtrado[df_filtrado['turma'] == turma]
                    st.markdown(f"### 🏫 {turma}")
                    for disc in sorted(t_df['disciplina'].unique()):
                        d_df = t_df[t_df['disciplina'] == disc]
                        erro_q = d_df.groupby('questao').agg(Erros=('acerto', lambda x: 1 - x.mean())).reset_index()
                        erro_q['Pct_Erro'] = erro_q['Erros'] * 100
                        top3 = erro_q.nlargest(3, 'Pct_Erro')
                        if not top3.empty:
                            st.markdown(f"**📚 {disc.upper()}**")
                            for _, q in top3.iterrows():
                                st.error(f"Q{int(q['questao'])} → {q['Pct_Erro']:.1f}% de erro")

        # -----------------------------------------------------------------
        # 📉 CRÍTICAS
        # -----------------------------------------------------------------
        with abas_avs[4]:
            if df_filtrado.empty: st.info("Sem dados.")
            else:
                st.subheader("📉 As 5 Disciplinas Mais Críticas")
                disc_stats = df_filtrado.groupby('disciplina').agg(Acertos=('acerto', 'sum'), Total=('questao', 'count')).reset_index()
                disc_stats['Nota'] = (disc_stats['Acertos'] / disc_stats['Total']) * 10
                disc_crit = disc_stats.sort_values('Nota').head(5)
                
                # CRÍTICAS EM PLOTLY
                disc_crit['Abreviacao'] = disc_crit['disciplina'].apply(lambda x: DICIONARIO_ABREVIACAO.get(x.upper(), x[:4].upper()))
                disc_crit['Nome Completo'] = disc_crit['disciplina'].str.upper()
                
                fig_c = px.bar(disc_crit, x='Abreviacao', y='Nota', color='Abreviacao', 
                               color_discrete_sequence=["#FF3D71", "#FFAA00", "#F97316", "#EAB308", "#84CC16"],
                               text='Nota', hover_data={'Nome Completo': True, 'Nota': ':.2f', 'Abreviacao': False})
                fig_c.update_traces(texttemplate='%{text:.1f}', textposition='outside')
                fig_c.update_layout(yaxis=dict(range=[0, 11]), plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', showlegend=False)
                
                st.plotly_chart(fig_c, use_container_width=True)
                
                for _, row in disc_crit.iterrows():
                    st.warning(f"📌 **{row['disciplina'].upper()}** - Média: {row['Nota']:.2f}")

        # -----------------------------------------------------------------
        # ⚙️ GERENCIAR DADOS
        # -----------------------------------------------------------------
        with abas_avs[5]:
            st.subheader("📥 Importar Novo Arquivo")
            c_up1, c_up2, c_up3 = st.columns(3)
            with c_up1: p_up = st.selectbox("Período:", PERIODOS, key="pup")
            with c_up2: a_up = st.selectbox("Área:", AREAS, key="aup")
            with c_up3: t_up = st.selectbox("Turma:", TURMAS_LISTA, key="tup")
            
            arquivo_avs = st.file_uploader("Arquivo CSV da Avaliação", type=["csv"], key="csv_avs_up")
            if st.button("PROCESSAR E SALVAR", type="primary", key="btn_salvar_avs") and arquivo_avs:
                sucesso, msg = importar_csv_avs_nuvem(arquivo_avs, p_up, a_up, t_up)
                if sucesso: st.success(msg); st.rerun()
                else: st.error(msg)
                
            st.markdown("---")
            st.subheader("🗑️ Limpeza Seletiva de Banco")
            st.write("Selecione um bloco de avaliação para excluir permanentemente da Nuvem:")
            
            if not df_avs.empty:
                blocos = df_avs[['periodo', 'area', 'turma']].drop_duplicates()
                lista_blocos = [f"{r['periodo']} | {r['area']} | {r['turma']}" for _, r in blocos.iterrows()]
                bloco_del = st.selectbox("Blocos importados:", lista_blocos, key="bloco_excluir_avs")
                
                if st.button("EXCLUIR BLOCO SELECIONADO", key="btn_excluir_avs"):
                    p_del, a_del, t_del = bloco_del.split(" | ")
                    linhas_apagadas = excluir_dados_avs(p_del, a_del, t_del)
                    st.success(f"{linhas_apagadas} registros excluídos com sucesso!"); st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)
