import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time as dtime
import urllib.parse
import pdfplumber
import re
import os
from fpdf import FPDF

# =========================
# CONFIGURAÇÃO GERAL
# =========================
st.set_page_config(
    page_title="ObraGestor Pro",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# CSS
st.markdown(
    """
    <style>
      .block-container { 
          padding-top: 3.5rem; 
          padding-bottom: 3rem; 
          max-width: 1200px; 
      }
      .card {
          background: rgba(255,255,255,0.95);
          border: 1px solid rgba(0,0,0,0.08);
          border-radius: 16px;
          padding: 20px;
          box-shadow: 0 2px 10px rgba(0,0,0,0.04);
          margin-bottom: 15px;
      }
      .alert-card {
          background-color: #FEF3C7;
          border-left: 5px solid #F59E0B;
          padding: 15px;
          border-radius: 8px;
          margin-bottom: 20px;
      }
      .kpi-title { font-size: 14px; opacity: .70; margin-bottom: 4px; font-weight: 500; }
      .kpi-value { font-size: 26px; font-weight: 800; color: #1f2937; }
      .stButton>button { width: 100%; height: 3.2em; border-radius: 12px; font-weight: 600; }
    </style>
    """,
    unsafe_allow_html=True,
)

CLIENTES_FILE = "clientes.csv"
OBRAS_FILE = "obras.csv"

# =========================
# FUNÇÕES DE SUPORTE
# =========================
def br_money(x) -> str:
    try:
        val = float(x)
        return f"R$ {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "R$ 0,00"

def ensure_cols(df, cols_defaults: dict):
    if df is None:
        df = pd.DataFrame()
    for c, d in cols_defaults.items():
        if c not in df.columns:
            df[c] = d
    return df

def normalize_status(s):
    s = str(s or "").strip()
    if s == "" or s.lower() == "nan":
        return "🔵 Agendamento"
    return s

def link_maps(endereco):
    return "https://www.google.com/maps/search/?api=1&query=" + urllib.parse.quote(str(endereco))

def link_calendar(titulo, data_visita, hora_visita, duracao_min, local):
    inicio_dt = datetime.combine(data_visita, hora_visita)
    fim_dt = inicio_dt + timedelta(minutes=int(duracao_min))
    start = inicio_dt.strftime("%Y%m%dT%H%M%S")
    end = fim_dt.strftime("%Y%m%dT%H%M%S")
    base = "https://calendar.google.com/calendar/render?action=TEMPLATE"
    params = f"&text={urllib.parse.quote(titulo)}&dates={start}/{end}&details={urllib.parse.quote('Visita Técnica')}&location={urllib.parse.quote(str(local))}&ctz=America/Sao_Paulo"
    return base + params

def load_data():
    if not os.path.exists(CLIENTES_FILE):
        cols_c = ["ID", "Nome", "Telefone", "Email", "Endereco", "Data_Cadastro"]
        df_c = pd.DataFrame(columns=cols_c)
        df_c.to_csv(CLIENTES_FILE, index=False)
    else:
        df_c = pd.read_csv(CLIENTES_FILE)

    if not os.path.exists(OBRAS_FILE):
        cols_o = [
            "ID", "Cliente", "Status",
            "Data_Contato", "Data_Visita", "Data_Orcamento", "Data_Aceite", "Data_Conclusao",
            "Custo_MO", "Custo_Material", "Total", "Entrada", "Pago", "Descricao", "Observacoes"
        ]
        df_o = pd.DataFrame(columns=cols_o)
        df_o.to_csv(OBRAS_FILE, index=False)
    else:
        df_o = pd.read_csv(OBRAS_FILE)

    defaults_c = {"ID": None, "Nome": "", "Telefone": "", "Email": "", "Endereco": "", "Data_Cadastro": ""}
    df_c = ensure_cols(df_c, defaults_c)

    defaults_o = {
        "ID": None, "Cliente": "", "Status": "🔵 Agendamento",
        "Data_Contato": None, "Data_Visita": None, "Data_Orcamento": None,
        "Data_Aceite": None, "Data_Conclusao": None,
        "Custo_MO": 0.0, "Custo_Material": 0.0, "Total": 0.0,
        "Entrada": 0.0, "Pago": False, "Descricao": "", "Observacoes": ""
    }
    df_o = ensure_cols(df_o, defaults_o)

    df_c["Nome"] = df_c["Nome"].astype(str).replace("nan", "").fillna("").str.strip()
    df_o["Cliente"] = df_o["Cliente"].astype(str).replace("nan", "").fillna("").str.strip()
    df_o["Status"] = df_o["Status"].apply(normalize_status)
    df_o["Observacoes"] = df_o["Observacoes"].astype(str).replace("nan", "").fillna("")
    
    for col in ["Custo_MO", "Custo_Material", "Total", "Entrada"]:
        df_o[col] = pd.to_numeric(df_o[col], errors="coerce").fillna(0.0)

    df_o["Pago"] = df_o["Pago"].astype(str).str.strip().str.lower().isin(["true", "1", "yes", "sim"])

    for col in ["Data_Visita", "Data_Orcamento", "Data_Conclusao", "Data_Contato"]:
        df_o[col] = pd.to_datetime(df_o[col], errors="coerce").dt.date

    return df_c, df_o

def save_data(df_c, df_o):
    df_c.to_csv(CLIENTES_FILE, index=False)
    df_o.to_csv(OBRAS_FILE, index=False)

def limpar_obras(df):
    if df is None or df.empty: return df
    df = df.copy()
    cols_needed = {"ID": None, "Cliente": "", "Descricao": "", "Data_Orcamento": None, "Total": 0.0, "Observacoes": ""}
    df = ensure_cols(df, cols_needed)
    df["Cliente"] = df["Cliente"].astype(str).replace("nan", "").fillna("").str.strip()
    df = df[df["Cliente"] != ""].reset_index(drop=True)
    
    df["ID"] = pd.to_numeric(df["ID"], errors="coerce")
    if df["ID"].isna().any():
        max_id = 0
        if df["ID"].max() > 0: max_id = int(df["ID"].max())
        for idx in df.index[df["ID"].isna()]:
            max_id += 1
            df.at[idx, "ID"] = max_id
            
    df["ID"] = df["ID"].astype(int)
    df = df.drop_duplicates(subset=["ID"], keep="last")
    return df.reset_index(drop=True)

# =========================
# GERAÇÃO DE PDF (COM ACENTOS)
# =========================
class PDFOrcamento(FPDF):
    def header(self):
        # Função interna para garantir acentos no cabeçalho
        def txt_h(s):
            return str(s).encode('latin-1', 'replace').decode('latin-1')

        # Logo
        logo_path = None
        if os.path.exists("logo.png"): logo_path = "logo.png"
        elif os.path.exists("logo.png.jpg"): logo_path = "logo.png.jpg"
        
        if logo_path:
            self.image(logo_path, x=10, y=8, w=30)
            
        # Título / Empresa
        self.set_xy(45, 10)
        self.set_font('Arial', 'B', 14)
        self.cell(0, 8, txt_h('Solução Reforma e Construção'), 0, 1, 'L')
        
        self.set_x(45)
        self.set_font('Arial', 'B', 9)
        self.cell(0, 5, txt_h('Solução CNPJ sob o nº 46.580.382/0001-70'), 0, 1, 'L')
        
        self.set_x(45)
        self.set_font('Arial', '', 8)
        self.cell(0, 4, txt_h('Rua Bandeirantes, 1303, Bairro Pedra Mole, CEP 64065040, TERESINA PI'), 0, 1, 'L')
        
        self.set_x(45)
        self.cell(0, 4, 'Email: solucoesreformaseconstrucao@gmail.com | Tel: (86) 9.9813-2225', 0, 1, 'L')
        
        self.ln(8)
        self.line(10, 38, 200, 38)
        self.ln(5)

    def footer(self):
        def txt_f(s):
            return str(s).encode('latin-1', 'replace').decode('latin-1')
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, txt_f(f'Página {self.page_no()}'), 0, 0, 'C')

