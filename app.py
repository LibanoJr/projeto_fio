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

# --- CSS (CORREÇÕES VISUAIS V44) ---
st.markdown("""
    <style>
        /* Espaçamento superior */
        .block-container {padding-top: 2rem;}
        
        /* Esconder menus do Streamlit */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        
        /* CORREÇÃO 1: Alinhar botão de Auditar com o input de texto */
        [data-testid="column"]:nth-child(2) div[data-testid="stVerticalBlock"] > div:has(button) {
            display: flex;
            align-items: flex-end;
            height: 100%;
        }
        /* Ajuste fino para ficar na mesma linha de base */
        [data-testid="column"]:nth-child(2) button {
            margin-bottom: 2px; 
        }

        /* CORREÇÃO 2: Removido o CSS que deixava as métricas brancas e bugadas no dark mode */
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
    bar = st.progress(0, text="Iniciando conexão...")
    for i, pag in enumerate(range(1, 4)):
        bar.progress((i+1)*33, text=f"Baixando página {pag} de contratos...")
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
    # Layout de colunas ajustado pelo CSS no início do código
    col1, col2 = st.columns([4, 1]) 
    cnpj_input = col1.text_input("CNPJ:", value="05.144.757/0001-72", placeholder="00.000.000/0000-00")
    
    # Botão agora alinhado pelo CSS
    if col2.button("🔍 Auditar", type="primary", use_container_width=True):
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
    analisar_risco = c_chk.checkbox("Ativar Radar de Risco", value=True, help="Audita os 10 maiores fornecedores encontrados.")
    
    if st.button("📥 Baixar Dados"):
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
                    "Data": item.get('dataAssinatura'),
                    "Valor (R$)": val,
                    "Fornecedor": item.get('fornecedor', {}).get('nome', 'N/A')[:40],
                    "CNPJ": cnpj,
                    "Objeto": item.get('objeto', '')[:100],
                    # CORREÇÃO 3: Nome da coluna alterado
                    "Situação da Empresa": "⚪ N/A" 
                })
            
            df = pd.DataFrame(tabela)
            
            # Análise de Risco (Top 10)
            if analisar_risco:
                st.info("🔎 Verificando antecedentes dos maiores contratos...")
                df_sorted = df.sort_values("Valor (R$)", ascending=False)
                top_cnpjs = df_sorted['CNPJ'].unique()[:10]
                
                status_cache = {}
                for c in top_cnpjs:
                    if c:
                        is_sujo = checar_risco_simples(c)
                        status_cache[c] = "🔴 ALERTA" if is_sujo else "🟢 OK"
                        time.sleep(0.1)
                
                # Mapeia usando o novo nome da coluna
                df['Situação da Empresa'] = df['CNPJ'].map(status_cache).fillna("⚪ N/A")

            # Métricas
            k1, k2, k3 = st.columns(3)
            k1.metric("Total Gasto", f"R$ {total:,.2f}")
            k2.metric("Qtd. Contratos", len(df))
            if analisar_risco:
                # Conta usando o novo nome da coluna
                suspeitos = len(df[df['Situação da Empresa'] == "🔴 ALERTA"])
                k3.metric("Fornecedores Suspeitos", suspeitos, delta_color="inverse")
            
            # Botão CSV
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("💾 Download CSV", csv, "auditoria_gov.csv", "text/csv")
            
            # Tabela Colorida
            def color_risk(val):
                if val == '🔴 ALERTA': return 'background-color: #ffcccc; color: red; font-weight: bold;'
                if val == '🟢 OK': return 'color: green; font-weight: bold;'
                return ''

            st.dataframe(
                # Aplica estilo e formatação na nova coluna
                df.style.applymap(color_risk, subset=['Situação da Empresa']).format({"Valor (R$)": "R$ {:,.2f}"}),
                use_container_width=True, hide_index=True
            )
        else:
            st.warning("Nenhum contrato encontrado neste período.")