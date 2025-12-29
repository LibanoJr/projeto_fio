import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import time
import os
import google.generativeai as genai
from google.api_core import exceptions
from dotenv import load_dotenv

# --- 1. CONFIGURAÇÃO SEGURA (SECRETS) ---
load_dotenv()

def get_secret(key_name):
    # 1. Tenta pegar do .env (Local)
    val = os.getenv(key_name)
    if val: return val
    # 2. Tenta pegar dos Secrets do Streamlit (Cloud)
    if hasattr(st, "secrets") and key_name in st.secrets:
        return st.secrets[key_name]
    return None

PORTAL_KEY = get_secret("PORTAL_KEY")
GEMINI_KEY = get_secret("GEMINI_API_KEY")

IA_ATIVA = False
if GEMINI_KEY:
    try:
        genai.configure(api_key=GEMINI_KEY)
        IA_ATIVA = True
    except Exception as e:
        print(f"Erro config IA: {e}")

st.set_page_config(page_title="GovAudit Pro", page_icon="⚖️", layout="wide")

# --- 2. CSS VISUAL ---
st.markdown("""
    <style>
        .block-container {padding-top: 2rem;}
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        .stButton > button {width: 100%; margin-top: 29px;}
        [data-testid="stMetricValue"] {font-size: 1.5rem;}
    </style>
""", unsafe_allow_html=True)

# --- 3. FUNÇÕES AUXILIARES ---
def formatar_moeda_br(valor):
    if not valor: return "R$ 0,00"
    texto = f"R$ {valor:,.2f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")

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

# --- 4. CONSULTA DE NOME (BRASIL API) ---
@st.cache_data(ttl=86400)
def buscar_dados_receita(cnpj):
    cnpj_limpo = limpar_string(cnpj)
    if not cnpj_limpo: return None, None
    try:
        url = f"https://brasilapi.com.br/api/cnpj/v1/{cnpj_limpo}"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            dados = resp.json()
            razao = dados.get('razao_social', '')
            fantasia = dados.get('nome_fantasia', '')
            return razao, fantasia
    except: pass
    return None, None

# --- 5. AUDITORIA DE CNPJ ---
@st.cache_data(ttl=3600)
def auditar_cnpj_detalhado(cnpj_alvo):
    resultados = []
    
    # Busca Identificação na Receita
    razao, fantasia = buscar_dados_receita(cnpj_alvo)
    nome_exibicao = razao if razao else "Empresa não identificada"
    if fantasia: nome_exibicao += f" ({fantasia})"
    
    if not PORTAL_KEY: return [], nome_exibicao
    
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
        
    return resultados, nome_exibicao

def checar_risco_simples(cnpj):
    res, _ = auditar_cnpj_detalhado(cnpj)
    return True if len(res) > 0 else False

# --- 6. FUNÇÃO IA (ANTI-BLOQUEIO) ---
def analisar_objeto_ia(objeto_texto):
    if not IA_ATIVA: return "IA OFF"
    if not objeto_texto: return "Vazio"
    
    # Loop de tentativas
    for tentativa in range(3):
        try:
            model = genai.GenerativeModel('gemini-2.0-flash')
            prompt = f"""Responda com uma única palavra: 'ALTO', 'MÉDIO' ou 'BAIXO'.
            Qual o risco de corrupção ou irregularidade neste objeto?
            Objeto: '{objeto_texto}'"""
            
            response = model.generate_content(prompt)
            return response.text.strip().upper()

        except exceptions.ResourceExhausted:
            # Se bater no limite, espera 5s e tenta de novo
            time.sleep(5) 
            continue
        except Exception:
            return "ERRO"
            
    return "DELAY" # Retorna se falhar após tentativas

# --- 7. BUSCA CONTRATOS ---
ORGAOS_SIAFI = {
    "Planalto": "20101", "Saúde": "36000", "Educação": "26000", 
    "DNIT": "39252", "Polícia Federal": "30108", "Justiça": "30000"
}

def buscar_contratos(codigo_orgao):
    if not PORTAL_KEY: return []
    lista = []
    dt_fim = datetime.now()
    dt_ini = dt_fim - timedelta(days=730)
    
    bar = st.progress(0, text="Acessando bases...")
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