def gerar_pdf_bytes(dados_obra):
    pdf = PDFOrcamento()
    pdf.add_page()
    
    # Função para codificar acentos do conteúdo
    def txt(s):
        return str(s).encode('latin-1', 'replace').decode('latin-1')

    # Dados do Orçamento
    pdf.set_xy(10, 45)
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, txt(f"ORÇAMENTO Nº {dados_obra['ID']}"), 0, 1, 'L')
    
    pdf.set_font('Arial', '', 10)
    data_orc = dados_obra.get('Data_Orcamento')
    if not data_orc: data_orc = datetime.now().date()
    pdf.cell(0, 6, txt(f"Data de Emissão: {data_orc.strftime('%d/%m/%Y')}"), 0, 1, 'L')
    pdf.ln(4)

    # Dados do Cliente
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(0, 8, txt(f"CLIENTE: {dados_obra['Cliente']}"), 1, 1, 'L', fill=True)
    pdf.ln(4)

    # Descrição
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(0, 6, txt("DESCRIÇÃO DOS SERVIÇOS:"), 0, 1, 'L')
    pdf.set_font('Arial', '', 10)
    pdf.multi_cell(0, 6, txt(dados_obra['Descricao']))
    pdf.ln(8)

    # Valores
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(0, 6, txt("RESUMO DE VALORES:"), 0, 1, 'L')
    
    pdf.set_font('Arial', '', 10)
    total = float(dados_obra.get('Total', 0))
    entrada = float(dados_obra.get('Entrada', 0))
    
    if entrada > 0:
        pdf.cell(100, 8, txt("Entrada (Sinal):"), 1, 0, 'L')
        pdf.cell(0, 8, txt(br_money(entrada)), 1, 1, 'R')
    
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(100, 10, txt("TOTAL DO ORÇAMENTO:"), 1, 0, 'L', fill=True)
    pdf.cell(0, 10, txt(br_money(total)), 1, 1, 'R', fill=True)
    
    pdf.ln(20)
    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 5, txt("________________________________________________"), 0, 1, 'C')
    pdf.cell(0, 5, txt("Assinatura do Responsável"), 0, 1, 'C')

    return pdf.output(dest='S').encode('latin-1')

