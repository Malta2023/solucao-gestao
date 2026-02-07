import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from fpdf import FPDF
import base64
import os
import urllib.parse

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="ObraGestor Pro", 
    page_icon="🏗️", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- ESTILO CSS PERSONALIZADO ---
st.markdown("""
    <style>
    .main {
        background-color: #f8f9fa;
    }
    .stMetric {
        background-color: #ffffff;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .stButton>button {
        width: 100%;
        border-radius: 5px;
        height: 3em;
        transition: all 0.3s;
    }
    .stButton>button:hover {
        border-color: #ff4b4b;
        color: #ff4b4b;
    }
    div[data-testid="stExpander"] {
        background-color: #ffffff;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        margin-bottom: 1rem;
    }
    </style>
    """, unsafe_allow_html=True)

# --- GERENCIAMENTO DE DADOS (CSV) ---
CLIENTES_FILE = 'clientes.csv'
OBRAS_FILE = 'obras.csv'

def load_data():
    if not os.path.exists(CLIENTES_FILE):
        df_c = pd.DataFrame(columns=["ID", "Nome", "Telefone", "Email", "Endereco", "Data_Cadastro"])
        df_c.to_csv(CLIENTES_FILE, index=False)
    else:
        df_c = pd.read_csv(CLIENTES_FILE)
    
    if not os.path.exists(OBRAS_FILE):
        cols = ["ID", "Cliente", "Status", "Data_Contato", "Data_Visita", "Data_Orcamento", 
                "Data_Aceite", "Data_Conclusao", "Custo_MO", "Custo_Material", 
                "Total", "Entrada", "Pago", "Descricao"]
        df_o = pd.DataFrame(columns=cols)
        df_o.to_csv(OBRAS_FILE, index=False)
    else:
        df_o = pd.read_csv(OBRAS_FILE)
        # Garantir que datas sejam lidas corretamente
        date_cols = ["Data_Visita", "Data_Orcamento", "Data_Conclusao"]
        for col in date_cols:
            if col in df_o.columns:
                df_o[col] = pd.to_datetime(df_o[col]).dt.date

    return df_c, df_o

def save_data(df_c, df_o):
    df_c.to_csv(CLIENTES_FILE, index=False)
    df_o.to_csv(OBRAS_FILE, index=False)

df_clientes, df_obras = load_data()

# --- FUNÇÕES UTILITÁRIAS ---

def gerar_pdf(tipo, dados):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    
    # Cabeçalho com Estilo
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font("Helvetica", 'B', 18)
    pdf.cell(0, 20, txt=f"OBRAGESTOR - {tipo.upper()}", ln=1, align='C', fill=True)
    pdf.ln(10)
    
    # Corpo
    pdf.set_font("Helvetica", 'B', 12)
    for key, value in dados.items():
        pdf.set_text_color(100, 100, 100)
        pdf.cell(50, 10, txt=f"{key}:", ln=0)
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Helvetica", '', 12)
        pdf.cell(0, 10, txt=str(value), ln=1)
        pdf.set_font("Helvetica", 'B', 12)
    
    pdf.ln(20)
    pdf.set_font("Helvetica", 'I', 10)
    pdf.set_text_color(150, 150, 150)
    pdf.cell(0, 10, txt=f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=1, align='C')
    
    return pdf.output(dest='S').encode('latin-1', 'replace')

def link_maps(endereco):
    base = "https://www.google.com/maps/search/?api=1&query="
    return base + urllib.parse.quote(str(endereco))

def link_calendar(titulo, data_str, local):
    try:
        dt = pd.to_datetime(data_str)
        start = dt.strftime("%Y%m%dT090000Z")
        end = dt.strftime("%Y%m%dT100000Z")
        base = "https://calendar.google.com/calendar/render?action=TEMPLATE"
        details = f"&text={urllib.parse.quote(titulo)}&dates={start}/{end}&details=Visita+Tecnica&location={urllib.parse.quote(str(local))}"
        return base + details
    except:
        return "#"

