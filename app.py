import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time as dtime
import urllib.parse
import pdfplumber
import re
import os

# =========================
# CONFIGURAÇÃO DA PÁGINA
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
      .block-container { 
          padding-top: 3.5rem; 
          padding-bottom: 3rem; 
          max-width: 1200px; 
      }
      .card {
          background: rgba(255,255,255,0.95);
          border: 1px solid rgba(0,0,0,0.08);
          border-radius: 16px;
          padding: 20px;
          box-shadow: 0 2px 10px rgba(0,0,0,0.04);
          margin-bottom: 15px;
      }
      .kpi-title { font-size: 14px; opacity: .70; margin-bottom: 4px; font-weight: 500; }
      .kpi-value { font-size: 26px; font-weight: 800; color: #1f2937; }
      
      @media (max-width: 600px) {
          .block-container {
              padding-top: 1.5rem;
              padding-left: 0.5rem;
              padding-right: 0.5rem;
          }
          .card { padding: 15px; margin-bottom: 10px; }
          .kpi-value { font-size: 22px; }
          h1 { font-size: 1.8rem !important; }
      }

      .stButton>button { 
          width: 100%; 
          height: 3.2em; 
          border-radius: 12px; 
          font-weight: 600;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

CLIENTES_FILE = "clientes.csv"
OBRAS_FILE = "obras.csv"

# =========================
# FUNÇÕES AUXILIARES
# =========================
def br_money(x) -> str:
    try:
        val = float(x)
        return f"R$ {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
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
    c = str(row.get("Cliente", "")).strip().lower()
    d = str(row.get("Descricao", "")).strip().lower()
    dt = str(row.get("Data_Orcamento", "")).strip()
    t = str(row.get("Total", "")).strip()
    return f"{c}||{d}||{dt}||{t}"

def link_maps(endereco):
    return "https://www.google.com/maps/search/?api=1&query=" + urllib.parse.quote(str(endereco))

def link_calendar(titulo, data_visita, hora_visita, duracao_min, local):
    inicio_dt = datetime.combine(data_visita, hora_visita)
    fim_dt = inicio_dt + timedelta(minutes=int(duracao_min))
    start = inicio_dt.strftime("%Y%m%dT%H%M%S")
    end = fim_dt.strftime("%Y%m%dT%H%M%S")
    base = "https://calendar.google.com/calendar/render?action=TEMPLATE"
    params = f"&text={urllib.parse.quote(titulo)}&dates={start}/{end}&details={urllib.parse.quote('Visita Técnica')}&location={urllib.parse.quote(str(local))}&ctz=America/Sao_Paulo"
    return base + params

# =========================
# DADOS
# =========================
def load_data():
    if not os.path.exists(CLIENTES_FILE):
        cols_c = ["ID", "Nome", "Telefone", "Email", "Endereco", "Data_Cadastro"]
        df_c = pd.DataFrame(columns=cols_c)
        df_c.to_csv(CLIENTES_FILE, index=False)
    else:
        df_c = pd.read_csv(CLIENTES_FILE)

    if not os.path.exists(OBRAS_FILE):
        cols_o = [
            "ID", "Cliente", "Status",
            "Data_Contato", "Data_Visita", "Data_Orcamento", "Data_Aceite", "Data_Conclusao",
            "Custo_MO", "Custo_Material", "Total", "Entrada", "Pago", "Descricao"
        ]
        df_o = pd.DataFrame(columns=cols_o)
        df_o.to_csv(OBRAS_FILE, index=False)
    else:
        df_o = pd.read_csv(OBRAS_FILE)

    defaults_c = {"ID": None, "Nome": "", "Telefone": "", "Email": "", "Endereco": "", "Data_Cadastro": ""}
    df_c = ensure_cols(df_c, defaults_c)

    defaults_o = {
        "ID": None, "Cliente": "", "Status": "🔵 Agendamento",
        "Data_Contato": None, "Data_Visita": None, "Data_Orcamento": None,
        "Data_Aceite": None, "Data_Conclusao": None,
        "Custo_MO": 0.0, "Custo_Material": 0.0, "Total": 0.0,
        "Entrada": 0.0, "Pago": False, "Descricao": ""
    }
    df_o = ensure_cols(df_o, defaults_o)

    df_c["Nome"] = df_c["Nome"].astype(str).replace("nan", "").fillna("").str.strip()
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

def limpar_obras(df):
    if df is None or df.empty:
        return df
    df = df.copy()
    cols_needed = {"ID": None, "Cliente": "", "Descricao": "", "Data_Orcamento": None, "Total": 0.0}
    df = ensure_cols(df, cols_needed)

    df["Cliente"] = df["Cliente"].astype(str).replace("nan", "").fillna("").str.strip()
    df = df[df["Cliente"] != ""].reset_index(drop=True)

    df["ID"] = pd.to_numeric(df["ID"], errors="coerce")
    
    max_id = 0
    if df["ID"].notna().any():
        try: max_id = int(df["ID"].max())
        except: max_id = 0

    missing_ids = df.index[df["ID"].isna()].tolist()
    for i in missing_ids:
        max_id += 1
        df.at[i, "ID"] = max_id

    df["ID"] = df["ID"].astype(int)
    df = df.drop_duplicates(subset=["ID"], keep="last")
    return df.reset_index(drop=True)

# =========================
# EXTRAÇÃO DE PDF (MELHORADA)
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
    dados = {}
    
    # 1. CLIENTE
    m = re.search(r"(?:Cliente|Para|Sr\(a\)|Nome):\s*(.+)", text, flags=re.IGNORECASE)
    if m:
        dados["Cliente"] = m.group(1).strip()

    # 2. DATA
    m = re.search(r"(\d{2}/\d{2}/\d{2,4})", text)
    if m:
        dados["Data"] = normalizar_data_ddmmaa(m.group(1))

    # 3. TOTAL (Tenta pegar o maior valor monetário encontrado no final do doc)
    valores = re.findall(r"R\$\s*([\d\.\,]+)", text)
    if valores:
        try:
            floats = [brl_to_float(v) for v in valores]
            dados["Total"] = max(floats) # Assume que o maior valor é o Total
        except:
            dados["Total"] = 0.0
    
    # 4. DESCRIÇÃO (ESTRATÉGIA NOVA)
    # Tenta pegar blocos de texto que não são cabeçalho
    # Remove linhas que tem cara de cabeçalho ou rodapé
    linhas = text.split('\n')
    desc_lines = []
    for l in linhas:
        l_clean = l.strip()
        # Ignora linhas curtas ou com palavras chave de estrutura
        if len(l_clean) < 3: continue
        if re.match(r"(Cliente|Data|Total|Orçamento|Telefone|CNPJ|R\$)", l_clean, re.IGNORECASE): continue
        desc_lines.append(l_clean)
    
    # Junta o que sobrou como descrição
    if desc_lines:
        # Pega as primeiras 5 linhas que sobraram (pra não pegar rodapé de contrato)
        dados["Descricao"] = "\n".join(desc_lines[:6])
    else:
        dados["Descricao"] = "Serviços diversos"

    # Fallback
    if "Cliente" not in dados: dados["Cliente"] = "Cliente Novo"
    if "Total" not in dados: dados["Total"] = 0.0
    if "Data" not in dados: dados["Data"] = datetime.now().strftime("%d/%m/%Y")

    return dados

def extrair_dados_pdf(pdf_file):
    text = extrair_texto_pdf(pdf_file)
    if not text:
        return None
    return extrair_dados_pdf_solucao(text)

# =========================
# LÓGICA DO DASHBOARD
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
    mapa_fase = dict(zip(ult["Cliente"].astype
