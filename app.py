import streamlit as st
import pandas as pd
from fpdf import FPDF
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import datetime

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="ObraGestor Pro", layout="wide")

# --- CONEXÃO COM GOOGLE SHEETS ---
def conectar_gsheets():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = st.secrets["gcp_service_account"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client

# --- FUNÇÕES DE BANCO DE DADOS (NUVEM) ---
def carregar_dados():
    try:
        client = conectar_gsheets()
        sheet = client.open("Gestao_Obras").sheet1
        dados = sheet.get_all_records()
        df = pd.DataFrame(dados)
        # Garante que as colunas existem mesmo se a planilha estiver vazia
        colunas_esperadas = ["ID", "Cliente", "Telefone", "Endereco", "Status", "ValorTotal", "Data"]
        for col in colunas_esperadas:
            if col not in df.columns:
                df[col] = ""
        return df
    except Exception as e:
        st.error(f"Erro na conexão: {e}")
        return pd.DataFrame(columns=["ID", "Cliente", "Telefone", "Endereco", "Status", "ValorTotal", "Data"])

def salvar_cliente(cliente_novo):
    try:
        client = conectar_gsheets()
        sheet = client.open("Gestao_Obras").sheet1
        # Gera um ID simples baseado na data/hora
        id_obra = datetime.datetime.now().strftime("%Y%m%d%H%M")
        sheet.append_row([
            id_obra,
            cliente_novo["Cliente"],
            cliente_novo["Telefone"],
            cliente_novo["Endereco"],
            "Orçamento", # Status inicial
            0.0,         # Valor inicial
            datetime.datetime.now().strftime("%d/%m/%Y")
        ])
        st.toast("✅ Cliente Salvo na Nuvem!", icon="☁️")
        return True
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")
        return False

# --- FUNÇÃO DE GERAR PDF (MANTIDA IGUAL) ---
class PDF(FPDF):
    def header(self):
        # Tenta carregar a logo se ela existir no projeto
        try:
            self.image("logo.png", 10, 8, 33)
        except:
            pass # Se não tiver logo, segue sem
        self.set_font('Arial', 'B', 15)
        self.cell(80)
        self.cell(30, 10, 'Orçamento de Obra', 0, 0, 'C')
        self.ln(20)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'C')

def gerar_pdf(dados_obra):
    pdf = PDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    
    pdf.cell(200, 10, txt=f"Cliente: {dados_obra['Cliente']}", ln=True)
    pdf.cell(200, 10, txt=f"Endereço: {dados_obra['Endereco']}", ln=True)
    pdf.cell(200, 10, txt=f"Data: {dados_obra['Data']}", ln=True)
    pdf.ln(10)
    
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(200, 10, txt="Detalhamento:", ln=True)
    pdf.set_font("Arial", size=12)
    pdf.multi_cell(0, 10, txt="Serviços de reforma e construção conforme combinado...")
    
    return pdf.output(dest='S').encode('latin-1')

# --- INTERFACE PRINCIPAL ---
st.sidebar.image("https://cdn-icons-png.flaticon.com/512/25/25694.png", width=50)
st.sidebar.title("ObraGestor Pro")
menu = st.sidebar.radio("Navegação", ["Dashboard", "Gestão de Obras", "Clientes", "Financeiro"])

if menu == "Dashboard":
    st.title("📊 Visão Geral")
    df = carregar_dados()
    
    if not df.empty:
        kpi1, kpi2, kpi3 = st.columns(3)
        kpi1.metric("Obras Ativas", len(df))
        kpi2.metric("Faturamento (Estimado)", f"R$ {pd.to_numeric(df['ValorTotal'], errors='coerce').sum():.2f}")
        kpi3.metric("Clientes", df['Cliente'].nunique())
    else:
        st.info("Nenhuma obra cadastrada ainda.")

elif menu == "Gestão de Obras":
    st.title("🏗️ Gestão de Obras")
    df = carregar_dados()
    st.dataframe(df, use_container_width=True)

elif menu == "Clientes":
    st.title("👥 Cadastro de Clientes")
    with st.form("form_cliente"):
        col1, col2 = st.columns(2)
        nome = col1.text_input("Nome Completo")
        tel = col2.text_input("Telefone")
        end = st.text_input("Endereço da Obra")
        obs = st.text_area("Observações Iniciais")
        
        btn_salvar = st.form_submit_button("Salvar Cliente")
        
        if btn_salvar:
            if nome:
                novo = {"Cliente": nome, "Telefone": tel, "Endereco": end}
                if salvar_cliente(novo):
                    st.success(f"Cliente {nome} cadastrado com sucesso!")
            else:
                st.warning("Preencha o nome!")

elif menu == "Financeiro":
    st.title("💰 Financeiro")
    st.info("Módulo em desenvolvimento... Aqui você verá custos vs lucro.")

