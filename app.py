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
        # MinhaReceita é gratuita e rápida
        r = requests.get(f"https://minhareceita.org/{limpar_cnpj(cnpj)}", timeout=5)
        if r.status_code == 200: return r.json()
    except: pass
    return None

def auditar_empresa_blindada(cnpj_alvo):
    resultados_validos = []
    cnpj_limpo_alvo = limpar_cnpj(cnpj_alvo)
    
    bases = ["ceis", "cnep"]
    
    for base in bases:
        url = f"https://api.portaldatransparencia.gov.br/api-de-dados/{base}"
        params = {"cnpjSancionado": cnpj_limpo_alvo, "pagina": 1}
        
        try:
            resp = requests.get(url, params=params, headers=get_headers(), timeout=15)
            if resp.status_code == 200:
                items = resp.json()
                
                # --- FILTRO PENTE-FINO ---
                for item in items:
                    cnpj_encontrado = ""
                    try: cnpj_encontrado = item['sancionado']['codigoFormatado']
                    except: pass
                    
                    if not cnpj_encontrado:
                        try: cnpj_encontrado = item['pessoa']['cnpjFormatado']
                        except: pass
                    
                    # Verifica se o CNPJ retornado contem o alvo (match exato ou filial)
                    if cnpj_limpo_alvo in limpar_cnpj(cnpj_encontrado):
                        item['_origem'] = base.upper()
                        resultados_validos.append(item)
                        
        except: pass
            
    return resultados_validos

# --- INTERFACE ---
st.title("⚖️ Auditoria Gov Federal (V31)")

aba1, aba2 = st.tabs(["🕵️ Auditoria CNPJ", "📊 Monitor de Contratos"])

# --- ABA 1 ---
with aba1:
    st.header("Verificar Fornecedor")
    cnpj_input = st.text_input("CNPJ:", value="07.161.936/0001-83") # Já deixei um "sujo" de exemplo
    
    if st.button("Auditar Agora", type="primary"):
        with st.spinner("Analisando..."):
            cad = consultar_dados_cadastrais(cnpj_input)
            razao = cad.get('razao_social') if cad else "Empresa não identificada"
            
            st.info(f"🏢 Alvo: **{razao}**")
            
            sancoes = auditar_empresa_blindada(cnpj_input)
            
            st.divider()
            if sancoes:
                st.error(f"🚨 **CUIDADO: {len(sancoes)} SANÇÕES ENCONTRADAS**")
                for s in sancoes:
                    st.markdown(f"**{s['_origem']}**: {s.get('tipoSancao', {}).get('descricaoResumida', 'Sanção')} - *{s.get('orgaoSancionador', {}).get('nome')}*")
            else:
                st.success("✅ Nada Consta (CNPJ Limpo)")

# --- ABA 2 ---
with aba2:
    st.header("Monitoramento de Contratos")
    
    c1, c2 = st.columns([2, 1])
    with c1: orgao = st.selectbox("Órgão", list(ORGAOS_SIAFI.keys()))
    
    # MUDANÇA V31: Padrão de 1 ANO atrás para garantir dados
    dt_hoje = datetime.now()
    dt_inicio = dt_hoje - timedelta(days=365) 
    
    with c2: 
        st.write(f"📅 Buscando desde: **{dt_inicio.strftime('%d/%m/%Y')}**")
    
    if st.button("Buscar Contratos (12 Meses)"):
        cod = ORGAOS_SIAFI[orgao]
        params = {
            "dataInicial": dt_inicio.strftime("%d/%m/%Y"),
            "dataFinal": dt_hoje.strftime("%d/%m/%Y"),
            "codigoOrgao": cod,
            "pagina": 1
        }
        
        try:
            with st.spinner(f"Baixando contratos do {orgao}..."):
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
                            "Fornecedor": d.get('fornecedor', {}).get('nome', 'N/A')[:40],
                            "Valor": val
                        })
                    
                    df = pd.DataFrame(lista)
                    
                    # KPIs
                    k1, k2 = st.columns(2)
                    k1.metric("Total Gasto", f"R$ {total:,.2f}")
                    k2.metric("Contratos", len(df))
                    
                    # Tabela
                    st.dataframe(df.sort_values("Data", ascending=False).style.format({"Valor": "R$ {:,.2f}"}), use_container_width=True)
                else:
                    st.warning("⚠️ Nenhum contrato encontrado, mesmo buscando 1 ano inteiro.")
                    st.caption("Isso indica que este órgão específico não reportou dados à API recentemente.")
        except Exception as e:
            st.error(f"Erro: {e}")