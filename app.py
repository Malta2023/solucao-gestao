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
    if "Cli
