import streamlit as st
import pandas as pd
from fpdf import FPDF
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import datetime
import pdfplumber
import re

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Solução Gestor", layout="wide", page_icon="🏗️")

if st.sidebar.button("🔄 Atualizar"):
    st.cache_data.clear()
    st.rerun()

# --- DADOS ---
EMP_NOME = "SOLUÇÃO REFORMA E CONSTRUÇÃO"
EMP_CNPJ = "CNPJ: 46.580.382/0001-70"
EMP_ENDERECO = "Rua Bandeirantes, 1303, Pedra Mole - Teresina/PI | CEP: 64065-040"
EMP_CONTATO = "Tel: (86) 9.9813-2225 | Email: solucoesreformaseconstrucao@gmail.com"

# --- CONEXÃO ---
def conectar_gsheets():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds_dict = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        return client
    except: return None

# --- CARREGAR DADOS ---
def carregar_dados():
    client = conectar_gsheets()
    if client:
        try:
            sheet = client.open("Gestao_Obras").sheet1
            dados = sheet.get_all_values()
            if len(dados) < 2: return pd.DataFrame()
            
            # Força nomes das 13 colunas
            cols = ["ID", "Status", "DataContato", "DataEnvio", "Cliente", "Telefone", 
                    "Endereco", "Descricao", "Observacao", "Valor", "Pagamento", 
                    "DataEntrada", "DataRestante"]
            
            linhas = dados[1:]
            df = pd.DataFrame(linhas)
            
            # Ajusta tamanho
            if len(df.columns) >= 13:
                df = df.iloc[:, :13]
                df.columns = cols
            else:
                for i in range(13 - len(df.columns)): df[len(df.columns)] = ""
                df.columns = cols
            return df
        except: return pd.DataFrame()
    return pd.DataFrame()

def salvar_obra(dados):
    client = conectar_gsheets()
    if client:
        try:
            sheet = client.open("Gestao_Obras").sheet1
            def fmt(d): return d.strftime("%d/%m/%Y") if hasattr(d, 'strftime') else str(d)
            row = [
                str(dados["ID"]), str(dados["Status"]), fmt(dados["DataContato"]), fmt(dados["DataEnvio"]),
                str(dados["Cliente"]), str(dados["Telefone"]), str(dados["Endereco"]),
                str(dados["Descricao"]), str(dados["Observacao"]), str(dados["Valor"]), 
                str(dados["Pagamento"]), fmt(dados["DataEntrada"]), fmt(dados["DataRestante"])
            ]
            sheet.append_row(row)
            st.toast("✅ Salvo!", icon="💾")
            return True
        except: 
            st.error("Erro ao salvar.")
            return False
    return False

# --- PDF ---
class PDF(FPDF):
    def header(self):
        try: self.image("logo.png", 10, 8, 30)
        except: pass
        self.set_font('Arial', 'B', 12)
        self.cell(0, 5, EMP_NOME, 0, 1, 'R')
        self.set_font('Arial', '', 8)
        self.cell(0, 5, EMP_CNPJ, 0, 1, 'R')
        self.cell(0, 5, EMP_ENDERECO, 0, 1, 'R')
        self.cell(0, 5, EMP_CONTATO, 0, 1, 'R')
        self.ln(10)
    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 7)
        self.cell(0, 10, 'Documento Oficial', 0, 0, 'C')

def gerar_orcamento(obra):
    pdf = PDF()
    pdf.add_page()
    pdf.set_font('Arial', 'B', 16)
    pdf.cell(0, 10, 'ORÇAMENTO', 0, 1, 'C')
    pdf.ln(5)
    
    pdf.set_fill_color(240,240,240)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 8, " DADOS DO CLIENTE", 0, 1, 'L', 1)
    pdf.set_font("Arial", size=10)
    pdf.ln(2)
    pdf.cell(0, 6, f"Cliente: {obra['Cliente']}", 0, 1)
    pdf.cell(0, 6, f"Data: {obra['DataEnvio']}", 0, 1)
    pdf.cell(0, 6, f"Telefone: {obra['Telefone']}", 0, 1)
    pdf.cell(0, 6, f"Endereço: {obra['Endereco']}", 0, 1)
    pdf.ln(5)
    
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 8, " DESCRIÇÃO", 0, 1, 'L', 1)
    pdf.ln(2)
    pdf.set_font("Arial", size=10)
    pdf.multi_cell(0, 6, str(obra['Descricao']))
    pdf.ln(5)
    
    if str(obra['Observacao']).strip():
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(0, 8, " OBSERVAÇÕES", 0, 1, 'L', 1)
        pdf.ln(2)
        pdf.set_font("Arial", size=9)
        pdf.multi_cell(0, 5, str(obra['Observacao']))
        pdf.ln(5)
    
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 12, f"TOTAL: R$ {obra['Valor']}", 1, 1, 'R')
    return pdf.output(dest='S').encode('latin-1')

def gerar_recibo(obra):
    pdf = PDF()
    pdf.add_page()
    pdf.ln(10)
    pdf.set_font('Arial', 'B', 20)
    pdf.cell(0, 15, 'RECIBO', 0, 1, 'C')
    pdf.ln(10)
    pdf.set_font('Arial', '', 12)
    texto = f"Recebemos de {obra['Cliente']}\n R$ {obra['Valor']}\nReferente a: {obra['Endereco']}.\nTeresina, {datetime.date.today().strftime('%d/%m/%Y')}"
    pdf.multi_cell(0, 9, texto, border=1, align='C')
    pdf.ln(30)
    pdf.cell(0, 5, "_______________________", 0, 1, 'C')
    pdf.cell(0, 5, EMP_NOME, 0, 1, 'C')
    return pdf.output(dest='S').encode('latin-1')

