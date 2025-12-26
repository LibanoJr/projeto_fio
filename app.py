import streamlit as st
import requests

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Auditoria Gov - Pente Fino", page_icon="🕵️", layout="centered")

# SUA CHAVE DE API
API_KEY = "d03ede6b6072b78e6df678b6800d4ba1"

def formatar_cnpj(cnpj):
    """Remove pontuação para envio à API"""
    return "".join([n for n in cnpj if n.isdigit()])

def consultar_base_gov_com_pente_fino(cnpj_alvo, base):
    """
    Consulta a API e faz uma verificação manual (Pente Fino) 
    para garantir que o resultado é EXATAMENTE do CNPJ alvo.
    """
    cnpj_limpo = formatar_cnpj(cnpj_alvo)
    
    url = f"https://api.portaldatransparencia.gov.br/api-de-dados/{base}"
    params = {"cnpjSancionado": cnpj_limpo, "pagina": 1}
    headers = {"chave-api-dados": API_KEY}
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=15)
        
        if response.status_code == 200:
            dados_brutos = response.json()
            
            # --- O PULO DO GATO: PENTE FINO ---
            # A API as vezes retorna listas genéricas. 
            # Vamos filtrar manualmente aqui no Python.
            resultados_exatos = []
            
            for item in dados_brutos:
                # Tenta pegar o CNPJ de dentro do JSON da resposta
                cnpj_encontrado = ""
                try:
                    # O campo pode variar, tentamos pegar o 'codigoFormatado' do sancionado
                    cnpj_encontrado = item.get('sancionado', {}).get('codigoFormatado', '')
                    # Se vier vazio, tenta em 'pessoa'
                    if not cnpj_encontrado:
                        cnpj_encontrado = item.get('pessoa', {}).get('cnpjFormatado', '')
                except:
                    continue

                # Limpa o CNPJ encontrado para comparar
                if cnpj_encontrado:
                    cnpj_encontrado_limpo = formatar_cnpj(cnpj_encontrado)

                    # COMPARAÇÃO EXATA
                    if cnpj_encontrado_limpo == cnpj_limpo:
                        resultados_exatos.append(item)
            
            # CORREÇÃO AQUI: Retornando a variável certa
            return resultados_exatos
            
        else:
            return f"Erro API ({response.status_code})"
            
    except Exception as e:
        return f"Erro Conexão: {str(e)}"

# --- INTERFACE ---
st.title("🕵️ Auditoria Gov (Engine V10.1)")
st.caption("Filtro: CNPJ Exato (Correção de variável aplicada)")

cnpj_input = st.text_input("CNPJ Alvo:", placeholder="Ex: 03.050.725/0001-82")
btn_auditar = st.button("RASTREAR AGORA", type="primary")

if btn_auditar and cnpj_input:
    st.divider()
    
    bases = ["ceis", "cnep"]
    encontrou_sujeira = False
    
    for base in bases:
        st.subheader(f"📡 Verificando {base.upper()}...")
        
        resultado = consultar_base_gov_com_pente_fino(cnpj_input, base)
        
        if isinstance(resultado, list):
            if len(resultado) > 0:
                st.error(f"🚨 ALERTA VERMELHO: {len(resultado)} SANÇÃO(ÕES) CONFIRMADA(S) NO {base.upper()}!")
                # Mostra o JSON bonitinho
                st.json(resultado) 
                encontrou_sujeira = True
            else:
                st.success(f"✅ {base.upper()}: Limpo (Nenhum vínculo exato encontrado).")
        else:
            st.warning(f"⚠️ Falha na consulta do {base.upper()}: {resultado}")

    st.markdown("---")
    if encontrou_sujeira:
        st.error("❌ CONCLUSÃO: A EMPRESA POSSUI RESTRIÇÕES NO GOVERNO FEDERAL.")
    else:
        st.balloons()
        st.success("✅ CONCLUSÃO: NADA CONSTA NAS BASES FEDERAIS (CEIS/CNEP).")