# =========================
# FUNÇÕES DE IMPORTAÇÃO
# =========================
def extrair_texto_pdf(pdf_file) -> str:
    try:
        with pdfplumber.open(pdf_file) as pdf:
            partes = []
            for page in pdf.pages:
                t = page.extract_text()
                if t: partes.append(t)
            return "\n".join(partes).strip()
    except: return ""

def brl_to_float(valor_txt: str) -> float:
    s = str(valor_txt or "").strip()
    s = s.replace("\xa0", " ").replace("R$", "").strip()
    s = re.sub(r"[^0-9\.,]", "", s)
    if not s: return 0.0
    if "," in s: s = s.replace(".", "").replace(",", ".")
    return float(s)

def normalizar_data_ddmmaa(data_txt: str) -> str:
    data_txt = str(data_txt).strip()
    try:
        if re.search(r"\d{2}/\d{2}/\d{2}$", data_txt):
            return datetime.strptime(data_txt, "%d/%m/%y").strftime("%d/%m/%Y")
        if re.search(r"\d{2}/\d{2}/\d{4}$", data_txt):
            return data_txt
    except: pass
    return data_txt

def extrair_dados_pdf_solucao(text: str):
    text = (text or "").replace("\r", "")
    linhas = [l.strip() for l in text.split("\n") if l.strip()]
    dados = {}
    m = re.search(r"(?:Cliente|Para|Sr\(a\)|Nome)[:\s]*\s*(.+)", text, flags=re.IGNORECASE)
    dados["Cliente"] = m.group(1).strip() if m else "Cliente Novo"

    m = re.search(r"Criado em[:\s]*(\d{2}/\d{2}/\d{2,4})", text, flags=re.IGNORECASE)
    if not m: m = re.search(r"(\d{2}/\d{2}/\d{2,4})", text)
    dados["Data"] = normalizar_data_ddmmaa(m.group(1)) if m else datetime.now().strftime("%d/%m/%Y")

    total = None
    m = re.search(r"Total[:\s]*(?:R\$\s*)?([\d\.\,]+)", text, flags=re.IGNORECASE)
    if m:
        try: total = brl_to_float(m.group(1))
        except: pass
    
    if total is None or total == 0:
        achados = re.findall(r"(?:R\$\s*)?(\d{1,3}(?:\.\d{3})*,\d{2})", text)
        vals = []
        for a in achados:
            try: vals.append(brl_to_float(a))
            except: pass
        if vals: total = max(vals)

    dados["Total"] = float(total) if total is not None else 0.0

    ignore_list = ["solução reforma", "antônio francisco", "rua bandeirantes", "pedra mole", "contato:", "orçamento", "criado em", "cliente:", "total:", "valor:"]
    capturar = False
    desc = []

    for l in linhas:
        low = l.lower()
        if low.startswith("descrição"):
            capturar = True
            if ":" in l:
                resto = l.split(":", 1)[1].strip()
                if resto and "valor" not in resto.lower(): desc.append(resto)
            continue

        if capturar:
            if low.startswith("total"): break
            if low.startswith("valor"): continue
            if any(bad in low for bad in ignore_list): continue
            if re.fullmatch(r"[R$\s]*\d{1,3}(?:\.\d{3})*,\d{2}", l.strip()): continue
            desc.append(l)

    dados["Descricao"] = "\n".join(desc).strip() if desc else "Serviço de Reforma"
    return dados

def extrair_dados_pdf(pdf_file):
    text = extrair_texto_pdf(pdf_file)
    if not text: return None
    return extrair_dados_pdf_solucao(text)