def ler_pdf(arq):
    texto = ""
    with pdfplumber.open(arq) as pdf:
        for p in pdf.pages: texto += p.extract_text() + "\n"
    d = {"Cliente":"", "Telefone":"", "Endereco":"", "Valor":0.0, "Descricao":texto}
    for l in texto.split('\n'):
        low = l.lower()
        if "cliente:" in low: d["Cliente"] = l.split(":",1)[1].strip()
        elif "total:" in low:
            try: d["Valor"] = float(re.findall(r'[\d.,]+', l)[-1].replace('.','').replace(',','.'))
            except: pass
    return d

# --- INTERFACE ---
if 'dados_imp' not in st.session_state: st.session_state['dados_imp'] = {}

st.sidebar.title("Solução Gestor")
menu = st.sidebar.radio("Menu", ["Dashboard", "Novo Orçamento", "Gerenciar"])

if menu == "Dashboard":
    st.title("📊 Painel")
    df = carregar_dados()
    if not df.empty:
        # Agenda
        hj = datetime.date.today().strftime("%d/%m/%Y")
        avisos = []
        if 'DataEntrada' in df.columns:
            for i,r in df.iterrows():
                if str(r['DataEntrada']) == hj: avisos.append(f"💰 Entrada: {r['Cliente']}")
        if avisos: 
            for a in avisos: st.warning(a)
        else: st.success("Agenda Livre")
        
        st.write("---")
        # Status (CORREÇÃO AQUI: st.primary não existe, troquei por st.info)
        if 'Status' in df.columns:
            c1, c2, c3, c4 = st.columns(4)
            with c1: 
                st.info("📞 **Contato**")
                for i,r in df[df['Status']=='Contato'].iterrows(): st.write(f"{r['Cliente']}")
            with c2: 
                st.warning("📐 **Visita**")
                for i,r in df[df['Status']=='Visita'].iterrows(): st.write(f"{r['Cliente']}")
            with c3: 
                st.error("📝 **Orçamento**") # Usei st.error (vermelho) pra destacar
                for i,r in df[df['Status']=='Orçamento'].iterrows(): st.write(f"{r['Cliente']}")
            with c4: 
                st.success("✅ **Fechado**")
                for i,r in df[df['Status']=='Fechado'].iterrows(): st.write(f"{r['Cliente']}")
    else: st.info("Sem dados.")

elif menu == "Novo Orçamento":
    st.title("📝 Cadastro")
    with st.expander("Importar PDF"):
        arq = st.file_uploader("Upload", type="pdf")
        if arq: st.session_state['dados_imp'] = ler_pdf(arq)
    
    mem = st.session_state['dados_imp']
    with st.form("form"):
        status = st.selectbox("Status", ["Contato", "Visita", "Orçamento", "Fechado"])
        c1, c2 = st.columns(2)
        cli = c1.text_input("Cliente", value=mem.get("Cliente",""))
        tel = c2.text_input("Telefone", value=mem.get("Telefone",""))
        end = st.text_input("Endereço", value=mem.get("Endereco",""))
        
        d1,d2,d3,d4 = st.columns(4)
        dt1 = d1.date_input("Contato", datetime.date.today())
        dt2 = d2.date_input("Envio", datetime.date.today())
        dt3 = d3.date_input("Entrada", datetime.date.today())
        dt4 = d4.date_input("Final", datetime.date.today())
        
        desc = st.text_area("Descrição", value=mem.get("Descricao",""), height=100)
        obs = st.text_area("Obs", value=mem.get("Observacao",""), height=60)
        
        c3, c4 = st.columns(2)
        val = c3.number_input("Valor", value=float(mem.get("Valor",0.0)), step=50.0)
        pag = c4.text_input("Pagamento", value=mem.get("Pagamento",""))
        
        if st.form_submit_button("Salvar"):
            if cli:
                id_u = datetime.datetime.now().strftime("%Y%m%d%H%M")
                dados = {
                    "ID": id_u, "Status": status, "DataContato": dt1, "DataEnvio": dt2,
                    "Cliente": cli, "Telefone": tel, "Endereco": end,
                    "Descricao": desc, "Observacao": obs, "Valor": val, "Pagamento": pag,
                    "DataEntrada": dt3, "DataRestante": dt4
                }
                salvar_obra(dados)
                st.session_state['dados_imp'] = {}
            else: st.warning("Nome!")

elif menu == "Gerenciar":
    st.title("📂 Obras")
    df = carregar_dados()
    if not df.empty:
        cols = [c for c in ['Status', 'Cliente', 'Valor', 'DataEnvio'] if c in df.columns]
        st.dataframe(df[cols])
        sel = st.selectbox("Cliente:", df['Cliente'].unique())
        if sel:
            obra = df[df['Cliente'] == sel].iloc[-1]
            c1,c2 = st.columns(2)
            with c1: st.download_button("Orçamento", gerar_orcamento(obra), f"Orc_{sel}.pdf")
            with c2: st.download_button("Recibo", gerar_recibo(obra), f"Rec_{sel}.pdf")
