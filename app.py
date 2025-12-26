import streamlit as st
import requests
import os
from dotenv import load_dotenv

# Configuração Básica
st.set_page_config(page_title="Debug API Governo", layout="centered")
load_dotenv()

# Pegando a Chave
API_KEY = os.getenv("API_KEY_GOVERNO")

st.title("🛠️ Modo de Diagnóstico: Conexão Real")
st.write("Este código consulta a API diretamente, sem cache e sem memória.")

# Input simples
cnpj_digitado = st.text_input("Digite o CNPJ para auditar (apenas números):")

if st.button("Consultar API Agora"):
    if not API_KEY:
        st.error("ERRO CRÍTICO: Chave da API não encontrada!")
    elif len(cnpj_digitado) < 14:
        st.warning("CNPJ muito curto.")
    else:
        # Limpeza do CNPJ
        cnpj_limpo = cnpj_digitado.replace(".", "").replace("/", "").replace("-", "")
        
        # URL Oficial do Governo (CEIS - Cadastro de Inidôneos)
        url = "https://api.portaldatransparencia.gov.br/api-de-dados/ceis"
        
        # Parâmetros exatos
        params = {"cnpjSancionado": cnpj_limpo, "pagina": 1}
        headers = {"chave-api-dados": API_KEY}

        st.info(f"📡 Enviando sinal para o Governo... (CNPJ: {cnpj_limpo})")
        
        try:
            # Faz a requisição REAL
            response = requests.get(url, headers=headers, params=params, timeout=10)
            
            # MOSTRA O RESULTADO TÉCNICO NA TELA
            st.write("---")
            st.write(f"**Status da Conexão:** {response.status_code}")
            
            if response.status_code == 200:
                dados = response.json()
                st.write(f"**Quantidade de Registros Encontrados:** {len(dados)}")
                
                if len(dados) == 0:
                    st.success("✅ RESPOSTA DA API: Lista Vazia (Nenhuma sanção encontrada).")
                    st.write("Se você está vendo isso, sua empresa está LIMPA de verdade.")
                else:
                    st.error(f"🚨 RESPOSTA DA API: Encontrou {len(dados)} sanções reais.")
                    st.json(dados) # Mostra o JSON cru para provar que não é inventado
            else:
                st.error("Erro na comunicação com o Governo.")
                st.write(response.text)
                
        except Exception as e:
            st.error(f"Erro de conexão: {e}")