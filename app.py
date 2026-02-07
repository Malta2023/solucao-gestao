import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from fpdf import FPDF
import base64
import os
import urllib.parse

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="ObraGestor", page_icon="🏗️", layout="wide")

# --- GERENCIAMENTO DE DADOS (CSV) ---
CLIENTES_FILE = 'clientes.csv'
OBRAS_FILE = 'obras.csv'

def load_data():
    if not os.path.exists(CLIENTES_FILE):
        df_c = pd.DataFrame(columns=["ID", "Nome", "Telefone", "Email", "Endereco", "Data_Cadastro"])
        df_c.to_csv(CLIENTES_FILE, index=False)
    
    if not os.path.exists(OBRAS_FILE):
        cols = ["ID", "Cliente", "Status", "Data_Contato", "Data_Visita", "Data_Orcamento", 
                "Data_Aceite", "Data_Conclusao", "Custo_MO", "Custo_Material", 
                "Total", "Entrada", "Pago", "Descricao"]
        df_o = pd.DataFrame(columns=cols)
        df_o.to_csv(OBRAS_FILE, index=False)

    return pd.read_csv(CLIENTES_FILE), pd.read_csv(OBRAS_FILE)

def save_data(df_c, df_o):
    df_c.to_csv(CLIENTES_FILE, index=False)
    df_o.to_csv(OBRAS_FILE, index=False)

df_clientes, df_obras = load_data()

# --- FUNÇÕES UTILITÁRIAS ---

# Gerador de PDF
def gerar_pdf(tipo, dados):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    
    # Cabeçalho
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, txt=f"DOCUMENTO: {tipo.upper()}", ln=1, align='C')
    pdf.ln(10)
    
    # Corpo
    pdf.set_font("Arial", size=12)
    for key, value in dados.items():
        pdf.cell(200, 10, txt=f"{key}: {value}", ln=1, align='L')
    
    pdf.ln(20)
    pdf.set_font("Arial", 'I', 10)
    pdf.cell(200, 10, txt="Gerado automaticamente pelo ObraGestor.", ln=1, align='C')
    
    return pdf.output(dest='S').encode('latin-1')

# Links Inteligentes
def link_maps(endereco):
    base = "https://www.google.com/maps/search/?api=1&query="
    return base + urllib.parse.quote(endereco)

def link_calendar(titulo, data_str, local):
    # Formato Google Calendar Link
    # Exige data formato YYYYMMDDTHHmmSSZ
    try:
        dt = datetime.strptime(str(data_str), "%Y-%m-%d")
        # Define horário padrão 09:00 as 10:00 se for apenas data
        start = dt.replace(hour=9, minute=0).strftime("%Y%m%dT%H%M%S")
        end = dt.replace(hour=10, minute=0).strftime("%Y%m%dT%H%M%S")
        
        base = "https://calendar.google.com/calendar/render?action=TEMPLATE"
        details = f"&text={urllib.parse.quote(titulo)}&dates={start}/{end}&details=Visita+Tecnica&location={urllib.parse.quote(local)}"
        return base + details
    except:
        return "#"

# --- INTERFACE ---

st.title("🏗️ ObraGestor Mobile")

# Sidebar para Navegação
menu = st.sidebar.radio("Navegação", ["Dashboard", "Gerenciar Obras", "Banco de Clientes", "Importar CSV"])

# --- ABA: DASHBOARD ---
if menu == "Dashboard":
    st.header("Visão Geral")
    
    # Métricas
    ativos = df_obras[df_obras['Status'] != '🟢 Concluído']['Total'].sum()
    recebidos = df_obras[df_obras['Pago'] == True]['Entrada'].sum() # Simplificação: considera entrada como recebido se pago=True
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Valor em Obras Ativas", f"R$ {ativos:,.2f}")
    col2.metric("Entradas/Caixa", f"R$ {recebidos:,.2f}")
    col3.metric("Obras em Andamento", len(df_obras[df_obras['Status'] == '🟤 Execução']))
    
    st.divider()
    st.subheader("Obras Recentes")
    st.dataframe(df_obras[['Cliente', 'Status', 'Total', 'Data_Visita']].tail(5))

