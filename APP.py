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
# 1. CONFIGURAÇÃO INICIAL
# ------------------------------------------------------------
st.set_page_config(page_title="Jansen Veloso - Gestão Escolar", page_icon="🏫", layout="wide", initial_sidebar_state="collapsed")

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

# ------------------------------------------------------------
# 3. CSS (FILTROS DESTACADOS E DESIGN)
# ------------------------------------------------------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap');
    :root { --primary: #0a1f35; --accent: #ff7b00; }
    .stApp { background: #f8fafc; }
    #MainMenu, footer, header {visibility: hidden;}
    
    .main-title { font-family: 'Inter', sans-serif; font-weight: 900; font-size: 3.8rem; color: var(--primary); text-align: center; text-transform: uppercase; letter-spacing: -2px; margin: 0;}
    .sub-title { font-family: 'Inter', sans-serif; font-size: 1.5rem; color: #64748b; text-align: center; font-weight: 700; margin-bottom: 2rem;}
    
    /* FILTROS COM DESTAQUE MÁXIMO */
    [data-baseweb="select"] > div { border: 2.5px solid #0a1f35 !important; border-radius: 12px !important; height: 55px !important; background: white !important;}
    [data-baseweb="select"] span { color: #000 !important; font-weight: 900 !important; font-size: 1.3rem !important; }
    
    .metric-card { background: white; padding: 2rem; border-radius: 16px; text-align: center; border-top: 8px solid var(--primary); box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
    .m-val { font-size: 3.2rem; font-weight: 900; display: block; color: #1e293b; }
    .m-lab { font-size: 1rem; font-weight: 700; color: #64748b; text-transform: uppercase; }

    .top7-card { background: white; border-left: 12px solid var(--accent); padding: 2rem; border-radius: 15px; margin-bottom: 1rem; text-align: center; box-shadow: 0 8px 15px rgba(0,0,0,0.05); }
    .top7-name { font-size: 3.5rem; font-weight: 900; color: var(--primary); text-transform: uppercase; }
    .top7-name-hidden { font-size: 3.5rem; font-weight: 900; color: #cbd5e1; filter: blur(15px); }
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------
# 4. BANCO DE DADOS (OTIMIZADO)
# ------------------------------------------------------------
DATABASE_URL = st.secrets.get("DATABASE_URL")
SENHA_OPERADOR = st.secrets.get("SENHA_OPERADOR", "admin123")
SENHA_ADMIN = st.secrets.get("SENHA_ADMIN", "admin123")

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
# 5. LÓGICA DE NEGÓCIO (VETORIZADA - ALTA PERFORMANCE)
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

# ------------------------------------------------------------
# 6. DESEMPENHO ACADÊMICO E PDF
# ------------------------------------------------------------
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
    for p in sorted(df_b.periodo.unique()):
        pdf.set_fill_color(230,230,230); pdf.set_font("Arial", "B", 12); pdf.cell(0, 10, f"  {p}", 0, 1, fill=True)
        for d in sorted(df_b[df_b.periodo==p].disciplina.unique()):
            df_d = df_b[(df_b.periodo==p) & (df_b.disciplina==d)]
            pdf.set_font("Arial", "B", 11); pdf.cell(0, 8, f"{d} - Nota: {(df_d.acerto.mean()*10):.2f}", 0, 1)
            x, y, col = 10, pdf.get_y(), 0
            for q in df_d.sort_values('questao').to_dict('records'):
                if y > 265: pdf.add_page(); y = 20
                c = (16,185,129) if q['acerto']==1 else ((245,158,11) if q['resposta']=='BRANCO' else (239,68,68))
                pdf.set_fill_color(*c); pdf.rect(x+(col*22), y, 20, 12, 'F'); pdf.set_text_color(255,255,255); pdf.set_font("Arial","B",8)
                pdf.text(x+(col*22)+2, y+5, f"Q{q['questao']}"); pdf.text(x+(col*22)+2, y+10, f"R:{q['resposta']}")
                col += 1
                if col > 7: col, y = 0, y+15
            y = y+15 if col > 0 else y; pdf.set_y(y+5); pdf.set_text_color(0,0,0)
    return pdf.output(dest='S').encode('latin-1')

# ------------------------------------------------------------
# 7. COMPONENTE CÂMERA QR CODE
# ------------------------------------------------------------
def gerar_camera(label, btn_label, cam_id):
    components.html(f"""
    <div style="text-align:center;"><button id="start-{cam_id}" style="padding:15px; background:#10b981; color:white; border:none; border-radius:10px; width:100%; font-weight:bold; cursor:pointer;">📷 LIGAR CÂMERA {label}</button>
    <div id="reader-{cam_id}" style="width:100%; margin-top:10px; display:none; border-radius:10px; overflow:hidden;"></div></div>
    <script src="https://unpkg.com/html5-qrcode"></script>
    <script>
        const scanner = new Html5Qrcode("reader-{cam_id}");
        document.getElementById("start-{cam_id}").onclick = () => {{
            document.getElementById("reader-{cam_id}").style.display = "block";
            scanner.start({{ facingMode: "environment" }}, {{ fps: 15, qrbox: 250 }}, (txt) => {{
                const input = window.parent.document.querySelectorAll('input[aria-label*="{label}"]')[0];
                input.value = txt; input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                setTimeout(() => {{ window.parent.document.querySelectorAll('button').forEach(b => {{ if(b.innerText.includes("{btn_label}")) b.click(); }}); }}, 500);
                scanner.stop(); document.getElementById("reader-{cam_id}").style.display = "none";
            }});
        }}
    </script>
    """, height=350)

# ------------------------------------------------------------
# 8. AUTH E DASHBOARD
# ------------------------------------------------------------
auth_cookie = cookies.get("auth_token")
if not auth_cookie:
    st.markdown('<div style="max-width:400px; margin: 10vh auto; padding: 3rem; background:white; border-radius:20px; border:3px solid #0a1f35; text-align:center;">', unsafe_allow_html=True)
    st.image("logo.png", width=120) if os.path.exists("logo.png") else None
    st.title("LOGIN ESCOLAR")
    passw = st.text_input("SENHA", type="password")
    if st.button("ENTRAR", use_container_width=True):
        if passw in [SENHA_ADMIN, SENHA_OPERADOR]:
            cookies["auth_token"] = base64.b64encode(json.dumps({"admin": passw==SENHA_ADMIN}).encode()).decode(); cookies.save(); st.rerun()
        else: st.error("Incorreta")
    st.stop()

user = json.loads(base64.b64decode(auth_cookie).decode()); eh_admin = user['admin']
df_alunos = carregar_alunos()

# HEADER
c_l, c_t, c_s = st.columns([1, 4, 1])
with c_l: st.image("logo.png", width=100) if os.path.exists("logo.png") else None
with c_t:
    st.markdown('<p class="main-title">SISTEMA DE FREQUÊNCIA</p>', unsafe_allow_html=True)
    st.markdown(f'<p class="sub-title">CEMA Jansen Veloso • {data_formatada_ptbr()}</p>', unsafe_allow_html=True)
with c_s: 
    if st.button("SAIR"): cookies["auth_token"] = ""; cookies.save(); st.rerun()

# MÉTRICAS
hoje = obter_hora_atual().strftime("%Y-%m-%d")
conn = conectar_bd(); cur = conn.cursor(); cur.execute("SELECT COUNT(*) FROM registros_v2 WHERE data=%s AND tipo_registro='PRESENCA'", (hoje,))
pres_hoje = cur.fetchone()[0]; conn.close()

m1, m2, m3, m4 = st.columns(4)
m1.markdown(f'<div class="metric-card"><span class="m-val">{len(df_alunos)}</span><span class="m-lab">Total Alunos</span></div>', unsafe_allow_html=True)
m2.markdown(f'<div class="metric-card"><span class="m-val">{pres_hoje}</span><span class="m-lab">Presentes</span></div>', unsafe_allow_html=True)
m3.markdown(f'<div class="metric-card"><span class="m-val">{len(df_alunos)-pres_hoje}</span><span class="m-lab">Faltas</span></div>', unsafe_allow_html=True)
m4.markdown(f'<div class="metric-card"><span class="m-val">--</span><span class="m-lab">Média Geral</span></div>', unsafe_allow_html=True)

tabs = st.tabs(["📝 Registro", "📊 Gestão", "🚨 Alertas", "📈 Histórico", "⚙️ Manutenção", "📑 Desempenho Académico"])

# --- ABA 0: REGISTRO ---
with tabs[0]:
    st.markdown('<div class="card-panel">', unsafe_allow_html=True)
    h_lim_e = st.time_input("Horário Limite Entrada", datetime.strptime("07:30", "%H:%M").time())
    t_en, t_sa = st.tabs(["✅ ENTRADA", "🚪 SAÍDA ANTECIPADA"])
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
    st.markdown('</div>', unsafe_allow_html=True)

# --- ABA 4: MANUTENÇÃO (ADMIN) ---
with tabs[4]:
    if not eh_admin: st.warning("Acesso restrito ao Administrador.")
    else:
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

# --- ABA 5: DESEMPENHO ACADÉMICO ---
with tabs[5]:
    st.markdown('<div class="card-panel">', unsafe_allow_html=True)
    st.title("📊 Desempenho Académico")
    df_da = pd.read_sql("SELECT * FROM avaliacoes_avs", conectar_bd())
    
    # Filtros com Destaque
    cf1, cf2, cf3 = st.columns(3)
    pf = cf1.selectbox("Período", ["Todos", "1º Período", "2º Período", "3º Período", "4º Período"])
    af = cf2.selectbox("Área", ["Todas", "LÍNGUA PORTUGUESA", "MATEMÁTICA", "LINGUAGENS", "HUMANAS", "NATUREZA"])
    tf = cf3.selectbox("Turma", ["Todas"] + sorted(df_alunos.turma.unique()))
    
    dff = df_da.copy()
    if pf != "Todos": dff = dff[dff.periodo==pf]
    if af != "Todas": dff = dff[dff.area==af]
    if tf != "Todas": dff = dff[dff.turma==tf]
    
    sub_da = ["🏆 Destaques", "🧑‍🎓 Estudantes", "📈 Gráficos", "📋 Questões"]
    if eh_admin: sub_da.append("⚙️ Gerenciar Dados")
    stabs = st.tabs(sub_da)
    
    with stabs[0]:
        if not dff.empty:
            top7 = dff.groupby(['nome','turma']).acerto.mean().reset_index().sort_values('acerto', ascending=False).head(7)
            for idx, r in enumerate(top7.to_dict('records')):
                rev = st.toggle("Revelar", key=f"rev_{idx}")
                st.markdown(f'<div class="top7-card"><div class="top7-medal">⭐ {idx+1}º LUGAR</div><div class="{"top7-name" if rev else "top7-name-hidden"}">{r["nome"] if rev else "OCULTO"}</div><div class="top7-details">NOTA: {r["acerto"]*10:.2f} | {r["turma"]}</div></div>', unsafe_allow_html=True)
    
    with stabs[1]:
        if not dff.empty:
            bus_al = st.text_input("Buscar Nome:")
            res_al = dff.groupby(['nome','turma']).acerto.mean().reset_index()
            if bus_al: res_al = res_al[res_al.nome.str.contains(bus_al.upper())]
            lista_ex = res_al.to_dict('records') if (tf != "Todas" or bus_al) else res_al.head(20).to_dict('records')
            for a in lista_ex:
                with st.expander(f"👤 {a['nome']} | Nota: {a['acerto']*10:.2f}"):
                    if st.button("GERAR PDF", key=f"p_{a['nome']}"):
                        b_pdf = gerar_pdf_boletim(a['nome'], a['turma'], a['acerto']*10, df_da[df_da.nome==a['nome']])
                        st.download_button("BAIXAR BOLETIM", b_pdf, f"Boletim_{a['nome']}.pdf")
    
    if eh_admin:
        with stabs[4]:
            up_da = st.file_uploader("Upload de Notas (CSV)", type="csv")
            if st.button("SALVAR NOTAS") and up_da:
                s, m = importar_csv_desempenho(up_da, pf, af, tf)
                if s: st.success(m); st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
