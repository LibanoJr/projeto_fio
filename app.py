import streamlit as st
import requests
import google.generativeai as genai
import os
from dotenv import load_dotenv

# 1. Configuração Inicial
load_dotenv()
st.set_page_config(page_title="Projeto FIO", page_icon="🏛️")

# Pega chaves (segurança em primeiro lugar!)
API_KEY_GOVERNO = os.getenv("API_KEY_GOVERNO")
API_KEY_GEMINI  = os.getenv("API_KEY_GEMINI")

# Configura IA
if API_KEY_GEMINI:
    genai.configure(api_key=API_KEY_GEMINI)
    model = genai.GenerativeModel('gemini-flash-latest')

# --- FUNÇÕES (A mesma lógica de antes) ---
def buscar_contratos_mec():
    url = "https://api.portaldatransparencia.gov.br/api-de-dados/contratos"
    headers = {"chave-api-dados": API_KEY_GOVERNO}
    params = {
        "dataInicioVigencia": "01/01/2024",
        "dataFimVigencia": "15/01/2024",
        "codigoOrgao": "26000", 
        "pagina": 1
    }
    try:
        response = requests.get(url, headers=headers, params=params, timeout=20)
        if response.status_code == 200:
            dados = response.json()
            return [d for d in dados if d.get('objeto')]
        return []
    except:
        return []

def analisar_juridico(contrato):
    prompt = f"""
    Analise este contrato público (MEC).
    VALOR: R$ {contrato.get('valorInicial', 0)}
    OBJETO: "{contrato.get('objeto')}"
    
    Responda em Markdown curto:
    **Resumo:** ...
    **Risco:** (Baixo/Médio/Alto) e o motivo.
    """
    try:
        res = model.generate_content(prompt)
        return res.text
    except:
        return "Erro na IA"

# --- A PARTE NOVA (INTERFACE VISUAL) ---
st.title("🏛️ Auditoria Governamental - Projeto FIO")
st.markdown("Sistema de fiscalização automática de contratos públicos usando IA.")

# Botão na tela
if st.button("🔎 Iniciar Auditoria no MEC"):
    
    with st.spinner("Conectando ao Portal da Transparência..."):
        contratos = buscar_contratos_mec()
    
    if contratos:
        st.success(f"Encontrados {len(contratos)} contratos! Analisando os 3 maiores...")
        
        # Ordena e pega os 3 maiores
        contratos.sort(key=lambda x: x.get('valorInicial', 0), reverse=True)
        
        for item in contratos[:3]:
            # Cria uma "Caixa" bonita para cada contrato
            with st.expander(f"📄 Contrato {item.get('numero')} - R$ {item.get('valorInicial', 0):,.2f}"):
                st.write(f"**Objeto Original:** {item.get('objeto')}")
                
                st.markdown("---")
                st.subheader("🤖 Parecer da IA")
                
                # Chama a IA e mostra o resultado enquanto escreve
                parecer = analisar_juridico(item)
                st.markdown(parecer)
    else:
        st.error("Nenhum contrato encontrado ou erro de API.")