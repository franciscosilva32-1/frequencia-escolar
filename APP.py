import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, timezone
FUSO_BRASILIA = timezone(timedelta(hours=-3))
import psycopg2
from psycopg2 import pool
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
import requests
from urllib.parse import quote

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
# 1. CONFIGURAÇÃO E COOKIES
# ------------------------------------------------------------
st.set_page_config(page_title="Centro Educa Mais Jansen Veloso", page_icon="🏫", layout="wide", initial_sidebar_state="expanded")

if 'pesquisa_enviada' not in st.session_state:
    st.session_state.pesquisa_enviada = False

cookies = CookieManager()
if not cookies.ready():
    st.warning("⏳ A inicializar as configurações. Por favor, aguarde um instante...")
    st.stop()

# ------------------------------------------------------------
# 2. BANCO DE DADOS
# ------------------------------------------------------------
DATABASE_URL = st.secrets.get("DATABASE_URL")
SENHA_OPERADOR = st.secrets.get("SENHA_OPERADOR", "")
SENHA_ADMIN = st.secrets.get("SENHA_ADMIN", "")

@st.cache_resource(ttl=600)
def get_connection_pool():
    url = st.secrets.get("DATABASE_URL")
    if not url:
        st.error("🚨 ERRO CRÍTICO: DATABASE_URL não encontrada no secrets.toml!")
        st.stop()

    if url and "sslmode" not in url:
        if "?" in url:
            url += "&sslmode=require"
        else:
            url += "?sslmode=require"

    try:
        return pool.ThreadedConnectionPool(1, 10, url, connect_timeout=10)
    except Exception as e:
        st.error(f"🚨 ERRO FATAL AO CRIAR POOL DE CONEXÕES: {e}")
        st.stop()

def conectar_bd():
    pool_obj = get_connection_pool()
    if not pool_obj:
        st.error("🚨 ERRO: Pool de conexões não foi criado.")
        st.stop()
        
    for tentativa in range(1, 4):
        conn = None
        try:
            conn = pool_obj.getconn()
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
            return conn
        except Exception as e:
            erro_exato = str(e)
            if tentativa == 3:
                st.error(f"🚨 FALHA NA CONEXÃO APÓS 3 TENTATIVAS. ERRO EXATO: {erro_exato}")
                st.stop()
            else:
                st.warning(f"⚠️ Tentativa {tentativa}/3 falhou: {erro_exato}. Tentando novamente...")
                time.sleep(2)
            
            if conn:
                try:
                    pool_obj.putconn(conn, close=True)
                except:
                    pass
    return None

def liberar_conn(conn):
    if conn:
        try:
            get_connection_pool().putconn(conn)
        except Exception:
            try: 
                conn.close()
            except: 
                pass

# ------------------------------------------------------------
# 3. FUNÇÕES DE SUPORTE
# ------------------------------------------------------------
def obter_hora_atual():
    return datetime.now(FUSO_BRASILIA)

