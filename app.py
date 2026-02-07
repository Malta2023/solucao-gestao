import streamlit as st
import pandas as pd
from datetime import datetime, date
import os
import re
import pdfplumber

# =====================================
# CONFIGURAÇÃO INICIAL
# =====================================
st.set_page_config(
    page_title="ObraGestor Pro",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
    <style>
        .block-container { padding-top: 1rem; padding-bottom: 2rem; }
        .stButton > button { width: 100%; height: 3em; font-size: 1.1em; }
        h1, h2, h3 { color: #2c3e50; }
    </style>
""", unsafe_allow_html=True)

# =====================================
# PASTA DE DADOS (essencial para Streamlit Cloud / hospedagem)
# =====================================
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

CLIENTES_FILE = os.path.join(DATA_DIR, "clientes.csv")
OBRAS_FILE    = os.path.join(DATA_DIR, "obras.csv")

# =====================================
# CARREGAR / SALVAR DADOS
# =====================================
@st.cache_data(ttl=300)  # cache de 5 minutos
def load_data():
    try:
        # Clientes
        if not os.path.exists(CLIENTES_FILE):
            df_c = pd.DataFrame(columns=["ID", "Nome", "Telefone", "Email", "Endereco", "Data_Cadastro"])
            df_c.to_csv(CLIENTES_FILE, index=False)
        else:
            df_c = pd.read_csv(CLIENTES_FILE)

        # Obras
        if not os.path.exists(OBRAS_FILE):
            cols = [
                "ID", "Cliente", "Status", "Data_Contato", "Data_Visita", "Data_Orcamento",
                "Data_Aceite", "Data_Conclusao", "Custo_MO", "Custo_Material", "Total",
                "Entrada", "Pago", "Descricao", "Numero_Orcamento"
            ]
            df_o = pd.DataFrame(columns=cols)
            df_o.to_csv(OBRAS_FILE, index=False)
        else:
            df_o = pd.read_csv(OBRAS_FILE)

        # Tratamento de tipos
        date_cols = ["Data_Contato", "Data_Visita", "Data_Orcamento", "Data_Aceite", "Data_Conclusao"]
        for col in date_cols:
            if col in df_o.columns:
                df_o[col] = pd.to_datetime(df_o[col], errors="coerce")

        numeric_cols = ["Custo_MO", "Custo_Material", "Total", "Entrada"]
        for col in numeric_cols:
            if col in df_o.columns:
                df_o[col] = pd.to_numeric(df_o[col], errors="coerce").fillna(0.0)

        if "Pago" in df_o.columns:
            df_o["Pago"] = df_o["Pago"].fillna(False).astype(bool)

        # Garante colunas mínimas
        for col, default in [("Descricao", ""), ("Numero_Orcamento", ""), ("Entrada", 0.0), ("Pago", False)]:
            if col not in df_o.columns:
                df_o[col] = default

        return df_c, df_o

    except Exception as e:
        st.error(f"Erro grave ao carregar dados: {str(e)}")
        st.stop()

def save_data(df_c, df_o):
    try:
        df_c.to_csv(CLIENTES_FILE, index=False)
        df_o.to_csv(OBRAS_FILE, index=False)
    except Exception as e:
        st.error(f"Erro ao salvar dados: {str(e)}")

# Carrega uma vez
if "df_clientes" not in st.session_state or "df_obras" not in st.session_state:
    st.session_state.df_clientes, st.session_state.df_obras = load_data()

df_clientes = st.session_state.df_clientes
df_obras    = st.session_state.df_obras

# =====================================
# FUNÇÕES AUXILIARES - PDF
# =====================================
def extrair_texto_pdf(pdf_file):
    try:
        with pdfplumber.open(pdf_file) as pdf:
            texto = []
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    texto.append(t)
            return "\n".join(texto).strip()
    except Exception as e:
        st.error(f"Erro ao ler PDF: {e}")
        return ""

def brl_to_float(valor_txt):
    try:
        v = str(valor_txt).strip().replace("R$", "").strip()
        v = v.replace(".", "").replace(",", ".")
        return float(v)
    except:
        return 0.0

def normalizar_data(data_txt):
    data_txt = str(data_txt).strip()
    patterns = [
        r"%d/%m/%Y",
        r"%d/%m/%y",
        r"%Y-%m-%d"
    ]
    for fmt in patterns:
        try:
            dt = datetime.strptime(data_txt, fmt)
            return dt.date()
        except:
            pass
    return None

def extrair_dados_pdf_solucao(texto: str):
    if not re.search(r"ORÇAMENTO", texto, re.IGNORECASE):
        return None

    dados = {
        "tipo": "Orçamento",
        "Cliente": "",
        "Numero": "",
        "Data": None,
        "TOTAL": 0.0,
        "Descricao": ""
    }

    # Cliente
    m = re.search(r"Cliente:\s*(.+?)(?:\n|$)", texto, re.I | re.M)
    if m:
        dados["Cliente"] = m.group(1).strip()

    # Número do orçamento
    m = re.search(r"ORÇAMENTO\s*[Nº°]?\s*:\s*(\d+)", texto, re.I)
    if m:
        dados["Numero"] = m.group(1).strip()

    # Data
    m = re.search(r"Criado em:\s*(\d{2}/\d{2}/\d{2,4})", texto, re.I)
    if m:
        dados["Data"] = normalizar_data(m.group(1))

    # Total
    m = re.search(r"Total:\s*R\$\s*([\d\.\, ]+)", texto, re.I)
    if m:
        dados["TOTAL"] = brl_to_float(m.group(1))

    # Descrição (até Total ou fim)
    m = re.search(r"Descrição:\s*(.+?)(?=Total:|Venda:|Condições:|Obs:|\Z)", texto, re.I | re.DOTALL | re.M)
    if m:
        desc = m.group(1).strip()
        desc = re.sub(r"\s+", " ", desc)  # limpa espaços extras
        dados["Descricao"] = desc

    return dados

# =====================================
# INTERFACE PRINCIPAL
# =====================================
st.title("🏗️ ObraGestor Pro")
st.markdown("Gestão simples de clientes e obras")

tab1, tab2, tab3 = st.tabs(["📄 Importar Orçamento PDF", "👥 Clientes", "🛠️ Obras"])

with tab1:
    st.subheader("Importar orçamento em PDF (formato Solução Reforma e Construção)")

    uploaded_file = st.file_uploader("Escolha o PDF do orçamento", type=["pdf"])

    if uploaded_file is not None:
        with st.spinner("Extraindo informações do PDF..."):
            texto = extrair_texto_pdf(uploaded_file)
            dados_extraidos = extrair_dados_pdf_solucao(texto)

        if dados_extraidos:
            st.success("Dados extraídos com sucesso!")
            st.json(dados_extraidos)

            col1, col2 = st.columns(2)
            with col1:
                cliente_nome = st.text_input("Cliente", value=dados_extraidos["Cliente"])
            with col2:
                valor_total = st.number_input("Valor Total (R$)", value=dados_extraidos["TOTAL"], step=100.0)

            descricao = st.text_area("Descrição do serviço", value=dados_extraidos["Descricao"], height=150)
            data_orc = st.date_input("Data do Orçamento", value=dados_extraidos["Data"] or date.today())

            if st.button("Cadastrar Obra a partir deste orçamento", type="primary"):
                novo_id = len(df_obras) + 1
                nova_obra = {
                    "ID": novo_id,
                    "Cliente": cliente_nome,
                    "Status": "Orçado",
                    "Data_Contato": date.today(),
                    "Data_Visita": None,
                    "Data_Orcamento": data_orc,
                    "Data_Aceite": None,
                    "Data_Conclusao": None,
                    "Custo_MO": 0.0,
                    "Custo_Material": 0.0,
                    "Total": valor_total,
                    "Entrada": 0.0,
                    "Pago": False,
                    "Descricao": descricao,
                    "Numero_Orcamento": dados_extraidos["Numero"]
                }

                df_obras = pd.concat([df_obras, pd.DataFrame([nova_obra])], ignore_index=True)
                save_data(df_clientes, df_obras)
                st.session_state.df_obras = df_obras
                st.success(f"Obra cadastrada com sucesso! ID: {novo_id}")
        else:
            st.warning("Não foi possível identificar um orçamento válido neste PDF.")

with tab2:
    st.subheader("Clientes cadastrados")
    st.dataframe(df_clientes)

with tab3:
    st.subheader("Obras cadastradas")
    st.dataframe(df_obras)

# Botão de debug / salvar manual
if st.sidebar.button("Forçar salvamento dos dados"):
    save_data(df_clientes, df_obras)
    st.sidebar.success("Dados salvos manualmente!")

st.sidebar.markdown("---")
st.sidebar.info("Versão 0.1 – Ainda em desenvolvimento")
