import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Auditoria Gov", page_icon="⚖️", layout="wide")

PORTAL_KEY = "d03ede6b6072b78e6df678b6800d4ba1"

# --- MAPA DE ÓRGÃOS ---
ORGAOS_SIAFI = {
    "Ministério da Saúde (MS)": "36000",
    "Ministério da Educação (MEC)": "26000",
    "Ministério da Defesa (MD)": "52000",
    "Ministério da Justiça (MJ)": "30000",
    "Presidência da República": "20000"
}

# --- FUNÇÕES ---
def formatar_moeda(valor):
    try:
        if not valor: return "R$ 0,00"
        return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except: return "R$ 0,00"

def safe_float(valor):
    try:
        return float(valor)
    except:
        return 0.0

@st.cache_data(ttl=3600)
def consultar_dados_cadastrais(cnpj):
    # Tenta BrasilAPI
    clean_cnpj = "".join([n for n in cnpj if n.isdigit()])
    try:
        url = f"https://brasilapi.com.br/api/cnpj/v1/{clean_cnpj}"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            return resp.json()
    except: pass
    
    # Fallback: Tenta ReceitaWS (opção gratuita pública) se BrasilAPI falhar
    try:
        url2 = f"https://www.receitaws.com.br/v1/cnpj/{clean_cnpj}"
        resp2 = requests.get(url2, timeout=5)
        if resp2.status_code == 200:
            data = resp2.json()
            # Padroniza chaves
            return {"razao_social": data.get('nome'), "descricao_situacao_cadastral": data.get('situacao')}
    except: pass
    
    return None

def consultar_portal(endpoint, params):
    headers = {"chave-api-dados": PORTAL_KEY}
    url = f"https://api.portaldatransparencia.gov.br/api-de-dados/{endpoint}"
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=30)
        if resp.status_code == 200:
            return resp.json()
    except: pass
    return []

def auditar_empresa(cnpj, nome_empresa_input):
    resultados = []
    cnpj_limpo = "".join([n for n in cnpj if n.isdigit()])
    bases = ["ceis", "cnep"]
    
    # 1. Busca por CNPJ
    for base in bases:
        items = consultar_portal(base, {"cnpjSancionado": cnpj_limpo, "pagina": 1})
        for item in items:
            item['_origem'] = base.upper()
            resultados.append(item)
            
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
                razao_social = cad.get('razao_social', 'Razão Social Não Localizada') if cad else "Empresa Não Identificada na Base"
                situacao = cad.get('descricao_situacao_cadastral', 'Desconhecida') if cad else "N/A"
                
                col_card, col_status = st.columns([3, 1])
                col_card.info(f"🏢 **{razao_social}**")
                col_status.metric("Situação RFB", situacao)
                
                # Auditoria
                sancoes = auditar_empresa(cnpj_input, razao_social)
                
                st.markdown("---")
                if sancoes:
                    st.error(f"🚨 **ALERTA: {len(sancoes)} Restrições Encontradas**")
                    for s in sancoes:
                        with st.expander(f"{s['_origem']} - {s.get('tipoSancao', {}).get('descricaoResumida', 'Sanção')}"):
                            st.write(f"**Órgão:** {s.get('orgaoSancionador', {}).get('nome')}")
                            st.write(f"**Motivo:** {s.get('motivo', 'Não detalhado')}")
                else:
                    st.success("✅ **NADA CONSTA** nas bases de sanções (CEIS/CNEP).")

# --- ABA 2: MONITORAMENTO ---
with aba2:
    st.header("Monitor de Gastos")
    
    # Filtros
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1: orgao_selecionado = st.selectbox("Órgão", list(ORGAOS_SIAFI.keys()))
    with c2: data_ini = st.date_input("Início", datetime.now() - timedelta(days=30))
    with c3: data_fim = st.date_input("Fim", datetime.now())
    
    cod_orgao = ORGAOS_SIAFI[orgao_selecionado]
    
    if st.button("Analisar Contratos e Licitações", type="primary"):
        with st.spinner(f"Minerando dados do {orgao_selecionado}..."):
            
            # PARÂMETROS API
            params = {
                "dataInicial": data_ini.strftime("%d/%m/%Y"),
                "dataFinal": data_fim.strftime("%d/%m/%Y"),
                "codigoOrgao": cod_orgao,
                "pagina": 1
            }
            
            # --- DEBUG VISUAL (Para resolvermos o problema do valor) ---
            with st.expander("🛠️ DEBUG API (Clique aqui se os valores estiverem zerados)"):
                # Fazemos uma requisição de teste só para mostrar o JSON bruto
                raw_data = consultar_portal("contratos", params)
                if raw_data:
                    st.write("Estrutura do Primeiro Item encontrado:")
                    st.json(raw_data[0])
                else:
                    st.warning("API retornou lista vazia.")

            # BUSCA REAL
            dados = consultar_portal("contratos", params)
            
            if dados:
                lista = []
                total = 0.0
                for d in dados:
                    # TENTATIVA DE RESGATE DE VALOR (Várias chaves possíveis)
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
                        "Valor": val_float # Numérico para ordenar
                    })
                
                df = pd.DataFrame(lista)
                
                # Exibição
                kpi1, kpi2 = st.columns(2)
                kpi1.metric("Total no Período", formatar_moeda(total))
                kpi2.metric("Contratos Encontrados", len(df))
                
                if not df.empty and total > 0:
                    st.markdown("### 🏆 Maiores Fornecedores")
                    df_chart = df.groupby("Fornecedor")["Valor"].sum().sort_values(ascending=False).head(5)
                    st.bar_chart(df_chart)
                
                st.markdown("### 📋 Tabela Detalhada")
                # Formata coluna valor para visualização
                df_view = df.copy()
                df_view["Valor"] = df_view["Valor"].apply(formatar_moeda)
                st.dataframe(df_view, use_container_width=True, hide_index=True)
                
            else:
                st.warning("Nenhum contrato encontrado neste período.")