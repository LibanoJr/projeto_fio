import streamlit as st
import requests
import google.generativeai as genai
import os
from dotenv import load_dotenv

# --- CONFIGURAÇÃO INICIAL ---
st.set_page_config(page_title="Auditoria IA - Gov", page_icon="⚖️", layout="wide")
load_dotenv()

# Configuração das Chaves
API_KEY_GOVERNO = os.getenv("API_KEY_GOVERNO")
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# --- FUNÇÕES DE BACKEND ---

def buscar_contratos():
    """Busca contratos recentes do MEC"""
    url = "https://api.portaldatransparencia.gov.br/api-de-dados/contratos"
    headers = {"chave-api-dados": API_KEY_GOVERNO}
    params = {
        "dataInicioVigencia": "01/01/2024",
        "dataFimVigencia": "31/01/2024",
        "codigoOrgao": "26000",  # MEC
        "pagina": 1
    }
    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            return response.json()
        return []
    except:
        return []

def analisar_ia(texto_contrato):
    """Pede para o Gemini analisar o texto"""
    modelo = genai.GenerativeModel("gemini-pro")
    prompt = f"""
    Você é um auditor federal especializado em combate à corrupção.
    Analise o seguinte resumo de contrato público e aponte:
    1. O objeto do contrato é claro ou vago?
    2. Há riscos aparentes?
    3. Dê um veredito final: 'Parece Normal' ou 'Requer Atenção'.
    
    Texto do Contrato: {texto_contrato}
    """
    try:
        resposta = modelo.generate_content(prompt)
        return resposta.text
    except Exception as e:
        return "Erro na análise de IA."

def consultar_ficha_suja(cnpj_consulta):
    """Verifica se o CNPJ está no cadastro de punidos (CEIS)"""
    # Remove formatação caso o usuário digite
    cnpj_limpo = cnpj_consulta.replace(".", "").replace("/", "").replace("-", "")
    
    url = "https://api.portaldatransparencia.gov.br/api-de-dados/ceis"
    headers = {"chave-api-dados": API_KEY_GOVERNO}
    params = {
        "cnpjSancionado": cnpj_limpo,
        "pagina": 1
    }
    
    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            return response.json() 
        return []
    except:
        return []

# --- INTERFACE VISUAL (FRONTEND) ---

# Menu Lateral
st.sidebar.title("👮‍♂️ Menu de Auditoria")
opcao = st.sidebar.radio(
    "Escolha a ferramenta:",
    ["🔍 Analisar Contratos (IA)", "🚫 Consultar Ficha Suja (CNPJ)"]
)

st.title("🏛️ Sistema de Auditoria e Compliance Governamental")

# --- TELA 1: AUDITORIA DE CONTRATOS ---
if opcao == "🔍 Analisar Contratos (IA)":
    st.header("Análise Inteligente de Contratos do MEC")
    
    if st.button("Buscar e Analisar Contratos Recentes"):
        with st.spinner("Conectando ao Portal da Transparência..."):
            dados = buscar_contratos()
        
        if len(dados) > 0:
            st.success(f"{len(dados)} contratos encontrados!")
            
            for contrato in dados[:3]:
                with st.expander(f"Contrato: {contrato.get('numero', 'S/N')} - R$ {contrato.get('valorInicialCompra', '0')}"):
                    objeto = contrato.get('objeto', 'Sem descrição')
                    st.write(f"**Objeto:** {objeto}")
                    st.write("---")
                    st.subheader("🤖 Parecer da IA:")
                    with st.spinner("A IA está lendo o contrato..."):
                        analise = analisar_ia(objeto)
                        st.markdown(analise)
        else:
            st.warning("Nenhum contrato encontrado ou erro na API.")

# --- TELA 2: FICHA SUJA (ATUALIZADA) ---
elif opcao == "🚫 Consultar Ficha Suja (CNPJ)":
    st.header("Investigação de Antecedentes (CEIS)")
    st.markdown("Consulte se uma empresa está na **Lista Negra** (CEIS) e proibida de licitar.")
    
    cnpj_input = st.text_input("Digite o CNPJ da empresa (apenas números):", max_chars=14)
    
    if st.button("Investigar Empresa"):
        if len(cnpj_input) < 14:
            st.error("Digite um CNPJ válido com 14 dígitos.")
        else:
            with st.spinner(f"Varrendo bancos de dados do governo para o CNPJ {cnpj_input}..."):
                sancoes = consultar_ficha_suja(cnpj_input)
                
            if len(sancoes) > 0:
                st.error(f"🚨 PERIGO: {len(sancoes)} SANÇÕES ENCONTRADAS!")
                
                # Loop para mostrar cada punição com os dados CERTOS do JSON
                for i, punicao in enumerate(sancoes):
                    # Extração segura dos dados
                    tipo_pena = punicao.get('tipoSancao', {}).get('descricaoResumida', 'Sanção Genérica')
                    orgao = punicao.get('orgaoSancionador', {}).get('nome', 'Órgão Desconhecido')
                    data = punicao.get('dataPublicacaoSancao', 'Data N/A')
                    link = punicao.get('linkPublicacao', None)
                    
                    # Tenta pegar o texto longo da lei (fundamentação)
                    detalhe_juridico = "Sem detalhes."
                    if 'fundamentacao' in punicao and len(punicao['fundamentacao']) > 0:
                        detalhe_juridico = punicao['fundamentacao'][0].get('descricao', '')

                    # --- EXIBIÇÃO DO CARTÃO DE ALERTA ---
                    with st.container():
                        st.markdown(f"### ⚠️ Processo #{i+1}: {tipo_pena}")
                        st.write(f"**Órgão Sancionador:** {orgao}")
                        st.write(f"**Data da Publicação:** {data}")
                        
                        # Botão Expansível para o "Juridiquês"
                        with st.expander("📜 Ver Fundamentação Legal (Lei/Artigo)"):
                            st.info(detalhe_juridico)
                        
                        # Link externo se existir
                        if link:
                            st.markdown(f"[🔗 **Ver no Diário Oficial da União**]({link})")
                        
                        st.divider() # Linha divisória
            else:
                st.success("✅ NADA CONSTA. Empresa limpa no cadastro CEIS.")