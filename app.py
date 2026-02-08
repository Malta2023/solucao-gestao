import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time as dtime
import urllib.parse
import pdfplumber
import re
import os
from fpdf import FPDF
import requests
from io import StringIO

# =========================
# CONFIGURAÇÃO GERAL
# =========================
st.set_page_config(
    page_title="ObraGestor Pro",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# CSS
st.markdown(
    """
    <style>
      .block-container { padding-top: 3.5rem; padding-bottom: 3rem; max-width: 1200px; }
      .card { background: rgba(255,255,255,0.95); border: 1px solid rgba(0,0,0,0.08); border-radius: 16px; padding: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.04); margin-bottom: 15px; }
      .kpi-title { font-size: 14px; opacity: .70; margin-bottom: 4px; font-weight: 500; }
      .kpi-value { font-size: 26px; font-weight: 800; color: #1f2937; }
      .stButton>button { width: 100%; height: 3.2em; border-radius: 12px; font-weight: 600; }
    </style>
    """,
    unsafe_allow_html=True,
)

CLIENTES_FILE = "clientes.csv"
OBRAS_FILE = "obras.csv"

def br_money(x) -> str:
    try:
        val = float(x)
        return f"R$ {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except: return "R$ 0,00"

def ensure_cols(df, cols_defaults: dict):
    if df is None: df = pd.DataFrame()
    for c, d in cols_defaults.items():
        if c not in df.columns: df[c] = d
    return df

def normalize_status(s):
    s = str(s or "").strip()
    if s == "" or s.lower() == "nan": return "🔵 Agendamento"
    return s

def load_data():
    if os.path.exists(CLIENTES_FILE): df_c = pd.read_csv(CLIENTES_FILE)
    else: df_c = pd.DataFrame(columns=["ID", "Nome", "Telefone", "Email", "Endereco", "Data_Cadastro"])
    
    if os.path.exists(OBRAS_FILE): df_o = pd.read_csv(OBRAS_FILE)
    else: df_o = pd.DataFrame(columns=["ID", "Cliente", "Status", "Data_Contato", "Data_Visita", "Data_Orcamento", "Data_Aceite", "Data_Conclusao", "Custo_MO", "Custo_Material", "Total", "Entrada", "Pago", "Descricao", "Observacoes"])

    df_c = ensure_cols(df_c, {"ID": None, "Nome": "", "Telefone": "", "Email": "", "Endereco": "", "Data_Cadastro": ""})
    df_o = ensure_cols(df_o, {"ID": None, "Cliente": "", "Status": "🔵 Agendamento", "Custo_MO": 0.0, "Custo_Material": 0.0, "Total": 0.0, "Entrada": 0.0, "Pago": False})

    for col in ["Custo_MO", "Custo_Material", "Total", "Entrada"]:
        df_o[col] = pd.to_numeric(df_o[col], errors="coerce").fillna(0.0)
    for col in ["Data_Visita", "Data_Orcamento", "Data_Conclusao", "Data_Contato"]:
        df_o[col] = pd.to_datetime(df_o[col], errors="coerce").dt.date
    return df_c, df_o

def save_data(df_c, df_o):
    df_c.to_csv(CLIENTES_FILE, index=False)
    df_o.to_csv(OBRAS_FILE, index=False)

# --- PDF E INTERFACE (Omitido aqui por brevidade, mas está no arquivo completo) ---
# [O RESTANTE DO CÓDIGO QUE ANALISAMOS ANTES]
