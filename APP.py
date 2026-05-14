import streamlit as st
import pandas as pd
from datetime import datetime
import psycopg2
import os
import io
import base64
import json
import streamlit.components.v1 as components
import plotly.express as px
from streamlit_cookies_manager import CookieManager

# ------------------------------------------------------------
# CONFIGURAÇÃO DA PÁGINA E ESTILIZAÇÃO (LOGO CENTRALIZADA)
# ------------------------------------------------------------
st.set_page_config(
    page_title="Centro Educa Mais Jansen Veloso",
    page_icon="🏫",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# CSS para centralizar a logo e melhorar a interface
st.markdown("""
<style>
    .header-container {
        display: flex;
        justify-content: center;
        align-items: center;
        width: 100%;
        padding: 20px 0;
    }
    .centered-logo {
        display: block;
        margin-left: auto;
        margin-right: auto;
        max-width: 200px;
    }
    .main-title {
        text-align: center;
        font-family: 'Inter', sans-serif;
        color: #0f2b4a;
        font-weight: 800;
        font-size: 2.5rem;
        margin-top: 10px;
    }
    /* Estilo para os cards */
    .stApp { background-color: #f8fafc; }
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------
# COMPONENTE DE LEITURA DE QR CODE (CORRIGIDO)
# ------------------------------------------------------------
def qr_scanner_v2(key):
    """
    Componente de leitura de QR Code usando Html5Qrcode.
    A correção foca no envio do valor via postMessage para o Streamlit.
    """
    html_code = f"""
    <div id="reader-{key}" style="width: 100%; max-width: 400px; margin: auto; border-radius: 10px; overflow: hidden;"></div>
    <div style="text-align: center; margin-top: 10px;">
        <button id="btn-{key}" style="padding: 10px 20px; background: #0f2b4a; color: white; border: none; border-radius: 5px; cursor: pointer;">
            📷 Iniciar Câmera
        </button>
    </div>

    <script src="https://unpkg.com/html5-qrcode"></script>
    <script>
        const scannerConfig = {{ fps: 15, qrbox: {{ width: 250, height: 250 }} }};
        const html5QrCode = new Html5Qrcode("reader-{key}");
        const btn = document.getElementById("btn-{key}");
        
        btn.onclick = () => {{
            html5QrCode.start(
                {{ facingMode: "environment" }}, 
                scannerConfig,
                (decodedText) => {{
                    // Envia o resultado de volta para o Streamlit
                    window.parent.postMessage({{
                        type: 'streamlit:setComponentValue',
                        value: decodedText
                    }}, '*');
                    html5QrCode.stop();
                }},
                (errorMessage) => {{ /* Erros de busca ignorados */ }}
            ).catch(err => alert("Erro ao acessar câmera: " + err));
        }};
    </script>
    """
    return components.html(html_code, height=350)

# ------------------------------------------------------------
# LOGICA DE BANCO DE DATA (SÍNTESE)
# ------------------------------------------------------------
DATABASE_URL = st.secrets.get("DATABASE_URL")

def conectar_bd():
    return psycopg2.connect(DATABASE_URL)

def registrar_presenca(nome_estudante, data_registro, hora_limite):
    agora = datetime.now()
    hora_atual = agora.strftime("%H:%M:%S")
    status = "PRESENTE" if agora.time() <= hora_limite else "ATRASO"
    
    conn = conectar_bd()
    cur = conn.cursor()
    try:
        # Verifica se aluno existe
        cur.execute("SELECT nome FROM alunos WHERE nome = %s", (nome_estudante,))
        if not cur.fetchone():
            return "erro_inexistente"
            
        # Tenta inserir registro
        cur.execute(\"\"\"
            INSERT INTO registros (nome_aluno, data, hora_entrada, status_entrada, tipo_registro) 
            VALUES (%s, %s, %s, %s, 'PRESENCA')
        \"\"\", (nome_estudante, data_registro, hora_atual, status))
        conn.commit()
        return status
    except Exception as e:
        conn.rollback()
        return "erro_duplicado"
    finally:
        conn.close()

# ------------------------------------------------------------
# INTERFACE PRINCIPAL
# ------------------------------------------------------------

# 1. Logo Centralizada
st.markdown('<div class="header-container">', unsafe_allow_html=True)
if os.path.exists("logo.png"):
    # Usando base64 para garantir centralização via HTML puro
    with open("logo.png", "rb") as f:
        data = base64.b64encode(f.read()).decode()
    st.markdown(f'<img src="data:image/png;base64,{data}" class="centered-logo">', unsafe_allow_html=True)
else:
    st.markdown("<h1 style='text-align: center;'>🏫</h1>", unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<p class="main-title">Sistema de Frequência</p>', unsafe_allow_html=True)

# 2. Tabs de Operação
tab_registro, tab_gestao = st.tabs(["📝 Registro", "📊 Gestão"])

with tab_registro:
    st.subheader("Configuração do Horário")
    col_h1, col_h2 = st.columns(2)
    with col_h1:
        data_hj = st.date_input("Data", datetime.now())
        limite_entrada = st.time_input("Limite Entrada", datetime.strptime("07:30", "%H:%M").time())
    
    st.divider()
    
    # Chamada do Scanner
    st.write("### Escanear Carteirinha")
    resultado_qr = qr_scanner_v2("entrada_principal")
    
    # Campo manual para redundância
    entrada_manual = st.text_input("Ou digite o nome/código e aperte Enter:").strip().upper()

    # Processamento da leitura (QR ou Manual)
    aluno_para_registrar = None
    if resultado_qr:
        aluno_para_registrar = resultado_qr.strip().upper()
    elif entrada_manual:
        aluno_para_registrar = entrada_manual

    if aluno_para_registrar:
        res = registrar_presenca(aluno_para_registrar, data_hj.strftime("%Y-%m-%d"), limite_entrada)
        if res == "PRESENTE":
            st.success(f"✅ {aluno_para_registrar} - Entrada registrada!")
        elif res == "ATRASO":
            st.warning(f"⏰ {aluno_para_registrar} - Atraso registrado!")
        elif res == "erro_inexistente":
            st.error("❌ Aluno não encontrado no sistema.")
        else:
            st.info("ℹ️ Aluno já possui registro hoje.")
