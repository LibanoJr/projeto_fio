import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import time

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="GovAudit Pro", 
    page_icon="🛡️", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CSS CUSTOMIZADO (ESTÉTICA) ---
st.markdown("""
    <style>
        .block-container {padding-top: 1.5rem; padding-bottom: 3rem;}
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        .stMetric {background-color: #f0f2f6; padding: 10px; border-radius: 5px; border-left: 5px solid #1f77b4;}
    </style>
""", unsafe_allow_html=True)

PORTAL_KEY = "d03ede6b6072b78e6df678b6800d4ba1"

# --- DADOS ---
ORGAOS_SIAFI = {
    "Secretaria-Geral Presidência (Planalto)": "20101",
    "Ministério da Saúde": "36000",
    "Ministério da Educação": "26000",
    "DNIT (Transportes)": "39252",
    "Polícia Federal": "30108",
    "Comando do Exército": "52121",
    "Ministério da Justiça": "30000"
}

# --- FUNÇÕES ---
def get_headers():
    return {"chave-api-dados": PORTAL_KEY, "Accept": "application/json"}

def limpar_string(texto):
    if not texto: return ""
    return "".join([c for c in str(texto) if c.isdigit()])

def safe_float(valor):
    try: return float(valor)
    except: return 0.0

@st.cache_data(ttl=3600) # Cache para não ficar lento
def auditar_cnpj_detalhado(cnpj_alvo):
    resultados = []
    cnpj_limpo = limpar_string(cnpj_alvo)
    raiz_alvo = cnpj_limpo[:8]
    bases = {"acordos-leniencia": "Acordo Leniência", "ceis": "Inidôneos (CEIS)", "cnep": "Punidos (CNEP)"}
    
    for endpoint, nome_base in bases.items():
        try:
            url = f"https://api.portaldatransparencia.gov.br/api-de-dados/{endpoint}"
            params = {"cnpjSancionado": cnpj_limpo, "pagina": 1}
            resp = requests.get(url, params=params, headers=get_headers(), timeout=5)
            if resp.status_code == 200:
                itens = resp.json()
                for item in itens:
                    # Lógica Fantasma & Raiz
                    cnpj_item = ""
                    nome_item = "Não informado"
                    try: 
                        sancionado = item.get('sancionado', {})
                        cnpj_item = sancionado.get('codigoFormatado') or item.get('pessoa', {}).get('cnpjFormatado')
                        nome_temp = sancionado.get('nome') or item.get('pessoa', {}).get('nome')
                        if nome_temp: nome_item = nome_temp
                    except: pass
                    
                    match = False
                    if cnpj_item and limpar_string(cnpj_item)[:8] == raiz_alvo: match = True
                    elif nome_base == "Acordo Leniência" and not cnpj_item:
                        match = True
                        item['_aviso_oculto'] = True

                    if match:
                        item['_origem'] = nome_base
                        item['_nome_exibicao'] = nome_item
                        resultados.append(item)
        except: pass
    return resultados

def checar_risco_simples(cnpj):
    # Versão simplificada para usar dentro do loop de contratos
    res = auditar_cnpj_detalhado(cnpj)
    return True if len(res) > 0 else False

def buscar_contratos(codigo_orgao):
    lista = []
    dt_fim = datetime.now()
    dt_ini = dt_fim - timedelta(days=730)
    
    # Barra de progresso visual
    bar = st.progress(0, text="Conectando ao Governo...")
    
    for i, pag in enumerate(range(1, 4)):
        bar.progress((i+1)*33, text=f"Baixando página {pag}...")
        try:
            params = {
                "dataInicial": dt_ini.strftime("%d/%m/%Y"), "dataFinal": dt_fim.strftime("%d/%m/%Y"),
                "codigoOrgao": codigo_orgao, "pagina": pag
            }
            r = requests.get("https://api.portaldatransparencia.gov.br/api-de-dados/contratos", 
                           params=params, headers=get_headers(), timeout=10)
            if r.status_code == 200:
                dados = r.json()
                if not dados: break
                lista.extend(dados)
            else: break
        except: break
    bar.empty()
    return lista

# --- LAYOUT SIDEBAR ---
with st.sidebar:
    st.title("🛡️ Painel de Controle")
    st.markdown("Filtros e Configurações")
    
    modo = st.radio("Selecione o Módulo:", ["🕵️ Auditoria Individual", "💰 Monitor de Contratos"])
    
    st.divider()
    st.caption(f"Versão 4.2 Stable | Base: Portal da Transparência")
    st.caption("Desenvolvido para Compliance Ágil")

# --- LÓGICA PRINCIPAL ---

