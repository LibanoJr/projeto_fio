import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta

# --- CONFIGURAÇÃO INICIAL (LAYOUT WIDE & SIDEBAR FECHADA) ---
st.set_page_config(
    page_title="Auditoria Gov",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="collapsed" # Começa fechado para não poluir
)

# Chave da API
PORTAL_KEY = "d03ede6b6072b78e6df678b6800d4ba1"

# --- ESTÉTICA PROFISSIONAL (DARK MODE CORRIGIDO) ---
st.markdown("""
<style>
    /* Forçar Tema Escuro e Fundo Limpo */
    .stApp {
        background-color: #0e1117;
        color: #fafafa;
    }
    
    /* Inputs Estilizados (Dark) */
    .stTextInput > div > div > input {
        background-color: #262730;
        color: #ffffff;
        border: 1px solid #41444e;
    }
    
    /* Cards de Métricas e Resultados */
    div[data-testid="stMetric"], div.stAlert {
        background-color: #1f2937; /* Cinza azulado escuro */
        border: 1px solid #374151;
        border-radius: 6px;
        color: white;
    }
    
    /* Ajuste de Texto para Leitura */
    h1, h2, h3, p, li {
        color: #e5e7eb !important;
        font-family: 'Segoe UI', sans-serif;
    }
    
    /* Botão Principal (Sobriedade) */
    .stButton>button {
        background-color: #2563eb; /* Azul Institucional */
        color: white;
        border: none;
        border-radius: 6px;
        height: 3em;
        font-weight: 500;
        transition: 0.3s;
    }
    .stButton>button:hover {
        background-color: #1d4ed8;
    }

    /* Remover padding excessivo do topo */
    .block-container {
        padding-top: 2rem;
    }
</style>
""", unsafe_allow_html=True)

# --- FUNÇÕES ---

def formatar_cnpj(cnpj):
    return "".join([n for n in cnpj if n.isdigit()])

def get_dates_for_week(offset):
    today = datetime.now()
    if offset == 0:
        end_date = today
        start_date = today - timedelta(days=7)
    elif offset < 0:
        end_date = today - timedelta(weeks=abs(offset))
        start_date = end_date - timedelta(days=7)
    else:
        start_date = today + timedelta(weeks=offset-1)
        end_date = start_date + timedelta(days=7)
    return start_date, end_date

@st.cache_data(ttl=3600)
def consultar_dados_cadastrais(cnpj):
    """Busca nome na BrasilAPI"""
    cnpj_limpo = formatar_cnpj(cnpj)
    try:
        url = f"https://brasilapi.com.br/api/cnpj/v1/{cnpj_limpo}"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            return response.json()
    except:
        pass
    return None

def consultar_portal_transparencia(endpoint, params):
    headers = {"chave-api-dados": PORTAL_KEY}
    url = f"https://api.portaldatransparencia.gov.br/api-de-dados/{endpoint}"
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json()
    except:
        return []
    return []

def auditar_empresa(cnpj, nome_empresa):
    resultados = {"CEIS": [], "CNEP": [], "status": "Limpo", "origem": "N/A"}
    cnpj_limpo = formatar_cnpj(cnpj)
    bases = ["ceis", "cnep"]
    
    for base in bases:
        # 1. Busca por CNPJ
        resp_cnpj = consultar_portal_transparencia(base, {"cnpjSancionado": cnpj_limpo, "pagina": 1})
        
        items_validos = []
        if resp_cnpj:
            for item in resp_cnpj:
                try:
                    c_sanc = item.get('sancionado', {}).get('codigoFormatado', '')
                    c_pessoa = item.get('pessoa', {}).get('cnpjFormatado', '')
                    if formatar_cnpj(c_sanc) == cnpj_limpo or formatar_cnpj(c_pessoa) == cnpj_limpo:
                        items_validos.append(item)
                except: pass
        
        if items_validos:
            resultados[base.upper()] = items_validos
            resultados["status"] = "Sujo"
            resultados["origem"] = "CNPJ"
        
        # 2. Busca por Nome (Fallback)
        elif not items_validos and nome_empresa:
            termo_busca = nome_empresa.split(" LTDA")[0].split(" S.A")[0][:60]
            resp_nome = consultar_portal_transparencia(base, {"nomeSancionado": termo_busca, "pagina": 1})
            
            items_nome_validos = []
            if resp_nome:
                for item in resp_nome:
                    c_sanc = formatar_cnpj(item.get('sancionado', {}).get('codigoFormatado', ''))
                    if c_sanc == cnpj_limpo:
                        items_nome_validos.append(item)
            
            if items_nome_validos:
                resultados[base.upper()] = items_nome_validos
                resultados["status"] = "Sujo"
                resultados["origem"] = f"Nome ({termo_busca})"
                
    return resultados

