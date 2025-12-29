import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import time
import os
from dotenv import load_dotenv
import google.generativeai as genai
from google.api_core import exceptions

# --- 1. CONFIGURAÇÃO ---
load_dotenv()

def get_secret(key_name):
    val = os.getenv(key_name)
    if val: return val
    if key_name in st.secrets:
        return st.secrets[key_name]
    return None

PORTAL_KEY = get_secret("PORTAL_KEY")
GEMINI_KEY = get_secret("GEMINI_API_KEY")

IA_ATIVA = False
if GEMINI_KEY:
    try:
        genai.configure(api_key=GEMINI_KEY)
        IA_ATIVA = True
    except: pass

st.set_page_config(page_title="GovAudit Pro", page_icon="⚖️", layout="wide")

# --- DEBUG: LISTAR MODELOS DISPONÍVEIS (IMPORTANTE) ---
with st.sidebar:
    st.header("🔧 Diagnóstico IA")
    if IA_ATIVA:
        st.success(f"Lib Google: {genai.__version__}")
        st.write("Modelos disponíveis para sua chave:")
        try:
            # Isso vai listar o que realmente funciona
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    st.code(m.name)
        except Exception as e:
            st.error(f"Erro ao listar modelos: {e}")
    else:
        st.error("Chave API não encontrada.")

# --- CSS ---
st.markdown("""
    <style>
        .block-container {padding-top: 2rem;}
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        .stButton > button {width: 100%; margin-top: 29px;}
    </style>
""", unsafe_allow_html=True)

# --- FUNÇÕES ---
def formatar_moeda_br(valor):
    if not valor: return "R$ 0,00"
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def formatar_data_br(data_iso):
    if not data_iso: return ""
    try: return datetime.strptime(data_iso, "%Y-%m-%d").strftime("%d/%m/%Y")
    except: return data_iso

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
    if not PORTAL_KEY: return [] 
    
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
                    match = False
                    cnpj_item = ""
                    try: 
                        sancionado = item.get('sancionado', {})
                        cnpj_item = sancionado.get('codigoFormatado') or item.get('pessoa', {}).get('cnpjFormatado')
                    except: pass
                    if cnpj_item and limpar_string(cnpj_item)[:8] == raiz_alvo: match = True
                    elif nome_base == "Acordo Leniência" and not cnpj_item: match = True
                    if match:
                        item['_origem'] = nome_base
                        resultados.append(item)
        except: pass
    return resultados

def checar_risco_simples(cnpj):
    return True if len(auditar_cnpj_detalhado(cnpj)) > 0 else False

# --- FUNÇÃO IA CORRIGIDA (SEM FALLBACK) ---
def analisar_objeto_ia(objeto_texto):
    if not IA_ATIVA: return "SEM CHAVE"
    if not objeto_texto: return "Vazio"
    
    try:
        # Tenta DIRETAMENTE o modelo flash 1.5
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"Classifique o risco (ALTO/MEDIO/BAIXO) do objeto: '{objeto_texto}'"
        response = model.generate_content(prompt)
        return response.text.strip().upper()
        
    except exceptions.ResourceExhausted:
        return "COTA EXCEDIDA (429)"
    except Exception as e:
        # Mostra o erro exato do Flash, sem tentar esconder
        return f"ERRO FLASH: {str(e)}"

# --- BUSCA E INTERFACE ---
ORGAOS_SIAFI = {"Planalto": "20101", "Saúde": "36000", "Educação": "26000", "Justiça": "30000"}

def buscar_contratos(codigo_orgao):
    if not PORTAL_KEY: return []
    lista = []
    dt_fim = datetime.now()
    dt_ini = dt_fim - timedelta(days=730)
    bar = st.progress(0, text="Buscando...")
    for i in range(1, 4):
        try:
            params = {"dataInicial": dt_ini.strftime("%d/%m/%Y"), "dataFinal": dt_fim.strftime("%d/%m/%Y"), "codigoOrgao": codigo_orgao, "pagina": i}
            r = requests.get("https://api.portaldatransparencia.gov.br/api-de-dados/contratos", params=params, headers=get_headers(), timeout=10)
            if r.status_code == 200:
                dados = r.json()
                if not dados: break
                lista.extend(dados)
            else: break
        except: break
        bar.progress(i*33)
    bar.empty()
    return lista

st.title("🛡️ Auditoria Gov Federal")
aba1, aba2 = st.tabs(["CNPJ", "Contratos"])

with aba1:
    c = st.text_input("CNPJ:", "05.144.757/0001-72")
    if st.button("Verificar"):
        res = auditar_cnpj_detalhado(c)
        if res: 
            st.error(f"{len(res)} SANÇÕES")
            for r in res: st.write(f"{r['_origem']}")
        else: st.success("LIMPO")

with aba2:
    c1, c2 = st.columns([3,1])
    org = c1.selectbox("Órgão", list(ORGAOS_SIAFI.keys()))
    use_ia = c2.toggle("IA", True)
    if st.button("Buscar"):
        raw = buscar_contratos(ORGAOS_SIAFI[org])
        if raw:
            raw.sort(key=lambda x: safe_float(x.get('valorInicialCompra')), reverse=True)
            top = raw[:8] # Reduzi pra 8 pra ser mais rápido
            tab = []
            
            prog = st.progress(0)
            for i, item in enumerate(top):
                val = safe_float(item.get('valorInicialCompra'))
                obj = item.get('objeto', '')[:100]
                cnpj = item.get('fornecedor', {}).get('cnpjFormatado', '')
                
                risco = "OFF"
                if use_ia:
                    risco = analisar_objeto_ia(obj)
                    time.sleep(1) # Delay vital
                
                tab.append({
                    "Valor": formatar_moeda_br(val),
                    "Risco IA": risco,
                    "Objeto": obj
                })
                prog.progress((i+1)/len(top))
            prog.empty()
            
            df = pd.DataFrame(tab)
            def cor(v):
                if "ALTO" in str(v): return 'color: red'
                if "ERRO" in str(v): return 'color: purple'
                return ''
            st.dataframe(df.style.applymap(cor, subset=['Risco IA']), use_container_width=True)
        else: st.warning("Sem dados")