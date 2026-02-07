import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time as dtime
import urllib.parse
import pdfplumber
import re
import os

# =========================
# CONFIG
# =========================
st.set_page_config(page_title="ObraGestor Pro", page_icon="🏗️", layout="wide", initial_sidebar_state="expanded")

st.markdown(
    """
    <style>
      .block-container { padding-top: 1.2rem; padding-bottom: 2.2rem; max-width: 1200px; }
      .stButton>button { width: 100%; height: 3em; border-radius: 12px; }
      .card { background: rgba(255,255,255,0.92); border: 1px solid rgba(0,0,0,0.06); border-radius: 16px; padding: 16px; box-shadow: 0 10px 22px rgba(0,0,0,0.06); }
      .kpi-title { font-size: 13px; opacity: .70; margin-bottom: 4px; }
      .kpi-value { font-size: 28px; font-weight: 800; margin-bottom: 2px; }
      .section-title { font-size: 22px; font-weight: 800; margin: 8px 0 6px; }
      .soft { opacity: .70; font-size: 13px; }
    </style>
    """,
    unsafe_allow_html=True,
)

CLIENTES_FILE = "clientes.csv"
OBRAS_FILE = "obras.csv"

# =========================
# HELPERS
# =========================
def br_money(x) -> str:
    try:
        return "R$ " + f"{float(x):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "R$ 0,00"

def ensure_cols(df, cols_defaults: dict):
    if df is None:
        df = pd.DataFrame()
    for c, d in cols_defaults.items():
        if c not in df.columns:
            df[c] = d
    return df

def normalize_status(s):
    s = str(s or "").strip()
    if s == "" or s.lower() == "nan":
        return "🔵 Agendamento"
    return s

def assinatura_obra(row):
    parts = [
        str(row.get("Cliente", "")).strip().lower(),
        str(row.get("Descricao", "")).strip().lower(),
        str(row.get("Data_Orcamento", "")).strip(),
        str(row.get("Total", "")).strip(),
    ]
    return "||".join(parts)

def link_maps(endereco):
    return "https://www.google.com/maps/search/?api=1&query=" + urllib.parse.quote(str(endereco))

def link_calendar(titulo, data_visita, hora_visita, duracao_min, local):
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
        df_o = pd.DataFrame(columns=[
            "ID", "Cliente", "Status",
            "Data_Contato", "Data_Visita", "Data_Orcamento", "Data_Aceite", "Data_Conclusao",
            "Custo_MO", "Custo_Material", "Total", "Entrada", "Pago", "Descricao",
        ])
        df_o.to_csv(OBRAS_FILE, index=False)
    else:
        df_o = pd.read_csv(OBRAS_FILE)

    df_c = ensure_cols(df_c, {"ID": None, "Nome": "", "Telefone": "", "Email": "", "Endereco": "", "Data_Cadastro": ""})
    df_o = ensure_cols(df_o, {
        "ID": None, "Cliente": "", "Status": "🔵 Agendamento",
        "Data_Contato": None, "Data_Visita": None, "Data_Orcamento": None, "Data_Aceite": None, "Data_Conclusao": None,
        "Custo_MO": 0.0, "Custo_Material": 0.0, "Total": 0.0, "Entrada": 0.0, "Pago": False, "Descricao": ""
    })

    df_c["Nome"] = df_c["Nome"].astype(str).replace("nan", "").fillna("").str.strip()
    for col in ["Telefone", "Email", "Endereco"]:
        df_c[col] = df_c[col].astype(str).replace("nan", "").fillna("").str.strip()

    df_o["Cliente"] = df_o["Cliente"].astype(str).replace("nan", "").fillna("").str.strip()
    df_o["Status"] = df_o["Status"].apply(normalize_status)
    df_o["Descricao"] = df_o["Descricao"].astype(str).replace("nan", "").fillna("")

    for col in ["Custo_MO", "Custo_Material", "Total", "Entrada"]:
        df_o[col] = pd.to_numeric(df_o[col], errors="coerce").fillna(0.0)

    df_o["Pago"] = df_o["Pago"].astype(str).str.strip().str.lower().isin(["true", "1", "yes", "sim"])
    for col in ["Data_Visita", "Data_Orcamento", "Data_Conclusao"]:
        df_o[col] = pd.to_datetime(df_o[col], errors="coerce").dt.date

    return df_c, df_o