# --- INTERFACE ---

# Sidebar Minimalista
with st.sidebar:
    st.title("Auditoria Gov")
    menu = st.radio("Ferramentas", ["Auditoria Rápida", "Monitor de Contratos"])
    st.markdown("---")
    st.caption("v13.0 Stable | Dark Mode")

if menu == "Auditoria Rápida":
    st.header("Auditoria de Fornecedores")
    st.markdown("Verificação de regularidade em bases federais (CEIS/CNEP).")
    
    col_inp, col_btn = st.columns([4, 1])
    with col_inp:
        cnpj_input = st.text_input("CNPJ", placeholder="Digite o CNPJ...", label_visibility="collapsed")
    with col_btn:
        btn_check = st.button("AUDITAR", type="primary")
        
    if btn_check and cnpj_input:
        st.markdown("---")
        with st.spinner("Processando cruzamento de dados..."):
            
            # 1. Dados Cadastrais
            dados_cadastrais = consultar_dados_cadastrais(cnpj_input)
            razao_social = dados_cadastrais.get('razao_social', '') if dados_cadastrais else ""
            
            if razao_social:
                st.info(f"🏢 **{razao_social}** ({dados_cadastrais.get('nome_fantasia', 'Sem fantasia')})")
            else:
                st.warning("CNPJ não localizado na base cadastral. Buscando apenas por numeração.")
            
            # 2. Auditoria
            resultado = auditar_empresa(cnpj_input, razao_social)
            
            col1, col2 = st.columns(2)
            
            # Bloco CEIS
            with col1:
                st.subheader("CEIS")
                if resultado["CEIS"]:
                    st.error(f"⚠️ {len(resultado['CEIS'])} RESTRIÇÕES")
                    for item in resultado["CEIS"]:
                        with st.expander("Detalhes da Sanção"):
                            st.write(f"**Orgão:** {item.get('orgaoSancionador', {}).get('nome', '')}")
                            st.write(f"**Motivo:** {item.get('tipoSancao', {}).get('descricaoResumida', 'N/A')}")
                else:
                    st.success("✅ Regular (Nada Consta)")

            # Bloco CNEP
            with col2:
                st.subheader("CNEP")
                if resultado["CNEP"]:
                    st.error(f"⚠️ {len(resultado['CNEP'])} RESTRIÇÕES")
                    st.json(resultado["CNEP"])
                else:
                    st.success("✅ Regular (Nada Consta)")
            
            # Resultado Final Limpo
            st.markdown("---")
            if resultado["status"] == "Sujo":
                st.error("❌ RESULTADO: **EMPRESA COM RESTRIÇÕES VIGENTES**")
            else:
                # Sem balões, apenas mensagem profissional
                st.success("✅ RESULTADO: **APTO PARA CONTRATAÇÃO**")

elif menu == "Monitor de Contratos":
    st.header("Monitor de Contratos")
    
    col_sem, col_space = st.columns([2, 3])
    with col_sem:
        opcao_semana = st.selectbox(
            "Período de Análise:",
            options=[-2, -1, 0, 1, 2],
            format_func=lambda x: "Semana Atual" if x == 0 else f"Semana {x:+d}",
            index=2
        )
    
    start, end = get_dates_for_week(opcao_semana)
    st.caption(f"De {start.strftime('%d/%m/%Y')} até {end.strftime('%d/%m/%Y')}")
    
    if st.button("Carregar Contratos"):
        with st.spinner("Buscando no Portal da Transparência..."):
            params = {
                "dataInicial": start.strftime("%d/%m/%Y"),
                "dataFinal": end.strftime("%d/%m/%Y"),
                "pagina": 1
            }
            dados = consultar_portal_transparencia("contratos", params)
            
            if dados:
                lista_tabela = []
                for d in dados:
                    lista_tabela.append({
                        "Data": d.get('dataAssinatura', ''),
                        "Órgão": d.get('unidadeGestora', {}).get('nome', 'N/A'),
                        "Fornecedor": d.get('fornecedor', {}).get('nome', 'N/A'),
                        "Valor": f"R$ {d.get('valorInicial', 0):,.2f}",
                    })
                st.dataframe(pd.DataFrame(lista_tabela), use_container_width=True, hide_index=True)
            else:
                st.info("Nenhum contrato encontrado para este período.")