import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time as dtime
from fpdf import FPDF
import os
import urllib.parse
import pdfplumber
import re

# =========================
# CONFIG
# =========================
st.set_page_config(
    page_title="ObraGestor Pro",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
      .block-container { padding-top: 1.2rem; padding-bottom: 2.2rem; max-width: 1200px; }
      .stButton>button { width: 100%; height: 3em; border-radius: 12px; }
      .card {
        background: rgba(255,255,255,0.9);
        border: 1px solid rgba(0,0,0,0.06);
        border-radius: 16px;
        padding: 16px 16px;
        box-shadow: 0 10px 22px rgba(0,0,0,0.06);
      }
      .kpi-title { font-size: 13px; opacity: .70; margin-bottom: 4px; }
      .kpi-value { font-size: 28px; font-weight: 800; margin-bottom: 2px; }
      .kpi-sub { font-size: 13px; opacity: .75; }
      .soft { opacity: .70; font-size: 13px; }
      .badge {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 999px;
        font-size: 12px;
        border: 1px solid rgba(0,0,0,0.08);
        background: rgba(0,0,0,0.03);
      }
      .section-title { font-size: 22px; font-weight: 800; margin: 8px 0 6px; }
    </style>
    """,
    unsafe_allow_html=True,
)

# =========================
# FILES
# =========================
CLIENTES_FILE = "clientes.csv"
OBRAS_FILE = "obras.csv"

# =========================
# HELPERS
# =========================
def br_money(x: float) -> str:
    try:
        return "R$ " + f"{float(x):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "R$ 0,00"

def safe_date(x):
    try:
        return pd.to_datetime(x, errors="coerce").date()
    except Exception:
        return None

def normalize_status(s):
    s = str(s or "").strip()
    if s == "" or s.lower() == "nan":
        return "🔵 Agendamento"
    return s

def assinatura_obra(row):
    # assinatura para deduplicar quando ID está quebrado
    parts = [
        str(row.get("Cliente", "")).strip().lower(),
        str(row.get("Descricao", "")).strip().lower(),
        str(row.get("Data_Orcamento", "")).strip(),
        str(row.get("Total", "")).strip(),
    ]
    return "||".join(parts)

# =========================
# LOAD/SAVE
# =========================
def load_data():
    if not os.path.exists(CLIENTES_FILE):
        df_c = pd.DataFrame(columns=["ID", "Nome", "Telefone", "Email", "Endereco", "Data_Cadastro"])
        df_c.to_csv(CLIENTES_FILE, index=False)
    else:
        df_c = pd.read_csv(CLIENTES_FILE)

    if not os.path.exists(OBRAS_FILE):
        cols = [
            "ID", "Cliente", "Status",
            "Data_Contato", "Data_Visita", "Data_Orcamento", "Data_Aceite", "Data_Conclusao",
            "Custo_MO", "Custo_Material", "Total", "Entrada", "Pago", "Descricao",
        ]
        df_o = pd.DataFrame(columns=cols)
        df_o.to_csv(OBRAS_FILE, index=False)
    else:
        df_o = pd.read_csv(OBRAS_FILE)

    # normaliza clientes
    if not df_c.empty:
        for col in ["Nome", "Telefone", "Email", "Endereco"]:
            if col in df_c.columns:
                df_c[col] = df_c[col].astype(str).replace("nan", "").fillna("").str.strip()

    # normaliza obras
    if not df_o.empty:
        if "Cliente" in df_o.columns:
            df_o["Cliente"] = df_o["Cliente"].astype(str).replace("nan", "").fillna("").str.strip()

        if "Status" in df_o.columns:
            df_o["Status"] = df_o["Status"].apply(normalize_status)

        for col in ["Data_Visita", "Data_Orcamento", "Data_Conclusao"]:
            if col in df_o.columns:
                df_o[col] = pd.to_datetime(df_o[col], errors="coerce").dt.date

        for col in ["Custo_MO", "Custo_Material", "Total", "Entrada"]:
            if col in df_o.columns:
                df_o[col] = pd.to_numeric(df_o[col], errors="coerce").fillna(0.0)

        if "Pago" in df_o.columns:
            df_o["Pago"] = (
                df_o["Pago"].astype(str).str.strip().str.lower().isin(["true", "1", "yes", "sim"])
            )
        else:
            df_o["Pago"] = False

        if "Descricao" not in df_o.columns:
            df_o["Descricao"] = ""

        if "ID" not in df_o.columns:
            df_o["ID"] = None

    return df_c, df_o

def save_data(df_c, df_o):
    df_c.to_csv(CLIENTES_FILE, index=False)
    df_o.to_csv(OBRAS_FILE, index=False)

df_clientes, df_obras = load_data()

# =========================
# CLEANUP (dedup + IDs)
# =========================
def limpar_obras(df):
    if df is None or df.empty:
        return df

    df = df.copy()

    # remove lixo
    df["Cliente"] = df["Cliente"].astype(str).replace("nan", "").fillna("").str.strip()
    df = df[df["Cliente"] != ""]

    # normaliza ID
    df["ID"] = pd.to_numeric(df["ID"], errors="coerce")
    # cria assinatura para dedup quando ID está NaN
    df["_sig"] = df.apply(assinatura_obra, axis=1)

    # garante ID para linhas sem ID
    max_id = int(df["ID"].max()) if df["ID"].notna().any() else 0
    for i in df.index[df["ID"].isna()].tolist():
        max_id += 1
        df.at[i, "ID"] = max_id

    df["ID"] = df["ID"].astype(int)

    # dedup por ID
    df = df.drop_duplicates(subset=["ID"], keep="last")

    # dedup por assinatura (se existirem duplicadas com IDs diferentes)
    # mantém a última (mais recente) por data de orçamento
    if "Data_Orcamento" in df.columns:
        df["_dt"] = pd.to_datetime(df["Data_Orcamento"], errors="coerce")
        df = df.sort_values(["_sig", "_dt"]).drop_duplicates(subset=["_sig"], keep="last")
        df = df.drop(columns=["_dt"])
    else:
        df = df.drop_duplicates(subset=["_sig"], keep="last")

    df = df.drop(columns=["_sig"])
    return df.reset_index(drop=True)

df_obras = limpar_obras(df_obras)
save_data(df_clientes, df_obras)

# =========================
# PDF
# =========================
def extrair_texto_pdf(pdf_file) -> str:
    with pdfplumber.open(pdf_file) as pdf:
        partes = []
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                partes.append(t)
        return "\n".join(partes).strip()

def brl_to_float(valor_txt: str) -> float:
    v = str(valor_txt).strip().replace("R$", "").strip()
    v = v.replace(".", "").replace(",", ".")
    return float(v)

def normalizar_data_ddmmaa(data_txt: str) -> str:
    data_txt = str(data_txt).strip()
    try:
        if re.search(r"\d{2}/\d{2}/\d{2}$", data_txt):
            return datetime.strptime(data_txt, "%d/%m/%y").strftime("%d/%m/%Y")
        if re.search(r"\d{2}/\d{2}/\d{4}$", data_txt):
            return data_txt
    except Exception:
        pass
    return data_txt

def extrair_dados_pdf_solucao(text: str):
    if not re.search(r"ORÇAMENTO", text, flags=re.IGNORECASE):
        return None

    dados = {"tipo": "Orçamento"}

    m = re.search(r"Cliente:\s*(.+)", text, flags=re.IGNORECASE)
    if m:
        dados["Cliente"] = m.group(1).strip()

    m = re.search(r"ORÇAMENTO\s*N[º°]:\s*([0-9]+)", text, flags=re.IGNORECASE)
    if m:
        dados["Numero"] = m.group(1).strip()

    m = re.search(r"Criado em:\s*(\d{2}/\d{2}/\d{2,4})", text, flags=re.IGNORECASE)
    if m:
        dados["Data"] = normalizar_data_ddmmaa(m.group(1))

    m = re.search(r"Total:\s*R\$\s*([\d\.\,]+)", text, flags=re.IGNORECASE)
    if m:
        try:
            dados["TOTAL"] = brl_to_float(m.group(1))
        except Exception:
            pass

    m = re.search(r"Descrição:\s*(.*?)\s*Total:", text, flags=re.IGNORECASE | re.DOTALL)
    if m:
        desc = m.group(1).strip()
        desc = re.sub(r"^\s*Valor:\s*$", "", desc, flags=re.IGNORECASE | re.MULTILINE).strip()
        desc = re.sub(r"\n{3,}", "\n\n", desc)
        dados["Serviço"] = desc

    if not dados.get("Cliente") or not dados.get("TOTAL"):
        return None

    return dados

def extrair_dados_pdf(pdf_file):
    try:
        text = extrair_texto_pdf(pdf_file)
        if not text:
            return None

        dados_solucao = extrair_dados_pdf_solucao(text)
        if dados_solucao:
            return dados_solucao

        dados = {"tipo": None}
        text_up = text.upper()

        if "ORÇAMENTO" in text_up:
            dados["tipo"] = "Orçamento"
            patterns = {
                "Cliente": r"Cliente:\s*(.*)",
                "Serviço": r"Serviço:\s*(.*)",
                "Mão de Obra": r"Mão de Obra:\s*R\$\s*([\d\.,]+)",
                "Materiais": r"Materiais:\s*R\$\s*([\d\.,]+)",
                "TOTAL": r"TOTAL:\s*R\$\s*([\d\.,]+)",
                "Data": r"Data:\s*(\d{2}/\d{2}/\d{4})",
            }
        elif "RECIBO" in text_up:
            dados["tipo"] = "Recibo"
            patterns = {
                "Recebemos de": r"Recebemos de:\s*(.*)",
                "Valor": r"Valor:\s*R\$\s*([\d\.,]+)",
                "Referente a": r"Referente a:\s*(.*)",
                "Data": r"Data:\s*(\d{2}/\d{2}/\d{4})",
            }
        else:
            return None

        for key, pattern in patterns.items():
            match = re.search(pattern, text)
            if match:
                val = match.group(1).strip()
                if key in ["Mão de Obra", "Materiais", "TOTAL", "Valor"]:
                    dados[key] = brl_to_float(val)
                else:
                    dados[key] = val

        return dados

    except Exception as e:
        st.error(f"Erro ao ler PDF: {e}")
        return None

# =========================
# PDF GENERATOR
# =========================
def gerar_pdf(tipo, dados):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)

    pdf.set_fill_color(245, 245, 245)
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 16, txt=f"OBRAGESTOR - {tipo.upper()}", ln=1, align="C", fill=True)
    pdf.ln(6)

    pdf.set_font("Helvetica", "B", 12)
    for key, value in dados.items():
        pdf.set_text_color(90, 90, 90)
        pdf.cell(48, 8, txt=f"{key}:", ln=0)

        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Helvetica", "", 12)

        txt = str(value)
        if len(txt) > 90:
            pdf.multi_cell(0, 7, txt=txt)
        else:
            pdf.cell(0, 8, txt=txt, ln=1)

        pdf.set_font("Helvetica", "B", 12)

    pdf.ln(10)
    pdf.set_font("Helvetica", "I", 10)
    pdf.set_text_color(140, 140, 140)
    pdf.cell(0, 10, txt=f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=1, align="C")
    return pdf.output(dest="S").encode("latin-1", "replace")

# =========================
# LINKS
# =========================
def link_maps(endereco):
    base = "https://www.google.com/maps/search/?api=1&query="
    return base + urllib.parse.quote(str(endereco))

def link_calendar(titulo, data_visita, hora_visita, duracao_min, local):
    try:
        inicio_dt = datetime.combine(data_visita, hora_visita)
        fim_dt = inicio_dt + timedelta(minutes=int(duracao_min))
        start = inicio_dt.strftime("%Y%m%dT%H%M%S")
        end = fim_dt.strftime("%Y%m%dT%H%M%S")

        base = "https://calendar.google.com/calendar/render?action=TEMPLATE"
        return (
            f"{base}"
            f"&text={urllib.parse.quote(titulo)}"
            f"&dates={start}/{end}"
            f"&details={urllib.parse.quote('Visita Técnica')}"
            f"&location={urllib.parse.quote(str(local))}"
            f"&ctz=America/Sao_Paulo"
        )
    except Exception:
        return "#"

# =========================
# VIEWS
# =========================
def resumo_por_cliente(df_c, df_o):
    if df_c is None or df_c.empty:
        return pd.DataFrame()

    base = df_c.copy()
    base["Nome"] = base["Nome"].astype(str).str.strip()

    if df_o is None or df_o.empty:
        base["Fase"] = "Sem obra"
        base["Total"] = 0.0
        base["Recebido"] = 0.0
        base["Pendente"] = 0.0
        base["Proxima_visita"] = None
        return base[["Nome", "Telefone", "Endereco", "Fase", "Total", "Recebido", "Pendente", "Proxima_visita"]]

    o = df_o.copy()
    o["Cliente"] = o["Cliente"].astype(str).str.strip()
    o["Status"] = o["Status"].apply(normalize_status)

    o["Data_Visita_dt"] = pd.to_datetime(o["Data_Visita"], errors="coerce")
    o["Data_Orc_dt"] = pd.to_datetime(o["Data_Orcamento"], errors="coerce")

    # fase mais recente
    o_sort = o.sort_values(["Cliente", "Data_Visita_dt", "Data_Orc_dt"])
    ult = o_sort.groupby("Cliente", as_index=False).tail(1)[["Cliente", "Status"]]
    mapa_fase = dict(zip(ult["Cliente"], ult["Status"]))

    # totais
    total = o.groupby("Cliente", as_index=False)["Total"].sum().rename(columns={"Total": "Total"})
    recebido = o.copy()
    recebido["Recebido_calc"] = recebido.apply(lambda r: float(r["Total"]) if bool(r["Pago"]) else float(r["Entrada"]), axis=1)
    recebido = recebido.groupby("Cliente", as_index=False)["Recebido_calc"].sum().rename(columns={"Recebido_calc": "Recebido"})

    # próxima visita
    hoje = pd.Timestamp.now().normalize()
    prox = o[o["Data_Visita_dt"].notna() & (o["Data_Visita_dt"] >= hoje)]
    if not prox.empty:
        prox = prox.sort_values(["Cliente", "Data_Visita_dt"]).groupby("Cliente", as_index=False).head(1)
        mapa_prox = dict(zip(prox["Cliente"], prox["Data_Visita_dt"].dt.date))
    else:
        mapa_prox = {}

    base["Fase"] = base["Nome"].map(mapa_fase).fillna("Sem obra")
    base = base.merge(total, how="left", left_on="Nome", right_on="Cliente").drop(columns=["Cliente"], errors="ignore")
    base = base.merge(recebido, how="left", left_on="Nome", right_on="Cliente").drop(columns=["Cliente"], errors="ignore")

    base["Total"] = pd.to_numeric(base["Total"], errors="coerce").fillna(0.0)
    base["Recebido"] = pd.to_numeric(base["Recebido"], errors="coerce").fillna(0.0)
    base["Pendente"] = (base["Total"] - base["Recebido"]).clip(lower=0.0)
    base["Proxima_visita"] = base["Nome"].map(mapa_prox)

    return base[["Nome", "Telefone", "Endereco", "Fase", "Total", "Recebido", "Pendente", "Proxima_visita"]]

# =========================
# SIDEBAR
# =========================
st.sidebar.title("🏗️ ObraGestor Pro")
menu = st.sidebar.radio("Navegação", ["📊 Dashboard", "🏗️ Gestão de Obras", "👥 Clientes", "📥 Importar/Exportar"])

# =========================
# DASHBOARD
# =========================
if menu == "📊 Dashboard":
    st.markdown("<div class='section-title'>Visão Geral</div>", unsafe_allow_html=True)

    obras_validas = df_obras.copy() if df_obras is not None else pd.DataFrame()
    if not obras_validas.empty:
        obras_validas["Status"] = obras_validas["Status"].apply(normalize_status)

    obras_ativas = 0 if obras_validas.empty else len(obras_validas[~obras_validas["Status"].isin(["🟢 Concluído", "🔴 Cancelado"])])
    valor_total = 0.0 if obras_validas.empty else float(obras_validas["Total"].sum())

    if obras_validas.empty:
        recebido = 0.0
    else:
        recebido = float(
            obras_validas.apply(lambda r: float(r["Total"]) if bool(r["Pago"]) else float(r["Entrada"]), axis=1).sum()
        )

    clientes_qtd = 0 if df_clientes is None else len(df_clientes)

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(f"<div class='card'><div class='kpi-title'>Obras ativas</div><div class='kpi-value'>{obras_ativas}</div><div class='kpi-sub'>Em andamento</div></div>", unsafe_allow_html=True)
    c2.markdown(f"<div class='card'><div class='kpi-title'>Clientes</div><div class='kpi-value'>{clientes_qtd}</div><div class='kpi-sub'>Cadastrados</div></div>", unsafe_allow_html=True)
    c3.markdown(f"<div class='card'><div class='kpi-title'>Total em contratos</div><div class='kpi-value'>{br_money(valor_total)}</div><div class='kpi-sub'>Somatório</div></div>", unsafe_allow_html=True)
    c4.markdown(f"<div class='card'><div class='kpi-title'>Caixa estimado</div><div class='kpi-value'>{br_money(recebido)}</div><div class='kpi-sub'>Total recebido</div></div>", unsafe_allow_html=True)

    st.write("")

    left, right = st.columns([1.2, 1])

    with left:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.markdown("<div class='section-title'>Resumo por cliente</div>", unsafe_allow_html=True)
        resumo = resumo_por_cliente(df_clientes, obras_validas)
        if resumo.empty:
            st.info("Sem dados ainda.")
        else:
            resumo_show = resumo.copy()
            resumo_show["Total"] = resumo_show["Total"].apply(br_money)
            resumo_show["Recebido"] = resumo_show["Recebido"].apply(br_money)
            resumo_show["Pendente"] = resumo_show["Pendente"].apply(br_money)
            st.dataframe(resumo_show, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with right:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.markdown("<div class='section-title'>Próximas visitas</div>", unsafe_allow_html=True)
        hoje = datetime.now().date()
        if obras_validas.empty or "Data_Visita" not in obras_validas.columns:
            st.info("Nenhuma visita.")
        else:
            prox = obras_validas.copy()
            prox = prox[prox["Data_Visita"].notna()]
            prox = prox[prox["Data_Visita"] >= hoje].sort_values("Data_Visita").head(8)
            if prox.empty:
                st.info("Nenhuma visita agendada para os próximos dias.")
            else:
                st.dataframe(prox[["Cliente", "Data_Visita", "Status"]], use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

        st.write("")

        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.markdown("<div class='section-title'>Status das obras</div>", unsafe_allow_html=True)
        if obras_validas.empty:
            st.info("Sem dados.")
        else:
            st.bar_chart(obras_validas["Status"].value_counts())
        st.markdown("</div>", unsafe_allow_html=True)

# =========================
# CLIENTES
# =========================
elif menu == "👥 Clientes":
    st.markdown("<div class='section-title'>Clientes</div>", unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["Listagem", "Novo cliente"])

    with tab1:
        search = st.text_input("Buscar por nome ou telefone")
        resumo = resumo_por_cliente(df_clientes, df_obras)

        if resumo.empty:
            st.info("Sem clientes cadastrados.")
        else:
            view = resumo.copy()
            if search:
                view = view[
                    view["Nome"].astype(str).str.contains(search, case=False, na=False)
                    | view["Telefone"].astype(str).str.contains(search, case=False, na=False)
                ]

            view_show = view.copy()
            view_show["Total"] = view_show["Total"].apply(br_money)
            view_show["Recebido"] = view_show["Recebido"].apply(br_money)
            view_show["Pendente"] = view_show["Pendente"].apply(br_money)
            st.dataframe(view_show, use_container_width=True)

    with tab2:
        with st.form("form_cliente", clear_on_submit=True):
            c_nome = st.text_input("Nome completo*")
            c_tel = st.text_input("Telefone/WhatsApp")
            c_email = st.text_input("E-mail")
            c_end = st.text_input("Endereço de obra")
            submit_c = st.form_submit_button("Cadastrar")

            if submit_c:
                if c_nome:
                    novo_id = df_clientes["ID"].max() + 1 if not df_clientes.empty else 1
                    novo_cliente = {
                        "ID": novo_id,
                        "Nome": c_nome.strip(),
                        "Telefone": c_tel.strip(),
                        "Email": c_email.strip(),
                        "Endereco": c_end.strip(),
                        "Data_Cadastro": datetime.now().strftime("%Y-%m-%d"),
                    }
                    df_clientes = pd.concat([df_clientes, pd.DataFrame([novo_cliente])], ignore_index=True)
                    save_data(df_clientes, df_obras)
                    st.success("Cliente cadastrado!")
                    st.rerun()
                else:
                    st.error("O nome do cliente é obrigatório.")

# =========================
# OBRAS
# =========================
elif menu == "🏗️ Gestão de Obras":
    st.markdown("<div class='section-title'>Gestão de Obras</div>", unsafe_allow_html=True)

    if df_clientes is None or df_clientes.empty:
        st.warning("Cadastre um cliente primeiro.")
    else:
        st.caption("Valores: use ponto para centavos. Ex: 3467.50 (o app salva certinho).")  # [web:185]

        cliente_nomes = sorted(df_clientes["Nome"].dropna().astype(str).str.strip().unique())
        cli_selecionado = st.selectbox("Cliente", [""] + cliente_nomes)

        if cli_selecionado:
            obras_cliente = df_obras[df_obras["Cliente"] == cli_selecionado] if (df_obras is not None and not df_obras.empty) else pd.DataFrame()

            if not obras_cliente.empty:
                obra_id_options = ["Nova obra"] + [f"Obra ID {i}" for i in obras_cliente["ID"].astype(int).tolist()]
                obra_selecao = st.radio("Obra", obra_id_options)
            else:
                obra_selecao = "Nova obra"

            if obra_selecao == "Nova obra":
                obra_atual = pd.Series({
                    "ID": None,
                    "Status": "🔵 Agendamento",
                    "Data_Visita": datetime.now().date(),
                    "Data_Orcamento": datetime.now().date(),
                    "Data_Conclusao": datetime.now().date() + timedelta(days=30),
                    "Custo_MO": 0.0,
                    "Custo_Material": 0.0,
                    "Entrada": 0.0,
                    "Pago": False,
                    "Descricao": "",
                })
                idx_obra = -1
            else:
                id_obra = int(obra_selecao.split("ID ")[1])
                idx_obra = df_obras[df_obras["ID"].astype(int) == id_obra].index[0]
                obra_atual = df_obras.loc[idx_obra]

            with st.form("form_obra_detalhe"):
                status_opts = ["🔵 Agendamento", "🟠 Orçamento Enviado", "🟤 Execução", "🟢 Concluído", "🔴 Cancelado"]
                status = st.selectbox(
                    "Status",
                    status_opts,
                    index=status_opts.index(normalize_status(obra_atual.get("Status"))) if normalize_status(obra_atual.get("Status")) in status_opts else 0
                )

                desc = st.text_area("Descrição do serviço", value=str(obra_atual.get("Descricao", "")), height=140)

                cA, cB, cC = st.columns(3)
                dt_visita = cA.date_input("Data da visita", value=obra_atual.get("Data_Visita") or datetime.now().date())
                dt_orc = cB.date_input("Data do orçamento", value=obra_atual.get("Data_Orcamento") or datetime.now().date())
                dt_conc = cC.date_input("Previsão de conclusão", value=obra_atual.get("Data_Conclusao") or (datetime.now().date() + timedelta(days=30)))

                c1, c2, c3 = st.columns(3)
                mo = c1.number_input("Mão de obra (R$)", min_value=0.0, step=10.0, value=float(obra_atual.get("Custo_MO", 0.0)), format="%.2f")
                mat = c2.number_input("Materiais (R$)", min_value=0.0, step=10.0, value=float(obra_atual.get("Custo_Material", 0.0)), format="%.2f")
                entrada = c3.number_input("Entrada (R$)", min_value=0.0, step=10.0, value=float(obra_atual.get("Entrada", 0.0)), format="%.2f")

                total = mo + mat
                st.info(f"Valor total: {br_money(total)}")

                pago = st.checkbox("Pagamento total recebido", value=bool(obra_atual.get("Pago", False)))

                salvar = st.form_submit_button("Salvar")

                if salvar:
                    if df_obras is None or df_obras.empty:
                        df_obras = pd.DataFrame(columns=[
                            "ID", "Cliente", "Status", "Data_Contato", "Data_Visita", "Data_Orcamento", "Data_Aceite", "Data_Conclusao",
                            "Custo_MO", "Custo_Material", "Total", "Entrada", "Pago", "Descricao"
                        ])

                    if idx_obra == -1:
                        novo_id = int(df_obras["ID"].max()) + 1 if df_obras["ID"].notna().any() else 1
                    else:
                        novo_id = int(obra_atual["ID"])

                    dados_obra = {
                        "ID": novo_id,
                        "Cliente": cli_selecionado,
                        "Status": status,
                        "Data_Visita": dt_visita,
                        "Data_Orcamento": dt_orc,
                        "Data_Conclusao": dt_conc,
                        "Custo_MO": float(mo),
                        "Custo_Material": float(mat),
                        "Total": float(total),
                        "Entrada": float(entrada),
                        "Pago": bool(pago),
                        "Descricao": desc,
                    }

                    if idx_obra == -1:
                        df_obras = pd.concat([df_obras, pd.DataFrame([dados_obra])], ignore_index=True)
                    else:
                        for k, v in dados_obra.items():
                            df_obras.at[idx_obra, k] = v

                    df_obras = limpar_obras(df_obras)
                    save_data(df_clientes, df_obras)
                    st.success("Salvo!")
                    st.rerun()

            if idx_obra != -1:
                st.markdown("<div class='soft'>Ações rápidas</div>", unsafe_allow_html=True)

                dados_cli = df_clientes[df_clientes["Nome"].astype(str).str.strip() == cli_selecionado].iloc[0]
                endereco = str(dados_cli.get("Endereco", "")).strip()

                c1, c2 = st.columns(2)
                hora_visita = c1.time_input("Hora", value=dtime(9, 0))
                duracao = c2.number_input("Duração (min)", min_value=15, max_value=480, value=60, step=15)

                st.link_button("📅 Agendar visita", link_calendar(f"Visita: {cli_selecionado}", dt_visita, hora_visita, duracao, endereco))
                st.link_button("📍 Ver endereço", link_maps(endereco))

                pdf_orc = gerar_pdf("Orçamento", {
                    "Cliente": cli_selecionado,
                    "Serviço": desc,
                    "Mão de Obra": br_money(mo),
                    "Materiais": br_money(mat),
                    "TOTAL": br_money(total),
                    "Data": dt_orc.strftime("%d/%m/%Y"),
                })
                st.download_button("📄 Baixar orçamento", data=pdf_orc, file_name=f"orcamento_{cli_selecionado}.pdf", mime="application/pdf")

                valor_recibo = total if pago else entrada
                pdf_rec = gerar_pdf("Recibo", {
                    "Recebemos de": cli_selecionado,
                    "Valor": br_money(valor_recibo),
                    "Referente a": desc,
                    "Data": datetime.now().strftime("%d/%m/%Y"),
                })
                st.download_button("🧾 Baixar recibo", data=pdf_rec, file_name=f"recibo_{cli_selecionado}.pdf", mime="application/pdf")

# =========================
# IMPORT / EXPORT
# =========================
elif menu == "📥 Importar/Exportar":
    st.markdown("<div class='section-title'>Importar / Exportar</div>", unsafe_allow_html=True)

    st.subheader("Importar PDF antigo e converter")
    pdf_file = st.file_uploader("Upload de PDF", type="pdf")

    if pdf_file:
        dados_extraidos = extrair_dados_pdf(pdf_file)

        if dados_extraidos:
            st.success("PDF reconhecido!")
            st.json(dados_extraidos)

            nome_cliente = dados_extraidos.get("Cliente") or dados_extraidos.get("Recebemos de")
            if not nome_cliente:
                st.error("Não achei o nome do cliente no PDF.")
            else:
                if st.button(f"Confirmar e cadastrar: {nome_cliente}"):
                    nome_cliente = str(nome_cliente).strip()

                    # cliente
                    if df_clientes.empty or (nome_cliente not in df_clientes["Nome"].astype(str).values):
                        novo_id_c = df_clientes["ID"].max() + 1 if not df_clientes.empty else 1
                        df_clientes = pd.concat([df_clientes, pd.DataFrame([{
                            "ID": novo_id_c,
                            "Nome": nome_cliente,
                            "Telefone": "",
                            "Email": "",
                            "Endereco": "",
                            "Data_Cadastro": datetime.now().strftime("%Y-%m-%d"),
                        }])], ignore_index=True)

                    # obra
                    if df_obras is None or df_obras.empty:
                        df_obras = pd.DataFrame(columns=[
                            "ID", "Cliente", "Status", "Data_Contato", "Data_Visita", "Data_Orcamento", "Data_Aceite", "Data_Conclusao",
                            "Custo_MO", "Custo_Material", "Total", "Entrada", "Pago", "Descricao"
                        ])

                    novo_id_o = int(df_obras["ID"].max()) + 1 if df_obras["ID"].notna().any() else 1

                    data_txt = dados_extraidos.get("Data")
                    data_obra = datetime.now().date()
                    if data_txt:
                        try:
                            if re.search(r"\d{2}/\d{2}/\d{4}$", data_txt):
                                data_obra = datetime.strptime(data_txt, "%d/%m/%Y").date()
                            elif re.search(r"\d{2}/\d{2}/\d{2}$", data_txt):
                                data_obra = datetime.strptime(data_txt, "%d/%m/%y").date()
                        except Exception:
                            pass

                    total_doc = float(dados_extraidos.get("TOTAL") or dados_extraidos.get("Valor") or 0.0)
                    desc_doc = dados_extraidos.get("Serviço") or dados_extraidos.get("Descricao") or ""

                    nova_o = {
                        "ID": novo_id_o,
                        "Cliente": nome_cliente,
                        "Status": "🟠 Orçamento Enviado",
                        "Data_Visita": data_obra,
                        "Data_Orcamento": data_obra,
                        "Data_Conclusao": data_obra,
                        "Custo_MO": 0.0,
                        "Custo_Material": 0.0,
                        "Total": total_doc,
                        "Entrada": 0.0,
                        "Pago": False,
                        "Descricao": str(desc_doc),
                    }

                    df_obras = pd.concat([df_obras, pd.DataFrame([nova_o])], ignore_index=True)
                    df_obras = limpar_obras(df_obras)
                    save_data(df_clientes, df_obras)
                    st.success("Importado e convertido!")
                    st.rerun()
        else:
            st.error("Não consegui ler esse PDF. Se ele for escaneado, precisa OCR.")

    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Exportar clientes")
        st.download_button("Baixar clientes (CSV)", df_clientes.to_csv(index=False).encode("utf-8"), "clientes_backup.csv", "text/csv")
    with c2:
        st.subheader("Exportar obras")
        st.download_button("Baixar obras (CSV)", df_obras.to_csv(index=False).encode("utf-8"), "obras_backup.csv", "text/csv")
