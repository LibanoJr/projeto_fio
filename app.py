import streamlit as st
import requests
import os
import re # Biblioteca de Expressões Regulares (O "Faxineiro")
from dotenv import load_dotenv

st.set_page_config(page_title="Debug API Governo - V2", layout="centered")
load_dotenv()

API_KEY = os.getenv("API_KEY_GOVERNO")

st.title("🛠️ Teste de Conexão: O Limpador de CNPJ")
st.write("Agora o sistema remove pontos e traços antes de enviar.")

# Input
cnpj_digitado = st.text_input("Cole o CNPJ (pode ser com ponto e traço):")

if st.button("Consultar API Agora"):
    # --- A MÁGICA ACONTECE AQUI ---
    # O comando abaixo remove TUDO que não for número (0-9)
    cnpj_limpo = re.sub(r'\D', '', cnpj_digitado)
    
    st.write(f"🔢 **CNPJ que será enviado:** `{cnpj_limpo}`")
    
    if len(cnpj_limpo) != 14:
        st.warning(f"⚠️ Atenção: O CNPJ deve ter 14 dígitos. Você digitou {len(cnpj_limpo)}.")
    else:
        url = "https://api.portaldatransparencia.gov.br/api-de-dados/ceis"
        params = {"cnpjSancionado": cnpj_limpo, "pagina": 1}
        headers = {"chave-api-dados": API_KEY}

        try:
            response = requests.get(url, headers=headers, params=params)
            
            if response.status_code == 200:
                dados = response.json()
                
                # VERIFICAÇÃO FINAL
                st.write("---")
                if len(dados) == 0:
                    st.success(f"✅ SUCESSO! Lista Vazia para o CNPJ {cnpj_limpo}.")
                    st.write("A API entendeu o filtro e confirmou: Nenhuma sanção.")
                else:
                    # Se vier dados, vamos conferir se é a empresa certa
                    primeiro_resultado = dados[0]
                    nome_empresa = primeiro_resultado.get('pessoa', {}).get('nome', 'Desconhecido')
                    cnpj_retornado = primeiro_resultado.get('pessoa', {}).get('cnpjFormatado', '???')
                    
                    st.error(f"🚨 Encontrado! Empresa: {nome_empresa}")
                    st.write(f"CNPJ do Processo: {cnpj_retornado}")
                    
                    # Se o CNPJ da resposta for diferente do buscado, a API ignorou o filtro
                    cnpj_retornado_limpo = re.sub(r'\D', '', cnpj_retornado)
                    if cnpj_retornado_limpo != cnpj_limpo:
                        st.warning("⚠️ ALERTA: A API ignorou seu filtro e mandou dados de OUTRA empresa. O sistema do governo pode estar instável.")
                    else:
                        st.json(dados)
            else:
                st.error(f"Erro na API: {response.status_code}")
                
        except Exception as e:
            st.error(f"Erro técnico: {e}")