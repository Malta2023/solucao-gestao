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
            df_o["Pago"] = df_o["Pago"].astype(str).str.strip().str.lower().isin(["true", "1", "yes", "sim"])
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
# CLEANUP
# =========================
def limpar_obras(df):
    if df is None or df.empty:
        return df

    df = df.copy()
    df["Cliente"] = df["Cliente"].astype(str).replace("nan", "").fillna("").str.strip()
    df = df[df["Cliente"] != ""]

    df["ID"] = pd.to_numeric(df["ID"], errors="coerce")
    df["_sig"] = df.apply(assinatura_obra, axis=1)

    max_id = int(df["ID"].max()) if df["ID"].notna().any() else 0
    for i in df.index[df["ID"].isna()].tolist():
        max_id += 1
        df.at[i, "ID"] = max_id

    df["ID"] = df["ID"].astype(int)
    df = df.drop_duplicates(subset=["ID"], keep="last")

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

        return None
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
        ba
