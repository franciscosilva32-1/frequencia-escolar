import streamlit as st
import base64
import json

from streamlit_cookies_manager import CookieManager

from avs_admin import renderizar

st.set_page_config(page_title="Painel de Avaliação", page_icon="📊", layout="wide")

# -----------------------------------------------------------------------------
# IDENTIDADE VISUAL — somente CSS, sem alterar lógica, consultas ou desempenho.
# -----------------------------------------------------------------------------
st.markdown("""
<style>
/* Tipografia maior e mais confortável na área de avaliações */
[data-testid="stAppViewContainer"] p,
[data-testid="stAppViewContainer"] label,
[data-testid="stAppViewContainer"] .stMarkdown,
[data-testid="stAppViewContainer"] [data-testid="stCaptionContainer"] {
    font-size: 1.18rem !important;
}

/* O título interno antigo é mantido no código por segurança, mas sua apresentação
   passa a usar a nomenclatura amigável solicitada. */
[data-testid="stAppViewContainer"] h1 {
    font-size: 0 !important;
    font-weight: 900 !important;
    letter-spacing: -0.5px;
    line-height: 1.2 !important;
}
[data-testid="stAppViewContainer"] h1::after {
    content: "📊 Painel de Avaliação" !important;
    font-size: 2.45rem !important;
    font-weight: 900 !important;
}

[data-testid="stAppViewContainer"] h2 {
    font-size: 1.85rem !important;
    font-weight: 900 !important;
}

[data-testid="stAppViewContainer"] h3 {
    font-size: 1.45rem !important;
    font-weight: 800 !important;
}

/* Campos e seletores maiores */
[data-testid="stAppViewContainer"] input,
[data-testid="stAppViewContainer"] textarea,
[data-testid="stAppViewContainer"] [data-baseweb="select"] span {
    font-size: 1.12rem !important;
}

[data-testid="stAppViewContainer"] [data-baseweb="select"] > div {
    min-height: 52px !important;
}

/* Abas do Painel de Avaliação */
[data-testid="stTabs"] [data-baseweb="tab-list"] {
    gap: 10px !important;
}

[data-testid="stTabs"] [data-baseweb="tab"] {
    font-size: 1.15rem !important;
    font-weight: 800 !important;
    padding: 12px 20px !important;
    border-radius: 12px 12px 0 0 !important;
}

/* Botões mais legíveis */
[data-testid="stAppViewContainer"] .stButton > button,
[data-testid="stAppViewContainer"] [data-testid="stDownloadButton"] button {
    font-size: 1.08rem !important;
    font-weight: 800 !important;
    min-height: 48px !important;
    border-radius: 11px !important;
}

/* Navegação lateral */
[data-testid="stSidebarNav"] {
    padding-top: 1rem !important;
}

[data-testid="stSidebarNav"] ul {
    gap: 8px !important;
}

[data-testid="stSidebarNav"] li a {
    border-radius: 12px !important;
    padding: 11px 13px !important;
    font-size: 1.08rem !important;
    font-weight: 750 !important;
    transition: transform .18s ease, background-color .18s ease, box-shadow .18s ease !important;
}

[data-testid="stSidebarNav"] li a:hover {
    transform: translateX(3px) !important;
    box-shadow: 0 4px 12px rgba(10,31,53,.10) !important;
}

/* Troca visual dos nomes da navegação sem alterar os nomes dos arquivos */
[data-testid="stSidebarNav"] li:first-child a span {
    font-size: 0 !important;
}
[data-testid="stSidebarNav"] li:first-child a span::after {
    content: "🏫 Gestão Escolar" !important;
    font-size: 1.08rem !important;
}

[data-testid="stSidebarNav"] li:nth-child(2) a span {
    font-size: 0 !important;
}
[data-testid="stSidebarNav"] li:nth-child(2) a span::after {
    content: "📊 Painel de Avaliação" !important;
    font-size: 1.08rem !important;
}

/* Botão que abre/fecha o menu: maior, visível e com feedback de movimento */
[data-testid="stSidebarCollapseButton"] button {
    width: 44px !important;
    height: 44px !important;
    border-radius: 50% !important;
    border: 2px solid #cbd5e1 !important;
    background: linear-gradient(135deg, #ffffff, #e8f0f8) !important;
    box-shadow: 0 4px 12px rgba(10,31,53,.18) !important;
    transition: transform .2s ease, box-shadow .2s ease, border-color .2s ease !important;
}

[data-testid="stSidebarCollapseButton"] button:hover {
    transform: scale(1.08) rotate(-4deg) !important;
    border-color: #ff7b00 !important;
    box-shadow: 0 6px 18px rgba(255,123,0,.28) !important;
}

/* Destaque discreto para a página atualmente selecionada */
[data-testid="stSidebarNav"] li:nth-child(2) a[aria-current="page"] {
    border-left: 5px solid #ff7b00 !important;
    box-shadow: 0 4px 14px rgba(10,31,53,.12) !important;
}
</style>
""", unsafe_allow_html=True)

cookies = CookieManager()
if not cookies.ready():
    st.stop()

SENHA_OPERADOR = st.secrets.get("SENHA_OPERADOR", "admin123")
SENHA_ADMIN = st.secrets.get("SENHA_ADMIN", "admin123")

auth_cookie = cookies.get("auth_token")
eh_admin = False

if auth_cookie:
    try:
        payload = json.loads(base64.b64decode(auth_cookie).decode("utf-8"))
        eh_admin = bool(payload.get("admin"))
    except Exception:
        eh_admin = False

if not eh_admin:
    st.error("🔒 Esta área é exclusiva do administrador do sistema.")
    st.stop()

renderizar()