def save_data(df_c, df_o):
    df_c.to_csv(CLIENTES_FILE, index=False)
    df_o.to_csv(OBRAS_FILE, index=False)

# =========================
# CLEANUP (sem ternário)
# =========================
def limpar_obras(df):
    if df is None or df.empty:
        return df

    df = df.copy()
    df = ensure_cols(df, {"ID": None, "Cliente": "", "Descricao": "", "Data_Orcamento": None, "Total": 0.0})

    df["Cliente"] = df["Cliente"].astype(str).replace("nan", "").fillna("").str.strip()
    df = df[df["Cliente"] != ""].reset_index(drop=True)

    df["ID"] = pd.to_numeric(df["ID"], errors="coerce")
    df["_sig"] = df.apply(assinatura_obra, axis=1)

    max_id = 0
    if df["ID"].notna().any():
        try:
            max_id = int(df["ID"].max())
        except Exception:
            max_id = 0

    missing_ids = df.index[df["ID"].isna()].tolist()
    for i in missing_ids:
        max_id += 1
        df.at[i, "ID"] = max_id

    df["ID"] = pd.to_numeric(df["ID"], errors="coerce").fillna(0).astype(int)

    df = df.drop_duplicates(subset=["ID"], keep="last")

    df["_dt"] = pd.to_datetime(df["Data_Orcamento"], errors="coerce")
    df = df.sort_values(["_sig", "_dt"]).drop_duplicates(subset=["_sig"], keep="last")
    df = df.drop(columns=["_sig", "_dt"])

    return df.reset_index(drop=True)

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

    dados = {}

    m = re.search(r"Cliente:\s*(.+)", text, flags=re.IGNORECASE)
    if m:
        dados["Cliente"] = m.group(1).strip()

    m = re.search(r"Criado em:\s*(\d{2}/\d{2}/\d{2,4})", text, flags=re.IGNORECASE)
    if m:
        dados["Data"] = normalizar_data_ddmmaa(m.group(1))

    m = re.search(r"Total:\s*R\$\s*([\d\.\,]+)", text, flags=re.IGNORECASE)
    if m:
        try:
            dados["Total"] = brl_to_float(m.group(1))
        except Exception:
            pass

    m = re.search(r"Descrição:\s*(.*?)\s*Total:", text, flags=re.IGNORECASE | re.DOTALL)
    if m:
        dados["Descricao"] = m.group(1).strip()

    if "Cliente" not in dados or "Total" not in dados:
        return None

    return dados

def extrair_dados_pdf(pdf_file):
    text = extrair_texto_pdf(pdf_file)
    if not text:
        return None
    return extrair_dados_pdf_solucao(text)

# =========================
# VIEWS
# =========================
def resumo_por_cliente(df_c, df_o):
    if df_c.empty:
        return pd.DataFrame()

    base = df_c.copy()

    if df_o is None or df_o.empty:
        base["Fase"] = "Sem obra"
        base["Total"] = 0.0
        base["Recebido"] = 0.0
        base["Pendente"] = 0.0
        return base[["Nome", "Telefone", "Endereco", "Fase", "Total", "Recebido", "Pendente"]]

    o = df_o.copy()
    o["Status"] = o["Status"].apply(normalize_status)
    o["Data_Visita_dt"] = pd.to_datetime(o["Data_Visita"], errors="coerce")
    o_sort = o.sort_values(["Cliente", "Data_Visita_dt"])
    ult = o_sort.groupby("Cliente", as_index=False).tail(1)[["Cliente", "Status"]]
    mapa_fase = dict(zip(ult["Cliente"].astype(str), ult["Status"].astype(str)))

    total = o.groupby("Cliente", as_index=False)["Total"].sum()

    recebido = o.copy()
    recebido["Recebido_calc"] = recebido.apply(lambda r: float(r["Total"]) if bool(r["Pago"]) else float(r["Entrada"]), axis=1)
    recebido = recebido.groupby("Cliente", as_index=False)["Recebido_calc"].sum().rename(columns={"Recebido_calc": "Recebido"})

    base["Fase"] = base["Nome"].astype(str).map(mapa_fase).fillna("Sem obra")
    base = base.merge(total, how="left", left_on="Nome", right_on="Cliente").drop(columns=["Cliente"], errors="ignore")
    base = base.merge(recebido, how="left", left_on="Nome", right_on="Cliente").drop(columns=["Cliente"], errors="ignore")

    base["Total"] = pd.to_numeric(base.get("Total", 0.0), errors="coerce").fillna(0.0)
    base["Recebido"] = pd.to_numeric(base.get("Recebido", 0.0), errors="coerce").fillna(0.0)
    base["Pendente"] = (base["Total"] - base["Recebido"]).clip(lower=0.0)

    return base[["Nome", "Telefone", "Endereco", "Fase", "Total", "Recebido", "Pendente"]]

