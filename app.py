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

# --- 2. CSS ---
st.markdown("""
    <style>
        .block-container {padding-top: 2rem;}
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        .stButton > button {width: 100%; margin-top: 29px;}
    </style>
""", unsafe_allow_html=True)

# --- 3. DADOS ---
ORGAOS_SIAFI = {
    "Secretaria-Geral Presidência (Planalto)": "20101",
    "Ministério da Saúde": "36000",
    "Ministério da Educação": "26000",
    "DNIT (Transportes)": "39252",
    "Polícia Federal": "30108",
    "Comando do Exército": "52121",
    "Ministério da Justiça": "30000"
}

# --- 4. FUNÇÕES ---
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
    res = auditar_cnpj_detalhado(cnpj)
    return True if len(res) > 0 else False

# --- IA ---
# --- Função de IA (MODO DEBUG E SEGURANÇA) ---
def analisar_objeto_ia(objeto_texto):
    if not IA_ATIVA: return "IA NÃO CONFIGURADA"
    if not objeto_texto: return "Texto Vazio"
    
    try:
        # Usando o modelo mais compatível e estável do Google (evita erro 404 e erro de cota baixa)
        model = genai.GenerativeModel('gemini-pro')
        
        prompt = f"""Analise o objeto deste contrato público e responda APENAS com uma destas palavras: 'ALTO', 'MÉDIO' ou 'BAIXO'.
        Classifique como ALTO se for vago, genérico (ex: 'aquisição de materiais') ou suspeito.
        Objeto: '{objeto_texto}'"""
        
        # Tenta gerar a resposta
        response = model.generate_content(prompt)
        return response.text.strip().upper()
    
    except exceptions.ResourceExhausted:
        return "COTA DIÁRIA EXCEDIDA"  # Agora sabemos se foi o limite
    except Exception as e:
        # ISSO VAI MOSTRAR O ERRO REAL NA TABELA PARA GENTE SABER O QUE É
        return f"ERRO: {str(e)}"
    
# --- BUSCA ---
def buscar_contratos(codigo_orgao):
    if not PORTAL_KEY: return []
    lista = []
    dt_fim = datetime.now()
    dt_ini = dt_fim - timedelta(days=730)
    
    bar = st.progress(0, text="Conectando...")
    for i, pag in enumerate(range(1, 4)):
        bar.progress((i+1)*33)
        try:
            params = {"dataInicial": dt_ini.strftime("%d/%m/%Y"), "dataFinal": dt_fim.strftime("%d/%m/%Y"), "codigoOrgao": codigo_orgao, "pagina": pag}
            r = requests.get("https://api.portaldatransparencia.gov.br/api-de-dados/contratos", params=params, headers=get_headers(), timeout=10)
            if r.status_code == 200:
                dados = r.json()
                if not dados: break
                lista.extend(dados)
            else: break
        except: break
    bar.empty()
    return lista

# --- INTERFACE ---
st.title("🛡️ Auditoria Gov Federal + IA")

aba1, aba2 = st.tabs(["🕵️ Checagem CNPJ", "📊 Auditoria de Contratos"])

with aba1:
    cnpj_input = st.text_input("CNPJ Alvo:", value="05.144.757/0001-72")
    if st.button("Verificar"):
        sancoes = auditar_cnpj_detalhado(cnpj_input)
        if sancoes:
            st.error(f"🚨 {len(sancoes)} SANÇÕES ENCONTRADAS")
            for s in sancoes: st.write(f"❌ {s['_origem']}")
        else: st.success("✅ NADA CONSTA")

with aba2:
    c1, c2 = st.columns([3,1])
    orgao = c1.selectbox("Órgão:", list(ORGAOS_SIAFI.keys()))
    usar_ia = c2.toggle("IA", value=True)
    
    if st.button("Buscar"):
        raw = buscar_contratos(ORGAOS_SIAFI[orgao])
        if raw:
            df = pd.DataFrame(raw)
            df['Valor'] = df.apply(lambda x: safe_float(x.get('valorInicialCompra') or x.get('valorFinalCompra')), axis=1)
            df = df.sort_values("Valor", ascending=False).head(10).reset_index(drop=True) # Só Top 10
            
            # Colunas novas
            df['Risco IA'] = "..."
            df['Status CNPJ'] = "..."
            
            bar = st.progress(0)
            for i in range(len(df)):
                # CNPJ
                cnpj = df.loc[i, 'fornecedor'].get('cnpjFormatado', '') if df.loc[i, 'fornecedor'] else ''
                if cnpj:
                    if checar_risco_simples(cnpj): df.at[i, 'Status CNPJ'] = "🚨 ALERTA"
                    else: df.at[i, 'Status CNPJ'] = "🟢 OK"
                
                # IA
                if usar_ia:
                    obj = df.loc[i, 'objeto'] if df.loc[i, 'objeto'] else ''
                    df.at[i, 'Risco IA'] = analisar_objeto_ia(obj)
                    time.sleep(1) # Pausa pra não travar
                
                bar.progress((i+1)/len(df))
            bar.empty()
            
            # Exibição
            st.dataframe(df[['dataAssinatura', 'Valor', 'objeto', 'Risco IA', 'Status CNPJ']])
        else: st.warning("Sem dados.")