import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time as dtime
import urllib.parse
import pdfplumber
import re
import os
from fpdf import FPDF
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# =========================
# CONFIGURAÇÃO GERAL
# =========================
st.set_page_config(
    page_title="ObraGestor Pro",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# CSS VISUAL (O SEU ANTIGO)
st.markdown(
    """
    <style>
      .block-container { 
          padding-top: 1rem; 
          padding-bottom: 3rem; 
          max-width: 1200px; 
      }
      .card {
          background: #ffffff;
          border: 1px solid #e0e0e0;
          border-radius: 12px;
          padding: 15px;
          box-shadow: 0 1px 3px rgba(0,0,0,0.1);
          margin-bottom: 10px;
      }
      .alert-card {
          background-color: #FEF3C7;
          border-left: 5px solid #F59E0B;
          padding: 15px;
          border-radius: 8px;
          margin-bottom: 20px;
      }
      .kpi-title { font-size: 14px; opacity: .70; font-weight: 500; }
      .kpi-value { font-size: 24px; font-weight: 800; color: #333; }
      div[data-testid="stExpander"] div[role="button"] p { font-size: 1.1rem; font-weight: 600; }
    </style>
    """,
    unsafe_allow_html=True,
)

# =========================
# CONEXÃO GOOGLE SHEETS (O MOTOR NOVO)
# =========================
def conectar_gsheets():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds_dict = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        return client
    except: return None

# Função para carregar tudo de uma vez e separar Clientes e Obras
def load_data():
    client = conectar_gsheets()
    df = pd.DataFrame()
    if client:
        try:
            sheet = client.open("Gestao_Obras").sheet1
            dados = sheet.get_all_values()
            if len(dados) > 1:
                # Força 13 Colunas (Padrão Novo)
                cols = ["ID", "Status", "DataContato", "DataEnvio", "Cliente", "Telefone", 
                        "Endereco", "Descricao", "Observacao", "Valor", "Pagamento", 
                        "DataEntrada", "DataRestante"]
                
                linhas = dados[1:]
                df = pd.DataFrame(linhas)
                if len(df.columns) >= 13:
                    df = df.iloc[:, :13]
                    df.columns = cols
                else:
                    for i in range(13 - len(df.columns)): df[len(df.columns)] = ""
                    df.columns = cols
        except: pass
    
    # Tratamento de Tipos
    if not df.empty:
        df["Valor"] = pd.to_numeric(df["Valor"], errors="coerce").fillna(0.0)
        df["ID"] = pd.to_numeric(df["ID"], errors="coerce").fillna(0).astype(int)
    
    return df

# Função para salvar no Google Sheets
def save_data_gsheets(df):
    client = conectar_gsheets()
    if client:
        try:
            sheet = client.open("Gestao_Obras").sheet1
            sheet.clear() # Limpa tudo
            
            # Cabeçalho
            cols = ["ID", "Status", "DataContato", "DataEnvio", "Cliente", "Telefone", 
                    "Endereco", "Descricao", "Observacao", "Valor", "Pagamento", 
                    "DataEntrada", "DataRestante"]
            
            # Prepara dados para subir
            dados_lista = [cols] + df.astype(str).values.tolist()
            sheet.update(dados_lista)
            return True
        except: return False
    return False

# =========================
# FUNÇÕES DE SUPORTE
# =========================
def br_money(x):
    try: return f"R$ {float(x):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except: return "R$ 0,00"

def link_maps(endereco):
    return "https://www.google.com/maps/search/?api=1&query=" + urllib.parse.quote(str(endereco))

def link_calendar(titulo, data, local):
    if not data: return "#"
    try:
        dt_str = pd.to_datetime(data).strftime("%Y%m%dT090000")
        dt_end = pd.to_datetime(data).strftime("%Y%m%dT100000")
        base = "https://calendar.google.com/calendar/render?action=TEMPLATE"
        params = f"&text={urllib.parse.quote(titulo)}&dates={dt_str}/{dt_end}&location={urllib.parse.quote(str(local))}"
        return base + params
    except: return "#"

# =========================
# PDF & EXTRAÇÃO
# =========================
class PDFOrcamento(FPDF):
    def header(self):
        try: self.image("logo.png", 10, 8, 30)
        except: pass
        self.set_font('Arial', 'B', 14)
        self.cell(0, 8, 'Solução Reforma e Construção', 0, 1, 'C')
        self.set_font('Arial', '', 9)
        self.cell(0, 5, 'CNPJ: 46.580.382/0001-70 | (86) 9.9813-2225', 0, 1, 'C')
        self.ln(10)

def gerar_pdf_bytes(obra):
    pdf = PDFOrcamento()
    pdf.add_page()
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, f"ORÇAMENTO Nº {obra['ID']}", 0, 1, 'L')
    
    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 6, f"Cliente: {obra['Cliente']}", 0, 1)
    pdf.cell(0, 6, f"Data: {obra['DataEnvio']}", 0, 1)
    pdf.ln(5)
    
    pdf.set_fill_color(240,240,240)
    pdf.multi_cell(0, 6, f"DESCRIÇÃO:\n{obra['Descricao']}", 1, 'L', True)
    pdf.ln(5)
    
    pdf.set_font('Arial', 'B', 12)
    val = float(obra.get("Valor", 0))
    pdf.cell(0, 10, f"TOTAL: {br_money(val)}", 1, 1, 'R')
    return pdf.output(dest='S').encode('latin-1')