def resumo_por_cliente(df_c, df_o):
    if df_c.empty: return pd.DataFrame()
    base = df_c.copy()
    if df_o is None or df_o.empty:
        base["Fase"] = "Sem obra"
        base["Total"] = 0.0; base["Recebido"] = 0.0; base["Pendente"] = 0.0
        return base[["Nome", "Telefone", "Endereco", "Fase", "Total", "Recebido", "Pendente"]]

    o = df_o.copy()
    o["Status"] = o["Status"].apply(normalize_status)
    o["Data_Visita_dt"] = pd.to_datetime(o["Data_Visita"], errors="coerce")
    
    o_sort = o.sort_values(["Cliente", "Data_Visita_dt"])
    ult = o_sort.groupby("Cliente", as_index=False).tail(1)[["Cliente", "Status"]]
    mapa_fase = dict(zip(ult["Cliente"].astype(str), ult["Status"].astype(str)))

    total = o.groupby("Cliente", as_index=False)["Total"].sum()
    recebido = o.copy()
    recebido["Recebido_calc"] = recebido.apply(lambda r: float(r["Total"]) if bool(r["Pago"]) else float(r["Entrada"]), axis=1)
    recebido_sum = recebido.groupby("Cliente", as_index=False)["Recebido_calc"].sum().rename(columns={"Recebido_calc": "Recebido"})

    base["Fase"] = base["Nome"].astype(str).map(mapa_fase).fillna("Sem obra")
    base = base.merge(total, how="left", left_on="Nome", right_on="Cliente").drop(columns=["Cliente"], errors="ignore")
    base = base.merge(recebido_sum, how="left", left_on="Nome", right_on="Cliente").drop(columns=["Cliente"], errors="ignore")
    base["Total"] = pd.to_numeric(base.get("Total", 0.0), errors="coerce").fillna(0.0)
    base["Recebido"] = pd.to_numeric(base.get("Recebido", 0.0), errors="coerce").fillna(0.0)
    base["Pendente"] = (base["Total"] - base["Recebido"]).clip(lower=0.0)
    return base[["Nome", "Telefone", "Endereco", "Fase", "Total", "Recebido", "Pendente"]]

def excluir_cliente(df_clientes, df_obras, nome, apagar_obras=True):
    nome = str(nome).strip()
    df_clientes = df_clientes[df_clientes["Nome"].astype(str).str.strip() != nome].reset_index(drop=True)
    if apagar_obras and (df_obras is not None) and (not df_obras.empty):
        df_obras = df_obras[df_obras["Cliente"].astype(str).str.strip() != nome].reset_index(drop=True)
    return df_clientes, df_obras

def excluir_obra(df_obras, obra_id):
    if df_obras is None or df_obras.empty: return df_obras
    obra_id = int(obra_id)
    df_obras = df_obras[df_obras["ID"].astype(int) != obra_id].reset_index(drop=True)
    return df_obras

# =========================
# MAIN APP
# =========================
df_clientes, df_obras = load_data()
df_obras = limpar_obras(df_obras)
save_data(df_clientes, df_obras)

st.sidebar.title("🏗️ ObraGestor Pro")
menu = st.sidebar.radio("Navegação", ["Dashboard", "Gestão de Obras", "Clientes", "Importar/Exportar"])

if menu == "Dashboard":
    st.markdown("<div class='section-title'>Visão Geral</div>", unsafe_allow_html=True)
    obras_ativas = 0
    valor_total = 0.0
    recebido_total = 0.0
    if not df_obras.empty:
        obras_ativas = len(df_obras[~df_obras["Status"].isin(["🟢 Concluído", "🔴 Cancelado"])])
        valor_total = float(df_obras["Total"].sum())
        recebido_total = float(df_obras.apply(lambda r: float(r["Total"]) if bool(r["Pago"]) else float(r["Entrada"]), axis=1).sum())

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(f"<div class='card'><div class='kpi-title'>Obras ativas</div><div class='kpi-value'>{obras_ativas}</div></div>", unsafe_allow_html=True)
    c2.markdown(f"<div class='card'><div class='kpi-title'>Clientes</div><div class='kpi-value'>{len(df_clientes)}</div></div>", unsafe_allow_html=True)
    c3.markdown(f"<div class='card'><div class='kpi-title'>Total Contratos</div><div class='kpi-value'>{br_money(valor_total)}</div></div>", unsafe_allow_html=True)
    c4.markdown(f"<div class='card'><div class='kpi-title'>Total Recebido</div><div class='kpi-value'>{br_money(recebido_total)}</div></div>", unsafe_allow_html=True)
    
    st.write("")
    if not df_obras.empty:
        hoje = datetime.now().date()
        df_contatos = df_obras[
            (df_obras["Data_Contato"].notnull()) & 
            (~df_obras["Status"].isin(["🟢 Concluído", "🔴 Cancelado"]))
        ].copy()
        
        df_contatos["Data_Contato_dt"] = pd.to_datetime(df_contatos["Data_Contato"], errors='coerce').dt.date
        df_contatos = df_contatos[df_contatos["Data_Contato_dt"].notna()]
        pendentes = df_contatos[df_contatos["Data_Contato_dt"] <= hoje + timedelta(days=7)].sort_values("Data_Contato_dt")
        
        if not pendentes.empty:
            st.markdown("<div class='alert-card'><h4>📞 Lembretes de Contato (Hoje e Próximos)</h4>", unsafe_allow_html=True)
            for _, row in pendentes.iterrows():
                d_cont = row["Data_Contato_dt"]
                d_fmt = d_cont.strftime("%d/%m")
                nome = row["Cliente"]
                status = row["Status"]
                msg_pre = ""
                if d_cont < hoje: msg_pre = "🔴 ATRASADO: "
                elif d_cont == hoje: msg_pre = "🟡 HOJE: "
                else: msg_pre = f"🔵 {d_fmt}: "
                st.markdown(f"**{msg_pre}** Entrar em contato com **{nome}** ({status})")
            st.markdown("</div>", unsafe_allow_html=True)
    
    st.write("")
    resumo = resumo_por_cliente(df_clientes, df_obras)
    if resumo.empty: st.info("Sem dados para exibir ainda.")
    else:
        r_show = resumo.copy()
        r_show["Total"] = r_show["Total"].apply(br_money)
        r_show["Recebido"] = r_show["Recebido"].apply(br_money)
        r_show["Pendente"] = r_show["Pendente"].apply(br_money)
        st.dataframe(r_show, use_container_width=True)

