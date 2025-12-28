import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import time

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="GovAudit Pro", 
    page_icon="⚖️", 
    layout="wide"
)

# --- CSS (VISUAL) ---
st.markdown("""
    <style>
        .block-container {padding-top: 2rem;}
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        
        /* Ajuste fino para tabelas */
        .stDataFrame {font-size: 0.9rem;}
    </style>
""", unsafe_allow_html=True)

PORTAL_KEY = "d03ede6b6072b78e6df678b6800d4ba1"

# --- LISTA DE ÓRGÃOS ---
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

def formatar_data_br(data_iso):
    # Transforma 2024-12-25 em 25/12/2024
    if not data_iso: return ""
    try:
        obj = datetime.strptime(data_iso, "%Y-%m-%d")
        return obj.strftime("%d/%m/%Y")
    except: return data_iso

@st.cache_data(ttl=3600)
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
    res = auditar_cnpj_detalhado(cnpj)
    return True if len(res) > 0 else False

def buscar_contratos(codigo_orgao):
    lista = []
    dt_fim = datetime.now()
    dt_ini = dt_fim - timedelta(days=730)
    bar = st.progress(0, text="Conectando ao Portal da Transparência...")
    for i, pag in enumerate(range(1, 4)):
        bar.progress((i+1)*33, text=f"Buscando página {pag} de contratos...")
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

# --- INTERFACE ---
st.title("🛡️ Auditoria Gov Federal")
st.markdown("---")

aba1, aba2 = st.tabs(["🕵️ Análise de Risco (CNPJ)", "💰 Monitor de Contratos"])

# --- ABA 1: CNPJ ---
with aba1:
    st.header("Verificar Fornecedor")
    col1, col2 = st.columns([4, 1])
    
    with col1:
        cnpj_input = st.text_input("CNPJ:", value="05.144.757/0001-72", placeholder="00.000.000/0000-00")
    
    with col2:
        # Truque do espaçamento para alinhar o botão com o input
        st.write("") 
        st.write("")
        botao_auditar = st.button("🔍 Auditar", type="primary", use_container_width=True)
    
    if botao_auditar:
        with st.spinner("Analisando sanções..."):
            try:
                r = requests.get(f"https://minhareceita.org/{limpar_string(cnpj_input)}", timeout=3)
                if r.status_code == 200: st.info(f"Razão Social: **{r.json().get('razao_social')}**")
            except: pass

            sancoes = auditar_cnpj_detalhado(cnpj_input)
            
            st.divider()
            if sancoes:
                st.error(f"🚨 **RISCO ALTO: {len(sancoes)} OCORRÊNCIAS**")
                for s in sancoes:
                    titulo = f"⚠️ {s['_origem']}"
                    if s.get('_aviso_oculto'): titulo += " (Sigilo Parcial)"
                    with st.expander(titulo):
                        st.write(f"**Envolvido:** {s['_nome_exibicao']}")
                        st.write(f"**Motivo:** {s.get('motivo') or s.get('situacaoAcordo')}")
            else:
                st.success("✅ **NADA CONSTA** - Fornecedor Limpo")

# --- ABA 2: CONTRATOS ---
with aba2:
    st.header("Análise de Gastos Públicos")
    
    c_input, c_chk = st.columns([3, 1])
    orgao_nome = c_input.selectbox("Selecione o Órgão:", list(ORGAOS_SIAFI.keys()))
    
    # Checkbox renomeado para explicar o que faz
    analisar_risco = c_chk.checkbox("Verificar Sanções (Lento)", value=True, help="Se marcado, o sistema verifica a 'ficha limpa' de cada fornecedor encontrado.")
    
    # Botão renomeado para "Buscar"
    if st.button("🔎 Buscar Contratos"):
        cod = ORGAOS_SIAFI[orgao_nome]
        raw = buscar_contratos(cod)
        
        if raw:
            tabela = []
            total = 0.0
            
            for item in raw:
                val = safe_float(item.get('valorInicialCompra') or item.get('valorFinalCompra'))
                cnpj = item.get('fornecedor', {}).get('cnpjFormatado', '')
                
                total += val
                tabela.append({
                    "Data": formatar_data_br(item.get('dataAssinatura')), # Data formatada BR
                    "Valor (R$)": val,
                    "Fornecedor": item.get('fornecedor', {}).get('nome', 'N/A')[:35],
                    "CNPJ": cnpj,
                    "Objeto": item.get('objeto', '')[:90],
                    "Situação": "⚪ N/A" 
                })
            
            df = pd.DataFrame(tabela)
            
            # Análise de Risco (Top 10)
            if analisar_risco:
                st.info("🔎 Verificando antecedentes criminais dos maiores fornecedores...")
                df_sorted = df.sort_values("Valor (R$)", ascending=False)
                top_cnpjs = df_sorted['CNPJ'].unique()[:10]
                
                status_cache = {}
                for c in top_cnpjs:
                    if c:
                        is_sujo = checar_risco_simples(c)
                        status_cache[c] = "🔴 ALERTA" if is_sujo else "🟢 OK"
                        time.sleep(0.1)
                
                df['Situação'] = df['CNPJ'].map(status_cache).fillna("⚪ N/A")

            # REORDENAR COLUNAS: Situação ao lado do CNPJ
            colunas_ordem = ["Data", "Valor (R$)", "Fornecedor", "CNPJ", "Situação", "Objeto"]
            df = df[colunas_ordem]

            # Métricas
            k1, k2, k3 = st.columns(3)
            k1.metric("Total Gasto", f"R$ {total:,.2f}")
            k2.metric("Qtd. Contratos", len(df))
            if analisar_risco:
                suspeitos = len(df[df['Situação'] == "🔴 ALERTA"])
                k3.metric("Fornecedores Suspeitos", suspeitos, delta_color="inverse")
            
            # Botão CSV
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("💾 Download Planilha (CSV)", csv, "auditoria_gov.csv", "text/csv")
            
            # Tabela Colorida
            def color_risk(val):
                if val == '🔴 ALERTA': return 'background-color: #ffcccc; color: red; font-weight: bold;'
                if val == '🟢 OK': return 'color: green; font-weight: bold;'
                return ''

            st.dataframe(
                df.style.applymap(color_risk, subset=['Situação']).format({"Valor (R$)": "R$ {:,.2f}"}),
                use_container_width=True, hide_index=True
            )
        else:
            st.warning("Nenhum contrato encontrado neste período.")