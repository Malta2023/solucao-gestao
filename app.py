import streamlit as st
import pandas as pd
from fpdf import FPDF
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import datetime
import pdfplumber
import re

# --- DADOS DA EMPRESA (Cabeçalho) ---
EMP_NOME = "SOLUÇÃO REFORMA E CONSTRUÇÃO"
EMP_CNPJ = "CNPJ: 46.580.382/0001-70"
EMP_ENDERECO = "Rua Bandeirantes, 1303, Pedra Mole - Teresina/PI | CEP: 64065-040"
EMP_CONTATO = "Tel: (86) 9.9813-2225 | Email: solucoesreformaseconstrucao@gmail.com"

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Solução Gestor", layout="wide", page_icon="🏗️")

# Botão de Emergência para Limpar Memória (No topo da barra lateral)
if st.sidebar.button("🔄 Forçar Atualização"):
    st.cache_data.clear()
    st.rerun()

# --- CONEXÃO COM GOOGLE SHEETS ---
def conectar_gsheets():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds_dict = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        return None

# --- CARREGAR DADOS (SEM CACHE PARA EVITAR ERROS) ---
def carregar_dados():
    client = conectar_gsheets()
    if client:
        try:
            sheet = client.open("Gestao_Obras").sheet1
            # Pega tudo fresco da planilha
            dados = sheet.get_all_records()
            return pd.DataFrame(dados)
        except Exception as e:
            st.error(f"Erro ao ler planilha: {e}")
            return pd.DataFrame()
    return pd.DataFrame()

# --- SALVAR DADOS (13 COLUNAS) ---
def salvar_obra(dados):
    client = conectar_gsheets()
    if client:
        try:
            sheet = client.open("Gestao_Obras").sheet1
            
            # Formatação segura de datas
            def fmt(d):
                if isinstance(d, (datetime.date, datetime.datetime)):
                    return d.strftime("%d/%m/%Y")
                return str(d) if d else ""
            
            # A ordem aqui tem que bater com a sua planilha (13 Colunas)
            linha = [
                dados["ID"],
                dados["Status"],        # Coluna B
                fmt(dados["DataContato"]),
                fmt(dados["DataEnvio"]),
                dados["Cliente"],
                dados["Telefone"],
                dados["Endereco"],
                dados["Descricao"],
                dados["Observacao"],
                dados["Valor"],
                dados["Pagamento"],
                fmt(dados["DataEntrada"]), # Financeiro 1
                fmt(dados["DataRestante"]) # Financeiro 2
            ]
            
            sheet.append_row(linha)
            st.toast("✅ Salvo com sucesso!", icon="💾")
            return True
        except Exception as e:
            st.error(f"Erro ao salvar: {e}")
            return False
    return False

# --- LEITURA DE PDF (IMPORTAR) ---
def ler_pdf(arquivo):
    texto = ""
    with pdfplumber.open(arquivo) as pdf:
        for p in pdf.pages: texto += p.extract_text() + "\n"
    
    dados = {"Cliente": "", "Telefone": "", "Endereco": "", "Valor": 0.0, "Descricao": texto}
    
    # Busca padrões no texto
    for linha in texto.split('\n'):
        l = linha.lower()
        if "cliente:" in l: dados["Cliente"] = linha.split(":",1)[1].strip()
        elif "telefone:" in l: dados["Telefone"] = linha.split(":",1)[1].strip()
        elif "endereço:" in l: dados["Endereco"] = linha.split(":",1)[1].strip()
        elif "total:" in l:
            try:
                nums = re.findall(r'[\d.,]+', linha)
                if nums: dados["Valor"] = float(nums[-1].replace('.','').replace(',','.'))
            except: pass
    return dados

# --- GERADOR DE PDF (CLASSE) ---
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
        self.cell(0, 10, 'Documento Oficial - Solução Reforma e Construção', 0, 0, 'C')

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
    pdf.cell(0, 8, " DESCRIÇÃO DOS SERVIÇOS", 0, 1, 'L', 1)
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
            f"A importância de R$ {obra['ValorTotal']}\n\n" \
            f"Referente aos serviços realizados no endereço: {obra['Endereco']}.\n\n" \
            f"Forma de Pagamento: {obra['Pagamento']}\n" \
            f"Teresina/PI, {datetime.date.today().strftime('%d/%m/%Y')}"
            
    pdf.multi_cell(0, 9, texto, border=1, align='C')
    pdf.ln(30)
    pdf.cell(0, 5, "___________________________________", 0, 1, 'C')
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(0, 5, EMP_NOME, 0, 1, 'C')
    return pdf.output(dest='S').encode('latin-1')


# --- INTERFACE PRINCIPAL ---
st.sidebar.title("Solução Gestor")
menu = st.sidebar.radio("Navegação", ["📊 Dashboard & Agenda", "📝 Novo Orçamento", "📂 Gerenciar & Recibos"])

# Variável de sessão para Importação
if 'dados_importados' not in st.session_state:
    st.session_state['dados_importados'] = {}

