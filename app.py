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

# Configuração da IA (Segura)
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)

# --- CSS ---
st.markdown("""
    <style>
        .block-container {padding-top: 2rem;}
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        .stDataFrame {font-size: 0.9rem;}
        div[data-testid="stMetricValue"] {font-size: 1.2rem;}
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

# --- FUNÇÃO 1: AUDITORIA (CNPJ) ---
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
            resp = requests.get(url, params=params, headers=get_headers(), timeout=4)
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

# --- FUNÇÃO 2: IA GEMINI (ROBUSTA) ---
def analisar_contrato_ia(objeto_texto):
    if not GEMINI_KEY: return "⚠️ S/ Chave"
    if not objeto_texto or len(objeto_texto) < 5: return "⚪ Vazio"
    
    prompt = f"""
    Analise o seguinte objeto de contrato público quanto a clareza e riscos de corrupção.
    Objeto: "{objeto_texto}"
    Responda APENAS com uma das opções abaixo:
    'ALTO RISCO' se for vago ou genérico demais.
    'MÉDIO RISCO' se for padrão mas com detalhes faltantes.
    'BAIXO RISCO' se for bem específico.
    """
    
    # Tenta modelos diferentes para evitar erro 404
    modelos = ['gemini-1.5-flash', 'gemini-pro', 'gemini-1.0-pro']
    
    for modelo_nome in modelos:
        try:
            model = genai.GenerativeModel(modelo_nome)
            response = model.generate_content(prompt)
            return response.text.strip()
        except:
            continue # Se falhar, tenta o próximo modelo da lista
            
    return "Erro Conexão IA"

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
st.title("🛡️ Auditoria Gov Federal + IA (V46.4)")
st.markdown("---")

aba1, aba2 = st.tabs(["🕵️ Auditoria (CNPJ)", "💰 Monitor + IA"])

# --- ABA 1: CNPJ ---
with aba1:
    st.header("Verificação de Antecedentes")
    c1, c2 = st.columns([4, 1])
    cnpj_in = c1.text_input("CNPJ:", value="05.144.757/0001-72")
    c2.write(""); c2.write("")
    
    if c2.button("🔍 Verificar", type="primary"):
        # Consulta Nome (MinhaReceita) - COM FALLBACK
        st.write("🔄 Buscando dados cadastrais...")
        nome_empresa = "Nome Indisponível (API Instável)"
        try:
            r = requests.get(f"https://minhareceita.org/{limpar_string(cnpj_in)}", timeout=5)
            if r.status_code == 200:
                d = r.json()
                if 'razao_social' in d:
                    nome_empresa = f"{d['razao_social']} ({d.get('nome_fantasia','')})"
        except: pass
        
        st.info(f"🏢 **Empresa:** {nome_empresa}")

        # Consulta Sanções
        with st.spinner("Analisando sanções..."):
            sancoes = auditar_cnpj_gov(cnpj_in)
            st.divider()
            if sancoes: 
                st.error(f"🚨 **ALERTA: {len(sancoes)} RESTRIÇÕES ENCONTRADAS**")
                for s in sancoes: st.write(f"⚠️ {s['_origem']}: {s.get('motivo','Sem motivo detalhado')}")
            else:
                st.success("✅ **NADA CONSTA** (Ficha Limpa)")

# --- ABA 2: MONITOR ---
with aba2:
    st.header("Análise Contratual + Parecer IA")
    col_org, col_ia = st.columns([3, 1])
    orgao = col_org.selectbox("Órgão:", list(ORGAOS_SIAFI.keys()))
    usar_ia = col_ia.checkbox("Ativar IA", value=True)
    
    if st.button("🔎 Buscar"):
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
            
            df = pd.DataFrame(tabela).sort_values("Valor", ascending=False).head(7)
            
            if usar_ia:
                if not GEMINI_KEY: st.error("❌ Configure GEMINI_API_KEY no .env")
                else:
                    st.info("🧠 IA analisando contratos... (Isso pode levar alguns segundos)")
                    bar_ia = st.progress(0)
                    for i, idx in enumerate(df.index):
                        # CNPJ
                        c = df.at[idx, "CNPJ"]
                        if c: 
                            res = auditar_cnpj_gov(c)
                            df.at[idx, "CNPJ Status"] = "🔴 ALERTA" if res else "🟢 OK"
                        
                        # IA
                        txt = df.at[idx, "Objeto"]
                        df.at[idx, "Parecer IA"] = analisar_contrato_ia(txt)
                        bar_ia.progress(int((i+1)/len(df)*100))
                    bar_ia.empty()

            # Estilização
            def cor_ia(v):
                if "ALTO" in str(v): return 'background-color: #ffcccc; color: #990000; font-weight: bold'
                if "BAIXO" in str(v): return 'color: green; font-weight: bold'
                if "Erro" in str(v): return 'background-color: #ffffcc; color: black'
                return ''

            def cor_cnpj(v):
                if "ALERTA" in str(v): return 'color: red; font-weight: bold'
                return 'color: green'

            st.dataframe(
                df.style.applymap(cor_ia, subset=['Parecer IA'])
                        .applymap(cor_cnpj, subset=['CNPJ Status'])
                        .format({"Valor": "R$ {:,.2f}"}),
                use_container_width=True
            )
        else: st.warning("Nenhum contrato recente encontrado.")