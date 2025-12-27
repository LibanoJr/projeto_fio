import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Auditoria Gov", page_icon="⚖️", layout="wide")

PORTAL_KEY = "d03ede6b6072b78e6df678b6800d4ba1"

# --- MAPA DE ÓRGÃOS ---
# Ordem alterada para priorizar o MS que sempre tem dados
ORGAOS_SIAFI = {
    "Ministério da Saúde (MS)": "36000",
    "Ministério da Educação (MEC)": "26000",
    "Ministério da Justiça (MJ)": "30000",
    "Presidência da República": "20000",
    "Ministério da Defesa (MD)": "52000"
}

# --- FUNÇÕES ---
def get_headers():
    # Finge ser um navegador para não ser bloqueado na nuvem
    return {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

def formatar_moeda(valor):
    try:
        if not valor: return "R$ 0,00"
        return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except: return "R$ 0,00"

def safe_float(valor):
    try:
        return float(valor)
    except: return 0.0

def limpar_cnpj(cnpj):
    return "".join([n for n in cnpj if n.isdigit()])

@st.cache_data(ttl=3600)
def consultar_dados_cadastrais(cnpj):
    clean_cnpj = limpar_cnpj(cnpj)
    headers = get_headers()
    
    # 1. Tenta BrasilAPI
    try:
        url = f"https://brasilapi.com.br/api/cnpj/v1/{clean_cnpj}"
        resp = requests.get(url, headers=headers, timeout=4)
        if resp.status_code == 200: return resp.json()
    except: pass
    
    # 2. Tenta ReceitaWS (Fallback 1)
    try:
        url2 = f"https://www.receitaws.com.br/v1/cnpj/{clean_cnpj}"
        resp2 = requests.get(url2, headers=headers, timeout=4)
        if resp2.status_code == 200:
            d = resp2.json()
            return {"razao_social": d.get('nome'), "descricao_situacao_cadastral": d.get('situacao')}
    except: pass

    # 3. Tenta MinhaReceita (Fallback 2 - Novo)
    try:
        url3 = f"https://minhareceita.org/{clean_cnpj}"
        resp3 = requests.get(url3, headers=headers, timeout=5)
        if resp3.status_code == 200:
            return resp3.json()
    except: pass
    
    return None

def consultar_portal(endpoint, params):
    headers = {"chave-api-dados": PORTAL_KEY}
    # Adiciona User-Agent também no Portal para garantir
    headers.update(get_headers())
    
    url = f"https://api.portaldatransparencia.gov.br/api-de-dados/{endpoint}"
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=30)
        if resp.status_code == 200:
            return resp.json()
    except: pass
    return []

def auditar_empresa(cnpj_alvo):
    resultados = []
    cnpj_limpo_alvo = limpar_cnpj(cnpj_alvo)
    bases = ["ceis", "cnep"]
    
    for base in bases:
        items = consultar_portal(base, {"cnpjSancionado": cnpj_limpo_alvo, "pagina": 1})
        for item in items:
            try:
                # Extração segura do CNPJ do retorno
                cnpj_retorno = item.get('sancionado', {}).get('codigoFormatado', '')
                if not cnpj_retorno:
                    cnpj_retorno = item.get('pessoa', {}).get('cnpjFormatado', '')
                
                # Filtro Rígido (Exato)
                if limpar_cnpj(cnpj_retorno) == cnpj_limpo_alvo:
                    item['_origem'] = base.upper()
                    resultados.append(item)
            except: continue
            
    return resultados

# --- INTERFACE ---
st.title("⚖️ Auditoria Gov Federal")
st.caption("Sistema de Monitoramento e Compliance em Contratações Públicas")

aba1, aba2 = st.tabs(["🕵️ Auditoria CNPJ", "📊 Monitoramento de Gastos"])