# --- 8. INTERFACE PRINCIPAL ---
st.title("🛡️ Auditoria Gov Federal + IA 2.0")

aba1, aba2 = st.tabs(["🕵️ Checagem CNPJ", "📊 Auditoria Contratual"])

with aba1:
    st.header("Antecedentes do Fornecedor")
    col1, col2 = st.columns([4, 1])
    cnpj_input = col1.text_input("CNPJ Alvo:", value="62.547.210/0001-51")
    
    if col2.button("Verificar", type="primary"):
        with st.spinner("Consultando Receita e Sanções..."):
            sancoes, nome_empresa = auditar_cnpj_detalhado(cnpj_input)
        
        st.divider()
        st.subheader(f"🏢 {nome_empresa}")
        
        if sancoes:
            st.error(f"🚨 ALERTA: {len(sancoes)} SANÇÕES")
            for s in sancoes: 
                dt = s.get('dataInicioSancao', 'Data N/A')
                st.write(f"❌ **{s['_origem']}** ({dt}): {s.get('motivo', 'Sem detalhes')}")
        else:
            st.success("✅ NADA CONSTA (CEIS/CNEP/LENIÊNCIA)")

with aba2:
    st.header("Análise de Riscos")
    c1, c2 = st.columns([3,1])
    orgao = c1.selectbox("Órgão:", list(ORGAOS_SIAFI.keys()))
    usar_ia = c2.toggle("Ativar IA", value=True)
    
    if st.button("Auditar Contratos"):
        raw = buscar_contratos(ORGAOS_SIAFI[orgao])
        if raw:
            raw.sort(key=lambda x: safe_float(x.get('valorInicialCompra') or x.get('valorFinalCompra')), reverse=True)
            top_10 = raw[:10]
            
            tabela = []
            total_val = 0
            
            bar = st.progress(0, text="IA Analisando (Lento para evitar bloqueio)...")
            for i, item in enumerate(top_10):
                val = safe_float(item.get('valorInicialCompra') or item.get('valorFinalCompra'))
                total_val += val
                
                cnpj = item.get('fornecedor', {}).get('cnpjFormatado', '')
                obj = item.get('objeto', '')[:120]
                
                risco_ia = "..."
                if usar_ia:
                    risco_ia = analisar_objeto_ia(obj)
                    # PAUSA DE 5 SEGUNDOS (O segredo para não dar erro)
                    time.sleep(5) 
                
                status_cnpj = "🟢 OK"
                if cnpj and checar_risco_simples(cnpj): status_cnpj = "🚨 ALERTA"
                
                tabela.append({
                    "Data": formatar_data_br(item.get('dataAssinatura')),
                    "Valor": formatar_moeda_br(val),
                    "Objeto": obj,
                    "CNPJ": cnpj,
                    "Risco IA": risco_ia,
                    "Status CNPJ": status_cnpj
                })
                bar.progress((i+1)/len(top_10))
            bar.empty()
            
            # Cards
            df = pd.DataFrame(tabela)
            m1, m2, m3 = st.columns(3)
            m1.metric("Volume Analisado", formatar_moeda_br(total_val))
            m2.metric("Contratos", len(raw))
            try:
                riscos = len(df[df['Risco IA'].str.contains("ALTO")])
                m3.metric("Riscos Altos", riscos, delta_color="inverse")
            except: m3.metric("Riscos Altos", 0)
            
            # Cores
            def style_risk(v):
                if "ALTO" in str(v): return 'color: red; font-weight: bold'
                if "MÉDIO" in str(v): return 'color: orange'
                if "BAIXO" in str(v): return 'color: green'
                return ''
            
            def style_cnpj(v):
                if "ALERTA" in str(v): return 'color: red; font-weight: bold'
                return 'color: green'

            st.dataframe(
                df.style.applymap(style_risk, subset=['Risco IA'])
                        .applymap(style_cnpj, subset=['Status CNPJ']),
                use_container_width=True, hide_index=True
            )
            
        else: st.warning("Sem dados recentes.")