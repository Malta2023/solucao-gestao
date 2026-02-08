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

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Solução Gestor", layout="wide", page_icon="🏗️")

# --- CONEXÃO GOOGLE SHEETS ---
def conectar_gsheets():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds_dict = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        return client
    except: return None

def carregar_dados():
    client = conectar_gsheets()
    if client:
        try:
            sheet = client.open("Gestao_Obras").sheet1
            return pd.DataFrame(sheet.get_all_records())
        except: return pd.DataFrame()
    return pd.DataFrame()

def salvar_obra(dados):
    client = conectar_gsheets()
    if client:
        try:
            sheet = client.open("Gestao_Obras").sheet1
            # Formata datas
            def fmt_date(d): return d.strftime("%d/%m/%Y") if hasattr(d, 'strftime') else str(d)
            
            row = [
                dados["ID"], fmt_date(dados["DataContato"]), fmt_date(dados["DataEnvio"]),
                dados["Cliente"], dados["Telefone"], dados["Endereco"],
                dados["Descricao"], dados["Observacao"], dados["Valor"], dados["Pagamento"],
                fmt_date(dados["DataEntrada"]), fmt_date(dados["DataRestante"]) # Financeiro
            ]
            sheet.append_row(row)
            st.toast("✅ Salvo com Sucesso!", icon="💾")
            return True
        except Exception as e:
            st.error(f"Erro ao salvar: {e}")
            return False
    return False

# --- LEITURA PDF ---
def ler_pdf_inteligente(arquivo):
    texto = ""
    with pdfplumber.open(arquivo) as pdf:
        for p in pdf.pages: texto += p.extract_text() + "\n"
    dados = {"Cliente": "", "Telefone": "", "Endereco": "", "Valor": 0.0, "Descricao": texto}
    # Regex simples
    lines = texto.split('\n')
    for l in lines:
        lower = l.lower()
        if "cliente:" in lower: dados["Cliente"] = l.split(":",1)[1].strip()
        elif "telefone:" in lower: dados["Telefone"] = l.split(":",1)[1].strip()
        elif "endereço:" in lower: dados["Endereco"] = l.split(":",1)[1].strip()
        elif "total:" in lower:
            try: 
                v = re.findall(r'[\d.,]+', l)[-1]
                dados["Valor"] = float(v.replace('.','').replace(',','.'))
            except: pass
    return dados

# --- PDF CLASS ---
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
        self.cell(0, 10, f'{EMP_NOME} - Documento Oficial', 0, 0, 'C')

def gerar_pdf_orcamento(obra):
    pdf = PDF()
    pdf.add_page()
    pdf.set_font('Arial', 'B', 16)
    pdf.cell(0, 10, 'ORÇAMENTO', 0, 1, 'C')
    pdf.ln(5)
    
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 8, "  DADOS DO CLIENTE", 0, 1, 'L', 1)
    pdf.ln(2)
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 6, f"Cliente: {obra['Cliente']}", 0, 1)
    pdf.cell(0, 6, f"Data: {obra['DataEnvio']}", 0, 1)
    pdf.cell(0, 6, f"Telefone: {obra['Telefone']}", 0, 1)
    pdf.cell(0, 6, f"Endereço: {obra['Endereco']}", 0, 1)
    pdf.ln(5)
    
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 8, "  DESCRIÇÃO DOS SERVIÇOS", 0, 1, 'L', 1)
    pdf.ln(2)
    pdf.set_font("Arial", size=10)
    pdf.multi_cell(0, 6, txt=str(obra['Descricao']), border=0)
    pdf.ln(5)
    
    if str(obra['Observacao']).strip():
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(0, 8, "  OBSERVAÇÕES", 0, 1, 'L', 1)
        pdf.ln(2)
        pdf.set_font("Arial", size=9)
        pdf.multi_cell(0, 5, txt=str(obra['Observacao']), border=0)
        pdf.ln(5)
        
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 12, f"VALOR TOTAL: R$ {obra['ValorTotal']}", 1, 1, 'R')
    return pdf.output(dest='S').encode('latin-1')

def gerar_pdf_recibo(obra):
    pdf = PDF()
    pdf.add_page()
    pdf.ln(10)
    pdf.set_font('Arial', 'B', 20)
    pdf.cell(0, 15, 'RECIBO', 0, 1, 'C')
    pdf.ln(10)
    pdf.set_font('Arial', '', 12)
    texto = f"Recebemos de {obra['Cliente']}\n" \
            f"A quantia de R$ {obra['ValorTotal']}\n\n" \
            f"Referente aos serviços em: {obra['Endereco']}.\n\n" \
            f"Forma de Pagamento: {obra['Pagamento']}\n" \
            f"Teresina/PI, {datetime.date.today().strftime('%d/%m/%Y')}"
    pdf.multi_cell(0, 9, texto, border=1, align='C')
    pdf.ln(30)
    pdf.cell(0, 5, "_______________________", 0, 1, 'C')
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(0, 5, EMP_NOME, 0, 1, 'C')
    return pdf.output(dest='S').encode('latin-1')

