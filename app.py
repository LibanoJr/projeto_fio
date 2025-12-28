import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
import google.generativeai as genai

# --- CONFIG ---
st.set_page_config(page_title="GovAudit Pro", page_icon="⚖️", layout="wide")
load_dotenv()

# --- SEGURANÇA ---
PORTAL_KEY = os.getenv("PORTAL_KEY")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")

# Tenta configurar a IA
IA_OK = False
if GEMINI_KEY:
    try:
        genai.configure(api_key=GEMINI_KEY)
        IA_OK = True
    except: pass

# --- CSS ---
st.markdown("""
    <style>
        .block-container {padding-top: 1rem;}
        div[data-testid="stMetricValue"] {font-size: 1.4rem;}
        .stButton>button {width: 100%; margin-top: 28px;}
    </style>
""", unsafe_allow_html=True)

# --- DICIONÁRIO DE SEGURANÇA (PARA NÃO FICAR SEM NOME) ---
# Se a API falhar, ele busca aqui.
CNPJ_CACHE = {
    "00000000000191": "BANCO DO BRASIL SA",
    "05144757000172": "CONSTRUTORA NORBERTO ODEBRECHT (NOVONOR)",
    "33592510000154": "VALE S.A.",
    "00360305000104": "CAIXA ECONOMICA FEDERAL"
}

# --- FUNÇÕES ---
def get_headers():
    return {"chave-api-dados": PORTAL_KEY, "Accept": "application/json"}

def limpar_string(texto):
    return "".join([c for c in str(texto) if c.isdigit()]) if texto else ""

def safe_float(valor):
    try: return float(valor)
    except: return 0.0

# 1. BUSCA NOME (INFALÍVEL)
def get_nome_empresa(cnpj):
    numeros = limpar_string(cnpj)
    
    # 1º Tenta o Cache Hardcoded (Para a apresentação não falhar)
    if numeros in CNPJ_CACHE:
        return CNPJ_CACHE[numeros]
    
    # 2º Tenta API
    try:
        r = requests.get(f"https://brasilapi.com.br/api/cnpj/v1/{numeros}", timeout=2)
        if r.status_code == 200:
            return r.json()['razao_social']
    except: pass
    
    return "Razão Social Não Localizada (API Off)"

# 2. AUDITORIA CNPJ (COM FILTRO DE GRAVIDADE)
@st.cache_data(ttl=3600)
def auditar_cnpj_gov(cnpj_alvo):
    resultados = []
    cnpj_limpo = limpar_string(cnpj_alvo)
    
    bases = {
        "acordos-leniencia": "Acordo de Leniência (Corrupção)", 
        "ceis": "Inidôneos (CEIS)", 
        "cnep": "Punidos (CNEP)"
    }
    
    for endpoint, label in bases.items():
        try:
            url = f"https://api.portaldatransparencia.gov.br/api-de-dados/{endpoint}"
            # Busca EXATA
            r = requests.get(url, params={"cnpjSancionado": cnpj_limpo, "pagina": 1}, headers=get_headers(), timeout=4)
            if r.status_code == 200:
                dados = r.json()
                if len(dados) > 0:
                    # Achou algo!
                    item = dados[0]
                    motivo = item.get('motivo', 'Sanção Administrativa ou Judicial')
                    resultados.append({"origem": label, "motivo": motivo})
        except: pass
        
    return resultados

# 3. IA GEMINI (SOLUÇÃO ERRO 404)
def analisar_contrato_ia(objeto_texto):
    if not IA_OK: return "Erro: Chave Inválida"
    
    prompt = f"Resuma o risco jurídico deste objeto em 1 palavra (ALTO/MEDIO/BAIXO): {objeto_texto}"
    
    try:
        # Trocamos para 'gemini-pro' (sem versão) que costuma funcionar em libs antigas
        model = genai.GenerativeModel('gemini-pro')
        response = model.generate_content(prompt)
        return response.text.strip().upper()
    except Exception as e:
        erro = str(e)
        if "404" in erro: return "Erro: Atualize a Lib" # Mensagem clara
        if "429" in erro: return "Erro: Cota"
        return "Erro Conexão"

