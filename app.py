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
        background: rgba(255,255,255,0.92);
        border: 1px solid rgba(0,0,0,0.06);
        border-radius: 16px;
        padding: 16px 16px;
        box-shadow: 0 10px 22px rgba(0,0,0,0.06);
      }
      .kpi-title { font-size: 13px; opacity: .70; margin-bottom: 4px; }
      .kpi-value { font-size: 28px; font-weight: 800; margin-bottom: 2px; }
      .kpi-sub { font-size: 13px; opacity: .75; }
      .soft { opacity: .70; font-size: 13px; }
      .section-title { font-size: 22px; font-weight: 800; margin: 8px 0 6px; }
    </style>
    """,
    unsafe_allow_html=True,
)

CLIENTES_FILE = "clientes.csv"
OBRAS_FILE = "obras.csv"

# =========================
# SAFE HELPERS
# =========================
def br_money(x) -> str:
    try:
        return "R$ " + f"{float(x):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "R$ 0,00"

def normalize_status(s):
    s = str(s or "").strip()
    if s == "" or s.lower() == "nan":
        return "🔵 Agendamento"
    return s

def col_or(df, col, default):
    if df is None or df.empty:
        return default
    return df[col] if col in df.columns else default

def ensure_cols(df, cols_defaults: dict):
    if df is None:
        df = pd.DataFrame()
    for c, d in cols_defaults.items():
        if c not in df.columns:
            df[c] = d
    return df

def assinatura_obra(row):
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
        df_o = pd.DataFrame(columns=[
            "ID", "Cliente", "Status",
            "Data_Contato", "Data_Visita", "Data_Orcamento", "Data_Aceite", "Data_Conclusao",
            "Custo_MO", "Custo_Material", "Total", "Entrada", "Pago", "Descricao",
        ])
        df_o.to_csv(OBRAS_FILE, index=False)
    else:
        df_o = pd.read_csv(OBRAS_FILE)

    df_c = ensure_cols(df_c, {
        "ID": None, "Nome": "", "Telefone": "", "Email": "", "Endereco": "", "Data_Cadastro": ""
    })
    df_o = ensure_cols(df_o, {
        "ID": None, "Cliente": "", "Status": "🔵 Agendamento",
        "Data_Contato": None, "Data_Visita": None, "Data_Orcamento": None, "Data_Aceite": None, "Data_Conclusao": None,
        "Custo_MO": 0.0, "Custo_Material": 0.0, "Total": 0.0, "Entrada": 0.0, "Pago": False, "Descricao": ""
    })

    # normalize
    df_c["Nome"] = df_c["Nome"].astype(str).replace("nan", "").fillna("").str.strip()
    for col in ["Telefone", "Email", "Endereco"]:
        df_c[col] = df_c[col].astype(str).replace("nan", "").fillna("").str.strip()

    df_o["Cliente"] = df_o["Cliente"].astype(str).replace("nan", "").fillna("").str.strip()
    df_o["Status"] = df_o["Status"].apply(normalize_status)
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
# CLEANUP (no crash)
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

    max_id = int(df["ID"].max()) if df["ID"].notna().any() else 0
    missing = df.index[df["ID"].isna()].tolist()
    for i in missing:
        max_id += 1
        df.at[i, "ID"] = max_id

    df["ID"] = df["ID"].astype(int)
    df = df.drop_duplicates(subset=["ID"], keep="last")

    dt = pd.to_datetime(df["Data_Orcamento"], errors="coerce")
    df["_dt"] = dt
    df = df.sort_values(["_sig", "_dt"]).drop_duplicates(subset=["_sig"], keep="last")
    df = df.drop(columns=["_sig", "_dt"])
    return df.reset_index(drop=True)

# =========================
# PDF (kept)
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
            return datetime.strptime(data_txt
