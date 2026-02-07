import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time
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
    initial_sidebar_state="collapsed"
)

st.markdown(
    """
    <style>
      .block-container { padding-top: 1.2rem; padding-bottom: 2.5rem; }
      h1, h2, h3 { letter-spacing: -0.2px; }
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
        df_c = pd.DataFrame(columns=["ID", "Nome", "Telefone", "Email", "Endereco", "Data_Cadastro"])
        df_c.to_csv(CLIENTES_FILE, index=False)
    else:
        df_c = pd.read_csv(CLIENTES_FILE)

    if not os.path.exists(OBRAS_FILE):
        cols = ["ID", "Cliente", "Status", "Data_Contato", "Data_Visita", "Data_Orcamento",
                "Data_Aceite", "Data_Conclusao", "Custo_MO", "Custo_Material",
                "Total", "Entrada", "Pago", "Descricao"]
        df_o = pd.DataFrame(columns=cols)
        df_o.to_csv(OBRAS_FILE, index=False)
    else:
        df_o = pd.read_csv(OBRAS_FILE)

        # datas
        for col in ["Data_Visita", "Data_Orcamento", "Data_Conclusao"]:
            if col in df_o.columns:
                df_o[col] = pd.to_datetime(df_o[col], errors="coerce").dt.date

        # bool
        if "Pago" in df_o.columns:
            df_o["Pago"] = df_o["Pago"].fillna(False).astype(bool)

        # números
        for col in ["Custo_MO", "Custo_Material", "Total", "Entrada"]:
            if col in df_o.columns:
                df_o[col] = pd.to_numeric(df_o[col], errors="coerce").fillna(0.0)

    return df_c, df_o

def save_data(df_c, df_o):
    df_c.to_csv(CLIENTES_FILE, index=False)
    df_o.to_csv(OBRAS_FILE, index=False)

df_clientes, df_obras = load_data()

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
    except:
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
        dados["TOTAL"] = brl_to_float(m.group(1))

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

        # fallback antigo
        dados = {"tipo": None}
        text_up = text.upper()

        if "ORÇAMENTO
