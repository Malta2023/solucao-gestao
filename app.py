import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from fpdf import FPDF
from datetime import datetime

# =====================================
# 1. DADOS OFICIAIS DA SUA EMPRESA
# =====================================
EMPRESA = {
    "nome": "Solução Reforma e Construção",
    "responsavel": "Antônio Francisco Carvalho Silva",
    "cnpj": "46.580.382/0001-70",
    "endereco": "Rua Bandeirantes, 1303, Pedra Mole, Teresina-PI",
    "telefone": "(86) 9.9813-2225",
    "email": "solucoesreformaseconstrucao@gmail.com"
}

# =====================================
# 2. CONFIGURAÇÃO DA PÁGINA E CONEXÃO
# =====================================
st.set_page_config(page_title="Solução Gestão", page_icon="🏗️", layout="wide")

# Estilo para ficar "bonito" e profissional
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stButton>button { width: 100%; background-color: #1b3644; color: white; }
    .stDownloadButton>button { width: 100%; background-color: #28a745; color: white; }
    </style>
    """, unsafe_allow_html=True)

# Conecta com sua planilha do Google
conn = st.connection("gsheets", type=GSheetsConnection)

# =====================================
# 3. GERADOR DE PDF PROFISSIONAL
# =====================================
class PDF_Solucao(FPDF):
    def header(self):
        # Tenta carregar sua logo se você subir logo.png pro GitHub
        try: self.image('logo.png', 10, 8, 30)
        except: pass
        
        self.set_font('Arial', 'B', 15)
        self.set_text_color(27, 54, 68)
        self.cell(0, 8, EMPRESA["nome"], ln=True, align='R')
        self.set_font('Arial', '', 9)
        self.cell(0, 5, f"CNPJ: {EMPRESA['cnpj']}", ln=True, align='R')
        self.cell(0, 5, EMPRESA["endereco"], ln=True, align='R')
        self.cell(0, 5, f"Contato: {EMPRESA['telefone']}", ln=True, align='R')
        self.ln(10)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(10)

def gerar_pdf(cliente, servico, valor, p_entrada):
    pdf = PDF_Solucao()
    pdf.add_page()
    
    # Título do Orçamento
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 10, f"ORÇAMENTO DE SERVIÇOS", ln=True, align='C')
    pdf.ln(5)
    
    # Dados do Cliente
    pdf.set_font('Arial', 'B', 11)
    pdf.cell(0, 10, f"CLIENTE: {cliente.upper()}", border='B', ln=True)
    pdf.set_font('Arial', '', 11)
    pdf.ln(5)
    
    # Descrição
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(0, 7, "DESCRIÇÃO DOS SERVIÇOS:", ln=True)
    pdf.set_font('Arial', '', 11)
    pdf.multi_cell(0, 7, servico)
    pdf.ln(10)
    
    # Valores
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(130, 12, "TOTAL DA MÃO DE OBRA", 1, 0, 'L', True)
    pdf.cell(60, 12, f"R$ {valor:,.2f}", 1, 1, 'C', True)
    
    if p_entrada > 0:
        v_entrada = valor * (p_entrada / 100)
        pdf.set_font('Arial', 'I', 10)
        pdf.set_text_color(150, 0, 0)
        pdf.cell(0, 10, f"* Condição de pagamento: {p_entrada}% de entrada (R$ {v_entrada:,.2f})", ln=True)
    
    return pdf.output(dest='S').encode('latin1')

# =====================================
# 4. INTERFACE DO USUÁRIO
# =====================================
st.title("🏗️ Solução Reforma & Construção")
st.write(f"Bem-vindo, **{EMPRESA['responsavel']}**")

aba1, aba2 = st.tabs(["📝 Novo Orçamento", "📊 Histórico de Obras"])

with aba1:
    with st.form("form_orcamento", clear_on_submit=False):
        c1, c2 = st.columns([2, 1])
        nome_cliente = c1.text_input("Nome do Cliente")
        data_hoje = c2.date_input("Data", datetime.now())
        
        desc_servico = st.text_area("O que será feito? (Descreva detalhadamente)", height=150)
        
        c3, c4 = st.columns(2)
        v_total = c3.number_input("Valor da Mão de Obra (R$)", min_value=0.0, step=50.0)
        porc_entrada = c4.slider("% de Entrada Requerida", 0, 100, 65)
        
        btn_salvar = st.form_submit_button("SALVAR NA PLANILHA E GERAR PDF")

    if btn_salvar:
        if nome_cliente and v_total > 0:
            try:
                # Salva no Google Sheets
                df_existente = conn.read()
                novo_registro = pd.DataFrame([{
                    "Data": data_hoje.strftime("%d/%m/%Y"),
                    "Cliente": nome_cliente,
                    "Serviço": desc_servico,
                    "Valor Total": v_total,
                    "Entrada %": porc_entrada
                }])
                df_atualizado = pd.concat([df_existente, novo_registro], ignore_index=True)
                conn.update(data=df_atualizado)
                
                # Gera o PDF
                pdf_res = gerar_pdf(nome_cliente, desc_servico, v_total, porc_entrada)
                
                st.success("✅ Tudo pronto! Os dados já estão na sua planilha.")
                st.download_button(
                    label="⬇️ BAIXAR ORÇAMENTO (PDF)",
                    data=pdf_res,
                    file_name=f"Orcamento_{nome_cliente}.pdf",
                    mime="application/pdf"
                )
            except Exception as e:
                st.error(f"Erro ao conectar com a planilha: {e}")
        else:
            st.warning("Preencha o nome do cliente e o valor para continuar.")

with aba2:
    st.subheader("Registros da Planilha Google")
    if st.button("🔄 Atualizar Lista"):
        st.cache_data.clear()
    
    try:
        dados_planilha = conn.read()
        st.dataframe(dados_planilha, use_container_width=True)
    except:
        st.info("Aguardando conexão com a planilha...")
