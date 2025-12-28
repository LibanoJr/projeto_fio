import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Auditoria Gov", page_icon="⚖️", layout="wide")

PORTAL_KEY = "d03ede6b6072b78e6df678b6800d4ba1"

ORGAOS_SIAFI = {
    "Ministério da Saúde (MS)": "36000",
    "Ministério da Educação (MEC)": "26000",
    "Ministério da Justiça (MJ)": "30000",
    "Presidência da República": "20000",
    "Ministério da Economia": "17000"
}

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

def safe_float(valor):
    try: return float(valor)
    except: return 0.0

@st.cache_data(ttl=3600)
def consultar_dados_cadastrais(cnpj):
    try:
        r = requests.get(f"https://minhareceita.org/{limpar_cnpj(cnpj)}", timeout=5)
        if r.status_code == 200: return r.json()
    except: pass
    return None

def auditar_empresa_blindada(cnpj_alvo):
    resultados_validos = []
    cnpj_limpo_alvo = limpar_cnpj(cnpj_alvo)
    
    # Bases de dados para varrer
    bases = ["ceis", "cnep"]
    
    for base in bases:
        url = f"https://api.portaldatransparencia.gov.br/api-de-dados/{base}"
        # Buscamos por CNPJ
        params = {"cnpjSancionado": cnpj_limpo_alvo, "pagina": 1}
        
        try:
            resp = requests.get(url, params=params, headers=get_headers(), timeout=15)
            if resp.status_code == 200:
                items = resp.json()
                
                # --- O GRANDE FILTRO (PENTE-FINO) ---
                # A API as vezes devolve lixo. Vamos conferir item por item.
                for item in items:
                    # Tenta achar o CNPJ dentro do registro complexo que o governo manda
                    cnpj_encontrado = ""
                    
                    # Caminho 1: Sancionado -> Codigo
                    try: cnpj_encontrado = item['sancionado']['codigoFormatado']
                    except: pass
                    
                    # Caminho 2: Pessoa -> CNPJ
                    if not cnpj_encontrado:
                        try: cnpj_encontrado = item['pessoa']['cnpjFormatado']
                        except: pass
                        
                    # Limpa o que achou para comparar
                    cnpj_encontrado_limpo = limpar_cnpj(cnpj_encontrado)
                    
                    # SÓ PASSA SE FOR EXATAMENTE O CNPJ DO USUÁRIO
                    # (Ou se contiver a raiz, para pegar filiais)
                    if cnpj_limpo_alvo in cnpj_encontrado_limpo:
                        item['_origem'] = base.upper()
                        resultados_validos.append(item)
                        
        except Exception as e:
            print(f"Erro silencioso na base {base}: {e}")
            pass
            
    return resultados_validos

# --- INTERFACE ---
st.title("⚖️ Auditoria Gov Federal (V30 - Blindada)")

aba1, aba2 = st.tabs(["🕵️ Auditoria CNPJ", "📊 Contratos e Testes"])

# --- ABA 1: AUDITORIA ---
with aba1:
    st.header("Verificar Fornecedor")
    st.info("ℹ️ Agora com Filtragem Dupla: Só mostra registros onde o CNPJ bate exatamente.")
    
    cnpj_input = st.text_input("CNPJ:", value="62.547.210/0001-51")
    
    if st.button("Varrer Bases do Governo", type="primary"):
        with st.spinner("Confrontando dados nas bases federais..."):
            # 1. Identificação Visual
            cad = consultar_dados_cadastrais(cnpj_input)
            nome_empresa = cad.get('razao_social') if cad else "Empresa não identificada na RFB"
            st.success(f"Alvo: **{nome_empresa}**")
            
            # 2. Busca e Filtragem
            sancoes = auditar_empresa_blindada(cnpj_input)
            
            st.divider()
            
            if len(sancoes) > 0:
                st.error(f"🚨 **ALERTA: {len(sancoes)} RESTRIÇÕES CONFIRMADAS**")
                for s in sancoes:
                    st.markdown(f"""
                    ---
                    **Base:** {s['_origem']}
                    **Órgão Sancionador:** {s.get('orgaoSancionador', {}).get('nome')}
                    **Motivo:** {s.get('motivo', 'Não informado')}
                    """)
            else:
                st.success(f"✅ **NADA CONSTA** (Protocolo Blindado)")
                st.caption("A API retornou dados, mas nosso sistema verificou que não pertencem a este CNPJ.")

# --- ABA 2: CONTRATOS E TESTES ---
with aba2:
    st.header("Monitoramento de Contratos")
    
    c1, c2 = st.columns(2)
    with c1: orgao_selecionado = st.selectbox("Órgão", list(ORGAOS_SIAFI.keys()))
    
    # Botão de Teste Corrigido
    if st.button("🛠️ Testar Conexão (Correção V30)"):
        # Agora enviamos o codigoOrgao OBRIGATÓRIO (36000 - Saúde)
        url = "https://api.portaldatransparencia.gov.br/api-de-dados/contratos"
        params = {
            "dataInicial": "01/01/2024",
            "dataFinal": "31/01/2024",
            "codigoOrgao": "36000", 
            "pagina": 1
        }
        
        try:
            resp = requests.get(url, params=params, headers=get_headers(), timeout=20)
            if resp.status_code == 200:
                st.success("✅ **CONEXÃO BEM SUCEDIDA!**")
                st.json(resp.json()[0]) # Mostra só o primeiro pra não poluir
            else:
                st.error(f"Erro: {resp.status_code}")
                st.write(resp.text)
        except Exception as e:
            st.error(f"Erro de Execução: {e}")

    st.divider()
    
    # Busca Real
    dt_hoje = datetime.now()
    dt_inicio = dt_hoje - timedelta(days=60)
    
    col_a, col_b = st.columns(2)
    d_ini = col_a.date_input("Início", dt_inicio)
    d_fim = col_b.date_input("Fim", dt_hoje)
    
    if st.button("Buscar Contratos do Órgão"):
        cod = ORGAOS_SIAFI[orgao_selecionado]
        p = {
            "dataInicial": d_ini.strftime("%d/%m/%Y"),
            "dataFinal": d_fim.strftime("%d/%m/%Y"),
            "codigoOrgao": cod,
            "pagina": 1
        }
        
        try:
            r = requests.get("https://api.portaldatransparencia.gov.br/api-de-dados/contratos", 
                           params=p, headers=get_headers(), timeout=30)
            data = r.json()
            
            if data:
                df = pd.DataFrame([{
                    "Data": d['dataAssinatura'],
                    "Fornecedor": d['fornecedor']['nome'],
                    "Valor": safe_float(d['valorInicial'])
                } for d in data])
                st.dataframe(df)
            else:
                st.warning("Nenhum contrato neste período.")
        except Exception as e:
            st.error(f"Erro: {e}")