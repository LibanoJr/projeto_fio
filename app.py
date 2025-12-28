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

# Configuração da IA
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)

# --- CSS OTIMIZADO ---
st.markdown("""
    <style>
        .block-container {padding-top: 1.5rem;}
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        .stButton>button {width: 100%; margin-top: 29px;} /* Alinha botão com input */
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

# --- AUDITORIA CNPJ ---
@st.cache_data(ttl=3600)
def auditar_cnpj_gov(cnpj_alvo):
    resultados = [] 
    cnpj_limpo = limpar_string(cnpj_alvo)
    raiz = cnpj_limpo[:8]
    bases = {"acordos-leniencia": "Leniência", "ceis": "Inidôneos", "cnep": "Punidos"}
    
    for endpoint, label in bases.items():
        try:
            url = f"https://api.portaldatransparencia.gov.br/api-de-dados/{endpoint}"
            r = requests.get(url, params={"cnpjSancionado": cnpj_limpo, "pagina": 1}, headers=get_headers(), timeout=4)
            if r.status_code == 200:
                for item in r.json():
                    c = item.get('sancionado', {}).get('codigoFormatado') or item.get('pessoa', {}).get('cnpjFormatado')
                    if c and limpar_string(c)[:8] == raiz:
                        item['_origem'] = label
                        resultados.append(item)
        except: pass
    return resultados

# --- IA GEMINI (V48 - Retry Strategy) ---
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
st.title("🛡️ Auditoria Gov Federal + IA (V48)")
st.markdown("---")

tab1, tab2 = st.tabs(["🔎 Auditoria CNPJ", "📊 Monitor de Contratos"])

# TAB 1: CNPJ
with tab1:
    st.header("Investigação de Fornecedor")
    col1, col2 = st.columns([3, 1])
    
    with col1:
        cnpj_input = st.text_input("CNPJ:", "05.144.757/0001-72")
    with col2:
        # Botão alinhado pelo CSS
        btn_check = st.button("Verificar Agora", type="primary")

    if btn_check:
        st.write("⏳ Consultando bases governamentais...")
        
        # Nome da Empresa (Soft Fail)
        nome_display = "Nome não obtido (API Externa Instável)"
        try:
            r = requests.get(f"https://minhareceita.org/{limpar_string(cnpj_input)}", timeout=3)
            if r.status_code == 200:
                nome_display = r.json().get('razao_social', nome_display)
        except: pass
        
        st.info(f"🏢 **Fornecedor:** {nome_display}")

        # Sanções
        sancoes = auditar_cnpj_gov(cnpj_input)
        st.divider()
        if sancoes:
            st.error(f"🚨 **ALERTA VERMELHO: {len(sancoes)} RESTRIÇÕES**")
            for s in sancoes:
                st.write(f"❌ **{s['_origem']}**: {s.get('motivo', 'Sem detalhes')}")
        else:
            st.success("✅ **FICHA LIMPA:** Nenhuma sanção ativa encontrada no Governo Federal.")

# TAB 2: CONTRATOS + IA
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
            
            # Pega Top 8 maiores valores
            df = pd.DataFrame(rows).sort_values("Valor", ascending=False).head(8)
            
            # --- CORREÇÃO DO CRASH DA BARRA DE PROGRESSO ---
            if ativar_ia:
                prog_bar = st.progress(0, text="IA Analisando contratos...")
                
                # Usamos enumerate para garantir contador de 0 a N correto
                for i, (index, row) in enumerate(df.iterrows()):
                    
                    # 1. Checa CNPJ
                    if row["CNPJ"]:
                        is_bad = auditar_cnpj_gov(row["CNPJ"])
                        df.at[index, "Status CNPJ"] = "🚨 ALERTA" if is_bad else "✅ OK"
                    
                    # 2. Checa IA
                    df.at[index, "Risco IA"] = analisar_contrato_ia(row["Objeto"])
                    
                    # Atualiza barra (Matemática segura: i+1 dividido pelo total)
                    prog_bar.progress((i + 1) / len(df))
                    
                prog_bar.empty()
            
            # Estilos
            def style_risk(v):
                if "ALTO" in str(v): return 'color: red; font-weight: bold; background-color: #ffe6e6'
                if "BAIXO" in str(v): return 'color: green; font-weight: bold'
                if "Erro" in str(v): return 'color: orange'
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
            st.warning("Nenhum contrato encontrado neste período.")