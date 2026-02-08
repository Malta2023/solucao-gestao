import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time as dtime
import urllib.parse
import pdfplumber
import re
import os
from fpdf import FPDF

# =========================
# CONFIGURAÇÃO GERAL
# =========================
st.set_page_config(
    page_title="ObraGestor Pro",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# CSS VISUAL
st.markdown(
    """
    <style>
      .block-container { padding-top: 1rem; padding-bottom: 3rem; max-width: 1200px; }
      .card { background: #ffffff; border: 1px solid #e0e0e0; border-radius: 12px; padding: 15px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 10px; }
      .alert-card { background-color: #FEF3C7; border-left: 5px solid #F59E0B; padding: 15px; border-radius: 8px; margin-bottom: 20px; }
      .kpi-title { font-size: 14px; opacity: .70; font-weight: 500; }
      .kpi-value { font-size: 24px; font-weight: 800; color: #333; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ARQUIVO LOCAL (SIMPLES E FUNCIONAL)
OBRAS_FILE = "obras_local.csv"

# =========================
# FUNÇÕES
# =========================
def load_data():
    if not os.path.exists(OBRAS_FILE):
        df = pd.DataFrame(columns=["ID", "Cliente", "Status", "Total", "Pago", "Data_Contato", "Data_Visita", "Descricao", "Endereco", "Telefone"])
        return df
    return pd.read_csv(OBRAS_FILE)

def save_data(df):
    df.to_csv(OBRAS_FILE, index=False)

def br_money(val):
    try: return f"R$ {float(val):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except: return "R$ 0,00"

def link_calendar(titulo, data, local):
    if pd.isnull(data): return "#"
    try:
        dt_str = pd.to_datetime(data).strftime("%Y%m%dT090000")
        dt_end = pd.to_datetime(data).strftime("%Y%m%dT100000")
        base = "https://calendar.google.com/calendar/render?action=TEMPLATE"
        params = f"&text={urllib.parse.quote(str(titulo))}&dates={dt_str}/{dt_end}&location={urllib.parse.quote(str(local))}"
        return base + params
    except: return "#"

# PDF
class PDFOrcamento(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 14)
        self.cell(0, 8, 'SOLUCAO REFORMA E CONSTRUCAO', 0, 1, 'C')
        self.set_font('Arial', '', 9)
        self.cell(0, 5, 'CNPJ: 46.580.382/0001-70', 0, 1, 'C')
        self.ln(5)

def gerar_pdf_bytes(dados):
    pdf = PDFOrcamento()
    pdf.add_page()
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, f"ORCAMENTO #{dados['ID']}", 0, 1)
    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 6, f"Cliente: {dados['Cliente']}", 0, 1)
    pdf.cell(0, 6, f"Data: {datetime.now().strftime('%d/%m/%Y')}", 0, 1)
    pdf.ln(5)
    pdf.multi_cell(0, 6, f"Descricao:\n{dados['Descricao']}", 1)
    pdf.ln(5)
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, f"TOTAL: {br_money(dados['Total'])}", 1, 1, 'R')
    return pdf.output(dest='S').encode('latin-1')

# LEITOR PDF
def ler_pdf(arquivo):
    text = ""
    with pdfplumber.open(arquivo) as pdf:
        for p in pdf.pages: text += p.extract_text() + "\n"
    dados = {"Cliente": "", "Total": 0.0, "Descricao": text}
    for l in text.split('\n'):
        if "cliente:" in l.lower(): dados["Cliente"] = l.split(":", 1)[1].strip()
        if "total:" in l.lower(): 
            try: dados["Total"] = float(re.findall(r'[\d.,]+', l)[-1].replace('.','').replace(',','.'))
            except: pass
    return dados

# =========================
# APP PRINCIPAL
# =========================
df = load_data()

st.sidebar.title("🏗️ ObraGestor Local")
menu = st.sidebar.radio("Menu", ["Dashboard", "Gestão de Obras", "Importar PDF"])

if menu == "Dashboard":
    st.title("📊 Painel Geral")
    
    total = df["Total"].sum() if not df.empty else 0
    ativas = len(df[df["Status"] != "Concluído"]) if not df.empty else 0
    
    c1, c2 = st.columns(2)
    c1.markdown(f"<div class='card'><div class='kpi-title'>Obras Ativas</div><div class='kpi-value'>{ativas}</div></div>", unsafe_allow_html=True)
    c2.markdown(f"<div class='card'><div class='kpi-title'>Total Estimado</div><div class='kpi-value'>{br_money(total)}</div></div>", unsafe_allow_html=True)
    
    st.write("")
    if not df.empty:
        st.subheader("📋 Lista Rápida")
        st.dataframe(df[["ID", "Cliente", "Status", "Total", "Data_Contato"]], use_container_width=True)

elif menu == "Gestão de Obras":
    st.title("🛠️ Gestão de Obras")
    
    opcoes = ["Nova Obra"] + (df["Cliente"].unique().tolist() if not df.empty else [])
    selecao = st.selectbox("Selecione Cliente/Obra:", opcoes)
    
    dados = {}
    if selecao != "Nova Obra":
        dados = df[df["Cliente"] == selecao].iloc[-1].to_dict()
    
    # AÇÕES
    if selecao != "Nova Obra":
        c1, c2 = st.columns(2)
        link_cal = link_calendar(f"Visita {selecao}", dados.get("Data_Visita"), dados.get("Endereco"))
        c1.markdown(f'''<a href="{link_cal}" target="_blank"><button style="width:100%; padding:10px;">📅 Agendar Visita</button></a>''', unsafe_allow_html=True)
    
    # FORM
    with st.form("form_obra"):
        c1, c2 = st.columns(2)
        nome = c1.text_input("Cliente", value=dados.get("Cliente", ""))
        status = c2.selectbox("Status", ["Contato", "Visita", "Orçamento", "Concluído"], index=0)
        
        c3, c4 = st.columns(2)
        total = c3.number_input("Valor Total", value=float(dados.get("Total", 0.0)), step=50.0)
        pago = c4.checkbox("Pago?", value=bool(dados.get("Pago", False)))
        
        desc = st.text_area("Descrição", value=dados.get("Descricao", ""))
        end = st.text_input("Endereço", value=dados.get("Endereco", ""))
        
        d1, d2 = st.columns(2)
        dt_cont = d1.date_input("Data Contato", datetime.now())
        dt_vis = d2.date_input("Data Visita", datetime.now())
        
        if st.form_submit_button("💾 SALVAR OBRA"):
            novo_id = int(dados.get("ID", df["ID"].max() + 1 if not df.empty else 1))
            
            nova_linha = {
                "ID": novo_id, "Cliente": nome, "Status": status, "Total": total, 
                "Pago": pago, "Descricao": desc, "Endereco": end,
                "Data_Contato": dt_cont, "Data_Visita": dt_vis, "Telefone": ""
            }
            
            # Remove anterior e adiciona novo (atualização)
            if selecao != "Nova Obra":
                df = df[df["ID"] != novo_id]
            
            df = pd.concat([df, pd.DataFrame([nova_linha])], ignore_index=True)
            save_data(df)
            st.success("Salvo com sucesso!")
            st.rerun()

    if selecao != "Nova Obra":
        st.download_button("⬇️ Baixar PDF", gerar_pdf_bytes(dados), f"Orcamento_{selecao}.pdf")

elif menu == "Importar PDF":
    st.title("📂 Importar Orçamento")
    arq = st.file_uploader("Suba o PDF aqui", type="pdf")
    if arq:
        dados = ler_pdf(arq)
        st.success("PDF Lido! Copie os dados abaixo:")
        st.json(dados)
