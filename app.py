import streamlit as st
import pandas as pd
from fpdf import FPDF
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import datetime
import pdfplumber
import re # Biblioteca para encontrar padrões de texto (Regex)

# --- IDENTIDADE VISUAL DA EMPRESA ---
EMP_NOME = "SOLUÇÃO REFORMA E CONSTRUÇÃO"
EMP_CNPJ = "CNPJ: 46.580.382/0001-70"
EMP_ENDERECO = "Rua Bandeirantes, 1303, Pedra Mole - Teresina/PI | CEP: 64065-040"
EMP_CONTATO = "Tel: (86) 9.9813-2225 | Email: solucoesreformaseconstrucao@gmail.com"

# --- CONFIGURAÇÃO DA PÁGINA ---
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
            # Garante que data venha como string
            d_contato = dados["DataContato"].strftime("%d/%m/%Y") if hasattr(dados["DataContato"], 'strftime') else str(dados["DataContato"])
            d_envio = dados["DataEnvio"].strftime("%d/%m/%Y") if hasattr(dados["DataEnvio"], 'strftime') else str(dados["DataEnvio"])
            
            sheet.append_row([
                dados["ID"], d_contato, d_envio, dados["Cliente"],
                dados["Telefone"], dados["Endereco"], dados["Descricao"],
                dados["Observacao"], dados["Valor"], dados["Pagamento"]
            ])
            st.toast("✅ Salvo com Sucesso!", icon="💾")
            return True
        except Exception as e:
            st.error(f"Erro ao salvar: {e}")
            return False
    return False

# --- INTELIGÊNCIA DE LEITURA DE PDF ---
def ler_pdf_inteligente(arquivo):
    texto_completo = ""
    with pdfplumber.open(arquivo) as pdf:
        for page in pdf.pages:
            texto_completo += page.extract_text() + "\n"
    
    # Dicionário inicial vazio
    dados_extraidos = {
        "Cliente": "", "Telefone": "", "Endereco": "", 
        "Valor": 0.0, "Descricao": texto_completo
    }
    
    # Lógica para encontrar campos linha por linha
    linhas = texto_completo.split('\n')
    for i, linha in enumerate(linhas):
        linha_lower = linha.lower()
        
        # Procura Cliente
        if "cliente:" in linha_lower:
            dados_extraidos["Cliente"] = linha.split(":", 1)[1].strip()
        
        # Procura Telefone
        elif "telefone:" in linha_lower or "celular:" in linha_lower or "tel:" in linha_lower:
            dados_extraidos["Telefone"] = linha.split(":", 1)[1].strip()
            
        # Procura Endereço
        elif "endereço:" in linha_lower or "local:" in linha_lower or "obra:" in linha_lower:
            dados_extraidos["Endereco"] = linha.split(":", 1)[1].strip()
            
        # Tenta achar Valor (Procura R$ e números)
        elif "total:" in linha_lower or "valor:" in linha_lower:
            # Tenta limpar o texto pra pegar só o numero
            try:
                valor_sujo = re.findall(r'[\d.,]+', linha)
                if valor_sujo:
                    # Pega o último numero encontrado na linha (geralmente é o total)
                    valor_limpo = valor_sujo[-1].replace('.', '').replace(',', '.')
                    dados_extraidos["Valor"] = float(valor_limpo)
            except: pass

    return dados_extraidos

# --- GERADOR DE PDF ---
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
        self.ln(10) # Espaço após cabeçalho

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 7)
        self.cell(0, 10, f'{EMP_NOME} - Documento Oficial', 0, 0, 'C')

def gerar_pdf_orcamento(obra):
    pdf = PDF()
    pdf.add_page()
    
    # Título
    pdf.set_font('Arial', 'B', 16)
    pdf.cell(0, 10, 'ORÇAMENTO', 0, 1, 'C')
    pdf.ln(5)
    
    # Bloco Cliente (Fundo Cinza Clean)
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 8, "  DADOS DO CLIENTE", 0, 1, 'L', 1) # O espaço no começo é margem
    
    pdf.set_font("Arial", size=10)
    pdf.ln(2)
    pdf.cell(100, 6, f"Nome: {obra['Cliente']}", 0, 0)
    pdf.cell(0, 6, f"Data: {obra['DataEnvio']}", 0, 1)
    pdf.cell(100, 6, f"Telefone: {obra['Telefone']}", 0, 0)
    pdf.cell(0, 6, f"Local: {obra['Endereco']}", 0, 1)
    pdf.ln(5)
    
    # Bloco Serviço
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 8, "  DESCRIÇÃO DOS SERVIÇOS", 0, 1, 'L', 1)
    pdf.ln(2)
    pdf.set_font("Arial", size=10)
    pdf.multi_cell(0, 6, txt=str(obra['Descricao']), border=0)
    pdf.ln(5)
    
    # Bloco Obs (se tiver)
    if str(obra['Observacao']).strip():
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(0, 8, "  OBSERVAÇÕES", 0, 1, 'L', 1)
        pdf.ln(2)
        pdf.set_font("Arial", size=9)
        pdf.multi_cell(0, 5, txt=str(obra['Observacao']), border=0)
        pdf.ln(5)
    
    # Total
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 14)
    # Caixa ao redor do preço
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
    texto = f"Recebemos de Sr(a). {obra['Cliente']}\n" \
            f"A quantia de R$ {obra['ValorTotal']}\n\n" \
            f"Referente aos serviços prestados de reforma e construção no endereço: {obra['Endereco']}.\n\n" \
            f"Forma de Pagamento: {obra['Pagamento']}\n" \
            f"Teresina/PI, {datetime.date.today().strftime('%d/%m/%Y')}"
            
    pdf.multi_cell(0, 9, texto, border=1, align='C')
    pdf.ln(30)
    
    pdf.cell(0, 5, "__________________________________________________", 0, 1, 'C')
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(0, 5, EMP_NOME, 0, 1, 'C')
    pdf.set_font('Arial', '', 8)
    pdf.cell(0, 5, EMP_CNPJ, 0, 1, 'C')
    
    return pdf.output(dest='S').encode('latin-1')