elif menu == "Importar/Exportar":
    st.markdown("<div class='section-title'>Importar / Exportar</div>", unsafe_allow_html=True)
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.subheader("1) Upload e Importação Automática")
    pdf_file = st.file_uploader("Selecione o arquivo PDF", type="pdf")
    
    if pdf_file:
        if "dados_pdf_cache" not in st.session_state or st.session_state.get("last_pdf") != pdf_file.name:
            dados_brutos = extrair_dados_pdf(pdf_file)
            st.session_state["dados_pdf_cache"] = dados_brutos
            st.session_state["last_pdf"] = pdf_file.name

        dados_pdf = st.session_state["dados_pdf_cache"]
        if dados_pdf:
            st.success("✅ PDF lido! Confira e salve.")
            st.divider()
            with st.form("form_importacao"):
                c_imp1, c_imp2 = st.columns(2)
                imp_cliente = c_imp1.text_input("Nome do Cliente", value=dados_pdf.get("Cliente", ""))
                val_data = datetime.now().date()
                if dados_pdf.get("Data"):
                    try: val_data = datetime.strptime(dados_pdf["Data"], "%d/%m/%Y").date()
                    except: pass
                imp_data = c_imp2.date_input("Data do Orçamento", value=val_data)
                imp_total = st.number_input("Valor Total (R$)", value=float(dados_pdf.get("Total", 0.0)), step=10.0)
                imp_desc = st.text_area("Descrição do Serviço", value=dados_pdf.get("Descricao", ""), height=100)
                
                if st.form_submit_button("💾 CONFIRMAR E SALVAR"):
                    imp_clean = imp_cliente.strip()
                    existe_cli = False
                    if not df_clientes.empty:
                         if imp_clean in df_clientes["Nome"].astype(str).str.strip().values:
                             existe_cli = True
                    
                    if not existe_cli:
                         novo_id_cli = 1
                         if not df_clientes.empty:
                             try: novo_id_cli = int(df_clientes["ID"].max()) + 1
                             except: pass
                         novo_cliente = pd.DataFrame([{
                             "ID": novo_id_cli, "Nome": imp_clean, "Telefone": "", "Email": "", "Endereco": "", 
                             "Data_Cadastro": datetime.now().strftime("%Y-%m-%d")
                         }])
                         df_clientes = pd.concat([df_clientes, novo_cliente], ignore_index=True)
                         st.toast(f"Novo cliente '{imp_clean}' cadastrado!")

                    # LOGICA DE ID INICIANDO EM 111
                    novo_id_obra = 111
                    if not df_obras.empty:
                        try:
                            max_id = int(df_obras["ID"].max())
                            novo_id_obra = max_id + 1 if max_id > 0 else 111
                        except: pass
                    
                    nova_obra = pd.DataFrame([{
                        "ID": novo_id_obra, "Cliente": imp_clean, "Status": "🟠 Orçamento Enviado",
                        "Data_Orcamento": imp_data, "Data_Visita": imp_data,
                        "Data_Contato": imp_data + timedelta(days=2),
                        "Total": imp_total, "Descricao": imp_desc,
                        "Custo_MO": imp_total, "Custo_Material": 0.0, "Entrada": 0.0, "Pago": False,
                        "Observacoes": ""
                    }])
                    df_obras = pd.concat([df_obras, nova_obra], ignore_index=True)
                    df_obras = limpar_obras(df_obras)
                    save_data(df_clientes, df_obras)
                    st.success(f"Importação concluída! Orçamento #{novo_id_obra} criado.")
                    st.balloons()
                    del st.session_state["dados_pdf_cache"]
        else: st.error("Erro ao ler PDF.")
    st.markdown("</div>", unsafe_allow_html=True)

