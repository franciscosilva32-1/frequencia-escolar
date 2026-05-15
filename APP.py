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

try:
    from fpdf import FPDF
except ImportError:
    FPDF = None

# ------------------------------------------------------------
# 1. CONFIGURAÇÃO INICIAL E COOKIES
# ------------------------------------------------------------
st.set_page_config(page_title="Centro Educa Mais Jansen Veloso", page_icon="🏫", layout="wide", initial_sidebar_state="collapsed")

if 'fila_offline' not in st.session_state: st.session_state.fila_offline = []
cookies = CookieManager()
if not cookies.ready(): st.stop()

# ------------------------------------------------------------
# 2. FUNÇÕES DE SUPORTE (TEMPO E E-MAIL)
# ------------------------------------------------------------
def obter_hora_atual(): return datetime.utcnow() - timedelta(hours=3)

def data_formatada_ptbr():
    dt = obter_hora_atual()
    meses = ["", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
    return f"{dt.day:02d} de {meses[dt.month]} de {dt.year}"

ATIVAR_EMAILS = True  
EMAIL_ESCOLA = "cejv.cema@gmail.com" 
SENHA_APP_ESCOLA = "jetkkkridsefalvd" 

def disparar_email_background(email_destino, nome_aluno, evento, horario, data):
    try: data_f = datetime.strptime(data, "%Y-%m-%d").strftime("%d/%m/%Y")
    except: data_f = data
    assunto = f"🏫 Aviso de {evento} - Jansen Veloso"
    if evento == "ENTRADA":
        texto = f"Olá, família!\n\nInformamos que o estudante {nome_aluno} registrou ENTRADA na escola hoje ({data_f}) às {horario}."
    else:
        texto = f"⚠️ ATENÇÃO!\n\nInformamos que o estudante {nome_aluno} registrou uma SAÍDA ANTECIPADA hoje ({data_f}) às {horario}.\n\nAtenciosamente,\nEquipe Jansen Veloso."
    
    msg = MIMEMultipart(); msg['From'] = EMAIL_ESCOLA; msg['To'] = email_destino; msg['Subject'] = assunto
    msg.attach(MIMEText(texto, 'plain'))
    def enviar():
        if ATIVAR_EMAILS:
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
            st.markdown(f'<div style="display: flex; justify-content: center; margin-bottom: 10px;"><img src="data:image/png;base64,{encoded_string}" width="120"></div>', unsafe_allow_html=True)
        except: pass

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
    
    .login-card { max-width: 500px; margin: 8vh auto; background: white; border-radius: 24px; padding: 3rem 2rem; text-align: center; box-shadow: 0 20px 40px rgba(0,0,0,0.1); border: 3px solid var(--primary); }
    .login-title { font-size: 2.2rem; font-weight: 900; color: var(--primary); margin-bottom: 1.5rem; }
    
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
# 4. BANCO DE DADOS E DICIONÁRIO DE MATÉRIAS
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

def conectar_bd(): return psycopg2.connect(DATABASE_URL)

def inicializar_tabelas():
    try:
        conn = conectar_bd(); cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS alunos_v2 (codigo TEXT PRIMARY KEY, nome TEXT, turma TEXT, status TEXT DEFAULT 'ATIVO', email_responsavel TEXT)")
        cur.execute("CREATE TABLE IF NOT EXISTS registros_v2 (id SERIAL PRIMARY KEY, codigo_aluno TEXT REFERENCES alunos_v2(codigo), data DATE, hora_entrada TIME, status_entrada TEXT, hora_saida TIME, motivo_saida TEXT, pais_informados BOOLEAN, tipo_registro TEXT, UNIQUE(codigo_aluno, data, tipo_registro))")
        cur.execute("CREATE TABLE IF NOT EXISTS avaliacoes_avs (id SERIAL PRIMARY KEY, periodo TEXT, area TEXT, turma TEXT, nome TEXT, disciplina TEXT, questao INTEGER, resposta TEXT, gabarito TEXT, acerto INTEGER, UNIQUE(periodo, area, turma, nome, disciplina, questao))")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_reg_data ON registros_v2(data)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_avs_geral ON avaliacoes_avs(periodo, area, turma)")
        conn.commit(); conn.close()
    except: pass

inicializar_tabelas()

# ------------------------------------------------------------
# 5. LÓGICA DE NEGÓCIO
# ------------------------------------------------------------
@st.cache_data(ttl=300)
def carregar_alunos():
    try:
        conn = conectar_bd(); df = pd.read_sql("SELECT codigo, nome, turma, status, email_responsavel FROM alunos_v2 ORDER BY turma, nome", conn); conn.close(); return df
    except: return pd.DataFrame(columns=['codigo','nome','turma','status','email_responsavel'])

def importar_csv_alunos(file):
    df = pd.read_csv(io.StringIO(file.read().decode('utf-8-sig')), sep=';')
    def norm(c): return ''.join(x for x in unicodedata.normalize('NFD', str(c)) if unicodedata.category(x) != 'Mn').strip().upper()
    df.columns = [norm(col) for col in df.columns]
    dados = [(str(r['CODIGO']).upper(), str(r['NOME']).upper(), str(r['TURMA']).upper(), 'ATIVO') for _, r in df.iterrows()]
    conn = conectar_bd(); cur = conn.cursor()
    execute_values(cur, "INSERT INTO alunos_v2 (codigo, nome, turma, status) VALUES %s ON CONFLICT (codigo) DO UPDATE SET nome=EXCLUDED.nome, turma=EXCLUDED.turma", dados)
    conn.commit(); conn.close(); st.cache_data.clear(); return True

def registrar_presenca(cod, data, h_limite):
    agora = obter_hora_atual()
    h_at = agora.strftime("%H:%M:%S")
    status = "PRESENTE" if agora.time() <= h_limite else "ATRASO"
    try:
        conn = conectar_bd(); cur = conn.cursor()
        cur.execute("SELECT nome, email_responsavel FROM alunos_v2 WHERE codigo = %s", (cod,))
        res = cur.fetchone()
        if not res: conn.close(); return "erro_cod"
        cur.execute("DELETE FROM registros_v2 WHERE codigo_aluno=%s AND data=%s AND tipo_registro='FALTA'", (cod, data))
        cur.execute("INSERT INTO registros_v2 (codigo_aluno, data, hora_entrada, status_entrada, tipo_registro) VALUES (%s, %s, %s, %s, 'PRESENCA') ON CONFLICT DO NOTHING", (cod, data, h_at, status))
        if res[1]: disparar_email_background(res[1], res[0], "ENTRADA", h_at, data)
        conn.commit(); conn.close(); return res[0]
    except: return False

def registrar_saida(cod, motivo, pais, data, h_saida):
    try:
        conn = conectar_bd(); cur = conn.cursor()
        cur.execute("SELECT nome, email_responsavel FROM alunos_v2 WHERE codigo = %s", (cod,))
        res = cur.fetchone()
        if not res: conn.close(); return False
        cur.execute("UPDATE registros_v2 SET hora_saida=%s, motivo_saida=%s, pais_informados=%s WHERE codigo_aluno=%s AND data=%s AND tipo_registro='PRESENCA'", (h_saida, motivo, pais, cod, data))
        if cur.rowcount > 0:
            if res[1]: disparar_email_background(res[1], res[0], "SAÍDA ANTECIPADA", h_saida, data)
            conn.commit(); conn.close(); return res[0]
        conn.close(); return False
    except: return False

def importar_csv_desempenho(file, periodo, area, turma):
    temp_df = pd.read_csv(io.StringIO(file.read().decode('utf-8-sig')), sep=';')
    temp_df.columns = [str(c).strip() for c in temp_df.columns]
    col_qs = [c for c in temp_df.columns if re.search(r'^Q\s*\d+\s*Options', c, re.IGNORECASE)]
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
    conn = conectar_bd(); cur = conn.cursor()
    execute_values(cur, "INSERT INTO avaliacoes_avs (periodo, area, turma, nome, disciplina, questao, resposta, gabarito, acerto) VALUES %s ON CONFLICT (periodo, area, turma, nome, disciplina, questao) DO UPDATE SET resposta=EXCLUDED.resposta, acerto=EXCLUDED.acerto", dados_l)
    conn.commit(); conn.close(); st.cache_data.clear(); return True, f"{len(dados_l)} registros salvos."

def gerar_pdf_boletim(aluno, turma, nota_g, df_b):
    if not FPDF: return None
    pdf = FPDF(); pdf.add_page()
    pdf.set_fill_color(10, 31, 53); pdf.rect(0, 0, 210, 35, 'F')
    pdf.set_font("Arial", "B", 18); pdf.set_text_color(255,255,255); pdf.cell(0, 15, "BOLETIM DE DESEMPENHO", 0, 1, "C")
    pdf.ln(20); pdf.set_text_color(0,0,0); pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, f"ESTUDANTE: {aluno}", 0, 1); pdf.cell(0, 10, f"TURMA: {turma} | MÉDIA GERAL: {nota_g:.2f}", 0, 1)
    
    pdf.set_font("Arial", "B", 8)
    pdf.cell(0, 6, "LEGENDA: VERDE = ACERTO | VERMELHO = ERRO | LARANJA = BRANCO | ROXO = DUPLA", 0, 1)
    pdf.ln(2)
    
    for p in sorted(df_b.periodo.unique()):
        pdf.set_fill_color(230,230,230); pdf.set_font("Arial", "B", 12); pdf.cell(0, 10, f"  {p}", 0, 1, fill=True)
        for d in sorted(df_b[df_b.periodo==p].disciplina.unique()):
            df_d = df_b[(df_b.periodo==p) & (df_b.disciplina==d)]
            pdf.set_font("Arial", "B", 11); pdf.cell(0, 8, f"{d} - Nota: {(df_d.acerto.mean()*10):.2f}", 0, 1)
            x, y, col = 10, pdf.get_y(), 0
            for q in df_d.sort_values('questao').to_dict('records'):
                if y > 265: pdf.add_page(); y = 20
                c = (16,185,129) if q['acerto']==1 else ((245,158,11) if q['resposta']=='BRANCO' else ((139,92,246) if q['resposta']=='DUPLA' else (239,68,68)))
                pdf.set_fill_color(*c); pdf.rect(x+(col*22), y, 20, 12, 'F'); pdf.set_text_color(255,255,255); pdf.set_font("Arial","B",8)
                pdf.text(x+(col*22)+2, y+5, f"Q{q['questao']}"); pdf.text(x+(col*22)+2, y+10, f"R:{q['resposta']}")
                col += 1
                if col > 7: col, y = 0, y+15
            y = y+15 if col > 0 else y; pdf.set_y(y+5); pdf.set_text_color(0,0,0)
    return pdf.output(dest='S').encode('latin-1')

