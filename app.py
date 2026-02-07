import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Solução Gestão Pro", page_icon="🏗️", layout="wide")

conn = st.connection("gsheets", type=GSheetsConnection)

def cor_status(status):
    cores = {"🟡 Orçado": "orange", "🟢 Em Obra": "blue", "✅ Finalizado": "purple", "💰 Pago": "green"}
    return cores.get(status, "grey")

st.title("🏗️ Solução Gestão: Central do Cliente")

tab1, tab2 = st.tabs(["📝 Novo Orçamento", "👥 Gestão por Cliente"])

with tab1:
    with st.form("orc_form"):
        col1, col2 = st.columns(2)
        cliente = col1.text_input("Nome do Cliente")
        fone = col2.text_input("Telefone/Zap")
        servico = st.text_area("Descrição do Serviço")
        col3, col4 = st.columns(2)
        valor = col3.number_input("Valor Total (R$)", min_value=0.0)
        status = col4.selectbox("Status Atual", ["🟡 Orçado", "🟢 Em Obra", "✅ Finalizado", "💰 Pago"])
        if st.form_submit_button("Salvar Orçamento"):
            df_old = conn.read()
            novo = pd.DataFrame([{
                "Data": datetime.now().strftime("%d/%m/%Y"),
                "Cliente": cliente,
                "Telefone": fone,
                "Serviço": servico,
                "Total": valor,
                "Status": status
            }])
            conn.update(data=pd.concat([df_old, novo], ignore_index=True))
            st.success("Salvo com sucesso!")

with tab2:
    st.subheader("Histórico Consolidado")
    try:
        df = conn.read()
        if not df.empty:
            # Pega a lista de clientes únicos
            clientes_unicos = df['Cliente'].unique()
            
            for c in clientes_unicos:
                # Filtra todos os orçamentos desse cliente
                obras_cliente = df[df['Cliente'] == c]
                qtd = len(obras_cliente)
                
                # Cria uma "Pasta" para o cliente
                with st.expander(f"👤 {c.upper()} ({qtd} orçamento(s))"):
                    st.write(f"**Contato:** {obras_cliente.iloc[0]['Telefone']}")
                    st.markdown("---")
                    
                    # Lista cada orçamento/obra dele
                    for i, row in obras_cliente.iterrows():
                        col_status, col_info = st.columns([1, 4])
                        
                        # Mostra a bolinha colorida do Status
                        col_status.markdown(f"### :{cor_status(row['Status'])}[{row['Status']}]")
                        
                        # Mostra os detalhes do orçamento
                        with col_info:
                            st.write(f"**Data:** {row['Data']} | **Valor:** R$ {row['Total']:,.2f}")
                            st.write(f"*Serviço:* {row['Serviço']}")
                            st.divider()
        else:
            st.info("Nenhum dado encontrado na planilha.")
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
