import streamlit as st
import base64
import json

from streamlit_cookies_manager import CookieManager

from avs_admin import renderizar

st.set_page_config(page_title="Manutenção AVS", page_icon="⚙️", layout="wide")

cookies = CookieManager()
if not cookies.ready():
    st.stop()

SENHA_OPERADOR = st.secrets.get("SENHA_OPERADOR", "admin123")
SENHA_ADMIN = st.secrets.get("SENHA_ADMIN", "admin123")

# A página exige a mesma credencial administrativa do sistema principal.
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
