import streamlit as st
import pandas as pd
from fpdf import FPDF
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import datetime

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="ObraGestor Pro", layout="wide", page_icon="🏗️")

# --- CONEXÃO GOOGLE SHEETS ---
def conectar_gsheets():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = st.secrets["gcp_service_account"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client

def carregar_dados():
    try:
        client = conectar_gsheets()
        sheet = client.open("Gestao_Obras").sheet1
        dados = sheet.get_all_records()
        return pd.DataFrame(dados)
    except:
        return pd.DataFrame()

def salvar_obra(dados):
    try:
        client = conectar_gsheets()
        sheet = client.open("Gestao_Obras").sheet1
        
        # Formata datas
        d_contato = dados["DataContato"].strftime("%d/%m/%Y")
        d_envio = dados["DataEnvio"].strftime("%d/%m/%Y")
        
        # Salva na ordem das 10 colunas
        sheet.append_row([
            dados["ID"],
            d_contato,
            d_envio,
            dados["Cliente"],
            dados["Telefone"],
            dados["Endereco"],
            dados["Descricao"],  # Texto 1
            dados["Observacao"], # Texto 2
            dados["Valor"],
            dados["Pagamento"]
        ])
        st.toast("✅ Dados Salvos na Nuvem!", icon="💾")
        return True
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")
        return False

# --- GERADOR DE PDF ---
class PDF(FPDF):
    def header(self):
        try: self.image("logo.png", 10, 8, 33)
        except: pass
        self.set_font('Arial', 'B', 16)
        self.cell(0, 10, 'PROPOSTA DE SERVIÇO', 0, 1, 'C')
        self.ln(5)
    
    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, 'ObraGestor Pro - Documento Oficial', 0, 0, 'C')

def gerar_pdf_detalhado(obra):
    pdf = PDF()
    pdf.add_page()
    
    # --- CABEÇALHO ---
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 8, "DADOS GERAIS", 1, 1, 'L', 1)
    
    pdf.set_font("Arial", size=10)
    pdf.cell(100, 8, f"Cliente: {obra['Cliente']}", 0, 0)
    pdf.cell(0, 8, f"Data do Envio: {obra['DataEnvio']}", 0, 1)
    
    pdf.cell(100, 8, f"Telefone: {obra['Telefone']}", 0, 0)
    pdf.cell(0, 8, f"Primeiro Contato: {obra['DataContato']}", 0, 1)
    
    pdf.cell(0, 8, f"Local: {obra['Endereco']}", 0, 1)
    pdf.ln(5)
    
    # --- DESCRIÇÃO DO SERVIÇO ---
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 8, "DESCRIÇÃO DETALHADA DO SERVIÇO", 1, 1, 'L', 1)
    pdf.set_font("Arial", size=10)
    pdf.multi_cell(0, 6, txt=str(obra['Descricao']), border=1)
    pdf.ln(5)
    
    # --- OBSERVAÇÕES ---
    if str(obra['Observacao']).strip(): # Só imprime se tiver algo escrito
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(0, 8, "OBSERVAÇÕES IMPORTANTES", 1, 1, 'L', 1)
        pdf.set_font("Arial", size=10)
        pdf.multi_cell(0, 6, txt=str(obra['Observacao']), border=1)
        pdf.ln(5)
    
    # --- VALORES ---
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 8, "VALORES E PAGAMENTO", 1, 1, 'L', 1)
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 8, f"Condição de Pagamento: {obra['Pagamento']}", 0, 1)
    
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, f"VALOR TOTAL: R$ {obra['ValorTotal']}", 1, 1, 'R')
    
    return pdf.output(dest='S').encode('latin-1')

# --- TELA ---
st.sidebar.title("ObraGestor Pro")
menu = st.sidebar.radio("Menu", ["Novo Orçamento", "Consultar"])

if menu == "Novo Orçamento":
    st.title("📝 Novo Cadastro")
    
    with st.form("form_completo"):
        col1, col2 = st.columns(2)
        cliente = col1.text_input("Nome do Cliente")
        telefone = col2.text_input("Telefone")
        endereco = st.text_input("Endereço da Obra")
        
        col3, col4 = st.columns(2)
        dt_contato = col3.date_input("Data do 1º Contato", datetime.date.today())
        dt_envio = col4.date_input("Data de Envio do Orçamento", datetime.date.today())
        
        st.write("---")
        # CAMPOS DE TEXTO SEPARADOS
        descricao = st.text_area("Descrição do Serviço (O que será feito?)", height=150)
        observacao = st.text_area("Observações (Avisos, detalhes extras)", height=100)
        
        col5, col6 = st.columns(2)
        valor = col5.number_input("Valor Total (R$)", min_value=0.0, step=50.0)
        pagamento = col6.text_input("Forma de Pagamento")
        
        btn_salvar = st.form_submit_button("💾 Salvar na Nuvem")
        
        if btn_salvar:
            if cliente and valor > 0:
                id_unico = datetime.datetime.now().strftime("%Y%m%d%H%M")
                dados = {
                    "ID": id_unico,
                    "DataContato": dt_contato,
                    "DataEnvio": dt_envio,
                    "Cliente": cliente,
                    "Telefone": telefone,
                    "Endereco": endereco,
                    "Descricao": descricao,
                    "Observacao": observacao,
                    "Valor": valor,
                    "Pagamento": pagamento
                }
                salvar_obra(dados)
            else:
                st.warning("Preencha pelo menos Nome e Valor!")

elif menu == "Consultar":
    st.title("📂 Meus Orçamentos")
    df = carregar_dados()
    
    if not df.empty:
        st.dataframe(df[['DataEnvio', 'Cliente', 'ValorTotal']])
        
        st.write("---")
        cliente_escolhido = st.selectbox("Selecione para ver detalhes ou baixar PDF:", df['Cliente'].unique())
        
        if cliente_escolhido:
            obra = df[df['Cliente'] == cliente_escolhido].iloc[-1]
            
            st.write(f"**Descrição:** {obra['Descricao']}")
            st.write(f"**Obs:** {obra['Observacao']}")
            
            pdf_bytes = gerar_pdf_detalhado(obra)
            st.download_button(
                label="⬇️ Baixar PDF Completo",
                data=pdf_bytes,
                file_name=f"Orcamento_{cliente_escolhido}.pdf",
                mime="application/pdf"
            )
    else:
        st.info("Nenhum dado encontrado.")