elif menu == "Clientes":
    st.markdown("<div class='section-title'>Clientes</div>", unsafe_allow_html=True)
    tab1, tab2, tab3, tab4 = st.tabs(["Listagem", "Novo", "Editar", "Excluir"])
    
    with tab1:
        resumo = resumo_por_cliente(df_clientes, df_obras)
        if resumo.empty: st.info("Nenhum cliente cadastrado.")
        else:
            r_show = resumo.copy()
            r_show["Total"] = r_show["Total"].apply(br_money)
            r_show["Recebido"] = r_show["Recebido"].apply(br_money)
            r_show["Pendente"] = r_show["Pendente"].apply(br_money)
            st.dataframe(r_show, use_container_width=True)
    
    with tab2:
        st.caption("Cadastrar novo cliente")
        with st.form("form_novo_cliente", clear_on_submit=True):
            nome = st.text_input("Nome*")
            tel = st.text_input("Telefone")
            email = st.text_input("E-mail")
            end = st.text_input("Endereço")
            if st.form_submit_button("Salvar Cliente"):
                if not nome.strip(): st.error("Nome é obrigatório.")
                else:
                    novo_id = 1
                    if not df_clientes.empty:
                        try: novo_id = int(pd.to_numeric(df_clientes["ID"], errors='coerce').max()) + 1
                        except: novo_id = 1
                    novo_registro = pd.DataFrame([{
                        "ID": novo_id, "Nome": nome.strip(), "Telefone": tel.strip(),
                        "Email": email.strip(), "Endereco": end.strip(),
                        "Data_Cadastro": datetime.now().strftime("%Y-%m-%d")
                    }])
                    df_clientes = pd.concat([df_clientes, novo_registro], ignore_index=True)
                    save_data(df_clientes, df_obras)
                    st.success("Cliente salvo!")
                    st.rerun()

    with tab3:
        st.caption("Editar dados de um cliente existente")
        if df_clientes.empty: 
            st.info("Nenhum cliente para editar.")
        else:
            lista_nomes = sorted(df_clientes["Nome"].astype(str).str.strip().unique())
            cli_edit = st.selectbox("Selecione o Cliente para Editar", lista_nomes)
            
            if cli_edit:
                dados_atuais = df_clientes[df_clientes["Nome"].astype(str).str.strip() == cli_edit].iloc[0]
                with st.form("form_editar_cliente"):
                    id_cli = dados_atuais["ID"]
                    novo_nome = st.text_input("Nome", value=dados_atuais["Nome"])
                    novo_tel = st.text_input("Telefone", value=str(dados_atuais["Telefone"]))
                    novo_email = st.text_input("E-mail", value=str(dados_atuais["Email"]))
                    novo_end = st.text_input("Endereço", value=str(dados_atuais["Endereco"]))
                    
                    if st.form_submit_button("Atualizar Dados"):
                        df_clientes = df_clientes[df_clientes["ID"] != id_cli]
                        linha_atualizada = pd.DataFrame([{
                            "ID": id_cli, "Nome": novo_nome.strip(), 
                            "Telefone": novo_tel.strip(), "Email": novo_email.strip(), "Endereco": novo_end.strip(),
                            "Data_Cadastro": dados_atuais["Data_Cadastro"]
                        }])
                        df_clientes = pd.concat([df_clientes, linha_atualizada], ignore_index=True)
                        if novo_nome.strip() != cli_edit:
                            df_obras.loc[df_obras["Cliente"] == cli_edit, "Cliente"] = novo_nome.strip()
                        save_data(df_clientes, df_obras)
                        st.success("Dados atualizados!")
                        st.rerun()

    with tab4:
        if df_clientes.empty: st.info("Nada para excluir.")
        else:
            lista_nomes = sorted(df_clientes["Nome"].astype(str).str.strip().unique())
            nome_del = st.selectbox("Selecione o Cliente para Excluir", lista_nomes)
            del_obras = st.checkbox("Apagar também as obras deste cliente?", value=True)
            confirm_del = st.checkbox("Confirmo a exclusão", value=False)
            if st.button("Excluir Cliente Definitivamente"):
                if not confirm_del: st.error("Marque a caixa de confirmação.")
                else:
                    df_clientes, df_obras = excluir_cliente(df_clientes, df_obras, nome_del, del_obras)
                    df_obras = limpar_obras(df_obras)
                    save_data(df_clientes, df_obras)
                    st.success("Cliente excluído com sucesso.")
                    st.rerun()