def ler_pdf(arq):
    texto = ""
    with pdfplumber.open(arq) as pdf:
        for p in pdf.pages: texto += p.extract_text() + "\n"
    d = {"Cliente":"", "Valor":0.0, "Descricao":texto}
    for l in texto.split('\n'):
        if "cliente:" in l.lower(): d["Cliente"] = l.split(":",1)[1].strip()
        elif "total:" in l.lower():
            try: d["Valor"] = float(re.findall(r'[\d.,]+', l)[-1].replace('.','').replace(',','.'))
            except: pass
    return d

# =========================
# MAIN APP
# =========================
df_obras = load_data()

st.sidebar.title("🏗️ ObraGestor Pro")
menu = st.sidebar.radio("Navegação", ["Dashboard", "Gestão de Obras", "Importar PDF"])

if menu == "Dashboard":
    st.markdown("### Visão Geral")
    
    total_val = 0.0
    ativas = 0
    if not df_obras.empty:
        total_val = df_obras["Valor"].sum()
        ativas = len(df_obras[~df_obras["Status"].isin(["Fechado", "Cancelado"])])
    
    c1, c2, c3 = st.columns(3)
    c1.markdown(f"<div class='card'><div class='kpi-title'>Obras Ativas</div><div class='kpi-value'>{ativas}</div></div>", unsafe_allow_html=True)
    c2.markdown(f"<div class='card'><div class='kpi-title'>Total Orçado</div><div class='kpi-value'>{br_money(total_val)}</div></div>", unsafe_allow_html=True)
    c3.markdown(f"<div class='card'><div class='kpi-title'>Clientes</div><div class='kpi-value'>{len(df_obras)}</div></div>", unsafe_allow_html=True)

    # AGENDA
    st.write("")
    if not df_obras.empty:
        hj = datetime.now().date().strftime("%d/%m/%Y")
        avisos = []
        for i, r in df_obras.iterrows():
            if str(r.get("DataEntrada")) == hj: avisos.append(f"💰 Receber Entrada: **{r['Cliente']}**")
            if str(r.get("DataRestante")) == hj: avisos.append(f"🏁 Receber Final: **{r['Cliente']}**")
            
        if avisos:
            st.markdown("<div class='alert-card'><h4>📅 Agenda de Hoje</h4>" + "<br>".join(avisos) + "</div>", unsafe_allow_html=True)