# =========================
# DELETE
# =========================
def excluir_cliente(df_clientes, df_obras, nome, apagar_obras=True):
    nome = str(nome).strip()
    df_clientes = df_clientes[df_clientes["Nome"].astype(str).str.strip() != nome].reset_index(drop=True)
    if apagar_obras and (df_obras is not None) and (not df_obras.empty):
        df_obras = df_obras[df_obras["Cliente"].astype(str).str.strip() != nome].reset_index(drop=True)
    return df_clientes, df_obras

def excluir_obra(df_obras, obra_id):
    if df_obras is None or df_obras.empty:
        return df_obras
    obra_id = int(obra_id)
    df_obras = df_obras[df_obras["ID"].astype(int) != obra_id].reset_index(drop=True)
    return df_obras

# =========================
# INIT
# =========================
df_clientes, df_obras = load_data()
df_obras = limpar_obras(df_obras)
save_data(df_clientes, df_obras)

# =========================
# NAV
# =========================
st.sidebar.title("🏗️ ObraGestor Pro")
menu = st.sidebar.radio("Navegação", ["Dashboard", "Gestão de Obras", "Clientes", "Importar/Exportar"])

# =========================
# PAGES
# =========================
if menu == "Dashboard":
    st.markdown("<div class='section-title'>Visão Geral</div>", unsafe_allow_html=True)

    obras_ativas = 0 if df_obras.empty else len(df_obras[~df_obras["Status"].isin(["🟢 Concluído", "🔴 Cancelado"])])
    valor_total = 0.0 if df_obras.empty else float(df_obras["Total"].sum())
    recebido = 0.0 if df_obras.empty else float(df_obras.apply(lambda r: float(r["Total"]) if bool(r["Pago"]) else float(r["Entrada"]), axis=1).sum())

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(f"<div class='card'><div class='kpi-title'>Obras ativas</div><div class='kpi-value'>{obras_ativas}</div></div>", unsafe_allow_html=True)
    c2.markdown(f"<div class='card'><div class='kpi-title'>Clientes</div><div class='kpi-value'>{len(df_clientes)}</div></div>", unsafe_allow_html=True)
    c3.markdown(f"<div class='card'><div class='kpi-title'>Total</div><div class='kpi-value'>{br_money(valor_total)}</div></div>", unsafe_allow_html=True)
    c4.markdown(f"<div class='card'><div class='kpi-title'>Recebido</div><div class='kpi-value'>{br_money(recebido)}</div></div>", unsafe_allow_html=True)

    st.write("")
    resumo = resumo_por_cliente(df_clientes, df_obras)
    if resumo.empty:
        st.info("Sem dados ainda.")
    else:
        r = resumo.copy()
        r["Total"] = r["Total"].apply(br_money)
        r["Recebido"] = r["Recebido"].apply(br_money)
        r["Pendente"] = r["Pendente"].apply(br_money)
        st.dataframe(r, use_container_width=True)

