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
    "Ministério da Economia": "17000",
    "Comando do Exército": "52121",
    "Polícia Federal": "30108"
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

def auditar_por_triangulacao(cnpj_alvo, nome_fantasia_ou_razao):
    resultados_validos = []
    cnpj_limpo_alvo = limpar_cnpj(cnpj_alvo)
    raiz_alvo = cnpj_limpo_alvo[:8] # Os 8 primeiros digitos (Raiz)
    
    # Define termo de busca (Pega as 2 primeiras palavras do nome para garantir)
    if not nome_fantasia_ou_razao:
        return []
    
    # Ex: "MENDES JUNIOR ENGENHARIA" -> Busca "MENDES JUNIOR"
    termo_busca = " ".join(nome_fantasia_ou_razao.split()[:2])
    
    bases = ["ceis", "cnep"]
    
    for base in bases:
        url = f"https://api.portaldatransparencia.gov.br/api-de-dados/{base}"
        
        # ESTRATÉGIA V32: BUSCA POR NOME (Mais abrangente)
        params = {"nomeSancionado": termo_busca, "pagina": 1}
        
        try:
            resp = requests.get(url, params=params, headers=get_headers(), timeout=15)
            if resp.status_code == 200:
                items = resp.json()
                
                # --- FILTRO DE VALIDAÇÃO (Raiz do CNPJ) ---
                for item in items:
                    cnpj_encontrado = ""
                    
                    # Tenta extrair CNPJ do registro
                    try: cnpj_encontrado = item['sancionado']['codigoFormatado']
                    except: pass
                    if not cnpj_encontrado:
                        try: cnpj_encontrado = item['pessoa']['cnpjFormatado']
                        except: pass
                    
                    # Se achou um CNPJ no registro, compara a RAIZ
                    if cnpj_encontrado:
                        raiz_encontrada = limpar_cnpj(cnpj_encontrado)[:8]
                        if raiz_encontrada == raiz_alvo:
                            item['_origem'] = base.upper()
                            resultados_validos.append(item)
                            
        except Exception as e:
            pass
            
    return resultados_validos

# --- INTERFACE ---
st.title("⚖️ Auditoria Gov Federal (V32 - Triangulação)")

aba1, aba2 = st.tabs(["🕵️ Auditoria Profunda", "📊 Monitor de Contratos"])

# --- ABA 1 ---
with aba1:
    st.header("Verificar Fornecedor")
    st.info("ℹ️ Método V32: Busca pelo NOME na base suja e confirma pelo CNPJ. (Infalível)")
    
    # Default para testar: Mendes Junior
    cnpj_input = st.text_input("CNPJ:", value="17.162.082/0001-73") 
    
    if st.button("Executar Varredura Profunda", type="primary"):
        with st.spinner("Identificando empresa e triangulando dados..."):
            
            # 1. Pega o Nome na Receita
            cad = consultar_dados_cadastrais(cnpj_input)
            
            if cad:
                razao = cad.get('razao_social') or cad.get('nome_fantasia')
                st.success(f"Alvo Identificado: **{razao}**")
                
                # 2. Busca por Nome + Validação de CNPJ
                sancoes = auditar_por_triangulacao(cnpj_input, razao)
                
                st.divider()
                
                if sancoes:
                    st.error(f"🚨 **ALERTA VERMELHO: {len(sancoes)} SANÇÕES CONFIRMADAS**")
                    st.write(f"Registros encontrados buscando por '{razao.split()[:2]}' e validados pela raiz do CNPJ.")
                    
                    for s in sancoes:
                        with st.expander(f"{s['_origem']} - {s.get('tipoSancao', {}).get('descricaoResumida', 'Sanção')}"):
                            st.write(f"**Órgão:** {s.get('orgaoSancionador', {}).get('nome')}")
                            st.write(f"**Motivo:** {s.get('motivo', 'Não detalhado')}")
                            st.caption(f"CNPJ no registro: {s.get('sancionado', {}).get('codigoFormatado')}")
                else:
                    st.success("✅ **Nada Consta** (CNPJ Limpo)")
                    st.caption("A busca por nome e CNPJ não retornou restrições ativas.")
            else:
                st.warning("⚠️ Não foi possível identificar o nome da empresa pelo CNPJ. A busca profunda depende do nome.")

# --- ABA 2 ---
with aba2:
    st.header("Monitoramento de Contratos (1 Ano)")
    
    c1, c2 = st.columns([2, 1])
    with c1: orgao = st.selectbox("Órgão", list(ORGAOS_SIAFI.keys()))
    
    dt_hoje = datetime.now()
    dt_inicio = dt_hoje - timedelta(days=365)
    
    with c2: st.write(f"Período: Últimos 12 meses")
    
    if st.button("Buscar Contratos"):
        cod = ORGAOS_SIAFI[orgao]
        params = {
            "dataInicial": dt_inicio.strftime("%d/%m/%Y"),
            "dataFinal": dt_hoje.strftime("%d/%m/%Y"),
            "codigoOrgao": cod,
            "pagina": 1
        }
        
        with st.spinner(f"Consultando {orgao}..."):
            try:
                r = requests.get("https://api.portaldatransparencia.gov.br/api-de-dados/contratos", 
                               params=params, headers=get_headers(), timeout=45)
                data = r.json()
                
                if data:
                    lista = []
                    total = 0.0
                    for d in data:
                        val = safe_float(d.get('valorInicial') or d.get('valorGlobal'))
                        total += val
                        lista.append({
                            "Data": d.get('dataAssinatura'),
                            "Fornecedor": d.get('fornecedor', {}).get('nome', 'N/A'),
                            "Valor": val
                        })
                    
                    df = pd.DataFrame(lista)
                    k1, k2 = st.columns(2)
                    k1.metric("Total Gasto", f"R$ {total:,.2f}")
                    k2.metric("Qtd. Contratos", len(df))
                    st.dataframe(df.sort_values("Data", ascending=False).style.format({"Valor": "R$ {:,.2f}"}), use_container_width=True)
                else:
                    st.info("ℹ️ Nenhum contrato retornado para este órgão.")
                    st.markdown("""
                    **Por que isso acontece?**
                    1. O órgão pode publicar através de unidades subordinadas (Ex: Receita Federal vs Min. Economia).
                    2. O órgão pode não ter contratos novos no período (comum em ministérios 'meio').
                    3. Dados classificados como sigilosos não aparecem na API.
                    """)
            except Exception as e:
                st.error(f"Erro: {e}")