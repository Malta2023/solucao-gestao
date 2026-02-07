import streamlit as st
import pandas as pd
from fpdf import FPDF
from datetime import datetime

# --- DADOS DA EMPRESA ---
EMPRESA = {
    "nome": "Solução Reforma e Construção",
    "responsavel": "Antônio Francisco Carvalho Silva",
    "cnpj": "46.580.382/0001-70",
    "endereco": "Rua Bandeirantes, 1303, Bairro Pedra Mole, Teresina-PI",
    "telefone": "(86) 9.9813-2225"
}

class PDF_Solucao(FPDF):
    def header(self):
        try: self.image('logo.png', 10, 8, 25)
        except: pass
        self.set_font('Arial', 'B', 16)
        self.cell(0, 10, EMPRESA["nome"], ln=True, align='C')
        self.set_font('Arial', '', 9)
        self.cell(0, 5, f"Responsável: {EMPRESA['responsavel']} | CNPJ: {EMPRESA['cnpj']}", ln=True, align='C')
        self.cell(0, 5, f"{EMPRESA['endereco']} | Tel: {EMPRESA['telefone']}", ln=True, align='C')
        self.ln(10)

def gerar_pdf(cliente, servico, valor, p_entrada):
    pdf = PDF_Solucao()
    pdf.add_page()
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, f"ORÇAMENTO - CLIENTE: {cliente.upper()}", border='B', ln=True)
    pdf.ln(5)
    pdf.set_font('Arial', '', 11)
    pdf.multi_cell(0, 7, f"Descrição dos Serviços:\n{servico}")
    pdf.ln(10)
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, f"VALOR TOTAL: R$ {valor:,.2f}", ln=True)
    if p_entrada > 0:
        pdf.set_font('Arial', 'I', 10)
        pdf.cell(0, 10, f"Condição: {p_entrada}% de entrada (R$ {valor*(p_entrada/100):,.2f})", ln=True)
    return pdf.output(dest='S').encode('latin1')

st.title("🏗️ Solução Reforma & Construção")
st.subheader("Gerador de Orçamento Profissional")

with st.form("orc_form"):
    cliente = st.text_input("Nome do Cliente")
    servico = st.text_area("Descrição detalhada do serviço")
    col1, col2 = st.columns(2)
    valor = col1.number_input("Valor Total (R$)", min_value=0.0)
    p_entrada = col2.number_input("% Entrada", value=65.0)
    enviar = st.form_submit_button("Gerar PDF")

if enviar:
    if cliente and valor > 0:
        pdf_bytes = gerar_pdf(cliente, servico, valor, p_entrada)
        st.success(f"Orçamento para {cliente} gerado com sucesso!")
        st.download_button("⬇️ Baixar Orçamento em PDF", pdf_bytes, f"Orcamento_{cliente}.pdf")
    else:
        st.warning("Por favor, preencha o nome do cliente e o valor.")
