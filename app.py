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

# --- ESTILO (V14 Mantido) ---
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
        # Aumentei o timeout para 25s pois Contratos é pesado
        resp = requests.get(url, params=params, headers=headers, timeout=25)
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
    st.caption("v15.0 | Date Picker Fix")

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
    st.header("Monitoramento Federal")
    
    # Filtros Manuais (Resolve o problema da data errada)
    col_tipo, col_date = st.columns([1, 2])
    with col_tipo:
        tipo_busca = st.selectbox("Tipo de Dado:", ["contratos", "licitacoes"], format_func=lambda x: x.capitalize())
    with col_date:
        # Padrão: Últimos 30 dias (Garante volume de dados)
        hoje = datetime.now()
        data_range = st.date_input(
            "Período de Análise:",
            value=(hoje - timedelta(days=30), hoje),
            format="DD/MM/YYYY"
        )
    
    if st.button("Buscar Dados"):
        if len(data_range) != 2:
            st.warning("Selecione uma data inicial e final.")
        else:
            start, end = data_range
            st.caption(f"Buscando {tipo_busca} de {start.strftime('%d/%m/%Y')} até {end.strftime('%d/%m/%Y')}...")
            
            with st.spinner("Conectando ao Portal da Transparência..."):
                params = {
                    "dataInicial": start.strftime("%d/%m/%Y"),
                    "dataFinal": end.strftime("%d/%m/%Y"),
                    "pagina": 1
                }
                
                dados = consultar_portal(tipo_busca, params)
                
                if dados:
                    st.success(f"{len(dados)} registros encontrados.")
                    lista_tabela = []
                    
                    # Formatação Dinâmica (Contrato vs Licitação)
                    for d in dados:
                        if tipo_busca == "contratos":
                            lista_tabela.append({
                                "Data": d.get('dataAssinatura'),
                                "Órgão": d.get('unidadeGestora', {}).get('nome'),
                                "Fornecedor": d.get('fornecedor', {}).get('nome', 'N/A'),
                                "Valor": f"R$ {d.get('valorInicial', 0):,.2f}"
                            })
                        else: # Licitações
                            lista_tabela.append({
                                "Data": d.get('dataAbertura'),
                                "Órgão": d.get('unidadeGestora', {}).get('nome'),
                                "Objeto": d.get('objeto', '')[:80] + "...",
                                "Situação": d.get('situacaoAviso', 'N/A')
                            })
                            
                    st.dataframe(pd.DataFrame(lista_tabela), use_container_width=True, hide_index=True)
                else:
                    st.warning("Nenhum registro encontrado para este período.")
                    # Debug: Mostra a URL se der vazio pra gente saber o porquê
                    with st.expander("🛠️ Debug Técnico (Por que veio vazio?)"):
                        st.write(f"**Endpoint:** {tipo_busca}")
                        st.write(f"**Params Enviados:** {params}")
                        st.write("Dica: Se a data estiver no futuro ou o período for muito curto (ex: feriado), a API retorna vazio.")