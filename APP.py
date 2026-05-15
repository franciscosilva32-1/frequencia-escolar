import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import execute_values
from psycopg2.pool import SimpleConnectionPool
import os
import io
import base64
import json
import unicodedata
import streamlit.components.v1 as components
from streamlit_cookies_manager import CookieManager
import tempfile

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import threading
import time

import re
import matplotlib.pyplot as plt
import matplotlib.style as mplstyle
from matplotlib.ticker import MaxNLocator
import plotly.express as px
mplstyle.use('seaborn-v0_8-whitegrid')

try:
    from fpdf import FPDF
except ImportError:
    FPDF = None

# ------------------------------------------------------------
# 1. CONFIGURAÇÃO GERAL E CREDENCIAIS (USE SECRETS!)
# ------------------------------------------------------------
st.set_page_config(page_title="Centro Educa Mais Jansen Veloso", page_icon="🏫", layout="wide", initial_sidebar_state="collapsed")

if 'fila_offline' not in st.session_state: st.session_state.fila_offline = []
if 'boletim_aluno_avs' not in st.session_state: st.session_state.boletim_aluno_avs = None

cookies = CookieManager()
if not cookies.ready(): st.stop()

ATIVAR_EMAILS = True
EMAIL_ESCOLA = st.secrets.get("EMAIL_ESCOLA", "cejv.cema@gmail.com")
SENHA_APP_ESCOLA = st.secrets.get("SENHA_APP_ESCOLA", "jetkkkridsefalvd")