elif menu == "Gestão de Obras":
    st.markdown("### Gestão de Obras")
    
    # Seletor de Cliente
    lista_clientes = ["Nova Obra"] + sorted(df_obras["Cliente"].unique().tolist()) if not df_obras.empty else ["Nova Obra"]
    cli_sel = st.selectbox("Selecione Obra/Cliente:", lista_clientes)
    
    dados = {}
    if cli_sel != "Nova Obra":
        dados = df_obras[df_obras["Cliente"] == cli_sel].iloc[-1].to_dict()
    
    # AÇÕES RÁPIDAS
    if cli_sel != "Nova Obra":
        c_act1, c_act2 = st.columns(2)
        link_w = link_maps(dados.get("Endereco",""))
        link_c = link_calendar(f"Visita {cli_sel}", dados.get("DataContato"), dados.get("Endereco"))
        
        c_act1.markdown(f'''<a href="{link_c}" target="_blank"><button>📅 Agendar Visita</button></a>''', unsafe_allow_html=True)
        c_act2.markdown(f'''<a href="{link_w}" target="_blank"><button>📍 Abrir Mapa</button></a>''', unsafe_allow_html=True)
        st.divider()

    # FORMULÁRIO
    with st.form("form_obra"):
        status = st.selectbox("Status", ["Contato", "Visita", "Orçamento", "Fechado"], 
                              index=["Contato", "Visita", "Orçamento", "Fechado"].index(dados.get("Status", "Contato")) if dados.get("Status") in ["Contato", "Visita", "Orçamento", "Fechado"] else 0)
        
        c1, c2 = st.columns(2)
        nome = c1.text_input("Cliente", value=dados.get("Cliente",""))
        fone = c2.text_input("Telefone", value=dados.get("Telefone",""))
        end = st.text_input("Endereço", value=dados.get("Endereco",""))
        
        d1, d2, d3, d4 = st.columns(4)
        def dt_val(v): 
            try: return pd.to_datetime(v).date()
            except: return datetime.now().date()
            
        dt_cont = d1.date_input("Contato", value=dt_val(dados.get("DataContato")))
        dt_env = d2.date_input("Envio", value=dt_val(dados.get("DataEnvio")))
        dt_ent = d3.date_input("Entrada", value=dt_val(dados.get("DataEntrada")))
        dt_rest = d4.date_input("Final", value=dt_val(dados.get("DataRestante")))
        
        desc = st.text_area("Descrição", value=dados.get("Descricao",""))
        obs = st.text_area("Obs Interna", value=dados.get("Observacao",""))
        
        c3, c4 = st.columns(2)
        val = c3.number_input("Valor Total", value=float(dados.get("Valor", 0.0)))
        pag = c4.text_input("Pagamento", value=dados.get("Pagamento",""))
        
        if st.form_submit_button("💾 SALVAR DADOS"):
            # Atualiza DataFrame
            novo_id = int(dados.get("ID", 0)) if dados.get("ID") else (df_obras["ID"].max() + 1 if not df_obras.empty else 1)
            
            nova_linha = {
                "ID": novo_id, "Status": status, "Cliente": nome, "Telefone": fone, "Endereco": end,
                "DataContato": dt_cont, "DataEnvio": dt_env, "DataEntrada": dt_ent, "DataRestante": dt_rest,
                "Descricao": desc, "Observacao": obs, "Valor": val, "Pagamento": pag
            }
            
            # Remove antigo se existir e adiciona novo
            if cli_sel != "Nova Obra":
                df_obras = df_obras[df_obras["ID"] != novo_id]
            
            df_obras = pd.concat([df_obras, pd.DataFrame([nova_linha])], ignore_index=True)
            
            if save_data_gsheets(df_obras):
                st.success("Salvo no Google Sheets!")
                st.rerun()
            else:
                st.error("Erro ao salvar no Google Sheets.")
    
    if cli_sel != "Nova Obra":
        st.download_button("⬇️ Baixar PDF", gerar_pdf_bytes(dados), f"Orc_{cli_sel}.pdf")

elif menu == "Importar PDF":
    st.markdown("### Importar Orçamento Antigo")
    arq = st.file_uploader("Selecione PDF", type="pdf")
    if arq:
        dados = ler_pdf(arq)
        st.info("Dados lidos! Copie abaixo para cadastrar:")
        st.json(dados)