# --- INTERFACE ---

st.sidebar.title("🏗️ ObraGestor Pro")
menu = st.sidebar.radio("Navegação", ["📊 Dashboard", "🏗️ Gestão de Obras", "👥 Clientes", "📥 Importar/Exportar"])

# --- ABA: DASHBOARD ---
if menu == "📊 Dashboard":
    st.title("Visão Geral do Negócio")
    
    # Métricas Processadas
    total_obras = len(df_obras)
    obras_ativas = len(df_obras[~df_obras['Status'].isin(['🟢 Concluído', '🔴 Cancelado'])])
    
    # Soma de valores
    valor_total_ativas = df_obras[~df_obras['Status'].isin(['🟢 Concluído', '🔴 Cancelado'])]['Total'].sum()
    recebido = df_obras[df_obras['Pago'] == True]['Total'].sum() + df_obras[df_obras['Pago'] == False]['Entrada'].sum()
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Obras Ativas", obras_ativas)
    col2.metric("Total em Contratos", f"R$ {valor_total_ativas:,.2f}")
    col3.metric("Caixa Estimado", f"R$ {recebido:,.2f}")
    col4.metric("Total de Clientes", len(df_clientes))
    
    st.divider()
    
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Próximas Visitas")
        hoje = datetime.now().date()
        proximas = df_obras[df_obras['Data_Visita'] >= hoje].sort_values('Data_Visita').head(5)
        if not proximas.empty:
            st.table(proximas[['Cliente', 'Data_Visita', 'Status']])
        else:
            st.info("Nenhuma visita agendada para os próximos dias.")
            
    with c2:
        st.subheader("Status das Obras")
        if not df_obras.empty:
            status_counts = df_obras['Status'].value_counts()
            st.bar_chart(status_counts)
        else:
            st.info("Sem dados para exibir o gráfico.")

# --- ABA: CLIENTES ---
elif menu == "👥 Clientes":
    st.title("Gestão de Clientes")
    
    tab1, tab2 = st.tabs(["Listagem", "Novo Cliente"])
    
    with tab1:
        search = st.text_input("🔍 Buscar cliente por nome ou telefone...")
        if search:
            filtered_df = df_clientes[
                df_clientes['Nome'].str.contains(search, case=False, na=False) | 
                df_clientes['Telefone'].str.contains(search, case=False, na=False)
            ]
            st.dataframe(filtered_df, use_container_width=True)
        else:
            st.dataframe(df_clientes, use_container_width=True)
            
    with tab2:
        with st.form("form_cliente", clear_on_submit=True):
            col_a, col_b = st.columns(2)
            c_nome = col_a.text_input("Nome Completo*")
            c_tel = col_b.text_input("Telefone/WhatsApp")
            c_email = col_a.text_input("E-mail")
            c_end = col_b.text_input("Endereço de Obra")
            
            submit_c = st.form_submit_button("✅ Cadastrar Cliente")
            
            if submit_c:
                if c_nome:
                    novo_id = df_clientes['ID'].max() + 1 if not df_clientes.empty else 1
                    novo_cliente = {
                        "ID": novo_id,
                        "Nome": c_nome, "Telefone": c_tel, 
                        "Email": c_email, "Endereco": c_end,
                        "Data_Cadastro": datetime.now().strftime("%Y-%m-%d")
                    }
                    df_clientes = pd.concat([df_clientes, pd.DataFrame([novo_cliente])], ignore_index=True)
                    save_data(df_clientes, df_obras)
                    st.success(f"Cliente {c_nome} cadastrado com sucesso!")
                    st.rerun()
                else:
                    st.error("O nome do cliente é obrigatório.")