elif menu == "Gestão de Obras":
    st.markdown("<div class='section-title'>Gestão de Obras</div>", unsafe_allow_html=True)
    if df_clientes.empty: st.warning("Cadastre clientes primeiro.")
    else:
        lista_cli = sorted(df_clientes["Nome"].astype(str).str.strip().unique())
        cli_sel = st.selectbox("Selecione o Cliente", [""] + lista_cli)
        
        if cli_sel:
            dados_cli_row = df_clientes[df_clientes["Nome"].astype(str).str.strip() == cli_sel]
            end_cliente = ""
            if not dados_cli_row.empty:
                end_cliente = str(dados_cli_row.iloc[0]["Endereco"])

            obras_do_cli = df_obras[df_obras["Cliente"].astype(str).str.strip() == cli_sel]
            
            if obras_do_cli.empty: 
                st.info("Este cliente não tem obras.")
            else:
                st.caption("Histórico:")
                show_o = obras_do_cli.copy()
                show_o["Total"] = show_o["Total"].apply(br_money)
                st.dataframe(show_o[["ID", "Status", "Data_Visita", "Data_Orcamento", "Total"]], use_container_width=True)
            
            st.divider()
            
            with st.expander("➕ Adicionar / Editar Obra", expanded=True):
                opcoes_obras = ["Nova Obra"]
                idx_selecao = 0 
                if not obras_do_cli.empty:
                    lista_ids = [f"ID {row['ID']} - {row['Status']}" for _, row in obras_do_cli.iterrows()]
                    opcoes_obras += lista_ids
                    idx_selecao = len(opcoes_obras) - 1

                if idx_selecao < 0: idx_selecao = 0
                
                obra_selecionada = st.selectbox("Selecione a obra para editar:", opcoes_obras, index=idx_selecao)
                
                dados_obra = {
                    "ID": None, "Status": "🔵 Agendamento", "Descricao": "", "Observacoes": "",
                    "Custo_MO": 0.0, "Custo_Material": 0.0, "Entrada": 0.0, "Pago": False,
                    "Total": 0.0,
                    "Data_Visita": datetime.now().date(), "Data_Orcamento": datetime.now().date(),
                    "Data_Contato": datetime.now().date()
                }

                if obra_selecionada != "Nova Obra":
                    try:
                        id_selecionado = int(obra_selecionada.split("ID ")[1].split(" -")[0])
                        filtro = df_obras[df_obras["ID"] == id_selecionado]
                        if not filtro.empty:
                            dados_obra = filtro.iloc[0].to_dict()
                    except: pass

                # === AREA DE AÇÃO RÁPIDA ===
                if obra_selecionada != "Nova Obra":
                    st.markdown("##### 🚀 Ações Rápidas")
                    col_act1, col_act2 = st.columns(2)
                    
                    with col_act1:
                        raw_visita = dados_obra.get("Data_Visita")
                        d_visita_dt = datetime.now().date()
                        if pd.notnull(raw_visita):
                            try: d_visita_dt = pd.to_datetime(raw_visita).date()
                            except: pass
                            
                        link_cal = link_calendar(f"Visita: {cli_sel}", d_visita_dt, dtime(9,0), 60, end_cliente)
                        st.markdown(f'''<a href="{link_cal}" target="_blank" style="text-decoration:none;"><button style="width:100%; padding:0.5rem; background-color:#E8F0FE; color:#1967D2; border:1px solid #1967D2; border-radius:8px; cursor:pointer;">📅 Agendar Visita no Google</button></a>''', unsafe_allow_html=True)
                    
                    with col_act2:
                        if end_cliente and len(end_cliente) > 3:
                            link_waze = link_maps(end_cliente)
                            st.markdown(f'''<a href="{link_waze}" target="_blank" style="text-decoration:none;"><button style="width:100%; padding:0.5rem; background-color:#CEEAD6; color:#137333; border:1px solid #137333; border-radius:8px; cursor:pointer;">📍 Abrir Rota (Maps)</button></a>''', unsafe_allow_html=True)
                        else:
                            st.warning("⚠️ Cadastre o endereço para liberar o mapa.")
                    st.write("") 

                with st.form("form_obra"):
                    status = st.selectbox("Status", ["🔵 Agendamento", "🟠 Orçamento Enviado", "🟤 Execução", "🟢 Concluído", "🔴 Cancelado"], index=["🔵 Agendamento", "🟠 Orçamento Enviado", "🟤 Execução", "🟢 Concluído", "🔴 Cancelado"].index(normalize_status(dados_obra["Status"])))
                    desc = st.text_area("Descrição (Vai no PDF)", value=str(dados_obra["Descricao"]))
                    obs_internas = st.text_area("Notas / Observações Internas (Só pra você)", value=str(dados_obra.get("Observacoes", "")), placeholder="Ex: Cliente prefere contato após as 14h; Comprar cimento...")

                    c_date1, c_date2, c_date3 = st.columns(3)
                    def clean_dt(val):
                        if pd.isnull(val): return datetime.now().date()
                        try: return pd.to_datetime(val).date()
                        except: return datetime.now().date()

                    d_visita = c_date1.date_input("Data Visita", value=clean_dt(dados_obra.get("Data_Visita")))
                    d_orc = c_date2.date_input("Data Orçamento", value=clean_dt(dados_obra.get("Data_Orcamento")))
                    d_contato = c_date3.date_input("Próximo Contato/Ligar", value=clean_dt(dados_obra.get("Data_Contato")))
                    
                    c3, c4, c5 = st.columns(3)
                    val_mo = float(dados_obra["Custo_MO"]); val_mat = float(dados_obra["Custo_Material"]); val_tot = float(dados_obra.get("Total", 0.0))
                    if val_mo == 0 and val_mat == 0 and val_tot > 0: val_mo = val_tot

                    mo = c3.number_input("Mão de Obra (R$)", value=val_mo, step=10.0)
                    mat = c4.number_input("Materiais (R$)", value=val_mat, step=10.0)
                    ent = c5.number_input("Entrada (R$)", value=float(dados_obra["Entrada"]), step=10.0)
                    pago = st.checkbox("Pago Integralmente?", value=bool(dados_obra["Pago"]))
                    
                    total_calc = mo + mat
                    st.markdown(f"**Total Calculado:** {br_money(total_calc)}")
                    
                    if st.form_submit_button("💾 Salvar Obra"):
                        novo_id = dados_obra["ID"]
                        if novo_id is None or novo_id == 0:
                            # LOGICA DE ID INICIANDO EM 111 (se não tiver obras)
                            if df_obras.empty:
                                novo_id = 111
                            else:
                                try: novo_id = int(df_obras["ID"].max()) + 1
                                except: novo_id = 111
                        else:
                             df_obras = df_obras[df_obras["ID"] != novo_id]
                        
                        nova_linha = {
                            "ID": novo_id, "Cliente": cli_sel, "Status": status, "Descricao": desc,
                            "Observacoes": obs_internas,
                            "Custo_MO": mo, "Custo_Material": mat, "Total": total_calc,
                            "Entrada": ent, "Pago": pago, 
                            "Data_Visita": d_visita, "Data_Orcamento": d_orc, "Data_Contato": d_contato
                        }
                        for col in df_obras.columns:
                            if col not in nova_linha: nova_linha[col] = None
                            
                        df_obras = pd.concat([df_obras, pd.DataFrame([nova_linha])], ignore_index=True)
                        save_data(df_clientes, df_obras)
                        st.success(f"Obra salva com sucesso! (ID #{novo_id})")
                        st.rerun()
                
                if obra_selecionada != "Nova Obra":
                    st.write("")
                    st.markdown("##### 📄 Exportar Orçamento")
                    if st.button("Gerar PDF do Orçamento"):
                        try:
                            pdf_bytes = gerar_pdf_bytes(dados_obra)
                            file_name = f"Orcamento_{dados_obra['ID']}_{cli_sel.replace(' ', '_')}.pdf"
                            st.download_button(
                                label="⬇️ Baixar PDF Pronto",
                                data=pdf_bytes,
                                file_name=file_name,
                                mime="application/pdf"
                            )
                            st.success("PDF gerado com sucesso! Clique acima para baixar.")
                        except Exception as e:
                            st.error(f"Erro ao gerar PDF: {e}")
            
            st.divider()
            with st.expander("🗑️ Excluir uma Obra"):
                if obras_do_cli.empty: st.info("Nada para excluir.")
                else:
                    lista_ids = obras_do_cli["ID"].astype(int).tolist()
                    id_del = st.selectbox("Selecione o ID da Obra", lista_ids)
                    confirm_obra = st.checkbox("Confirmo exclusão da obra", value=False)
                    if st.button("Excluir Obra"):
                        if not confirm_obra: st.error("Confirme a exclusão.")
                        else:
                            df_obras = excluir_obra(df_obras, id_del)
                            df_obras = limpar_obras(df_obras)
                            save_data(df_clientes, df_obras)
                            st.success("Obra removida.")
                            st.rerun()
