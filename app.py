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

# --- FUNÇÕES ---

def buscar_contratos():
    """Busca contratos (Mantivemos a mesma lógica)"""
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
    CONSULTA BLINDADA:
    Mesmo que a API devolva lixo, nós filtramos manualmente aqui.
    """
    # 1. Limpa o CNPJ alvo (só números)
    cnpj_alvo_limpo = re.sub(r'\D', '', cnpj_alvo)
    
    url = "https://api.portaldatransparencia.gov.br/api-de-dados/ceis"
    headers = {"chave-api-dados": API_KEY_GOVERNO}
    
    # Tenta enviar só números
    params = {"cnpjSancionado": cnpj_alvo_limpo, "pagina": 1}
    
    lista_filtrada = []
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=15)
        if response.status_code == 200:
            dados_brutos = response.json()
            
            # --- O GRANDE FILTRO (SEGURANÇA LOCAL) ---
            # O Python vai olhar um por um e ver se é o SEU Cnpj.
            for item in dados_brutos:
                try:
                    # Tenta pegar o CNPJ que veio da API
                    cnpj_da_api = item.get('pessoa', {}).get('cnpjFormatado', '')
                    # Limpa ele também
                    cnpj_da_api_limpo = re.sub(r'\D', '', cnpj_da_api)
                    
                    # SÓ GUARDA SE FOR IGUALZINHO
                    if cnpj_da_api_limpo == cnpj_alvo_limpo:
                        lista_filtrada.append(item)
                except:
                    continue
                    
        return lista_filtrada # Retorna apenas os REAIS, ou lista vazia
    except:
        return []

def gerar_pdf(cnpj, dados):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = [Paragraph(f"RELATÓRIO: {cnpj}", getSampleStyleSheet()['Title'])]
    # (Resumi a função PDF pra caber aqui, mas funciona igual)
    data = [["Sanção", "Órgão"]]
    for d in dados:
        data.append([d.get('tipoSancao',{}).get('descricaoResumida','Unknown')[:40], d.get('orgaoSancionador',{}).get('nome','Unknown')[:30]])
    t = Table(data)
    t.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 1, colors.black)]))
    elements.append(t)
    doc.build(elements)
    buffer.seek(0)
    return buffer

# --- FRONTEND ---
st.sidebar.title("👮‍♂️ Menu Auditoria")
if st.sidebar.button("🗑️ Limpar / Resetar"):
    st.session_state.clear()
    st.rerun()

opcao = st.sidebar.radio("Opção:", ["🔍 Analisar Contratos", "🚫 Consultar CNPJ (Blindado)"])

st.title("🏛️ Sistema de Compliance")

if opcao == "🔍 Analisar Contratos":
    if st.button("Buscar Contratos MEC"):
        contratos = buscar_contratos()
        if contratos:
            st.success(f"{len(contratos)} achados.")
            for c in contratos[:2]:
                with st.expander(f"Contrato R$ {c.get('valorInicialCompra')}"):
                    st.write(c.get('objeto'))
                    st.info(analisar_ia(c.get('objeto')))

elif opcao == "🚫 Consultar CNPJ (Blindado)":
    st.header("Investigação de CNPJ")
    st.markdown("**Modo de Segurança:** Filtra falsos positivos da API.")
    
    with st.form("busca"):
        cnpj_in = st.text_input("CNPJ:")
        btn = st.form_submit_button("Investigar")
    
    if btn:
        if len(re.sub(r'\D','',cnpj_in)) != 14:
            st.error("CNPJ deve ter 14 dígitos.")
        else:
            with st.spinner("Conferindo bases oficiais..."):
                # Busca e aplica o FILTRO MANUAL
                resultado_real = consultar_ficha_suja_blindada(cnpj_in)
                st.session_state['dados_busca'] = resultado_real
                st.session_state['cnpj_atual'] = cnpj_in

    if st.session_state['dados_busca'] is not None:
        # Verifica se o input na tela bate com o da memória
        input_limpo = re.sub(r'\D','', cnpj_in)
        memoria_limpo = re.sub(r'\D','', st.session_state['cnpj_atual'])

        if input_limpo == memoria_limpo:
            sancoes = st.session_state['dados_busca']
            
            if len(sancoes) == 0:
                st.divider()
                st.success(f"✅ CONFIRMADO: NADA CONSTA PARA O CNPJ {st.session_state['cnpj_atual']}")
                st.markdown("O sistema verificou e **não encontrou** correspondência exata.")
                st.balloons()
            else:
                st.error(f"🚨 {len(sancoes)} SANÇÕES REAIS ENCONTRADAS!")
                st.download_button("Baixar PDF", data=gerar_pdf(cnpj_in, sancoes), file_name="relatorio.pdf")
                for s in sancoes:
                    st.write(f"**Motivo:** {s.get('fundamentacao',[{}])[0].get('descricao','-')}")