# --- ABA: GESTÃO DE OBRAS ---
elif menu == "🏗️ Gestão de Obras":
    st.title("Controle de Obras e Orçamentos")
    
    if df_clientes.empty:
        st.warning("⚠️ Você precisa cadastrar clientes antes de gerenciar obras.")
    else:
        # Seleção de Cliente
        cliente_nomes = sorted(df_clientes['Nome'].unique())
        cli_selecionado = st.selectbox("Selecione o Cliente para gerenciar a obra:", [""] + cliente_nomes)
        
        if cli_selecionado:
            obras_cliente = df_obras[df_obras['Cliente'] == cli_selecionado]
            
            # Escolher entre editar existente ou criar nova
            if not obras_cliente.empty:
                obra_id_options = ["Nova Obra"] + [f"Obra ID {id}" for id in obras_cliente['ID'].tolist()]
                obra_selecao = st.radio("Selecione a obra:", obra_id_options, horizontal=True)
            else:
                obra_selecao = "Nova Obra"
            
            # Preparar dados da obra
            if obra_selecao == "Nova Obra":
                obra_atual = pd.Series({
                    'Status': "🔵 Agendamento",
                    'Data_Visita': datetime.now().date(),
                    'Data_Orcamento': datetime.now().date(),
                    'Data_Conclusao': datetime.now().date() + timedelta(days=30),
                    'Custo_MO': 0.0, 'Custo_Material': 0.0, 'Entrada': 0.0,
                    'Pago': False, 'Descricao': ""
                })
                idx_obra = -1
            else:
                id_obra = int(obra_selecao.split("ID ")[1])
                idx_obra = df_obras[df_obras['ID'] == id_obra].index[0]
                obra_atual = df_obras.loc[idx_obra]

            # Formulário de Edição/Criação
            with st.expander("📝 Detalhes da Obra", expanded=True):
                with st.form("form_obra_detalhe"):
                    status_opts = ["🔵 Agendamento", "🟠 Orçamento Enviado", "🟤 Execução", "🟢 Concluído", "🔴 Cancelado"]
                    
                    c1, c2 = st.columns(2)
                    status = c1.selectbox("Status Atual", status_opts, index=status_opts.index(obra_atual['Status']) if obra_atual['Status'] in status_opts else 0)
                    desc = c2.text_input("Breve descrição do serviço", value=str(obra_atual['Descricao']))
                    
                    st.markdown("---")
                    d1, d2, d3 = st.columns(3)
                    dt_visita = d1.date_input("Data da Visita", value=obra_atual['Data_Visita'])
                    dt_orc = d2.date_input("Data do Orçamento", value=obra_atual['Data_Orcamento'])
                    dt_conc = d3.date_input("Previsão Conclusão", value=obra_atual['Data_Conclusao'])
                    
                    st.markdown("---")
                    f1, f2, f3 = st.columns(3)
                    mo = f1.number_input("Mão de Obra (R$)", value=float(obra_atual['Custo_MO']), min_value=0.0, step=100.0)
                    mat = f2.number_input("Materiais (R$)", value=float(obra_atual['Custo_Material']), min_value=0.0, step=100.0)
                    entrada = f3.number_input("Valor de Entrada (R$)", value=float(obra_atual['Entrada']), min_value=0.0, step=100.0)
                    
                    total = mo + mat
                    st.info(f"💰 **Valor Total do Contrato: R$ {total:,.2f}**")
                    
                    pago = st.checkbox("Pagamento Total Recebido", value=bool(obra_atual['Pago']))
                    
                    salvar = st.form_submit_button("💾 Salvar Obra")
                    
                    if salvar:
                        dados_obra = {
                            "ID": df_obras['ID'].max() + 1 if idx_obra == -1 else obra_atual['ID'],
                            "Cliente": cli_selecionado,
                            "Status": status,
                            "Data_Visita": dt_visita,
                            "Data_Orcamento": dt_orc,
                            "Data_Conclusao": dt_conc,
                            "Custo_MO": mo, "Custo_Material": mat,
                            "Total": total, "Entrada": entrada,
                            "Pago": pago, "Descricao": desc
                        }
                        
                        if idx_obra == -1:
                            df_obras = pd.concat([df_obras, pd.DataFrame([dados_obra])], ignore_index=True)
                        else:
                            for key, val in dados_obra.items():
                                df_obras.at[idx_obra, key] = val
                        
                        save_data(df_clientes, df_obras)
                        st.success("Dados salvos com sucesso!")
                        st.rerun()

            # Ações e Documentos
            if idx_obra != -1:
                st.subheader("🛠️ Ações Rápidas")
                dados_cli = df_clientes[df_clientes['Nome'] == cli_selecionado].iloc[0]
                
                ac1, ac2, ac3, ac4 = st.columns(4)
                
                with ac1:
                    st.link_button("📍 Ver Endereço", link_maps(dados_cli['Endereco']))
                
                with ac2:
                    if status == "🔵 Agendamento":
                        st.link_button("📅 Agendar Visita", link_calendar(f"Visita: {cli_selecionado}", dt_visita, dados_cli['Endereco']))
                    else:
                        st.button("📅 Agendar", disabled=True)
                
                with ac3:
                    pdf_orc = gerar_pdf("Orçamento", {
                        "Cliente": cli_selecionado, "Serviço": desc,
                        "Mão de Obra": f"R$ {mo:,.2f}", "Materiais": f"R$ {mat:,.2f}",
                        "TOTAL": f"R$ {total:,.2f}", "Data": dt_orc.strftime("%d/%m/%Y")
                    })
                    st.download_button("📄 Baixar Orçamento", data=pdf_orc, file_name=f"orcamento_{cli_selecionado}.pdf", mime="application/pdf")
                
                with ac4:
                    valor_recibo = total if pago else entrada
                    pdf_rec = gerar_pdf("Recibo", {
                        "Recebemos de": cli_selecionado, "Valor": f"R$ {valor_recibo:,.2f}",
                        "Referente a": desc, "Data": datetime.now().strftime("%d/%m/%Y")
                    })
                    st.download_button("🧾 Baixar Recibo", data=pdf_rec, file_name=f"recibo_{cli_selecionado}.pdf", mime="application/pdf")