# --- INTERFACE ---
st.sidebar.title("Solução Gestor")
st.sidebar.image("logo.png", width=100) if pd.io.common.file_exists("logo.png") else None
menu = st.sidebar.radio("Navegação", ["Dashboard", "Novo Orçamento", "Consultar & Recibos"])

if 'form_data' not in st.session_state: st.session_state['form_data'] = {}

if menu == "Dashboard":
    st.title("📊 Visão Geral")
    df = carregar_dados()
    if not df.empty:
        c1, c2, c3 = st.columns(3)
        c1.metric("Obras", len(df))
        val = pd.to_numeric(df['ValorTotal'], errors='coerce').sum()
        c2.metric("Total Orçado", f"R$ {val:,.2f}")
        c3.metric("Última Obra", df.iloc[-1]['DataEnvio'])
        st.dataframe(df[['DataEnvio', 'Cliente', 'Status' if 'Status' in df.columns else 'ValorTotal']])
    else: st.info("Sem dados ainda.")

elif menu == "Novo Orçamento":
    st.title("📝 Novo Orçamento")
    
    # Upload opcional no topo
    with st.expander("📂 Importar PDF Antigo (Opcional)", expanded=False):
        uploaded_pdf = st.file_uploader("Solte o PDF aqui", type="pdf")
        if uploaded_pdf:
            st.session_state['form_data'] = ler_pdf_inteligente(uploaded_pdf)
            st.success("Dados carregados!")

    defaults = st.session_state['form_data']

    with st.form("form_obra"):
        st.subheader("1. Cliente")
        c1, c2 = st.columns(2)
        cliente = c1.text_input("Nome", value=defaults.get("Cliente", ""))
        fone = c2.text_input("Telefone", value=defaults.get("Telefone", ""))
        end = st.text_input("Endereço", value=defaults.get("Endereco", ""))
        
        st.subheader("2. Datas")
        c3, c4, c5, c6 = st.columns(4)
        dt_contato = c3.date_input("1º Contato", datetime.date.today())
        dt_envio = c4.date_input("Envio Orçamento", datetime.date.today())
        # Financeiro Simples
        dt_entrada = c5.date_input("Previsão Entrada", datetime.date.today())
        dt_restante = c6.date_input("Previsão Restante", datetime.date.today())
        
        st.subheader("3. Serviço")
        desc = st.text_area("Descrição Completa", value=defaults.get("Descricao", ""), height=150)
        obs = st.text_area("Observações", value=defaults.get("Observacao", ""), height=80)
        
        st.subheader("4. Valores")
        c7, c8 = st.columns(2)
        val = c7.number_input("Valor Total (R$)", min_value=0.0, value=float(defaults.get("Valor", 0.0)), step=50.0)
        pag = c8.text_input("Forma Pagamento", value=defaults.get("Pagamento", ""))
        
        if st.form_submit_button("💾 Salvar Tudo"):
            if cliente and val > 0:
                id_unico = datetime.datetime.now().strftime("%Y%m%d%H%M")
                dados = {
                    "ID": id_unico, "DataContato": dt_contato, "DataEnvio": dt_envio,
                    "Cliente": cliente, "Telefone": fone, "Endereco": end,
                    "Descricao": desc, "Observacao": obs, "Valor": val, "Pagamento": pag,
                    "DataEntrada": dt_entrada, "DataRestante": dt_restante
                }
                salvar_obra(dados)
                st.session_state['form_data'] = {} # Limpa
            else: st.warning("Preencha Nome e Valor!")

elif menu == "Consultar & Recibos":
    st.title("📂 Gerenciar Obras")
    df = carregar_dados()
    if not df.empty:
        st.dataframe(df[['DataEnvio', 'Cliente', 'ValorTotal', 'Pagamento']])
        
        cli = st.selectbox("Selecione Cliente:", df['Cliente'].unique())
        if cli:
            obra = df[df['Cliente'] == cli].iloc[-1]
            c_a, c_b = st.columns(2)
            with c_a:
                st.download_button("📄 Baixar Orçamento", gerar_pdf_orcamento(obra), f"Orcamento_{cli}.pdf")
            with c_b:
                st.download_button("💰 Baixar Recibo", gerar_pdf_recibo(obra), f"Recibo_{cli}.pdf")
            
            st.write("---")
            st.caption(f"Controle Financeiro: Entrada em {obra.get('DataEntrada','-')} | Restante em {obra.get('DataRestante','-')}")
