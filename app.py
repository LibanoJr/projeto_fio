import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Auditoria Gov Federal", page_icon="🏛️", layout="wide")
PORTAL_KEY = "d03ede6b6072b78e6df678b6800d4ba1"

# --- LISTA DE ÓRGÃOS (SIAFI - CÓDIGOS PAGADORES REAIS) ---
ORGAOS_SIAFI = {
    "Ministério da Saúde": "36000",
    "Ministério da Educação": "26000",
    "DNIT (Transportes)": "39252",
    "Polícia Federal": "30108",
    "Comando do Exército": "52121",
    "Secretaria-Geral Presidência (Planalto)": "20101", # MUDEI PARA O CÓDIGO QUE TEM CONTRATOS
    "Ministério da Justiça": "30000"
}

# --- FUNÇÕES ---
def get_headers():
    return {
        "chave-api-dados": PORTAL_KEY,
        "Accept": "application/json"
    }

def limpar_string(texto):
    if not texto: return ""
    return "".join([c for c in str(texto) if c.isdigit()])

def safe_float(valor):
    try: return float(valor)
    except: return 0.0

# --- AUDITORIA (MANTIDA IGUAL V39 - PERFEITA) ---
def auditar_cnpj_final(cnpj_alvo):
    resultados_reais = []
    cnpj_limpo_alvo = limpar_string(cnpj_alvo)
    raiz_alvo = cnpj_limpo_alvo[:8]
    
    bases = {
        "acordos-leniencia": "ACORDO DE LENIÊNCIA",
        "ceis": "INIDÔNEO (CEIS)",
        "cnep": "PUNIDO (CNEP)"
    }
    
    for endpoint, nome_base in bases.items():
        try:
            url = f"https://api.portaldatransparencia.gov.br/api-de-dados/{endpoint}"
            params = {"cnpjSancionado": cnpj_limpo_alvo, "pagina": 1}
            resp = requests.get(url, params=params, headers=get_headers(), timeout=10)
            
            if resp.status_code == 200:
                itens = resp.json()
                for item in itens:
                    cnpj_item = ""
                    nome_item = "Nome não informado na API"
                    try: 
                        sancionado = item.get('sancionado', {})
                        cnpj_item = sancionado.get('codigoFormatado') or item.get('pessoa', {}).get('cnpjFormatado')
                        nome_temp = sancionado.get('nome') or item.get('pessoa', {}).get('nome')
                        if nome_temp: nome_item = nome_temp
                    except: pass
                    
                    match = False
                    if cnpj_item:
                        if limpar_string(cnpj_item)[:8] == raiz_alvo: match = True
                    elif nome_base == "ACORDO DE LENIÊNCIA" and not cnpj_item:
                        match = True
                        item['_aviso_oculto'] = True 

                    if match:
                        item['_origem'] = nome_base
                        item['_nome_exibicao'] = nome_item
                        resultados_reais.append(item)
        except Exception: pass
            
    return resultados_reais

# --- CONTRATOS (TURBINADO 2 ANOS) ---
def buscar_contratos(codigo_orgao):
    lista_final = []
    dt_fim = datetime.now()
    dt_ini = dt_fim - timedelta(days=730) # AQUI: AUMENTEI PARA 2 ANOS
    
    # Busca 3 páginas
    for pag in range(1, 4):
        params = {
            "dataInicial": dt_ini.strftime("%d/%m/%Y"),
            "dataFinal": dt_fim.strftime("%d/%m/%Y"),
            "codigoOrgao": codigo_orgao,
            "pagina": pag
        }
        try:
            r = requests.get("https://api.portaldatransparencia.gov.br/api-de-dados/contratos", 
                           params=params, headers=get_headers(), timeout=15)
            if r.status_code == 200:
                dados = r.json()
                if not dados: break
                lista_final.extend(dados)
            else: break
        except: break
    return lista_final

# --- INTERFACE ---
st.title("🏛️ Auditoria Governamental")
st.markdown("---")

aba1, aba2 = st.tabs(["🕵️ Análise de Risco (CNPJ)", "💰 Gastos Públicos"])

# --- ABA 1 ---
with aba1:
    st.header("Compliance & Sanções")
    col1, col2 = st.columns([3, 1])
    cnpj_input = col1.text_input("CNPJ:", value="05.144.757/0001-72")
    
    if col2.button("Verificar", type="primary"):
        with st.spinner("Consultando bases oficiais..."):
            # Receita
            try:
                r = requests.get(f"https://minhareceita.org/{limpar_string(cnpj_input)}", timeout=3)
                if r.status_code == 200:
                    st.info(f"Razão Social: **{r.json().get('razao_social')}**")
            except: pass

            # Auditoria
            sancoes = auditar_cnpj_final(cnpj_input)
            st.divider()
            
            if sancoes:
                st.error(f"🚨 **ALERTA: {len(sancoes)} OCORRÊNCIAS CONFIRMADAS**")
                for s in sancoes:
                    titulo = f"⚠️ {s['_origem']}"
                    if s.get('_aviso_oculto'): titulo += " (Sigilo Parcial)"
                    with st.expander(titulo):
                        st.write(f"**Envolvido:** {s['_nome_exibicao']}")
                        st.write(f"**Motivo:** {s.get('motivo') or s.get('situacaoAcordo')}")
                        st.write(f"**Órgão:** {s.get('orgaoSancionador', {}).get('nome')}")
            else:
                st.success("✅ **NADA CONSTA**")
                st.caption(f"Nenhuma sanção ativa encontrada para a raiz {cnpj_input[:10]}...")

# --- ABA 2 ---
with aba2:
    st.header("Monitoramento de Contratos (Últimos 2 Anos)")
    orgao_nome = st.selectbox("Selecione o Órgão:", list(ORGAOS_SIAFI.keys()))
    
    if st.button("Buscar Contratos"):
        cod = ORGAOS_SIAFI[orgao_nome]
        with st.spinner(f"Baixando contratos da {orgao_nome}..."):
            raw = buscar_contratos(cod)
            
            if raw:
                dados_tab = []
                total = 0.0
                for item in raw:
                    val = safe_float(item.get('valorInicialCompra') or item.get('valorFinalCompra'))
                    total += val
                    dados_tab.append({
                        "Data": item.get('dataAssinatura'),
                        "Fornecedor": item.get('fornecedor', {}).get('nome', 'N/A')[:35],
                        "Objeto": item.get('objeto', 'N/A')[:75] + "...",
                        "Valor": val
                    })
                
                df = pd.DataFrame(dados_tab)
                c1, c2 = st.columns(2)
                c1.metric("Total Encontrado", f"R$ {total:,.2f}")
                c2.metric("Contratos (Amostra)", len(df))
                
                st.dataframe(
                    df.sort_values("Data", ascending=False).style.format({"Valor": "R$ {:,.2f}"}),
                    use_container_width=True, hide_index=True
                )
            else:
                st.warning(f"⚠️ Nenhum contrato encontrado para {orgao_nome} nos últimos 24 meses.")
                st.caption("Dica: Alguns órgãos centralizam compras em outros códigos SIAFI.")