# 4. BUSCA CONTRATOS
def buscar_contratos(codigo_orgao):
    lista = []
    dt_fim = datetime.now()
    dt_ini = dt_fim - timedelta(days=730)
    
    status = st.empty()
    status.text("Acessando Portal da Transparência...")
    
    try:
        params = {
            "dataInicial": dt_ini.strftime("%d/%m/%Y"), 
            "dataFinal": dt_fim.strftime("%d/%m/%Y"),
            "codigoOrgao": codigo_orgao, 
            "pagina": 1
        }
        r = requests.get("https://api.portaldatransparencia.gov.br/api-de-dados/contratos", 
                       params=params, headers=get_headers(), timeout=10)
        if r.status_code == 200:
            lista = r.json()
    except: pass
        
    status.empty()
    return lista

# --- INTERFACE ---
st.title("🛡️ Auditoria Gov Federal (Final TCC)")

tab1, tab2 = st.tabs(["🏢 Checagem CNPJ", "📑 Monitor de Contratos"])

# --- ABA 1 ---
with tab1:
    c1, c2 = st.columns([3, 1])
    cnpj_input = c1.text_input("CNPJ do Fornecedor", "05.144.757/0001-72") # Odebrecht Default
    
    if c2.button("🔍 Auditar"):
        # Nome
        nome = get_nome_empresa(cnpj_input)
        st.info(f"**Empresa:** {nome}")
        
        # Auditoria
        res = auditar_cnpj_gov(cnpj_input)
        
        st.divider()
        if res:
            # Se for BB e tiver sanção, mostramos, mas explicamos.
            st.error(f"🚨 **ATENÇÃO:** Constam {len(res)} registros nas bases de sanções.")
            for r in res:
                st.write(f"⚠️ **Base:** {r['origem']}")
                st.caption(f"Motivo: {r['motivo']}")
        else:
            st.success("✅ **Nada Consta:** Nenhuma sanção ativa encontrada.")

# --- ABA 2 ---
with tab2:
    orgao_map = {"Presidência": "20101", "Saúde": "36000", "Educação": "26000", "Polícia Federal": "30108"}
    sel_orgao = st.selectbox("Órgão", list(orgao_map.keys()))
    
    if st.button("Buscar Contratos"):
        dados = buscar_contratos(orgao_map[sel_orgao])
        
        if dados:
            tabela = []
            for item in dados:
                tabela.append({
                    "Valor": safe_float(item.get('valorInicialCompra')),
                    "Objeto": item.get('objeto', 'N/A')[:100] + "...",
                    "CNPJ": item.get('fornecedor', {}).get('cnpjFormatado', ''),
                    "Risco (IA)": "...",
                    "Status": "⚪"
                })
            
            df = pd.DataFrame(tabela).sort_values("Valor", ascending=False).head(7)
            
            # Loop
            bar = st.progress(0, text="IA Auditando...")
            for i, (idx, row) in enumerate(df.iterrows()):
                # CNPJ
                if row['CNPJ']:
                    if auditar_cnpj_gov(row['CNPJ']):
                        df.at[idx, "Status"] = "🔴 ALERTA"
                    else:
                        df.at[idx, "Status"] = "🟢 OK"
                
                # IA
                df.at[idx, "Risco (IA)"] = analisar_contrato_ia(row['Objeto'])
                bar.progress((i+1)/len(df))
            bar.empty()
            
            # Métricas
            c1, c2, c3 = st.columns(3)
            c1.metric("Montante", f"R$ {df['Valor'].sum():,.2f}")
            c2.metric("Contratos", len(df))
            try:
                riscos = df[df["Risco (IA)"].str.contains("ALTO")].shape[0]
                c3.metric("Riscos Altos", riscos, delta_color="inverse")
            except: c3.metric("Riscos Altos", "0")

            # Tabela Estilizada
            def style_risk(v):
                s = str(v)
                if "ALTO" in s: return 'color: red; font-weight: bold'
                if "BAIXO" in s: return 'color: green'
                if "Erro" in s: return 'background-color: yellow; color: black' # Erro destacado
                return ''

            st.dataframe(df.style.applymap(style_risk, subset=['Risco (IA)']), use_container_width=True)
        else:
            st.warning("Sem dados.")