# --- MENU 1: DASHBOARD ---
if menu == "📊 Dashboard & Agenda":
    st.title("📊 Painel de Controle")
    df = carregar_dados()
    
    if not df.empty:
        # Verifica se as colunas essenciais existem para não dar erro
        colunas_ok = all(col in df.columns for col in ['Status', 'DataEntrada', 'DataRestante'])
        
        if colunas_ok:
            # AGENDA
            st.subheader("📅 Agenda Financeira (Hoje)")
            hoje = datetime.date.today().strftime("%d/%m/%Y")
            avisos = []
            for i, row in df.iterrows():
                if str(row['DataEntrada']) == hoje:
                    avisos.append(f"💰 Entrada de {row['Cliente']}")
                if str(row['DataRestante']) == hoje:
                    avisos.append(f"🏁 Final de {row['Cliente']}")
            
            if avisos:
                for a in avisos: st.warning(a)
            else:
                st.success("Nenhuma pendência financeira hoje.")
            
            st.write("---")
            
            # KANBAN (STATUS)
            st.subheader("🚀 Status das Obras")
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.info("**📞 Contato**")
                for i,r in df[df['Status']=='Contato'].iterrows(): st.write(f"- {r['Cliente']}")
            with c2:
                st.warning("**📐 Visita**")
                for i,r in df[df['Status']=='Visita'].iterrows(): st.write(f"- {r['Cliente']}")
            with c3:
                st.primary("**📝 Orçamento**")
                for i,r in df[df['Status']=='Orçamento'].iterrows(): st.write(f"- {r['Cliente']}")
            with c4:
                st.success("**✅ Fechado**")
                for i,r in df[df['Status']=='Fechado'].iterrows(): st.write(f"- {r['Cliente']}")
        else:
            st.error("⚠️ Colunas 'Status', 'DataEntrada' ou 'DataRestante' não encontradas na planilha.")
            st.info("Clique em 'Forçar Atualização' no menu lateral ou verifique o Google Sheets.")
    else:
        st.info("Nenhum dado encontrado.")

# --- MENU 2: NOVO ORÇAMENTO ---
elif menu == "📝 Novo Orçamento":
    st.title("📝 Cadastro de Obra")
    
    # Upload PDF
    with st.expander("📂 Importar PDF (Preencher Automático)", expanded=True):
        arq = st.file_uploader("Suba o arquivo PDF aqui", type="pdf")
        if arq:
            st.session_state['dados_importados'] = ler_pdf(arq)
            st.success("Dados carregados!")

    mem = st.session_state['dados_importados']

    with st.form("form_obra"):
        st.subheader("1. Situação")
        status = st.selectbox("Fase Atual", ["Contato", "Visita", "Orçamento", "Fechado"])
        
        c1, c2 = st.columns(2)
        cliente = c1.text_input("Cliente", value=mem.get("Cliente", ""))
        fone = c2.text_input("Telefone", value=mem.get("Telefone", ""))
        end = st.text_input("Endereço", value=mem.get("Endereco", ""))
        
        st.subheader("2. Prazos & Financeiro")
        d1, d2, d3, d4 = st.columns(4)
        dt_cont = d1.date_input("1º Contato", datetime.date.today())
        dt_env = d2.date_input("Envio Orç.", datetime.date.today())
        dt_ent = d3.date_input("Prev. Entrada", datetime.date.today())
        dt_rest = d4.date_input("Prev. Final", datetime.date.today())
        
        st.subheader("3. Detalhes")
        desc = st.text_area("Descrição do Serviço", value=mem.get("Descricao", ""), height=120)
        obs = st.text_area("Observações", value=mem.get("Observacao", ""), height=80)
        
        c3, c4 = st.columns(2)
        val = c3.number_input("Valor Total (R$)", value=float(mem.get("Valor", 0.0)), step=50.0)
        pag = c4.text_input("Forma de Pagamento", value=mem.get("Pagamento", ""))
        
        if st.form_submit_button("💾 Salvar Obra"):
            if cliente:
                id_unico = datetime.datetime.now().strftime("%Y%m%d%H%M")
                dados = {
                    "ID": id_unico, "Status": status,
                    "DataContato": dt_cont, "DataEnvio": dt_env,
                    "Cliente": cliente, "Telefone": fone, "Endereco": end,
                    "Descricao": desc, "Observacao": obs,
                    "Valor": val, "Pagamento": pag,
                    "DataEntrada": dt_ent, "DataRestante": dt_rest
                }
                salvar_obra(dados)
                st.session_state['dados_importados'] = {}
            else:
                st.warning("Preencha o nome do Cliente!")

# --- MENU 3: GERENCIAR ---
elif menu == "📂 Gerenciar & Recibos":
    st.title("📂 Gerenciamento")
    df = carregar_dados()
    
    if not df.empty and 'Cliente' in df.columns:
        st.dataframe(df[['Status', 'Cliente', 'Valor', 'DataEnvio']])
        
        st.write("---")
        st.subheader("🖨️ Documentos")
        
        cli_sel = st.selectbox("Selecione o Cliente:", df['Cliente'].unique())
        
        if cli_sel:
            obra = df[df['Cliente'] == cli_sel].iloc[-1]
            
            st.info(f"Cliente: {cli_sel} | Status: {obra.get('Status', '-')}")
            
            col_a, col_b = st.columns(2)
            with col_a:
                pdf_orc = gerar_pdf_orcamento(obra)
                st.download_button("📄 Baixar ORÇAMENTO", pdf_orc, f"Orcamento_{cli_sel}.pdf")
            
            with col_b:
                pdf_rec = gerar_pdf_recibo(obra)
                st.download_button("💰 Baixar RECIBO", pdf_rec, f"Recibo_{cli_sel}.pdf")
