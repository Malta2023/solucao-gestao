import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time
from fpdf import FPDF
import os
import urllib.parse
import pdfplumber
import re

# =========================
# CONFIGURAÇÃO MOBILE FIRST
# =========================
st.set_page_config(
    page_title="ObraGestor Pro",
    page_icon="🏗️",
    layout="centered",
    initial_sidebar_state="auto"
)

# CSS leve (sem mexer em classes internas frágeis)
st.markdown(
    """
    <style>
      .block-container { padding-top: 1.2rem; padding-bottom: 2.5rem; }
      h1, h2, h3 { letter-spacing: -0.2px; }
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

        # garantir datas (sem quebrar se tiver vazio)
        date_cols = ["Data_Visita", "Data_Orcamento", "Data_Conclusao"]
        for col in date_cols:
            if col in df_o.columns:
                df_o[col] = pd.to_datetime(df_o[col], errors="coerce").dt.date

        # garantir boolean
        if "Pago" in df_o.columns:
            df_o["Pago"] = df_o["Pago"].fillna(False).astype(bool)

        # garantir números
        for col in ["Custo_MO", "Custo_Material", "Total", "Entrada"]:
            if col in df_o.columns:
                df_o[col] = pd.to_numeric(df_o[col], errors="coerce").fillna(0.0)

    return df_c, df_o


def save_data(df_c, df_o):
    df_c.to_csv(CLIENTES_FILE, index=False)
    df_o.to_csv(OBRAS_FILE, index=False)


df_clientes, df_obras = load_data()

# =========================
# UTIL: PDF -> TEXTO (SEGURANÇA)
# =========================
def extrair_texto_pdf(pdf_file) -> str:
    with pdfplumber.open(pdf_file) as pdf:
        partes = []
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                partes.append(t)
        return "\n".join(partes).strip()

# =========================
# UTIL: NORMALIZAÇÃO
# =========================
def brl_to_float(valor_txt: str) -> float:
    # "3.467,00" -> 3467.00
    v = str(valor_txt).strip()
    v = v.replace("R$", "").strip()
    v = v.replace(".", "").replace(",", ".")
    return float(v)

def normalizar_data_ddmmaa(data_txt: str) -> str:
    # "06/02/26" -> "06/02/2026"
    data_txt = data_txt.strip()
    try:
        if re.search(r"\d{2}/\d{2}/\d{2}$", data_txt):
            dt = datetime.strptime(data_txt, "%d/%m/%y")
            return dt.strftime("%d/%m/%Y")
        if re.search(r"\d{2}/\d{2}/\d{4}$", data_txt):
            return data_txt
    except:
        pass
    return data_txt

# =========================
# RECONHECER PDF ANTIGO (Solução Reforma e Construção)
# =========================
def extrair_dados_pdf_solucao(text: str):
    t = text

    # Deve ter pelo menos "ORÇAMENTO" e "Criado em"
    if not re.search(r"ORÇAMENTO", t, flags=re.IGNORECASE):
        return None

    dados = {"tipo": "Orçamento"}

    m = re.search(r"Cliente:\s*(.+)", t, flags=re.IGNORECASE)
    if m:
        dados["Cliente"] = m.group(1).strip()

    m = re.search(r"ORÇAMENTO\s*N[º°]:\s*([0-9]+)", t, flags=re.IGNORECASE)
    if m:
        dados["Numero"] = m.group(1).strip()

    m = re.search(r"Criado em:\s*(\d{2}/\d{2}/\d{2,4})", t, flags=re.IGNORECASE)
    if m:
        dados["Data"] = normalizar_data_ddmmaa(m.group(1))

    # Total: R$ 3.467,00
    m = re.search(r"Total:\s*R\$\s*([\d\.\,]+)", t, flags=re.IGNORECASE)
    if m:
        dados["TOTAL"] = brl_to_float(m.group(1))

    # Valor (às vezes aparece como número sozinho no meio)
    m = re.search(r"\n\s*([\d\.\,]+)\s*\n\s*Total:\s*R\$", t, flags=re.IGNORECASE)
    if m:
        try:
            dados["Valor"] = brl_to_float(m.group(1))
        except:
            pass

    # Descrição: entre "Descrição:" e "Total:"
    m = re.search(r"Descrição:\s*(.*?)\s*Total:", t, flags=re.IGNORECASE | re.DOTALL)
    if m:
        desc = m.group(1).strip()
        # remove linhas só "Valor:"
        desc = re.sub(r"^\s*Valor:\s*$", "", desc, flags=re.IGNORECASE | re.MULTILINE).strip()
        # reduz excesso de quebras
        desc = re.sub(r"\n{3,}", "\n\n", desc)
        dados["Serviço"] = desc

    # Validação mínima
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

        # 1) tenta modelo antigo "Solução Reforma e Construção"
        dados_solucao = extrair_dados_pdf_solucao(text)
        if dados_solucao:
            return dados_solucao

        # 2) fallback: seus padrões antigos (ObraGestor antigo)
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
# GERAR PDF NOVO (PADRÃO OBRAGESTOR)
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

        # quebra manual simples em linhas
        txt = str(value)
        if len(txt) > 80:
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
    except:
        return "#"

# =========================
# UI - SIDEBAR
# =========================
st.sidebar.title("🏗️ ObraGestor Pro")
menu = st.sidebar.radio("Navegação", ["📊 Dashboard", "🏗️ Gestão de Obras", "👥 Clientes", "📥 Importar/Exportar"])

# =========================
# DASHBOARD
# =========================
if menu == "📊 Dashboard":
    st.title("Visão Geral")

    total_obras = len(df_obras)
    obras_ativas = len(df_obras[~df_obras["Status"].isin(["🟢 Concluído", "🔴 Cancelado"])])
    valor_total_ativas = df_obras[~df_obras["Status"].isin(["🟢 Concluído", "🔴 Cancelado"])]["Total"].sum()
    recebido = df_obras[df_obras["Pago"] == True]["Total"].sum() + df_obras[df_obras["Pago"] == False]["Entrada"].sum()

    with st.container(border=True):
        m1, m2 = st.columns(2)
        m1.metric("Obras ativas", obras_ativas)
        m2.metric("Clientes", len(df_clientes))

        m3, m4 = st.columns(2)
        m3.metric("Total em contratos", f"R$ {valor_total_ativas:,.2f}")
        m4.metric("Caixa estimado", f"R$ {recebido:,.2f}")

    st.write("")

    colA, colB = st.columns(2)
    with colA:
        with st.container(border=True):
            st.subheader("Próximas visitas")
            hoje = datetime.now().date()
            if "Data_Visita" in df_obras.columns:
                proximas = df_obras[df_obras["Data_Visita"] >= hoje].sort_values("Data_Visita").head(8)
            else:
                proximas = pd.DataFrame()

            if not proximas.empty:
                st.dataframe(proximas[["Cliente", "Data_Visita", "Status"]], use_container_width=True, hide_index=True)
            else:
                st.info("Nenhuma visita agendada para os próximos dias.")

    with colB:
        with st.container(border=True):
            st.subheader("Status das obras")
            if not df_obras.empty and "Status" in df_obras.columns:
                status_counts = df_obras["Status"].value_counts()
                st.bar_chart(status_counts)
            else:
                st.info("Sem dados para exibir.")

# =========================
# CLIENTES
# =========================
elif menu == "👥 Clientes":
    st.title("Clientes")

    tab1, tab2 = st.tabs(["Listagem", "Novo cliente"])
    with tab1:
        with st.container(border=True):
            search = st.text_input("Buscar por nome ou telefone")
            if search:
                filtered_df = df_clientes[
                    df_clientes["Nome"].astype(str).str.contains(search, case=False, na=False)
                    | df_clientes["Telefone"].astype(str).str.contains(search, case=False, na=False)
                ]
                st.dataframe(filtered_df, use_container_width=True, hide_index=True)
            else:
                st.dataframe(df_clientes, use_container_width=True, hide_index=True)

    with tab2:
        with st.container(border=True):
            with st.form("form_cliente", clear_on_submit=True):
                c_nome = st.text_input("Nome completo*")
                c_tel = st.text_input("Telefone/WhatsApp")
                c_email = st.text_input("E-mail")
                c_end = st.text_input("Endereço de obra")
                submit_c = st.form_submit_button("Cadastrar", use_container_width=True)

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
                        df_clientes = pd.concat([df_clientes, pd.DataFrame([novo_cliente])], ignore_index=True)
                        save_data(df_clientes, df_obras)
                        st.success(f"Cliente {c_nome} cadastrado!")
                        st.rerun()
                    else:
                        st.error("O nome do cliente é obrigatório.")

# =========================
# GESTÃO DE OBRAS
# =========================
elif menu == "🏗️ Gestão de Obras":
    st.title("Gestão de Obras")

    if df_clientes.empty:
        st.warning("Você precisa cadastrar clientes antes.")
    else:
        with st.container(border=True):
            cliente_nomes = sorted(df_clientes["Nome"].dropna().unique())
            cli_selecionado = st.selectbox("Cliente", [""] + cliente_nomes)

        if cli_selecionado:
            obras_cliente = df_obras[df_obras["Cliente"] == cli_selecionado] if not df_obras.empty else pd.DataFrame()

            with st.container(border=True):
                if not obras_cliente.empty:
                    obra_id_options = ["Nova obra"] + [f"Obra ID {i}" for i in obras_cliente["ID"].tolist()]
                    obra_selecao = st.radio("Obra", obra_id_options, horizontal=False)
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

            # BLOCO: DETALHES
            with st.container(border=True):
                st.subheader("Detalhes")

                with st.form("form_obra_detalhe"):
                    status_opts = ["🔵 Agendamento", "🟠 Orçamento Enviado", "🟤 Execução", "🟢 Concluído", "🔴 Cancelado"]
                    status = st.selectbox(
                        "Status",
                        status_opts,
                        index=status_opts.index(obra_atual["Status"]) if obra_atual["Status"] in status_opts else 0,
                    )

                    desc = st.text_area("Descrição do serviço", value=str(obra_atual.get("Descricao", "")), height=120)

                    cA, cB = st.columns(2)
                    dt_visita = cA.date_input("Data da visita", value=obra_atual["Data_Visita"])
                    dt_orc = cB.date_input("Data do orçamento", value=obra_atual["Data_Orcamento"])

                    dt_conc = st.date_input("Previsão de conclusão", value=obra_atual["Data_Conclusao"])

                    f1, f2 = st.columns(2)
                    mo = f1.number_input("Mão de obra (R$)", value=float(obra_atual["Custo_MO"]), min_value=0.0, step=100.0)
                    mat = f2.number_input("Materiais (R$)", value=float(obra_atual["Custo_Material"]), min_value=0.0, step=100.0)

                    total = mo + mat
                    st.info(f"Valor total do contrato: R$ {total:,.2f}")

                    entrada = st.number_input("Entrada (R$)", value=float(obra_atual["Entrada"]), min_value=0.0, step=50.0)
                    pago = st.checkbox("Pagamento total recebido", value=bool(obra_atual["Pago"]))

                    salvar = st.form_submit_button("Salvar", use_container_width=True)

                    if salvar:
                        dados_obra = {
                            "ID": (df_obras["ID"].max() + 1 if not df_obras.empty else 1) if idx_obra == -1 else obra_atual["ID"],
                            "Cliente": cli_selecionado,
                            "Status": status,
                            "Data_Visita": dt_visita,
                            "Data_Orcamento": dt_orc,
                            "Data_Conclusao": dt_conc,
                            "Custo_MO": mo,
                            "Custo_Material": mat,
                            "Total": total,
                            "Entrada": entrada,
                            "Pago": pago,
                            "Descricao": desc,
                        }
                        if idx_obra == -1:
                            df_obras = pd.concat([df_obras, pd.DataFrame([dados_obra])], ignore_index=True)
                        else:
                            for k, v in dados_obra.items():
                                df_obras.at[idx_obra, k] = v

                        save_data(df_clientes, df_obras)
                        st.success("Salvo!")
                        st.rerun()

            # BLOCO: AÇÕES RÁPIDAS (só se já existir obra)
            if idx_obra != -1:
                dados_cli = df_clientes[df_clientes["Nome"] == cli_selecionado].iloc[0]

                with st.container(border=True):
                    st.subheader("Ações rápidas")

                    # agendamento só para gerar link (não salva)
                    c1, c2 = st.columns(2)
                    hora_default = time(9, 0)
                    hora_visita = c1.time_input("Hora", value=hora_default)
                    duracao = c2.number_input("Duração (min)", min_value=15, max_value=480, value=60, step=15)

                    a1, a2 = st.columns(2)
                    a1.link_button("📅 Agendar visita", link_calendar(f"Visita: {cli_selecionado}", dt_visita, hora_visita, duracao, dados_cli.get("Endereco", "")))
                    a2.link_button("📍 Ver endereço", link_maps(dados_cli.get("Endereco", "")))

                    b1, b2 = st.columns(2)
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
                    b1.download_button("📄 Baixar orçamento", data=pdf_orc, file_name=f"orcamento_{cli_selecionado}.pdf", mime="application/pdf", use_container_width=True)

                    valor_recibo = total if pago else entrada
                    pdf_rec = gerar_pdf(
                        "Recibo",
                        {"Recebemos de": cli_selecionado, "Valor": f"R$ {valor_recibo:,.2f}", "Referente a": desc, "Data": datetime.now().strftime("%d/%m/%Y")},
                    )
                    b2.download_button("🧾 Baixar recibo", data=pdf_rec, file_name=f"recibo_{cli_selecionado}.pdf", mime="application/pdf", use_container_width=True)

# =========================
# IMPORTAR / EXPORTAR
# =========================
elif menu == "📥 Importar/Exportar":
    st.title("Importar / Exportar")

    with st.container(border=True):
        st.subheader("Importar PDF (antigo ou novo)")
        st.write("Suba um PDF de orçamento/recibo. Se for do seu modelo antigo, eu converto para a versão nova mantendo os dados.")

        pdf_file = st.file_uploader("Upload de PDF", type="pdf")

        if pdf_file:
            dados_extraidos = extrair_dados_pdf(pdf_file)

            if dados_extraidos:
                st.success(f"PDF reconhecido: {dados_extraidos.get('tipo', 'Documento')}")
                st.json(dados_extraidos)

                nome_cliente = dados_extraidos.get("Cliente") or dados_extraidos.get("Recebemos de")
                if not nome_cliente:
                    st.error("Não consegui achar o nome do cliente no PDF.")
                else:
                    if st.button(f"Confirmar e cadastrar: {nome_cliente}", use_container_width=True):
                        # 1) Cliente
                        if nome_cliente not in df_clientes["Nome"].values:
                            novo_id_c = df_clientes["ID"].max() + 1 if not df_clientes.empty else 1
                            novo_c = {
                                "ID": novo_id_c,
                                "Nome": nome_cliente,
                                "Telefone": "",
                                "Email": "",
                                "Endereco": "",
                                "Data_Cadastro": datetime.now().strftime("%Y-%m-%d"),
                            }
                            df_clientes = pd.concat([df_clientes, pd.DataFrame([novo_c])], ignore_index=True)

                        # 2) Obra
                        novo_id_o = df_obras["ID"].max() + 1 if not df_obras.empty else 1

                        # data
                        data_txt = dados_extraidos.get("Data")
                        data_obra = datetime.now().date()
                        if data_txt:
                            try:
                                if re.search(r"\d{2}/\d{2}/\d{4}$", data_txt):
                                    data_obra = datetime.strptime(data_txt, "%d/%m/%Y").date()
                                elif re.search(r"\d{2}/\d{2}/\d{2}$", data_txt):
                                    data_obra = datetime.strptime(data_txt, "%d/%m/%y").date()
                            except:
                                pass

                        tipo = dados_extraidos.get("tipo")

                        if tipo == "Recibo":
                            total_doc = float(dados_extraidos.get("Valor", 0.0))
                            desc_doc = dados_extraidos.get("Referente a", "")
                            status_doc = "🟢 Concluído"
                            pago_doc = True
                            entrada_doc = total_doc
                            mo_doc = 0.0
                            mat_doc = 0.0
                        else:
                            total_doc = float(dados_extraidos.get("TOTAL") or dados_extraidos.get("Valor") or 0.0)
                            desc_doc = dados_extraidos.get("Serviço") or dados_extraidos.get("Descricao") or ""
                            status_doc = "🟠 Orçamento Enviado"
                            pago_doc = False
                            entrada_doc = 0.0
                            mo_doc = float(dados_extraidos.get("Mão de Obra", 0.0)) if "Mão de Obra" in dados_extraidos else 0.0
                            mat_doc = float(dados_extraidos.get("Materiais", 0.0)) if "Materiais" in dados_extraidos else 0.0

                        nova_o = {
                            "ID": novo_id_o,
                            "Cliente": nome_cliente,
                            "Status": status_doc,
                            "Data_Visita": data_obra,
                            "Data_Orcamento": data_obra,
                            "Data_Conclusao": data_obra,
                            "Custo_MO": mo_doc,
                            "Custo_Material": mat_doc,
                            "Total": total_doc,
                            "Entrada": entrada_doc,
                            "Pago": pago_doc,
                            "Descricao": desc_doc,
                        }

                        df_obras = pd.concat([df_obras, pd.DataFrame([nova_o])], ignore_index=True)
                        save_data(df_clientes, df_obras)
                        st.success("Importado e convertido para a versão nova!")
                        st.rerun()
            else:
                st.error("Não consegui reconhecer esse PDF. Se for escaneado, aí precisa OCR.")

    st.write("")
    c1, c2 = st.columns(2)

    with c1:
        with st.container(border=True):
            st.subheader("Importar clientes (CSV)")
            uploaded_file = st.file_uploader("Upload CSV de Clientes", type="csv", key="csv_clientes")
            if uploaded_file:
                try:
                    df_import = pd.read_csv(uploaded_file)
                    col_n = st.selectbox("Coluna Nome", df_import.columns, key="col_nome")
                    col_t = st.selectbox("Coluna Telefone", df_import.columns, key="col_tel")
                    if st.button("Confirmar importação CSV", use_container_width=True):
                        for _, row in df_import.iterrows():
                            novo_id = df_clientes["ID"].max() + 1 if not df_clientes.empty else 1
                            novo = {
                                "ID": novo_id,
                                "Nome": row[col_n],
                                "Telefone": row[col_t],
                                "Email": "",
                                "Endereco": "",
                                "Data_Cadastro": datetime.now().strftime("%Y-%m-%d"),
                            }
                            df_clientes = pd.concat([df_clientes, pd.DataFrame([novo])], ignore_index=True)
                        save_data(df_clientes, df_obras)
                        st.success("Importação concluída!")
                        st.rerun()
                except Exception as e:
                    st.error(f"Erro ao processar: {e}")

    with c2:
        with st.container(border=True):
            st.subheader("Exportar dados")
            csv_c = df_clientes.to_csv(index=False).encode("utf-8")
            st.download_button("Baixar clientes (CSV)", csv_c, "clientes_backup.csv", "text/csv", use_container_width=True)

            csv_o = df_obras.to_csv(index=False).encode("utf-8")
            st.download_button("Baixar obras (CSV)", csv_o, "obras_backup.csv", "text/csv", use_container_width=True)
