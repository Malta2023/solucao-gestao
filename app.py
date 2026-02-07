import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from fpdf import FPDF
from datetime import datetime

# --- DADOS DA EMPRESA ---
EMPRESA = {
    "nome": "Solução Reforma e Construção",
    "responsavel": "Antônio Francisco Carvalho Silva",
    "cnpj": "46.580.382/0001-70",
    "endereco": "Rua Bandeirantes, 1303, Bairro Pedra Mole, Teresina-PI",
    "email": "solucoesreformaseconstrucao@gmail.com",
    "telefone": "(86) 9.9813-2225"
}

# --- CONFIGURAÇÃO DA CONEXÃO GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- CLASSE DO PDF PROFISSIONAL ---
class PDF_Solucao(FPDF):
    def header(self):
        try:
            self.image('logo.png', 10, 8, 25)
            self.ln(15)
        except:
            self.ln(5)
        self.set_font('Arial', 'B', 16)
        self.set_text_color(27, 54, 68) 
        self.cell(0, 10, EMPRESA["nome"], ln=True)
        self.set_font('Arial', '', 9)
        self.set_text_color(50)
        self.cell(0, 5, f"Responsável: {EMPRESA['responsavel']}", ln=True)
        self.cell(0, 5, EMPRESA["endereco"], ln=True)
        self.cell(0, 5, f"Contato: {EMPRESA['telefone']}", ln=True)
        self.ln(5)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(10)

def gerar_pdf(cliente, servico, valor, porcentagem_entrada):
    pdf = PDF_Solucao()
    pdf.add_page()
    pdf.set_font('Arial', 'B', 11)
    pdf.cell(0, 10, f"CLIENTE: {cliente.upper()}", border='B', ln=True)
    pdf.ln(5)
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(0, 7, "DESCRIÇÃO DOS SERVIÇOS:", ln=True)
    pdf.set_font('Arial', '', 11)
    pdf.multi_cell(0, 6, servico)
    pdf.ln(10)
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(140, 10, "TOTAL DA MÃO DE OBRA:", align='R')
    pdf.cell(50, 10, f"R$ {valor:,.2f}", ln=True, align='R', border=1)
    if porcentagem_entrada > 0:
        valor_entrada = valor * (porcentagem_entrada / 100)
        pdf.ln(2)
        pdf.set_font('Arial', 'I', 10)
        pdf.set_text_color(200, 0, 0)
        pdf.cell(0, 10, f"OBS: Pagamento com {porcentagem_entrada}% de entrada (R$ {valor_entrada:,.2f})", ln=True, align='R')
    return pdf.output(dest='S').encode('latin1')

# --- INTERFACE ---
st.set_page_config(page_title="Solução Gestão", page_icon="🏗️")
st.title("🏗️ Solução Reforma & Construção")

tab1, tab2 = st.tabs(["Novo Orçamento", "Histórico"])

with tab1:
    with st.form("orc_form", clear_on_submit=True):
        cliente = st.text_input("Nome do Cliente")
        servico = st.text_area("Descrição detalhada")
        col1, col2 = st.columns(2)
        valor = col1.number_input("Valor Total (R$)", min_value=0.0)
        p_entrada = col2.number_input("% Entrada", min_value=0.0, max_value=100.0, value=65.0)
        submit = st.form_submit_button("Salvar e Gerar Orçamento")

    if submit:
        try:
            df_atual = conn.read()
            novo_dado = pd.DataFrame([{"cliente": cliente, "serviço": servico, "valor": valor, "entrada_p": p_entrada, "data": datetime.now().strftime("%d/%m/%Y")}])
            df_final = pd.concat([df_atual, novo_dado], ignore_index=True)
            conn.update(data=df_final)
            pdf_bytes = gerar_pdf(cliente, servico, valor, p_entrada)
            st.success("✅ Orçamento salvo!")
            st.download_button("⬇️ Baixar PDF", pdf_bytes, f"Orcamento_{cliente}.pdf", "application/pdf")
        except:
            st.error("Erro nos Secrets da Planilha.")

with tab2:
    if st.button("Atualizar"): st.cache_data.clear()
    st.dataframe(conn.read(), use_container_width=True)
