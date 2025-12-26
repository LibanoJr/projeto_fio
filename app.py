import streamlit as st
import requests
import google.generativeai as genai
import os
import re
from dotenv import load_dotenv
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
import io

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Auditoria IA - Gov", page_icon="⚖️", layout="wide")
load_dotenv()

API_KEY_GOVERNO = os.getenv("API_KEY_GOVERNO")
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# --- SESSION STATE ---
if 'dados_busca' not in st.session_state:
    st.session_state['dados_busca'] = None
if 'cnpj_atual' not in st.session_state:
    st.session_state['cnpj_atual'] = ""
if 'nome_empresa_atual' not in st.session_state:
    st.session_state['nome_empresa_atual'] = ""

# --- FUNÇÕES ---

def buscar_dados_receita(cnpj):
    """
    Busca o Nome/Razão Social na BrasilAPI (Pública e Gratuita)
    Para garantir que estamos auditando a empresa certa.
    """
    cnpj_limpo = re.sub(r'\D', '', cnpj)
    url = f"https://brasilapi.com.br/api/cnpj/v1/{cnpj_limpo}"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            dados = response.json()
            # Retorna Razão Social ou Nome Fantasia
            return dados.get('razao_social', dados.get('nome_fantasia', 'Nome não encontrado'))
        return None
    except:
        return None

def buscar_contratos():
    url = "https://api.portaldatransparencia.gov.br/api-de-dados/contratos"
    headers = {"chave-api-dados": API_KEY_GOVERNO}
    params = {"dataInicioVigencia": "01/01/2024", "dataFimVigencia": "31/12/2024", "codigoOrgao": "26000", "pagina": 1}
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        return response.json() if response.status_code == 200 else []
    except:
        return []

def analisar_ia(texto):
    modelo = genai.GenerativeModel("gemini-pro")
    try:
        return modelo.generate_content(f"Auditoria resumida deste objeto de contrato: {texto}").text
    except:
        return "Erro IA."

def consultar_ficha_suja_blindada(cnpj_alvo):
    """
    CONSULTA BLINDADA: Filtra falsos positivos manualmente.
    """
    cnpj_alvo_limpo = re.sub(r'\D', '', cnpj_alvo)
    url = "https://api.portaldatransparencia.gov.br/api-de-dados/ceis"
    headers = {"chave-api-dados": API_KEY_GOVERNO}
    params = {"cnpjSancionado": cnpj_alvo_limpo, "pagina": 1}
    
    lista_filtrada = []
    try:
        response = requests.get(url, headers=headers, params=params, timeout=15)
        if response.status_code == 200:
            dados_brutos = response.json()
            for item in dados_brutos:
                try:
                    cnpj_da_api = item.get('pessoa', {}).get('cnpjFormatado', '')
                    if re.sub(r'\D', '', cnpj_da_api) == cnpj_alvo_limpo:
                        lista_filtrada.append(item)
                except:
                    continue
        return lista_filtrada
    except:
        return []

def gerar_pdf(cnpj, nome, dados):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()
    
    elements.append(Paragraph(f"RELATÓRIO DE AUDITORIA", styles['Title']))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(f"<b>Empresa:</b> {nome}", styles['Normal']))
    elements.append(Paragraph(f"<b>CNPJ:</b> {cnpj}", styles['Normal']))
    elements.append(Spacer(1, 20))
    
    data = [["Sanção", "Órgão", "Data"]]
    for d in dados:
        tipo = d.get('tipoSancao',{}).get('descricaoResumida','Unknown')[:40]
        orgao = d.get('orgaoSancionador',{}).get('nome','Unknown')[:30]
        data_pub = d.get('dataPublicacaoSancao', '-')
        data.append([tipo, orgao, data_pub])
        
    t = Table(data, colWidths=[200, 180, 80])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.darkblue),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 1, colors.black)
    ]))
    elements.append(t)
    doc.build(elements)
    buffer.seek(0)
    return buffer

# --- FRONTEND ---
st.sidebar.title("👮‍♂️ Menu Auditoria")
if st.sidebar.button("🗑️ Nova Consulta"):
    st.session_state.clear()
    st.rerun()

opcao = st.sidebar.radio("Opção:", ["🔍 Analisar Contratos", "🚫 Consultar Empresa (CNPJ)"])

st.title("🏛️ Sistema de Compliance")

if opcao == "🔍 Analisar Contratos":
    if st.button("Buscar Contratos MEC"):
        contratos = buscar_contratos()
        if contratos:
            st.success(f"{len(contratos)} contratos recentes.")
            for c in contratos[:2]:
                with st.expander(f"Contrato R$ {c.get('valorInicialCompra')}"):
                    st.write(c.get('objeto'))
                    st.info(analisar_ia(c.get('objeto')))

elif opcao == "🚫 Consultar Empresa (CNPJ)":
    st.header("Investigação de CNPJ")
    
    with st.form("busca"):
        cnpj_in = st.text_input("CNPJ:")
        btn = st.form_submit_button("Identificar e Investigar")
    
    if btn:
        if len(re.sub(r'\D','',cnpj_in)) != 14:
            st.error("CNPJ inválido.")
        else:
            # 1. Busca o Nome da Empresa (BrasilAPI)
            with st.spinner("Identificando empresa na Receita..."):
                nome_empresa = buscar_dados_receita(cnpj_in)
                
            if nome_empresa:
                st.session_state['nome_empresa_atual'] = nome_empresa
                st.success(f"🏢 Empresa Identificada: **{nome_empresa}**")
                
                # 2. Busca Sanções (Gov API)
                with st.spinner(f"Auditando bases do governo para {nome_empresa}..."):
                    resultado_real = consultar_ficha_suja_blindada(cnpj_in)
                    st.session_state['dados_busca'] = resultado_real
                    st.session_state['cnpj_atual'] = cnpj_in
            else:
                st.warning("CNPJ não encontrado na base da Receita Federal (BrasilAPI). Verifique o número.")

    # Exibição Final
    if st.session_state['dados_busca'] is not None and st.session_state['nome_empresa_atual']:
        # Verifica consistência
        input_limpo = re.sub(r'\D','', cnpj_in)
        memoria_limpo = re.sub(r'\D','', st.session_state['cnpj_atual'])

        if input_limpo == memoria_limpo:
            sancoes = st.session_state['dados_busca']
            nome = st.session_state['nome_empresa_atual']
            
            if len(sancoes) == 0:
                st.divider()
                st.success(f"✅ NADA CONSTA: {nome}")
                st.markdown(f"A empresa **{nome}** (CNPJ {st.session_state['cnpj_atual']}) foi auditada e **não possui registros** no Cadastro de Empresas Inidôneas (CEIS).")
                st.balloons()
            else:
                st.divider()
                st.error(f"🚨 ALERTA: {len(sancoes)} PROCESSOS PARA {nome}")
                
                pdf = gerar_pdf(st.session_state['cnpj_atual'], nome, sancoes)
                st.download_button("📥 Baixar Relatório", data=pdf, file_name=f"auditoria_{nome}.pdf")
                
                for s in sancoes:
                    st.write(f"**Motivo:** {s.get('fundamentacao',[{}])[0].get('descricao','-')}")