def obter_hora_atual(): return datetime.utcnow() - timedelta(hours=3)
def data_formatada_ptbr():
    dt = obter_hora_atual()
    meses = ["", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
    return f"{dt.day:02d} de {meses[dt.month]} de {dt.year}"

def disparar_email_background(email_destino, nome_aluno, evento, horario, data):
    try: data_formatada = datetime.strptime(data, "%Y-%m-%d").strftime("%d/%m/%Y")
    except: data_formatada = data
    assunto = f"🏫 Aviso de {evento} - Centro Educa Mais Jansen Veloso"
    texto = f"Olá, família!\n\nInformamos que o estudante {nome_aluno} registrou sua {evento} hoje ({data_formatada}) no horário exato de: {horario}.\n\nAtenciosamente,\nEquipe Jansen Veloso." if evento == "ENTRADA" else f"⚠️ ATENÇÃO, família!\n\nInformamos que o estudante {nome_aluno} registrou uma SAÍDA ANTECIPADA hoje ({data_formatada}) no horário exato de: {horario}.\n\nAtenciosamente,\nEquipe Jansen Veloso."
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
# 2. CSS (O MESMO QUE VOCÊ JÁ ESTÁ USANDO – MANTENHA O SEU ÚLTIMO CSS AQUI)
# ------------------------------------------------------------
st.markdown("""
<style>
    /* ... (seu CSS atual, não mexemos) ... */
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------
# 3. POOL DE CONEXÕES PERSISTENTE (OTIMIZAÇÃO CRÍTICA)
# ------------------------------------------------------------
DATABASE_URL = st.secrets["DATABASE_URL"]
SENHA_OPERADOR = st.secrets.get("SENHA_OPERADOR", "admin123")
SENHA_ADMIN = st.secrets.get("SENHA_ADMIN", "admin123")

@st.cache_resource
def get_connection_pool():
    """Cria um pool de conexões reutilizável durante toda a sessão."""
    return SimpleConnectionPool(1, 10, DATABASE_URL)

def conectar_bd():
    """Obtém uma conexão do pool."""
    pool = get_connection_pool()
    conn = pool.getconn()
    conn.autocommit = True
    return conn

def devolver_conn(conn):
    """Devolve a conexão ao pool."""
    get_connection_pool().putconn(conn)

# ------------------------------------------------------------
# 4. TABELAS E CACHE
# ------------------------------------------------------------
@st.cache_resource
def inicializar_tabelas():
    conn = conectar_bd()
    cur = conn.cursor()
    try:
        cur.execute('''CREATE TABLE IF NOT EXISTS alunos_v2 (codigo TEXT PRIMARY KEY, nome TEXT, turma TEXT)''')
        cur.execute("ALTER TABLE alunos_v2 ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'ATIVO'")
        cur.execute("ALTER TABLE alunos_v2 ADD COLUMN IF NOT EXISTS email_responsavel TEXT")
        cur.execute('''CREATE TABLE IF NOT EXISTS registros_v2 (id SERIAL PRIMARY KEY, codigo_aluno TEXT REFERENCES alunos_v2(codigo), data DATE, hora_entrada TIME, status_entrada TEXT, hora_saida TIME, motivo_saida TEXT, pais_informados BOOLEAN, tipo_registro TEXT, UNIQUE(codigo_aluno, data, tipo_registro))''')
        cur.execute('''CREATE TABLE IF NOT EXISTS avaliacoes_avs (id SERIAL PRIMARY KEY, periodo TEXT, area TEXT, turma TEXT, nome TEXT, disciplina TEXT, questao INTEGER, resposta TEXT, gabarito TEXT, acerto INTEGER, UNIQUE(periodo, area, turma, nome, disciplina, questao))''')
    finally:
        devolver_conn(conn)
inicializar_tabelas()

# ------------------------------------------------------------
# 5. FUNÇÕES DE NEGÓCIO (COM CACHE ONDE POSSÍVEL)
# ------------------------------------------------------------
@st.cache_data(ttl=300)
def carregar_alunos():
    conn = conectar_bd()
    try:
        df = pd.read_sql_query("SELECT codigo, nome, turma, status, email_responsavel FROM alunos_v2 ORDER BY turma, nome", conn)
        return df
    finally:
        devolver_conn(conn)

def importar_csv_para_bd(arquivo_csv):
    conteudo = arquivo_csv.read()
    try: texto = conteudo.decode('utf-8-sig')
    except: texto = conteudo.decode('latin-1')
    df = pd.read_csv(io.StringIO(texto), sep=';')
    def normalizar_coluna(nome_col): return ''.join(c for c in unicodedata.normalize('NFD', str(nome_col)) if unicodedata.category(c) != 'Mn').strip().upper()
    df.columns = [normalizar_coluna(col) for col in df.columns]
    if 'CODIGO' not in df.columns or 'NOME' not in df.columns or 'TURMA' not in df.columns: return False
    conn = conectar_bd(); cur = conn.cursor()
    try:
        for _, row in df.iterrows():
            codigo, nome, turma = str(row['CODIGO']).strip().upper(), str(row['NOME']).strip().upper(), str(row['TURMA']).strip().upper()
            if codigo == 'NAN' or nome == 'NAN': continue
            cur.execute("INSERT INTO alunos_v2 (codigo, nome, turma, status) VALUES (%s, %s, %s, 'ATIVO') ON CONFLICT (codigo) DO UPDATE SET nome = EXCLUDED.nome, turma = EXCLUDED.turma", (codigo, nome, turma))
    finally:
        devolver_conn(conn)
    st.cache_data.clear()
    return True

def adicionar_aluno_manual(codigo, nome, turma):
    conn = conectar_bd(); cur = conn.cursor()
    try:
        cur.execute("INSERT INTO alunos_v2 (codigo, nome, turma, status) VALUES (%s, %s, %s, 'ATIVO')", (codigo.strip().upper(), nome.strip().upper(), turma.strip().upper()))
        st.cache_data.clear()
        return True
    except psycopg2.errors.UniqueViolation: return "duplicado"
    except: return False
    finally: devolver_conn(conn)

def atualizar_email_aluno(codigo, email):
    conn = conectar_bd(); cur = conn.cursor()
    try:
        cur.execute("UPDATE alunos_v2 SET email_responsavel = %s WHERE codigo = %s", (email.strip().lower(), codigo))
        st.cache_data.clear()
        return True
    except: return False
    finally: devolver_conn(conn)

def abrir_dia_letivo(data_str):
    conn = conectar_bd(); cur = conn.cursor()
    try:
        cur.execute("SELECT codigo FROM alunos_v2 WHERE status = 'ATIVO'")
        alunos = [row[0] for row in cur.fetchall()]
        faltas_geradas = 0
        for codigo in alunos:
            cur.execute("SELECT id FROM registros_v2 WHERE codigo_aluno = %s AND data = %s", (codigo, data_str))
            if not cur.fetchone():
                cur.execute("INSERT INTO registros_v2 (codigo_aluno, data, tipo_registro) VALUES (%s, %s, 'FALTA')", (codigo, data_str))
                faltas_geradas += 1
        return faltas_geradas
    finally:
        devolver_conn(conn)

def registrar_presenca(codigo_estudante, data_registro, hora_limite_entrada, hora_exata=None):
    agora = obter_hora_atual()
    hora_atual = hora_exata if hora_exata else agora.strftime("%H:%M:%S")
    hora_obj = datetime.strptime(hora_atual, "%H:%M:%S").time()
    status_entrada = "PRESENTE" if hora_obj <= hora_limite_entrada else "ATRASO"
    conn = conectar_bd(); cur = conn.cursor()
    try:
        cur.execute("SELECT nome, status, email_responsavel FROM alunos_v2 WHERE codigo = %s", (codigo_estudante,))
        resultado = cur.fetchone()
        if not resultado: st.error(f"❌ Código não cadastrado: {codigo_estudante}"); return False
        nome_aluno, status_aluno, email_resp = resultado
        if status_aluno != 'ATIVO': st.warning(f"⚠️ Atenção: {nome_aluno} está marcado como {status_aluno}.")
        cur.execute("SELECT * FROM registros_v2 WHERE codigo_aluno = %s AND data = %s AND tipo_registro = 'PRESENCA'", (codigo_estudante, data_registro))
        if cur.fetchone(): st.warning(f"⚠️ {nome_aluno} já tem presença registrada hoje."); return False
        cur.execute("DELETE FROM registros_v2 WHERE codigo_aluno = %s AND data = %s AND tipo_registro = 'FALTA'", (codigo_estudante, data_registro))
        cur.execute("INSERT INTO registros_v2 (codigo_aluno, data, hora_entrada, status_entrada, tipo_registro) VALUES (%s, %s, %s, %s, 'PRESENCA')", (codigo_estudante, data_registro, hora_atual, status_entrada))
        st.success(f"✅ {nome_aluno} - PRESENTE ({hora_atual})") if status_entrada == "PRESENTE" else st.warning(f"⏰ {nome_aluno} - ATRASO ({hora_atual})")
        if email_resp: disparar_email_background(email_resp, nome_aluno, "ENTRADA", hora_atual, data_registro)
        return True
    except: return False
    finally: devolver_conn(conn)

def registrar_saida(codigo_estudante, motivo, pais_informados, data_registro, hora_saida, hora_limite_saida):
    conn = conectar_bd(); cur = conn.cursor()
    try:
        cur.execute("SELECT nome, email_responsavel FROM alunos_v2 WHERE codigo = %s", (codigo_estudante,))
        resultado = cur.fetchone()
        if not resultado: st.error(f"❌ Código não encontrado."); return False
        nome_aluno, email_resp = resultado
        hora_atual = obter_hora_atual().time()
        if hora_atual < hora_limite_saida:
            cur.execute("UPDATE registros_v2 SET hora_saida = %s, motivo_saida = %s, pais_informados = %s WHERE codigo_aluno = %s AND data = %s AND tipo_registro = 'PRESENCA'", (hora_saida, motivo, pais_informados, codigo_estudante, data_registro))
            if cur.rowcount > 0:
                st.success(f"✅ Saída autorizada: {nome_aluno}")
                if email_resp: disparar_email_background(email_resp, nome_aluno, "SAÍDA ANTECIPADA", hora_saida, data_registro)
                return True
            else: st.error("Erro: Aluno não tem registro de entrada hoje.")
        else: st.info("Saída no horário normal.")
        return False
    except: return False
    finally: devolver_conn(conn)

# ------------------------------------------------------------
# 6. ANALISADOR AVS (VELOZ COM CONSULTAS DIRETAS)
# ------------------------------------------------------------
@st.cache_data(ttl=30)
def carregar_dados_avs_filtrados(periodo=None, area=None, turma=None):
    """Busca SOMENTE os registros filtrados no banco de dados."""
    conn = conectar_bd()
    try:
        query = "SELECT * FROM avaliacoes_avs WHERE 1=1"
        params = []
        if periodo: query += " AND periodo = %s"; params.append(periodo)
        if area: query += " AND area = %s"; params.append(area)
        if turma: query += " AND turma = %s"; params.append(turma)
        df = pd.read_sql_query(query, conn, params=params)
        return df
    finally:
        devolver_conn(conn)

def importar_csv_avs_nuvem(arquivo_csv, periodo, area, turma):
    conteudo = arquivo_csv.read()
    try: texto = conteudo.decode('utf-8-sig')
    except: texto = conteudo.decode('latin-1')
    temp_df = pd.read_csv(io.StringIO(texto), sep=';')
    temp_df.columns = [str(c).strip() for c in temp_df.columns]
    col_options = [c for c in temp_df.columns if re.search(r'^Q\s*\d+\s*Options', c, re.IGNORECASE)]
    if not col_options: return False, "Nenhuma coluna de questão."
    idx_not_attempted = next((i for i, c in enumerate(temp_df.columns) if re.match(r'^Not\s+attempted', c, re.IGNORECASE)), -1)
    idx_first_q = temp_df.columns.get_loc(col_options[0])
    disciplinas = [str(c).strip().upper() for c in temp_df.columns[idx_not_attempted+1:idx_first_q] if c and not str(c).startswith('Unnamed') and 'AV' not in str(c).upper()] if idx_not_attempted != -1 and idx_first_q > idx_not_attempted+1 else [area.upper()]
    questoes_por_disc = len(col_options) // len(disciplinas)
    dados_longos = []
    for _, row in temp_df.iterrows():
        nome = str(row.get('Nome', '')).strip()
        if not nome or nome.lower() == 'nan': continue
        for i, col_opt in enumerate(col_options):
            d_idx = min(i // questoes_por_disc, len(disciplinas)-1)
            q_num = int(re.search(r'Q\s*(\d+)', col_opt, re.IGNORECASE).group(1)) if re.search(r'Q\s*(\d+)', col_opt, re.IGNORECASE) else (i+1)
            resp = str(row.get(col_opt, '')).strip().upper()
            resp = 'BRANCO' if not resp or resp == 'NAN' else ('DUPLA' if len(resp) > 1 else resp)
            gab = str(row.get(col_opt.replace('Options', 'Key'), '')).strip().upper()
            acerto = 1 if resp == gab and resp != 'BRANCO' else 0
            dados_longos.append((periodo, area, turma, nome, disciplinas[d_idx], q_num, resp, gab, acerto))
    if not dados_longos: return False, "Nenhum dado."
    conn = conectar_bd(); cur = conn.cursor()
    try:
        execute_values(cur, "INSERT INTO avaliacoes_avs (periodo, area, turma, nome, disciplina, questao, resposta, gabarito, acerto) VALUES %s ON CONFLICT (periodo, area, turma, nome, disciplina, questao) DO UPDATE SET resposta=EXCLUDED.resposta, gabarito=EXCLUDED.gabarito, acerto=EXCLUDED.acerto", dados_longos, page_size=2000)
        st.cache_data.clear()
        return True, f"{len(dados_longos)} registros inseridos."
    except Exception as e: return False, str(e)
    finally: devolver_conn(conn)

def excluir_dados_avs(periodo, area, turma):
    conn = conectar_bd(); cur = conn.cursor()
    try:
        cur.execute("DELETE FROM avaliacoes_avs WHERE periodo = %s AND area = %s AND turma = %s", (periodo, area, turma))
        linhas = cur.rowcount
        st.cache_data.clear()
        return linhas
    finally: devolver_conn(conn)

@st.cache_data
def gerar_pdf_boletim(aluno_nome, turma, nota, df_bol):
    if FPDF is None: return None
    pdf = FPDF(); pdf.add_page()
    pdf.set_fill_color(10,31,53); pdf.rect(0,0,210,40,'F')
    pdf.set_text_color(255,255,255); pdf.set_font("Arial","B",22)
    pdf.cell(0,15,"BOLETIM AVS",0,1,"C"); pdf.set_font("Arial","",12)
    pdf.cell(0,10,f"Centro Educa Mais Jansen Veloso | {datetime.now().strftime('%d/%m/%Y')}",0,1,"C")
    pdf.ln(15); pdf.set_text_color(0,0,0); pdf.set_font("Arial","B",14)
    pdf.cell(0,10,f"ALUNO: {aluno_nome}   TURMA: {turma}   NOTA: {nota:.2f}",0,1)
    pdf.ln(5)
    for _, q in df_bol.sort_values(['periodo','disciplina','questao']).iterrows():
        cor = (16,185,129) if q['acerto']==1 else ((245,158,11) if q['resposta']=='BRANCO' else (239,68,68))
        pdf.set_fill_color(*cor); pdf.set_text_color(255,255,255)
        pdf.rect(10 + ((q['questao']-1)%8)*24, pdf.get_y(), 22, 14, 'F')
        pdf.text(10 + ((q['questao']-1)%8)*24+2, pdf.get_y()+5, f"Q{q['questao']}")
        pdf.text(10 + ((q['questao']-1)%8)*24+2, pdf.get_y()+12, f"R:{q['resposta']}")
        if q['questao']%8==0: pdf.ln(16)
    pdf_bytes = pdf.output()
    return pdf_bytes.encode('latin-1') if isinstance(pdf_bytes, str) else bytes(pdf_bytes)

# ------------------------------------------------------------
# 7. COMPONENTE CÂMERA (INALTERADO)
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
# 8. AUTENTICAÇÃO
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
        col_log1, col_log2, col_log3 = st.columns([1.5, 1, 1.5])
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
    col_main1, col_main2, col_main3 = st.columns([1.5, 1, 1.5])
    with col_main2: st.image("logo.png", use_container_width=True)

st.markdown('<p class="main-title">SISTEMA DE FREQUÊNCIA</p>', unsafe_allow_html=True)
st.markdown(f'<p class="sub-title">Centro Educa Mais Jansen Veloso • {data_formatada_ptbr()}</p>', unsafe_allow_html=True)
c1, c2 = st.columns([8, 1]); c2.button("SAIR", on_click=lambda: (cookies.update({"auth_token": ""}), cookies.save(), st.rerun()))

df_alunos = carregar_alunos()
hoje_str = obter_hora_atual().strftime("%Y-%m-%d")

# Métricas cacheadas
@st.cache_data(ttl=60)
def obter_metricas_hoje(hoje):
    conn = conectar_bd()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(CASE WHEN tipo_registro='PRESENCA' THEN 1 END), COUNT(CASE WHEN tipo_registro='FALTA' THEN 1 END), COUNT(CASE WHEN tipo_registro='PRESENCA' AND status_entrada='ATRASO' THEN 1 END) FROM registros_v2 WHERE data=%s", (hoje,))
        pres, falt, atras = cur.fetchone()
        return pres or 0, falt or 0, atras or 0
    finally:
        devolver_conn(conn)

pres_hoje, falt_hoje, atras_hoje = obter_metricas_hoje(hoje_str)
total_ativos = len(df_alunos[df_alunos['status'] == 'ATIVO']) if not df_alunos.empty else 0

st.markdown(f'''
<div class="metrics-container">
    <div class="metric-card m-total"><span class="m-val">{total_ativos}</span><span class="m-lab">📋 Alunos Ativos</span></div>
    <div class="metric-card m-presente"><span class="m-val">{pres_hoje}</span><span class="m-lab">✅ Presentes</span></div>
    <div class="metric-card m-falta"><span class="m-val">{falt_hoje}</span><span class="m-lab">❌ Faltas</span></div>
    <div class="metric-card m-atraso"><span class="m-val">{atras_hoje}</span><span class="m-lab">⏰ Atrasos</span></div>
</div>
''', unsafe_allow_html=True)

abas = ["📝 Registro", "📊 Gestão", "🚨 Alertas", "📈 Histórico", "⚙️ Manutenção", "📑 Analisador AVS"] if st.session_state.eh_admin else ["📝 Registro", "📊 Gestão", "🚨 Alertas", "📈 Histórico"]
tabs = st.tabs(abas)

# ABA REGISTRO (mantida igual, só usando pool)
with tabs[0]:
    # ... (código idêntico ao seu último, apenas substitua conectar_bd() e devolver_conn() conforme já está)
    pass  # substituir pelo conteúdo real da aba registro

# As demais abas também mantêm a lógica, mas sempre usando conectar_bd() e devolver_conn().

# =================================================================================
# ABA ANALISADOR AVS (USANDO CONSULTAS DIRETAS)
# =================================================================================
if st.session_state.eh_admin:
    with tabs[5]:
        st.title("📊 AVS Analytics PRO")
        PERIODOS = ["1º Período", "2º Período", "3º Período", "4º Período"]
        AREAS = ["LÍNGUA PORTUGUESA", "MATEMÁTICA", "LINGUAGENS", "HUMANAS", "NATUREZA"]
        TURMAS_LISTA = sorted(df_alunos['turma'].unique()) if not df_alunos.empty else []

        c_f1, c_f2, c_f3 = st.columns(3)
        with c_f1: p_filtro = st.selectbox("Período", ["Todos"] + PERIODOS, key="avs_p")
        with c_f2: a_filtro = st.selectbox("Área", ["Todas"] + AREAS, key="avs_a")
        with c_f3: t_filtro = st.selectbox("Turma", ["Todas"] + TURMAS_LISTA, key="avs_t")

        # Carrega somente os dados filtrados
        filtro_p = None if p_filtro == "Todos" else p_filtro
        filtro_a = None if a_filtro == "Todas" else a_filtro
        filtro_t = None if t_filtro == "Todas" else t_filtro
        df_filtrado = carregar_dados_avs_filtrados(filtro_p, filtro_a, filtro_t)

        abas_avs = st.tabs(["🏆 Destaques", "🧑‍🎓 Estudantes", "📈 Gráficos", "📋 Questões", "📉 Críticas", "⚙️ Gerenciar Dados"])

        # ... (as sub-abas permanecem com a mesma lógica, mas agora df_filtrado já vem filtrado, sem necessidade de filtrar novamente)
        # Elas devem usar df_filtrado diretamente.
