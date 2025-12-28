import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import time
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
        .block-container {padding-top: 1rem;}
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        .stDataFrame {font-size: 0.9rem;}
        div[data-testid="stMetricValue"] {font-size: 1.1rem;}
    </style>
""", unsafe_allow_html=True)

# --- DADOS ---
ORGAOS_SIAFI = {
    "Secretaria-Geral Presidência (Planalto)": "20101",
    "Ministério da Saúde": "36000",
    "Ministério da Educação": "26000",
    "Polícia Federal": "30108",
    "Comando do Exército": "52121"
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
                    # Verifica correspondência frouxa (raiz do CNPJ)
                    c = item.get('sancionado', {}).get('codigoFormatado') or item.get('pessoa', {}).get('cnpjFormatado')
                    if c and limpar_string(c)[:8] == raiz:
                        item['_origem'] = label
                        resultados.append(item)
        except: pass
    return resultados

# --- IA GEMINI (V47 - Debug Real) ---
def analisar_contrato_ia(objeto_texto):
    if not GEMINI_KEY: return "⚠️ S/ Chave"
    
    prompt = f"""
    Analise este objeto de contrato público. Identifique riscos de imprecisão ou sobrepreço potencial.
    Objeto: "{objeto_texto}"
    Responda APENAS: 'ALTO RISCO', 'MÉDIO RISCO' ou 'BAIXO RISCO'.
    """
    
    # Lista de modelos por prioridade
    modelos = ['gemini-1.5-flash', 'gemini-pro']
    last_error = ""

    for modelo in modelos:
        try:
            model = genai.GenerativeModel(modelo)
            response = model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            last_error = str(e)
            continue
            
    # Se chegou aqui, falhou tudo. Retorna o erro real para debug
    if "404" in last_error: return "Erro: Modelo 404 (Update pip)"
    if "403" in last_error: return "Erro: Chave Inválida"
    if "429" in last_error: return "Erro: Limite Excedido"
    return f"Erro: {last_error[:15]}..."

# --- BUSCA CONTRATOS ---
def buscar_contratos(codigo_orgao):
    lista = []
    dt_fim = datetime.now()
    dt_ini = dt_fim - timedelta(days=730) # 2 anos
    
    # Barra de progresso visual
    bar = st.progress(0, text="Conectando ao Portal...")
    
    for i, pag in enumerate(range(1, 4)): # Busca até 3 páginas
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
    bar.empty()
    return lista

# --- INTERFACE ---
st.title("🛡️ Auditoria Gov Federal + IA (V47 Final)")
st.markdown("---")

tab1, tab2 = st.tabs(["🔎 Auditoria CNPJ", "📊 Monitor de Contratos"])

# TAB 1: CNPJ
with tab1:
    st.header("Investigação de Fornecedor")
    col1, col2 = st.columns([3, 1])
    cnpj_input = col1.text_input("Digite o CNPJ:", "05.144.757/0001-72")
    if col2.button("Verificar Agora", type="primary"):
        st.write("⏳ Consultando bases governamentais...")
        
        # Nome da Empresa
        try:
            r = requests.get(f"https://minhareceita.org/{limpar_string(cnpj_input)}", timeout=5)
            nome = r.json().get('razao_social', 'Nome Indisponível')
            st.info(f"🏢 **{nome}**")
        except: st.warning("⚠️ MinhaReceita indisponível, seguindo auditoria...")

        # Sanções
        sancoes = auditar_cnpj_gov(cnpj_input)
        st.divider()
        if sancoes:
            st.error(f"🚨 **ALERTA: {len(sancoes)} OCORRÊNCIAS ENCONTRADAS**")
            for s in sancoes:
                st.write(f"❌ **{s['_origem']}**: {s.get('motivo', 'Sem detalhes')}")
        else:
            st.success("✅ **Ficha Limpa:** Nenhuma sanção ativa encontrada.")

# TAB 2: CONTRATOS + IA
with tab2:
    st.header("Monitoramento de Gastos & IA")
    c_org, c_ia = st.columns([3, 1])
    orgao_selecionado = c_org.selectbox("Órgão Público:", list(ORGAOS_SIAFI.keys()))
    ativar_ia = c_ia.toggle("Ativar IA Gemini", value=True)
    
    if st.button("Buscar Dados"):
        raw_data = buscar_contratos(ORGAOS_SIAFI[orgao_selecionado])
        
        if raw_data:
            # Prepara Tabela
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
            
            # Processamento
            if ativar_ia:
                prog_bar = st.progress(0, text="IA Analisando contratos...")
                for idx, row in df.iterrows():
                    # 1. Checa CNPJ
                    if row["CNPJ"]:
                        is_bad = auditar_cnpj_gov(row["CNPJ"])
                        df.at[idx, "Status CNPJ"] = "🚨 ALERTA" if is_bad else "✅ OK"
                    
                    # 2. Checa IA
                    df.at[idx, "Risco IA"] = analisar_contrato_ia(row["Objeto"])
                    prog_bar.progress((idx + 1) / len(df))
                prog_bar.empty()
            
            # Estilos
            def style_risk(v):
                if "ALTO" in str(v): return 'color: red; font-weight: bold; background-color: #ffe6e6'
                if "BAIXO" in str(v): return 'color: green; font-weight: bold'
                if "Erro" in str(v): return 'color: orange'
                return ''
                
            st.dataframe(
                df.style.applymap(style_risk, subset=['Risco IA'])
                        .format({"Valor": "R$ {:,.2f}"}),
                use_container_width=True
            )
        else:
            st.warning("Nenhum contrato encontrado no período.")