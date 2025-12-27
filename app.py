import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta

# --- CONFIGURAÇÃO ---
st.set_page_config(
    page_title="Auditoria Gov",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

PORTAL_KEY = "d03ede6b6072b78e6df678b6800d4ba1"

# --- MAPA DE ÓRGÃOS ---
ORGAOS_SIAFI = {
    "Ministério da Saúde (MS)": "36000",
    "Ministério da Educação (MEC)": "26000",
    "Ministério da Defesa (MD)": "52000",
    "Ministério da Justiça (MJ)": "30000",
    "Presidência da República": "20000"
}

# --- ESTILO ---
st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #fafafa; }
    .stTextInput > div > div > input { background-color: #262730; color: #fff; border: 1px solid #41444e; }
    
    /* Card de Sanção */
    .sancao-card {
        background-color: #1f2937;
        padding: 15px;
        border-radius: 8px;
        border-left: 5px solid #ef4444;
        margin-bottom: 10px;
    }
    .tag-ceis { background-color: #7f1d1d; color: #fca5a5; padding: 2px 8px; border-radius: 4px; font-size: 0.8em; font-weight: bold; }
    .tag-cnep { background-color: #451a03; color: #fdba74; padding: 2px 8px; border-radius: 4px; font-size: 0.8em; font-weight: bold; }
    
    /* Métricas */
    div[data-testid="stMetricValue"] {
        font-size: 1.8rem;
        color: #4ade80; /* Verde Dinheiro */
    }
    
    h1, h2, h3, p { font-family: 'Segoe UI', sans-serif; }
    
    .stButton>button {
        background-color: #2563eb; color: white; border: none; border-radius: 6px; height: 3em; font-weight: 500;
    }
    .stButton>button:hover { background-color: #1d4ed8; }
</style>
""", unsafe_allow_html=True)

# --- FUNÇÕES ---
def formatar_cnpj(cnpj):
    return "".join([n for n in cnpj if n.isdigit()])

@st.cache_data(ttl=3600)
def consultar_dados_cadastrais(cnpj):
    try:
        url = f"https://brasilapi.com.br/api/cnpj/v1/{formatar_cnpj(cnpj)}"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200: return resp.json()
    except: pass
    return None

def consultar_portal(endpoint, params):
    headers = {"chave-api-dados": PORTAL_KEY}
    url = f"https://api.portaldatransparencia.gov.br/api-de-dados/{endpoint}"
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=30)
        return resp.json() if resp.status_code == 200 else []
    except: return []

def auditar_empresa(cnpj, nome_empresa):
    resultados = []
    cnpj_limpo = formatar_cnpj(cnpj)
    bases = ["ceis", "cnep"]
    encontrou_algo = False
    
    for base in bases:
        items = consultar_portal(base, {"cnpjSancionado": cnpj_limpo, "pagina": 1})
        validos = []
        for item in items:
            try:
                c1 = formatar_cnpj(item.get('sancionado', {}).get('codigoFormatado', ''))
                c2 = formatar_cnpj(item.get('pessoa', {}).get('cnpjFormatado', ''))
                if c1 == cnpj_limpo or c2 == cnpj_limpo:
                    item['_origem'] = base.upper()
                    validos.append(item)
            except: pass
            
        if not validos and nome_empresa and not encontrou_algo:
            termo = nome_empresa.split(" LTDA")[0].split(" S.A")[0][:60]
            items_nome = consultar_portal(base, {"nomeSancionado": termo, "pagina": 1})
            for item in items_nome:
                c1 = formatar_cnpj(item.get('sancionado', {}).get('codigoFormatado', ''))
                if c1 == cnpj_limpo:
                    item['_origem'] = base.upper()
                    validos.append(item)
        
        if validos:
            resultados.extend(validos)
            encontrou_algo = True
            
    return resultados

# --- INTERFACE ---
with st.sidebar:
    st.title("Auditoria Gov")
    menu = st.radio("Menu", ["Auditoria Unificada", "Monitor de Dados"])
    st.info("v20.0 | Dashboard Ativo 📊")

if menu == "Auditoria Unificada":
    st.header("Auditoria de Fornecedores")
    
    col_inp, col_btn = st.columns([4, 1])
    with col_inp:
        cnpj_input = st.text_input("CNPJ", placeholder="Digite o CNPJ...", label_visibility="collapsed")
    with col_btn:
        btn_check = st.button("AUDITAR", type="primary")
        
    if btn_check and cnpj_input:
        st.markdown("---")
        with st.spinner("Analisando todas as bases federais..."):
            cad = consultar_dados_cadastrais(cnpj_input)
            razao = cad.get('razao_social', '') if cad else ""
            if razao: st.info(f"🏢 **{razao}**")
            
            lista_sancoes = auditar_empresa(cnpj_input, razao)
            
            if lista_sancoes:
                st.error(f"❌ **EMPRESA RESTRITA:** {len(lista_sancoes)} sanções encontradas.")
                for item in lista_sancoes:
                    origem = item.get('_origem', 'GOV')
                    orgao = item.get('orgaoSancionador', {}).get('nome', 'Órgão não informado')
                    motivo = item.get('tipoSancao', {}).get('descricaoResumida', 'Motivo não detalhado')
                    data_fim = item.get('dataFimSancao', 'Indeterminado')
                    tag_class = "tag-cnep" if origem == "CNEP" else "tag-ceis"
                    
                    st.markdown(f"""
                    <div class="sancao-card">
                        <span class="{tag_class}">{origem}</span>
                        <span style="margin-left: 10px; font-weight: bold; color: #e5e7eb;">{orgao}</span>
                        <div style="margin-top: 8px; color: #9ca3af; font-size: 0.9em;">
                            Motivo: {motivo} <br>
                            <strong>Vigência até: {data_fim}</strong>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.success("✅ **APTO PARA CONTRATAÇÃO:** Nenhuma restrição encontrada.")

elif menu == "Monitor de Dados":
    st.header("Monitoramento Federal 📊")
    st.markdown("Analise gastos e contratos em tempo real.")
    
    # Filtros em container para ficar organizado
    with st.container():
        col_tipo, col_orgao = st.columns([1, 2])
        with col_tipo:
            tipo_busca = st.selectbox("Tipo de Dado:", ["licitacoes", "contratos"], format_func=lambda x: x.capitalize())
        with col_orgao:
            orgao_selecionado = st.selectbox("Órgão Público:", list(ORGAOS_SIAFI.keys()))
            cod_orgao = ORGAOS_SIAFI[orgao_selecionado]
        
        col_inicio, col_fim = st.columns([1, 1])
        default_inicio = datetime(2024, 10, 1)
        default_fim = datetime(2024, 10, 31)
        
        with col_inicio:
            data_inicio = st.date_input("De:", value=default_inicio, format="DD/MM/YYYY")
        with col_fim:
            data_fim = st.date_input("Até:", value=default_fim, format="DD/MM/YYYY")
        
        btn_buscar = st.button("Analisar Dados", type="primary", use_container_width=True)
    
    if btn_buscar:
        st.markdown("---")
        with st.spinner(f"Minerando dados do {orgao_selecionado}..."):
            params = {
                "dataInicial": data_inicio.strftime("%d/%m/%Y"),
                "dataFinal": data_fim.strftime("%d/%m/%Y"),
                "codigoOrgao": cod_orgao,
                "pagina": 1
            }
            
            dados = consultar_portal(tipo_busca, params)
            
            if dados:
                lista_tabela = []
                total_gasto = 0.0
                
                # Processamento dos Dados
                for d in dados:
                    if tipo_busca == "contratos":
                        val = d.get('valorInicial', 0)
                        if val == 0: val = d.get('valorVigente', 0)
                        if val == 0: val = d.get('valorGlobal', 0)
                        
                        total_gasto += val
                        forn = d.get('fornecedor', {}).get('nome', 'OUTROS/SIGILOSO')
                        
                        lista_tabela.append({
                            "Data": d.get('dataAssinatura'),
                            "Fornecedor": forn[:30], # Corta nomes muito longos
                            "Valor_Num": val, # Usado para gráficos
                            "Valor": f"R$ {val:,.2f}" # Usado para exibir
                        })
                    else:
                        lista_tabela.append({
                            "Data": d.get('dataAbertura'),
                            "Objeto": d.get('objeto', 'Sem descrição')[:80] + "...",
                            "Situação": d.get('situacaoAviso', 'N/A')
                        })

                # Cria DataFrame
                df = pd.DataFrame(lista_tabela)
                
                # --- DASHBOARD (SÓ PARA CONTRATOS) ---
                if tipo_busca == "contratos" and not df.empty:
                    # 1. KPIs (Indicadores)
                    kpi1, kpi2, kpi3 = st.columns(3)
                    kpi1.metric("Total Analisado", f"R$ {total_gasto:,.2f}")
                    kpi2.metric("Qtd. Contratos", len(df))
                    media = total_gasto / len(df) if len(df) > 0 else 0
                    kpi3.metric("Ticket Médio", f"R$ {media:,.2f}")
                    
                    st.markdown("### 🏆 Top Fornecedores por Valor")
                    
                    # 2. Gráfico de Barras
                    # Agrupa por fornecedor e soma os valores
                    df_chart = df.groupby("Fornecedor")["Valor_Num"].sum().reset_index()
                    df_chart = df_chart.sort_values(by="Valor_Num", ascending=False).head(5)
                    df_chart = df_chart.set_index("Fornecedor") # Índice vira o label do gráfico
                    
                    st.bar_chart(df_chart["Valor_Num"], color="#2563eb")
                    
                    # Limpa colunas auxiliares para a tabela final
                    df_display = df.drop(columns=["Valor_Num"]).sort_values(by="Data", ascending=False)
                else:
                    df_display = df
                
                # Exibe Tabela
                st.markdown("### 📋 Detalhamento dos Registros")
                st.dataframe(df_display, use_container_width=True, hide_index=True)
                
            else:
                st.warning("Nenhum dado encontrado para os filtros selecionados.")