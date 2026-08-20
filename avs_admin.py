import io
import re
import unicodedata
from datetime import datetime

import pandas as pd
import streamlit as st
import psycopg2
from psycopg2.extras import execute_values

try:
    from fpdf import FPDF
except ImportError:
    FPDF = None

PERIODOS = ["1º Período", "2º Período", "3º Período", "4º Período"]
AREAS = ["LÍNGUA PORTUGUESA", "MATEMÁTICA", "LINGUAGENS", "HUMANAS", "NATUREZA"]


def _db_url():
    url = st.secrets.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL não configurada.")
    if "sslmode" not in url:
        url += "&sslmode=require" if "?" in url else "?sslmode=require"
    return url


def conectar():
    return psycopg2.connect(_db_url(), connect_timeout=10)


def normalizar_nome_coluna(nome):
    texto = unicodedata.normalize("NFD", str(nome))
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return texto.strip().upper()


def importar_csv_avs(arquivo, ano, periodo, area, turma):
    conteudo = arquivo.getvalue()
    try:
        texto = conteudo.decode("utf-8-sig")
    except UnicodeDecodeError:
        texto = conteudo.decode("latin-1")

    sep = ";" if texto.count(";") >= texto.count(",") else ","
    df = pd.read_csv(io.StringIO(texto), sep=sep)
    df.columns = [str(c).strip() for c in df.columns]

    col_options = [c for c in df.columns if re.search(r"^Q\s*\d+\s*Options$", c, re.I)]
    if not col_options:
        col_options = [c for c in df.columns if re.search(r"^Q\s*\d+\s*Options", c, re.I)]
    if not col_options:
        return False, "Nenhuma coluna de questão 'Q Options' foi encontrada no CSV."

    col_nome = next((c for c in df.columns if normalizar_nome_coluna(c) in {"NOME", "ESTUDANTE", "STUDENT"}), None)
    if not col_nome:
        return False, "A coluna NOME/ESTUDANTE não foi encontrada no CSV."

    idx_not_attempted = next((i for i, c in enumerate(df.columns) if re.match(r"^Not\s+attempted", c, re.I)), -1)
    idx_first_q = df.columns.get_loc(col_options[0])

    disciplinas = []
    if idx_not_attempted >= 0 and idx_first_q > idx_not_attempted + 1:
        for c in df.columns[idx_not_attempted + 1:idx_first_q]:
            s = str(c).strip().upper()
            if s and not s.startswith("UNNAMED") and "AV" not in s:
                disciplinas.append(s)
    if not disciplinas:
        disciplinas = [area.upper()]

    questoes_por_disc = max(1, len(col_options) // len(disciplinas))
    dados = []

    for row in df.to_dict("records"):
        nome = str(row.get(col_nome, "")).strip()
        if not nome or nome.lower() == "nan":
            continue
        for i, col_opt in enumerate(col_options):
            match = re.search(r"Q\s*(\d+)", col_opt, re.I)
            q_num = int(match.group(1)) if match else i + 1
            d_idx = min(i // questoes_por_disc, len(disciplinas) - 1)
            resposta_bruta = row.get(col_opt)
            resposta = "BRANCO" if pd.isna(resposta_bruta) or str(resposta_bruta).strip().upper() in {"", "NAN"} else str(resposta_bruta).strip().upper()
            if len(resposta) > 1 and resposta != "BRANCO":
                resposta = "DUPLA"
            col_key = col_opt.replace("Options", "Key")
            gabarito_bruto = row.get(col_key, "")
            gabarito = "" if pd.isna(gabarito_bruto) else str(gabarito_bruto).strip().upper()
            acerto = 1 if resposta != "BRANCO" and resposta == gabarito else 0
            dados.append((str(ano), periodo, area, turma, nome.upper(), disciplinas[d_idx], q_num, resposta, gabarito, acerto))

    if not dados:
        return False, "Nenhum registro processável foi encontrado no CSV."

    conn = None
    try:
        conn = conectar()
        cur = conn.cursor()
        sql = """
            INSERT INTO avaliacoes_avs
                (ano, periodo, area, turma, nome, disciplina, questao, resposta, gabarito, acerto)
            VALUES %s
            ON CONFLICT (ano, periodo, area, turma, nome, disciplina, questao)
            DO UPDATE SET resposta=EXCLUDED.resposta,
                          gabarito=EXCLUDED.gabarito,
                          acerto=EXCLUDED.acerto
        """
        execute_values(cur, sql, dados, page_size=2000)
        conn.commit()
        return True, f"{len(dados):,} respostas importadas/atualizadas com sucesso.".replace(",", ".")
    except Exception as exc:
        if conn:
            conn.rollback()
        return False, f"Erro ao gravar no banco: {exc}"
    finally:
        if conn:
            conn.close()


def listar_blocos_avs(ano=None):
    conn = None
    try:
        conn = conectar()
        if ano:
            df = pd.read_sql_query("SELECT ano, periodo, area, turma, COUNT(*) AS registros FROM avaliacoes_avs WHERE ano=%s GROUP BY ano, periodo, area, turma ORDER BY periodo, area, turma", conn, params=[str(ano)])
        else:
            df = pd.read_sql_query("SELECT ano, periodo, area, turma, COUNT(*) AS registros FROM avaliacoes_avs GROUP BY ano, periodo, area, turma ORDER BY ano DESC, periodo, area, turma", conn)
        return df
    except Exception:
        return pd.DataFrame(columns=["ano", "periodo", "area", "turma", "registros"])
    finally:
        if conn:
            conn.close()


def excluir_bloco_avs(ano, periodo, area, turma):
    conn = None
    try:
        conn = conectar()
        cur = conn.cursor()
        cur.execute("DELETE FROM avaliacoes_avs WHERE ano=%s AND periodo=%s AND area=%s AND turma=%s", (str(ano), periodo, area, turma))
        n = cur.rowcount
        conn.commit()
        return n, None
    except Exception as exc:
        if conn:
            conn.rollback()
        return 0, str(exc)
    finally:
        if conn:
            conn.close()


def carregar_faltas_1a(ano):
    conn = None
    try:
        conn = conectar()
        sql = """
            SELECT f.id, f.ano, f.periodo, f.area, f.motivo, f.data_registro,
                   a.codigo, a.nome, a.turma
            FROM faltas_primeira_chamada f
            JOIN alunos_v2 a ON a.codigo = f.codigo_aluno
            WHERE f.ano=%s
            ORDER BY a.turma, a.nome, f.periodo, f.area
        """
        return pd.read_sql_query(sql, conn, params=[str(ano)])
    except Exception:
        return pd.DataFrame()
    finally:
        if conn:
            conn.close()


def _texto_pdf(texto):
    return unicodedata.normalize("NFKD", str(texto)).encode("latin-1", "ignore").decode("latin-1")


def gerar_pdf_faltas(df, titulo="Histórico de Faltas na 1ª Chamada"):
    if FPDF is None or df.empty:
        return None
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_fill_color(10, 31, 53)
    pdf.rect(0, 0, 210, 30, "F")
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 12, _texto_pdf(titulo), ln=1, align="C")
    pdf.set_font("Arial", "", 9)
    pdf.cell(0, 6, _texto_pdf(f"Centro Educa Mais Jansen Veloso | Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}"), ln=1, align="C")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(8)

    if len(df) == 1:
        r = df.iloc[0]
        pdf.set_font("Arial", "B", 13)
        pdf.cell(0, 8, _texto_pdf(str(r['nome'])), ln=1)
        pdf.set_font("Arial", "", 10)
        pdf.cell(0, 7, _texto_pdf(f"Código: {r['codigo']} | Turma: {r['turma']}"), ln=1)
        pdf.ln(3)

    pdf.set_font("Arial", "B", 10)
    headers = ["Estudante", "Turma", "Período", "Área", "Motivo"]
    widths = [48, 25, 25, 48, 38]
    for h, w in zip(headers, widths):
        pdf.cell(w, 7, _texto_pdf(h), border=1, align="C")
    pdf.ln()
    pdf.set_font("Arial", "", 8)
    for _, r in df.iterrows():
        vals = [r['nome'], r['turma'], r['periodo'], r['area'], r['motivo']]
        for v, w in zip(vals, widths):
            pdf.cell(w, 7, _texto_pdf(v), border=1)
        pdf.ln()

    try:
        out = pdf.output(dest="S")
        return out.encode("latin-1") if isinstance(out, str) else bytes(out)
    except Exception:
        return None


def renderizar():
    st.title("⚙️ Manutenção AVS e Histórico de 1ª Chamada")
    st.caption("Área administrativa independente. Não altera o fluxo normal de registro de entrada nem o analisador atual.")

    tab_avs, tab_faltas = st.tabs(["📥 Avaliações CSV", "📝 Histórico de Faltas 1ª Chamada"])

    with tab_avs:
        st.subheader("📥 Importar avaliação CSV")
        ano = st.number_input("Ano letivo", min_value=2020, max_value=2100, value=datetime.now().year, step=1, key="avs_admin_ano")
        c1, c2, c3 = st.columns(3)
        with c1:
            periodo = st.selectbox("Período", PERIODOS, key="avs_admin_periodo")
        with c2:
            area = st.selectbox("Área", AREAS, key="avs_admin_area")
        with c3:
            blocos_existentes = listar_blocos_avs(ano)
            turmas = sorted(blocos_existentes["turma"].dropna().unique().tolist()) if not blocos_existentes.empty else []
            st.session_state.setdefault("avs_admin_turmas", turmas)
            turma = st.selectbox("Turma", turmas, key="avs_admin_turma") if turmas else st.text_input("Turma", key="avs_admin_turma_text")

        arquivo = st.file_uploader("Selecione o CSV da avaliação", type=["csv"], key="avs_admin_upload")
        if arquivo and st.button("🚀 PROCESSAR E SALVAR CSV", type="primary", use_container_width=True):
            with st.spinner("Processando respostas em lote..."):
                ok, msg = importar_csv_avs(arquivo, ano, periodo, area, turma)
            if ok:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)

        st.divider()
        st.subheader("🗂️ Importações existentes")
        blocos = listar_blocos_avs()
        if blocos.empty:
            st.info("Nenhuma importação de avaliação encontrada.")
        else:
            st.dataframe(blocos, use_container_width=True, hide_index=True)
            opcoes = [f"{r.ano} | {r.periodo} | {r.area} | {r.turma} ({r.registros} registros)" for r in blocos.itertuples()]
            escolhido = st.selectbox("Selecione uma importação para excluir", opcoes, key="avs_admin_delete")
            confirmar = st.checkbox("Confirmo que desejo excluir permanentemente esta importação.", key="avs_admin_confirm")
            if st.button("🗑️ EXCLUIR IMPORTAÇÃO SELECIONADA", type="primary", disabled=not confirmar):
                r = blocos.iloc[opcoes.index(escolhido)]
                n, erro = excluir_bloco_avs(r["ano"], r["periodo"], r["area"], r["turma"])
                if erro:
                    st.error(erro)
                else:
                    st.success(f"{n} registros excluídos.")
                    st.rerun()

    with tab_faltas:
        st.subheader("📝 Histórico de faltas na 1ª chamada")
        ano_f = st.number_input("Ano letivo", min_value=2020, max_value=2100, value=datetime.now().year, step=1, key="faltas_admin_ano")
        df = carregar_faltas_1a(ano_f)
        if df.empty:
            st.success("Nenhum registro de falta na 1ª chamada encontrado para este ano.")
        else:
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                per = st.selectbox("Período", ["Todos"] + PERIODOS, key="faltas_admin_per")
            with c2:
                areas = ["Todas"] + sorted(df["area"].dropna().unique().tolist())
                ar = st.selectbox("Área", areas, key="faltas_admin_area")
            with c3:
                turmas = ["Todas"] + sorted(df["turma"].dropna().unique().tolist())
                tu = st.selectbox("Turma", turmas, key="faltas_admin_turma")
            with c4:
                alunos = ["Todos"] + sorted(df["nome"].dropna().unique().tolist())
                al = st.selectbox("Estudante", alunos, key="faltas_admin_aluno")

            filt = df.copy()
            if per != "Todos": filt = filt[filt["periodo"] == per]
            if ar != "Todas": filt = filt[filt["area"] == ar]
            if tu != "Todas": filt = filt[filt["turma"] == tu]
            if al != "Todos": filt = filt[filt["nome"] == al]

            st.metric("Estudantes faltosos", filt["codigo"].nunique())
            st.metric("Ocorrências", len(filt))
            st.dataframe(filt[["codigo", "nome", "turma", "periodo", "area", "motivo", "data_registro"]], use_container_width=True, hide_index=True)

            c_pdf1, c_pdf2 = st.columns(2)
            with c_pdf1:
                pdf_geral = gerar_pdf_faltas(filt, "Relatório Geral - Faltas na 1ª Chamada")
                if pdf_geral:
                    st.download_button("📄 BAIXAR PDF GERAL", pdf_geral, "faltas_primeira_chamada_geral.pdf", "application/pdf", use_container_width=True)
            with c_pdf2:
                if al != "Todos":
                    pdf_ind = gerar_pdf_faltas(filt, f"Histórico - {al}")
                    if pdf_ind:
                        st.download_button("📄 BAIXAR PDF DO ESTUDANTE", pdf_ind, f"faltas_{al}.pdf", "application/pdf", use_container_width=True)
                else:
                    st.info("Selecione um estudante para habilitar o PDF individual.")