# --- ABA: BANCO DE CLIENTES ---
elif menu == "Banco de Clientes":
    st.header("Clientes")
    
    with st.expander("➕ Novo Cliente"):
        with st.form("form_cliente"):
            c_nome = st.text_input("Nome")
            c_tel = st.text_input("Telefone")
            c_email = st.text_input("Email")
            c_end = st.text_input("Endereço Completo")
            submit_c = st.form_submit_button("Salvar Cliente")
            
            if submit_c and c_nome:
                novo_cliente = {
                    "ID": len(df_clientes) + 1,
                    "Nome": c_nome, "Telefone": c_tel, 
                    "Email": c_email, "Endereco": c_end,
                    "Data_Cadastro": datetime.now().strftime("%Y-%m-%d")
                }
                df_clientes = pd.concat([df_clientes, pd.DataFrame([novo_cliente])], ignore_index=True)
                save_data(df_clientes, df_obras)
                st.success("Cliente salvo!")
                st.rerun()

    # Busca
    search = st.text_input("Buscar cliente...")
    if search:
        st.dataframe(df_clientes[df_clientes['Nome'].str.contains(search, case=False)])
    else:
        st.dataframe(df_clientes)

# --- ABA: GERENCIAR OBRAS (CORE) ---
elif menu == "Gerenciar Obras":
    st.header("Gestão de Obras")
    
    # 1. Seleção ou Criação
    opcoes_clientes = df_clientes['Nome'].tolist()
    
    if not opcoes_clientes:
        st.warning("Cadastre clientes primeiro.")
    else:
        col_sel, col_add = st.columns([3, 1])
        cli_selecionado = col_sel.selectbox("Selecione o Cliente", [""] + opcoes_clientes)
        
        if cli_selecionado:
            # Verifica se já existe obra ativa ou cria nova
            obras_cliente = df_obras[df_obras['Cliente'] == cli_selecionado]
            
            # --- FORMULÁRIO DA OBRA ---
            st.markdown(f"### Obra de: **{cli_selecionado}**")
            
            # Recupera dados do cliente para Maps/Calendar
            dados_cli = df_clientes[df_clientes['Nome'] == cli_selecionado].iloc[0]
            
            # Se já existir obra, permite editar a última (simplificação para demo)
            # Na prática, você selecionaria qual ID da obra editar
            if not obras_cliente.empty:
                obra_atual = obras_cliente.iloc[-1]
                idx_obra = df_obras[df_obras['ID'] == obra_atual['ID']].index[0]
            else:
                # Cria estrutura vazia
                obra_atual = pd.Series(dtype='object')
                idx_obra = -1

            with st.form("form_obra"):
                # Status com Cores (via Emoji)
                status_opts = ["🔵 Agendamento", "🟠 Orçamento Enviado", "🟤 Execução", "🟢 Concluído", "🔴 Cancelado"]
                
                # Tenta pegar valor atual ou default
                st_idx = 0
                if 'Status' in obra_atual and obra_atual['Status'] in status_opts:
                    st_idx = status_opts.index(obra_atual['Status'])
                
                status = st.selectbox("Status Atual", status_opts, index=st_idx)
                
                # Datas
                c1, c2, c3 = st.columns(3)
                dt_visita = c1.date_input("Data Visita", value=pd.to_datetime(obra_atual.get('Data_Visita', datetime.now())))
                dt_orc = c2.date_input("Envio Orçamento", value=pd.to_datetime(obra_atual.get('Data_Orcamento', datetime.now())))
                dt_conc = c3.date_input("Conclusão", value=pd.to_datetime(obra_atual.get('Data_Conclusao', datetime.now())))
                
                # Financeiro (Cálculo Automático)
                st.subheader("Financeiro")
                fc1, fc2, fc3 = st.columns(3)
                mo = fc1.number_input("Mão de Obra (R$)", value=float(obra_atual.get('Custo_MO', 0.0)))
                mat = fc2.number_input("Material (R$)", value=float(obra_atual.get('Custo_Material', 0.0)))
                entrada = fc3.number_input("Entrada (R$)", value=float(obra_atual.get('Entrada', 0.0)))
                
                total = mo + mat
                st.markdown(f"**Total: R$ {total:.2f}**")
                
                pago = st.checkbox("Pagamento Total Recebido?", value=bool(obra_atual.get('Pago', False)))
                desc = st.text_area("Descrição do Serviço", value=str(obra_atual.get('Descricao', '')))
                
                # Botões de Ação dentro do Form
                salvar = st.form_submit_button("💾 Salvar Alterações")

            # --- LÓGICA DE SALVAMENTO ---
            if salvar:
                dados_obra = {
                    "ID": len(df_obras) + 1 if idx_obra == -1 else obra_atual['ID'],
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
                    # Atualiza linha existente
                    for key, val in dados_obra.items():
                        df_obras.at[idx_obra, key] = val
                
                save_data(df_clientes, df_obras)
                st.success("Obra Atualizada!")
                st.rerun()

            # --- AÇÕES EXTERNAS (Fora do form para interatividade) ---
            st.divider()
            ac1, ac2, ac3, ac4 = st.columns(4)
            
            # 1. Mapa
            url_map = link_maps(dados_cli['Endereco'])
            ac1.link_button("📍 Abrir Mapa", url_map)
            
            # 2. Calendar
            if status == "🔵 Agendamento":
                url_cal = link_calendar(f"Visita: {cli_selecionado}", dt_visita, dados_cli['Endereco'])
                ac2.link_button("📅 Add Agenda", url_cal)
            
            # 3. Gerar PDF Orçamento
            if ac3.button("📄 PDF Orçamento"):
                dados_pdf = {
                    "Cliente": cli_selecionado, "Servico": desc,
                    "Mao de Obra": f"R$ {mo}", "Material": f"R$ {mat}",
                    "TOTAL": f"R$ {total}", "Validade": "15 dias"
                }
                pdf_bytes = gerar_pdf("Orçamento", dados_pdf)
                st.download_button("Baixar Orçamento", data=pdf_bytes, file_name="orcamento.pdf", mime="application/pdf")

            # 4. Gerar Recibo
            if ac4.button("🧾 PDF Recibo"):
                dados_pdf = {
                    "Recebemos de": cli_selecionado, "Valor": f"R$ {entrada if not pago else total}",
                    "Referente a": desc, "Data": str(datetime.now().date())
                }
                pdf_bytes = gerar_pdf("Recibo", dados_pdf)
                st.download_button("Baixar Recibo", data=pdf_bytes, file_name="recibo.pdf", mime="application/pdf")

# --- ABA: IMPORTAR CSV ---
elif menu == "Importar CSV":
    st.header("Importação de Dados Antigos")
    uploaded_file = st.file_uploader("Escolha um arquivo CSV", type="csv")
    if uploaded_file is not None:
        df_import = pd.read_csv(uploaded_file)
        st.write("Visualização:", df_import.head())
        
        # Mapeamento simples
        col_nome = st.selectbox("Qual coluna é o NOME?", df_import.columns)
        col_tel = st.selectbox("Qual coluna é o TELEFONE?", df_import.columns)
        
        if st.button("Importar"):
            for index, row in df_import.iterrows():
                novo = {
                    "ID": len(df_clientes) + 1 + index,
                    "Nome": row[col_nome],
                    "Telefone": row[col_tel],
                    "Email": "", "Endereco": "", 
                    "Data_Cadastro": datetime.now().strftime("%Y-%m-%d")
                }
                df_clientes = pd.concat([df_clientes, pd.DataFrame([novo])], ignore_index=True)
            
            save_data(df_clientes, df_obras)
            st.success(f"{len(df_import)} clientes importados!")