elif menu == "Importar/Exportar":
    st.markdown("<div class='section-title'>Importar / Exportar</div>", unsafe_allow_html=True)

    col1, col2 = st.columns([1.2, 1])

    with col1:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.subheader("1) Upload do PDF")
        pdf = st.file_uploader("Envie o PDF", type="pdf")
        st.markdown("</div>", unsafe_allow_html=True)

        st.write("")

        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.subheader("2) Extração de dados")
        dados = None
        if pdf:
            dados = extrair_dados_pdf(pdf)
            if dados:
                st.success("Extraído com sucesso")
                st.json(dados)
            else:
                st.error("Não consegui extrair desse PDF.")
        else:
            st.info("Envie um PDF primeiro.")
        st.markdown("</div>", unsafe_allow_html=True)

    with col2:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.subheader("3) Google Calendar")
        if 'dados' in locals() and dados and dados.get("Cliente"):
            data_visita = datetime.now().date()
            if dados.get("Data"):
                try:
                    data_visita = datetime.strptime(dados["Data"], "%d/%m/%Y").date()
                except Exception:
                    pass

            data_visita = st.date_input("Data", value=data_visita)
            hora = st.time_input("Hora", value=dtime(9, 0))
            dur = st.number_input("Duração (min)", min_value=15, max_value=480, value=60, step=15)
            end = st.text_input("Endereço (opcional)", value="")
            st.link_button("Criar evento", link_calendar(f"Visita: {dados['Cliente']}", data_visita, hora, dur, end))
        else:
            st.info("Extraia um PDF para liberar.")
        st.markdown("</div>", unsafe_allow_html=True)

        st.write("")

        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.subheader("4) Google Maps")
        end_maps = st.text_input("Endereço para Maps", value="")
        st.link_button("Abrir no Maps", link_maps(end_maps) if end_maps else "#")
        st.markdown("</div>", unsafe_allow_html=True)

elif menu == "Clientes":
    st.markdown("<div class='section-title'>Clientes</div>", unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["Listagem", "Excluir"])

    with tab1:
        resumo = resumo_por_cliente(df_clientes, df_obras)
        if resumo.empty:
            st.info("Sem clientes.")
        else:
            r = resumo.copy()
            r["Total"] = r["Total"].apply(br_money)
            r["Recebido"] = r["Recebido"].apply(br_money)
            r["Pendente"] = r["Pendente"].apply(br_money)
            st.dataframe(r, use_container_width=True)

    with tab2:
        if df_clientes.empty:
            st.info("Sem clientes para excluir.")
        else:
            nome = st.selectbox("Cliente", sorted(df_clientes["Nome"].astype(str).str.strip().unique()))
            apagar_obras = st.checkbox("Apagar obras desse cliente", value=True)
            confirm = st.checkbox("Confirmo que quero excluir", value=False)
            if st.button("Excluir cliente"):
                if not confirm:
                    st.error("Marque a confirmação.")
                else:
                    df_clientes, df_obras = excluir_cliente(df_clientes, df_obras, nome, apagar_obras)
                    df_obras = limpar_obras(df_obras)
                    save_data(df_clientes, df_obras)
                    st.success("Excluído.")
                    st.rerun()

elif menu == "Gestão de Obras":
    st.markdown("<div class='section-title'>Gestão de Obras</div>", unsafe_allow_html=True)
    if df_clientes.empty:
        st.warning("Cadastre um cliente primeiro.")
    else:
        cliente = st.selectbox("Cliente", [""] + sorted(df_clientes["Nome"].astype(str).str.strip().unique()))
        if cliente:
            obras_cliente = df_obras[df_obras["Cliente"].astype(str).str.strip() == cliente] if not df_obras.empty else pd.DataFrame()

            if obras_cliente.empty:
                st.info("Sem obras para esse cliente.")
            else:
                show = obras_cliente.copy()
                show["Total"] = show["Total"].apply(br_money)
                st.dataframe(show[["ID", "Status", "Data_Visita", "Data_Orcamento", "Total"]], use_container_width=True)

            with st.expander("Excluir obra"):
                if obras_cliente.empty:
                    st.info("Nada para excluir.")
                else:
                    obra_id = st.selectbox("Obra (ID)", obras_cliente["ID"].astype(int).tolist())
                    confirm = st.checkbox("Confirmo excluir", value=False, key="conf_excluir_obra")
                    if st.button("Excluir obra"):
                        if not confirm:
                            st.error("Marque a confirmação.")
                        else:
                            df_obras = excluir_obra(df_obras, obra_id)
                            df_obras = limpar_obras(df_obras)
                            save_data(df_clientes, df_obras)
                            st.success("Obra excluída.")
                            st.rerun()
