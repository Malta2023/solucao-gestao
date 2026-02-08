import streamlit as st
import pandas as pd
from fpdf import FPDF
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import datetime

# --- CONFIGURAÇÃO DA CONEXÃO COM GOOGLE SHEETS ---
def conectar_gsheets():
    # Define o escopo de permissão
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    # Pega as credenciais que você acabou de salvar nos Secrets
    creds_dict = st.secrets["gcp_service_account"]
    
    # Conecta com o Google
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client

# --- FUNÇÃO PARA SALVAR CLIENTE ---
def salvar_cliente(cliente_novo):
    try:
        client = conectar_gsheets()
        # IMPORTANTE: O nome aqui tem que ser IGUAL ao nome da sua planilha no Google
        sheet = client.open("Gestao_Obras").sheet1
        
        # Adiciona a linha nova
        sheet.append_row([
            cliente_novo["Cliente"],
            cliente_novo["Telefone"],
            cliente_novo["Endereco"],
            datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
        ])
        st.success("✅ Cliente salvo na nuvem com sucesso!")
        
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")

# --- FUNÇÃO PARA LER DADOS ---
def carregar_dados():
    try:
        client = conectar_gsheets()
        sheet = client.open("Gestao_Obras").sheet1
        dados = sheet.get_all_records()
        return pd.DataFrame(dados)
    except Exception as e:
        return pd.DataFrame()

# --- TELA DO SISTEMA ---
st.title("Gestão de Obras - Nuvem ☁️")

aba = st.sidebar.radio("Navegação", ["Novo Cliente", "Ver Lista"])

if aba == "Novo Cliente":
    with st.form("meu_form"):
        nome = st.text_input("Nome do Cliente")
        tel = st.text_input("Telefone")
        end = st.text_input("Endereço da Obra")
        botao = st.form_submit_button("Salvar no Google Sheets")
        
        if botao:
            if nome:
                dados = {"Cliente": nome, "Telefone": tel, "Endereco": end}
                salvar_cliente(dados)
            else:
                st.warning("Preencha o nome pelo menos!")

if aba == "Ver Lista":
    st.subheader("Clientes Cadastrados")
    df = carregar_dados()
    if not df.empty:
        st.dataframe(df)
    else:
        st.info("Nenhum cliente encontrado ou erro na conexão.")
