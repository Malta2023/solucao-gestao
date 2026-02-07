import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time as dtime
from fpdf import FPDF
import os
import urllib.parse
import pdfplumber
import re

# =========================
# CONFIG (SEGURO)
# =========================
st.set_page_config(
    page_title="ObraGestor Pro",
    page_icon="🏗️",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
      .block-container { padding-top: 1.2rem; padding-bottom: 2.5rem; }
      .stButton>button { width: 100%; height: 3em; }
    </style>
    """,
    unsafe_allow_html=True,
)

# =========================
# ARQUIVOS
# =========================
CLIENTES_FILE = "clientes.csv"
OBRAS_FILE = "obras.csv"

# =========================
# DADOS
# =========================
def load_data():
    if not os.path.exists(CLIENTES_FILE):
        df_c = pd.DataFrame(
            columns=["ID", "Nome", "Telefone", "Email", "Endereco", "Data_Cadastro"]
        )
        df_c.to_csv(CLIENTES_FILE, index=False)
    else:
        df_c = pd.read_csv(CLIENTES_FILE)

    if not os.path.exists(OBRAS_FILE):
        cols = [
            "ID",
            "Cliente",
            "Status",
            "Data_Contato",
            "Data_Visita",
            "Data_Orcamento",
            "Data_Aceite",
            "Data_Conclusao",
            "Custo_MO",
            "Custo_Material",
            "Total",
            "Entrada",
            "Pago",
            "Descricao",
        ]
        df_o = pd.DataFrame(columns=cols)
        df_o.to_csv(OBRAS_FILE, index=False)
    else:
        df_o = pd.read_csv(OBRAS_FILE)

        # datas
        for col in ["Data_Visita", "Data_Orcamento", "Data_Conclusao"]:
            if col in df_o.columns:
                df_o[col] = pd.to_datetime(df_o[col], errors="coerce").dt.date

        # bool (garante que "True"/"False" vindo do CSV vira bool)
        if "Pago" in df_o.columns:
            df_o["Pago"] = (
                df_o["Pago"]
                .astype(str)
                .str.strip()
                .str.lower()
                .isin(["true", "1", "yes", "sim"])
            )

        # números
        for col in ["Custo_MO", "Custo_Material", "Total", "Entrada"]:
            if col in df_o.columns:
                df_o[col] = pd.to_numeric(df_o[col], errors="coerce").fillna(0.0)

        # garante colunas mínimas (caso CSV antigo)
        if "Descricao" not in df_o.columns:
            df_o["Descricao"] = ""
        if "Entrada" not in df_o.columns:
            df_o["Entrada"] = 0.0
        if "Pago" not in df_o.columns:
            df_o["Pago"] = False

    return df_c, df_o


def save_data(df_c, df_o):
    df_c.to_csv(CLIENTES_FILE, index=False)
    df_o.to_csv(OBRAS_FILE, index=False)


df_clientes, df_obras = load_data()

# =========================
# LIMPEZA (corrige contagem errada)
# =========================
def limpar_obras(df):
    if df is None or df.empty:
        return df

    df = df.copy()

    # remove linhas sem cliente (lixo de CSV)
    if "Cliente" in df.columns:
        df["Cliente"] = df["Cliente"].astype(str).str.strip()
        df = df[
            df["Cliente"].notna()
            & (df["Cliente"] != "")
            & (df["Cliente"].str.lower() != "nan")
        ]

    # remove duplicadas
    if "ID" in df.columns:
        df["ID"] = pd.to_numeric(df["ID"], errors="coerce")
        df = df.drop_duplicates(subset=["ID"], keep="last")
    else:
        base_cols = [c for c in ["Cliente", "Data_Orcamento", "Total", "Descricao"] if c in df.columns]
        if base_cols:
            df = df.drop_duplicates(subset=base_cols, keep="last")

    return df.reset_index(drop=True)


df_obras = limpar_obras(df_obras)

# =========================
# INPUT BR (celular)
# =========================
def parse_brl_num(s, default=0.0):
    try:
        s = str(s).strip()
        if s == "":
            return float(default)
        s = s.replace("R$", "").strip()
        s = s.replace(".", "").replace(",", ".")
        return float(s)
    except Exception:
        return float(default)

def fmt_brl_num(x):
    try:
        return f"{float(x):.2f}".replace(".", ",")
    except Exception:
        return "0,00"

# =========================
# PDF -> TEXTO (SEM QUEBRAR)
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


# =========================
# RECONHECER PDF ANTIGO (Solução Reforma e Construção)
# =========================
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

    m = re.search(
        r"Descrição:\s*(.*?)\s*Total:", text, flags=re.IGNORECASE | re.DOTALL
    )
    if m:
        desc = m.group(1).strip()
        desc = re.sub(
            r"^\s*Valor:\s*$", "", desc, flags=re.IGNORECASE | re.MULTILINE
        ).strip()
        desc = re.sub(r"\n{3,}", "\n\n", desc)
        dados["Serviço"] = desc

    if not dados.get("Cliente") or not dados.get("TOTAL"):
        return None

    return dados


# =========================
# RECONHECER PDF (GERAL)
# =========================
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
# GERAR PDF NOVO (PADRÃO)
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
    pdf.cell(
        0,
        10,
        txt=f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        ln=1,
        align="C",
    )
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
# CLIENTES + FASE
# =========================
def status_por_cliente(df_clientes_in, df_obras_in):
    if df_clientes_in is None or df_clientes_in.empty:
        return df_clientes_in

    out = df_clientes_in.copy()

    if df_obras_in is None or df_obras_in.empty or "Cliente" not in df_obras_in.columns:
        out["Fase"] = "Sem obra"
        return out

    tmp = df_obras_in.copy()

    data_col = "Data_Visita" if "Data_Visita" in tmp.columns else ("Data_Orcamento" if "Data_Orcamento" in tmp.columns else None)
    if data_col:
        tmp[data_col] = pd.to_datetime(tmp[data_col], errors="coerce")
        tmp = tmp.sort_values(data_col)
        ult = tmp.groupby("Cliente", as_index=False).tail(1)
    else:
        ult = tmp.groupby("Cliente", as_index=False).tail(1)

    mapa = dict(zip(ult["Cliente"].astype(str), ult["Status"].astype(str)))
    out["Fase"] = out["Nome"].astype(str).map(mapa).fillna("Sem obra")
    return out


# =========================
# UI
# =========================
st.sidebar.title("🏗️ ObraGestor Pro")
menu = st.sidebar.radio(
    "Navegação",
    ["📊 Dashboard", "🏗️ Gestão de Obras", "👥 Clientes", "📥 Importar/Exportar"],
)

# ---------- DASHBOARD ----------
if menu == "📊 Dashboard":
    st.title("Visão Geral")

    if df_obras is None or df_obras.empty:
        obras_ativas = 0
        valor_total_ativas = 0.0
        recebido = 0.0
    else:
        obras_ativas = len(
            df_obras[~df_obras["Status"].isin(["🟢 Concluído", "🔴 Cancelado"])]
        )
        valor_total_ativas = df_obras[
            ~df_obras["Status"].isin(["🟢 Concluído", "🔴 Cancelado"])
        ]["Total"].sum()

        recebido = df_obras[df_obras["Pago"] == True]["Total"].sum() + df_obras[
            df_obras["Pago"] == False
        ]["Entrada"].sum()

    m1, m2 = st.columns(2)
    m1.metric("Obras ativas", obras_ativas)
    m2.metric("Clientes", len(df_clientes))

    m3, m4 = st.columns(2)
    m3.metric("Total em contratos", f"R$ {valor_total_ativas:,.2f}")
    m4.metric("Caixa estimado", f"R$ {recebido:,.2f}")

    st.divider()

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Próximas visitas")
        hoje = datetime.now().date()
        proximas = pd.DataFrame()
        if df_obras is not None and not df_obras.empty and "Data_Visita" in df_obras.columns:
            proximas = (
                df_obras[df_obras["Data_Visita"] >= hoje]
                .sort_values("Data_Visita")
                .head(8)
            )

        if not proximas.empty:
            st.dataframe(
                proximas[["Cliente", "Data_Visita", "Status"]],
                use_container_width=True,
            )
        else:
            st.info("Nenhuma visita agendada para os próximos dias.")

    with c2:
        st.subheader("Status das obras")
        if df_obras is not None and not df_obras.empty and "Status" in df_obras.columns:
            st.bar_chart(df_obras["Status"].value_counts())
        else:
            st.info("Sem dados para exibir.")

# ---------- CLIENTES ----------
elif menu == "👥 Clientes":
    st.title("Clientes")

    tab1, tab2 = st.tabs(["Listagem", "Novo cliente"])

    with tab1:
        search = st.text_input("Buscar por nome ou telefone")
        df_view = status_por_cliente(df_clientes, df_obras)

        if search:
            filtered_df = df_view[
                df_view["Nome"].astype(str).str.contains(search, case=False, na=False)
                | df_view["Telefone"].astype(str).str.contains(search, case=False, na=False)
            ]
            st.dataframe(filtered_df, use_container_width=True)
        else:
            st.dataframe(df_view, use_container_width=True)

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
                        "Nome": c_nome,
                        "Telefone": c_tel,
                        "Email": c_email,
                        "Endereco": c_end,
                        "Data_Cadastro": datetime.now().strftime("%Y-%m-%d"),
                    }
                    df_clientes = pd.concat(
                        [df_clientes, pd.DataFrame([novo_cliente])], ignore_index=True
                    )
                    save_data(df_clientes, df_obras)
                    st.success("Cliente cadastrado!")
                    st.rerun()
                else:
                    st.error("O nome do cliente é obrigatório.")

# ---------- OBRAS ----------
elif menu == "🏗️ Gestão de Obras":
    st.title("Gestão de Obras")

    if df_clientes is None or df_clientes.empty:
        st.warning("Cadastre um cliente primeiro.")
    else:
        cliente_nomes = sorted(df_clientes["Nome"].dropna().unique())
        cli_selecionado = st.selectbox("Cliente", [""] + cliente_nomes)

        if cli_selecionado:
            obras_cliente = (
                df_obras[df_obras["Cliente"] == cli_selecionado]
                if df_obras is not None and not df_obras.empty
                else pd.DataFrame()
            )

            if not obras_cliente.empty:
                obra_id_options = ["Nova obra"] + [
                    f"Obra ID {i}" for i in obras_cliente["ID"].tolist()
                ]
                obra_selecao = st.radio("Obra", obra_id_options)
            else:
                obra_selecao = "Nova obra"

            if obra_selecao == "Nova obra":
                obra_atual = pd.Series(
                    {
                        "Status": "🔵 Agendamento",
                        "Data_Visita": datetime.now().date(),
                        "Data_Orcamento": datetime.now().date(),
                        "Data_Conclusao": datetime.now().date() + timedelta(days=30),
                        "Custo_MO": 0.0,
                        "Custo_Material": 0.0,
                        "Entrada": 0.0,
                        "Pago": False,
                        "Descricao": "",
                    }
                )
                idx_obra = -1
            else:
                id_obra = int(obra_selecao.split("ID ")[1])
                idx_obra = df_obras[df_obras["ID"] == id_obra].index[0]
                obra_atual = df_obras.loc[idx_obra]

            with st.form("form_obra_detalhe"):
                status_opts = [
                    "🔵 Agendamento",
                    "🟠 Orçamento Enviado",
                    "🟤 Execução",
                    "🟢 Concluído",
                    "🔴 Cancelado",
                ]
                status = st.selectbox(
                    "Status",
                    status_opts,
                    index=status_opts.index(obra_atual["Status"])
                    if obra_atual["Status"] in status_opts
                    else 0,
                )

                desc = st.text_area(
                    "Descrição do serviço",
                    value=str(obra_atual.get("Descricao", "")),
                    height=130,
                )

                cA, cB = st.columns(2)
                dt_visita = cA.date_input("Data da visita", value=obra_atual["Data_Visita"])
                dt_orc = cB.date_input(
                    "Data do orçamento", value=obra_atual["Data_Orcamento"]
                )

                dt_conc = st.date_input(
                    "Previsão de conclusão", value=obra_atual["Data_Conclusao"]
                )

                # inputs BR (melhor no celular)
                mo_txt = st.text_input("Mão de obra (R$)", value=fmt_brl_num(obra_atual.get("Custo_MO", 0.0)))
                mat_txt = st.text_input("Materiais (R$)", value=fmt_brl_num(obra_atual.get("Custo_Material", 0.0)))

                mo = parse_brl_num(mo_txt, 0.0)
                mat = parse_brl_num(mat_txt, 0.0)

                total = mo + mat
                st.info(f"Valor total: R$ {total:,.2f}")

                entrada_txt = st.text_input("Entrada (R$)", value=fmt_brl_num(obra_atual.get("Entrada", 0.0)))
                entrada = parse_brl_num(entrada_txt, 0.0)

                pago = st.checkbox(
                    "Pagamento total recebido", value=bool(obra_atual["Pago"])
                )

                salvar = st.form_submit_button("Salvar")

                if salvar:
                    # cria ID
                    if idx_obra == -1:
                        novo_id = (df_obras["ID"].max() + 1) if (df_obras is not None and not df_obras.empty) else 1
                    else:
                        novo_id = obra_atual["ID"]

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

                    if df_obras is None or df_obras.empty:
                        df_obras = pd.DataFrame([dados_obra])
                    elif idx_obra == -1:
                        df_obras = pd.concat(
                            [df_obras, pd.DataFrame([dados_obra])], ignore_index=True
                        )
                    else:
                        for k, v in dados_obra.items():
                            df_obras.at[idx_obra, k] = v

                    df_obras = limpar_obras(df_obras)
                    save_data(df_clientes, df_obras)
                    st.success("Salvo!")
                    st.rerun()

            if idx_obra != -1:
                st.subheader("Ações rápidas")

                dados_cli = df_clientes[df_clientes["Nome"] == cli_selecionado].iloc[0]
                endereco = dados_cli.get("Endereco", "")

                c1, c2 = st.columns(2)
                hora_visita = c1.time_input("Hora", value=dtime(9, 0))
                duracao = c2.number_input(
                    "Duração (min)", min_value=15, max_value=480, value=60, step=15
                )

                st.link_button(
                    "📅 Agendar visita",
                    link_calendar(
                        f"Visita: {cli_selecionado}",
                        dt_visita,
                        hora_visita,
                        duracao,
                        endereco,
                    ),
                )
                st.link_button("📍 Ver endereço", link_maps(endereco))

                pdf_orc = gerar_pdf(
                    "Orçamento",
                    {
                        "Cliente": cli_selecionado,
                        "Serviço": desc,
                        "Mão de Obra": f"R$ {mo:,.2f}",
                        "Materiais": f"R$ {mat:,.2f}",
                        "TOTAL": f"R$ {total:,.2f}",
                        "Data": dt_orc.strftime("%d/%m/%Y"),
                    },
                )
                st.download_button(
                    "📄 Baixar orçamento",
                    data=pdf_orc,
                    file_name=f"orcamento_{cli_selecionado}.pdf",
                    mime="application/pdf",
                )

                valor_recibo = total if pago else entrada
                pdf_rec = gerar_pdf(
                    "Recibo",
                    {
                        "Recebemos de": cli_selecionado,
                        "Valor": f"R$ {valor_recibo:,.2f}",
                        "Referente a": desc,
                        "Data": datetime.now().strftime("%d/%m/%Y"),
                    },
                )
                st.download_button(
                    "🧾 Baixar recibo",
                    data=pdf_rec,
                    file_name=f"recibo_{cli_selecionado}.pdf",
                    mime="application/pdf",
                )

# ---------- IMPORTAR ----------
elif menu == "📥 Importar/Exportar":
    st.title("Importar / Exportar")

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
                    # cliente
                    if nome_cliente not in df_clientes["Nome"].values:
                        novo_id_c = df_clientes["ID"].max() + 1 if not df_clientes.empty else 1
                        df_clientes = pd.concat(
                            [
                                df_clientes,
                                pd.DataFrame(
                                    [
                                        {
                                            "ID": novo_id_c,
                                            "Nome": nome_cliente,
                                            "Telefone": "",
                                            "Email": "",
                                            "Endereco": "",
                                            "Data_Cadastro": datetime.now().strftime("%Y-%m-%d"),
                                        }
                                    ]
                                ),
                            ],
                            ignore_index=True,
                        )

                    # obra
                    novo_id_o = df_obras["ID"].max() + 1 if (df_obras is not None and not df_obras.empty) else 1

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
                        "Descricao": desc_doc,
                    }

                    if df_obras is None or df_obras.empty:
                        df_obras = pd.DataFrame([nova_o])
                    else:
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
        st.download_button(
            "Baixar clientes (CSV)",
            df_clientes.to_csv(index=False).encode("utf-8"),
            "clientes_backup.csv",
            "text/csv",
        )
    with c2:
        st.subheader("Exportar obras")
        st.download_button(
            "Baixar obras (CSV)",
            df_obras.to_csv(index=False).encode("utf-8") if df_obras is not None else b"",
            "obras_backup.csv",
            "text/csv",
        )
