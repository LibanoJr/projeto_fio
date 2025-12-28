import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Auditoria Gov", page_icon="⚖️", layout="wide")

# Chave da API (Hardcoded para garantir)
PORTAL_KEY = "d03ede6b6072b78e6df678b6800d4ba1"

# --- FUNÇÕES ---
def get_headers():
    return {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        "chave-api-dados": PORTAL_KEY,
        "Accept": "application/json"
    }

def limpar_cnpj(cnpj):
    if not cnpj: return ""
    return "".join([n for n in str(cnpj) if n.isdigit()])

def auditar_empresa_debug(cnpj_alvo, debug_mode=False):
    resultados = []
    cnpj_limpo = limpar_cnpj(cnpj_alvo)
    
    bases = ["ceis", "cnep"]
    
    for base in bases:
        url = f"https://api.portaldatransparencia.gov.br/api-de-dados/{base}"
        # V29: Usando cnpjSancionado que é mais garantido que codigoSancionado
        params = {"cnpjSancionado": cnpj_limpo, "pagina": 1}
        
        try:
            if debug_mode:
                st.write(f"🔄 **Tentando conectar em:** `{base.upper()}`...")
            
            resp = requests.get(url, params=params, headers=get_headers(), timeout=20)
            
            if debug_mode:
                st.write(f"📡 Status Code: `{resp.status_code}`")
            
            if resp.status_code == 200:
                dados = resp.json()
                if debug_mode:
                    with st.expander(f"📦 Ver JSON Bruto ({base.upper()})"):
                        st.json(dados)
                
                # Se voltou lista vazia, o governo diz que não tem nada
                if isinstance(dados, list):
                    for item in dados:
                        item['_origem'] = base.upper()
                        resultados.append(item)
            elif resp.status_code == 401:
                st.error("🔒 Erro 401: A API negou a chave. A chave pode estar expirada ou bloqueada.")
        except Exception as e:
            st.error(f"Erro de conexão na base {base}: {e}")

    return resultados

# --- INTERFACE ---
st.title("⚖️ Auditoria Gov Federal (V29 - Debug Mode)")

aba1, aba2 = st.tabs(["🕵️ Auditoria CNPJ", "📊 Contratos"])

# --- ABA 1 ---
with aba1:
    st.header("Verificar Fornecedor")
    
    # CHECKBOX DE DEBUG PARA VOCÊ VER A VERDADE
    debug_mode = st.checkbox("🐞 Ativar Modo Detetive (Mostrar JSON Bruto)")
    
    cnpj_input = st.text_input("CNPJ:", value="17.162.082/0001-73")
    
    if st.button("Varrer Bases do Governo"):
        if len(cnpj_input) < 10:
            st.warning("CNPJ Inválido")
        else:
            # 1. Dados Básicos (MinhaReceita)
            try:
                r_cad = requests.get(f"https://minhareceita.org/{limpar_cnpj(cnpj_input)}", timeout=5)
                if r_cad.status_code == 200:
                    cad = r_cad.json()
                    st.success(f"Empresa Identificada: **{cad.get('razao_social')}**")
            except:
                st.warning("MinhaReceita fora do ar (Dados cadastrais pulados)")

            # 2. Busca Sanções
            sancoes = auditar_empresa_debug(cnpj_input, debug_mode)
            
            st.divider()
            if sancoes:
                st.error(f"🚨 **ENCONTRADO(S) {len(sancoes)} REGISTRO(S)**")
                for s in sancoes:
                    st.markdown(f"""
                    ---
                    **Origem:** {s['_origem']}
                    **Órgão:** {s.get('orgaoSancionador', {}).get('nome')}
                    **Motivo:** {s.get('motivo')}
                    """)
            else:
                st.success("✅ O Governo retornou lista vazia (Nada Consta).")
                if debug_mode:
                    st.info("Se você ativou o Modo Detetive e o JSON apareceu como `[]`, é certeza absoluta que o governo não tem dados para este CNPJ.")

# --- ABA 2 ---
with aba2:
    st.header("Teste de Conexão - Contratos")
    st.info("Vamos testar se a API de Contratos aceita nossa chave.")
    
    if st.button("Testar Conexão Contratos"):
        # Tenta pegar apenas 1 contrato aleatório de 2024 para ver se conecta
        url = "https://api.portaldatransparencia.gov.br/api-de-dados/contratos"
        params = {
            "dataInicial": "01/01/2024",
            "dataFinal": "10/01/2024",
            "pagina": 1
        }
        
        try:
            resp = requests.get(url, params=params, headers=get_headers(), timeout=20)
            
            st.write(f"**Status da Resposta:** {resp.status_code}")
            
            if resp.status_code == 200:
                dados = resp.json()
                st.success(f"✅ Conexão BEM SUCEDIDA! A API retornou {len(dados)} contratos de teste.")
                st.dataframe(dados)
            elif resp.status_code == 401:
                st.error("⛔ ERRO 401: Chave de API Inválida/Bloqueada.")
                st.write("Isso significa que o problema é na CHAVE, não no código.")
            elif resp.status_code == 403:
                st.error("⛔ ERRO 403: Acesso Proibido (IP bloqueado ou WAF).")
            else:
                st.error(f"Erro desconhecido: {resp.text}")
                
        except Exception as e:
            st.error(f"Erro crítico de Python: {e}")