# --- ABA 1: AUDITORIA ---
with aba1:
    st.header("Compliance de Fornecedores")
    cnpj_input = st.text_input("CNPJ da Empresa:", placeholder="Ex: 00.000.000/0000-00")
    
    if st.button("Verificar Antecedentes", type="primary"):
        if len(cnpj_input) < 10:
            st.warning("CNPJ inválido.")
        else:
            with st.spinner("Consultando bases federais..."):
                cad = consultar_dados_cadastrais(cnpj_input)
                
                # Tratamento de erro visual se não achar nome
                if cad:
                    razao = cad.get('razao_social', 'Razão Social Não Localizada')
                    sit = cad.get('descricao_situacao_cadastral', 'N/A')
                else:
                    razao = "Nome não retornado pela API Pública"
                    sit = "Verifique o CNPJ"

                col_card, col_status = st.columns([3, 1])
                col_card.info(f"🏢 **{razao}**")
                
                if sit == "ATIVA":
                    col_status.success(f"RFB: {sit}")
                else:
                    col_status.warning(f"RFB: {sit}")
                
                # Auditoria
                sancoes = auditar_empresa(cnpj_input)
                
                st.markdown("---")
                if sancoes:
                    st.error(f"🚨 **ALERTA: {len(sancoes)} Restrições Confirmadas**")
                    for s in sancoes:
                        with st.expander(f"{s['_origem']} - {s.get('tipoSancao', {}).get('descricaoResumida', 'Sanção')}"):
                            st.write(f"**Órgão:** {s.get('orgaoSancionador', {}).get('nome')}")
                            st.write(f"**Motivo:** {s.get('motivo', 'Não detalhado')}")
                else:
                    st.success(f"✅ **NADA CONSTA** - CNPJ Limpo.")
                    st.caption("Nenhuma sanção encontrada nas bases CEIS/CNEP.")

# --- ABA 2: MONITORAMENTO ---
with aba2:
    st.header("Monitor de Gastos")
    
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1: orgao_selecionado = st.selectbox("Órgão", list(ORGAOS_SIAFI.keys()))
    
    # PADRÃO 60 DIAS (Para garantir dados)
    with c2: 
        data_ini = st.date_input("Início", datetime.now() - timedelta(days=60), format="DD/MM/YYYY")
    with c3: 
        data_fim = st.date_input("Fim", datetime.now(), format="DD/MM/YYYY")
    
    cod_orgao = ORGAOS_SIAFI[orgao_selecionado]
    
    if st.button("Analisar Contratos", type="primary"):
        with st.spinner(f"Buscando dados no Portal da Transparência..."):
            
            params = {
                "dataInicial": data_ini.strftime("%d/%m/%Y"),
                "dataFinal": data_fim.strftime("%d/%m/%Y"),
                "codigoOrgao": cod_orgao,
                "pagina": 1
            }
            
            dados = consultar_portal("contratos", params)
            
            if dados:
                lista = []
                total = 0.0
                for d in dados:
                    val = d.get('valorInicial', 0)
                    if val == 0: val = d.get('valorGlobal', 0)
                    if val == 0: val = d.get('valorVigente', 0)
                    if val == 0: val = d.get('valorContratado', 0)
                    
                    val_float = safe_float(val)
                    total += val_float
                    
                    lista.append({
                        "Data": d.get('dataAssinatura', 'N/A'),
                        "Fornecedor": d.get('fornecedor', {}).get('nome', 'Desconhecido')[:40],
                        "Objeto": d.get('objeto', 'Sem descrição')[:80] + "...",
                        "Valor": val_float 
                    })
                
                df = pd.DataFrame(lista)
                
                kpi1, kpi2 = st.columns(2)
                kpi1.metric("Volume Financeiro", formatar_moeda(total))
                kpi2.metric("Contratos Analisados", len(df))
                
                if not df.empty and total > 0:
                    st.markdown("### 🏆 Top Fornecedores")
                    try:
                        df_chart = df.groupby("Fornecedor")["Valor"].sum().sort_values(ascending=False).head(5)
                        st.bar_chart(df_chart)
                    except: pass
                
                st.markdown("### 📋 Detalhamento")
                df_view = df.copy()
                df_view["Valor"] = df_view["Valor"].apply(formatar_moeda)
                if "Data" in df_view.columns:
                    df_view = df_view.sort_values(by="Data", ascending=False)
                st.dataframe(df_view, use_container_width=True, hide_index=True)
                
            else:
                st.warning(f"⚠️ Nenhum contrato encontrado para o **{orgao_selecionado}**.")
                st.info("💡 A Presidência e o MJ publicam menos contratos que a Saúde. Tente aumentar o período ou selecionar 'Ministério da Saúde' para ver mais exemplos.")