# --- INTERFACE STREAMLIT ---
menu = st.sidebar.radio("Navegação", ["Novo Orçamento / Importar", "Meus Orçamentos"])

# Estado para guardar dados do PDF
if 'form_data' not in st.session_state:
    st.session_state['form_data'] = {}

if menu == "Novo Orçamento / Importar":
    st.title("📝 Novo Orçamento")
    
    # --- ÁREA DE UPLOAD CLEAN ---
    with st.expander("📂 Importar PDF Antigo (Clique para Abrir)", expanded=True):
        uploaded_pdf = st.file_uploader("Solte o arquivo PDF aqui para preenchimento automático", type="pdf")
        if uploaded_pdf:
            dados_pdf = ler_pdf_inteligente(uploaded_pdf)
            st.session_state['form_data'] = dados_pdf
            st.success("Dados lidos com sucesso! Verifique abaixo.")

    # Pega dados da memória
    defaults = st.session_state['form_data']

    # --- FORMULÁRIO ORGANIZADO ---
    with st.form("form_obra"):
        st.subheader("1. Dados do Cliente")
        col1, col2 = st.columns(2)
        cliente = col1.text_input("Nome Completo", value=defaults.get("Cliente", ""))
        telefone = col2.text_input("Telefone / WhatsApp", value=defaults.get("Telefone", ""))
        endereco = st.text_input("Endereço da Obra", value=defaults.get("Endereco", ""))
        
        col_dt1, col_dt2 = st.columns(2)
        dt_contato = col_dt1.date_input("Data 1º Contato", datetime.date.today())
        dt_envio = col_dt2.date_input("Data Envio", datetime.date.today())
        
        st.write("---")
        st.subheader("2. Detalhes do Serviço")
        # Altura maior para caber bastante texto
        descricao = st.text_area("Descrição Detalhada", value=defaults.get("Descricao", ""), height=200)
        observacao = st.text_area("Observações Extras", value=defaults.get("Observacao", ""), height=80)
        
        st.write("---")
        st.subheader("3. Valores")
        col3, col4 = st.columns(2)
        valor_padrao = float(defaults.get("Valor", 0.0))
        valor = col3.number_input("Valor Total (R$)", min_value=0.0, value=valor_padrao, step=50.0)
        pagamento = col4.text_input("Forma de Pagamento", placeholder="Ex: 50% Entrada + 50% Final")
        
        # Botão Grande
        submitted = st.form_submit_button("💾 SALVAR DADOS NA NUVEM", use_container_width=True)
        
        if submitted:
            if cliente and valor > 0:
                id_unico = datetime.datetime.now().strftime("%Y%m%d%H%M")
                dados = {
                    "ID": id_unico, "DataContato": dt_contato, "DataEnvio": dt_envio,
                    "Cliente": cliente, "Telefone": telefone, "Endereco": endereco,
                    "Descricao": descricao, "Observacao": observacao,
                    "Valor": valor, "Pagamento": pagamento
                }
                if salvar_obra(dados):
                    # Limpa os dados da memória após salvar
                    st.session_state['form_data'] = {}
                    st.rerun() # Recarrega a página pra limpar o form
            else:
                st.warning("Preencha pelo menos o NOME e o VALOR.")

elif menu == "Meus Orçamentos":
    st.title("📂 Gerenciador de Obras")
    df = carregar_dados()
    
    if not df.empty:
        # Filtros rápidos
        filtro = st.text_input("🔍 Pesquisar Cliente...")
        if filtro:
            df = df[df['Cliente'].str.contains(filtro, case=False, na=False)]
        
        st.dataframe(df[['DataEnvio', 'Cliente', 'ValorTotal', 'Pagamento']], use_container_width=True)
        
        st.markdown("---")
        st.subheader("🖨️ Central de Documentos")
        
        col_sel, col_btn = st.columns([2, 1])
        cliente_escolhido = col_sel.selectbox("Selecione o Cliente:", df['Cliente'].unique())
        
        if cliente_escolhido:
            obra = df[df['Cliente'] == cliente_escolhido].iloc[-1]
            
            # Botões lado a lado
            b1, b2 = st.columns(2)
            with b1:
                pdf_orc = gerar_pdf_orcamento(obra)
                st.download_button("📄 Baixar ORÇAMENTO", pdf_orc, f"Orcamento_{cliente_escolhido}.pdf", use_container_width=True)
            
            with b2:
                pdf_rec = gerar_pdf_recibo(obra)
                st.download_button("💰 Baixar RECIBO", pdf_rec, f"Recibo_{cliente_escolhido}.pdf", use_container_width=True)
    else:
        st.info("Nenhuma obra cadastrada. Vá em 'Novo Orçamento' para começar.")
