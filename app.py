import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import time
import os
from dotenv import load_dotenv
import google.generativeai as genai
from google.api_core import exceptions

# --- 1. CONFIGURAÇÃO E SEGURANÇA ---
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

# --- 2. CSS VISUAL ---
st.markdown("""
    <style>
        .block-container {padding-top: 2rem;}
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        .stButton > button {width: 100%; margin-top: 29px;}
    </style>
""", unsafe_allow_html=True)

# --- 3. FUNÇÕES DE FORMATAÇÃO (NOVO) ---
def formatar_moeda_br(valor):
    if not valor: return "R$ 0,00"
    # Formata como moeda brasileira (inverte ponto e virgula)
    texto = f"R$ {valor:,.2f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")

def formatar_data_br(data_iso):
    if not data_iso: return ""
    try:
        # Tenta converter de AAAA-MM-DD para DD/MM/AAAA
        data_obj = datetime.strptime(data_iso, "%Y-%m-%d")
        return data_obj.strftime("%d/%m/%Y")
    except:
        return data_iso # Se falhar, retorna como veio

# --- 4. DADOS AUXILIARES ---
ORGAOS_SIAFI = {
    "Secretaria-Geral Presidência (Planalto)": "20101",
    "Ministério da Saúde": "36000",
    "Ministério da Educação": "26000",
    "DNIT (Transportes)": "39252",
    "Polícia Federal": "30108",
    "Comando do Exército": "52121",
    "Ministério da Justiça": "30000"
}

# --- 5. FUNÇÕES DO SISTEMA ---
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

# --- Função de IA (ATUALIZADA) ---
def analisar_objeto_ia(objeto_texto):
    if not IA_ATIVA: return "IA Off (Sem Chave)"
    if not objeto_texto: return "Vazio"
    
    try:
        # Tenta o modelo rápido e moderno
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"Analise o objeto deste contrato público e responda APENAS 'ALTO', 'MÉDIO' ou 'BAIXO'. Objeto: '{objeto_texto}'"
        response = model.generate_content(prompt)
        return response.text.strip().upper()
    except exceptions.ResourceExhausted:
        return "COTA EXCEDIDA"
    except Exception as e:
        # Se der erro no Flash, tenta o Pro (Fallback)
        try:
            model = genai.GenerativeModel('gemini-pro')
            prompt = f"Analise risco (ALTO/MEDIO/BAIXO) do objeto: '{objeto_texto}'"
            response = model.generate_content(prompt)
            return response.text.strip().upper()
        except:
            return f"ERRO IA" # Simplificado para não quebrar a tabela

# --- Busca de Contratos ---
def buscar_contratos(codigo_orgao):
    if not PORTAL_KEY: return []
    lista = []
    dt_fim = datetime.now()
    dt_ini = dt_fim - timedelta(days=730)
    
    bar = st.progress(0, text="Conectando ao Portal...")
    for i, pag in enumerate(range(1, 4)):
        bar.progress((i+1)*33)
        try:
            params = {
                "dataInicial": dt_ini.strftime("%d/%m/%Y"), 
                "dataFinal": dt_fim.strftime("%d/%m/%Y"), 
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

# --- 6. INTERFACE PRINCIPAL ---
st.title("🛡️ Auditoria Gov Federal + IA")

aba1, aba2 = st.tabs(["🕵️ Checagem CNPJ", "📊 Auditoria de Contratos"])

with aba1:
    st.header("Investigação de Fornecedor")
    col1, col2 = st.columns([4, 1]) 
    cnpj_input = col1.text_input("CNPJ Alvo:", value="05.144.757/0001-72")
    if col2.button("Verificar", type="primary"):
        sancoes = auditar_cnpj_detalhado(cnpj_input)
        st.divider()
        if sancoes:
            st.error(f"🚨 **{len(sancoes)} REGISTROS ENCONTRADOS**")
            for s in sancoes: st.write(f"❌ **{s['_origem']}**: {s.get('motivo', 'Sanção ativa')}")
        else:
            st.success("✅ **NADA CONSTA**")

with aba2:
    st.header("Monitoramento de Gastos & IA")
    c_input, c_ia = st.columns([3, 1])
    orgao_nome = c_input.selectbox("Órgão Público:", list(ORGAOS_SIAFI.keys()))
    usar_ia = c_ia.toggle("Ativar IA Gemini", value=True)
    
    if st.button("Buscar Dados"):
        cod = ORGAOS_SIAFI[orgao_nome]
        raw = buscar_contratos(cod)
        
        if raw:
            tabela = []
            
            # Ordena por valor antes de formatar (para pegar os mais caros)
            raw.sort(key=lambda x: safe_float(x.get('valorInicialCompra') or x.get('valorFinalCompra')), reverse=True)
            top_10 = raw[:10]
            
            prog_text = "IA analisando..." if usar_ia else "Formatando..."
            bar_auditoria = st.progress(0, text=prog_text)
            
            for i, item in enumerate(top_10):
                val_float = safe_float(item.get('valorInicialCompra') or item.get('valorFinalCompra'))
                cnpj = item.get('fornecedor', {}).get('cnpjFormatado', '')
                data_crua = item.get('dataAssinatura', '')
                obj_texto = item.get('objeto', '')[:120]
                
                # Análises
                risco_ia = "⚪ N/A"
                status_cnpj = "⚪ OK"
                
                if cnpj and checar_risco_simples(cnpj): status_cnpj = "🚨 ALERTA"
                
                if usar_ia:
                    risco_ia = analisar_objeto_ia(obj_texto)
                    time.sleep(1.0) # Respeita limite da API
                
                tabela.append({
                    "Data": formatar_data_br(data_crua),      # Data formatada BR
                    "Valor": formatar_moeda_br(val_float),    # Valor formatado BR
                    "Objeto": obj_texto,
                    "CNPJ": cnpj,
                    "Risco IA": risco_ia,
                    "Status CNPJ": status_cnpj
                })
                
                bar_auditoria.progress((i + 1) / len(top_10))
            
            bar_auditoria.empty()
            
            # Mostra a tabela
            df = pd.DataFrame(tabela)
            
            def style_risk(v):
                if "ALTO" in str(v): return 'color: red; font-weight: bold'
                if "MÉDIO" in str(v): return 'color: orange'
                if "BAIXO" in str(v): return 'color: green'
                return ''
                
            st.dataframe(
                df.style.applymap(style_risk, subset=['Risco IA']),
                use_container_width=True,
                hide_index=True
            )
        else:
            st.warning("Nenhum dado encontrado.")