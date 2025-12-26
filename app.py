import streamlit as st
import requests
import pandas as pd
import google.generativeai as genai
import os
from dotenv import load_dotenv
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
import io

# --- CONFIGURAÇÃO INICIAL DA PÁGINA ---
st.set_page_config(page_title="Auditoria IA - Gov", page_icon="⚖️", layout="wide")
load_dotenv()

# --- CONFIGURAÇÃO DE CHAVES DE API ---
API_KEY_GOVERNO = os.getenv("API_KEY_GOVERNO")
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# --- INICIALIZAÇÃO DA MEMÓRIA (SESSION STATE) ---
if 'dados_busca' not in st.session_state:
    st.session_state['dados_busca'] = None
if 'cnpj_atual' not in st.session_state:
    st.session_state['cnpj_atual'] = ""

# --- FUNÇÕES DE BACKEND ---
def buscar_contratos():
    url = "https://api.portaldatransparencia.gov.br/api-de-dados/contratos"
    headers = {"chave-api-dados": API_KEY_GOVERNO}
    params = {"dataInicioVigencia": "01/01/2024", "dataFimVigencia": "31/01/2024", "codigoOrgao": "26000", "pagina": 1}
    try:
        response = requests.get(url, headers=headers, params=params)
        return response.json() if response.status_code == 200 else []
    except:
        return []

def analisar_ia(texto_contrato):
    modelo = genai.GenerativeModel("gemini-pro")
    prompt = f"Analise este contrato público como um auditor e diga se há riscos ou se é vago: {texto_contrato}"
    try:
        return modelo.generate_content(prompt).text
    except:
        return "Erro na análise de IA."

def consultar_ficha_suja(cnpj_consulta):
    cnpj_limpo = cnpj_consulta.replace(".", "").replace("/", "").replace("-", "")
    url = "https://api.portaldatransparencia.gov.br/api-de-dados/ceis"
    headers = {"chave-api-dados": API_KEY_GOVERNO}
    params = {"cnpjSancionado": cnpj_limpo, "pagina": 1}
    try:
        response = requests.get(url, headers=headers, params=params)
        return response.json() if response.status_code == 200 else []
    except:
        return []

def gerar_pdf_relatorio(cnpj, dados_sancoes):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()
    elements.append(Paragraph(f"RELATÓRIO DE AUDITORIA", styles['Title']))
    elements.append(Paragraph(f"<b>CNPJ Alvo:</b> {cnpj}", styles['Normal']))
    elements.append(Spacer(1, 12))
    dados_tabela = [["Tipo de Sanção", "Órgão", "Data"]]
    for item in dados_sancoes:
        tipo = item.get('tipoSancao', {}).get('descricaoResumida', 'N/A')[:50]
        orgao = item.get('orgaoSancionador', {}).get('nome', 'N/A')[:40]
        data = item.get('dataPublicacaoSancao', 'N/A')
        dados_tabela.append([tipo, orgao, data])
    tabela = Table(dados_tabela)
    tabela.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.darkred), ('TEXTCOLOR', (0,0), (-1,0), colors.white), ('GRID', (0,0), (-1,-1), 1, colors.black)]))
    elements.append(tabela)
    doc.build(elements)
    buffer.seek(0)
    return buffer

# --- INTERFACE VISUAL ---
st.sidebar.title("👮‍♂️ Menu de Auditoria")

# --- BOTÃO MÁGICO DE LIMPEZA ---
if st.sidebar.button("🗑️ Nova Consulta (Limpar Tudo)"):
    st.session_state.clear()
    st.rerun()

opcao = st.sidebar.radio("Ferramentas:", ["🔍 Analisar Contratos (IA)", "🚫 Consultar Ficha Suja (CNPJ)"])

st.title("🏛️ Sistema de Auditoria e Compliance Governamental")

if opcao == "🔍 Analisar Contratos (IA)":
    st.header("Análise de Contratos MEC")
    if st.button("Buscar Contratos"):
        with st.spinner("Analisando..."):
            dados = buscar_contratos()
            for contrato in dados[:2]:
                st.write(f"**Contrato:** {contrato.get('objeto', 'N/A')}")
                st.markdown(analisar_ia(contrato.get('objeto', '')))
                st.divider()

elif opcao == "🚫 Consultar Ficha Suja (CNPJ)":
    st.header("Investigação de CNPJ (CEIS)")
    with st.form("form_busca"):
        cnpj_input = st.text_input("CNPJ (Apenas números):")
        btn_buscar = st.form_submit_button("Investigar")
    
    if btn_buscar:
        if len(cnpj_input) < 14:
            st.error("CNPJ inválido.")
        else:
            st.session_state['dados_busca'] = consultar_ficha_suja(cnpj_input)
            st.session_state['cnpj_atual'] = cnpj_input

    if st.session_state['dados_busca'] is not None and st.session_state['cnpj_atual'] == cnpj_input:
        sancoes = st.session_state['dados_busca']
        if sancoes:
            st.error(f"🚨 {len(sancoes)} PROCESSOS ENCONTRADOS!")
            st.download_button("Baixar PDF", data=gerar_pdf_relatorio(cnpj_input, sancoes), file_name="relatorio.pdf")
            for item in sancoes:
                st.write(f"**Sanção:** {item.get('tipoSancao', {}).get('descricaoResumida')}")
        else:
            st.success("✅ Nada Consta. Empresa Limpa!")
            st.balloons()