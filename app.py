import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta

# --- CONFIGURAÇÃO INICIAL E ESTÉTICA ---
st.set_page_config(
    page_title="GovMonitor Pro",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Chave da API do Portal da Transparência
PORTAL_KEY = "d03ede6b6072b78e6df678b6800d4ba1"

# CSS para Visual Profissional e Minimalista
st.markdown("""
<style>
    /* Fundo e Fontes */
    .stApp {
        background-color: #f8f9fa;
    }
    h1, h2, h3 {
        font-family: 'Segoe UI', sans-serif;
        color: #0f172a;
    }
    
    /* Cards de Métricas */
    div[data-testid="stMetric"] {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        padding: 15px;
        border-radius: 8px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    
    /* Alerts customizados */
    .stAlert {
        border-radius: 8px;
    }
    
    /* Botões */
    .stButton>button {
        width: 100%;
        border-radius: 6px;
        height: 3em;
        font-weight: 600;
    }
    
    /* Tabelas */
    .dataframe {
        font-size: 0.9rem !important;
    }
</style>
""", unsafe_allow_html=True)

# --- FUNÇÕES AUXILIARES ---

def formatar_cnpj(cnpj):
    return "".join([n for n in cnpj if n.isdigit()])

def get_dates_for_week(offset):
    """
    Calcula data inicial e final com base no offset de semanas.
    0 = Semana atual (Hoje - 7 dias até Hoje)
    -1 = Semana passada
    1 = Semana futura
    """
    today = datetime.now()
    if offset == 0:
        end_date = today
        start_date = today - timedelta(days=7)
    elif offset < 0:
        # Passado: desloca semanas para trás
        end_date = today - timedelta(weeks=abs(offset))
        start_date = end_date - timedelta(days=7)
    else:
        # Futuro
        start_date = today + timedelta(weeks=offset-1)
        end_date = start_date + timedelta(days=7)
    
    return start_date, end_date

@st.cache_data(ttl=3600)
def consultar_dados_cadastrais(cnpj):
    """
    Busca nome e dados básicos na BrasilAPI (Rápida e sem chave)
    para garantir que sempre temos o nome da empresa.
    """
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
    """Função genérica para bater na API do governo"""
    headers = {"chave-api-dados": PORTAL_KEY}
    url = f"https://api.portaldatransparencia.gov.br/api-de-dados/{endpoint}"
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        return []
    return []

# --- LÓGICA DE AUDITORIA (CNPJ + NOME) ---

def auditar_empresa(cnpj, nome_empresa):
    resultados = {"CEIS": [], "CNEP": [], "status": "Limpo", "origem": "N/A"}
    cnpj_limpo = formatar_cnpj(cnpj)
    
    bases = ["ceis", "cnep"]
    
    for base in bases:
        # 1. Tenta busca pelo CNPJ
        resp_cnpj = consultar_portal_transparencia(base, {"cnpjSancionado": cnpj_limpo, "pagina": 1})
        
        # Filtra resposta do CNPJ (Pente Fino)
        items_validos = []
        if resp_cnpj:
            for item in resp_cnpj:
                try:
                    c_sanc = item.get('sancionado', {}).get('codigoFormatado', '')
                    c_pessoa = item.get('pessoa', {}).get('cnpjFormatado', '')
                    if formatar_cnpj(c_sanc) == cnpj_limpo or formatar_cnpj(c_pessoa) == cnpj_limpo:
                        items_validos.append(item)
                except:
                    pass
        
        if items_validos:
            resultados[base.upper()] = items_validos
            resultados["status"] = "Sujo"
            resultados["origem"] = "CNPJ"
        
        # 2. SE NÃO ACHOU POR CNPJ, MAS TEMOS O NOME, TENTA PELO NOME
        # (Isso resolve o caso Denipotti onde a API falha no CNPJ)
        elif not items_validos and nome_empresa:
            # Pega o primeiro nome ou nome principal para busca
            termo_busca = nome_empresa.split(" LTDA")[0].split(" S.A")[0][:60] 
            resp_nome = consultar_portal_transparencia(base, {"nomeSancionado": termo_busca, "pagina": 1})
            
            # Filtra por similaridade de CNPJ se disponível no retorno do nome
            items_nome_validos = []
            if resp_nome:
                for item in resp_nome:
                    # Verifica se o CNPJ bate, caso exista no registro retornado pelo nome
                    c_sanc = formatar_cnpj(item.get('sancionado', {}).get('codigoFormatado', ''))
                    if c_sanc == cnpj_limpo:
                        items_nome_validos.append(item)
            
            if items_nome_validos:
                resultados[base.upper()] = items_nome_validos
                resultados["status"] = "Sujo"
                resultados["origem"] = f"Nome ({termo_busca})"
                
    return resultados

# --- INTERFACE: SIDEBAR ---
with st.sidebar:
    st.header("GovMonitor Pro")
    menu = st.radio("Navegação", ["🔍 Auditoria Express", "📊 Monitor de Contratos"])
    st.divider()
    st.caption("Sistema v12.0 (Stable)")
    st.caption("Status API: Online 🟢")

# --- PÁGINA 1: AUDITORIA ---
if menu == "🔍 Auditoria Express":
    st.title("Auditoria de Fornecedores")
    st.markdown("Verificação cruzada de sanções (CEIS/CNEP) via CNPJ e Razão Social.")
    
    col_inp, col_btn = st.columns([3, 1])
    with col_inp:
        cnpj_input = st.text_input("CNPJ da Empresa", placeholder="00.000.000/0001-00")
    with col_btn:
        st.write("") # Espaçamento
        st.write("") 
        btn_check = st.button("🛡️ AUDITAR", type="primary")
        
    if btn_check and cnpj_input:
        st.divider()
        with st.spinner("Consultando Receita e Bases Sancionadoras..."):
            
            # 1. Pega Dados Cadastrais (BrasilAPI)
            dados_cadastrais = consultar_dados_cadastrais(cnpj_input)
            razao_social = dados_cadastrais.get('razao_social', '') if dados_cadastrais else ""
            fantasia = dados_cadastrais.get('nome_fantasia', '')
            
            # Exibe Cabeçalho da Empresa
            if razao_social:
                st.success(f"🏢 **Empresa Identificada:** {razao_social}")
                if fantasia:
                    st.caption(f"Nome Fantasia: {fantasia}")
            else:
                st.warning("⚠️ Nome não encontrado na base cadastral. Buscando apenas por CNPJ numérico.")
            
            # 2. Auditoria Pesada
            resultado = auditar_empresa(cnpj_input, razao_social)
            
            # 3. Exibição dos Resultados
            col1, col2 = st.columns(2)
            
            # CEIS
            with col1:
                st.subheader("CEIS")
                lista_ceis = resultado["CEIS"]
                if lista_ceis:
                    st.error(f"🚨 {len(lista_ceis)} REGISTROS ENCONTRADOS")
                    for item in lista_ceis:
                        with st.expander(f"🚫 Sanção: {item.get('tipoSancao', {}).get('descricaoResumida', 'N/A')}"):
                            st.write(f"**Orgão:** {item.get('orgaoSancionador', {}).get('nome', '')}")
                            st.write(f"**Início:** {item.get('dataInicioSancao', '')}")
                            st.write(f"**Fim:** {item.get('dataFimSancao', 'Indeterminado')}")
                else:
                    st.success("✅ Nada Consta")

            # CNEP
            with col2:
                st.subheader("CNEP")
                lista_cnep = resultado["CNEP"]
                if lista_cnep:
                    st.error(f"🚨 {len(lista_cnep)} REGISTROS ENCONTRADOS")
                    st.json(lista_cnep)
                else:
                    st.success("✅ Nada Consta")
            
            # Conclusão Final
            st.markdown("---")
            if resultado["status"] == "Sujo":
                st.error(f"❌ RESULTADO: **RESTRITO**. Encontrado via busca por: {resultado['origem']}")
            else:
                st.balloons()
                st.success("✅ RESULTADO: **APTO**. Nenhuma restrição encontrada nas bases federais.")

# --- PÁGINA 2: MONITORAMENTO ---
elif menu == "📊 Monitor de Contratos":
    st.title("Monitoramento de Contratos")
    st.markdown("Acompanhamento semanal de contratos e licitações do Governo Federal.")
    
    # Seletor de Semanas
    col_sem, col_info = st.columns([1, 2])
    with col_sem:
        opcao_semana = st.selectbox(
            "Selecione o Período:",
            options=[-2, -1, 0, 1, 2],
            format_func=lambda x: "Semana Atual" if x == 0 else f"Semana {x:+d}",
            index=2 # Começa no 0
        )
    
    start, end = get_dates_for_week(opcao_semana)
    
    with col_info:
        st.info(f"📅 Período: **{start.strftime('%d/%m/%Y')}** até **{end.strftime('%d/%m/%Y')}**")
    
    if st.button("🔄 Buscar Contratos"):
        with st.spinner("Buscando contratos no período..."):
            # Parâmetros para API
            params = {
                "dataInicial": start.strftime("%d/%m/%Y"),
                "dataFinal": end.strftime("%d/%m/%Y"),
                "pagina": 1
            }
            
            # Busca Contratos (Endpoint do Portal)
            dados = consultar_portal_transparencia("contratos", params)
            
            if dados:
                st.success(f"Encontrados {len(dados)} contratos recentes.")
                
                # Processamento para Tabela
                lista_tabela = []
                for d in dados:
                    lista_tabela.append({
                        "Data": d.get('dataAssinatura', ''),
                        "Órgão": d.get('unidadeGestora', {}).get('nome', 'N/A'),
                        "Fornecedor": d.get('fornecedor', {}).get('nome', 'N/A'),
                        "Valor (R$)": f"R$ {d.get('valorInicial', 0):,.2f}",
                        "Objeto": d.get('objeto', '')[:100] + "..."
                    })
                
                df = pd.DataFrame(lista_tabela)
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.warning("Nenhum contrato encontrado neste período ou API instável.")