if modo == "🕵️ Auditoria Individual":
    st.title("Auditoria de Compliance (CNPJ)")
    st.markdown("Verifique se uma empresa específica possui sanções no CEIS, CNEP ou Acordos de Leniência.")
    
    col1, col2 = st.columns([3, 1])
    cnpj_input = col1.text_input("Digite o CNPJ:", value="05.144.757/0001-72", placeholder="00.000.000/0000-00")
    
    if col2.button("🔍 Rastrear", type="primary"):
        with st.spinner("Cruzando dados federais..."):
            # 1. Identidade
            try:
                r = requests.get(f"https://minhareceita.org/{limpar_string(cnpj_input)}", timeout=3)
                if r.status_code == 200:
                    dados_rec = r.json()
                    st.info(f"Empresa: **{dados_rec.get('razao_social')}** | Status: {dados_rec.get('descricao_situacao_cadastral')}")
            except: pass
            
            # 2. Sanções
            sancoes = auditar_cnpj_detalhado(cnpj_input)
            
            st.divider()
            if sancoes:
                st.error(f"🚨 **RISCO ALTO:** Foram encontrados {len(sancoes)} registros impeditivos.")
                for s in sancoes:
                    txt_titulo = f"{s['_origem']}"
                    if s.get('_aviso_oculto'): txt_titulo += " (Dados Sigilosos/Parciais)"
                    
                    with st.expander(f"⚠️ {txt_titulo}"):
                        st.write(f"**Envolvido:** {s['_nome_exibicao']}")
                        st.write(f"**Motivo:** {s.get('motivo') or s.get('situacaoAcordo')}")
                        st.write(f"**Órgão Sancionador:** {s.get('orgaoSancionador', {}).get('nome')}")
            else:
                st.success("✅ **NADA CONSTA**")
                st.markdown(f"A raiz do CNPJ **{cnpj_input}** não consta nas listas de sanções vigentes.")

elif modo == "💰 Monitor de Contratos":
    st.title("Monitoramento de Gastos Públicos")
    
    # Filtros no topo
    c_filt1, c_filt2 = st.columns([3, 1])
    orgao_selecionado = c_filt1.selectbox("Selecione o Órgão:", list(ORGAOS_SIAFI.keys()))
    analisar_risco = c_filt2.checkbox("Ativar Radar de Risco?", value=True, help="Verifica antecedentes dos 10 maiores fornecedores.")
    
    if st.button("📥 Baixar Dados do Governo"):
        cod_siafi = ORGAOS_SIAFI[orgao_selecionado]
        
        raw_data = buscar_contratos(cod_siafi)
        
        if raw_data:
            tabela = []
            total_gasto = 0.0
            
            # Processamento
            for item in raw_data:
                val = safe_float(item.get('valorInicialCompra') or item.get('valorFinalCompra'))
                cnpj = item.get('fornecedor', {}).get('cnpjFormatado', '')
                nome = item.get('fornecedor', {}).get('nome', 'Sem Nome')
                
                total_gasto += val
                tabela.append({
                    "Data Assinatura": item.get('dataAssinatura'),
                    "Valor (R$)": val,
                    "Fornecedor": nome,
                    "CNPJ": cnpj,
                    "Objeto": item.get('objeto', '')[:100],
                    "Risco": "⚪ Não analisado"
                })
            
            df = pd.DataFrame(tabela)
            
            # Análise de Risco (Se ativado)
            if analisar_risco:
                st.info("🔎 Analisando fornecedores (Amostra dos maiores contratos)...")
                # Pega os CNPJs únicos dos maiores contratos para não demorar
                df = df.sort_values("Valor (R$)", ascending=False)
                top_cnpjs = df['CNPJ'].unique()[:10] # Limite de 10 para ser rápido
                
                status_cache = {}
                for cnpj_teste in top_cnpjs:
                    if cnpj_teste:
                        is_sujo = checar_risco_simples(cnpj_teste)
                        status_cache[cnpj_teste] = "🔴 ALERTA" if is_sujo else "🟢 OK"
                        time.sleep(0.1)
                
                # Aplica na tabela
                df['Risco'] = df['CNPJ'].map(status_cache).fillna("⚪ N/A")

            # Métricas
            m1, m2, m3 = st.columns(3)
            m1.metric("Volume Financeiro", f"R$ {total_gasto:,.2f}")
            m2.metric("Contratos Encontrados", len(df))
            if analisar_risco:
                riscos = len(df[df['Risco'] == "🔴 ALERTA"])
                m3.metric("Fornecedores Suspeitos", riscos, delta_color="inverse")
            
            # Botão de Download
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="💾 Baixar Relatório (CSV)",
                data=csv,
                file_name=f"auditoria_{orgao_selecionado}_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
            )
            
            # Tabela Visual
            def style_risk(v):
                if v == '🔴 ALERTA': return 'background-color: #ffcccc; color: red; font-weight: bold;'
                if v == '🟢 OK': return 'color: green; font-weight: bold;'
                return ''
                
            st.dataframe(
                df.style.applymap(style_risk, subset=['Risco']).format({"Valor (R$)": "R$ {:,.2f}"}),
                use_container_width=True,
                hide_index=True
            )
            
        else:
            st.warning("Nenhum contrato encontrado para este órgão no período de 2 anos.")