# --- ABA: IMPORTAR/EXPORTAR ---
elif menu == "📥 Importar/Exportar":
    st.title("Gerenciamento de Dados")
    
    col_imp, col_exp = st.columns(2)
    
    with col_imp:
        st.subheader("Importar Clientes")
        uploaded_file = st.file_uploader("Upload CSV de Clientes", type="csv")
        if uploaded_file:
            try:
                df_import = pd.read_csv(uploaded_file)
                st.write("Amostra dos dados:", df_import.head(2))
                
                col_n = st.selectbox("Coluna Nome", df_import.columns)
                col_t = st.selectbox("Coluna Telefone", df_import.columns)
                
                if st.button("Confirmar Importação"):
                    for _, row in df_import.iterrows():
                        novo_id = df_clientes['ID'].max() + 1 if not df_clientes.empty else 1
                        novo = {
                            "ID": novo_id, "Nome": row[col_n], "Telefone": row[col_t],
                            "Email": "", "Endereco": "", "Data_Cadastro": datetime.now().strftime("%Y-%m-%d")
                        }
                        df_clientes = pd.concat([df_clientes, pd.DataFrame([novo])], ignore_index=True)
                    save_data(df_clientes, df_obras)
                    st.success("Importação concluída!")
            except Exception as e:
                st.error(f"Erro ao processar arquivo: {e}")
                
    with col_exp:
        st.subheader("Exportar Dados")
        st.write("Baixe seus dados atuais para backup.")
        
        csv_c = df_clientes.to_csv(index=False).encode('utf-8')
        st.download_button("💾 Baixar Clientes (CSV)", csv_c, "clientes_backup.csv", "text/csv")
        
        csv_o = df_obras.to_csv(index=False).encode('utf-8')
        st.download_button("💾 Baixar Obras (CSV)", csv_o, "obras_backup.csv", "text/csv")