# ------------------------------------------------------------
# 7. COMPONENTE CÂMARA (NOVO DESIGN COM CONTROLO DE LARGURA)
# ------------------------------------------------------------
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
                    input.value = txt; 
                    input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    setTimeout(() => {{ 
                        window.parent.document.querySelectorAll('button').forEach(b => {{ 
                            if(b.innerText.includes("{btn_label}")) b.click(); 
                        }}); 
                    }}, 500);
                }}
                scanner_{cam_id}.stop().then(() => {{ document.getElementById("reader-{cam_id}").style.display = "none"; }});
            }}).catch(err => console.error(err));
        }};
        document.getElementById("stop-{cam_id}").onclick = () => {{
            if(scanner_{cam_id}) {{
                scanner_{cam_id}.stop().then(() => {{
                    document.getElementById("reader-{cam_id}").style.display = "none";
                }}).catch(err => console.error(err));
            }}
        }};
    </script>
    """, height=450)

# ------------------------------------------------------------
# 8. AUTH E DASHBOARD
# ------------------------------------------------------------
auth_cookie = cookies.get("auth_token")

if not auth_cookie:
    st.markdown('<div class="login-card">', unsafe_allow_html=True)
    if os.path.exists("logo.png"):
        st.image("logo.png", width=120)
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

# --- HEADER COM LOGO E TÍTULO CENTRALIZADOS ---
c_out1, c_out2 = st.columns([10, 1])
with c_out2:
    if st.button("SAIR"): cookies["auth_token"] = ""; cookies.save(); st.rerun()

renderizar_logo_central()
st.markdown('<p class="main-title">SISTEMA DE FREQUÊNCIA</p>', unsafe_allow_html=True)
st.markdown(f'<p class="sub-title">CEMA Jansen Veloso • {data_formatada_ptbr()}</p>', unsafe_allow_html=True)

hoje = obter_hora_atual().strftime("%Y-%m-%d")
try:
    conn = conectar_bd(); cur = conn.cursor(); cur.execute("SELECT COUNT(*) FROM registros_v2 WHERE data=%s AND tipo_registro='PRESENCA'", (hoje,))
    pres_hoje = cur.fetchone()[0]; conn.close()
except: pres_hoje = 0

st.markdown(f'''
<div class="metrics-container">
    <div class="metric-card m-total"><span class="m-val">{len(df_alunos)}</span><span class="m-lab">Total Alunos</span></div>
    <div class="metric-card m-presente"><span class="m-val">{pres_hoje}</span><span class="m-lab">Presentes</span></div>
    <div class="metric-card m-falta"><span class="m-val">{len(df_alunos)-pres_hoje}</span><span class="m-lab">Faltas</span></div>
    <div class="metric-card m-atraso"><span class="m-val">--</span><span class="m-lab">Média Geral</span></div>
</div>
''', unsafe_allow_html=True)

tabs = st.tabs(["📝 Registro", "📊 Gestão", "🚨 Alertas", "📈 Histórico", "⚙️ Manutenção", "📑 Desempenho Acadêmico"])

# --- ABA 0: REGISTRO ---
with tabs[0]:
    st.markdown('<div class="card-panel">', unsafe_allow_html=True)
    h_lim_e = st.time_input("Horário Limite Entrada", datetime.strptime("07:30", "%H:%M").time())
    t_en, t_sa, t_jf = st.tabs(["✅ ENTRADA", "🚪 SAÍDA ANTECIPADA", "📝 JUSTIFICAR FALTAS"])
    
    with t_en:
        gerar_camera("Entrada", "REGISTRAR ENTRADA", "c_in")
        with st.form("f_en", clear_on_submit=True):
            cod_en = st.text_input("Código Aluno (Entrada)")
            if st.form_submit_button("REGISTRAR ENTRADA") and cod_en:
                res = registrar_presenca(cod_en.upper(), hoje, h_lim_e)
                if res == "erro_cod": st.error("Código não encontrado.")
                elif res: st.success(f"Bem-vindo, {res}!")
                
    with t_sa:
        gerar_camera("Saída", "CONFIRMAR SAÍDA", "c_out")
        with st.form("f_sa", clear_on_submit=True):
            cod_sa = st.text_input("Código Aluno (Saída)")
            mot = st.selectbox("Motivo", ["Mal-estar", "Consulta Médica", "Outros"])
            if st.form_submit_button("CONFIRMAR SAÍDA") and cod_sa:
                res = registrar_saida(cod_sa.upper(), mot, True, hoje, obter_hora_atual().strftime("%H:%M:%S"))
                if res: st.success(f"Saída de {res} autorizada!"); st.rerun()
                else: st.error("Erro: Aluno sem entrada hoje.")
                
    with t_jf:
        st.subheader("Justificar Faltas de Estudantes")
        d_just = st.date_input("Data da Falta", obter_hora_atual().date())
        conn = conectar_bd()
        df_faltas = pd.read_sql("SELECT r.codigo_aluno, a.nome, a.turma, r.motivo_saida FROM registros_v2 r JOIN alunos_v2 a ON r.codigo_aluno = a.codigo WHERE r.data = %s AND r.tipo_registro = 'FALTA'", conn, params=[d_just])
        conn.close()
        
        if not df_faltas.empty:
            with st.form("form_justificar"):
                al_falta_sel = st.selectbox("Selecione o Estudante Faltoso", [""] + [f"{r['codigo_aluno']} - {r['nome']} ({r['turma']})" for _, r in df_faltas.iterrows()])
                motivo_falta = st.selectbox("Justificativa", ["Atestado Médico", "Problemas Familiares", "Problemas de Transporte", "Outros"])
                if st.form_submit_button("SALVAR JUSTIFICATIVA") and al_falta_sel:
                    cod_f = al_falta_sel.split(" - ")[0]
                    conn = conectar_bd(); cur = conn.cursor()
                    cur.execute("UPDATE registros_v2 SET motivo_saida=%s WHERE codigo_aluno=%s AND data=%s AND tipo_registro='FALTA'", (motivo_falta, cod_f, d_just))
                    conn.commit(); conn.close()
                    st.success("Justificativa salva com sucesso!"); st.rerun()
            st.markdown("---")
            st.write("**Faltas já justificadas nesta data:**")
            faltas_justificadas = df_faltas[df_faltas['motivo_saida'].notna()]
            if not faltas_justificadas.empty:
                for _, f in faltas_justificadas.iterrows():
                    st.info(f"👤 {f['nome']} - Justificativa: **{f['motivo_saida']}**")
            else: st.write("Nenhuma falta justificada ainda.")
        else: st.success("Nenhuma falta registada para esta data!")
    st.markdown('</div>', unsafe_allow_html=True)

# --- ABA 1: GESTÃO ---
with tabs[1]:
    st.markdown('<div class="card-panel">', unsafe_allow_html=True); st.subheader("📊 Relatório Diário")
    c1, c2, c3, c4 = st.columns(4)
    with c1: dt_f = st.date_input("Data", obter_hora_atual(), key="data_relatorio")
    with c2: t_f = st.selectbox("Turma", ["Todas"] + sorted(df_alunos['turma'].unique()) if not df_alunos.empty else ["Todas"], key="filtro_turma_gestao")
    with c3: s_f = st.selectbox("Status", ["Todos", "Presentes", "Ausentes"], key="filtro_status_gestao")
    with c4: b_f = st.text_input("Buscar Nome", key="busca_nome_gestao")
    try:
        query = "SELECT a.codigo, a.nome, a.turma, r.tipo_registro, r.hora_entrada, r.status_entrada, r.hora_saida, r.motivo_saida FROM registros_v2 r JOIN alunos_v2 a ON r.codigo_aluno = a.codigo WHERE r.data = %s"; params = [dt_f.strftime("%Y-%m-%d")]
        if t_f != "Todas": query += " AND a.turma = %s"; params.append(t_f)
        if s_f == "Presentes": query += " AND r.tipo_registro = 'PRESENCA'"
        elif s_f == "Ausentes": query += " AND r.tipo_registro = 'FALTA'"
        if b_f: query += " AND a.nome ILIKE %s"; params.append(f"%{b_f}%")
        conn = conectar_bd(); df_relatorio = pd.read_sql_query(query + " ORDER BY a.turma, a.nome", conn, params=params); conn.close()
        st.dataframe(df_relatorio, use_container_width=True, hide_index=True)
    except: st.info("Sem dados para exibir no momento.")
    st.markdown('</div>', unsafe_allow_html=True)

# --- ABA 2: ALERTAS ---
with tabs[2]:
    st.markdown('<div class="card-panel">', unsafe_allow_html=True); st.subheader("🚨 Alunos em Risco (5 dias ausentes)")
    dias_u = [(obter_hora_atual() - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7) if (obter_hora_atual() - timedelta(days=i)).weekday() < 5][:5]
    if dias_u:
        try:
            conn = conectar_bd(); df_risco = pd.read_sql_query("SELECT a.codigo, a.nome, a.turma FROM alunos_v2 a WHERE a.status = 'ATIVO' AND a.codigo NOT IN (SELECT DISTINCT codigo_aluno FROM registros_v2 WHERE data IN %s AND tipo_registro='PRESENCA')", conn, params=[tuple(dias_u)]); conn.close()
            if not df_risco.empty: st.error(f"{len(df_risco)} alunos em risco"); st.dataframe(df_risco, hide_index=True)
            else: st.success("Nenhum aluno ativo nesta situação.")
        except: st.info("Aguardando...")
    st.markdown('</div>', unsafe_allow_html=True)

# --- ABA 3: HISTÓRICO ---
with tabs[3]:
    st.markdown('<div class="card-panel">', unsafe_allow_html=True); st.subheader("📈 Histórico Individual")
    aluno_sel = st.selectbox("Selecione o aluno", [""] + [f"{r['codigo']} - {r['nome']} ({r['status']})" for _, r in df_alunos.iterrows()] if not df_alunos.empty else [], key="historico_aluno")
    if aluno_sel:
        try:
            conn = conectar_bd(); df_hist = pd.read_sql_query("SELECT data, tipo_registro, hora_entrada, status_entrada, hora_saida, motivo_saida FROM registros_v2 WHERE codigo_aluno = %s ORDER BY data DESC, hora_entrada DESC", conn, params=[aluno_sel.split(" - ")[0]]); conn.close(); st.dataframe(df_hist, hide_index=True)
        except: st.warning("Erro ao carregar histórico.")
    st.markdown('</div>', unsafe_allow_html=True)

# --- ABA 4: MANUTENÇÃO (ADMIN) ---
with tabs[4]:
    if not eh_admin: st.warning("Acesso restrito ao Administrador.")
    else:
        st.markdown('<div class="card-panel">', unsafe_allow_html=True)
        st.subheader("📧 Gerir E-mails e Alunos")
        col1, col2 = st.columns(2)
        with col1:
            al_email = st.selectbox("Selecione o Aluno", [""] + [f"{r['codigo']} - {r['nome']}" for _, r in df_alunos.iterrows()])
            novo_e = st.text_input("Novo E-mail do Responsável")
            if st.button("SALVAR E-MAIL") and al_email and novo_e:
                conn = conectar_bd(); cur = conn.cursor()
                cur.execute("UPDATE alunos_v2 SET email_responsavel=%s WHERE codigo=%s", (novo_e.lower(), al_email.split(" - ")[0]))
                conn.commit(); conn.close(); st.cache_data.clear(); st.success("Atualizado!")
        with col2:
            st.write("Adição Manual")
            m_cod = st.text_input("Matrícula")
            m_nom = st.text_input("Nome Completo")
            m_tur = st.text_input("Turma")
            if st.button("CADASTRAR") and m_cod and m_nom:
                conn = conectar_bd(); cur = conn.cursor()
                cur.execute("INSERT INTO alunos_v2 (codigo, nome, turma) VALUES (%s, %s, %s)", (m_cod.upper(), m_nom.upper(), m_tur.upper()))
                conn.commit(); conn.close(); st.cache_data.clear(); st.success("Cadastrado!")
        st.divider()
        up_al = st.file_uploader("Importar Lista de Alunos (CSV)", type="csv")
        if st.button("PROCESSAR LISTA") and up_al:
            if importar_csv_alunos(up_al): st.success("Base de Alunos Sincronizada!"); st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

# --- ABA 5: DESEMPENHO ACADÊMICO ---
with tabs[5]:
    st.markdown('<div class="card-panel">', unsafe_allow_html=True)
    st.title("📊 Desempenho Acadêmico")
    df_da = pd.read_sql("SELECT * FROM avaliacoes_avs", conectar_bd())
    
    if not df_da.empty:
        df_da['disciplina'] = df_da['disciplina'].replace({
            'LÍNGUA PORTUGESA': 'LÍNGUA PORTUGUESA', 
            'SOCIOLGIA': 'SOCIOLOGIA'
        })

    cf1, cf2, cf3 = st.columns(3)
    pf = cf1.selectbox("Período", ["Todos", "1º Período", "2º Período", "3º Período", "4º Período"])
    af = cf2.selectbox("Área", ["Todas", "LÍNGUA PORTUGUESA", "MATEMÁTICA", "LINGUAGENS", "HUMANAS", "NATUREZA"])
    tf = cf3.selectbox("Turma", ["Todas"] + sorted(df_alunos.turma.unique()))
    
    dff = df_da.copy()
    if pf != "Todos": dff = dff[dff.periodo==pf]
    if af != "Todas": dff = dff[dff.area==af]
    if tf != "Todas": dff = dff[dff.turma==tf]
    
    # Adicionada nova aba: 🚫 Faltosos
    sub_da = ["🏆 Destaques", "🧑‍🎓 Estudantes", "🚫 Faltosos", "📈 Gráficos", "📋 Questões"]
    if eh_admin: sub_da.append("⚙️ Gerenciar Dados")
    stabs = st.tabs(sub_da)
    
    with stabs[0]:
        if not dff.empty:
            top7 = dff.groupby(['nome','turma']).acerto.mean().reset_index().sort_values('acerto', ascending=False).head(7)
            for idx, r in enumerate(top7.to_dict('records')):
                rev = st.toggle("Revelar", key=f"rev_{idx}")
                medalha = "🥇 1º LUGAR" if idx == 0 else ("🥈 2º LUGAR" if idx == 1 else ("🥉 3º LUGAR" if idx == 2 else f"⭐ {idx+1}º LUGAR"))
                classe_nome = "top7-name" if rev else "top7-name-hidden"
                texto_nome = r['nome'] if rev else "OCULTO"
                st.markdown(f'<div class="top7-card"><div class="top7-medal">{medalha}</div><div class="{classe_nome}">{texto_nome}</div><div class="top7-details">NOTA: {r["acerto"]*10:.2f} | {r["turma"]}</div></div>', unsafe_allow_html=True)
    
    # Processamento compartilhado para Faltas e Erros (Usado na aba 1 e 2)
    alertas_estudante = {}
    if not dff.empty:
        area_stats = dff.groupby(['nome', 'turma', 'periodo', 'area']).agg(
            Total=('questao', 'count'),
            Brancos=('resposta', lambda x: (x == 'BRANCO').sum()),
            Duplas=('resposta', lambda x: (x == 'DUPLA').sum())
        ).reset_index()

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
    
    with stabs[1]:
        if not dff.empty:
            st.markdown("#### ⚙️ Filtros do Boletim do Estudante")
            c_est1, c_est2, c_est3 = st.columns([2, 1, 1])
            with c_est1: bus_al = st.text_input("Buscar Nome:")
            with c_est2: filtro_desempenho = st.selectbox("Desempenho:", ["Todos", "INSUFICIENTE", "BOM", "ÓTIMO"])
            with c_est3: 
                st.markdown("<br>", unsafe_allow_html=True)
                filtro_erros = st.checkbox("Somente c/ erros")

            res_al = dff.groupby(['nome','turma']).acerto.mean().reset_index()
            erros_n = dff[dff.resposta.isin(['BRANCO','DUPLA'])].nome.unique()
            
            if bus_al: res_al = res_al[res_al.nome.str.contains(bus_al.upper())]
            if filtro_erros: res_al = res_al[res_al.nome.isin(erros_n)]
            if filtro_desempenho == "INSUFICIENTE": res_al = res_al[res_al.acerto*10 < 6.0]
            elif filtro_desempenho == "BOM": res_al = res_al[(res_al.acerto*10 >= 6.0) & (res_al.acerto*10 <= 7.5)]
            elif filtro_desempenho == "ÓTIMO": res_al = res_al[res_al.acerto*10 > 7.5]

            mostrar_todos = (tf != "Todas") or bus_al or filtro_erros or (filtro_desempenho != "Todos")
            lista = res_al.to_dict('records') if mostrar_todos else res_al.head(20).to_dict('records')
            
            if not mostrar_todos: st.info("A exibir os 20 primeiros. Selecione uma turma ou use os filtros acima para ver a lista completa.")
            else: st.info(f"Encontrados: {len(res_al)} estudantes.")
            
            for a in lista:
                alerta_str = alertas_estudante.get(a['nome'], "")
                tag = f" &nbsp; 🚨 [{alerta_str}]" if alerta_str else ""
                
                with st.expander(f"👤 {a['nome']} | Nota GERAL: {a['acerto']*10:.2f} {tag}"):
                    if st.button("GERAR PDF", key=f"p_{a['nome']}"):
                        b_pdf = gerar_pdf_boletim(a['nome'], a['turma'], a['acerto']*10, df_da[df_da.nome==a['nome']])
                        st.download_button("BAIXAR BOLETIM", b_pdf, f"Boletim_{a['nome']}.pdf")
                        
                    st.markdown("#### 📈 Evolução ao Longo do Ano")
                    df_bol_ind = df_da[df_da.nome==a['nome']]
                    progresso = df_bol_ind.groupby(['periodo', 'disciplina']).agg(Acertos=('acerto', 'sum'), Total=('questao', 'count')).reset_index()
                    progresso['Nota'] = (progresso['Acertos'] / progresso['Total']) * 10
                    try:
                        progresso_pivot = progresso.pivot(index='periodo', columns='disciplina', values='Nota')
                        st.line_chart(progresso_pivot, height=250)
                    except: pass

                    st.markdown("#### 📊 Médias por Disciplina")
                    medias_b = df_bol_ind.groupby(['disciplina', 'periodo']).agg(Nota=('acerto', lambda x: (sum(x)/len(x))*10)).reset_index()
                    for _, mb in medias_b.iterrows():
                        st.write(f"{mb['disciplina'].upper()} - {mb['periodo']} (Nota: {mb['Nota']:.1f})")
                        st.progress(min(mb['Nota'] / 10, 1.0))

                    st.markdown("#### 📋 Mapa de Questões")
                    for p_m in sorted(df_bol_ind.periodo.unique()):
                        for d_m in sorted(df_bol_ind[df_bol_ind.periodo==p_m].disciplina.unique()):
                            st.markdown(f"**{d_m} - {p_m}**")
                            q_df = df_bol_ind[(df_bol_ind.periodo==p_m) & (df_bol_ind.disciplina==d_m)].sort_values("questao")
                            grid = '<div style="display: flex; flex-wrap: wrap; gap: 8px;">'
                            for _, q in q_df.iterrows():
                                cor = "#10b981" if q.acerto==1 else ("#f59e0b" if q.resposta=='BRANCO' else ("#8b5cf6" if q.resposta=='DUPLA' else "#ef4444"))
                                grid += f'<div style="background:{cor}; color:white; padding:8px; border-radius:6px; width:75px; text-align:center; font-size:11px;">Q{q.questao}<br>R:{q.resposta} G:{q.gabarito}</div>'
                            st.markdown(grid+'</div><br>', unsafe_allow_html=True)
                            
    with stabs[2]:
        if not dff.empty:
            estudantes_faltosos = area_stats[area_stats['Faltou']]
            if not estudantes_faltosos.empty:
                st.error(f"⚠️ **REGISTO DE FALTAS ({len(estudantes_faltosos)})**")
                st.write("Estudantes que deixaram 100% do gabarito em branco em uma ou mais áreas específicas:")
                
                # Exibindo os faltosos em 3 colunas para um layout agradável
                cols_f = st.columns(3)
                for i, r_f in enumerate(estudantes_faltosos.to_dict('records')):
                    cols_f[i % 3].markdown(f"🚫 **{r_f['nome']}** ({r_f['turma']}) <br> <span style='color:#ef4444;'>Falta em: **{r_f['area']}** ({r_f['periodo']})</span>", unsafe_allow_html=True)
            else:
                st.success("✨ Nenhum estudante faltou na avaliação selecionada (de acordo com os filtros atuais).")

    with stabs[3]:
        if not dff.empty:
            tipo_grafico = st.radio("Agrupar por:", ["Área", "Disciplina"], horizontal=True)
            col_agrup = 'area' if tipo_grafico == "Área" else 'disciplina'
            
            periodos_disponiveis = sorted(dff['periodo'].unique())
            for p in periodos_disponiveis:
                st.markdown(f"#### 📊 Desempenho: {p}")
                dff_p = dff[dff['periodo'] == p]
                
                resumo_graf = dff_p.groupby(col_agrup).agg(Acertos=('acerto', 'sum'), Total=('questao', 'count')).reset_index()
                resumo_graf['Nota'] = (resumo_graf['Acertos'] / resumo_graf['Total']) * 10
                
                if tipo_grafico == "Área":
                    resumo_graf['Abreviacao'] = resumo_graf['area'].str.upper() 
                else:
                    resumo_graf['Abreviacao'] = resumo_graf['disciplina'].apply(lambda x: DICIONARIO_ABREVIACAO.get(x.upper(), x[:4].upper()))
                
                resumo_graf['Nome Completo'] = resumo_graf[col_agrup].str.upper()
                resumo_graf = resumo_graf.sort_values('Nota')
                
                fig_g = px.bar(resumo_graf, x='Abreviacao', y='Nota', color='Abreviacao', text='Nota', hover_data={'Nome Completo': True, 'Nota': ':.2f', 'Abreviacao': False})
                fig_g.update_traces(texttemplate='%{text:.1f}', textposition='outside')
                fig_g.update_layout(yaxis=dict(range=[0, 11]), plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', showlegend=False)
                st.plotly_chart(fig_g, use_container_width=True, key=f"grafico_{p}_{tipo_grafico}")

    with stabs[4]:
        if not dff.empty:
            st.subheader("❌ Questões com Maior Índice de Erro")
            st.write("Visão detalhada das questões onde as turmas apresentaram maior dificuldade (taxa de erro > 50%).")
            
            q_err = dff.groupby(['turma', 'disciplina', 'questao']).agg(
                Total=('questao', 'count'),
                Acertos=('acerto', 'sum')
            ).reset_index()
            q_err['Taxa de Erro (%)'] = ((q_err['Total'] - q_err['Acertos']) / q_err['Total']) * 100
            q_err = q_err.sort_values('Taxa de Erro (%)', ascending=False)
            q_err = q_err[q_err['Taxa de Erro (%)'] > 50] 
            
            st.dataframe(q_err[['turma', 'disciplina', 'questao', 'Taxa de Erro (%)']].style.format({'Taxa de Erro (%)': '{:.1f}%'}), use_container_width=True, hide_index=True)
            
    if eh_admin:
        with stabs[5]:
            st.subheader("☁️ Gerenciamento do Banco de Dados AVS")
            st.write("Somente administradores podem enviar ou excluir dados do banco.")
            
            c_up1, c_up2, c_up3 = st.columns(3)
            with c_up1: p_up = st.selectbox("Período:", ["1º Período", "2º Período", "3º Período", "4º Período"], key="pup")
            with c_up2: a_up = st.selectbox("Área:", ["LÍNGUA PORTUGUESA", "MATEMÁTICA", "LINGUAGENS", "HUMANAS", "NATUREZA"], key="aup")
            with c_up3: t_up = st.selectbox("Turma:", sorted(df_alunos.turma.unique()) if not df_alunos.empty else ["Todas"], key="tup")
            
            arquivo_avs = st.file_uploader("Arquivo CSV da Avaliação", type=["csv"], key="csv_avs_up")
            if st.button("PROCESSAR E SALVAR AGORA", type="primary", key="btn_salvar_avs") and arquivo_avs:
                with st.spinner("Processando e injetando dados em lote..."):
                    sucesso, msg = importar_csv_desempenho(arquivo_avs, p_up, a_up, t_up)
                    if sucesso: st.success(msg); st.rerun()
                    else: st.error(msg)
                
            st.markdown("---")
            st.subheader("🗑️ Limpeza Seletiva de Banco")
            st.write("Selecione um bloco de avaliação para excluir permanentemente da Nuvem:")
            
            df_banco_avs = pd.read_sql("SELECT * FROM avaliacoes_avs", conectar_bd())
            if not df_banco_avs.empty:
                blocos = df_banco_avs[['periodo', 'area', 'turma']].drop_duplicates()
                lista_blocos = [f"{r['periodo']} | {r['area']} | {r['turma']}" for _, r in blocos.iterrows()]
                bloco_del = st.selectbox("Blocos importados:", lista_blocos, key="bloco_excluir_avs")
                
                if st.button("EXCLUIR BLOCO SELECIONADO", key="btn_excluir_avs_db"):
                    p_del, a_del, t_del = bloco_del.split(" | ")
                    conn = conectar_bd(); cur = conn.cursor()
                    cur.execute("DELETE FROM avaliacoes_avs WHERE periodo=%s AND area=%s AND turma=%s", (p_del, a_del, t_del))
                    conn.commit(); conn.close()
                    st.success("Bloco removido do servidor!"); st.rerun()
            else:
                st.info("O banco de dados de desempenho está vazio.")

    st.markdown('</div>', unsafe_allow_html=True)
