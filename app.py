import streamlit as st
import pandas as pd
from fpdf import FPDF
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import datetime
import pdfplumber
import re

# --- DADOS DA EMPRESA ---
EMP_NOME = "SOLUÇÃO REFORMA E CONSTRUÇÃO"
EMP_CNPJ = "CNPJ: 46.580.382/0001-70"
EMP_ENDERECO = "Rua Bandeirantes, 1303, Pedra Mole - Teresina/PI | CEP: 64065-040"
EMP_CONTATO = "Tel: (86) 9.9813-2225 | Email: solucoesreformaseconstrucao@gmail.com"

st.set_page_config(page_title="Solução Gestor", layout="wide", page_icon="🏗️")

# --- CONEXÃO ---
def conectar_gsheets():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds_dict = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        return client
    except: return None

# --- CARREGAR DADOS (COM PROTEÇÃO CONTRA ERRO) ---
def carregar_dados():
    client = conectar_gsheets()
    if client:
        try:
            sheet = client.open("Gestao_Obras").sheet1
            # Pega todos os dados e força recarregar
            dados = sheet.get_all_records()
            df = pd.DataFrame(dados)
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
                dados["ID"], dados["Status"],
                fmt(dados["DataContato"]), fmt(dados["DataEnvio"]),
                dados["Cliente"], dados["Telefone"], dados["Endereco"],
                dados["Descricao"], dados["Observacao"], dados["Valor"], dados["Pagamento"],
                fmt(dados["DataEntrada"]), fmt(dados["DataRestante"])
            ]
            sheet.append_row(row)
            st.toast("✅ Salvo!", icon="💾")
            return True
        except Exception as e:
            st.error(f"Erro ao salvar: {e}")
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

def gerar_pdf_orcamento(obra):
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
    pdf.cell(0, 12, f"TOTAL: R$ {obra['ValorTotal']}", 1, 1, 'R')
    return pdf.output(dest='S').encode('latin-1')

def gerar_pdf_recibo(obra):
    pdf = PDF()
    pdf.add_page()
    pdf.ln(10)
    pdf.set_font('Arial', 'B', 20)
    pdf.cell(0, 15, 'RECIBO', 0, 1, 'C')
    pdf.ln(10)
    pdf.set_font('Arial', '', 12)
    texto = f"Recebemos de {obra['Cliente']}\n R$ {obra['ValorTotal']}\nReferente a: {obra['Endereco']}.\nTeresina, {datetime.date.today().strftime('%d/%m/%Y')}"
    pdf.multi_cell(0, 9, texto, border=1, align='C')
    pdf.ln(30)
    pdf.cell(0, 5, "_______________________", 0, 1, 'C')
    pdf.cell(0, 5, EMP_NOME, 0, 1, 'C')
    return pdf.output(dest='S').encode('latin-1')

def ler_pdf(arquivo):
    texto = ""
    with pdfplumber.open(arquivo) as pdf:
        for p in pdf.pages: texto += p.extract_text() + "\n"
    dados = {"Cliente": "", "Telefone": "", "Endereco": "", "Valor": 0.0, "Descricao": texto}
    lines = texto.split('\n')
    for l in lines:
        if "cliente:" in l.lower(): dados["Cliente"] = l.split(":",1)[1].strip()
        elif "total:" in l.lower():
            try: dados["Valor"] = float(re.findall(r'[\d.,]+', l)[-1].replace('.','').replace(',','.'))
            except: pass
    return dados

# --- INTERFACE ---
if 'dados_importados' not in st.session_state: st.session_state['dados_importados'] = {}

st.sidebar.title("Solução Gestor")
menu = st.sidebar.radio("Navegação", ["📊 Dashboard & Agenda", "📝 Novo Orçamento", "📂 Obras & Recibos"])

