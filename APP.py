import streamlit as st
import pandas as pd
from datetime import datetime
import psycopg2
import os
import io
import base64
import streamlit.components.v1 as components

# ------------------------------------------------------------
# CONFIGURAÇÃO DA PÁGINA E ESTILIZAÇÃO
# ------------------------------------------------------------
st.set_page_config(
    page_title="Centro Educa Mais Jansen Veloso",
    page_icon="🏫",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# CSS para centralizar a logo e títulos
st.markdown("""
<style>
    .header-container {
        display: flex;
        justify-content: center;
        align-items: center;
        flex-direction: column;
        width: 100%;
        padding: 20px 0;
    }
    .centered-logo {
        max-width: 180px;
        height: auto;
        margin-bottom: 15px;
    }
    .main-title {
        text-align: center;
        color: #0f2b4a;
        font-family: 'Inter', sans-serif;
        font-weight: 800;
        font-size: 2.2rem;
        margin: 0;
    }
    .stApp { background-color: #f8fafc; }
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------
# COMPONENTE DE LEITURA DE QR CODE
# ------------------------------------------------------------
def qr_scanner_v2(key):
    html_code = f"""
    <div id="reader-{key}" style="width: 100%; max-width: 400px; margin: auto; border-radius: 12px; overflow: hidden; border: 2px solid #0f2b4a;"></div>
    <div style="text-align: center; margin-top: 15px;">
        <button id="btn-{key}" style="padding: 12px 24px; background: #0f2b4a; color: white; border: none; border-radius: 8px; font-weight: bold; cursor: pointer;">
            📷 Abrir Câmera para Leitura
        </button>
    </div>

    <script src="https://unpkg.com/html5-qrcode"></script>
    <script>
        const html5QrCode = new Html5Qrcode("reader-{key}");
        const btn = document.getElementById("btn-{key}");
        
        btn.onclick = () => {{
            html5QrCode.start(
                {{ facingMode: "environment" }}, 
                {{ fps: 10, qrbox: 250 }},
                (decodedText) => {{
                    window.parent.postMessage({{
                        type: 'streamlit:setComponentValue',
                        value: decodedText
                    }}, '*');
                    html5QrCode.stop();
                }},
                (errorMessage) => {{ }}
            ).catch(err => alert("Erro na câmera: " + err));
        }};
    </script>
    """
    return components.html(html_code, height=400)

# ------------------------------------------------------------
# FUNÇÕES DE BANCO DE DADOS
# ------------------------------------------------------------
def conectar_bd():
    return psycopg2.connect(st.secrets["DATABASE_URL"])

def registrar_presenca(nome_estudante, data_registro, hora_limite):
    agora = datetime.now()
    hora_atual = agora.strftime("%H:%M:%S")
    status = "PRESENTE" if agora.time() <= hora_limite else "ATRASO"
    
    conn = conectar_bd()
    cur = conn.cursor()
    try:
        # Verifica se o aluno existe
        cur.execute("SELECT nome FROM alunos WHERE nome = %s", (nome_estudante,))
        if not cur.fetchone():
            return "erro_inexistente"
            
        # Comando SQL corrigido (sem barras invertidas extras)
        cur.execute(
            "INSERT INTO registros (nome_aluno, data, hora_entrada, status_entrada, tipo_registro) "
            "VALUES (%s, %s, %s, %s, 'PRESENCA')",
            (nome_estudante, data_registro, hora_atual, status)
        )
        conn.commit()
        return status
    except Exception as e:
        conn.rollback()
        return "erro_duplicado"
    finally:
        conn.close()

# ------------------------------------------------------------
# INTERFACE DO USUÁRIO
# ------------------------------------------------------------

# Cabeçalho Centralizado
st.markdown('<div class="header-container">', unsafe_allow_html=True)
if os.path.exists("logo.png"):
    with open("logo.png", "rb") as f:
        data = base64.b64encode(f.read()).decode()
    st.markdown(f'<img src="data:image/png;base64,{data}" class="centered-logo">', unsafe_allow_html=True)
else:
    st.markdown("<h1 style='text-align: center;'>🏫</h1>", unsafe_allow_html=True)
st.markdown('<p class="main-title">Sistema de Frequência</p>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# Área de Registro
st.divider()
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("⚙️ Configurações")
    data_hj = st.date_input("Data do Registro", datetime.now())
    limite_entrada = st.time_input("Horário Limite (Entrada)", datetime.strptime("07:30", "%H:%M").time())

with col2:
    st.subheader("🔍 Identificação")
    # Captura o valor do Scanner
    resultado_qr = qr_scanner_v2("leitor_principal")
    entrada_manual = st.text_input("Ou digite o nome e aperte Enter:").strip().upper()

# Lógica de processamento
aluno_detectado = None
if resultado_qr:
    aluno_detectado = resultado_qr.strip().upper()
elif entrada_manual:
    aluno_detectado = entrada_manual

if aluno_detectado:
    resultado = registrar_presenca(aluno_detectado, data_hj.strftime("%Y-%m-%d"), limite_entrada)
    
    if resultado == "PRESENTE":
        st.success(f"✅ Sucesso: {aluno_detectado} registrado no horário.")
    elif resultado == "ATRASO":
        st.warning(f"⏰ Atraso: {aluno_detectado} registrado fora do horário.")
    elif resultado == "erro_inexistente":
        st.error(f"❌ Erro: '{aluno_detectado}' não está na lista de alunos.")
    else:
        st.info(f"ℹ️ Aviso: {aluno_detectado} já possui registro para hoje.")
