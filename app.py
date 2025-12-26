import streamlit as st
import requests
import re

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Auditoria Gov - Direct", page_icon="⚡", layout="centered")

# A CHAVE QUE FUNCIONA (Do seu script)
API_KEY = "d03ede6b6072b78e6df678b6800d4ba1"

# --- FUNÇÃO EXATA DO SEU SCRIPT ---
def consultar_base_gov(cnpj, base):
    """
    Réplica exata da lógica do script 'consultar_ceis' enviado pelo usuário.
    """
    # Limpa o CNPJ (Apenas números, igual ao seu script)
    cnpj_limpo = "".join([n for n in cnpj if n.isdigit()])
    
    url = f"https://api.portaldatransparencia.gov.br/api-de-dados/{base}"
    params = {"cnpjSancionado": cnpj_limpo, "pagina": 1}
    headers = {"chave-api-dados": API_KEY}
    
    try:
        # Request padrão, sem headers de navegador, sem verify=False
        response = requests.get(url, params=params, headers=headers, timeout=10)
        
        if response.status_code == 200:
            return response.json() # Retorna a lista crua
        else:
            return f"Erro API: {response.status_code}"
            
    except Exception as e:
        return f"Erro Conexão: {str(e)}"

# --- INTERFACE ---
st.title("⚡ Auditoria Gov (Engine V9)")
st.markdown("Replicando exatamente a lógica do script Python funcional via `requests`.")

cnpj_input = st.text_input("Cole o CNPJ:", placeholder="Ex: 03.050.725/0001-82")
btn_auditar = st.button("AUDITAR AGORA")

if btn_auditar and cnpj_input:
    st.divider()
    
    # Bases para consultar
    bases = ["ceis", "cnep"]
    encontrou_algo = False
    
    for base in bases:
        st.subheader(f"📡 Consultando {base.upper()}...")
        
        # Chama a função limpa
        resultado = consultar_base_gov(cnpj_input, base)
        
        if isinstance(resultado, list):
            if len(resultado) > 0:
                st.error(f"🚨 REGISTRO ENCONTRADO NO {base.upper()}!")
                st.json(resultado) # Mostra o JSON igualzinho o print do seu script
                encontrou_algo = True
            else:
                st.success(f"✅ {base.upper()}: Nada consta (Lista vazia retornada).")
        else:
            st.warning(f"⚠️ Erro técnico no {base.upper()}: {resultado}")

    st.markdown("---")
    if encontrou_algo:
        st.error("❌ RESULTADO FINAL: EMPRESA COM RESTRIÇÕES.")
    else:
        st.balloons()
        st.success("✅ RESULTADO FINAL: NADA CONSTA EM NENHUMA BASE.")