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

# --- CSS PARA DEIXAR BONITO ---
st.markdown("""
    <style>
        .block-container {padding-top: 2rem;}
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        .stButton > button {width: 100%; margin-top: 29px;}
        [data-testid="stMetricValue"] {font-size: 1.5rem;}
    </style>
""", unsafe_allow_html=True)

# --- FUNÇÕES DE FORMATAÇÃO ---
def formatar_moeda_br(valor):
    if not valor: return "R$ 0,00"
    texto = f"R$ {valor:,.2f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")

def formatar_data_br(data_iso):
    if not data_iso: return ""
    try:
        data_obj = datetime.strptime(data_iso, "%Y-%m-%d")
        return data_obj.strftime("%d/%m/%Y")
    except: return data_iso

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

# --- FUNÇÕES CORE ---
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

# --- FUNÇÃO IA (COM VISUALIZAÇÃO DE ERRO REAL) ---
def analisar_objeto_ia(objeto_texto):
    if not IA_ATIVA: return "SEM CHAVE"
    if not objeto_texto: return "Vazio"
    
    try:
        # Tenta o modelo rápido
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"Analise o objeto deste contrato público e responda APENAS 'ALTO', 'MÉDIO' ou 'BAIXO'. Objeto: '{objeto_texto}'"
        response = model.generate_content(prompt)
        return response.text.strip().upper()
    except exceptions.ResourceExhausted:
        return "COTA EXCEDIDA"
    except Exception as e_flash:
        # Se falhar, tenta o antigo e mostra o erro se falhar de novo
        try:
            model = genai.GenerativeModel('gemini-pro')
            prompt = f"Analise o risco (ALTO/MEDIO/BAIXO) do objeto: '{objeto_texto}'"
            response = model.generate_content(prompt)
            return response.text.strip().upper()
        except Exception as e_pro:
            # MOSTRA O ERRO REAL NA TABELA
            return f"ERRO: {str(e_pro)[:20]}..."

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
    if st.button("Verificar CNPJ"):
        sancoes = auditar_cnpj_detalhado(cnpj_input)
        if sancoes:
            st.error(f"🚨 {len(sancoes)} RESTRIÇÕES ENCONTRADAS")
            for s in sancoes: st.write(f"❌ {s['_origem']}")
        else: st.success("✅ NADA CONSTA - Fornecedor Limpo")

with aba2:
    c1, c2 = st.columns([3,1])
    orgao = c1.selectbox("Órgão:", list(ORGAOS_SIAFI.keys()))
    usar_ia = c2.toggle("IA", value=True)
    
    if st.button("Auditar Contratos"):
        raw = buscar_contratos(ORGAOS_SIAFI[orgao])
        if raw:
            # 1. Calcula Totais
            total_dinheiro = 0.0
            tabela = []
            
            # Ordena e pega Top 10 para tabela
            raw.sort(key=lambda x: safe_float(x.get('valorInicialCompra') or x.get('valorFinalCompra')), reverse=True)
            top_10 = raw[:10]
            
            # Processamento
            bar = st.progress(0, text="Analisando contratos...")
            
            for i, item in enumerate(top_10):
                val = safe_float(item.get('valorInicialCompra') or item.get('valorFinalCompra'))
                total_dinheiro += val # Soma (nota: aqui soma só o top 10 pra ser rápido, ideal seria somar tudo antes)
                
                cnpj = item.get('fornecedor', {}).get('cnpjFormatado', '')
                obj = item.get('objeto', '')[:150]
                
                # Checagens
                status_cnpj = "🟢 OK"
                if cnpj and checar_risco_simples(cnpj): 
                    status_cnpj = "🚨 ALERTA"
                
                risco_ia = "⚪ N/A"
                if usar_ia:
                    risco_ia = analisar_objeto_ia(obj)
                    time.sleep(1) # Delay anti-bloqueio
                
                tabela.append({
                    "Data": formatar_data_br(item.get('dataAssinatura', '')),
                    "Valor": formatar_moeda_br(val),
                    "Objeto": obj,
                    "CNPJ": cnpj,
                    "Risco IA": risco_ia,
                    "Status CNPJ": status_cnpj
                })
                bar.progress((i+1)/len(top_10))
            bar.empty()
            
            # 2. Exibe Métricas (VOLTOU!)
            df = pd.DataFrame(tabela)
            k1, k2, k3 = st.columns(3)
            k1.metric("Valor Analisado (Top 10)", formatar_moeda_br(sum([safe_float(x.get('valorInicialCompra')) for x in top_10])))
            k2.metric("Contratos Listados", len(raw))
            # Conta riscos altos
            qtd_risco = len(df[df['Risco IA'].astype(str).str.contains("ALTO")])
            k3.metric("Riscos Altos Detectados", qtd_risco, delta_color="inverse")
            
            # 3. Exibe Tabela Colorida
            def style_risk(v):
                if "ALTO" in str(v): return 'color: red; font-weight: bold'
                if "MÉDIO" in str(v): return 'color: orange; font-weight: bold'
                if "BAIXO" in str(v): return 'color: green'
                return ''
                
            def style_cnpj(v):
                if "ALERTA" in str(v): return 'background-color: #ffcccc; color: red; font-weight: bold'
                if "OK" in str(v): return 'color: green; font-weight: bold'
                return ''

            st.dataframe(
                df.style.applymap(style_risk, subset=['Risco IA'])
                        .applymap(style_cnpj, subset=['Status CNPJ']),
                use_container_width=True, hide_index=True
            )
            
        else: st.warning("Nenhum contrato encontrado no período.")