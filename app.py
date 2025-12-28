import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
import google.generativeai as genai

# --- CONFIGURAÇÃO INICIAL ---
st.set_page_config(page_title="GovAudit Pro + IA", page_icon="⚖️", layout="wide")
load_dotenv()

# Recupera chaves
PORTAL_KEY = os.getenv("PORTAL_KEY")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")

if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)

# --- CSS ---
st.markdown("""
    <style>
        .block-container {padding-top: 1.5rem;}
        div[data-testid="stMetricValue"] {font-size: 1.8rem;}
        .stButton>button {width: 100%; margin-top: 29px;}
    </style>
""", unsafe_allow_html=True)

# --- DADOS ---
ORGAOS_SIAFI = {
    "Secretaria-Geral Presidência (Planalto)": "20101",
    "Ministério da Saúde": "36000",
    "Ministério da Educação": "26000",
    "Polícia Federal": "30108",
    "Comando do Exército": "52121",
    "Ministério da Justiça": "30000"
}

# --- FUNÇÕES ---
def get_headers():
    return {"chave-api-dados": PORTAL_KEY, "Accept": "application/json"}

def limpar_string(texto):
    return "".join([c for c in str(texto) if c.isdigit()]) if texto else ""

def safe_float(valor):
    try: return float(valor)
    except: return 0.0

# --- AUDITORIA CNPJ (CORRIGIDA) ---
@st.cache_data(ttl=3600)
def auditar_cnpj_gov(cnpj_alvo):
    resultados = [] 
    cnpj_limpo = limpar_string(cnpj_alvo)
    
    # Bases a consultar
    bases = {
        "acordos-leniencia": "Leniência (Corrupção)", 
        "ceis": "Inidôneos (CEIS)", 
        "cnep": "Punidos (CNEP)"
    }
    
    for endpoint, label in bases.items():
        try:
            url = f"https://api.portaldatransparencia.gov.br/api-de-dados/{endpoint}"
            # Busca simples: se retornar lista não vazia, é flag
            params = {"cnpjSancionado": cnpj_limpo, "pagina": 1}
            r = requests.get(url, params=params, headers=get_headers(), timeout=5)
            
            if r.status_code == 200 and len(r.json()) > 0:
                # Pega o primeiro motivo encontrado
                item = r.json()[0]
                motivo = "Sanção identificada na base de dados."
                
                # Tenta extrair detalhes dependendo da base
                if 'motivo' in item: motivo = item['motivo']
                elif 'sancionado' in item: motivo = "Registro ativo no cadastro de sanções."
                
                resultados.append({"_origem": label, "motivo": motivo})
        except:
            pass # Falha de conexão ignora, mas não quebra
            
    return resultados

# --- IA GEMINI ---
def analisar_contrato_ia(objeto_texto):
    if not GEMINI_KEY: return "⚠️ S/ Chave"
    
    prompt = f"""
    Analise este objeto de contrato público. Identifique riscos de imprecisão ou sobrepreço potencial.
    Objeto: "{objeto_texto}"
    Responda APENAS: 'ALTO RISCO', 'MÉDIO RISCO' ou 'BAIXO RISCO'.
    """
    
    modelos = ['gemini-1.5-flash', 'gemini-pro']
    for modelo in modelos:
        try:
            model = genai.GenerativeModel(modelo)
            response = model.generate_content(prompt)
            return response.text.strip()
        except: continue
    return "Erro Conexão IA"

# --- BUSCA CONTRATOS ---
def buscar_contratos(codigo_orgao):
    lista = []
    dt_fim = datetime.now()
    dt_ini = dt_fim - timedelta(days=730)
    
    placeholder = st.empty()
    bar = placeholder.progress(0, text="Conectando ao Portal...")
    
    # Baixa 3 páginas
    for i, pag in enumerate(range(1, 4)):
        bar.progress((i+1)*30, text=f"Baixando Contratos (Pág {pag})...")
        try:
            params = {
                "dataInicial": dt_ini.strftime("%d/%m/%Y"), 
                "dataFinal": dt_fim.strftime("%d/%m/%Y"),
                "codigoOrgao": codigo_orgao, 
                "pagina": pag
            }
            r = requests.get("https://api.portaldatransparencia.gov.br/api-de-dados/contratos", 
                           params=params, headers=get_headers(), timeout=10)
            if r.status_code == 200:
                d = r.json()
                if not d: break
                lista.extend(d)
            else: break
        except: break
    placeholder.empty()
    return lista

# --- INTERFACE ---
st.title("🛡️ Auditoria Gov Federal + IA (V49)")
st.markdown("---")

tab1, tab2 = st.tabs(["🔎 Auditoria CNPJ", "📊 Monitor de Contratos"])

