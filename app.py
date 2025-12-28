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

# --- CSS ---
st.markdown("""
    <style>
        .block-container {padding-top: 2rem;}
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        .stDataFrame {font-size: 0.9rem;}
    </style>
""", unsafe_allow_html=True)

# --- ÓRGÃOS ---
ORGAOS_SIAFI = {
    "Secretaria-Geral Presidência (Planalto)": "20101",
    "Ministério da Saúde": "36000",
    "Ministério da Educação": "26000",
    "DNIT (Transportes)": "39252",
    "Polícia Federal": "30108",
    "Comando do Exército": "52121",
    "Ministério da Justiça": "30000"
}

# --- FUNÇÕES AUXILIARES ---
def get_headers():
    return {"chave-api-dados": PORTAL_KEY, "Accept": "application/json"}

def limpar_string(texto):
    if not texto: return ""
    return "".join([c for c in str(texto) if c.isdigit()])

def safe_float(valor):
    try: return float(valor)
    except: return 0.0

def formatar_data_br(data_iso):
    if not data_iso: return ""
    try: return datetime.strptime(data_iso, "%Y-%m-%d").strftime("%d/%m/%Y")
    except: return data_iso

# --- FUNÇÃO 1: AUDITORIA GOVERNAMENTAL (CNPJ) ---
@st.cache_data(ttl=3600)
def auditar_cnpj_gov(cnpj_alvo):
    resultados = [] 
    cnpj_limpo = limpar_string(cnpj_alvo)
    raiz_alvo = cnpj_limpo[:8]
    bases = {"acordos-leniencia": "Leniência", "ceis": "Inidôneos", "cnep": "Punidos"}
    
    for endpoint, nome_base in bases.items():
        try:
            url = f"https://api.portaldatransparencia.gov.br/api-de-dados/{endpoint}"
            params = {"cnpjSancionado": cnpj_limpo, "pagina": 1}
            resp = requests.get(url, params=params, headers=get_headers(), timeout=5)
            if resp.status_code == 200:
                itens = resp.json()
                for item in itens:
                    cnpj_item = ""
                    try: 
                        sancionado = item.get('sancionado', {})
                        cnpj_item = sancionado.get('codigoFormatado') or item.get('pessoa', {}).get('cnpjFormatado')
                    except: pass
                    
                    match = False
                    if cnpj_item and limpar_string(cnpj_item)[:8] == raiz_alvo: match = True
                    elif nome_base == "Leniência" and not cnpj_item: match = True 

                    if match:
                        item['_origem'] = nome_base
                        try: item['_nome'] = item.get('sancionado', {}).get('nome') or item.get('pessoa', {}).get('nome')
                        except: item['_nome'] = "Desconhecido"
                        resultados.append(item)
        except: pass
    return resultados

# --- FUNÇÃO 2: IA GEMINI (CORRIGIDA) ---
def analisar_contrato_ia(objeto_texto):
    if not GEMINI_KEY: return "⚠️ S/ Chave"
    if not objeto_texto or len(objeto_texto) < 5: return "⚪ Vazio"
    
    try:
        # Prompt
        prompt = f"""
        Analise o objeto deste contrato público e identifique riscos de corrupção ou imprecisão.
        Objeto: "{objeto_texto}"
        Responda estritamente com uma destas opções: 'ALTO RISCO', 'MÉDIO RISCO' ou 'BAIXO RISCO'.
        """
        
        # Tenta o modelo atual (FLASH 1.5)
        # Se der erro de "not found", tentamos o PRO
        try:
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content(prompt)
        except:
            model = genai.GenerativeModel('gemini-pro')
            response = model.generate_content(prompt)
            
        return response.text.strip()
        
    except Exception as e:
        erro = str(e)
        if "404" in erro: return "Erro: Modelo 404"
        if "429" in erro: return "Erro: Cota"
        if "API_KEY" in erro: return "Erro: Key Inválida"
        return "Erro Técnico"

# --- FUNÇÃO 3: BUSCA CONTRATOS ---
def buscar_contratos(codigo_orgao):
    lista = []
    dt_fim = datetime.now()
    dt_ini = dt_fim - timedelta(days=730)
    bar = st.progress(0, text="Acessando Portal da Transparência...")
    
    for i, pag in enumerate(range(1, 4)):
        bar.progress((i+1)*33, text=f"Baixando página {pag}...")
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
st.title("🛡️ Auditoria Gov Federal + IA (Final)")
st.markdown("---")

