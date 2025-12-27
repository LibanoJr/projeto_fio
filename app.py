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
    "Ministério da Defesa (MD)": "52000"
}

# --- FUNÇÕES ---
def get_headers():
    return {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        "chave-api-dados": PORTAL_KEY
    }

def formatar_moeda(valor):
    try:
        if not valor: return "R$ 0,00"
        return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except: return "R$ 0,00"

def safe_float(valor):
    try: return float(valor)
    except: return 0.0

def limpar_cnpj(cnpj):
    if not cnpj: return ""
    return "".join([n for n in str(cnpj) if n.isdigit()])

@st.cache_data(ttl=3600)
def consultar_dados_cadastrais(cnpj):
    clean_cnpj = limpar_cnpj(cnpj)
    # Tenta MinhaReceita (Mais rápida e permissiva)
    try:
        r = requests.get(f"https://minhareceita.org/{clean_cnpj}", timeout=5)
        if r.status_code == 200: return r.json()
    except: pass
    return None

def auditar_empresa(cnpj_alvo):
    resultados = []
    cnpj_limpo_alvo = limpar_cnpj(cnpj_alvo)
    
    # Busca CEIS (Inidôneos) e CNEP (Punidos)
    bases = ["ceis", "cnep"]
    for base in bases:
        url = f"https://api.portaldatransparencia.gov.br/api-de-dados/{base}"
        # Buscamos apenas pelo CNPJ. Se a API devolver, É SUJEIRA. Não filtramos mais.
        params = {"cnpjSancionado": cnpj_limpo_alvo, "pagina": 1}
        
        try:
            resp = requests.get(url, params=params, headers=get_headers(), timeout=10)
            if resp.status_code == 200:
                items = resp.json()
                # Adiciona tudo o que a API retornou
                for item in items:
                    item['_origem'] = base.upper()
                    resultados.append(item)
        except: pass
            
    return resultados

# --- INTERFACE ---
st.title("⚖️ Auditoria Gov Federal (2025)")
st.caption(f"Data do Sistema: {datetime.now().strftime('%d/%m/%Y')}")

aba1, aba2 = st.tabs(["🕵️ Auditoria CNPJ", "📊 Contratos e Licitações"])

# --- ABA 1 ---
with aba1:
    st.header("Verificar Sanções")
    st.info("ℹ️ Agora o sistema exibe qualquer registro retornado pelo governo, sem filtros ocultos.")
    
    cnpj_input = st.text_input("CNPJ para Análise:", placeholder="Ex: 00.000.000/0000-00")
    
    if st.button("VARRER BASE DE DADOS", type="primary"):
        if len(cnpj_input) < 10:
            st.warning("CNPJ muito curto.")
        else:
            with st.spinner("Aguarde..."):
                cad = consultar_dados_cadastrais(cnpj_input)
                razao = cad.get('razao_social') or cad.get('nome_fantasia') or "Razão Social não localizada"
                
                st.subheader(f"🏢 {razao}")
                
                # BUSCA DIRETA SEM FILTRO
                sancoes = auditar_empresa(cnpj_input)
                
                st.divider()
                
                if sancoes:
                    st.error(f"🚨 **ALERTA MÁXIMO: {len(sancoes)} REGISTROS ENCONTRADOS**")
                    for s in sancoes:
                        with st.expander(f"⚠️ {s['_origem']} - Detalhes da Sanção"):
                            st.write(f"**Órgão Sancionador:** {s.get('orgaoSancionador', {}).get('nome')}")
                            st.write(f"**Motivo:** {s.get('motivo', 'Motivo não cadastrado no sistema')}")
                            st.write(f"**Processo:** {s.get('numeroProcesso', 'N/A')}")
                            data_pub = s.get('dataPublicacao')
                            if data_pub: st.caption(f"Publicado em: {data_pub}")
                else:
                    st.success("✅ **NADA CONSTA** (Consulta API Oficial)")

# --- ABA 2 ---
with aba2:
    st.header("Monitoramento de Gastos")
    
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1: orgao_selecionado = st.selectbox("Selecione o Órgão", list(ORGAOS_SIAFI.keys()))
    
    # DATAS AUTOMÁTICAS (HOJE - 60 DIAS)
    hoje = datetime.now()
    inicio_padrao = hoje - timedelta(days=60)
    
    with c2: data_ini = st.date_input("De:", inicio_padrao, format="DD/MM/YYYY")
    with c3: data_fim = st.date_input("Até:", hoje, format="DD/MM/YYYY")
    
    if st.button("BUSCAR CONTRATOS", type="primary"):
        cod_orgao = ORGAOS_SIAFI[orgao_selecionado]
        params = {
            "dataInicial": data_ini.strftime("%d/%m/%Y"),
            "dataFinal": data_fim.strftime("%d/%m/%Y"),
            "codigoOrgao": cod_orgao,
            "pagina": 1
        }
        
        url_debug = f"https://api.portaldatransparencia.gov.br/api-de-dados/contratos?dataInicial={params['dataInicial']}&dataFinal={params['dataFinal']}&codigoOrgao={cod_orgao}&pagina=1"

        with st.spinner("Consultando Portal da Transparência..."):
            try:
                # Timeout maior para garantir resposta
                resp = requests.get("https://api.portaldatransparencia.gov.br/api-de-dados/contratos", 
                                  params=params, headers=get_headers(), timeout=45)
                dados = resp.json() if resp.status_code == 200 else []
            except Exception as e:
                st.error(f"Erro de conexão: {e}")
                dados = []
            
            if dados:
                lista = []
                total = 0.0
                for d in dados:
                    val = d.get('valorInicial') or d.get('valorGlobal') or 0
                    val_float = safe_float(val)
                    total += val_float
                    lista.append({
                        "Data": d.get('dataAssinatura', 'N/A'),
                        "Fornecedor": d.get('fornecedor', {}).get('nome', 'N/A')[:40],
                        "Objeto": d.get('objeto', 'N/A')[:80]+"...",
                        "Valor": val_float
                    })
                
                df = pd.DataFrame(lista)
                k1, k2 = st.columns(2)
                k1.metric("Total no Período", formatar_moeda(total))
                k2.metric("Quantidade de Contratos", len(df))
                
                st.markdown("### 📋 Tabela de Contratos")
                st.dataframe(df.sort_values("Data", ascending=False).style.format({"Valor": "R$ {:,.2f}"}), use_container_width=True, hide_index=True)
            else:
                st.warning("⚠️ Nenhum contrato encontrado neste período.")
                st.markdown(f"**Diagnóstico:** O órgão pode não ter publicado dados entre {data_ini.strftime('%d/%m')} e {data_fim.strftime('%d/%m')}.")
                st.markdown(f"[🔎 Clique aqui para checar o JSON oficial]({url_debug})")