# TAB 1: CNPJ
with tab1:
    st.header("Investigação de Fornecedor")
    col1, col2 = st.columns([3, 1])
    
    with col1:
        cnpj_input = st.text_input("CNPJ:", "05.144.757/0001-72") # Default: Novonor
    with col2:
        btn_check = st.button("Verificar Agora", type="primary")

    if btn_check:
        st.write("⏳ Consultando bases governamentais...")
        
        # Busca Nome (BrasilAPI - Mais estável)
        cnpj_numeros = limpar_string(cnpj_input)
        nome_display = "Razão Social não identificada"
        try:
            r_nome = requests.get(f"https://brasilapi.com.br/api/cnpj/v1/{cnpj_numeros}", timeout=5)
            if r_nome.status_code == 200:
                dados = r_nome.json()
                nome_display = dados.get('razao_social', nome_display)
                st.info(f"🏢 **Empresa:** {nome_display} ({dados.get('descricao_situacao_cadastral', '')})")
            else:
                st.warning("⚠️ Não foi possível obter o nome (API instável), mas a auditoria continua.")
        except:
            st.warning("⚠️ Erro de conexão ao buscar nome.")

        # Busca Sanções
        sancoes = auditar_cnpj_gov(cnpj_input)
        st.divider()
        if sancoes:
            st.error(f"🚨 **ALERTA VERMELHO: {len(sancoes)} REGISTROS ENCONTRADOS**")
            for s in sancoes:
                st.write(f"❌ **{s['_origem']}**: {s.get('motivo', 'Sem detalhes')}")
        else:
            st.success("✅ **FICHA LIMPA:** Nenhuma sanção ativa encontrada no Governo Federal.")

# TAB 2: CONTRATOS
with tab2:
    st.header("Monitoramento de Gastos & IA")
    c_org, c_ia = st.columns([3, 1])
    orgao_selecionado = c_org.selectbox("Órgão Público:", list(ORGAOS_SIAFI.keys()))
    ativar_ia = c_ia.toggle("Ativar IA Gemini", value=True)
    
    if st.button("Buscar Dados"):
        raw_data = buscar_contratos(ORGAOS_SIAFI[orgao_selecionado])
        
        if raw_data:
            rows = []
            for item in raw_data:
                rows.append({
                    "Valor": safe_float(item.get('valorInicialCompra')),
                    "Objeto": item.get('objeto', 'N/A'),
                    "CNPJ": item.get('fornecedor', {}).get('cnpjFormatado', ''),
                    "Risco IA": "⏳",
                    "Status CNPJ": "⚪"
                })
            
            df = pd.DataFrame(rows).sort_values("Valor", ascending=False).head(8)
            
            # --- IA LOOP ---
            if ativar_ia:
                prog_bar = st.progress(0, text="IA Analisando contratos...")
                for i, (index, row) in enumerate(df.iterrows()):
                    # CNPJ Check
                    if row["CNPJ"]:
                        is_bad = auditar_cnpj_gov(row["CNPJ"])
                        df.at[index, "Status CNPJ"] = "🚨 ALERTA" if is_bad else "✅ OK"
                    
                    # IA Check
                    df.at[index, "Risco IA"] = analisar_contrato_ia(row["Objeto"])
                    
                    prog_bar.progress((i + 1) / len(df))
                prog_bar.empty()
            
            # --- MÉTRICAS (KPIs) VOLTARAM AQUI ---
            total_gasto = df["Valor"].sum()
            qtd_contratos = len(df)
            riscos_altos = df[df["Risco IA"].str.contains("ALTO", na=False)].shape[0]

            m1, m2, m3 = st.columns(3)
            m1.metric("💰 Volume Analisado", f"R$ {total_gasto:,.2f}")
            m2.metric("📄 Contratos", f"{qtd_contratos}")
            m3.metric("⚠️ Riscos Altos (IA)", f"{riscos_altos}", delta_color="inverse")
            
            st.divider()

            # Tabela
            def style_risk(v):
                if "ALTO" in str(v): return 'color: red; font-weight: bold; background-color: #ffe6e6'
                if "BAIXO" in str(v): return 'color: green; font-weight: bold'
                return ''
            
            def style_cnpj(v):
                if "ALERTA" in str(v): return 'color: red; font-weight: bold'
                return 'color: green'

            st.dataframe(
                df.style.applymap(style_risk, subset=['Risco IA'])
                        .applymap(style_cnpj, subset=['Status CNPJ'])
                        .format({"Valor": "R$ {:,.2f}"}),
                use_container_width=True
            )
        else:
            st.warning("Nenhum contrato encontrado.")