def data_formatada_ptbr():
    dt = obter_hora_atual()
    meses = ["", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
    return f"{dt.day:02d} de {meses[dt.month]} de {dt.year}"

ATIVAR_EMAILS = True  
EMAIL_ESCOLA = st.secrets.get("EMAIL_ESCOLA", "") 
SENHA_APP_ESCOLA = st.secrets.get("SENHA_APP_ESCOLA", "") 

DICIONARIO_CORES = {
    "LP": "#2563eb", "MAT": "#dc2626", "MTM": "#dc2626", "BIO": "#16a34a",
    "ART": "#d97706", "EDF": "#7c3aed", "ESP": "#db2777", "FIL": "#4f46e5",
    "FIS": "#0d9488", "GGF": "#ea580c", "HST": "#9333ea", "ING": "#0891b2",
    "QUI": "#65a30d", "SOC": "#ca8a04",
    "LÍNGUA PORTUGUESA": "#2563eb", "MATEMÁTICA": "#dc2626",
    "LINGUAGENS": "#d97706", "HUMANAS": "#7c3aed", "NATUREZA": "#16a34a"
}

DICIONARIO_ABREVIACAO = {
    "BIOLOGIA": "BIO", "ARTE": "ART", "EDUCAÇÃO FÍSICA": "EDF",
    "LÍNGUA ESPANHOLA": "ESP", "FILOSOFIA": "FIL", "FÍSICA": "FIS",
    "GEOGRAFIA": "GGF", "MATEMÁTICA": "MTM", "HISTÓRIA": "HST",
    "LÍNGUA INGLESA": "ING", "LÍNGUA PORTUGUESA": "LP", "LÍNGUA PORTUGESA": "LP",
    "QUÍMICA": "QUI", "SOCIOLOGIA": "SOC", "SOCIOLGIA": "SOC"
}

MOTIVOS_JUSTIFICATIVA = [
    "Febre",
    "Dor de cabeça",
    "Gripe",
    "Tontura",
    "Dor de cólica",
    "Dor de barriga",
    "Sinusite-Rinite",
    "Alergia",
    "Vômito",
    "Solicitação do responsável",
    "Consulta Médica",
    "Liberação da Direção",
    "Término do Turno",
    "Outros",
    "Sem justificativa do responsável",
    "Falta de transporte",
]

MOTIVOS_SUSPENSAO = {
    "Violência e segurança": [
        "Brigas, agressão física ou tentativa de lesão",
        "Ameaças verbais, escritas ou virtuais contra colegas, professores ou funcionários",
        "Porte ou uso de armas (incluindo réplicas, canivetes, estiletes etc.)",
        "Comportamento que coloque em risco a segurança coletiva, como acionar alarme de incêndio sem necessidade",
    ],
    "Substâncias proibidas": [
        "Posse, uso, venda ou distribuição de drogas ilícitas",
        "Porte ou consumo de bebidas alcoólicas na escola ou em eventos escolares",
        "Uso de cigarro, cigarro eletrônico ou produtos de tabaco em menores de idade, quando proibido",
    ],
    "Conduta e respeito": [
        "Bullying, cyberbullying ou assédio moral",
        "Assédio sexual, comentários ou gestos de conotação sexual indevidos",
        "Discriminação, injúria racial, homofobia, intolerância religiosa ou qualquer forma de preconceito",
        "Desacato, insulto ou desobediência grave a professor ou funcionário",
        "Uso de linguagem obscena, agressiva ou desrespeitosa",
    ],
    "Dano e patrimônio": [
        "Vandalismo, pichação ou depredação de instalações e materiais escolares",
        "Furto ou roubo de pertences de colegas, funcionários ou da própria escola",
        "Danificação de equipamentos, livros, laboratórios ou outros recursos",
    ],
    "Integridade acadêmica e regras escolares": [
        "Cola, plágio ou fraude em provas, trabalhos e avaliações",
        "Uso indevido de celular ou dispositivos eletrônicos para filmar, difamar, trapacear ou invadir privacidade",
        "Reincidência em infrações disciplinares após advertências e notificações aos responsáveis",
        "Violação de regras de uso da internet ou da rede da escola, como acesso a conteúdo impróprio ou invasão de sistemas",
    ],
    "Outros motivos comuns": [
        "Participação em tumultos, motins, trotes violentos ou incitação à desordem coletiva",
        "Falsificação de assinatura de responsáveis, documentos escolares ou comunicados",
        "Atos de desrespeito a normas de saúde e segurança, como exposição a risco em laboratório ou oficina",
    ],
}


DICIONARIO_PERGUNTAS_SATISFACAO = {
    "Todos": ["Conservação/Limpeza", "Acolhimento/Atenção", "Satisfação Geral", "Específica 1", "Específica 2"],
    "Estudante": ["Conservação/Limpeza", "Acolhimento/Atenção", "Satisfação Geral", "Qualidade das Aulas", "Organização Eventos"],
    "Pais/Responsável": ["Conservação/Limpeza", "Acolhimento/Atenção", "Satisfação Geral", "Facilidade Certificados", "Comunicação Escola"],
    "Professor": ["Conservação/Limpeza", "Acolhimento/Atenção", "Satisfação Geral", "Recursos Pedagógicos", "Engajamento Alunos"],
    "Servidor": ["Conservação/Limpeza", "Acolhimento/Atenção", "Satisfação Geral", "Condições de Trabalho", "Clima Organizacional"]
}

def preparar_mensagem_email(nome_aluno, evento, horario, data):
    """Prepara a mensagem usando um evento explícito e validado."""
    try:
        data_f = datetime.strptime(str(data), "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        try:
            data_f = pd.to_datetime(data).strftime("%d/%m/%Y")
        except Exception:
            data_f = str(data)

    evento = str(evento or "").strip().upper()

    if evento == "ENTRADA":
        assunto = "🏫 Aviso de Entrada - Jansen Veloso"
        texto = (
            f"Olá, família!\n\n"
            f"Informamos que o estudante {nome_aluno} registrou ENTRADA "
            f"na escola hoje ({data_f}) às {horario} "
            f"(Dentro do horário regular).\n\n"
            f"Atenciosamente,\nEquipe Jansen Veloso."
        )
    elif evento == "ENTRADA COM ATRASO":
        assunto = "🏫 Aviso de Entrada - Jansen Veloso"
        texto = (
            f"Olá, família!\n\n"
            f"Informamos que o estudante {nome_aluno} registrou ENTRADA COM ATRASO "
            f"na escola hoje ({data_f}) às {horario}.\n\n"
            f"Atenciosamente,\nEquipe Jansen Veloso."
        )
    elif evento == "SAÍDA REGULAR":
        assunto = "🏫 Aviso de Saída - Jansen Veloso"
        texto = (
            f"Olá, família!\n\n"
            f"Informamos que o estudante {nome_aluno} registrou SAÍDA REGULAR "
            f"da escola hoje ({data_f}) às {horario}.\n\n"
            f"Atenciosamente,\nEquipe Jansen Veloso."
        )
    elif evento == "SAÍDA ANTECIPADA":
        assunto = "🏫 Aviso de SAÍDA ANTECIPADA - Jansen Veloso"
        texto = (
            f"⚠️ ATENÇÃO!\n\n"
            f"Informamos que o estudante {nome_aluno} registrou uma SAÍDA ANTECIPADA "
            f"hoje ({data_f}) às {horario}.\n\n"
            f"Atenciosamente,\nEquipe Jansen Veloso."
        )
    else:
        raise ValueError(f"Evento de e-mail inválido: {evento!r}")

    return assunto, texto


def enviar_email_smtp(server, email_destino, nome_aluno, evento, horario, data):
    """
    Monta e envia uma mensagem individual.

    Importante: smtplib.send_message() retorna um dicionário com os
    destinatários que foram recusados pelo servidor SMTP. Um retorno
    não vazio NÃO é considerado envio bem-sucedido.

    Retorna:
        {}  -> servidor aceitou o destinatário;
        dict -> destinatários recusados pelo servidor.

    O evento recebido é preservado integralmente. Assim, uma saída
    antecipada nunca pode ser convertida acidentalmente em entrada.
    """
    assunto, texto = preparar_mensagem_email(
        nome_aluno, evento, horario, data
    )
    msg = MIMEMultipart()
    msg["From"] = EMAIL_ESCOLA
    msg["To"] = email_destino
    msg["Subject"] = assunto
    msg.attach(MIMEText(texto, "plain", "utf-8"))

    recusados = server.send_message(msg)
    return recusados or {}


def formatar_recusa_smtp(recusados):
    """Converte o retorno de send_message em texto legível."""
    if not recusados:
        return ""

    partes = []
    for destinatario, detalhe in recusados.items():
        try:
            codigo, mensagem = detalhe
            partes.append(
                f"{destinatario}: código {codigo} - {mensagem}"
            )
        except Exception:
            partes.append(f"{destinatario}: {detalhe}")

    return "; ".join(partes)


def enviar_emails_em_lote(email_lista):
    """
    Envia mensagens de forma sequencial usando uma única conexão SMTP.

    Retorna (enviados, falhas, indisponivel).

    'enviados' contém SOMENTE destinatários que não foram recusados pelo
    servidor SMTP. Isso evita contabilizar como enviado um e-mail que o
    servidor rejeitou durante o comando RCPT TO/SMTP.
    """
    enviados = []
    falhas = []

    if not email_lista:
        return enviados, falhas, False

    if not ATIVAR_EMAILS:
        return enviados, [
            (item[0], item[1], "Envio de e-mails está desativado.")
            for item in email_lista
        ], True

    if not EMAIL_ESCOLA or not SENHA_APP_ESCOLA:
        return enviados, [
            (item[0], item[1], "EMAIL_ESCOLA ou SENHA_APP_ESCOLA não configurados.")
            for item in email_lista
        ], True

    server = None

    try:
        server = smtplib.SMTP(
            "smtp.gmail.com",
            587,
            timeout=30
        )
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(
            EMAIL_ESCOLA,
            SENHA_APP_ESCOLA
        )

        for nome, email, horario, data, status in email_lista:
            email_limpo = str(email or "").strip()

            if not email_limpo:
                falhas.append(
                    (nome, email_limpo, "E-mail vazio.")
                )
                continue

            status_normalizado = str(status or "").strip().upper()

            if status_normalizado == "PRESENTE":
                evento = "ENTRADA"
            elif status_normalizado == "ATRASO":
                evento = "ENTRADA COM ATRASO"
            else:
                falhas.append(
                    (
                        nome,
                        email_limpo,
                        f"Status de entrada inválido para e-mail: {status_normalizado!r}"
                    )
                )
                continue

            try:
                recusados = enviar_email_smtp(
                    server,
                    email_limpo,
                    nome,
                    evento,
                    horario,
                    data
                )

                if recusados:
                    falhas.append(
                        (
                            nome,
                            email_limpo,
                            "Destinatário recusado pelo servidor SMTP: "
                            + formatar_recusa_smtp(recusados)
                        )
                    )
                else:
                    enviados.append(
                        (nome, email_limpo)
                    )

            except smtplib.SMTPRecipientsRefused as e:
                falhas.append(
                    (
                        nome,
                        email_limpo,
                        f"Destinatário recusado pelo servidor: {e}"
                    )
                )

            except smtplib.SMTPException as e:
                falhas.append(
                    (
                        nome,
                        email_limpo,
                        f"Erro SMTP: {e}"
                    )
                )

            except Exception as e:
                falhas.append(
                    (
                        nome,
                        email_limpo,
                        f"Erro inesperado: {e}"
                    )
                )

    except smtplib.SMTPAuthenticationError as e:
        motivo = (
            "Falha de autenticação no Gmail. "
            "Verifique EMAIL_ESCOLA e SENHA_APP_ESCOLA. "
            f"Detalhe: {e}"
        )
        falhas = [
            (nome, email, motivo)
            for nome, email, *_ in email_lista
        ]

    except smtplib.SMTPException as e:
        motivo = (
            f"Não foi possível estabelecer o envio SMTP: {e}"
        )
        falhas = [
            (nome, email, motivo)
            for nome, email, *_ in email_lista
        ]

    except Exception as e:
        motivo = (
            f"Falha ao iniciar o serviço de e-mail: {e}"
        )
        falhas = [
            (nome, email, motivo)
            for nome, email, *_ in email_lista
        ]

    finally:
        if server is not None:
            try:
                server.quit()
            except Exception:
                pass

    return enviados, falhas, False


def disparar_email_background(
    email_destino,
    nome_aluno,
    evento,
    horario,
    data
):
    """
    Dispara uma notificação individual preservando exatamente o evento recebido:
    ENTRADA, ENTRADA COM ATRASO, SAÍDA REGULAR ou SAÍDA ANTECIPADA.
    """
    if not email_destino:
        return False, "E-mail vazio.", True

    if not ATIVAR_EMAILS:
        return False, "Envio de e-mails está desativado.", True

    if not EMAIL_ESCOLA or not SENHA_APP_ESCOLA:
        return (
            False,
            "EMAIL_ESCOLA ou SENHA_APP_ESCOLA não configurados.",
            True,
        )

    server = None

    try:
        server = smtplib.SMTP(
            "smtp.gmail.com",
            587,
            timeout=30,
        )
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(
            EMAIL_ESCOLA,
            SENHA_APP_ESCOLA,
        )

        email_limpo = str(email_destino).strip()
        recusados = enviar_email_smtp(
            server,
            email_limpo,
            nome_aluno,
            evento,
            horario,
            data,
        )

        if recusados:
            return (
                False,
                "Destinatário recusado pelo servidor SMTP: "
                + formatar_recusa_smtp(recusados),
                False,
            )

        return True, None, False

    except smtplib.SMTPRecipientsRefused as e:
        return (
            False,
            f"Destinatário recusado pelo servidor: {e}",
            False,
        )

    except smtplib.SMTPAuthenticationError as e:
        return (
            False,
            f"Falha de autenticação no Gmail: {e}",
            True,
        )

    except smtplib.SMTPException as e:
        return (
            False,
            f"Erro SMTP: {e}",
            False,
        )

    except Exception as e:
        return (
            False,
            f"Erro inesperado: {e}",
            False,
        )

    finally:
        if server is not None:
            try:
                server.quit()
            except Exception:
                pass


def mensagem_suspensao_email(nome_aluno, turma, data_inicio, data_fim, motivo):
    try:
        inicio = pd.to_datetime(data_inicio).strftime("%d/%m/%Y")
        fim = pd.to_datetime(data_fim).strftime("%d/%m/%Y")
    except Exception:
        inicio = str(data_inicio)
        fim = str(data_fim)

    assunto = "🏫 Comunicação de Suspensão Disciplinar - Jansen Veloso"
    texto = (
        f"Olá, família!\n\n"
        f"Informamos que o(a) estudante {nome_aluno}, da turma {turma}, "
        f"foi submetido(a) a uma SUSPENSÃO DISCIPLINAR.\n\n"
        f"Período da suspensão: {inicio} a {fim}.\n"
        f"Motivo: {motivo}.\n\n"
        f"Solicitamos a atenção do responsável para o cumprimento do período informado.\n\n"
        f"Atenciosamente,\nEquipe Jansen Veloso."
    )
    return assunto, texto


def enviar_email_suspensao_background(email_destino, nome_aluno, turma, data_inicio, data_fim, motivo):
    if not email_destino or not ATIVAR_EMAILS or not EMAIL_ESCOLA or not SENHA_APP_ESCOLA:
        return False, "Configuração de e-mail indisponível."

    server = None
    try:
        server = smtplib.SMTP("smtp.gmail.com", 587, timeout=30)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(EMAIL_ESCOLA, SENHA_APP_ESCOLA)
        assunto, texto = mensagem_suspensao_email(
            nome_aluno, turma, data_inicio, data_fim, motivo
        )
        msg = MIMEMultipart()
        msg["From"] = EMAIL_ESCOLA
        msg["To"] = str(email_destino).strip()
        msg["Subject"] = assunto
        msg.attach(MIMEText(texto, "plain", "utf-8"))
        recusados = server.send_message(msg) or {}
        if recusados:
            return False, "Destinatário recusado pelo servidor SMTP: " + formatar_recusa_smtp(recusados)
        return True, None
    except smtplib.SMTPException as e:
        return False, f"Erro SMTP: {e}"
    except Exception as e:
        return False, f"Erro inesperado: {e}"
    finally:
        if server is not None:
            try:
                server.quit()
            except Exception:
                pass


def mensagem_suspensao_whatsapp(nome_aluno, data_inicio, data_fim, motivo):
    try:
        inicio = pd.to_datetime(data_inicio).strftime("%d/%m/%Y")
        fim = pd.to_datetime(data_fim).strftime("%d/%m/%Y")
    except Exception:
        inicio = str(data_inicio)
        fim = str(data_fim)
    return (
        f"Olá, família!\n\n"
        f"Informamos que o(a) estudante {nome_aluno} recebeu uma SUSPENSÃO DISCIPLINAR.\n\n"
        f"Período: {inicio} a {fim}.\n"
        f"Motivo: {motivo}.\n\n"
        f"Atenciosamente,\nEquipe Jansen Veloso."
    )


@st.cache_resource 
def carregar_logo_base64():
    if os.path.exists("logo.png"):
        try:
            with open("logo.png", "rb") as image_file: 
                return base64.b64encode(image_file.read()).decode()
        except: 
            return None
    return None

def renderizar_logo_central():
    encoded_string = carregar_logo_base64()
    if encoded_string:
        st.markdown(f'<div style="display: flex; justify-content: center; margin-bottom: 10px;"><img src="data:image/png;base64,{encoded_string}" width="170"></div>', unsafe_allow_html=True)

# ------------------------------------------------------------
# 4. INICIALIZAÇÃO DE TABELAS (INCLUINDO CONFIGURACOES)
# ------------------------------------------------------------
@st.cache_resource
def inicializar_tabelas():
    conn = conectar_bd()
    if not conn: 
        return
    try:
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS alunos_v2 (codigo TEXT PRIMARY KEY, nome TEXT, turma TEXT, status TEXT DEFAULT 'ATIVO', email_responsavel TEXT, telefone_responsavel TEXT)")
        cur.execute("CREATE TABLE IF NOT EXISTS registros_v2 (id SERIAL PRIMARY KEY, codigo_aluno TEXT REFERENCES alunos_v2(codigo), data DATE, hora_entrada TIME, status_entrada TEXT, hora_saida TIME, motivo_saida TEXT, pais_informados BOOLEAN, tipo_registro TEXT, origem_entrada TEXT, UNIQUE(codigo_aluno, data, tipo_registro))")
        cur.execute("""CREATE TABLE IF NOT EXISTS suspensoes_v1 (
            id SERIAL PRIMARY KEY,
            codigo_aluno TEXT REFERENCES alunos_v2(codigo),
            data_inicio DATE NOT NULL,
            data_fim DATE NOT NULL,
            motivo TEXT NOT NULL,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_susp_codigo_datas ON suspensoes_v1(codigo_aluno, data_inicio, data_fim)")
        try:
            cur.execute("ALTER TABLE registros_v2 ADD COLUMN origem_entrada TEXT")
            conn.commit()
        except Exception:
            conn.rollback()
        cur.execute("CREATE TABLE IF NOT EXISTS avaliacoes_avs (id SERIAL PRIMARY KEY, ano TEXT, periodo TEXT, area TEXT, turma TEXT, nome TEXT, disciplina TEXT, questao INTEGER, resposta TEXT, gabarito TEXT, acerto INTEGER, UNIQUE(ano, periodo, area, turma, nome, disciplina, questao))")
        cur.execute("""CREATE TABLE IF NOT EXISTS faltas_primeira_chamada (
            id SERIAL PRIMARY KEY, codigo_aluno TEXT REFERENCES alunos_v2(codigo), ano TEXT, periodo TEXT, area TEXT, motivo TEXT, data_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP, UNIQUE(codigo_aluno, ano, periodo, area)
        )""")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS configuracoes (
                chave TEXT PRIMARY KEY,
                valor TEXT,
                atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        try:
            cur.execute("ALTER TABLE alunos_v2 ADD COLUMN telefone_responsavel TEXT")
            conn.commit()
        except Exception:
            conn.rollback()
        try: 
            cur.execute("ALTER TABLE faltas_primeira_chamada ADD COLUMN area TEXT DEFAULT 'GERAL'")
            conn.commit()
        except Exception: 
            conn.rollback() 
        try:
            cur.execute("SELECT constraint_name FROM information_schema.table_constraints WHERE table_name='faltas_primeira_chamada' AND constraint_type='UNIQUE'")
            constraints = cur.fetchall()
            for c in constraints: 
                cur.execute(f"ALTER TABLE faltas_primeira_chamada DROP CONSTRAINT {c[0]}")
            cur.execute("ALTER TABLE faltas_primeira_chamada ADD UNIQUE (codigo_aluno, ano, periodo, area)")
            conn.commit()
        except Exception: 
            conn.rollback()
        try: 
            cur.execute("ALTER TABLE avaliacoes_avs ADD COLUMN ano TEXT DEFAULT '2026'")
            conn.commit()
        except Exception: 
            conn.rollback()
        try:
            cur.execute("SELECT constraint_name FROM information_schema.table_constraints WHERE table_name='avaliacoes_avs' AND constraint_type='UNIQUE'")
            constraints = cur.fetchall()
            for c in constraints: 
                cur.execute(f"ALTER TABLE avaliacoes_avs DROP CONSTRAINT {c[0]}")
            cur.execute("ALTER TABLE avaliacoes_avs ADD UNIQUE (ano, periodo, area, turma, nome, disciplina, questao)")
            conn.commit()
        except Exception: 
            conn.rollback()
        cur.execute("""CREATE TABLE IF NOT EXISTS satisfacao_v1 (
            id SERIAL PRIMARY KEY, data_hora TIMESTAMP, categoria TEXT, turma TEXT, q1 INTEGER, q2 INTEGER, q3 INTEGER, q4 INTEGER, q5 INTEGER, sugestao TEXT
        )""")
        cur.execute("CREATE TABLE IF NOT EXISTS calendario_letivo (data DATE PRIMARY KEY, dia_letivo BOOLEAN DEFAULT TRUE)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_reg_data ON registros_v2(data)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_avs_geral ON avaliacoes_avs(ano, periodo, area, turma)")
        conn.commit()
        for tb in ['alunos_v2', 'registros_v2', 'avaliacoes_avs', 'faltas_primeira_chamada', 'satisfacao_v1', 'calendario_letivo', 'configuracoes']:
            try: 
                cur.execute(f"ALTER TABLE {tb} ENABLE ROW LEVEL SECURITY;")
                conn.commit()
            except Exception: 
                conn.rollback() 
    except Exception as e: 
        print(f"Erro inicialização: {e}")
    finally: 
        liberar_conn(conn)

# inicializar_tabelas() será executada somente após autenticação.

# ------------------------------------------------------------
# 5. CSS
# ------------------------------------------------------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap');
    :root { --primary: #0a1f35; --accent: #ff7b00; --success: #10b981; --danger: #ef4444; --bg-color: #f8fafc; }
    .stApp { background: var(--bg-color); }
    #MainMenu, footer, header {visibility: hidden;}
    html, body, [class*="css"], p, span, label, div { font-size: 1.15rem !important; }
    [data-testid="stRadio"] div[role="radiogroup"] > label { font-size: 1.3rem !important; padding: 16px 15px !important; margin-bottom: 12px !important; background-color: #ffffff !important; color: #000000 !important; border: 2px solid #cbd5e1 !important; border-radius: 12px; box-shadow: 0 3px 6px rgba(0,0,0,0.04); cursor: pointer; transition: all 0.2s ease; }
    [data-testid="stRadio"] div[role="radiogroup"] > label * { color: #000000 !important; -webkit-text-fill-color: #000000 !important; }
    [data-testid="stRadio"] div[role="radiogroup"] > label:hover { border-color: var(--accent) !important; transform: translateY(-2px); }
    .main-title { font-family: 'Inter', sans-serif; font-weight: 900; font-size: clamp(3.5rem, 8vw, 4.8rem); color: var(--primary); text-align: center; margin:0; text-transform: uppercase; letter-spacing: -2px;}
    .sub-title { font-family: 'Inter', sans-serif; font-size: 1.6rem; color: #64748b; text-align: center; margin-bottom: 2rem; font-weight: 700;}
    .metrics-container { display: grid; grid-template-columns: repeat(5, 1fr); gap: 1.5rem; margin-bottom: 2rem; }
    @media (max-width: 1400px) { .metrics-container { grid-template-columns: repeat(3, 1fr); } }
    @media (max-width: 1000px) { .metrics-container { grid-template-columns: repeat(2, 1fr); } }
    @media (max-width: 800px) { .metrics-container { grid-template-columns: 1fr; } }
    .metric-card { background: white; padding: 2.5rem 1.5rem; border-radius: 20px; box-shadow: 0 8px 25px rgba(0,0,0,0.06); text-align: center; position: relative; overflow: hidden; border: 2px solid #e2e8f0; transition: transform 0.2s ease;}
    .metric-card:hover { transform: translateY(-5px); }
    .metric-card::before { content: ''; position: absolute; top: 0; left: 0; right: 0; height: 10px; }
    .m-total::before { background: #0ea5e9; } .m-presente::before { background: var(--success); } .m-liberado::before { background: #8b5cf6; } .m-falta::before { background: var(--danger); } .m-atraso::before { background: #f59e0b; } .m-acad::before { background: #8b5cf6; } .m-satest::before { background: #10b981; } .m-satpais::before { background: #f59e0b; } .m-sateq::before { background: #3b82f6; }
    .m-val { font-size: 4rem; font-weight: 900; color: #0f172a; display: block; line-height: 1.1; letter-spacing: -2px; text-shadow: 2px 2px 4px rgba(0,0,0,0.05); }
    .m-current { display: block; margin-top: 0.5rem; font-size: 1.25rem; font-weight: 900; color: #0f766e; letter-spacing: 0.5px; }
    .m-lab { font-size: 1.2rem; font-weight: 900; color: #475569; text-transform: uppercase; letter-spacing: 1px; margin-top: 1rem; display: block; }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; padding-bottom: 0px; flex-wrap: wrap; }
    .stTabs [data-baseweb="tab"] { background-color: #f1f5f9 !important; border: 3px solid #cbd5e1 !important; border-bottom: none !important; border-radius: 18px 18px 0 0 !important; padding: 15px 25px !important; font-size: 1.5rem !important; font-weight: 900 !important; color: #64748b !important; transition: all 0.3s ease !important; }
    .stTabs [data-baseweb="tab"]:hover { background-color: #e2e8f0 !important; color: var(--primary) !important; }
    .stTabs [aria-selected="true"] { background-color: var(--primary) !important; color: #ffffff !important; border: 5px solid var(--accent) !important; border-bottom: none !important; transform: translateY(-4px); box-shadow: 0 -8px 25px rgba(255, 123, 0, 0.35) !important; }
    div[data-baseweb="input"] { border: 2px solid #cbd5e1 !important; border-radius: 12px !important; background-color: #ffffff !important; }
    div[data-baseweb="input"] input { color: #000000 !important; -webkit-text-fill-color: #000000 !important; font-weight: 900 !important; font-size: 1.5rem !important; padding: 1rem 1.2rem !important; }
    div[data-baseweb="input"]:focus-within { border-color: var(--accent) !important; box-shadow: 0 0 0 4px rgba(255, 123, 0, 0.2) !important; }
    [data-baseweb="select"] > div { background-color: #ffffff !important; border: 2.5px solid #0a1f35 !important; border-radius: 12px !important; height: 55px !important; color: #000000 !important; }
    [data-baseweb="select"] span { color: #000000 !important; -webkit-text-fill-color: #000000 !important; font-weight: 900 !important; font-size: 1.4rem !important;}
    ul[data-baseweb="menu"] { background-color: #ffffff !important; }
    ul[data-baseweb="menu"] li { color: #000000 !important; -webkit-text-fill-color: #000000 !important; }
    .stButton > button { border-radius: 12px !important; font-weight: 800 !important; font-size: 1.3rem !important; padding: 0.8rem 2rem !important; border: none !important; transition: all 0.2s ease !important; }
    [data-testid="stFormSubmitButton"] > button { background: linear-gradient(135deg, var(--primary), #1a4b82) !important; color: white !important; box-shadow: 0 6px 15px rgba(10, 31, 53, 0.3) !important; width: 100% !important; text-transform: uppercase !important; font-size: 1.4rem !important;}
    [data-testid="stFormSubmitButton"] > button:active { transform: scale(0.95); }
    .login-title { font-size: 2.2rem; font-weight: 900; color: var(--primary); margin-bottom: 1.5rem; text-align: center; }
    [data-testid="stDataFrame"] { font-size: 1.2rem !important; }
    .streamlit-expanderHeader { font-size: 1.3rem !important; font-weight: bold !important; }
    .top7-card { background: linear-gradient(135deg, #ffffff, #f8fafc); border-left: 12px solid var(--accent); padding: 3rem 1.5rem; border-radius: 20px; margin-bottom: 1.5rem; box-shadow: 0 10px 30px rgba(0,0,0,0.08); text-align: center;}
    .top7-medal { font-size: 3.8rem !important; font-weight: 900; color: var(--primary); margin-bottom: 0.5rem; letter-spacing: -1px;}
    .top7-name { font-size: 4.5rem !important; font-weight: 900; color: var(--primary); letter-spacing: -2px; margin: 1.5rem 0; line-height: 1.1; text-transform: uppercase;}
    .top7-name-hidden { font-size: 4.5rem !important; font-weight: 900; color: #94a3b8; filter: blur(12px); user-select: none; margin: 1.5rem 0; line-height: 1.1;}
    .top7-details { font-size: 1.8rem !important; color: #64748b; font-weight: 800; background: #e2e8f0; display: inline-block; padding: 0.5rem 1.5rem; border-radius: 30px;}

    /* ---------------------------------------------------------
       MENU LATERAL - navegação principal
       --------------------------------------------------------- */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #f8fafc 0%, #eef4fa 100%) !important;
        border-right: 1px solid #dbe4ee !important;
    }
    section[data-testid="stSidebar"] .menu-header {
        background: linear-gradient(135deg, #0a1f35 0%, #1a4b82 100%);
        color: #ffffff;
        border-radius: 16px;
        padding: 14px 18px;
        margin: 8px 0 18px 0;
        text-align: center;
        font-size: 1.45rem !important;
        font-weight: 900;
        letter-spacing: 1px;
        box-shadow: 0 7px 18px rgba(10,31,53,.18);
    }
    section[data-testid="stSidebar"] [data-testid="stRadio"] > div {
        gap: 10px !important;
    }
    section[data-testid="stSidebar"] div[role="radiogroup"] > label {
        display: flex !important;
        align-items: center !important;
        min-height: 54px !important;
        padding: 10px 14px !important;
        margin: 0 !important;
        border: 2px solid #d8e1eb !important;
        border-radius: 14px !important;
        background: #ffffff !important;
        box-shadow: 0 3px 10px rgba(15,23,42,.05) !important;
        color: #1e293b !important;
        font-size: 1.08rem !important;
        font-weight: 850 !important;
        transition: .18s ease !important;
    }
    section[data-testid="stSidebar"] div[role="radiogroup"] > label:hover {
        transform: translateX(3px);
        box-shadow: 0 6px 14px rgba(15,23,42,.10) !important;
    }
    section[data-testid="stSidebar"] div[role="radiogroup"] > label:nth-child(1) { border-left: 7px solid #0ea5e9 !important; }
    section[data-testid="stSidebar"] div[role="radiogroup"] > label:nth-child(2) { border-left: 7px solid #10b981 !important; }
    section[data-testid="stSidebar"] div[role="radiogroup"] > label:nth-child(3) { border-left: 7px solid #f97316 !important; }
    section[data-testid="stSidebar"] div[role="radiogroup"] > label:nth-child(4) { border-left: 7px solid #8b5cf6 !important; }
    section[data-testid="stSidebar"] div[role="radiogroup"] > label:nth-child(5) { border-left: 7px solid #3b82f6 !important; }
    section[data-testid="stSidebar"] div[role="radiogroup"] > label:nth-child(6) { border-left: 7px solid #ec4899 !important; }
    section[data-testid="stSidebar"] div[role="radiogroup"] > label:nth-child(7) { border-left: 7px solid #f59e0b !important; }
    section[data-testid="stSidebar"] div[role="radiogroup"] > label:nth-child(8) { border-left: 7px solid #14b8a6 !important; }
    section[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) {
        background: linear-gradient(90deg, #0a1f35 0%, #173f6d 100%) !important;
        color: #ffffff !important;
        border-color: #0a1f35 !important;
        box-shadow: 0 8px 18px rgba(10,31,53,.20) !important;
    }
    section[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) * {
        color: #ffffff !important;
        -webkit-text-fill-color: #ffffff !important;
    }
    section[data-testid="stSidebar"] .stButton > button {
        width: 100%;
        border: 2px solid #d8e1eb !important;
        background: #ffffff !important;
        color: #0a1f35 !important;
    }
    section[data-testid="stSidebar"] .stButton > button:hover {
        border-color: #ff7b00 !important;
        color: #ff7b00 !important;
    }
    /* Oculta apenas a navegação nativa de páginas do Streamlit. */
    div[data-testid="stSidebarNav"] {
        display: none !important;
    }

    /* Botão nativo de abrir/fechar a barra lateral: mostra MENU. */
    div[data-testid="stSidebarCollapseButton"] button,
    div[data-testid="stSidebarCollapsedControl"] button,
    div[data-testid="collapsedControl"] button {
        width: 125px !important;
        min-width: 125px !important;
        height: 48px !important;
        min-height: 48px !important;
        border-radius: 14px !important;
        background: linear-gradient(135deg, #0a1f35 0%, #1a4b82 100%) !important;
        color: #ffffff !important;
        box-shadow: 0 6px 16px rgba(10,31,53,.20) !important;
        padding: 0 !important;
        border: none !important;
    }

    div[data-testid="stSidebarCollapseButton"] button:hover,
    div[data-testid="stSidebarCollapsedControl"] button:hover,
    div[data-testid="collapsedControl"] button:hover {
        background: linear-gradient(135deg, #102d4c 0%, #245d98 100%) !important;
        transform: translateY(-1px);
    }

    div[data-testid="stSidebarCollapseButton"] button svg,
    div[data-testid="stSidebarCollapsedControl"] button svg,
    div[data-testid="collapsedControl"] button svg {
        display: none !important;
    }

    div[data-testid="stSidebarCollapseButton"] button::after,
    div[data-testid="stSidebarCollapsedControl"] button::after,
    div[data-testid="collapsedControl"] button::after {
        content: "☰  MENU";
        color: #ffffff !important;
        -webkit-text-fill-color: #ffffff !important;
        font-size: 1.05rem !important;
        font-weight: 900 !important;
        letter-spacing: 0.8px !important;
        line-height: 1 !important;
    }

    div[data-testid="stExpander"]:nth-child(even) { background-color: #f8fafc; border-radius: 12px; border: 1px solid #cbd5e1; margin-bottom: 10px;}
    div[data-testid="stExpander"]:nth-child(odd) { background-color: #e2e8f0; border-radius: 12px; border: 1px solid #94a3b8; margin-bottom: 10px;}

    /* =========================================================
       PAINEL INFORMATIVO — VISUAL PÚBLICO
       ========================================================= */
    .info-panel-hero {
        background: linear-gradient(135deg, #0a1f35 0%, #1a4b82 58%, #0f766e 100%);
        border-radius: 24px;
        padding: 28px 30px;
        color: #ffffff;
        margin: 10px 0 24px 0;
        box-shadow: 0 14px 35px rgba(10,31,53,.18);
        position: relative;
        overflow: hidden;
    }
    .info-panel-hero::after {
        content: '';
        position: absolute;
        width: 230px;
        height: 230px;
        border-radius: 50%;
        background: rgba(255,255,255,.08);
        right: -65px;
        top: -80px;
    }
    .info-panel-title { font-size: 2.45rem !important; font-weight: 900 !important; margin: 0; letter-spacing: -.5px; }
    .info-panel-subtitle { font-size: 1.15rem !important; margin: 7px 0 0 0; opacity: .92; font-weight: 700; }
    .info-filter-card { background: #ffffff; border: 2px solid #dbe4ee; border-radius: 18px; padding: 16px 18px; box-shadow: 0 6px 18px rgba(15,23,42,.06); margin-bottom: 20px; }
    .info-section { border-radius: 22px; padding: 18px; background: #ffffff; border: 2px solid #e2e8f0; box-shadow: 0 8px 24px rgba(15,23,42,.06); height: 100%; }
    .info-section-title { font-size: 1.55rem !important; font-weight: 900 !important; margin-bottom: 4px; }
    .info-section-count { font-size: 1rem !important; color: #64748b; font-weight: 800; margin-bottom: 14px; }
    .info-student { padding: 13px 14px; margin: 9px 0; border-radius: 14px; border: 1px solid #e2e8f0; background: linear-gradient(90deg,#f8fafc,#ffffff); }
    .info-student-name { font-weight: 900; color: #0f172a; font-size: 1.03rem; }
    .info-student-meta { color: #64748b; font-size: .93rem; font-weight: 700; margin-top: 2px; }
    .info-empty { padding: 35px 16px; text-align: center; color: #64748b; font-weight: 800; }
    .info-public-note { text-align:center; color:#64748b; font-size:.92rem; margin-top:18px; }
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------
# 6.0 FUNÇÕES DE COMUNICAÇÃO VIA WHATSAPP
# ------------------------------------------------------------
def normalizar_telefone_whatsapp(valor):
    if valor is None or pd.isna(valor):
        return ""
    texto = str(valor).strip()
    if not texto:
        return ""
    digitos = re.sub(r"\D", "", texto)
    if digitos.startswith("00"):
        digitos = digitos[2:]
    if digitos.startswith("55") and len(digitos) in (12, 13):
        return digitos
    if len(digitos) in (10, 11):
        return "55" + digitos
    return digitos


def gerar_link_whatsapp(telefone, mensagem):
    numero = normalizar_telefone_whatsapp(telefone)
    if not numero or len(numero) < 12 or len(numero) > 13:
        return None
    return f"https://web.whatsapp.com/send?phone={numero}&text={quote(mensagem)}"


def mensagem_falta_whatsapp(nome_aluno, data):
    try:
        data_f = datetime.strptime(str(data), "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        data_f = str(data)
    return (
        f"Olá, família!\n\n"
        f"Informamos que o estudante {nome_aluno} não registrou presença "
        f"na escola no dia {data_f}.\n\n"
        f"Caso a falta já esteja justificada, desconsidere esta mensagem.\n\n"
        f"Atenciosamente,\nEquipe Jansen Veloso."
    )

# ------------------------------------------------------------
# 6. LÓGICA DE NEGÓCIO E CACHES
# ------------------------------------------------------------
def _fetch_dia_letivo_db(data_atual):
    conn = conectar_bd()
    if not conn: 
        raise ConnectionError("Sem conexão com o banco de dados")
    try:
        cur = conn.cursor()
        cur.execute("SELECT dia_letivo FROM calendario_letivo WHERE data = %s", (data_atual,))
        res = cur.fetchone()
        if res: 
            return res[0]
        return False
    finally:
        liberar_conn(conn)

@st.cache_data(ttl=300)
def _verificar_dia_letivo_cache(data_atual):
    return _fetch_dia_letivo_db(data_atual)

def verificar_dia_letivo(data_atual):
    if 'cache_dias_letivos' not in st.session_state:
        st.session_state['cache_dias_letivos'] = {}
    try:
        resultado = _verificar_dia_letivo_cache(data_atual)
        st.session_state['cache_dias_letivos'][data_atual] = resultado
        return resultado
    except Exception:
        return st.session_state['cache_dias_letivos'].get(data_atual, False)

def _fetch_alunos_db():
    conn = conectar_bd()
    if not conn: 
        raise ConnectionError("Sem conexão com o banco de dados")
    try:
        return pd.read_sql("SELECT codigo, nome, turma, status, email_responsavel, telefone_responsavel FROM alunos_v2 ORDER BY turma, nome", conn)
    finally:
        liberar_conn(conn)

@st.cache_data(ttl=3600)
def _carregar_alunos_cache():
    return _fetch_alunos_db()

def carregar_alunos():
    try:
        df = _carregar_alunos_cache()
        st.session_state['ultimo_df_alunos_ok'] = df
        return df
    except Exception:
        if 'ultimo_df_alunos_ok' in st.session_state:
            return st.session_state['ultimo_df_alunos_ok']
        return pd.DataFrame(columns=['codigo','nome','turma','status','email_responsavel','telefone_responsavel'])

@st.cache_data(ttl=60)
def contar_presencas_data(data_str, turma="Todas"):
    conn = None
    try:
        conn = conectar_bd()
        if not conn:
            return 0
        cur = conn.cursor()
        if turma == "Todas":
            cur.execute(
                "SELECT COUNT(*) FROM registros_v2 WHERE data=%s AND tipo_registro='PRESENCA'",
                (data_str,),
            )
        else:
            cur.execute(
                "SELECT COUNT(r.id) FROM registros_v2 r "
                "JOIN alunos_v2 a ON r.codigo_aluno = a.codigo "
                "WHERE r.data=%s AND r.tipo_registro='PRESENCA' AND a.turma=%s",
                (data_str, turma),
            )
        return int(cur.fetchone()[0] or 0)
    except Exception:
        return 0
    finally:
        liberar_conn(conn)

@st.cache_data(ttl=30)
def carregar_resumo_dashboard(data_str, turma="Todas", horario_limite_saida_str="17:00:00"):
    """Retorna total ativo, entradas registradas, liberados antes do horário e presentes atuais."""
    conn = None
    try:
        conn = conectar_bd()
        if not conn:
            return 0, 0, 0, 0

        cur = conn.cursor()

        # Horário padrão da saída escolar. Quando o usuário configura outro
        # horário na aba de registro, ele fica disponível na sessão.
        h_limite_saida = st.session_state.get(
            "h_lim_s_atual",
            datetime.strptime(horario_limite_saida_str, "%H:%M:%S").time()
        )

        if turma == "Todas":
            cur.execute("SELECT COUNT(*) FROM alunos_v2 WHERE status = 'ATIVO'")
            total_alunos = int(cur.fetchone()[0] or 0)

            cur.execute("""
                SELECT r.codigo_aluno, r.hora_saida
                FROM registros_v2 r
                JOIN alunos_v2 a ON a.codigo = r.codigo_aluno
                WHERE r.data = %s
                  AND r.tipo_registro = 'PRESENCA'
                  AND a.status = 'ATIVO'
            """, (data_str,))
        else:
            cur.execute(
                "SELECT COUNT(*) FROM alunos_v2 WHERE status = 'ATIVO' AND turma = %s",
                (turma,)
            )
            total_alunos = int(cur.fetchone()[0] or 0)

            cur.execute("""
                SELECT r.codigo_aluno, r.hora_saida
                FROM registros_v2 r
                JOIN alunos_v2 a ON a.codigo = r.codigo_aluno
                WHERE r.data = %s
                  AND r.tipo_registro = 'PRESENCA'
                  AND a.status = 'ATIVO'
                  AND a.turma = %s
            """, (data_str, turma))

        registros = cur.fetchall()

        entradas = len({row[0] for row in registros})
        liberados_antes = sum(
            1 for _, hora_saida in registros
            if hora_saida is not None and hora_saida < h_limite_saida
        )
        presentes_atuais = max(entradas - liberados_antes, 0)

        return total_alunos, entradas, presentes_atuais, liberados_antes
    except Exception:
        return 0, 0, 0, 0
    finally:
        liberar_conn(conn)

@st.cache_data(ttl=60)
def carregar_faltas(data_str):
    conn = None
    try:
        conn = conectar_bd()
        if not conn:
            return pd.DataFrame()
        query = """
            SELECT a.codigo as codigo_aluno, a.nome, a.turma, r.motivo_saida
            FROM alunos_v2 a
            LEFT JOIN registros_v2 r
                ON a.codigo = r.codigo_aluno
               AND r.data = %s
               AND r.tipo_registro = 'FALTA'
            WHERE a.status = 'ATIVO'
              AND NOT EXISTS (
                  SELECT 1
                  FROM registros_v2 p
                  WHERE p.codigo_aluno = a.codigo
                    AND p.data = %s
                    AND p.tipo_registro = 'PRESENCA'
              )
            ORDER BY a.turma, a.nome
        """
        return pd.read_sql(query, conn, params=[data_str, data_str])
    except Exception as e:
        print(f"Erro ao carregar faltas: {e}")
        return pd.DataFrame()
    finally:
        liberar_conn(conn)

@st.cache_data(ttl=60)
def carregar_faltas_primeira_chamada(ano):
    query = """
        SELECT a.nome, a.turma, f.periodo, f.area, f.motivo, TO_CHAR(f.data_registro, 'DD/MM/YYYY') as data_registro 
        FROM faltas_primeira_chamada f JOIN alunos_v2 a ON f.codigo_aluno = a.codigo WHERE f.ano = %s ORDER BY f.periodo, f.area, a.turma, a.nome
    """
    conn = conectar_bd()
    if not conn: 
        return pd.DataFrame()
    try:
        df = pd.read_sql(query, conn, params=[str(ano)])
        return df
    except Exception: 
        return pd.DataFrame()
    finally: 
        liberar_conn(conn)

@st.cache_data(ttl=300)
def obter_dados_acad_filtrados(ano, p, a, t):
    conditions = ["avs.ano = %s"]
    params = [str(ano)]
    if p != "Todos": 
        conditions.append("avs.periodo = %s")
        params.append(p)
    if a != "Todas": 
        conditions.append("avs.area = %s")
        params.append(a)
    if t != "Todas": 
        conditions.append("COALESCE(al.turma, avs.turma) = %s")
        params.append(t)
    where_clause = " AND ".join(conditions)
    query = f"SELECT avs.id, avs.ano, avs.periodo, avs.area, COALESCE(al.turma, avs.turma) as turma, avs.nome, avs.disciplina, avs.questao, avs.resposta, avs.gabarito, avs.acerto FROM avaliacoes_avs avs LEFT JOIN alunos_v2 al ON avs.nome = al.nome WHERE {where_clause}"
    conn = conectar_bd()
    if not conn: 
        return pd.DataFrame()
    try: 
        df = pd.read_sql(query, conn, params=params)
    except Exception: 
        df = pd.DataFrame()
    finally: 
        liberar_conn(conn)
    if not df.empty and 'disciplina' in df.columns:
        df['disciplina'] = df['disciplina'].replace({'LÍNGUA PORTUGESA': 'LÍNGUA PORTUGUESA', 'SOCIOLGIA': 'SOCIOLOGIA'})
    return df

@st.cache_data(ttl=300)
def obter_estatisticas_areas_cached(ano, p, a, t):
    df_filtrado = obter_dados_acad_filtrados(ano, p, a, t)
    alertas_estudante = {}
    area_stats = pd.DataFrame()
    if not df_filtrado.empty:
        area_stats = df_filtrado.groupby(['nome', 'turma', 'periodo', 'area']).agg(Total=('questao', 'count'), Brancos=('resposta', lambda x: (x == 'BRANCO').sum()), Duplas=('resposta', lambda x: (x == 'DUPLA').sum())).reset_index()
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
    return alertas_estudante, area_stats

@st.cache_data(ttl=300)
def obter_top7_cached(ano, p, a, t):
    dff = obter_dados_acad_filtrados(ano, p, a, t)
    if dff.empty: 
        return pd.DataFrame()
    return dff.groupby(['nome','turma']).acerto.mean().reset_index().sort_values('acerto', ascending=False).head(7)

@st.cache_data(ttl=300)
def obter_resumo_estudantes_cached(ano, p, a, t):
    dff = obter_dados_acad_filtrados(ano, p, a, t)
    if dff.empty: 
        return pd.DataFrame(), []
    res_al = dff.groupby(['nome','turma']).acerto.mean().reset_index()
    erros_n = dff[dff['resposta'].isin(['BRANCO','DUPLA'])]['nome'].unique()
    return res_al, erros_n

@st.cache_data(ttl=300)
def obter_top3_erros_cached(ano, p, a, t):
    dff = obter_dados_acad_filtrados(ano, p, a, t)
    if dff.empty: 
        return pd.DataFrame()
    q_err = dff.groupby(['turma', 'periodo', 'disciplina', 'questao']).agg(Total=('questao', 'count'), Acertos=('acerto', 'sum')).reset_index()
    q_err['Taxa de Erro (%)'] = ((q_err['Total'] - q_err['Acertos']) / q_err['Total']) * 100
    q_err_top3 = q_err[q_err['Taxa de Erro (%)'] > 0].sort_values(['turma', 'periodo', 'disciplina', 'Taxa de Erro (%)'], ascending=[True, True, True, False]).groupby(['turma', 'periodo', 'disciplina']).head(3)
    return q_err_top3

@st.cache_data(ttl=300)
def carregar_satisfacao_por_ano(ano):
    query = "SELECT * FROM satisfacao_v1 WHERE EXTRACT(YEAR FROM data_hora) = %s"
    conn = conectar_bd()
    if not conn: 
        return pd.DataFrame()
    try:
        df = pd.read_sql(query, conn, params=[int(ano)])
        if not df.empty: 
            df['media_resposta'] = df[['q1','q2','q3','q4','q5']].mean(axis=1)
        return df
    except Exception: 
        return pd.DataFrame()
    finally: 
        liberar_conn(conn)

@st.cache_data(ttl=300)
def calcular_satisfacao_global_cached(ano, tf):
    df_sat = carregar_satisfacao_por_ano(ano)
    sat_est_str = "--"
    sat_pais_str = "--"
    sat_eq_str = "--"
    if not df_sat.empty:
        df_sat_est = df_sat[df_sat['categoria'] == 'Estudante']
        if tf != "Todas": 
            df_sat_est = df_sat_est[df_sat_est['turma'] == tf]
        if not df_sat_est.empty: 
            sat_est_str = f"{df_sat_est['media_resposta'].mean():.1f} / 5"
        df_sat_pais = df_sat[df_sat['categoria'] == 'Pais/Responsável']
        if not df_sat_pais.empty: 
            sat_pais_str = f"{df_sat_pais['media_resposta'].mean():.1f} / 5"
        df_sat_eq = df_sat[df_sat['categoria'].isin(['Professor', 'Servidor'])]
        if not df_sat_eq.empty: 
            sat_eq_str = f"{df_sat_eq['media_resposta'].mean():.1f} / 5"
    return sat_est_str, sat_pais_str, sat_eq_str

def importar_csv_alunos(file):
    conteudo_bytes = file.read()
    try: 
        conteudo_str = conteudo_bytes.decode('utf-8-sig')
    except: 
        conteudo_str = conteudo_bytes.decode('latin-1')
    df = pd.read_csv(io.StringIO(conteudo_str), sep=';')
    def norm(c): 
        return ''.join(x for x in unicodedata.normalize('NFD', str(c)) if unicodedata.category(x) != 'Mn').strip().upper()
    df.columns = [norm(col) for col in df.columns]
    dados = [(str(r['CODIGO']).upper(), str(r['NOME']).upper(), str(r['TURMA']).upper(), 'ATIVO') for _, r in df.iterrows()]
    conn = conectar_bd()
    if not conn: 
        return False
    try:
        cur = conn.cursor()
        execute_values(cur, "INSERT INTO alunos_v2 (codigo, nome, turma, status) VALUES %s ON CONFLICT (codigo) DO UPDATE SET nome=EXCLUDED.nome, turma=EXCLUDED.turma", dados)
        conn.commit()
        _carregar_alunos_cache.clear()
        return True
    finally: 
        liberar_conn(conn)

# ------------------------------------------------------------
# 6.1 FUNÇÕES PARA GERENCIAR O LINK DA PLANILHA
# ------------------------------------------------------------
def salvar_link_planilha(link):
    conn = conectar_bd()
    if not conn:
        return False
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO configuracoes (chave, valor, atualizado_em)
            VALUES ('link_entrada', %s, CURRENT_TIMESTAMP)
            ON CONFLICT (chave) DO UPDATE SET valor = EXCLUDED.valor, atualizado_em = CURRENT_TIMESTAMP
        """, (link,))
        conn.commit()
        return True
    except Exception as e:
        print(f"Erro ao salvar link: {e}")
        return False
    finally:
        liberar_conn(conn)

def obter_link_planilha():
    conn = conectar_bd()
    if not conn:
        return None
    try:
        cur = conn.cursor()
        cur.execute("SELECT valor FROM configuracoes WHERE chave = 'link_entrada'")
        res = cur.fetchone()
        return res[0] if res else None
    except Exception:
        return None
    finally:
        liberar_conn(conn)

def excluir_link_planilha():
    conn = conectar_bd()
    if not conn:
        return False
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM configuracoes WHERE chave = 'link_entrada'")
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        liberar_conn(conn)

# ------------------------------------------------------------
# 6.2 FUNÇÃO PARA NORMALIZAR COLUNAS
# ------------------------------------------------------------
def normalizar_colunas(df):
    import unicodedata
    new_cols = []
    for col in df.columns:
        col_norm = ''.join(c for c in unicodedata.normalize('NFD', str(col)) 
                           if unicodedata.category(c) != 'Mn')
        col_norm = col_norm.strip().upper()
        new_cols.append(col_norm)
    df.columns = new_cols
    return df

# ------------------------------------------------------------
# 6.3A FUNÇÃO ROBUSTA PARA PRESERVAR A HORA REAL DA FONTE
# ------------------------------------------------------------
def normalizar_hora_entrada(valor):
    """
    Converte a hora ORIGINAL da planilha/CSV para datetime.time,
    preservando a hora real registrada na fonte.

    Aceita:
      - datetime.time
      - datetime.datetime
      - strings HH:MM:SS / HH:MM
      - strings com data + hora
      - valores numéricos de fração do dia usados por planilhas

    Nunca usa a hora atual do servidor como fallback.
    Se não for possível interpretar o valor, retorna None.
    """
    if valor is None or pd.isna(valor):
        return None

    if isinstance(valor, datetime):
        return valor.time().replace(microsecond=0)

    # pandas Timestamp / datetime-like
    if hasattr(valor, "to_pydatetime"):
        try:
            return valor.to_pydatetime().time().replace(microsecond=0)
        except Exception:
            pass

    # datetime.time
    try:
        from datetime import time as dt_time
        if isinstance(valor, dt_time):
            return valor.replace(microsecond=0)
    except Exception:
        pass

    # Valores numéricos: planilhas podem representar hora como fração do dia.
    if isinstance(valor, (int, float, np.integer, np.floating)):
        try:
            numero = float(valor)
            if 0 <= numero < 1:
                total_segundos = round(numero * 24 * 60 * 60)
                total_segundos %= 24 * 60 * 60
                horas = total_segundos // 3600
                minutos = (total_segundos % 3600) // 60
                segundos = total_segundos % 60
                return dt_time(horas, minutos, segundos)
        except Exception:
            pass

    texto = str(valor).strip()
    if not texto:
        return None

    # Remove espaços e normaliza separadores comuns.
    texto = texto.replace("T", " ").strip()

    formatos = (
        "%H:%M:%S",
        "%H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
    )

    for formato in formatos:
        try:
            return datetime.strptime(texto, formato).time().replace(microsecond=0)
        except ValueError:
            continue

    # Último fallback: parsing controlado pelo pandas, mas sem jamais usar NOW().
    try:
        parsed = pd.to_datetime(texto, errors="coerce")
        if not pd.isna(parsed):
            return parsed.to_pydatetime().time().replace(microsecond=0)
    except Exception:
        pass

    return None

# ------------------------------------------------------------
# 6.3 FUNÇÃO AUXILIAR: MAPEAR COLUNAS DE ENTRADA
# ------------------------------------------------------------
def mapear_colunas_entrada(df):
    """
    Normaliza e mapeia as colunas usadas pela entrada em lote.
    Retorna (df_mapeado, colunas_encontradas, erros).
    """
    df = normalizar_colunas(df)
    colunas_esperadas = {
        'CODIGO': ['CODIGO', 'COD', 'MATRICULA', 'MATRIC', 'COD_ALUNO', 'CODALUNO'],
        'ESTUDANTE': ['ESTUDANTE', 'NOME', 'ALUNO', 'NOME_ALUNO', 'NOME DO ALUNO'],
        'HORA': ['HORA DE ENTRADA', 'HORA_ENTRADA', 'HORAENTRADA', 'HORA', 'HORARIO'],
        'DATA': ['DATA', 'DIA', 'DT', 'DAT']
    }

    colunas_disponiveis = df.columns.tolist()
    colunas_encontradas = {}

    for nome, sinonimos in colunas_esperadas.items():
        for col in colunas_disponiveis:
            if any(sin == col or sin in col for sin in sinonimos):
                colunas_encontradas[nome] = col
                break

    erros = []
    if 'CODIGO' not in colunas_encontradas:
        erros.append("CÓDIGO (nenhuma coluna contém: " + ", ".join(colunas_esperadas['CODIGO']) + ")")
    if 'HORA' not in colunas_encontradas:
        erros.append("HORA DE ENTRADA (nenhuma coluna contém: " + ", ".join(colunas_esperadas['HORA']) + ")")

    if erros:
        return df, colunas_encontradas, erros

    renomear = {
        colunas_encontradas['CODIGO']: 'CODIGO',
        colunas_encontradas['HORA']: 'HORA',
    }
    if 'DATA' in colunas_encontradas:
        renomear[colunas_encontradas['DATA']] = 'DATA'
    if 'ESTUDANTE' in colunas_encontradas:
        renomear[colunas_encontradas['ESTUDANTE']] = 'ESTUDANTE'

    # Evita problemas quando uma coluna já tem o nome final.
    df = df.rename(columns=renomear)
    return df, colunas_encontradas, erros

# ------------------------------------------------------------
# 6.3 FUNÇÃO PARA LER PLANILHA GOOGLE (SEM EXPANDER ANINHADO)
# ------------------------------------------------------------
def ler_planilha_google(url, data_base):
    """
    Lê uma planilha Google a partir de uma URL pública e filtra apenas registros da data_base.
    Reconhece as colunas: 'CÓDIGO', 'ESTUDANTE' (ignorada), 'HORA DE ENTRADA' e 'DATA'.
    Retorna: (DataFrame ou None, diagnostic_string)
    """
    diagnostic = ""
    try:
        # Converte a URL para o formato de download CSV
        if '/pub?' in url or '/pubhtml' in url:
            csv_url = url
        elif 'docs.google.com/spreadsheets' in url:
            import re
            match = re.search(r'/d/([a-zA-Z0-9-_]+)', url)
            if match:
                sheet_id = match.group(1)
                gid_match = re.search(r'gid=([0-9]+)', url)
                gid_param = f"&gid={gid_match.group(1)}" if gid_match else ""
                csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv{gid_param}"
            else:
                csv_url = url
        else:
            csv_url = url

        response = requests.get(csv_url, timeout=30)
        response.raise_for_status()

        from io import StringIO
        content = response.text

        total_linhas_fonte = 0

        # Tenta ler com separador vírgula, depois ponto e vírgula
        try:
            df = pd.read_csv(StringIO(content), sep=',', encoding='utf-8', dtype=str, keep_default_na=False)
        except:
            df = pd.read_csv(StringIO(content), sep=';', encoding='utf-8', dtype=str, keep_default_na=False)

        df, colunas_encontradas, erros_colunas = mapear_colunas_entrada(df)

        diagnostic = f"Colunas disponíveis: {', '.join(df.columns.tolist())}\n"
        diagnostic += f"Mapeamento: {colunas_encontradas}\n"

        if erros_colunas:
            diagnostic += "Erros: " + "; ".join(erros_colunas)
            return None, diagnostic

        # Processa a coluna de data (se existir)
        if 'DATA' in colunas_encontradas:
            df.rename(columns={colunas_encontradas['DATA']: 'DATA'}, inplace=True)
            # Tenta converter no formato DD/MM/YYYY
            try:
                df['DATA'] = pd.to_datetime(df['DATA'], format='%d/%m/%Y', errors='coerce').dt.date
            except:
                # Fallback para formato automático
                df['DATA'] = pd.to_datetime(df['DATA'], errors='coerce').dt.date
            df = df.dropna(subset=['DATA'])
            registros_data_atual = int((df['DATA'] == data_base).sum())
            registros_outras_datas = int(len(df) - registros_data_atual)
            df = df[df['DATA'] == data_base]
        else:
            # Se não tem coluna DATA, assume que todos são da data base
            df['DATA'] = data_base

        # Preserva explicitamente a HORA ORIGINAL da planilha.
        # IMPORTANTE: nunca substituir por obter_hora_atual() ou pela hora do upload.
        df['HORA'] = df['HORA'].apply(normalizar_hora_entrada)
        df = df.dropna(subset=['HORA'])

        # Remove linhas com código vazio ou nulo
        df = df[df['CODIGO'].notna()]
        df['CODIGO'] = (
    df['CODIGO']
    .astype(str)
    .str.strip()
    .str.upper()
    .str.replace(r'^(\d+)[\.,]0+$', r'\1', regex=True)
)

        # Se houver coluna ESTUDANTE, mantém para diagnóstico
        if 'ESTUDANTE' in colunas_encontradas:
            df.rename(columns={colunas_encontradas['ESTUDANTE']: 'ESTUDANTE'}, inplace=True)

        if 'registros_data_atual' not in locals():
            registros_data_atual = len(df)
            registros_outras_datas = max(total_linhas_fonte - registros_data_atual, 0)
        diagnostic += (
            f"Data protegida: {data_base.strftime('%d/%m/%Y')}\n"
            f"Linhas encontradas na planilha: {total_linhas_fonte}\n"
            f"Registros da data atual: {registros_data_atual}\n"
            f"Registros de outras datas ignorados: {registros_outras_datas}"
        )
        return df, diagnostic

    except requests.exceptions.RequestException as e:
        return None, f"Erro ao baixar a planilha: {e}"
    except Exception as e:
        return None, f"Erro ao processar a planilha: {e}"

# ------------------------------------------------------------
# 6.4 FUNÇÃO CENTRAL DE PROCESSAMENTO (DF)
# ------------------------------------------------------------
def processar_entrada_df(df, data_base, hora_limite, origem_entrada="PLANILHA"):
    """
    Processa os registros de entrada provenientes da planilha/CSV.

    Regras:
    - PLANILHA: a hora_entrada é exclusivamente a hora da planilha/CSV.
    - SISTEMA: a hora_entrada é exclusivamente a hora do servidor no momento do registro.
    - Um registro existente não é sobrescrito por uma fonte menos autoritativa.
    - Quando a origem é PLANILHA, a fonte pode corrigir hora/status existentes.
    - Quando a origem é SISTEMA, um registro existente é preservado.
    """
    origem_entrada = str(origem_entrada or "PLANILHA").strip().upper()
    if origem_entrada not in {"PLANILHA", "SISTEMA"}:
        origem_entrada = "PLANILHA"

    if df.empty:
        return 0, 0, 0, ["Nenhum registro encontrado para a data selecionada."]

    if "HORA" not in df.columns:
        return 0, 0, 0, [
            "A coluna HORA DE ENTRADA não foi encontrada nos dados."
        ]

    df = df.copy()
    df["HORA"] = df["HORA"].apply(normalizar_hora_entrada)

    linhas_invalidas_hora = df["HORA"].isna()
    erros = []

    if linhas_invalidas_hora.any():
        for idx in df.index[linhas_invalidas_hora]:
            erros.append(
                f"Linha {idx+1}: horário de entrada inválido ou ausente; "
                "registro ignorado."
            )
        df = df.loc[~linhas_invalidas_hora].copy()

    if df.empty:
        return (
            0,
            0,
            0,
            erros
            or [
                "Nenhum registro com horário de entrada válido foi encontrado."
            ],
        )

    conn = conectar_bd()
    if not conn:
        return (
            0,
            0,
            0,
            erros + ["Erro de conexão com o banco de dados."],
        )

    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                codigo,
                nome,
                email_responsavel
            FROM alunos_v2
            WHERE status = 'ATIVO'
            """
        )
        alunos = {
            row[0]: (row[1], row[2])
            for row in cur.fetchall()
        }
    finally:
        liberar_conn(conn)

    if not alunos:
        return (
            0,
            0,
            0,
            erros + ["Nenhum aluno ativo encontrado."],
        )

    # Busca registros de presença já existentes para as datas da fonte.
    datas_unicas = list(df["DATA"].dropna().unique())
    registros_existentes = {}

    if datas_unicas:
        conn2 = conectar_bd()
        if conn2:
            try:
                cur2 = conn2.cursor()
                placeholders = ",".join(["%s"] * len(datas_unicas))
                cur2.execute(
                    f"""
                    SELECT
                        codigo_aluno,
                        data,
                        hora_entrada,
                        status_entrada
                    FROM registros_v2
                    WHERE data IN ({placeholders})
                      AND tipo_registro = 'PRESENCA'
                    """,
                    datas_unicas,
                )
                for codigo_db, data_db, hora_db, status_db in cur2.fetchall():
                    registros_existentes[
                        (codigo_db, data_db)
                    ] = (
                        hora_db,
                        status_db,
                    )
            finally:
                liberar_conn(conn2)

    registros_novos = []
    registros_atualizar = []
    emails_para_disparar = []

    for idx, row in df.iterrows():
        codigo = str(row["CODIGO"]).strip().upper()
        data = row["DATA"]
        hora_real = row["HORA"]

        if codigo not in alunos:
            erros.append(
                f"Linha {idx+1}: Código '{codigo}' não encontrado ou inativo."
            )
            continue

        status = (
            "PRESENTE"
            if hora_real <= hora_limite
            else "ATRASO"
        )

        hora_real_str = hora_real.strftime("%H:%M:%S")
        chave = (codigo, data)

        if chave in registros_existentes:
            hora_existente, status_existente = registros_existentes[chave]

            hora_existente_str = (
                hora_existente.strftime("%H:%M:%S")
                if hora_existente is not None
                else None
            )

            # A PLANILHA é a fonte oficial para correção da hora/status.
            # A entrada via SISTEMA nunca sobrescreve um registro já existente.
            if origem_entrada == "PLANILHA":
                if (
                    hora_existente_str != hora_real_str
                    or status_existente != status
                ):
                    registros_atualizar.append(
                        (
                            codigo,
                            data,
                            hora_real_str,
                            status,
                        )
                    )

            # Não dispara e-mail novamente para um registro que já existia.
            continue

        registros_novos.append(
            (
                codigo,
                data,
                hora_real_str,
                status,
                "PRESENCA",
                origem_entrada,
            )
        )

        nome, email = alunos[codigo]

        if email:
            emails_para_disparar.append(
                (
                    nome,
                    email,
                    hora_real_str,
                    data.strftime("%Y-%m-%d"),
                    status,
                )
            )

    salvos = 0
    atualizados = 0

    conn3 = conectar_bd()

    if conn3:
        try:
            cur3 = conn3.cursor()

            if registros_novos:
                execute_values(
                    cur3,
                    """
                    INSERT INTO registros_v2 (
                        codigo_aluno,
                        data,
                        hora_entrada,
                        status_entrada,
                        tipo_registro,
                        origem_entrada
                    )
                    VALUES %s
                    ON CONFLICT DO NOTHING
                    """,
                    registros_novos,
                )
                salvos = cur3.rowcount

            if registros_atualizar:
                execute_values(
                    cur3,
                    """
                    UPDATE registros_v2 AS r
                    SET
                        hora_entrada = v.hora::time,
                        status_entrada = v.status,
                        origem_entrada = 'PLANILHA'
                    FROM (
                        VALUES %s
                    ) AS v(
                        codigo_aluno,
                        data,
                        hora,
                        status
                    )
                    WHERE r.codigo_aluno = v.codigo_aluno
                      AND r.data = v.data::date
                      AND r.tipo_registro = 'PRESENCA'
                    """,
                    registros_atualizar,
                )
                atualizados = cur3.rowcount

            conn3.commit()

        except Exception as e:
            try:
                conn3.rollback()
            except Exception:
                pass

            erros.append(
                f"Erro na atualização/inserção das entradas: {e}"
            )

        finally:
            liberar_conn(conn3)

    # Envia e-mails SOMENTE para registros novos.
    emails_enviados = []
    falhas_email = []
    smtp_indisponivel = False

    if emails_para_disparar:
        (
            emails_enviados,
            falhas_email,
            smtp_indisponivel,
        ) = enviar_emails_em_lote(
            emails_para_disparar
        )

    emails_disparados = len(emails_enviados)

    if smtp_indisponivel:
        erros.append(
            "O serviço de e-mail não está configurado ou "
            "não foi possível iniciar o envio."
        )

    for nome_falha, email_falha, motivo_falha in falhas_email:
        erros.append(
            f"E-mail NÃO enviado para {nome_falha} <{email_falha}>: "
            f"{motivo_falha}"
        )

    # Se houve correção de horários/status, informe de forma explícita.
    if atualizados:
        erros.append(
            f"ℹ️ {atualizados} registro(s) já existente(s) "
            "foram corrigidos com a hora/status exatos da planilha."
        )

    return (
        len(df),
        salvos + atualizados,
        emails_disparados,
        erros,
    )

# ------------------------------------------------------------
# 6.5 FUNÇÃO DE IMPORTAÇÃO DE CSV (REUTILIZA A PROCESSADORA)
# ------------------------------------------------------------
def importar_csv_entrada(file, data_base, hora_limite):
    """Importa CSV de entrada usando o mesmo mapeamento robusto da planilha Google."""
    conteudo = file.read()
    try:
        conteudo_str = conteudo.decode("utf-8-sig")
    except Exception:
        conteudo_str = conteudo.decode("latin-1")

    try:
        df = pd.read_csv(
            io.StringIO(conteudo_str),
            sep=";",
            dtype=str,
            keep_default_na=False,
        )
        if len(df.columns) == 1:
            df = pd.read_csv(
                io.StringIO(conteudo_str),
                sep=",",
                dtype=str,
                keep_default_na=False,
            )
    except Exception:
        df = pd.read_csv(
            io.StringIO(conteudo_str),
            sep=",",
            dtype=str,
            keep_default_na=False,
        )

    df, _, erros_colunas = mapear_colunas_entrada(df)
    if erros_colunas:
        return (
            0,
            0,
            0,
            ["Erro nas colunas do CSV: " + "; ".join(erros_colunas)],
        )

    if "DATA" not in df.columns:
        df["DATA"] = data_base
    else:
        df["DATA"] = pd.to_datetime(
            df["DATA"],
            errors="coerce",
            dayfirst=True,
        ).dt.date
        df = df[df["DATA"] == data_base]

    df["HORA"] = df["HORA"].apply(normalizar_hora_entrada)
    return processar_entrada_df(df, data_base, hora_limite)


def registrar_saida(cod, motivo, pais, data, h_saida, h_limite_saida):
    """
    Registra a saída, confirma a persistência no banco e só então
    envia o e-mail EXATO correspondente à saída.
    """
    codigo = str(cod or "").strip().upper()
    if not codigo:
        return False

    conn = conectar_bd()
    if not conn:
        return False

    nome_aluno = None
    email_responsavel = None
    evento_email = None
    hora_saida_str = None

    try:
        cur = conn.cursor()

        cur.execute(
            """
            SELECT nome, email_responsavel
            FROM alunos_v2
            WHERE UPPER(TRIM(codigo)) = %s
            LIMIT 1
            """,
            (codigo,),
        )
        res = cur.fetchone()
        if not res:
            conn.rollback()
            return False

        nome_aluno, email_responsavel = res

        try:
            h_s_obj = (
                h_saida
                if hasattr(h_saida, "hour")
                else datetime.strptime(str(h_saida), "%H:%M:%S").time()
            )
        except Exception:
            h_s_obj = datetime.strptime(str(h_saida)[:8], "%H:%M:%S").time()

        hora_saida_str = h_s_obj.strftime("%H:%M:%S")
        evento_email = (
            "SAÍDA ANTECIPADA"
            if h_s_obj < h_limite_saida
            else "SAÍDA REGULAR"
        )

        cur.execute(
            """
            UPDATE registros_v2
               SET hora_saida = %s,
                   motivo_saida = %s,
                   pais_informados = %s
             WHERE codigo_aluno = %s
               AND data = %s
               AND tipo_registro = 'PRESENCA'
            RETURNING id, hora_saida
            """,
            (hora_saida_str, motivo, pais, codigo, data),
        )
        alterado = cur.fetchone()
        if not alterado:
            conn.rollback()
            return False

        conn.commit()

        # Confirmação pós-commit: a saída realmente ficou persistida.
        cur.execute(
            """
            SELECT id, hora_saida
            FROM registros_v2
            WHERE codigo_aluno = %s
              AND data = %s
              AND tipo_registro = 'PRESENCA'
            LIMIT 1
            """,
            (codigo, data),
        )
        confirmado = cur.fetchone()
        if not confirmado or confirmado[1] is None:
            return False

    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        print(f"Erro ao registrar saída: {e}")
        return False
    finally:
        liberar_conn(conn)

    # O banco já foi confirmado. Agora envia o evento correto e imutável.
    # A mensagem é enviada em segundo plano para não tornar o registro de
    # saída dependente da latência do SMTP. A função ainda valida recusas
    # retornadas pelo servidor antes de considerar o envio bem-sucedido.
    if email_responsavel:
        sucesso_email, erro_email, _ = disparar_email_background(
            email_responsavel,
            nome_aluno,
            evento_email,
            hora_saida_str,
            data,
        )
        if not sucesso_email:
            print(
                f"Falha ao enviar {evento_email} para {email_responsavel}: {erro_email}"
            )

    contar_presencas_data.clear()
    carregar_resumo_dashboard.clear()
    carregar_faltas.clear()
    return nome_aluno


def importar_csv_desempenho(file, ano, periodo, area, turma):
    conteudo_bytes = file.read()
    try: 
        conteudo_str = conteudo_bytes.decode('utf-8-sig')
    except: 
        conteudo_str = conteudo_bytes.decode('latin-1')
    temp_df = pd.read_csv(io.StringIO(conteudo_str), sep=';')
    temp_df.columns = [str(c).strip() for c in temp_df.columns]
    col_qs = [c for c in temp_df.columns if re.search(r'^Q\s*\d+\s*Options', c, re.IGNORECASE)]
    idx_not = next((i for i, c in enumerate(temp_df.columns) if 'Not attempted' in c), -1)
    idx_f = temp_df.columns.get_loc(col_qs[0])
    if idx_not != -1:
        discs = [str(c).strip().upper() for c in temp_df.columns[idx_not+1:idx_f] if 'AV' not in str(c).upper()]
    else:
        discs = [area.upper()]
    q_p_d = len(col_qs) // len(discs)
    dados_l = []
    nomes = temp_df.get('Nome', pd.Series(dtype=str)).astype(str).str.strip().tolist()
    col_keys = [cq.replace('Options', 'Key') for cq in col_qs]
    for ck in col_keys:
        if ck not in temp_df.columns: 
            temp_df[ck] = ''
    options_matrix = temp_df[col_qs].fillna('').astype(str).values
    keys_matrix = temp_df[col_keys].fillna('').astype(str).values

    for r_idx, n in enumerate(nomes):
        if not n or n.lower() == 'nan': 
            continue
        for i in range(len(col_qs)):
            d_i = min(i // q_p_d, len(discs)-1)
            rb = options_matrix[r_idx, i].strip()
            g = keys_matrix[r_idx, i].strip().upper()
            if not rb:
                r = 'BRANCO'
            elif len(rb) == 1:
                r = rb.upper()
            else:
                r = 'DUPLA'
            if r == g and r != 'BRANCO':
                acerto = 1
            else:
                acerto = 0
            dados_l.append((str(ano), periodo, area, turma, n, discs[d_i], i+1, r, g, acerto))
    conn = conectar_bd()
    if not conn: 
        return False, "Erro de conexão ao banco de dados."
    try:
        cur = conn.cursor()
        execute_values(cur, "INSERT INTO avaliacoes_avs (ano, periodo, area, turma, nome, disciplina, questao, resposta, gabarito, acerto) VALUES %s ON CONFLICT (ano, periodo, area, turma, nome, disciplina, questao) DO UPDATE SET resposta=EXCLUDED.resposta, acerto=EXCLUDED.acerto", dados_l)
        conn.commit()
        obter_dados_acad_filtrados.clear()
        return True, f"{len(dados_l)} registros salvos."
    except Exception as e: 
        return False, str(e)
    finally: 
        liberar_conn(conn)



@st.cache_data(ttl=60)
def carregar_historico_frequencia_aluno(codigo_aluno):
    """Retorna o histórico completo de frequência do estudante até hoje."""
    if not codigo_aluno:
        return pd.DataFrame()
    conn = conectar_bd()
    if not conn:
        return pd.DataFrame()
    try:
        query = """
            WITH dias AS (
                SELECT data
                FROM calendario_letivo
                WHERE dia_letivo = TRUE
                  AND data <= CURRENT_DATE
                UNION
                SELECT data
                FROM registros_v2
                WHERE codigo_aluno = %s
                  AND data <= CURRENT_DATE
            )
            SELECT
                d.data,
                CASE
                    WHEN r.tipo_registro = 'PRESENCA'
                         AND r.status_entrada = 'ATRASO' THEN 'ATRASO'
                    WHEN r.tipo_registro = 'PRESENCA' THEN 'PRESENTE'
                    WHEN r.tipo_registro = 'FALTA'
                         AND NULLIF(TRIM(r.motivo_saida), '') IS NOT NULL
                        THEN 'FALTA JUSTIFICADA'
                    WHEN r.tipo_registro = 'FALTA' THEN 'FALTA'
                    ELSE 'AUSENTE SEM REGISTRO'
                END AS situacao,
                r.hora_entrada,
                r.hora_saida,
                r.motivo_saida
            FROM dias d
            LEFT JOIN registros_v2 r
              ON r.codigo_aluno = %s
             AND r.data = d.data
            ORDER BY d.data DESC
        """
        return pd.read_sql_query(
            query, conn, params=[codigo_aluno, codigo_aluno]
        )
    except Exception:
        return pd.DataFrame()
    finally:
        liberar_conn(conn)


def obter_codigo_aluno_df(nome, turma, df_alunos):
    """Localiza o código do estudante sem nova consulta ao banco."""
    if df_alunos is None or df_alunos.empty:
        return None
    try:
        filtro = (
            df_alunos['nome'].astype(str).str.upper().eq(str(nome).upper())
            & df_alunos['turma'].astype(str).str.upper().eq(str(turma).upper())
        )
        linhas = df_alunos.loc[filtro]
        if not linhas.empty:
            return str(linhas.iloc[0]['codigo']).strip()
    except Exception:
        pass
    return None


def gerar_pdf_painel_informativo(data_info, turma_info, df_aus, df_tarde, df_lib):
    """Gera PDF com exatamente os três grupos exibidos no Painel Informativo."""
    if not FPDF:
        return None

    def txt(valor):
        if valor is None or (isinstance(valor, float) and pd.isna(valor)):
            return ''
        return str(valor)

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Cabeçalho
    pdf.set_fill_color(10, 31, 53)
    pdf.rect(0, 0, 210, 38, 'F')
    pdf.set_text_color(255, 255, 255)
    pdf.set_font('Arial', 'B', 18)
    pdf.cell(0, 12, 'PAINEL INFORMATIVO', 0, 1, 'C')
    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 7, 'Relatorio diario de frequencia dos estudantes', 0, 1, 'C')
    pdf.ln(14)
    pdf.set_text_color(15, 23, 42)

    data_fmt = data_info.strftime('%d/%m/%Y')
    pdf.set_font('Arial', 'B', 11)
    pdf.cell(95, 8, f'Data: {data_fmt}', 0, 0)
    pdf.cell(95, 8, f'Turma: {txt(turma_info)}', 0, 1)
    pdf.ln(4)

    # Resumo
    resumo = [
        ('AUSENTES', len(df_aus), (239, 68, 68)),
        ('PRESENTES A TARDE', len(df_tarde), (14, 165, 233)),
        ('LIBERADOS', len(df_lib), (139, 92, 246)),
    ]
    largura = 60
    for i, (rotulo, qtd, cor) in enumerate(resumo):
        x = 10 + i * 65
        pdf.set_fill_color(*cor)
        pdf.rect(x, pdf.get_y(), largura, 22, 'F')
        pdf.set_text_color(255, 255, 255)
        pdf.set_font('Arial', 'B', 8)
        pdf.set_xy(x, pdf.get_y() + 3)
        pdf.cell(largura, 6, rotulo, 0, 1, 'C')
        pdf.set_font('Arial', 'B', 15)
        pdf.cell(largura, 8, str(qtd), 0, 0, 'C')
    pdf.ln(28)
    pdf.set_text_color(15, 23, 42)

    def secao(titulo, cor, registros, tipo):
        pdf.set_fill_color(*cor)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(0, 9, titulo, 0, 1, 'L', fill=True)
        pdf.set_text_color(15, 23, 42)
        pdf.set_font('Arial', 'B', 9)
        if tipo == 'ausentes':
            pdf.cell(55, 7, 'Estudante', 1)
            pdf.cell(25, 7, 'Codigo', 1)
            pdf.cell(28, 7, 'Turma', 1)
            pdf.cell(82, 7, 'Situacao / Motivo', 1)
            pdf.ln()
        elif tipo == 'tarde':
            pdf.cell(65, 7, 'Estudante', 1)
            pdf.cell(25, 7, 'Codigo', 1)
            pdf.cell(35, 7, 'Turma', 1)
            pdf.cell(65, 7, 'Entrada', 1)
            pdf.ln()
        else:
            pdf.cell(55, 7, 'Estudante', 1)
            pdf.cell(25, 7, 'Codigo', 1)
            pdf.cell(28, 7, 'Turma', 1)
            pdf.cell(25, 7, 'Saida', 1)
            pdf.cell(57, 7, 'Motivo', 1)
            pdf.ln()

        pdf.set_font('Arial', '', 8)
        if registros is None or registros.empty:
            pdf.cell(0, 8, 'Nenhum estudante nesta condicao.', 1, 1)
            pdf.ln(5)
            return

        for row in registros.to_dict('records'):
            if pdf.get_y() > 265:
                pdf.add_page()
                pdf.set_font('Arial', 'B', 12)
                pdf.cell(0, 9, titulo + ' (continua)', 0, 1, 'L', fill=True)
                pdf.set_font('Arial', '', 8)
            nome = txt(row.get('nome'))
            codigo = txt(row.get('codigo'))
            turma = txt(row.get('turma'))
            if tipo == 'ausentes':
                motivo = txt(row.get('motivo_falta')).strip()
                motivo_susp = txt(row.get('motivo_suspensao')).strip()
                if motivo_susp:
                    inicio_s = txt(row.get('suspensao_inicio'))[:10]
                    fim_s = txt(row.get('suspensao_fim'))[:10]
                    situacao = f'SUSPENSAO DISCIPLINAR | {inicio_s} a {fim_s} | {motivo_susp}'
                else:
                    situacao = 'FALTA JUSTIFICADA - ' + motivo if motivo else 'FALTA NAO JUSTIFICADA'
                pdf.cell(55, 7, nome[:35], 1)
                pdf.cell(25, 7, codigo[:15], 1)
                pdf.cell(28, 7, turma[:18], 1)
                pdf.cell(82, 7, situacao[:58], 1)
            elif tipo == 'tarde':
                hora = txt(row.get('hora_entrada'))[:8]
                pdf.cell(65, 7, nome[:40], 1)
                pdf.cell(25, 7, codigo[:15], 1)
                pdf.cell(35, 7, turma[:22], 1)
                pdf.cell(65, 7, hora, 1)
            else:
                hora = txt(row.get('hora_saida'))[:8]
                motivo = txt(row.get('motivo_saida')).strip()
                pdf.cell(55, 7, nome[:35], 1)
                pdf.cell(25, 7, codigo[:15], 1)
                pdf.cell(28, 7, turma[:18], 1)
                pdf.cell(25, 7, hora, 1)
                pdf.cell(57, 7, motivo[:40], 1)
            pdf.ln()
        pdf.ln(7)

    secao('AUSENTES', (239, 68, 68), df_aus, 'ausentes')
    secao('PRESENTES A TARDE (ENTRADA A PARTIR DE 12:00)', (14, 165, 233), df_tarde, 'tarde')
    secao('LIBERADOS', (139, 92, 246), df_lib, 'liberados')

    pdf.set_font('Arial', 'I', 8)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(0, 7, 'Documento gerado pelo sistema de gestao escolar.', 0, 1, 'C')

    out = pdf.output(dest='S')
    if isinstance(out, str):
        return out.encode('latin-1', errors='replace')
    return bytes(out)

@st.cache_data(ttl=60)
def carregar_suspensoes_aluno(codigo_aluno):
    if not codigo_aluno:
        return pd.DataFrame()
    conn = conectar_bd()
    if not conn:
        return pd.DataFrame()
    try:
        query = """
            SELECT data_inicio, data_fim, motivo, criado_em
            FROM suspensoes_v1
            WHERE codigo_aluno = %s
            ORDER BY data_inicio DESC, id DESC
        """
        return pd.read_sql_query(query, conn, params=[codigo_aluno])
    except Exception:
        return pd.DataFrame()
    finally:
        liberar_conn(conn)


def registrar_suspensao(codigo_aluno, data_inicio, data_fim, motivo):
    codigo = str(codigo_aluno or "").strip().upper()
    motivo = str(motivo or "").strip()
    if not codigo or not motivo:
        return False, "Dados incompletos para registrar a suspensão."
    if data_fim < data_inicio:
        return False, "A data final não pode ser anterior à data inicial."

    conn = conectar_bd()
    if not conn:
        return False, "Não foi possível conectar ao banco de dados."

    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT nome, turma, email_responsavel FROM alunos_v2 WHERE codigo=%s AND status='ATIVO' LIMIT 1",
            (codigo,),
        )
        aluno = cur.fetchone()
        if not aluno:
            conn.rollback()
            return False, "Estudante não encontrado ou inativo."

        nome, turma, email = aluno
        cur.execute(
            """
            INSERT INTO suspensoes_v1 (codigo_aluno, data_inicio, data_fim, motivo)
            VALUES (%s, %s, %s, %s)
            RETURNING id
            """,
            (codigo, data_inicio, data_fim, motivo),
        )
        susp_id = cur.fetchone()[0]
        conn.commit()
        carregar_suspensoes_aluno.clear()
        return True, {
            "id": susp_id,
            "codigo": codigo,
            "nome": nome,
            "turma": turma,
            "email": email,
            "data_inicio": data_inicio,
            "data_fim": data_fim,
            "motivo": motivo,
        }
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        return False, f"Erro ao registrar suspensão: {e}"
    finally:
        liberar_conn(conn)


def excluir_suspensao(suspensao_id):
    conn = conectar_bd()
    if not conn:
        return False, "Sem conexão com o banco de dados."
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM suspensoes_v1 WHERE id=%s", (suspensao_id,))
        apagados = cur.rowcount
        conn.commit()
        carregar_suspensoes_aluno.clear()
        return (True, "Suspensão excluída com sucesso." if apagados else "Registro não encontrado.")
    except Exception as e:
        conn.rollback()
        return False, f"Erro ao excluir suspensão: {e}"
    finally:
        liberar_conn(conn)


def buscar_suspensoes_na_data(data_str, turma="Todas"):
    conn = conectar_bd()
    if not conn:
        return pd.DataFrame()
    try:
        params = [data_str, data_str]
        query = """
            SELECT s.id, a.codigo, a.nome, a.turma, s.data_inicio, s.data_fim, s.motivo, a.telefone_responsavel, a.email_responsavel
            FROM suspensoes_v1 s
            JOIN alunos_v2 a ON a.codigo = s.codigo_aluno
            WHERE s.data_inicio <= %s AND s.data_fim >= %s AND a.status='ATIVO'
        """
        if turma != "Todas":
            query += " AND a.turma=%s"
            params.append(turma)
        query += " ORDER BY a.turma, a.nome"
        return pd.read_sql_query(query, conn, params=params)
    except Exception:
        return pd.DataFrame()
    finally:
        liberar_conn(conn)


def gerar_pdf_boletim(aluno, turma, nota_g, df_b, df_historico_aluno=None, df_frequencia_aluno=None, df_suspensoes_aluno=None):
    if not FPDF: 
        return None
    pdf = FPDF()
    pdf.add_page()
    pdf.set_fill_color(10, 31, 53)
    pdf.rect(0, 0, 210, 35, 'F')
    pdf.set_font("Arial", "B", 18)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 15, "BOLETIM DE DESEMPENHO", 0, 1, "C")
    pdf.ln(20)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, f"ESTUDANTE: {aluno} ({turma})", 0, 1)
    pdf.cell(0, 10, f"MÉDIA (Filtro): {nota_g:.2f}", 0, 1)
    pdf.set_font("Arial", "B", 8)
    pdf.cell(0, 6, "LEGENDA: VERDE = ACERTO | VERMELHO = ERRO | LARANJA = BRANCO | ROXO = DUPLA", 0, 1)
    pdf.ln(2)
    for p in sorted(df_b['periodo'].unique()):
        pdf.set_fill_color(230, 230, 230)
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 10, f"  {p}", 0, 1, fill=True)
        for d in sorted(df_b[df_b['periodo']==p]['disciplina'].unique()):
            df_d = df_b[(df_b['periodo']==p) & (df_b['disciplina']==d)]
            pdf.set_font("Arial", "B", 11)
            pdf.cell(0, 8, f"{d} - Nota: {(df_d['acerto'].mean()*10):.2f}", 0, 1)
            x = 10
            y = pdf.get_y()
            col = 0
            for q in df_d.sort_values('questao').to_dict('records'):
                if y > 265: 
                    pdf.add_page()
                    y = 20
                if q['acerto'] == 1:
                    c = (16, 185, 129)
                elif q['resposta'] == 'BRANCO':
                    c = (245, 158, 11)
                elif q['resposta'] == 'DUPLA':
                    c = (139, 92, 246)
                else:
                    c = (239, 68, 68)
                pdf.set_fill_color(*c)
                pdf.rect(x + (col * 22), y, 20, 12, 'F')
                pdf.set_text_color(255, 255, 255)
                pdf.set_font("Arial", "B", 8)
                pdf.text(x + (col * 22) + 2, y + 5, f"Q{q['questao']}")
                pdf.text(x + (col * 22) + 2, y + 10, f"R:{q['resposta']}")
                col += 1
                if col > 7: 
                    col = 0
                    y += 15
            if col > 0:
                y = y + 15 
            else:
                y = y
            pdf.set_y(y + 5)
            pdf.set_text_color(0, 0, 0)
    # ------------------------------------------------------------
    # FREQUENCIA: faltas, justificativas e atrasos
    # ------------------------------------------------------------
    if df_frequencia_aluno is not None and not df_frequencia_aluno.empty:
        df_freq = df_frequencia_aluno.copy()
        total_dias = len(df_freq)
        presentes_freq = int(df_freq['situacao'].isin(['PRESENTE', 'ATRASO']).sum())
        atrasos_freq = int((df_freq['situacao'] == 'ATRASO').sum())
        faltas_just = int((df_freq['situacao'] == 'FALTA JUSTIFICADA').sum())
        faltas_nao = int(df_freq['situacao'].isin(['FALTA', 'AUSENTE SEM REGISTRO']).sum())
        total_faltas = faltas_just + faltas_nao
        frequencia_pct = (presentes_freq / total_dias * 100) if total_dias else 0

        pdf.add_page()
        pdf.set_fill_color(10, 31, 53)
        pdf.rect(0, 0, 210, 30, 'F')
        pdf.set_text_color(255, 255, 255)
        pdf.set_font('Arial', 'B', 16)
        pdf.cell(0, 12, 'HISTORICO DE FREQUENCIA', 0, 1, 'C')
        pdf.ln(12)
        pdf.set_text_color(15, 23, 42)

        indicadores = [
            ('Dias letivos', total_dias),
            ('Presencas', presentes_freq),
            ('Atrasos', atrasos_freq),
            ('Faltas', total_faltas),
            ('Justificadas', faltas_just),
            ('Nao justificadas', faltas_nao),
        ]
        x_positions = [10, 43, 76, 109, 142, 175]
        for (rotulo, valor), x in zip(indicadores, x_positions):
            pdf.set_fill_color(241, 245, 249)
            pdf.rect(x, pdf.get_y(), 28, 23, 'F')
            pdf.set_xy(x, pdf.get_y() + 3)
            pdf.set_font('Arial', 'B', 7)
            pdf.cell(28, 6, rotulo, 0, 1, 'C')
            pdf.set_font('Arial', 'B', 12)
            pdf.cell(28, 8, str(valor), 0, 0, 'C')
        pdf.ln(28)
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(0, 7, f'Frequencia registrada: {frequencia_pct:.1f}%', 0, 1)
        pdf.ln(3)

        # No histórico detalhado, mostrar apenas ocorrências relevantes:
        # faltas, faltas justificadas e atrasos. Presenças normais são
        # contabilizadas nos indicadores, mas não ocupam espaço na tabela.
        # O histórico completo também pode representar uma ausência sem uma
        # linha explícita de FALTA em registros_v2. Nesses casos, a consulta
        # retorna AUSENTE SEM REGISTRO; para o boletim, isso deve aparecer
        # como FALTA NAO JUSTIFICADA, pois também compõe as faltas.
        df_ocorrencias = df_freq[df_freq['situacao'].isin([
            'FALTA', 'FALTA JUSTIFICADA', 'AUSENTE SEM REGISTRO', 'ATRASO'
        ])].copy()

        pdf.set_font('Arial', 'B', 9)
        pdf.cell(28, 7, 'Data', 1)
        pdf.cell(50, 7, 'Situacao', 1)
        pdf.cell(35, 7, 'Hora de Entrada', 1)
        pdf.cell(77, 7, 'Motivo / Justificativa', 1)
        pdf.ln()
        pdf.set_font('Arial', '', 8)

        if df_ocorrencias.empty:
            pdf.cell(190, 8, 'Nenhuma falta ou atraso registrado no periodo.', 1, 1, 'C')

        for row in df_ocorrencias.to_dict('records'):
            if pdf.get_y() > 268:
                pdf.add_page()
                pdf.set_font('Arial', 'B', 9)
                pdf.cell(28, 7, 'Data', 1)
                pdf.cell(50, 7, 'Situacao', 1)
                pdf.cell(35, 7, 'Hora de Entrada', 1)
                pdf.cell(77, 7, 'Motivo / Justificativa', 1)
                pdf.ln()
                pdf.set_font('Arial', '', 8)

            data_val = row.get('data')
            try:
                data_txt = pd.to_datetime(data_val).strftime('%d/%m/%Y')
            except Exception:
                data_txt = str(data_val)
            situacao_raw = str(row.get('situacao') or '')
            entrada = str(row.get('hora_entrada') or '')[:8]
            motivo = str(row.get('motivo_saida') or '')

            # Normaliza a ausência sem registro para a mesma categoria
            # apresentada nos indicadores do boletim: falta não justificada.
            if situacao_raw == 'AUSENTE SEM REGISTRO':
                situacao = 'FALTA NAO JUSTIFICADA'
                motivo = ''
            else:
                situacao = situacao_raw

            # Para atraso, mostra a hora real de entrada. Para faltas,
            # o campo de horário permanece vazio e o motivo aparece ao lado.
            pdf.cell(28, 7, data_txt, 1)
            pdf.cell(50, 7, situacao[:34], 1)
            pdf.cell(35, 7, entrada if situacao == 'ATRASO' else '', 1)
            pdf.cell(77, 7, motivo[:52], 1)
            pdf.ln()

    # ------------------------------------------------------------
    # SUSPENSÕES DISCIPLINARES
    # ------------------------------------------------------------
    if df_suspensoes_aluno is not None and not df_suspensoes_aluno.empty:
        pdf.add_page()
        pdf.set_fill_color(124, 45, 18)
        pdf.rect(0, 0, 210, 30, 'F')
        pdf.set_text_color(255, 255, 255)
        pdf.set_font('Arial', 'B', 16)
        pdf.cell(0, 12, 'HISTORICO DE SUSPENSOES DISCIPLINARES', 0, 1, 'C')
        pdf.ln(12)
        pdf.set_text_color(15, 23, 42)
        pdf.set_font('Arial', 'B', 9)
        pdf.cell(38, 7, 'Inicio', 1)
        pdf.cell(38, 7, 'Fim', 1)
        pdf.cell(114, 7, 'Motivo', 1)
        pdf.ln()
        pdf.set_font('Arial', '', 8)
        for row in df_suspensoes_aluno.to_dict('records'):
            if pdf.get_y() > 268:
                pdf.add_page()
                pdf.set_font('Arial', 'B', 9)
                pdf.cell(38, 7, 'Inicio', 1)
                pdf.cell(38, 7, 'Fim', 1)
                pdf.cell(114, 7, 'Motivo', 1)
                pdf.ln()
                pdf.set_font('Arial', '', 8)
            try:
                di = pd.to_datetime(row.get('data_inicio')).strftime('%d/%m/%Y')
            except Exception:
                di = str(row.get('data_inicio') or '')
            try:
                dfim = pd.to_datetime(row.get('data_fim')).strftime('%d/%m/%Y')
            except Exception:
                dfim = str(row.get('data_fim') or '')
            pdf.cell(38, 7, di, 1)
            pdf.cell(38, 7, dfim, 1)
            pdf.cell(114, 7, str(row.get('motivo') or '')[:78], 1)
            pdf.ln()

    if df_historico_aluno is not None and not df_historico_aluno.empty and MATPLOTLIB_AVAILABLE:
        progresso = df_historico_aluno.groupby(['periodo', 'disciplina']).agg(Acertos=('acerto', 'sum'), Total=('questao', 'count')).reset_index()
        progresso['Nota'] = (progresso['Acertos'] / progresso['Total']) * 10
        progresso_pivot = progresso.pivot(index='periodo', columns='disciplina', values='Nota')
        fig, ax = plt.subplots(figsize=(10, 6))
        for col_name in progresso_pivot.columns:
            abreviacao = DICIONARIO_ABREVIACAO.get(col_name, col_name[:4].upper())
            cor = DICIONARIO_CORES.get(abreviacao, DICIONARIO_CORES.get(col_name, "#000000"))
            ax.plot(progresso_pivot.index, progresso_pivot[col_name], marker='o', linewidth=5, markersize=12, label=col_name, color=cor)
            for x_val, y_val in zip(progresso_pivot.index, progresso_pivot[col_name]):
                if pd.notna(y_val): 
                    ax.text(x_val, y_val + 0.3, abreviacao, color=cor, fontsize=10, fontweight='bold', ha='center', va='bottom')
        ax.set_title("Evolucao Geral ao Longo do Ano", fontweight='bold', fontsize=18)
        ax.set_ylabel("Nota", fontweight='bold', fontsize=14)
        ax.set_xlabel("Periodo", fontweight='bold', fontsize=14)
        ax.set_ylim(0, 11) 
        ax.grid(True, linestyle='--', alpha=0.7)
        ax.legend(loc='center left', bbox_to_anchor=(1, 0.5), fontsize=12)
        plt.tight_layout()
        with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp: 
            plt.savefig(tmp.name, format='png', dpi=300, bbox_inches='tight')
            tmp_img_name = tmp.name
        plt.close(fig)
        pdf.add_page()
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, "EVOLUCAO AO LONGO DO ANO (HISTORICO COMPLETO)", 0, 1, "C")
        pdf.ln(5)
        pdf.image(tmp_img_name, x=10, w=190)
        try: 
            os.remove(tmp_img_name)
        except: 
            pass
    out = pdf.output(dest='S')
    if isinstance(out, str):
        return out.encode('latin-1')
    return bytes(out)

def gerar_pdf_relatorio_critico(df_critico):
    if not FPDF: 
        return None
    pdf = FPDF()
    pdf.add_page()
    pdf.set_fill_color(10, 31, 53)
    pdf.rect(0, 0, 210, 35, 'F')
    pdf.set_font("Arial", "B", 16)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 15, "QUESTOES CRITICAS (TOP 3 ERROS)", 0, 1, "C")
    pdf.ln(20)
    pdf.set_text_color(0, 0, 0)
    for t in sorted(df_critico['turma'].unique()):
        pdf.set_fill_color(230, 230, 230)
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, f" Turma: {t}", 0, 1, fill=True)
        df_t = df_critico[df_critico['turma'] == t]
        for p in sorted(df_t['periodo'].unique()):
            pdf.set_font("Arial", "B", 12)
            pdf.cell(0, 8, f"   Periodo: {p}", 0, 1)
            df_p = df_t[df_t['periodo'] == p]
            for d in sorted(df_p['disciplina'].unique()):
                pdf.set_font("Arial", "B", 11)
                pdf.cell(0, 6, f"      Disciplinas: {d}", 0, 1)
                df_d = df_p[df_p['disciplina'] == d]
                pdf.set_font("Arial", "", 10)
                for _, r in df_d.iterrows():
                    if pdf.get_y() > 270: 
                        pdf.add_page()
                    pdf.cell(15)
                    pdf.cell(0, 5, f"- Questao {r['questao']}: {r['Taxa de Erro (%)']:.1f}% de erro", 0, 1)
                pdf.ln(2)
        pdf.ln(5)
    out = pdf.output(dest='S')
    if isinstance(out, str):
        return out.encode('latin-1')
    return bytes(out)

def gerar_camera(label, btn_label, cam_id):
    components.html(f"""
    <div style="text-align:center; max-width:450px; margin: 0 auto; padding:15px; border-radius:15px; background:white; border: 2px solid #e2e8f0; box-shadow: 0 4px 10px rgba(0,0,0,0.05);">
        <div style="display:flex; gap:10px; margin-bottom:15px;">
            <button id="start-{cam_id}" style="flex:1; padding:12px; background:#10b981; color:white; border:none; border-radius:8px; font-weight:900; font-size:1rem; cursor:pointer;">🟢 LIGAR CÂMARA (Contínuo)</button>
            <button id="stop-{cam_id}" style="flex:1; padding:12px; background:#ef4444; color:white; border:none; border-radius:8px; font-weight:900; font-size:1rem; cursor:pointer;">🔴 DESLIGAR</button>
        </div>
        <div id="reader-{cam_id}" style="width:100%; display:none; border-radius:10px; overflow:hidden; border: 3px solid #0a1f35; background: #000;"></div>
    </div>
    <script src="https://unpkg.com/html5-qrcode"></script>
    <script>
        let scanner_{cam_id};
        document.getElementById("start-{cam_id}").onclick = () => {{
            const container = document.getElementById("reader-{cam_id}");
            container.style.display = "block";
            if(!scanner_{cam_id}) {{
                scanner_{cam_id} = new Html5Qrcode("reader-{cam_id}");
            }}
            const configuracao = {{ fps: 20, qrbox: {{ width: 260, height: 260 }} }};
            const aoLerCodigo = (txt) => {{
                const input = window.parent.document.querySelectorAll('input[aria-label*="{label}"]')[0];
                if(input) {{ 
                    let nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
                    nativeInputValueSetter.call(input, txt);
                    input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    setTimeout(() => {{ 
                        window.parent.document.querySelectorAll('button').forEach(b => {{ 
                            if(b.innerText.includes("{btn_label}")) {{
                                b.click();
                            }}
                        }}); 
                    }}, 100);
                }}
            }};
            scanner_{cam_id}.start({{ facingMode: "environment" }}, configuracao, aoLerCodigo)
            .catch(erroTraseira => {{
                scanner_{cam_id}.start({{ facingMode: "user" }}, configuracao, aoLerCodigo)
                .catch(erroFrontal => {{
                    alert("⚠️ Erro ao acessar a câmera: Verifique permissões.");
                    container.style.display = "none";
                }});
            }});
        }};
        document.getElementById("stop-{cam_id}").onclick = () => {{
            if(scanner_{cam_id}) {{ 
                scanner_{cam_id}.stop().then(() => {{ 
                    document.getElementById("reader-{cam_id}").style.display = "none"; 
                }}) 
            }}
        }};
    </script>
    """, height=450)

# ------------------------------------------------------------
# 7. MÓDULO PÚBLICO: PESQUISA DE SATISFAÇÃO
# ------------------------------------------------------------
if st.query_params.get("modo") == "pesquisa":
    renderizar_logo_central()
    if st.session_state.pesquisa_enviada:
        st.markdown("<div style='text-align: center; padding: 40px 10px;'><h1 style='font-size: 5rem; margin-bottom: 0;'>🎉</h1><h2 style='color: #10b981; font-weight: 900;'>Avaliação Recebida!</h2><p style='font-size: 1.4rem; color: #64748b; margin-top: 15px;'>Muito obrigado por contribuir com a melhoria da nossa escola.<br>Sua opinião faz toda a diferença!</p></div>", unsafe_allow_html=True)
        if st.button("Enviar nova avaliação", use_container_width=True):
            st.session_state.pesquisa_enviada = False
            st.rerun()
        st.stop()
    st.markdown("<h2 style='color: var(--primary); text-align: center; margin-bottom: 5px;'>Pesquisa de Satisfação Escolar</h2><p style='text-align: center; color: #64748b; font-weight: bold; margin-bottom: 25px;'>Sua opinião é 100% anônima e essencial para melhorarmos nossa escola.</p>", unsafe_allow_html=True)
    cat = st.selectbox("1. Identifique seu perfil para iniciarmos:", ["", "Estudante", "Pais/Responsável", "Professor", "Servidor"])
    if cat:
        with st.form("form_sat", clear_on_submit=True):
            turma_sel = ""
            if cat == "Estudante":
                df_al = carregar_alunos()
                if not df_al.empty:
                    lista_t = sorted(df_al['turma'].unique()) 
                else:
                    lista_t = []
                turma_sel = st.selectbox("Qual é a sua Turma?", [""] + lista_t)
                st.markdown("---")
            opcoes = ["1 - 😡 Muito Insatisfeito", "2 - 😟 Insatisfeito", "3 - 😐 Neutro", "4 - 😊 Satisfeito", "5 - 🤩 Muito Satisfeito"]
            st.markdown("#### 🔹 Avaliação Geral")
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
            else: 
                q4 = st.radio("Como você avalia as condições de trabalho e recursos disponíveis no seu setor?", opcoes, index=None)
                q5 = st.radio("Como você avalia o clima organizacional e a colaboração da equipe?", opcoes, index=None)
            sugestao = st.text_area("Deixe aqui uma sugestão, crítica ou elogio (Opcional)")
            if st.form_submit_button("🚀 ENVIAR MINHA AVALIAÇÃO AGORA"):
                if not all([q1, q2, q3, q4, q5]): 
                    st.error("⚠️ Atenção: Por favor, selecione uma nota para todas as 5 perguntas antes de enviar.")
                elif cat == "Estudante" and not turma_sel: 
                    st.error("⚠️ Atenção: Por favor, selecione a sua turma no topo do formulário.")
                else:
                    conn = conectar_bd()
                    if conn:
                        try:
                            cur = conn.cursor()
                            cur.execute("INSERT INTO satisfacao_v1 (data_hora, categoria, turma, q1, q2, q3, q4, q5, sugestao) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)", (obter_hora_atual(), cat, turma_sel, int(q1[0]), int(q2[0]), int(q3[0]), int(q4[0]), int(q5[0]), sugestao))
                            conn.commit()
                            st.session_state.pesquisa_enviada = True
                            st.rerun()
                        except: 
                            st.error("Erro de conexão ao salvar avaliação. Tente novamente.")
                        finally: 
                            liberar_conn(conn)
                    else: 
                        st.error("Não foi possível conectar ao banco de dados no momento.")
    st.stop() 

# ------------------------------------------------------------
# 7.1 MÓDULO PÚBLICO: PAINEL INFORMATIVO
# ------------------------------------------------------------
@st.cache_data(ttl=30)
def carregar_dados_painel_informativo(data_str, turma, hora_limite_saida_str="17:00:00"):
    """Carrega, em uma única conexão, ausentes, presentes à tarde e liberados."""
    try:
        hora_limite = datetime.strptime(hora_limite_saida_str, "%H:%M:%S").time()
    except Exception:
        hora_limite = datetime.strptime("17:00:00", "%H:%M:%S").time()

    conn = conectar_bd()
    if not conn:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), False, "Não foi possível conectar ao banco de dados."

    try:
        # A consulta utiliza quatro parâmetros de data:
        # 1) falta, 2) início da suspensão, 3) fim da suspensão, 4) presença.
        params_aus = [data_str, data_str, data_str, data_str]
        query_aus = """
            SELECT
                a.codigo,
                a.nome,
                a.turma,
                f.motivo_saida AS motivo_falta,
                s.data_inicio AS suspensao_inicio,
                s.data_fim AS suspensao_fim,
                s.motivo AS motivo_suspensao
            FROM alunos_v2 a
            LEFT JOIN registros_v2 f
                ON f.codigo_aluno = a.codigo
               AND f.data = %s
               AND f.tipo_registro = 'FALTA'
            LEFT JOIN LATERAL (
                SELECT data_inicio, data_fim, motivo
                FROM suspensoes_v1 s0
                WHERE s0.codigo_aluno = a.codigo
                  AND s0.data_inicio <= %s::date
                  AND s0.data_fim >= %s::date
                ORDER BY s0.data_inicio DESC, s0.id DESC
                LIMIT 1
            ) s ON TRUE
            WHERE a.status = 'ATIVO'
              AND NOT EXISTS (
                    SELECT 1
                    FROM registros_v2 r
                    WHERE r.codigo_aluno = a.codigo
                      AND r.data = %s
                      AND r.tipo_registro = 'PRESENCA'
              )
        """
        if turma != "Todas":
            query_aus += " AND a.turma = %s"
            params_aus.append(turma)
        query_aus += " ORDER BY a.turma, a.nome"
        df_aus = pd.read_sql_query(query_aus, conn, params=params_aus)

        params_tarde = [data_str]
        query_tarde = """
            SELECT
                a.codigo,
                a.nome,
                a.turma,
                r.hora_entrada,
                r.status_entrada
            FROM registros_v2 r
            JOIN alunos_v2 a ON a.codigo = r.codigo_aluno
            WHERE r.data = %s
              AND r.tipo_registro = 'PRESENCA'
              AND r.hora_entrada >= TIME '12:00:00'
              AND a.status = 'ATIVO'
        """
        if turma != "Todas":
            query_tarde += " AND a.turma = %s"
            params_tarde.append(turma)
        query_tarde += " ORDER BY a.turma, r.hora_entrada, a.nome"
        df_tarde = pd.read_sql_query(query_tarde, conn, params=params_tarde)

        params_lib = [data_str, hora_limite]
        query_lib = """
            SELECT a.codigo, a.nome, a.turma, r.hora_saida, r.motivo_saida
            FROM registros_v2 r
            JOIN alunos_v2 a ON a.codigo = r.codigo_aluno
            WHERE r.data = %s
              AND r.tipo_registro = 'PRESENCA'
              AND r.hora_saida IS NOT NULL
              AND r.hora_saida < %s
              AND a.status = 'ATIVO'
        """
        if turma != "Todas":
            query_lib += " AND a.turma = %s"
            params_lib.append(turma)
        query_lib += " ORDER BY a.turma, r.hora_saida, a.nome"
        df_lib = pd.read_sql_query(query_lib, conn, params=params_lib)

        cur = conn.cursor()
        cur.execute(
            "SELECT COALESCE(dia_letivo, FALSE) FROM calendario_letivo WHERE data = %s",
            (data_str,),
        )
        res_cal = cur.fetchone()
        dia_letivo = bool(res_cal[0]) if res_cal else False
        # Um estudante liberado não permanece na lista de presentes à tarde.
        if not df_tarde.empty and not df_lib.empty:
            codigos_liberados = set(df_lib["codigo"].astype(str))
            df_tarde = df_tarde[
                ~df_tarde["codigo"].astype(str).isin(codigos_liberados)
            ].copy()

        return df_aus, df_tarde, df_lib, dia_letivo, ""
    except Exception as e:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), False, str(e)
    finally:
        liberar_conn(conn)


def renderizar_painel_informativo_publico():
    """Painel público, sem senha, com três grupos mutuamente exclusivos."""
    import html as _html

    renderizar_logo_central()
    st.markdown(
        '<div class="info-panel-hero">'
        '<div class="info-panel-title">📢 PAINEL INFORMATIVO</div>'
        '<div class="info-panel-subtitle">Acompanhamento da frequência diária dos estudantes</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    st.markdown('<div class="info-filter-card">', unsafe_allow_html=True)
    c1, c2 = st.columns([1, 1.6])
    with c1:
        data_info = st.date_input(
            "📅 Data",
            value=obter_hora_atual().date(),
            key="painel_info_data_publico",
        )
    with c2:
        df_publico_alunos = carregar_alunos()
        turmas_publico = []
        if not df_publico_alunos.empty:
            turmas_publico = sorted(
                df_publico_alunos["turma"].dropna().astype(str).unique()
            )
        turma_info = st.selectbox(
            "🏫 Turma",
            ["Todas"] + turmas_publico,
            key="painel_info_turma_publico",
        )
    st.markdown('</div>', unsafe_allow_html=True)

    data_str = data_info.strftime("%Y-%m-%d")
    (
        df_aus,
        df_tarde,
        df_lib,
        dia_letivo,
        erro_info,
    ) = carregar_dados_painel_informativo(
        data_str,
        turma_info,
        "17:00:00",
    )

    if erro_info:
        st.error(f"Não foi possível carregar o painel: {erro_info}")
        return

    if not dia_letivo:
        st.warning(
            f"📅 {data_info.strftime('%d/%m/%Y')} não está configurado como dia letivo. "
            "O painel não apresenta estudantes como ausentes para evitar interpretações incorretas."
        )
        st.markdown(
            '<div class="info-public-note">Painel público • consulta apenas informações de frequência</div>',
            unsafe_allow_html=True,
        )
        return

    total_aus = len(df_aus)
    total_tarde = len(df_tarde)
    total_lib = len(df_lib)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("❌ Ausentes", total_aus)
    c2.metric("🌤️ Presentes à tarde", total_tarde)
    c3.metric("🚪 Liberados", total_lib)
    c4.metric("📅 Data", data_info.strftime("%d/%m/%Y"))

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    col_aus, col_tarde, col_lib = st.columns(3, gap="medium")

    with col_aus:
        st.markdown(
            f'<div class="info-section">'
            f'<div class="info-section-title">❌ AUSENTES</div>'
            f'<div class="info-section-count">{total_aus} estudante(s)</div>',
            unsafe_allow_html=True,
        )

        if df_aus.empty:
            st.markdown(
                '<div class="info-empty">✅ Nenhum estudante ausente.</div>',
                unsafe_allow_html=True,
            )
        else:
            for row in df_aus.to_dict("records"):
                nome = _html.escape(str(row.get("nome") or ""))
                codigo = _html.escape(str(row.get("codigo") or ""))
                turma = _html.escape(str(row.get("turma") or ""))
                motivo_falta = _html.escape(
                    str(row.get("motivo_falta") or "").strip()
                )
                motivo_suspensao = _html.escape(
                    str(row.get("motivo_suspensao") or "").strip()
                )

                if motivo_suspensao:
                    inicio_s = _html.escape(str(row.get("suspensao_inicio") or "")[:10])
                    fim_s = _html.escape(str(row.get("suspensao_fim") or "")[:10])
                    status_falta = (
                        '<span style="color:#7c2d12;font-weight:900;">'
                        '⛔ SUSPENSÃO DISCIPLINAR</span><br>'
                        f'Período: <b>{inicio_s} a {fim_s}</b><br>'
                        f'Motivo: <b>{motivo_suspensao}</b>'
                    )
                elif motivo_falta:
                    status_falta = (
                        '<span style="color:#166534;font-weight:900;">'
                        '✅ FALTA JUSTIFICADA</span> • Motivo: '
                        f'<b>{motivo_falta}</b>'
                    )
                else:
                    status_falta = (
                        '<span style="color:#b91c1c;font-weight:900;">'
                        '⚠️ FALTA NÃO JUSTIFICADA</span>'
                    )

                st.markdown(
                    f'<div class="info-student">'
                    f'<div class="info-student-name">{nome}</div>'
                    f'<div class="info-student-meta">'
                    f'Código: <b>{codigo}</b> • Turma: <b>{turma}</b>'
                    f'</div>'
                    f'<div style="margin-top:7px;font-size:.92rem;">'
                    f'{status_falta}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

        st.markdown('</div>', unsafe_allow_html=True)

    with col_tarde:
        st.markdown(
            f'<div class="info-section">'
            f'<div class="info-section-title">🌤️ PRESENTES À TARDE</div>'
            f'<div class="info-section-count">'
            f'{total_tarde} estudante(s) com entrada a partir de 12:00</div>',
            unsafe_allow_html=True,
        )

        if df_tarde.empty:
            st.markdown(
                '<div class="info-empty">Nenhum estudante nesta condição.</div>',
                unsafe_allow_html=True,
            )
        else:
            for row in df_tarde.to_dict("records"):
                nome = _html.escape(str(row.get("nome") or ""))
                codigo = _html.escape(str(row.get("codigo") or ""))
                turma = _html.escape(str(row.get("turma") or ""))
                hora_entrada = _html.escape(
                    str(row.get("hora_entrada") or "")[:8]
                )

                st.markdown(
                    f'<div class="info-student">'
                    f'<div class="info-student-name">{nome}</div>'
                    f'<div class="info-student-meta">'
                    f'Código: <b>{codigo}</b> • Turma: <b>{turma}</b> • '
                    f'Entrada: <b>{hora_entrada}</b>'
                    f'</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

        st.markdown('</div>', unsafe_allow_html=True)

    with col_lib:
        st.markdown(
            f'<div class="info-section">'
            f'<div class="info-section-title">🚪 LIBERADOS</div>'
            f'<div class="info-section-count">{total_lib} estudante(s)</div>',
            unsafe_allow_html=True,
        )

        if df_lib.empty:
            st.markdown(
                '<div class="info-empty">✅ Nenhum estudante liberado.</div>',
                unsafe_allow_html=True,
            )
        else:
            for row in df_lib.to_dict("records"):
                nome = _html.escape(str(row.get("nome") or ""))
                codigo = _html.escape(str(row.get("codigo") or ""))
                turma = _html.escape(str(row.get("turma") or ""))
                hora_saida = _html.escape(
                    str(row.get("hora_saida") or "")[:8]
                )
                motivo = _html.escape(
                    str(row.get("motivo_saida") or "").strip()
                )
                motivo_html = (
                    f' • Motivo: <b>{motivo}</b>' if motivo else ""
                )

                st.markdown(
                    f'<div class="info-student">'
                    f'<div class="info-student-name">{nome}</div>'
                    f'<div class="info-student-meta">'
                    f'Código: <b>{codigo}</b> • Turma: <b>{turma}</b> • '
                    f'Saída: <b>{hora_saida}</b>{motivo_html}'
                    f'</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('---')
    pdf_painel = gerar_pdf_painel_informativo(
        data_info, turma_info, df_aus, df_tarde, df_lib
    )
    if pdf_painel:
        nome_pdf_painel = f"Painel_Informativo_{data_info.strftime('%Y-%m-%d')}"
        if turma_info != 'Todas':
            nome_pdf_painel += '_' + re.sub(r'[^A-Za-z0-9_-]+', '_', str(turma_info))
        nome_pdf_painel += '.pdf'
        st.download_button(
            '📄 EXPORTAR PAINEL EM PDF',
            data=pdf_painel,
            file_name=nome_pdf_painel,
            mime='application/pdf',
            use_container_width=True,
        )

    st.markdown(
        '<div class="info-public-note">'
        'Painel público • informações exclusivamente necessárias à consulta diária.'
        '</div>',
        unsafe_allow_html=True,
    )


if st.query_params.get("modo") in {"painel_informativo", "painel"}:
    renderizar_painel_informativo_publico()
    st.stop()

# ------------------------------------------------------------
# 8. AUTH E DASHBOARD
# ------------------------------------------------------------
# Credenciais obrigatórias no ambiente de produção. Não há mais senha padrão.
if not SENHA_ADMIN or not SENHA_OPERADOR:
    st.error(
        "🚨 Configuração de segurança incompleta: defina SENHA_ADMIN e "
        "SENHA_OPERADOR nos Secrets do Streamlit antes de acessar o painel administrativo."
    )
    st.stop()

auth_cookie = cookies.get("auth_token")
if not auth_cookie:
    if os.path.exists("logo.png"): 
        st.image("logo.png", width=120)
    st.markdown('<div class="login-title">LOGIN ESCOLAR</div>', unsafe_allow_html=True)
    passw = st.text_input("SENHA", type="password")
    if st.button("ENTRAR", use_container_width=True):
        if passw in [SENHA_ADMIN, SENHA_OPERADOR]:
            cookies["auth_token"] = base64.b64encode(json.dumps({"admin": passw==SENHA_ADMIN}).encode()).decode()
            cookies.save()
            st.session_state['auth_timestamp'] = datetime.now(timezone.utc).timestamp()
            st.rerun()
        else: 
            st.error("Incorreta")
    st.stop()

if 'auth_timestamp' in st.session_state:
    tempo_decorrido = datetime.now(timezone.utc).timestamp() - st.session_state['auth_timestamp']
    if tempo_decorrido > 3600:
        cookies["auth_token"] = ""
        cookies.save()
        if 'auth_timestamp' in st.session_state: del st.session_state['auth_timestamp']
        st.warning("Sua sessão expirou. Por favor, faça login novamente.")
        st.rerun()
else:
    st.session_state['auth_timestamp'] = datetime.now(timezone.utc).timestamp()

try:
    user = json.loads(base64.b64decode(auth_cookie).decode())
    eh_admin = user.get('admin', user.get('eh_admin', False)) 
except Exception: 
    cookies["auth_token"] = ""
    cookies.save()
    st.rerun()

# Inicializa/valida o schema apenas para usuários autenticados.
inicializar_tabelas()

df_alunos = carregar_alunos()

c_out1, c_out2 = st.columns([10, 1])
with c_out2:
    if st.button("SAIR"): 
        cookies["auth_token"] = ""
        cookies.save()
        if 'auth_timestamp' in st.session_state: del st.session_state['auth_timestamp']
        st.rerun()

renderizar_logo_central()
st.markdown('<p class="main-title">PAINEL INTEGRADO</p>', unsafe_allow_html=True)
st.markdown(f'<p class="sub-title">Gestão Escolar • {data_formatada_ptbr()}</p>', unsafe_allow_html=True)

# --- FILTROS GLOBAIS ---
st.markdown("### 🎛️ Filtros Globais do Painel")
c_data, c_ano, cf1, cf2, cf3 = st.columns([1.5, 1, 1.5, 1.5, 2])
anos_disponiveis = [str(y) for y in range(2024, 2035)]
ano_atual = str(obter_hora_atual().year)
if ano_atual not in anos_disponiveis: 
    anos_disponiveis.append(ano_atual)
data_f_global = c_data.date_input("Data (Frequência)", obter_hora_atual().date(), key="filtro_data_global")
ano_f = c_ano.selectbox("Ano Letivo", anos_disponiveis, index=anos_disponiveis.index(ano_atual), key="filtro_ano_da")
pf = cf1.selectbox("Período Acadêmico", ["Todos", "1º Período", "2º Período", "3º Período", "4º Período"], key="filtro_periodo_da")
af = cf2.selectbox("Área Acadêmica", ["Todas", "LÍNGUA PORTUGUESA", "MATEMÁTICA", "LINGUAGENS", "HUMANAS", "NATUREZA"], key="filtro_area_da")
lista_turmas_filtro = []
if not df_alunos.empty:
    lista_turmas_filtro = sorted(df_alunos['turma'].unique())
tf = cf3.selectbox("Turma (Filtra TUDO)", ["Todas"] + lista_turmas_filtro, key="filtro_turma_da")

hoje_real = obter_hora_atual().strftime("%Y-%m-%d")
data_selecionada_str = data_f_global.strftime("%Y-%m-%d")

total_alunos, pres_data, pres_atual, liberados_antes = carregar_resumo_dashboard(
    data_selecionada_str,
    tf,
    st.session_state.get(
        "h_lim_s_atual",
        datetime.strptime("17:00", "%H:%M").time()
    ).strftime("%H:%M:%S")
)
if total_alunos > 0:
    media_geral_freq = f"{(pres_data / total_alunos) * 100:.1f}%"
else:
    media_geral_freq = "0%"

abas_do_sistema = [
    "🏠 Visão Geral",
    "📝 Registro",
    "📊 Gestão de Frequência",
    "📱 Comunicação de Falta",
    "📢 Painel Informativo",
    "🚨 Risco de Evasão",
    "📈 Histórico de Frequência",
    "📑 Desempenho Acadêmico",
    "💬 Satisfação Pública"
]
if eh_admin:
    abas_do_sistema.append("⚙️ Manutenção do Sistema")

st.sidebar.markdown('<div class="menu-header">☰ MENU</div>', unsafe_allow_html=True)
aba_atual = st.sidebar.radio(
    "Navegação principal",
    abas_do_sistema,
    index=0,
    key="navegacao_principal",
    label_visibility="collapsed"
)

if eh_admin and aba_atual == "⚙️ Manutenção do Sistema":
    st.sidebar.markdown(
        '<div style="margin:8px 0 4px 18px;padding:10px 14px;border-left:5px solid #f59e0b;'
        'background:#fff7ed;border-radius:10px;font-weight:900;color:#9a3412;">'
        'SUBMENU DE MANUTENÇÃO</div>',
        unsafe_allow_html=True,
    )
    try:
        st.sidebar.page_link("pages/06_Manutencao_AVS.py", label="↳ 📊 Painel de Avaliação")
    except Exception:
        pass

dff = pd.DataFrame()
if aba_atual == "📑 Desempenho Acadêmico":
    with st.spinner("Sincronizando dados acadêmicos..."):
        dff = obter_dados_acad_filtrados(ano_f, pf, af, tf)

if not dff.empty:
    media_geral_acad = f"{dff['acerto'].mean() * 10:.1f}" 
else:
    media_geral_acad = "--"
if aba_atual == "💬 Satisfação Pública":
    sat_est_str, sat_pais_str, sat_eq_str = calcular_satisfacao_global_cached(ano_f, tf)
else:
    sat_est_str, sat_pais_str, sat_eq_str = "--", "--", "--"

st.markdown(f"""
<div class="metrics-container">
    <div class="metric-card m-total">
        <span class="m-val">{total_alunos}</span>
        <span class="m-lab">Total Alunos</span>
    </div>
    <div class="metric-card m-presente">
        <span class="m-val">{pres_data}</span>
        <span class="m-current">AGORA: {pres_atual}</span>
        <span class="m-lab">Presentes (Dia)</span>
    </div>
    <div class="metric-card m-liberado">
        <span class="m-val">{liberados_antes}</span>
        <span class="m-lab">Liberados Antes do Horário</span>
    </div>
    <div class="metric-card m-falta">
        <span class="m-val">{total_alunos-pres_data}</span>
        <span class="m-lab">Faltas (Dia)</span>
    </div>
    <div class="metric-card m-atraso">
        <span class="m-val">{media_geral_freq}</span>
        <span class="m-lab">Frequência (Dia)</span>
    </div>
</div>
<div class="metrics-container" style="margin-top: 15px;">
    <div class="metric-card m-acad">
        <span class="m-val">{media_geral_acad}</span>
        <span class="m-lab">Média Acad. (Filtrada)</span>
    </div>
    <div class="metric-card m-satest">
        <span class="m-val">{sat_est_str}</span>
        <span class="m-lab">Satisfação Estudante</span>
    </div>
    <div class="metric-card m-satpais">
        <span class="m-val">{sat_pais_str}</span>
        <span class="m-lab">Satisfação Pais</span>
    </div>
    <div class="metric-card m-sateq">
        <span class="m-val">{sat_eq_str}</span>
        <span class="m-lab">Satisfação Equipe</span>
    </div>
</div>
""", unsafe_allow_html=True)

# 0 = Visão Geral (somente filtros e cards); os módulos existentes começam no índice 1.
indice_aba = 1

# =====================================================================
# POP-UP DE ENTRADA RÁPIDA
# =====================================================================
def registrar_entrada_direta(codigo, data, hora_entrada, hora_limite):
    """
    Registra entrada pelo MODO SISTEMA.
    A hora recebida é a hora do servidor; não consulta a planilha.
    Um registro já existente é preservado para evitar sobrescrita de uma hora
    oficial proveniente da planilha.
    """
    codigo = str(codigo or "").strip().upper()
    if not codigo:
        return False, "Código do estudante não informado."

    # Garante tipos consistentes para o PostgreSQL.
    try:
        data_db = data if hasattr(data, "year") else datetime.strptime(str(data), "%Y-%m-%d").date()
    except Exception as e:
        return False, f"Data inválida: {e}"

    try:
        hora_db = hora_entrada if hasattr(hora_entrada, "hour") else normalizar_hora_entrada(hora_entrada)
        limite_db = hora_limite if hasattr(hora_limite, "hour") else normalizar_hora_entrada(hora_limite)
        if hora_db is None or limite_db is None:
            return False, "Horário de entrada inválido."
    except Exception as e:
        return False, f"Horário inválido: {e}"

    status = "PRESENTE" if hora_db <= limite_db else "ATRASO"
    hora_str = hora_db.strftime("%H:%M:%S")
    conn = conectar_bd()
    if not conn:
        return False, "Não foi possível conectar ao banco de dados."

    email_responsavel = None
    nome_aluno = None
    try:
        cur = conn.cursor()

        cur.execute(
            """
            SELECT nome, email_responsavel
            FROM alunos_v2
            WHERE UPPER(TRIM(codigo)) = %s
              AND UPPER(TRIM(status)) = 'ATIVO'
            LIMIT 1
            """,
            (codigo,),
        )
        aluno = cur.fetchone()
        if not aluno:
            conn.rollback()
            return False, f"Código {codigo} não encontrado ou aluno inativo."

        nome_aluno, email_responsavel = aluno

        # Se já existir um registro para a data, preserva integralmente
        # o registro existente. Assim, o modo SISTEMA nunca sobrescreve
        # uma entrada previamente registrada pela PLANILHA.
        cur.execute(
            """
            SELECT id, status_entrada, hora_entrada
            FROM registros_v2
            WHERE codigo_aluno = %s
              AND data = %s
              AND tipo_registro = 'PRESENCA'
            LIMIT 1
            """,
            (codigo, data_db),
        )
        existente = cur.fetchone()

        if existente:
            registro_id, status_existente, hora_existente = existente
            conn.rollback()
            hora_confirmada_str = (
                hora_existente.strftime("%H:%M:%S")
                if hora_existente else hora_str
            )
            contar_presencas_data.clear()
            carregar_resumo_dashboard.clear()
            carregar_faltas.clear()
            return True, f"{nome_aluno} | {status_existente} | {hora_confirmada_str}"

        cur.execute(
            """
            INSERT INTO registros_v2 (
                codigo_aluno, data, hora_entrada, status_entrada, tipo_registro, origem_entrada
            )
            VALUES (%s, %s, %s, %s, 'PRESENCA', 'SISTEMA')
            RETURNING id
            """,
            (codigo, data_db, hora_db, status),
        )
        registro_id = cur.fetchone()[0]
        conn.commit()

        # Confirma no próprio banco que o registro realmente ficou persistido.
        cur.execute(
            """
            SELECT id, status_entrada, hora_entrada
            FROM registros_v2
            WHERE id = %s
              AND codigo_aluno = %s
              AND data = %s
              AND tipo_registro = 'PRESENCA'
            """,
            (registro_id, codigo, data_db),
        )
        confirmado = cur.fetchone()

        if not confirmado:
            return False, "O banco não confirmou a gravação da entrada."

        _, status_confirmado, hora_confirmada = confirmado
        hora_confirmada_str = (
            hora_confirmada.strftime("%H:%M:%S") if hora_confirmada else hora_str
        )

    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        return False, f"Erro ao registrar entrada no banco: {e}"
    finally:
        liberar_conn(conn)

    # Limpa somente os caches que dependem da frequência.
    contar_presencas_data.clear()
    carregar_resumo_dashboard.clear()
    carregar_faltas.clear()

    if email_responsavel:
        evento = "ENTRADA" if status_confirmado == "PRESENTE" else "ENTRADA COM ATRASO"
        threading.Thread(
            target=disparar_email_background,
            args=(email_responsavel, nome_aluno, evento, hora_confirmada_str, data_db),
            daemon=True,
        ).start()

    return True, f"{nome_aluno} | {status_confirmado} | {hora_confirmada_str}"


@st.dialog("🚀 MODO DE ENTRADA RÁPIDA", width="large")
def popup_entrada_rapida(data_hoje, hora_limite):
    st.markdown(
        "<p style='text-align:center; color:#64748b;'>"
        "Bipe o cartão ou digite o código. "
        "A entrada será gravada diretamente no sistema usando o horário do servidor."
        "</p>",
        unsafe_allow_html=True,
    )

    gerar_camera("Entrada", "REGISTRAR", "cam_popup")

    with st.form("f_popup", clear_on_submit=False):
        cod_en = st.text_input(
            "Código do Estudante",
            placeholder="Bipe o cartão ou digite manualmente...",
            key="codigo_entrada_popup",
        )
        enviar = st.form_submit_button("REGISTRAR", use_container_width=True)

    if enviar:
        if not cod_en or not cod_en.strip():
            st.warning("Digite ou bipe um código de estudante.")
            return

        # MODO 2 — ENTRADA VIA ABA DO SISTEMA:
        # a hora é exclusivamente o instante real do servidor.
        agora = obter_hora_atual()
        hora_registro = agora.time().replace(microsecond=0)

        sucesso, mensagem = registrar_entrada_direta(
            cod_en.strip(),
            data_hoje,
            hora_registro,
            hora_limite,
        )

        if sucesso:
            st.success(f"✅ Entrada registrada: {mensagem}")
            st.markdown(
                """
                <script>
                    var utterance = new SpeechSynthesisUtterance("BEM-VINDO, ESTUDANTE!");
                    utterance.lang = 'pt-BR';
                    utterance.rate = 1.2;
                    window.speechSynthesis.speak(utterance);
                </script>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.error(f"⚠️ {mensagem}")


# =====================================================================

if aba_atual == abas_do_sistema[indice_aba]:
    st.markdown("#### ⚙️ Configuração do Turno e Dia Letivo")
    c_cfg1, c_cfg2 = st.columns(2)
    with c_cfg1:
        h_lim_e = st.time_input("🟢 Horário Limite de Entrada", datetime.strptime("07:30", "%H:%M").time())
        st.session_state.h_lim_e_atual = h_lim_e
    with c_cfg2:
        h_lim_s = st.time_input("🔴 Horário de Término (Saída)", datetime.strptime("17:00", "%H:%M").time())
        st.session_state.h_lim_s_atual = h_lim_s
    
    with st.form("form_controle_dias"):
        st.markdown("📅 **Ativação do Calendário:**")
        col_d1, col_d2 = st.columns(2)
        with col_d1: 
            data_selecionada = st.date_input("Selecione a Data no Calendário", value=obter_hora_atual().date())
        with col_d2: 
            st.write("")
            st.write("")
            is_ativo = st.checkbox("Ativar como Dia Letivo?", value=True)
            
        if st.form_submit_button("💾 Salvar Configuração do Dia"):
            conn = conectar_bd()
            if conn:
                try:
                    cur = conn.cursor()
                    cur.execute("INSERT INTO calendario_letivo (data, dia_letivo) VALUES (%s, %s) ON CONFLICT (data) DO UPDATE SET dia_letivo = EXCLUDED.dia_letivo", (data_selecionada, is_ativo))
                    conn.commit()
                    _verificar_dia_letivo_cache.clear()
                    st.success(f"Pronto! A data {data_selecionada.strftime('%d/%m/%Y')} foi configurada.")
                except Exception as e: 
                    st.error(f"Erro ao salvar: {e}")
                finally: 
                    liberar_conn(conn)
            else: 
                st.error("Sem conexão com o banco de dados.")

    st.markdown("---")
    
    t_en, t_sa, t_jf, t_susp = st.tabs(["✅ ENTRADA", "🚪 REGISTRO DE SAÍDA", "📝 JUSTIFICAR FALTAS", "⛔ SUSPENSÃO DO ESTUDANTE"])
    
    with t_en:
        if not verificar_dia_letivo(hoje_real): 
            st.error("⚠️ REGISTRO BLOQUEADO: A data de HOJE não foi ativada como Dia Letivo no painel logo acima.")
        else:
            st.markdown("### 🏃‍♂️ Controle de Entrada")
            st.write("Use o Modo Rápido durante o horário de pico. Cada entrada é gravada diretamente no sistema no momento do registro.")
            
            if st.button("🟢 ABRIR JANELA DE ENTRADA RÁPIDA", type="primary", use_container_width=True):
                popup_entrada_rapida(hoje_real, h_lim_e)
            
            # ========== UPLOAD DE CSV E PLANILHA GOOGLE COM LINK SALVO ==========
            st.markdown("---")
            with st.expander("📤 Carregar Entradas em Lote (CSV ou Planilha Google)"):
                st.info("""
                **Formato esperado (separador ; ou ,):**
                - Coluna **CÓDIGO** (obrigatória)
                - Coluna **ESTUDANTE** (opcional, será ignorada)
                - Coluna **HORA DE ENTRADA** (obrigatória) – formato `HH:MM:SS` ou `HH:MM`
                - Coluna **DATA** (opcional) – formato `DD/MM/YYYY` (ex: 14/08/2026). Se ausente, o sistema usará a data selecionada.

                **Planilha Google:** o link pode ser salvo permanentemente no banco de dados.
                """)

                # Exibir o link salvo atualmente
                link_salvo = obter_link_planilha()
                if link_salvo:
                    st.info(f"🔗 **Link atual:** {link_salvo}")
                else:
                    st.warning("Nenhum link de planilha salvo. Use o botão abaixo para definir um.")

                col_links, col_botoes = st.columns([3, 1])
                with col_links:
                    with st.form("form_gerenciar_link", clear_on_submit=True):
                        novo_link = st.text_input("Novo link (ou cole o link para salvar)", 
                                                 placeholder="https://docs.google.com/spreadsheets/d/...",
                                                 value=link_salvo if link_salvo else "")
                        c_btn1, c_btn2 = st.columns(2)
                        with c_btn1:
                            if st.form_submit_button("💾 Salvar Link"):
                                if novo_link:
                                    if salvar_link_planilha(novo_link):
                                        st.success("Link salvo com sucesso!")
                                        st.rerun()
                                    else:
                                        st.error("Erro ao salvar link.")
                                else:
                                    st.warning("Cole um link válido.")
                        with c_btn2:
                            if st.form_submit_button("🗑️ Excluir Link"):
                                if excluir_link_planilha():
                                    st.success("Link removido!")
                                    st.rerun()
                                else:
                                    st.error("Erro ao excluir link.")

                st.markdown("---")
                st.subheader("Carregar dados da planilha")
                with st.form("form_upload_entrada", clear_on_submit=True):
                    data_base = obter_hora_atual().date()
                    st.info(f"📅 **Data protegida do processamento: {data_base.strftime('%d/%m/%Y')}**\n\nO carregamento diário da Google Planilha utiliza sempre a data atual do sistema. Registros de dias anteriores permanecem na planilha, mas são ignorados.")

                    # Opção 1: Upload de arquivo CSV (mantido)
                    arquivo_csv = st.file_uploader("Opção 1: Escolha um arquivo CSV", type=["csv"], key="csv_entrada")

                    st.markdown("---")
                    st.markdown("**OU**")

                    # Opção 2: Usar link salvo
                    usar_link_salvo = st.checkbox("Usar link salvo (se existir)", value=bool(link_salvo), disabled=not link_salvo)

                    # Opção 3: fornecer um link temporário (não salva)
                    link_temporario = st.text_input("Opção 3: Ou insira um link temporário (não será salvo)", 
                                                    placeholder="https://docs.google.com/spreadsheets/d/...")

                    if st.form_submit_button("🚀 CARREGAR DADOS"):
                        df_processar = None
                        fonte = ""
                        diagnostic = ""

                        if arquivo_csv:
                            conteudo = arquivo_csv.read()
                            try:
                                conteudo_str = conteudo.decode('utf-8-sig')
                            except:
                                conteudo_str = conteudo.decode('latin-1')
                            try:
                                df_processar = pd.read_csv(io.StringIO(conteudo_str), sep=';', dtype=str, keep_default_na=False)
                                if len(df_processar.columns) == 1:
                                    df_processar = pd.read_csv(io.StringIO(conteudo_str), sep=',', dtype=str, keep_default_na=False)
                            except Exception:
                                df_processar = pd.read_csv(io.StringIO(conteudo_str), sep=',', dtype=str, keep_default_na=False)

                            df_processar, _, erros_colunas = mapear_colunas_entrada(df_processar)
                            if erros_colunas:
                                diagnostic = "Erros: " + "; ".join(erros_colunas)
                                df_processar = None
                            else:
                                if 'DATA' not in df_processar.columns:
                                    df_processar['DATA'] = data_base
                                else:
                                    df_processar['DATA'] = pd.to_datetime(
                                        df_processar['DATA'], errors='coerce', dayfirst=True
                                    ).dt.date
                                df_processar['HORA'] = df_processar['HORA'].apply(normalizar_hora_entrada)
                                df_processar = df_processar[df_processar['DATA'] == data_base]
                            fonte = "CSV"
                        elif usar_link_salvo and link_salvo:
                            df_processar, diagnostic = ler_planilha_google(link_salvo, data_base)
                            fonte = "Planilha Google (salva)"
                        elif link_temporario:
                            df_processar, diagnostic = ler_planilha_google(link_temporario, data_base)
                            fonte = "Planilha Google (temporária)"
                        else:
                            st.warning("Por favor, forneça um CSV, use o link salvo ou insira um link temporário.")
                            st.stop()

                        if diagnostic:
                            st.markdown("### 🔍 Diagnóstico da leitura da planilha")
                            st.code(diagnostic)

                        if df_processar is not None:
                            with st.spinner(f"Processando registros da {fonte}..."):
                                hora_limite = st.session_state.get('h_lim_e_atual', datetime.strptime("07:30", "%H:%M").time())
                                total, salvos, emails, erros = processar_entrada_df(df_processar, data_base, hora_limite, origem_entrada="PLANILHA")
                                if emails:
                                    st.success(
                                        f"✅ Processamento concluído: {salvos} registros salvos; "
                                        f"{emails} e-mails aceitos pelo servidor SMTP "
                                        f"(de {total} linhas lidas)."
                                    )
                                else:
                                    st.success(
                                        f"✅ Processamento concluído: {salvos} registros salvos; "
                                        f"nenhum e-mail foi aceito pelo servidor SMTP "
                                        f"(de {total} linhas lidas)."
                                    )
                                if erros:
                                    st.markdown("### ⚠️ Detalhes dos erros")
                                    for e in erros:
                                        st.error(e)
                                contar_presencas_data.clear()
                                carregar_faltas.clear()
                        else:
                            st.error("Falha ao carregar dados da planilha. Verifique o diagnóstico acima.")
            # ========== FIM DO BLOCO ==========

    with t_sa:
        if not verificar_dia_letivo(hoje_real): 
            st.error("⚠️ REGISTRO BLOQUEADO: A data de HOJE não foi ativada como Dia Letivo no painel logo acima.")
        else:
            gerar_camera("Saída", "CONFIRMAR SAÍDA", "c_out")
            
            with st.form("f_sa", clear_on_submit=True):
                st.markdown("##### Identifique o estudante:")
                
                c_sa1, c_sa2 = st.columns(2)
                with c_sa1: 
                    cod_sa = st.text_input("Por Código (Bipe o Cartão)")
                with c_sa2: 
                    lista_alunos_saida = [""] + [f"{r['codigo']} - {r['nome']} ({r['turma']})" for _, r in df_alunos.iterrows()]
                    nome_sa = st.selectbox("Ou busque pelo Nome / Turma", lista_alunos_saida)
                
                hora_saida_manual = st.time_input("Horário Exato da Saída", obter_hora_atual().time())
                mot = st.selectbox("Motivo", MOTIVOS_JUSTIFICATIVA)
                
                if st.form_submit_button("CONFIRMAR SAÍDA"):
                    if cod_sa:
                        aluno_identificado = cod_sa.upper()
                    elif nome_sa:
                        aluno_identificado = nome_sa.split(" - ")[0]
                    else:
                        aluno_identificado = None
                    
                    if aluno_identificado:
                        res = registrar_saida(aluno_identificado, mot, True, hoje_real, hora_saida_manual.strftime("%H:%M:%S"), h_lim_s)
                        if res: 
                            st.success(f"Saída de {res} registrada às {hora_saida_manual.strftime('%H:%M')}!")
                            st.rerun()
                        else: 
                            st.error("Erro: Aluno sem registro de entrada hoje.")
                    else:
                        st.warning("⚠️ Por favor, informe o código do cartão ou selecione o nome na lista antes de confirmar.")

    with t_susp:
        st.subheader("⛔ Suspensão do Estudante")
        st.info(
            "Registre aqui uma suspensão disciplinar. Se houver e-mail cadastrado, "
            "o responsável receberá automaticamente a comunicação após o salvamento."
        )

        lista_susp_alunos = [""]
        if not df_alunos.empty:
            lista_susp_alunos += [
                f"{r['codigo']} - {r['nome']} ({r['turma']})"
                for _, r in df_alunos.iterrows()
            ]

        with st.form("form_suspensao", clear_on_submit=True):
            aluno_susp = st.selectbox(
                "👤 Estudante",
                lista_susp_alunos,
                key="suspensao_aluno"
            )
            c_s1, c_s2 = st.columns(2)
            with c_s1:
                data_susp_inicio = st.date_input(
                    "📅 Início da suspensão",
                    value=obter_hora_atual().date(),
                    key="suspensao_inicio"
                )
            with c_s2:
                data_susp_fim = st.date_input(
                    "📅 Fim da suspensão",
                    value=obter_hora_atual().date(),
                    key="suspensao_fim"
                )

            categoria_susp = st.selectbox(
                "📚 Categoria da infração",
                list(MOTIVOS_SUSPENSAO.keys()),
                key="categoria_suspensao"
            )
            motivo_susp = st.selectbox(
                "⚖️ Motivo da penalidade",
                MOTIVOS_SUSPENSAO[categoria_susp],
                key="motivo_suspensao"
            )

            if st.form_submit_button("💾 APLICAR SUSPENSÃO", type="primary"):
                if not aluno_susp:
                    st.warning("Selecione um estudante.")
                elif data_susp_fim < data_susp_inicio:
                    st.error("A data final não pode ser anterior à data inicial.")
                else:
                    cod_susp = aluno_susp.split(" - ")[0].strip()
                    sucesso_susp, resultado_susp = registrar_suspensao(
                        cod_susp,
                        data_susp_inicio,
                        data_susp_fim,
                        motivo_susp,
                    )
                    if sucesso_susp:
                        st.success(
                            f"✅ Suspensão registrada para {resultado_susp['nome']} "
                            f"({data_susp_inicio.strftime('%d/%m/%Y')} a {data_susp_fim.strftime('%d/%m/%Y')})."
                        )
                        if resultado_susp.get("email"):
                            threading.Thread(
                                target=enviar_email_suspensao_background,
                                args=(
                                    resultado_susp["email"],
                                    resultado_susp["nome"],
                                    resultado_susp["turma"],
                                    data_susp_inicio,
                                    data_susp_fim,
                                    motivo_susp,
                                ),
                                daemon=True,
                            ).start()
                            st.info("📧 Comunicação de suspensão enviada para processamento.")
                        else:
                            st.warning("⚠️ O estudante não possui e-mail de responsável cadastrado.")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(resultado_susp)

        st.markdown("---")
        st.subheader("📋 Suspensões registradas")
        susp_aluno_filtro = aluno_susp if 'aluno_susp' in locals() else ""
        if susp_aluno_filtro:
            cod_filtro_susp = susp_aluno_filtro.split(" - ")[0].strip()
            df_susp_reg = carregar_suspensoes_aluno(cod_filtro_susp)
        else:
            df_susp_reg = buscar_suspensoes_na_data(hoje_real, tf)

        if df_susp_reg.empty:
            st.info("Nenhuma suspensão encontrada para a seleção atual.")
        else:
            df_susp_exib = df_susp_reg.copy()
            if 'codigo' not in df_susp_exib.columns:
                df_susp_exib = df_susp_exib.rename(columns={'codigo_aluno': 'codigo'})
            cols_show = [c for c in ['data_inicio','data_fim','motivo'] if c in df_susp_exib.columns]
            if cols_show:
                df_susp_exib = df_susp_exib[cols_show].rename(columns={
                    'data_inicio': 'Início', 'data_fim': 'Fim', 'motivo': 'Motivo'
                })
                st.dataframe(df_susp_exib, use_container_width=True, hide_index=True)

    with t_jf:
        st.subheader("Justificar Faltas de Estudantes")
        d_just = st.date_input("Data da Falta", value=data_f_global)
        df_faltas = carregar_faltas(d_just.strftime("%Y-%m-%d"))
        
        if not df_faltas.empty:
            turmas_disponiveis = ["Todas"] + sorted(df_faltas['turma'].unique())
            turma_just = st.selectbox("Filtrar por Turma", turmas_disponiveis)
            
            if turma_just == "Todas":
                df_faltas_filtrado = df_faltas
            else:
                df_faltas_filtrado = df_faltas[df_faltas['turma'] == turma_just]
                
            df_pendentes = df_faltas_filtrado[df_faltas_filtrado['motivo_saida'].isnull()]
            
            if not df_pendentes.empty:
                with st.form("form_justificar"):
                    al_falta_sel = st.selectbox(
                        "Selecione o Estudante Faltoso", 
                        [""] + [f"{r['codigo_aluno']} - {r['nome']} ({r['turma']})" for _, r in df_pendentes.iterrows()]
                    )
                    motivo_falta = st.selectbox(
                        "Justificativa Oficial",
                        MOTIVOS_JUSTIFICATIVA
                    )
                    
                    if st.form_submit_button("SALVAR JUSTIFICATIVA") and al_falta_sel:
                        cod_f = al_falta_sel.split(" - ")[0]
                        conn = conectar_bd()
                        if conn:
                            try:
                                cur = conn.cursor()
                                cur.execute("""
                                    INSERT INTO registros_v2 (codigo_aluno, data, tipo_registro, motivo_saida) 
                                    VALUES (%s, %s, 'FALTA', %s)
                                    ON CONFLICT (codigo_aluno, data, tipo_registro) 
                                    DO UPDATE SET motivo_saida = EXCLUDED.motivo_saida
                                """, (cod_f, d_just.strftime("%Y-%m-%d"), motivo_falta))
                                conn.commit()
                                carregar_faltas.clear()
                                st.success("Justificativa salva com sucesso!")
                                time.sleep(1)
                                st.rerun()
                            finally: 
                                liberar_conn(conn)
            else:
                st.info(f"Todos os alunos faltosos da turma {turma_just} já foram justificados.")

            st.markdown("---")
            st.write("**Faltas já justificadas nesta data:**")
            faltas_justificadas = df_faltas[df_faltas['motivo_saida'].notna()]
            
            if not faltas_justificadas.empty:
                for _, f in faltas_justificadas.iterrows(): 
                    st.info(f"👤 {f['nome']} ({f['turma']}) - Justificativa: **{f['motivo_saida']}**")
            else: 
                st.write("Nenhuma falta justificada ainda.")
        else: 
            st.success("Nenhum aluno faltou nesta data! Todos os alunos ativos estão com 'PRESENCA'.")
indice_aba += 1

# ================================================================
# ABA "📊 GESTÃO DE FREQUÊNCIA" – COM CONTADORES
# ================================================================
if aba_atual == abas_do_sistema[indice_aba]:
    st.subheader("📊 Relatório Diário")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        dt_f = st.date_input("Data", value=data_f_global, key="data_relatorio")
    with c2:
        lista_turmas_gestao = ["Todas"]
        if not df_alunos.empty:
            lista_turmas_gestao += sorted(df_alunos['turma'].unique())
        index_turma = 0
        if tf != "Todas" and tf in lista_turmas_gestao:
            index_turma = lista_turmas_gestao.index(tf)
        t_f_gestao = st.selectbox("Turma (Frequência)", lista_turmas_gestao, index=index_turma, key="filtro_turma_gestao")
    with c3:
        s_f = st.selectbox("Status", ["TODOS", "PRESENTES", "AUSENTES", "COM ATRASO", "FALTA JUSTIFICADA"], key="filtro_status_gestao")
    with c4:
        b_f = st.text_input("Buscar Nome", key="busca_nome_gestao")

    params = [dt_f.strftime("%Y-%m-%d")]
    query = """
        SELECT a.codigo, a.nome, a.turma,
               CASE
                   WHEN r.tipo_registro = 'FALTA' AND r.motivo_saida IS NOT NULL THEN 'FALTA JUSTIFICADA'
                   WHEN r.tipo_registro = 'PRESENCA' AND r.status_entrada = 'ATRASO' THEN 'PRESENCA COM ATRASO'
                   ELSE COALESCE(r.tipo_registro, 'NÃO REGISTRADO (AUSENTE)')
               END as status_exibicao,
               r.hora_entrada,
               r.status_entrada,
               r.hora_saida,
               r.motivo_saida
        FROM alunos_v2 a
        LEFT JOIN registros_v2 r ON a.codigo = r.codigo_aluno AND r.data = %s
        WHERE a.status = 'ATIVO'
    """
    if t_f_gestao != "Todas":
        query += " AND a.turma = %s"
        params.append(t_f_gestao)

    if s_f == "PRESENTES":
        query += " AND r.tipo_registro = 'PRESENCA'"
    elif s_f == "AUSENTES":
        query += " AND (r.tipo_registro = 'FALTA' OR r.tipo_registro IS NULL)"
    elif s_f == "COM ATRASO":
        query += " AND r.tipo_registro = 'PRESENCA' AND r.status_entrada = 'ATRASO'"
    elif s_f == "FALTA JUSTIFICADA":
        query += " AND r.tipo_registro = 'FALTA' AND r.motivo_saida IS NOT NULL"

    if b_f:
        query += " AND a.nome ILIKE %s"
        params.append(f"%{b_f}%")

    query += " ORDER BY a.turma, a.nome"

    conn = conectar_bd()
    if conn:
        try:
            df_relatorio = pd.read_sql_query(query, conn, params=params)
            df_relatorio.rename(columns={'status_exibicao': 'Status'}, inplace=True)
            
            total = len(df_relatorio)
            presentes = len(df_relatorio[df_relatorio['Status'] == 'PRESENCA'])
            com_atraso = len(df_relatorio[df_relatorio['Status'] == 'PRESENCA COM ATRASO'])
            falta_justificada = len(df_relatorio[df_relatorio['Status'] == 'FALTA JUSTIFICADA'])
            ausentes = len(df_relatorio[df_relatorio['Status'] == 'NÃO REGISTRADO (AUSENTE)'])
            falta_sem_justificativa = len(df_relatorio[df_relatorio['Status'] == 'FALTA'])
            
            col1, col2, col3, col4, col5, col6 = st.columns(6)
            col1.metric("Total", total)
            col2.metric("✅ Presentes", presentes)
            col3.metric("⏰ Com Atraso", com_atraso)
            col4.metric("📝 Falta Justificada", falta_justificada)
            col5.metric("❌ Ausentes", ausentes)
            col6.metric("🚫 Falta s/ Justif.", falta_sem_justificativa)
            
            st.markdown("---")
            st.dataframe(df_relatorio, use_container_width=True, hide_index=True)
        except Exception as e:
            st.info(f"Sem dados para exibir no momento. {e}")
        finally:
            liberar_conn(conn)
    else:
        st.error("Sem conexão com o banco de dados.")
indice_aba += 1


# ================================================================
# COMUNICAÇÃO DE FALTA — WHATSAPP WEB
# ================================================================
if aba_atual == abas_do_sistema[indice_aba]:
    st.title("📱 Comunicação de Falta")
    st.info(
        f"Os estudantes listados abaixo não possuem registro de presença "
        f"na data selecionada ({data_f_global.strftime('%d/%m/%Y')}). "
        "O botão abre o WhatsApp Web com a mensagem já preparada."
    )

    data_comunicacao = data_f_global.strftime("%Y-%m-%d")
    turma_comunicacao = tf

    conn_com = conectar_bd()
    df_faltosos_com = pd.DataFrame()

    if conn_com:
        try:
            params_com = [data_comunicacao]
            query_com = """
                SELECT
                    a.codigo,
                    a.nome,
                    a.turma,
                    a.telefone_responsavel,
                    r.motivo_saida
                FROM alunos_v2 a
                LEFT JOIN registros_v2 r
                    ON a.codigo = r.codigo_aluno
                    AND r.data = %s
                    AND r.tipo_registro = 'FALTA'
                WHERE a.status = 'ATIVO'
                  AND a.codigo NOT IN (
                      SELECT codigo_aluno
                      FROM registros_v2
                      WHERE data = %s
                        AND tipo_registro = 'PRESENCA'
                  )
            """
            params_com.append(data_comunicacao)

            if turma_comunicacao != "Todas":
                query_com += " AND a.turma = %s"
                params_com.append(turma_comunicacao)

            query_com += " ORDER BY a.turma, a.nome"

            df_faltosos_com = pd.read_sql_query(
                query_com,
                conn_com,
                params=params_com
            )
        except Exception as e:
            st.error(f"Não foi possível carregar os estudantes faltosos: {e}")
        finally:
            liberar_conn(conn_com)

    if df_faltosos_com.empty:
        st.success("✅ Nenhum estudante faltoso encontrado para os filtros selecionados.")
    else:
        total_faltosos_com = len(df_faltosos_com)
        total_com_whatsapp = int(
            df_faltosos_com["telefone_responsavel"]
            .fillna("")
            .astype(str)
            .apply(normalizar_telefone_whatsapp)
            .ne("")
            .sum()
        )
        total_sem_whatsapp = total_faltosos_com - total_com_whatsapp

        c_com1, c_com2, c_com3 = st.columns(3)
        c_com1.metric("❌ Faltosos", total_faltosos_com)
        c_com2.metric("📱 Com WhatsApp", total_com_whatsapp)
        c_com3.metric("⚠️ Sem WhatsApp", total_sem_whatsapp)

        st.markdown("---")

        for idx, row in enumerate(df_faltosos_com.to_dict("records"), start=1):
            nome_f = str(row.get("nome") or "").strip()
            turma_f = str(row.get("turma") or "").strip()
            telefone_f = normalizar_telefone_whatsapp(
                row.get("telefone_responsavel", "")
            )
            motivo_f = str(row.get("motivo_saida") or "").strip()

            col_nome, col_status, col_acao = st.columns([4, 2, 2])

            with col_nome:
                st.markdown(
                    f"**{idx}. {nome_f}**  \n"
                    f"Turma: **{turma_f}**"
                )

            with col_status:
                if motivo_f:
                    st.warning(f"Falta registrada: {motivo_f}")
                else:
                    st.error("Falta sem justificativa")

            with col_acao:
                if telefone_f:
                    mensagem_f = mensagem_falta_whatsapp(
                        nome_f,
                        data_comunicacao
                    )
                    link_f = gerar_link_whatsapp(
                        telefone_f,
                        mensagem_f
                    )
                    if link_f:
                        st.link_button(
                            "📱 ENVIAR WHATSAPP",
                            link_f,
                            use_container_width=True
                        )
                    else:
                        st.warning("Número inválido")
                else:
                    st.warning("Sem WhatsApp cadastrado")

            st.markdown("---")

    st.markdown("## ⛔ Suspensões disciplinares")
    st.caption("Estudantes com suspensão vigente na data selecionada. A comunicação pode ser encaminhada pelo WhatsApp.")
    df_susp_com = buscar_suspensoes_na_data(data_comunicacao, turma_comunicacao)
    if df_susp_com.empty:
        st.info("Nenhuma suspensão vigente para os filtros selecionados.")
    else:
        for _, row_susp in df_susp_com.iterrows():
            nome_susp = str(row_susp.get("nome") or "").strip()
            turma_susp = str(row_susp.get("turma") or "").strip()
            telefone_susp = normalizar_telefone_whatsapp(row_susp.get("telefone_responsavel", ""))
            motivo_susp_com = str(row_susp.get("motivo") or "").strip()
            try:
                inicio_susp = pd.to_datetime(row_susp.get("data_inicio")).strftime("%d/%m/%Y")
                fim_susp = pd.to_datetime(row_susp.get("data_fim")).strftime("%d/%m/%Y")
            except Exception:
                inicio_susp = str(row_susp.get("data_inicio") or "")
                fim_susp = str(row_susp.get("data_fim") or "")

            c_sc1, c_sc2 = st.columns([4, 2])
            with c_sc1:
                st.markdown(
                    f"**⛔ {nome_susp}**  \n"
                    f"Código: **{row_susp.get('codigo')}** • Turma: **{turma_susp}**  \n"
                    f"Período: **{inicio_susp} a {fim_susp}**  \n"
                    f"Motivo: **{motivo_susp_com}**"
                )
            with c_sc2:
                if telefone_susp:
                    link_susp = gerar_link_whatsapp(
                        telefone_susp,
                        mensagem_suspensao_whatsapp(
                            nome_susp,
                            row_susp.get("data_inicio"),
                            row_susp.get("data_fim"),
                            motivo_susp_com,
                        ),
                    )
                    if link_susp:
                        st.link_button("📱 ENVIAR SUSPENSÃO", link_susp, use_container_width=True)
                else:
                    st.warning("Sem WhatsApp cadastrado")
            st.markdown("---")

indice_aba += 1

# ================================================================
# PAINEL INFORMATIVO — versão integrada ao menu autenticado
# ================================================================
if aba_atual == abas_do_sistema[indice_aba]:
    renderizar_painel_informativo_publico()

indice_aba += 1

# ------------------------------------------------------------
# DEMAIS ABAS (Risco de Evasão, Histórico de Frequência, Desempenho, Satisfação, Manutenção)
# ------------------------------------------------------------
if aba_atual == abas_do_sistema[indice_aba]:
    st.subheader("🚨 Risco de Evasão — alunos com 5 dias ausentes")
    dias_u = [(obter_hora_atual() - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7) if (obter_hora_atual() - timedelta(days=i)).weekday() < 5][:5]
    
    if dias_u:
        conn = conectar_bd()
        if conn:
            try:
                df_risco = pd.read_sql_query("SELECT a.codigo, a.nome, a.turma FROM alunos_v2 a WHERE a.status = 'ATIVO' AND a.codigo NOT IN (SELECT DISTINCT codigo_aluno FROM registros_v2 WHERE data IN %s AND tipo_registro='PRESENCA')", conn, params=[tuple(dias_u)])
                if not df_risco.empty: 
                    st.error(f"{len(df_risco)} alunos em risco")
                    st.dataframe(df_risco, hide_index=True)
                else: 
                    st.success("Nenhum aluno ativo nesta situação.")
            except: 
                st.info("Aguardando...")
            finally: 
                liberar_conn(conn)
indice_aba += 1

if aba_atual == abas_do_sistema[indice_aba]:
    st.subheader("📈 Histórico Individual")

    lista_historico = [""]
    if not df_alunos.empty:
        lista_historico += [
            f"{r['codigo']} - {r['nome']} ({r['turma']}) - {r['status']}"
            for _, r in df_alunos.iterrows()
        ]

    aluno_sel = st.selectbox(
        "Selecione o aluno",
        lista_historico,
        key="historico_aluno",
    )

    if aluno_sel:
        codigo_historico = aluno_sel.split(" - ")[0]

        conn = conectar_bd()

        if conn:
            try:
                # A tabela de calendário é usada para representar também os dias
                # em que o aluno não possui uma linha em registros_v2. Isso evita
                # que faltas não justificadas "desapareçam" do histórico.
                query_hist = """
                    WITH dias AS (
                        SELECT data
                        FROM calendario_letivo
                        WHERE dia_letivo = TRUE
                          AND data <= CURRENT_DATE

                        UNION

                        SELECT data
                        FROM registros_v2
                        WHERE codigo_aluno = %s
                          AND data <= CURRENT_DATE
                    )
                    SELECT
                        d.data,
                        CASE
                            WHEN r.tipo_registro = 'PRESENCA'
                                 AND r.status_entrada = 'ATRASO'
                                THEN 'PRESENÇA COM ATRASO'
                            WHEN r.tipo_registro = 'PRESENCA'
                                THEN 'PRESENTE'
                            WHEN r.tipo_registro = 'FALTA'
                                 AND r.motivo_saida IS NOT NULL
                                THEN 'FALTA JUSTIFICADA'
                            WHEN r.tipo_registro = 'FALTA'
                                THEN 'FALTA'
                            ELSE
                                'AUSENTE SEM REGISTRO'
                        END AS status,
                        r.hora_entrada,
                        r.hora_saida,
                        r.motivo_saida
                    FROM dias d
                    LEFT JOIN registros_v2 r
                      ON r.codigo_aluno = %s
                     AND r.data = d.data
                    ORDER BY d.data DESC
                """

                df_hist = pd.read_sql_query(
                    query_hist,
                    conn,
                    params=[
                        codigo_historico,
                        codigo_historico,
                    ],
                )

                if df_hist.empty:
                    st.info(
                        "Ainda não existem dias letivos ou registros "
                        "disponíveis para este estudante."
                    )
                else:
                    # Indicadores rápidos do histórico.
                    total_dias = len(df_hist)
                    presentes_hist = int(
                        df_hist["status"]
                        .isin(
                            [
                                "PRESENTE",
                                "PRESENÇA COM ATRASO",
                            ]
                        )
                        .sum()
                    )
                    atrasos_hist = int(
                        (
                            df_hist["status"]
                            == "PRESENÇA COM ATRASO"
                        ).sum()
                    )
                    faltas_hist = int(
                        df_hist["status"]
                        .isin(
                            [
                                "FALTA",
                                "FALTA JUSTIFICADA",
                                "AUSENTE SEM REGISTRO",
                            ]
                        )
                        .sum()
                    )
                    justificadas_hist = int(
                        (
                            df_hist["status"]
                            == "FALTA JUSTIFICADA"
                        ).sum()
                    )

                    h1, h2, h3, h4, h5 = st.columns(5)
                    h1.metric("📅 Dias letivos", total_dias)
                    h2.metric("✅ Presenças", presentes_hist)
                    h3.metric("⏰ Atrasos", atrasos_hist)
                    h4.metric("❌ Faltas", faltas_hist)
                    h5.metric(
                        "📝 Justificadas",
                        justificadas_hist,
                    )

                    st.markdown("---")

                    df_hist_exib = df_hist.rename(
                        columns={
                            "data": "Data",
                            "status": "Situação",
                            "hora_entrada": "Hora de Entrada",
                            "hora_saida": "Hora de Saída",
                            "motivo_saida": "Motivo",
                        }
                    )

                    st.dataframe(
                        df_hist_exib,
                        use_container_width=True,
                        hide_index=True,
                    )

                    st.markdown("### ⛔ Suspensões disciplinares")
                    df_susp_hist = carregar_suspensoes_aluno(codigo_historico)
                    if df_susp_hist.empty:
                        st.info("Nenhuma suspensão disciplinar registrada para este estudante.")
                    else:
                        df_susp_hist_exib = df_susp_hist.copy()
                        df_susp_hist_exib["data_inicio"] = pd.to_datetime(df_susp_hist_exib["data_inicio"], errors="coerce").dt.strftime("%d/%m/%Y")
                        df_susp_hist_exib["data_fim"] = pd.to_datetime(df_susp_hist_exib["data_fim"], errors="coerce").dt.strftime("%d/%m/%Y")
                        df_susp_hist_exib = df_susp_hist_exib.rename(
                            columns={"data_inicio": "Início", "data_fim": "Fim", "motivo": "Motivo"}
                        )[["Início", "Fim", "Motivo"]]
                        st.dataframe(df_susp_hist_exib, use_container_width=True, hide_index=True)

            except Exception as e:
                st.warning(
                    f"Erro ao carregar histórico: {e}"
                )
            finally:
                liberar_conn(conn)

indice_aba += 1

if aba_atual == abas_do_sistema[indice_aba]:
    st.title("📊 Desempenho Acadêmico")
    st.info("💡 **Atenção:** Os dados exibidos nesta aba obedecem aos Filtros Globais selecionados no topo da tela (Ano, Período, Área e Turma).")
    
    sub_da = ["🏆 Destaques", "🧑‍🎓 Estudantes", "🚫 Faltosos na Prova", "📈 Gráficos", "📋 Questões Críticas", "📝 Faltou 1ª Chamada"]
    stabs = st.tabs(sub_da)
    
    alertas_estudante, area_stats = obter_estatisticas_areas_cached(ano_f, pf, af, tf)
    
    with stabs[0]:
        if not dff.empty:
            top7 = obter_top7_cached(ano_f, pf, af, tf)
            for idx, r in enumerate(top7.to_dict('records')):
                if eh_admin: 
                    rev = st.toggle("Revelar", key=f"rev_{idx}")
                else: 
                    rev = False
                    
                if idx == 0:
                    medalha = "🥇 1º LUGAR"
                elif idx == 1:
                    medalha = "🥈 2º LUGAR"
                elif idx == 2:
                    medalha = "🥉 3º LUGAR"
                else:
                    medalha = f"⭐ {idx+1}º LUGAR"
                    
                if rev:
                    classe_nome = "top7-name"
                    texto_nome = f"{r['nome']} ({r['turma']})"
                else:
                    classe_nome = "top7-name-hidden"
                    texto_nome = "OCULTO"
                    
                st.markdown(f'<div class="top7-card"><div class="top7-medal">{medalha}</div><div class="{classe_nome}">{texto_nome}</div><div class="top7-details">NOTA (FILTRADA): {r["acerto"]*10:.2f} | {r["turma"]}</div></div>', unsafe_allow_html=True)
    
    with stabs[1]:
        if not dff.empty:
            st.markdown("#### ⚙️ Filtros do Boletim do Estudante")
            c_est1, c_est2, c_est3, c_est4 = st.columns([2, 1, 1, 1])
            with c_est1: 
                bus_al = st.text_input("Buscar Nome:", key="busca_nome_est")
            with c_est2: 
                filtro_desempenho = st.selectbox("Desempenho:", ["Todos", "INSUFICIENTE", "BOM", "ÓTIMO"], key="filtro_desempenho_est")
            with c_est3: 
                ordenar_por = st.selectbox("Ordenar por:", ["Alfabética", "Maior Nota", "Menor Nota"], key="ordenar_est")
            with c_est4: 
                st.markdown("<br>", unsafe_allow_html=True)
                filtro_erros = st.checkbox("Somente c/ erros", key="filtro_erros_est")

            res_al, erros_n = obter_resumo_estudantes_cached(ano_f, pf, af, tf)
            
            if bus_al: 
                res_al = res_al[res_al['nome'].str.contains(bus_al.upper())]
            if filtro_erros: 
                res_al = res_al[res_al['nome'].isin(erros_n)]
                
            if filtro_desempenho == "INSUFICIENTE": 
                res_al = res_al[res_al['acerto']*10 < 6.0]
            elif filtro_desempenho == "BOM": 
                res_al = res_al[(res_al['acerto']*10 >= 6.0) & (res_al['acerto']*10 <= 7.5)]
            elif filtro_desempenho == "ÓTIMO": 
                res_al = res_al[res_al['acerto']*10 > 7.5]

            if ordenar_por == "Maior Nota": 
                res_al = res_al.sort_values(by=['acerto', 'nome'], ascending=[False, True])
            elif ordenar_por == "Menor Nota": 
                res_al = res_al.sort_values(by=['acerto', 'nome'], ascending=[True, True])
            else: 
                res_al = res_al.sort_values(by='nome')

            total_estudantes_avaliados = len(res_al)
            filtros_ativos = (tf != "Todas") or (pf != "Todos") or (af != "Todas") or bool(bus_al) or filtro_erros or (filtro_desempenho != "Todos") or (ordenar_por != "Alfabética")
            
            lista_completa = res_al.to_dict('records')
            
            if filtros_ativos:
                lista_visualizacao = lista_completa
            else:
                lista_visualizacao = res_al.head(20).to_dict('records')
            
            st.markdown("---")
            gerar_em_lote = st.checkbox("📦 Gerar todos os boletins listados acima em lote (Arquivo ZIP)", key="chk_lote")
            
            if gerar_em_lote:
                st.warning(f"Você está prestes a gerar **{len(lista_completa)} boletins** de uma só vez.")
                zip_key = f"zip_{ano_f}_{pf}_{af}_{tf}_{bus_al}_{filtro_desempenho}_{filtro_erros}_{ordenar_por}"
                
                if st.button("⚙️ PROCESSAR BOLETINS EM LOTE", type="primary"):
                    with st.spinner(f"Gerando {len(lista_completa)} boletins. Por favor, aguarde..."):
                        zip_buffer = io.BytesIO()
                        df_historico_base = obter_dados_acad_filtrados(ano_f, "Todos", "Todas", "Todas")
                        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                            for a in lista_completa:
                                df_bol_ind = dff[dff['nome'] == a['nome']]
                                df_historico_aluno = df_historico_base[df_historico_base['nome'] == a['nome']]
                                codigo_a = obter_codigo_aluno_df(a['nome'], a['turma'], df_alunos)
                                df_freq_a = carregar_historico_frequencia_aluno(codigo_a)
                                df_susp_a = carregar_suspensoes_aluno(codigo_a)
                                pdf_bytes = gerar_pdf_boletim(a['nome'], a['turma'], a['acerto']*10, df_bol_ind, df_historico_aluno, df_freq_a, df_susp_a)
                                
                                if pdf_bytes:
                                    safe_name = "".join([c for c in a['nome'] if c.isalpha() or c.isdigit() or c==' ']).rstrip()
                                    zip_file.writestr(f"Boletim_{a['turma']}_{safe_name}.pdf", pdf_bytes)
                                    
                        st.session_state[zip_key] = zip_buffer.getvalue()
                        
                if zip_key in st.session_state:
                    st.success("✅ Arquivo ZIP gerado com sucesso!")
                    st.download_button("📥 BAIXAR ARQUIVO ZIP COM OS BOLETINS", data=st.session_state[zip_key], file_name=f"Boletins_{tf.replace(' ', '_')}_{ano_f}.zip", mime="application/zip")
            else:
                if not filtros_ativos: 
                    st.info(f"📊 **Total de estudantes avaliados:** {total_estudantes_avaliados} (Exibindo os 20 primeiros).")
                else: 
                    st.info(f"📊 **Total de estudantes encontrados:** {len(lista_visualizacao)}.")
                
                df_historico_base = obter_dados_acad_filtrados(ano_f, "Todos", "Todas", "Todas")
                
                if not dff.empty:
                    medias_gerais_turma = dff.groupby(['nome', 'disciplina', 'periodo']).agg(Nota=('acerto', lambda x: (sum(x)/len(x))*10)).reset_index()
                    piores_por_aluno = medias_gerais_turma.sort_values(['nome', 'Nota']).groupby('nome').head(3)
                else:
                    piores_por_aluno = pd.DataFrame(columns=['nome', 'disciplina', 'periodo', 'Nota'])
                
                for idx, a in enumerate(lista_visualizacao, start=1):
                    alerta_str = alertas_estudante.get(a['nome'], "")
                    if alerta_str:
                        tag = f" &nbsp; 🚨 [{alerta_str}]"
                    else:
                        tag = ""
                        
                    with st.expander(f"👤 {idx}º | {a['nome']} ({a['turma']}) | Nota: {a['acerto']*10:.2f} {tag}"):
                        
                        df_bol_ind = dff[dff['nome'] == a['nome']]
                        df_historico_aluno = df_historico_base[df_historico_base['nome'] == a['nome']]
                        
                        piores_3 = piores_por_aluno[piores_por_aluno['nome'] == a['nome']]
                        piores_str = " &nbsp;&nbsp;|&nbsp;&nbsp; ".join([f"📉 <span style='color:#ef4444; font-weight:900;'>{r['disciplina']} ({r['Nota']:.1f})</span>" for _, r in piores_3.iterrows()])
                        
                        if not piores_3.empty: 
                            st.markdown(f"<div style='margin-bottom: 15px; padding: 10px; background-color: #fef2f2; border-left: 5px solid #ef4444; border-radius: 5px; font-size: 1.1rem;'><b>Atenção - Menores Notas:</b> {piores_str}</div>", unsafe_allow_html=True)
                        
                        if st.button("GERAR PDF (PERÍODO SELECIONADO)", key=f"pdf_{idx}_{a['nome']}"):
                            codigo_a = obter_codigo_aluno_df(a['nome'], a['turma'], df_alunos)
                            df_freq_a = carregar_historico_frequencia_aluno(codigo_a)
                            df_susp_a = carregar_suspensoes_aluno(codigo_a)
                            b_pdf = gerar_pdf_boletim(a['nome'], a['turma'], a['acerto']*10, df_bol_ind, df_historico_aluno, df_freq_a, df_susp_a)
                            if b_pdf: 
                                st.download_button("BAIXAR BOLETIM", b_pdf, f"Boletim_{a['nome']}.pdf")
                            else: 
                                st.error("Erro ao gerar PDF.")
                            
                        st.markdown(f"#### 📈 Evolução ao Longo do Ano ({ano_f})")
                        progresso = df_historico_aluno.groupby(['periodo', 'disciplina']).agg(Acertos=('acerto', 'sum'), Total=('questao', 'count')).reset_index()
                        progresso['Nota'] = (progresso['Acertos'] / progresso['Total']) * 10
                        try: 
                            st.line_chart(progresso.pivot(index='periodo', columns='disciplina', values='Nota'), height=250)
                        except: 
                            pass
                        
                        st.markdown("#### 📊 Médias por Disciplina (Filtros Atuais)")
                        medias_b = df_bol_ind.groupby(['disciplina', 'periodo']).agg(Nota=('acerto', lambda x: (sum(x)/len(x))*10)).reset_index()
                        for _, mb in medias_b.iterrows(): 
                            st.write(f"{mb['disciplina'].upper()} - {mb['periodo']} (Nota: {mb['Nota']:.1f})")
                            st.progress(min(mb['Nota'] / 10, 1.0))
                        
                        st.markdown("#### 📋 Mapa de Questões (Filtros Atuais)")
                        for p_m in sorted(df_bol_ind['periodo'].unique()):
                            for d_m in sorted(df_bol_ind[df_bol_ind['periodo']==p_m]['disciplina'].unique()):
                                st.markdown(f"**{d_m} - {p_m}**")
                                q_df = df_bol_ind[(df_bol_ind['periodo']==p_m) & (df_bol_ind['disciplina']==d_m)].sort_values("questao")
                                grid = '<div style="display: flex; flex-wrap: wrap; gap: 8px;">'
                                
                                for _, q in q_df.iterrows():
                                    if q['acerto'] == 1:
                                        cor = "#10b981"
                                    elif q['resposta'] == 'BRANCO':
                                        cor = "#f59e0b"
                                    elif q['resposta'] == 'DUPLA':
                                        cor = "#8b5cf6"
                                    else:
                                        cor = "#ef4444"
                                        
                                    grid += f'<div style="background:{cor}; color:white; padding:8px; border-radius:6px; width:75px; text-align:center; font-size:11px;">Q{q["questao"]}<br>R:{q["resposta"]} G:{q["gabarito"]}</div>'
                                    
                                st.markdown(grid+'</div><br>', unsafe_allow_html=True)
                            
    with stabs[2]:
        if not dff.empty and not area_stats.empty:
            estudantes_faltosos = area_stats[area_stats['Faltou']]
            
            if not estudantes_faltosos.empty:
                st.error(f"⚠️ **REGISTO DE FALTAS NA PROVA ({len(estudantes_faltosos)})**")
                cols_f = st.columns(3)
                for i, r_f in enumerate(estudantes_faltosos.to_dict('records')): 
                    cols_f[i % 3].markdown(f"🚫 **{r_f['nome']}** ({r_f['turma']}) <br> <span style='color:#ef4444;'>Falta em: **{r_f['area']}** ({r_f['periodo']})</span>", unsafe_allow_html=True)
            else: 
                st.success("✨ Nenhum estudante faltou na avaliação selecionada.")

    with stabs[3]:
        if not dff.empty:
            tipo_grafico = st.radio("Agrupar por:", ["Área", "Disciplina"], horizontal=True)
            if tipo_grafico == "Área":
                col_agrup = 'area'
            else:
                col_agrup = 'disciplina'
                
            for p in sorted(dff['periodo'].unique()):
                st.markdown(f"#### 📊 Desempenho: {p}")
                resumo_graf = dff[dff['periodo'] == p].groupby(col_agrup).agg(Acertos=('acerto', 'sum'), Total=('questao', 'count')).reset_index()
                resumo_graf['Nota'] = (resumo_graf['Acertos'] / resumo_graf['Total']) * 10
                
                if tipo_grafico == "Área":
                    resumo_graf['Abreviacao'] = resumo_graf['area'].str.upper()
                else:
                    resumo_graf['Abreviacao'] = resumo_graf['disciplina'].apply(lambda x: DICIONARIO_ABREVIACAO.get(x.upper(), x[:4].upper()))
                    
                resumo_graf['Nome Completo'] = resumo_graf[col_agrup].str.upper()
                
                fig_g = px.bar(
                    resumo_graf.sort_values('Nota'), 
                    x='Abreviacao', y='Nota', color='Abreviacao', 
                    text='Nota', hover_data={'Nome Completo': True, 'Nota': ':.2f', 'Abreviacao': False},
                    color_discrete_map=DICIONARIO_CORES
                )
                fig_g.update_traces(texttemplate='%{text:.1f}', textposition='outside')
                fig_g.update_layout(yaxis=dict(range=[0, 11]), plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', showlegend=False)
                st.plotly_chart(fig_g, use_container_width=True, key=f"grafico_{p}_{tipo_grafico}")

    with stabs[4]:
        if not dff.empty:
            st.subheader("❌ Top 3 Erros (Por Matéria e Turma)")
            q_err_top3 = obter_top3_erros_cached(ano_f, pf, af, tf)
            
            if not q_err_top3.empty:
                pdf_data = gerar_pdf_relatorio_critico(q_err_top3)
                if pdf_data: 
                    st.download_button("📥 BAIXAR RELATÓRIO EM PDF", data=pdf_data, file_name="Questoes_Criticas.pdf", mime="application/pdf")
                    
                st.markdown("---")
                for t in sorted(q_err_top3['turma'].unique()):
                    st.markdown(f"### 🏫 Turma: **{t}**")
                    df_t = q_err_top3[q_err_top3['turma'] == t]
                    
                    for p in sorted(df_t['periodo'].unique()):
                        st.markdown(f"#### 📅 Período: **{p}**")
                        df_p = df_t[df_t['periodo'] == p]
                        
                        for d in sorted(df_p['disciplina'].unique()):
                            st.markdown(f"- **{d}**")
                            for _, r in df_p[df_p['disciplina'] == d].iterrows(): 
                                st.write(f"  - Questão {r['questao']} (Erro: **{r['Taxa de Erro (%)']:.1f}%**)")
                                
                        st.markdown("<br>", unsafe_allow_html=True)
                    st.markdown("---")
            else: 
                st.success("Não foram detectados erros de marcação para estes filtros!")
            
    with stabs[5]:
        st.markdown("#### 📝 Histórico de Faltas na 1ª Chamada")
        st.write(f"Visualizando dados do Ano Letivo: **{ano_f}**")
        df_faltas_1a = carregar_faltas_primeira_chamada(ano_f)
        
        if pf != "Todos" and not df_faltas_1a.empty:
            df_faltas_1a = df_faltas_1a[df_faltas_1a['periodo'] == pf]
            
        if af != "Todas" and not df_faltas_1a.empty:
            df_faltas_1a = df_faltas_1a[df_faltas_1a['area'] == af]
            
        if tf != "Todas" and not df_faltas_1a.empty:
            df_faltas_1a = df_faltas_1a[df_faltas_1a['turma'] == tf]
        
        if df_faltas_1a.empty:
            st.success(f"🎉 Nenhum registro de falta na 1ª chamada encontrado para os filtros atuais!")
        else:
            st.dataframe(df_faltas_1a, use_container_width=True, hide_index=True)
indice_aba += 1

if aba_atual == abas_do_sistema[indice_aba]:
    st.title("💬 Análise de Satisfação da Comunidade")
    st.info(f"💡 **Dica:** Os dados exibidos obedecem ao Ano Global selecionado no topo ({ano_f}) e à Turma (para Estudantes).")
    
    df_sat_ano = carregar_satisfacao_por_ano(ano_f)
    
    if df_sat_ano.empty:
        st.warning(f"Nenhuma avaliação registrada para o ano de {ano_f}.")
    else:
        cat_sat = st.selectbox("Selecione o Segmento para Análise Gráfica:", ["Todos", "Estudante", "Pais/Responsável", "Professor", "Servidor"], key="filtro_cat_sat")
        
        df_sat_filtrado = df_sat_ano.copy()
        if cat_sat != "Todos": 
            df_sat_filtrado = df_sat_filtrado[df_sat_filtrado['categoria'] == cat_sat]
            
        if cat_sat in ["Todos", "Estudante"] and tf != "Todas": 
            df_sat_filtrado = df_sat_filtrado[df_sat_filtrado['turma'] == tf]
            
        if df_sat_filtrado.empty:
            st.info("Nenhum dado encontrado para os filtros selecionados.")
        else:
            nomes_perguntas = DICIONARIO_PERGUNTAS_SATISFACAO[cat_sat]
            df_grafico_sat = pd.DataFrame({
                'Pergunta': nomes_perguntas,
                'Média (Max 5)': [df_sat_filtrado['q1'].mean(), df_sat_filtrado['q2'].mean(), df_sat_filtrado['q3'].mean(), df_sat_filtrado['q4'].mean(), df_sat_filtrado['q5'].mean()]
            })
            
            fig_sat = px.bar(df_grafico_sat, x='Pergunta', y='Média (Max 5)', text='Média (Max 5)', color='Pergunta', title=f"Média de Satisfação: {cat_sat}")
            fig_sat.update_traces(texttemplate='%{text:.2f}', textposition='outside')
            fig_sat.update_layout(yaxis=dict(range=[0, 5.5]), plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', showlegend=False)
            st.plotly_chart(fig_sat, use_container_width=True)

            st.markdown("---")
            st.subheader("📝 Mural de Sugestões e Feedbacks")
            df_sugestoes = df_sat_filtrado[df_sat_filtrado['sugestao'].notna() & (df_sat_filtrado['sugestao'].str.strip() != "")]
            
            if df_sugestoes.empty: 
                st.success("Não há sugestões em texto para este grupo.")
            else:
                for _, sug in df_sugestoes.iterrows():
                    data_str = sug['data_hora'].strftime("%d/%m/%Y %H:%M")
                    if sug['turma']:
                        turma_str = f" ({sug['turma']})"
                    else:
                        turma_str = ""
                        
                    st.info(f"**Data:** {data_str} | **Perfil:** {sug['categoria']}{turma_str}\n\n**Mensagem:** {sug['sugestao']}")
indice_aba += 1

if eh_admin:
    if aba_atual == abas_do_sistema[indice_aba]:
        st.subheader("📝 Registrar Falta na 1ª Chamada de Avaliação")
        with st.form("form_falta_1a", clear_on_submit=True):
            c_f1, c_f2, c_f3 = st.columns([1, 1, 2])
            with c_f1: 
                f1_ano = st.selectbox("Ano Letivo", anos_disponiveis, index=anos_disponiveis.index(ano_atual))
            with c_f2: 
                f1_per = st.selectbox("Período Acadêmico", ["1º Período", "2º Período", "3º Período", "4º Período"])
            with c_f3: 
                f1_area = st.selectbox("Área Acadêmica", ["LÍNGUA PORTUGUESA", "MATEMÁTICA", "LINGUAGENS", "HUMANAS", "NATUREZA"])
            
            lista_alunos_falta = [""]
            if not df_alunos.empty:
                lista_alunos_falta += [f"{r['codigo']} - {r['nome']} ({r['turma']})" for _, r in df_alunos.iterrows()]
                
            f1_aluno = st.selectbox("Selecione o Estudante", lista_alunos_falta)
            f1_motivo = st.selectbox("Motivo da Falta / Justificativa", MOTIVOS_JUSTIFICATIVA)
            
            if st.form_submit_button("💾 SALVAR REGISTRO DE FALTA"):
                if f1_aluno:
                    cod_aluno = f1_aluno.split(" - ")[0]
                    conn_f1 = conectar_bd()
                    if conn_f1:
                        try:
                            cur_f1 = conn_f1.cursor()
                            cur_f1.execute("""
                                INSERT INTO faltas_primeira_chamada (codigo_aluno, ano, periodo, area, motivo) 
                                VALUES (%s, %s, %s, %s, %s) 
                                ON CONFLICT (codigo_aluno, ano, periodo, area) 
                                DO UPDATE SET motivo = EXCLUDED.motivo, data_registro = CURRENT_TIMESTAMP
                            """, (cod_aluno, f1_ano, f1_per, f1_area, f1_motivo))
                            conn_f1.commit()
                            carregar_faltas_primeira_chamada.clear()
                            st.success(f"Falta na 1ª chamada de {f1_area} registrada com sucesso para {f1_aluno.split(' - ')[1]}!")
                        except Exception as e: 
                            st.error(f"Erro ao salvar: {e}")
                        finally: 
                            liberar_conn(conn_f1)
                    else: 
                        st.error("Sem conexão com o banco de dados.")
                else: 
                    st.error("Por favor, selecione um estudante na lista.")
                    
        st.markdown("---")
        
        st.subheader("🔗 Link da Pesquisa de Satisfação Pública")
        link_completo = f"https://seu-projeto.streamlit.app/?modo=pesquisa"
        st.code(link_completo, language="text")
        st.markdown("---")

        st.subheader("📧📱 Gerir E-mails, WhatsApp e Alunos")

        total_alunos_cadastrados = int(len(df_alunos)) if not df_alunos.empty else 0

        if not df_alunos.empty:
            emails_validos = (
                df_alunos["email_responsavel"]
                .fillna("")
                .astype(str)
                .str.strip()
            )
            total_emails_cadastrados = int((emails_validos != "").sum())
            telefones_validos = (
                df_alunos["telefone_responsavel"]
                .fillna("")
                .astype(str)
                .apply(normalizar_telefone_whatsapp)
            )
            total_telefones_cadastrados = int((telefones_validos != "").sum())
        else:
            total_emails_cadastrados = 0
            total_telefones_cadastrados = 0

        total_sem_email = max(
            total_alunos_cadastrados - total_emails_cadastrados,
            0
        )
        total_sem_telefone = max(
            total_alunos_cadastrados - total_telefones_cadastrados,
            0
        )

        c_email1, c_email2, c_email3 = st.columns(3)
        c_email1.metric("👥 Total de alunos", total_alunos_cadastrados)
        c_email2.metric("✉️ E-mails cadastrados", total_emails_cadastrados)
        c_email3.metric("⚠️ Sem e-mail", total_sem_email)

        c_tel1, c_tel2, c_tel3 = st.columns(3)
        c_tel1.metric("📱 WhatsApp cadastrados", total_telefones_cadastrados)
        c_tel2.metric("⚠️ Sem WhatsApp", total_sem_telefone)
        c_tel3.metric("📨 Contatos completos", int(min(total_emails_cadastrados, total_telefones_cadastrados)))

        st.markdown("---")

        col1, col2 = st.columns(2)
        
        with col1:
            lista_emails_aluno = [""]
            if not df_alunos.empty:
                lista_emails_aluno += [
                    f"{r['codigo']} - {r['nome']} ({r['turma']})"
                    for _, r in df_alunos.iterrows()
                ]

            al_email = st.selectbox(
                "Selecione o Aluno",
                lista_emails_aluno,
                key="selecionar_aluno_email"
            )

            codigo_email_selecionado = ""
            email_atual_responsavel = ""
            telefone_atual_responsavel = ""

            if al_email:
                codigo_email_selecionado = al_email.split(" - ")[0].strip()

                try:
                    linha_aluno_email = df_alunos[
                        df_alunos["codigo"].astype(str).str.upper()
                        == codigo_email_selecionado.upper()
                    ]

                    if not linha_aluno_email.empty:
                        valor_email = linha_aluno_email.iloc[0].get("email_responsavel", "")
                        valor_telefone = linha_aluno_email.iloc[0].get("telefone_responsavel", "")
                        if pd.notna(valor_email):
                            email_atual_responsavel = str(valor_email).strip()
                        if pd.notna(valor_telefone):
                            telefone_atual_responsavel = str(valor_telefone).strip()
                except Exception:
                    email_atual_responsavel = ""
                    telefone_atual_responsavel = ""

            novo_e = st.text_input(
                "E-mail do Responsável",
                value=email_atual_responsavel,
                key=f"campo_email_{codigo_email_selecionado or 'vazio'}"
            )

            novo_tel = st.text_input(
                "📱 WhatsApp / Celular do Responsável",
                value=telefone_atual_responsavel,
                placeholder="(98) 99999-9999",
                key=f"campo_telefone_{codigo_email_selecionado or 'vazio'}"
            )

            if email_atual_responsavel:
                st.caption("📌 E-mail atualmente cadastrado. Você pode editá-lo antes de salvar.")
            elif al_email:
                st.caption("⚠️ Este aluno ainda não possui e-mail cadastrado.")

            if telefone_atual_responsavel:
                st.caption("📌 WhatsApp atualmente cadastrado. Você pode editá-lo antes de salvar.")
            elif al_email:
                st.caption("⚠️ Este aluno ainda não possui WhatsApp/celular cadastrado.")

            if st.button(
                "SALVAR CONTATOS",
                key="salvar_contatos_responsavel"
            ) and al_email:
                conn = conectar_bd()
                if conn:
                    try:
                        cur = conn.cursor()
                        telefone_normalizado = normalizar_telefone_whatsapp(novo_tel)
                        cur.execute(
                            "UPDATE alunos_v2 SET email_responsavel=%s, telefone_responsavel=%s WHERE codigo=%s",
                            (
                                novo_e.strip().lower(),
                                telefone_normalizado or None,
                                codigo_email_selecionado
                            )
                        )
                        conn.commit()
                        _carregar_alunos_cache.clear()
                        st.success("E-mail e WhatsApp atualizados com sucesso!")
                        st.rerun()
                    except Exception as e:
                        conn.rollback()
                        st.error(f"Erro ao salvar os contatos: {e}")
                    finally:
                        liberar_conn(conn)
        
        with col2:
            st.write("Adição Manual de Aluno")
            m_cod = st.text_input("Matrícula")
            m_nom = st.text_input("Nome Completo")
            
            if not df_alunos.empty:
                lista_turmas = sorted(df_alunos['turma'].unique()) 
            else:
                lista_turmas = []
                
            m_tur_sel = st.selectbox("Selecione a Turma", ["Selecione..."] + lista_turmas + ["+ Criar Nova Turma"])
            
            if m_tur_sel == "+ Criar Nova Turma": 
                m_tur = st.text_input("Digite o nome da nova turma")
            else: 
                m_tur = m_tur_sel

            if st.button("CADASTRAR ALUNO"):
                if m_cod and m_nom and m_tur and m_tur != "Selecione...":
                    conn = conectar_bd()
                    if conn:
                        try:
                            cur = conn.cursor()
                            cur.execute("INSERT INTO alunos_v2 (codigo, nome, turma) VALUES (%s, %s, %s)", (m_cod.upper(), m_nom.upper(), m_tur.upper()))
                            conn.commit()
                            _carregar_alunos_cache.clear()
                            st.success("Cadastrado com sucesso!")
                        except Exception as e:
                            conn.rollback()
                            if "UniqueViolation" in str(type(e).__name__): 
                                st.error("⚠️ Atenção: Já existe um aluno cadastrado no sistema com esta mesma Matrícula!")
                            else: 
                                st.error(f"Erro inesperado: {e}")
                        finally: 
                            liberar_conn(conn)
                else: 
                    st.warning("Preencha todos os campos antes de cadastrar.")

        st.divider()

        st.markdown("#### 🗑️ Excluir Registro de Aluno")
        st.warning("⚠️ **ATENÇÃO:** A exclusão apagará o aluno e todo o seu histórico (frequência/notas) para evitar conflitos no banco.")
        
        c_del1, c_del2 = st.columns([3, 1])
        with c_del1: 
            lista_excluir = [""]
            if not df_alunos.empty:
                lista_excluir += [f"{r['codigo']} - {r['nome']} ({r['turma']})" for _, r in df_alunos.iterrows()]
            aluno_excluir = st.selectbox("Selecione o Aluno para exclusão definitiva", lista_excluir, key="sel_del_aluno")
            
        with c_del2: 
            st.write("")
            st.write("")
            btn_excluir = st.button("🚨 EXCLUIR ALUNO", type="primary", use_container_width=True)

        if btn_excluir and aluno_excluir:
            cod_del = aluno_excluir.split(" - ")[0]
            conn = conectar_bd()
            if conn:
                try:
                    cur = conn.cursor()
                    cur.execute("DELETE FROM registros_v2 WHERE codigo_aluno = %s", (cod_del,))
                    cur.execute("DELETE FROM faltas_primeira_chamada WHERE codigo_aluno = %s", (cod_del,))
                    cur.execute("DELETE FROM suspensoes_v1 WHERE codigo_aluno = %s", (cod_del,))
                    cur.execute("DELETE FROM alunos_v2 WHERE codigo = %s", (cod_del,))
                    conn.commit()
                    _carregar_alunos_cache.clear() 
                    st.success(f"O registro {cod_del} foi completamente excluído!")
                    time.sleep(2)
                    st.rerun()
                except Exception as e: 
                    conn.rollback()
                    st.error(f"Erro ao tentar excluir aluno: {e}")
                finally: 
                    liberar_conn(conn)

        st.divider()
        up_al = st.file_uploader("Importar Lista de Alunos (CSV)", type="csv")
        
        if st.button("PROCESSAR LISTA") and up_al:
            if importar_csv_alunos(up_al): 
                st.success("Base de Alunos Sincronizada!")
                st.rerun()

        st.markdown("---")
       
