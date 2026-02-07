import streamlit as st
import pdfplumber
import re
from datetime import datetime, timedelta, time
import urllib.parse

st.set_page_config(page_title="ObraGestor Pro", page_icon="🏗️", layout="centered")

st.title("ObraGestor Pro")

def extrair_texto_pdf(pdf_file) -> str:
    with pdfplumber.open(pdf_file) as pdf:
        partes = []
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                partes.append(t)
        return "\n".join(partes).strip()

def brl_to_float(valor_txt: str) -> float:
    v = str(valor_txt).strip().replace("R$", "").strip()
    v = v.replace(".", "").replace(",", ".")
    return float(v)

def normalizar_data_ddmmaa(data_txt: str) -> str:
    data_txt = str(data_txt).strip()
    try:
        if re.search(r"\\d{2}/\\d{2}/\\d{2}$", data_txt):
            return datetime.strptime(data_txt, "%d/%m/%y").strftime("%d/%m/%Y")
        if re.search(r"\\d{2}/\\d{2}/\\d{4}$", data_txt):
            return data_txt
    except Exception:
        pass
    return data_txt

def extrair_dados_pdf_solucao(text: str):
    if not re.search(r"ORÇAMENTO", text, flags=re.IGNORECASE):
        return None

    dados = {}

    m = re.search(r"Cliente:\\s*(.+)", text, flags=re.IGNORECASE)
    if m:
        dados["Cliente"] = m.group(1).strip()

    m = re.search(r"Criado em:\\s*(\\d{2}/\\d{2}/\\d{2,4})", text, flags=re.IGNORECASE)
    if m:
        dados["Data"] = normalizar_data_ddmmaa(m.group(1))

    m = re.search(r"Total:\\s*R\\$\\s*([\\d\\.\\,]+)", text, flags=re.IGNORECASE)
    if m:
        try:
            dados["Total"] = brl_to_float(m.group(1))
        except Exception:
            pass

    m = re.search(r"Descrição:\\s*(.*?)\\s*Total:", text, flags=re.IGNORECASE | re.DOTALL)
    if m:
        dados["Descricao"] = m.group(1).strip()

    if "Cliente" not in dados or "Total" not in dados:
        return None

    return dados

def link_maps(endereco):
    return "https://www.google.com/maps/search/?api=1&query=" + urllib.parse.quote(str(endereco))

def link_calendar(titulo, data_visita, hora_visita, duracao_min, local):
    inicio = datetime.combine(data_visita, hora_visita)
    fim = inicio + timedelta(minutes=int(duracao_min))
    start = inicio.strftime("%Y%m%dT%H%M%S")
    end = fim.strftime("%Y%m%dT%H%M%S")
    base = "https://calendar.google.com/calendar/render?action=TEMPLATE"
    return (
        f"{base}"
        f"&text={urllib.parse.quote(titulo)}"
        f"&dates={start}/{end}"
        f"&location={urllib.parse.quote(str(local))}"
        f"&ctz=America/Sao_Paulo"
    )

st.subheader("1) Upload do PDF")
pdf = st.file_uploader("Envie o PDF", type="pdf")

dados = None
if pdf:
    st.subheader("2) Extração")
    texto = extrair_texto_pdf(pdf)
    dados = extrair_dados_pdf_solucao(texto)
    if dados:
        st.success("Extraído com sucesso")
        st.json(dados)
    else:
        st.error("Não consegui extrair desse PDF")

st.subheader("3) Google Calendar")
if dados:
    data_visita = datetime.now().date()
    if dados.get("Data"):
        try:
            data_visita = datetime.strptime(dados["Data"], "%d/%m/%Y").date()
        except Exception:
            pass

    data_visita = st.date_input("Data", value=data_visita)
    hora = st.time_input("Hora", value=time(9, 0))
    dur = st.number_input("Duração (min)", min_value=15, max_value=480, value=60, step=15)
    endereco = st.text_input("Endereço", value="")

    st.link_button("Criar evento", link_calendar(f"Visita: {dados['Cliente']}", data_visita, hora, dur, endereco))

st.subheader("4) Google Maps")
endereco_maps = st.text_input("Endereço para Maps", value="")
st.link_button("Abrir no Maps", link_maps(endereco_maps) if endereco_maps else "#")
