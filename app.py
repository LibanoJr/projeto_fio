import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Auditoria Final", page_icon="🚨", layout="wide")
PORTAL_KEY = "d03ede6b6072b78e6df678b6800d4ba1"

# --- FUNÇÕES ---
def get_headers():
    return {
        "chave-api-dados": PORTAL_KEY,
        "Accept": "application/json"
    }

def limpar_cnpj(cnpj):
    return "".join([n for n in str(cnpj) if n.isdigit()])

# --- AUDITORIA MODO BRUTO (SEM FILTROS) ---
def auditar_sem_barreiras(cnpj):
    resultados = []
    cnpj_limpo = limpar_cnpj(cnpj)
    
    # Bases Críticas
    bases = {
        "acordos-leniencia": "ACORDO LENIÊNCIA",
        "ceis": "INIDÔNEOS (CEIS)",
        "cnep": "PUNIDOS (CNEP)"
    }
    
    for endpoint, nome_base in bases.items():
        try:
            url = f"https://api.portaldatransparencia.gov.br/api-de-dados/{endpoint}"
            # Solicita à API. Se ela devolver, nós mostramos.
            params = {"cnpjSancionado": cnpj_limpo, "pagina": 1}
            
            resp = requests.get(url, params=params, headers=get_headers(), timeout=10)
            
            if resp.status_code == 200:
                dados = resp.json()
                # Se vier lista vazia [], ignora
                if dados and isinstance(dados, list):
                    for item in dados:
                        item['_base_origem'] = nome_base
                        resultados.append(item)
        except:
            pass
            
    return resultados

# --- INTERFACE ---
st.title("🚨 Auditoria V36 (Modo Bruto)")

aba1, aba2 = st.tabs(["🔥 Auditoria CNPJ", "💰 Debug Contratos"])

# --- ABA 1 ---
with aba1:
    st.write("Dica: Teste **05.144.757/0001-72** (Odebrecht). Se aparecer algo, o sistema funciona.")
    cnpj_input = st.text_input("CNPJ Alvo:", value="05.144.757/0001-72")
    
    if st.button("RASTREAR (SEM FILTROS)"):
        # 1. Tenta pegar o nome (Opcional, se falhar não trava)
        try:
            r = requests.get(f"https://minhareceita.org/{limpar_cnpj(cnpj_input)}", timeout=2)
            if r.status_code == 200:
                st.info(f"Receita Federal: **{r.json().get('razao_social')}**")
        except:
            st.warning("MinhaReceita instável (Nome ignorado)")

        # 2. Busca Bruta
        sancoes = auditar_sem_barreiras(cnpj_input)
        
        st.divider()
        if sancoes:
            st.error(f"⚠️ **A API RETORNOU {len(sancoes)} REGISTROS**")
            st.write("Confira abaixo se pertencem à empresa (Nomes e Datas):")
            
            for s in sancoes:
                with st.expander(f"{s['_base_origem']} (Clique para ver detalhes)"):
                    # Tenta mostrar o máximo de campos possíveis sem quebrar
                    st.json(s) 
        else:
            st.success("✅ O Governo retornou lista vazia (Nada Consta Absoluto)")

# --- ABA 2 ---
with aba2:
    st.header("Descobrir Campos de Valor")
    st.info("Vamos ver o JSON cru para descobrir qual o nome do campo 'Valor'.")
    
    # Ministério da Saúde (Sempre tem dados)
    if st.button("🔍 BAIXAR JSON PURO (Saúde)"):
        url = "https://api.portaldatransparencia.gov.br/api-de-dados/contratos"
        params = {
            "dataInicial": "01/06/2024", # Periodo curto pra ser rapido
            "dataFinal": "30/06/2024",
            "codigoOrgao": "36000", # Saúde
            "pagina": 1
        }
        
        try:
            r = requests.get(url, params=params, headers=get_headers())
            data = r.json()
            
            if data and len(data) > 0:
                primeiro_item = data[0]
                st.success("✅ Dados recebidos! Veja abaixo as chaves disponíveis:")
                
                # MOSTRA AS CHAVES NA TELA
                keys = list(primeiro_item.keys())
                st.write(f"**Campos disponíveis:** {keys}")
                
                # MOSTRA O JSON INTEIRO
                st.text("JSON do Primeiro Contrato:")
                st.json(primeiro_item)
                
                # TENTA TABELA SIMPLES
                df = pd.DataFrame(data)
                st.dataframe(df)
            else:
                st.warning("Lista vazia retornada pela API.")
                
        except Exception as e:
            st.error(f"Erro: {e}")