aba1, aba2 = st.tabs(["🕵️ Auditoria (CNPJ)", "💰 Monitor + IA"])

# --- ABA 1: CNPJ ---
with aba1:
    st.header("Verificação de Fornecedor")
    c1, c2 = st.columns([4, 1])
    cnpj_in = c1.text_input("CNPJ:", value="05.144.757/0001-72")
    c2.write(""); c2.write("")
    
    if c2.button("🔍 Verificar", type="primary"):
        # 1. Recuperar Nome (MinhaReceita) - SEM SILENCIAR ERRO
        st.write("🔄 Consultando base cadastral...")
        nome_empresa = "Nome não disponível (API Instável)"
        try:
            r = requests.get(f"https://minhareceita.org/{limpar_string(cnpj_in)}", timeout=10)
            if r.status_code == 200:
                d = r.json()
                razao = d.get('razao_social')
                fantasia = d.get('nome_fantasia')
                if razao:
                    nome_empresa = f"{razao} ({fantasia})" if fantasia else razao
        except: pass
        
        st.info(f"🏢 **Empresa Identificada:** {nome_empresa}")

        # 2. Sanções
        with st.spinner("Varrendo listas de sanções (CEIS/CNEP/Leniência)..."):
            sancoes = auditar_cnpj_gov(cnpj_in)
            st.divider()
            if sancoes: 
                st.error(f"🚨 **ALERTA MÁXIMO: {len(sancoes)} REGISTRO(S) ENCONTRADO(S)**")
                for s in sancoes:
                    st.write(f"⚠️ **{s['_origem']}**: {s.get('motivo') or s.get('situacaoAcordo')}")
            else:
                st.success("✅ **NADA CONSTA** - Fornecedor Ficha Limpa")

# --- ABA 2: MONITOR ---
with aba2:
    st.header("Análise Contratual com Inteligência Artificial")
    col_org, col_ia = st.columns([3, 1])
    orgao = col_org.selectbox("Órgão:", list(ORGAOS_SIAFI.keys()))
    usar_ia = col_ia.checkbox("Ativar IA Gemini", value=True)
    
    if st.button("🔎 Buscar e Analisar"):
        raw = buscar_contratos(ORGAOS_SIAFI[orgao])
        
        if raw:
            tabela = []
            for item in raw:
                val = safe_float(item.get('valorInicialCompra') or item.get('valorFinalCompra'))
                tabela.append({
                    "Valor": val,
                    "Objeto": item.get('objeto', 'N/A'),
                    "CNPJ": item.get('fornecedor', {}).get('cnpjFormatado', ''),
                    "Parecer IA": "⚪ Aguardando",
                    "CNPJ Status": "⚪"
                })
            
            # Pega os 8 maiores contratos para análise
            df = pd.DataFrame(tabela).sort_values("Valor", ascending=False).head(8)
            
            if usar_ia:
                if not GEMINI_KEY:
                    st.error("❌ Configure a GEMINI_API_KEY no arquivo .env")
                else:
                    st.info("🧠 A IA está lendo os objetos dos contratos. Aguarde...")
                    bar_ia = st.progress(0)
                    
                    for i, idx in enumerate(df.index):
                        # CNPJ Check
                        c = df.at[idx, "CNPJ"]
                        if c: df.at[idx, "CNPJ Status"] = "🔴 ALERTA" if auditar_cnpj_gov(c) else "🟢 OK"
                        
                        # IA Check
                        txt = df.at[idx, "Objeto"]
                        df.at[idx, "Parecer IA"] = analisar_contrato_ia(txt)
                        
                        bar_ia.progress(int((i+1)/len(df)*100))
                    
                    bar_ia.empty()

            # Estilização Condicional
            def highlight_ia(val):
                v = str(val).upper()
                if "ALTO" in v: return 'background-color: #ffcccc; color: red; font-weight: bold'
                if "BAIXO" in v: return 'color: green; font-weight: bold'
                if "ERRO" in v: return 'background-color: #ffffcc; color: black'
                return ''
                
            def highlight_cnpj(val):
                if "ALERTA" in str(val): return 'color: red; font-weight: bold'
                if "OK" in str(val): return 'color: green; font-weight: bold'
                return ''

            st.dataframe(
                df.style.applymap(highlight_ia, subset=['Parecer IA'])
                        .applymap(highlight_cnpj, subset=['CNPJ Status'])
                        .format({"Valor": "R$ {:,.2f}"}),
                use_container_width=True
            )
        else:
            st.warning("Nenhum contrato recente encontrado para este órgão.")