if menu == "📊 Dashboard & Agenda":
    st.title("📊 Painel de Controle")
    df = carregar_dados()
    
    if not df.empty:
        # --- BLINDAGEM CONTRA ERRO DE COLUNA ---
        colunas_existem = 'DataEntrada' in df.columns and 'DataRestante' in df.columns
        
        if colunas_existem:
            st.subheader("📅 Agenda do Dia")
            hoje = datetime.date.today().strftime("%d/%m/%Y")
            avisos = []
            for index, row in df.iterrows():
                # Converte pra string pra não dar erro de tipo
                if str(row['DataEntrada']) == hoje:
                    avisos.append(f"💰 Entrada de **{row['Cliente']}** hoje!")
                if str(row['DataRestante']) == hoje:
                    avisos.append(f"🏁 Final de **{row['Cliente']}** hoje!")
            
            if avisos:
                for a in avisos: st.warning(a)
            else: st.success("Agenda livre hoje.")
        else:
            st.warning("⚠️ Atenção: Atualize as colunas da Planilha (DataEntrada, DataRestante) para ver a Agenda.")

        st.write("---")
        
        # FASES (KANBAN) - SÓ MOSTRA SE TIVER A COLUNA STATUS
        if 'Status' in df.columns:
            st.subheader("🚀 Fases dos Clientes")
            c1, c2, c3, c4 = st.columns(4)
            with c1: 
                st.markdown("### 📞 Contato")
                for i,r in df[df['Status']=='Contato'].iterrows(): st.info(f"{r['Cliente']}")
            with c2: 
                st.markdown("### 📐 Visita")
                for i,r in df[df['Status']=='Visita'].iterrows(): st.warning(f"{r['Cliente']}")
            with c3: 
                st.markdown("### 📝 Orçamento")
                for i,r in df[df['Status']=='Orçamento'].iterrows(): st.primary(f"{r['Cliente']}")
            with c4: 
                st.markdown("### ✅ Fechado")
                for i,r in df[df['Status']=='Fechado'].iterrows(): st.success(f"{r['Cliente']}")
        else:
            st.error("Coluna 'Status' não encontrada na planilha.")

    else: st.info("Sem dados. Cadastre sua primeira obra!")

elif menu == "📝 Novo Orçamento":
    st.title("📝 Cadastro")
    
    with st.expander("📂 Importar PDF"):
        arq = st.file_uploader("Upload PDF", type="pdf")
        if arq: st.session_state['dados_importados'] = ler_pdf(arq)

    mem = st.session_state['dados_importados']

    with st.form("form_cad"):
        st.subheader("1. Fase")
        status = st.selectbox("Status", ["Contato", "Visita", "Orçamento", "Fechado"])
        
        c1, c2 = st.columns(2)
        cli = c1.text_input("Nome", value=mem.get("Cliente", ""))
        end = c2.text_input("Endereço", value=mem.get("Endereco", ""))
        tel = st.text_input("Telefone", value=mem.get("Telefone", ""))
        
        st.subheader("2. Financeiro")
        d1, d2, d3, d4 = st.columns(4)
        dt1 = d1.date_input("Contato", datetime.date.today())
        dt2 = d2.date_input("Envio", datetime.date.today())
        dt3 = d3.date_input("Entrada", datetime.date.today())
        dt4 = d4.date_input("Restante", datetime.date.today())
        
        desc = st.text_area("Descrição", value=mem.get("Descricao", ""), height=100)
        obs = st.text_area("Obs", value=mem.get("Observacao", ""), height=60)
        
        c3, c4 = st.columns(2)
        val = c3.number_input("Valor", value=float(mem.get("Valor", 0.0)), step=50.0)
        pag = c4.text_input("Pagamento", value=mem.get("Pagamento", ""))
        
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
                st.session_state['dados_importados'] = {}
            else: st.warning("Nome obrigatório!")

elif menu == "📂 Obras & Recibos":
    st.title("📂 Gerenciar")
    df = carregar_dados()
    if not df.empty:
        cols_view = [c for c in ['Status', 'Cliente', 'Valor', 'DataEntrada'] if c in df.columns]
        st.dataframe(df[cols_view])
        
        sel = st.selectbox("Cliente:", df['Cliente'].unique())
        if sel:
            obra = df[df['Cliente'] == sel].iloc[-1]
            c_a, c_b = st.columns(2)
            with c_a: st.download_button("📄 Orçamento", gerar_pdf_orcamento(obra), f"Orc_{sel}.pdf")
            with c_b: st.download_button("💰 Recibo", gerar_pdf_recibo(obra), f"Rec_{sel}.pdf")
