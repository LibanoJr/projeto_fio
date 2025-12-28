import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
import google.generativeai as genai

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="GovAudit Pro", page_icon="⚖️", layout="wide")
load_dotenv()

# --- CHAVES (COM DEBUG) ---
PORTAL_KEY = os.getenv("PORTAL_KEY")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")

if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)

# --- CSS ---
st.markdown("""
    <style>
        .block-container {padding-top: 1rem;}
        div[data-testid="stMetricValue"] {font-size: 1.5rem;}
        .stButton>button {width: 100%; margin-top: 28px;}
    </style>
""", unsafe_allow_html=True)

# --- FUNÇÕES BÁSICAS ---
def get_headers():
    return {"chave-api-dados": PORTAL_KEY, "Accept": "application/json"}

def limpar_string(texto):
    return "".join([c for c in str(texto) if c.isdigit()]) if texto else ""

def safe_float(valor):
    try: return float(valor)
    except: return 0.0

# --- AUDITORIA CNPJ (MODO RAIZ - PEGA TUDO) ---
@st.cache_data(ttl=3600)
def auditar_cnpj_gov(cnpj_alvo):
    resultados = [] 
    cnpj_limpo = limpar_string(cnpj_alvo)
    raiz_alvo = cnpj_limpo[:8] # Pega os 8 primeiros dígitos (Matriz)
    
    # Se não tiver CNPJ válido, retorna vazio
    if len(raiz_alvo) < 8: return []

    bases = {
        "acordos-leniencia": "Leniência", 
        "ceis": "Inidôneos (CEIS)", 
        "cnep": "Punidos (CNEP)"
    }
    
    for endpoint, label in bases.items():
        try:
            # Busca pela raiz para garantir que pega tudo
            url = f"https://api.portaldatransparencia.gov.br/api-de-dados/{endpoint}"
            params = {"cnpjSancionado": cnpj_limpo, "pagina": 1}
            r = requests.get(url, params=params, headers=get_headers(), timeout=5)
            
            if r.status_code == 200:
                itens = r.json()
                # Se a API devolveu algo, verificamos se bate a raiz
                for item in itens:
                    # Tenta achar o CNPJ na resposta
                    cnpj_resp = ""
                    try:
                        cnpj_resp = item.get('sancionado', {}).get('codigoFormatado') or \
                                    item.get('pessoa', {}).get('cnpjFormatado') or ""
                    except: pass
                    
                    # Se a raiz bater, é flag!
                    if limpar_string(cnpj_resp)[:8] == raiz_alvo:
                        motivo = item.get('motivo') or "Sanção Vigente na Base de Dados"
                        resultados.append({"origem": label, "motivo": motivo})
                        # Paramos no primeiro erro daquela base para não poluir
                        break 
        except Exception as e:
            # Se der erro de conexão, ignora
            pass
            
    return resultados

# --- IA GEMINI (DEBUG ERROR MODE) ---
def analisar_contrato_ia(objeto_texto):
    if not GEMINI_KEY: return "⚠️ S/ Chave"
    if not objeto_texto: return "⚪ Vazio"
    
    prompt = f"""
    Analise APENAS RISCOS JURÍDICOS E FINANCEIROS do objeto: "{objeto_texto}"
    Responda EXATAMENTE uma das opções: 'ALTO RISCO', 'MÉDIO RISCO' ou 'BAIXO RISCO'.
    """
    
    # Tenta modelos diferentes
    modelos = ['gemini-1.5-flash', 'gemini-pro', 'gemini-1.0-pro']
    
    erro_msg = ""
    for modelo in modelos:
        try:
            model = genai.GenerativeModel(modelo)
            response = model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            erro_msg = str(e)
            continue
    
    # Se falhar, mostra o erro real
    if "429" in erro_msg: return "Erro: Cota Excedida"
    if "403" in erro_msg: return "Erro: Chave Inválida"
    if "404" in erro_msg: return "Erro: Modelo 404 (Pip)"
    return "Erro IA"

# --- BUSCA CONTRATOS ---
def buscar_contratos(codigo_orgao):
    lista = []
    dt_fim = datetime.now()
    dt_ini = dt_fim - timedelta(days=730)
    
    # Feedback visual
    status = st.empty()
    status.text("Conectando API...")
    
    for pag in range(1, 3): # 2 páginas para ser rápido
        try:
            params = {
                "dataInicial": dt_ini.strftime("%d/%m/%Y"), 
                "dataFinal": dt_fim.strftime("%d/%m/%Y"),
                "codigoOrgao": codigo_orgao, 
                "pagina": pag
            }
            r = requests.get("https://api.portaldatransparencia.gov.br/api-de-dados/contratos", 
                           params=params, headers=get_headers(), timeout=8)
            if r.status_code == 200:
                d = r.json()
                if not d: break
                lista.extend(d)
            else: break
        except: break
    status.empty()
    return lista

# --- INTERFACE PRINCIPAL ---
st.title("🛡️ Auditoria Gov Federal (V51 Debug)")

# Menu lateral simplificado
with st.sidebar:
    st.header("Configurações")
    st.info(f"🔑 Portal Key: {'OK' if PORTAL_KEY else 'Ausente'}")
    st.info(f"🤖 Gemini Key: {'OK' if GEMINI_KEY else 'Ausente'}")
    orgao_selecionado = st.selectbox("Órgão", [
        "20101 - Presidência (Planalto)",
        "36000 - Min. Saúde",
        "26000 - Min. Educação",
        "30108 - Polícia Federal",
        "52121 - Exército"
    ])
    cod_orgao = orgao_selecionado.split(" - ")[0]

tab_cnpj, tab_contratos = st.tabs(["🕵️ Checagem CNPJ", "💰 Contratos e IA"])

# --- ABA 1: CNPJ ---
with tab_cnpj:
    st.subheader("Auditoria de Fornecedor")
    c1, c2 = st.columns([3, 1])
    cnpj_digitado = c1.text_input("CNPJ Alvo", value="05.144.757/0001-72") # Default Novonor
    
    if c2.button("Auditar CNPJ"):
        st.write("---")
        
        # 1. Nome (BrasilAPI)
        with st.spinner("Buscando Razão Social..."):
            nome = "Não identificado"
            try:
                r = requests.get(f"https://brasilapi.com.br/api/cnpj/v1/{limpar_string(cnpj_digitado)}", timeout=4)
                if r.status_code == 200:
                    nome = r.json().get('razao_social', nome)
            except: pass
            st.success(f"🏢 **Empresa:** {nome}")

        # 2. Sanções (Portal)
        with st.spinner("Verificando Sanções (CEIS/CNEP/Leniência)..."):
            sancoes = auditar_cnpj_gov(cnpj_digitado)
            
            if sancoes:
                st.error(f"🚨 **ALERTA MÁXIMO:** {len(sancoes)} Restrições Encontradas!")
                for s in sancoes:
                    st.write(f"❌ **{s['origem']}:** {s['motivo']}")
            else:
                st.success("✅ **Nada Consta** (Nenhuma sanção ativa encontrada para este CNPJ/Raiz).")

# --- ABA 2: CONTRATOS ---
with tab_contratos:
    st.subheader(f"Contratos: {orgao_selecionado}")
    
    col_btn, col_check = st.columns([1, 4])
    rodar = col_btn.button("🔎 Buscar Dados")
    usar_ia = col_check.checkbox("Ativar Análise IA", value=True)

    if rodar:
        dados = buscar_contratos(cod_orgao)
        
        if dados:
            # Processamento
            lista_final = []
            for item in dados:
                lista_final.append({
                    "Valor": safe_float(item.get('valorInicialCompra')),
                    "Objeto": item.get('objeto', 'N/A'),
                    "CNPJ": item.get('fornecedor', {}).get('cnpjFormatado', ''),
                    "IA": "...",
                    "Status": "⚪"
                })
            
            # DataFrame Top 8
            df = pd.DataFrame(lista_final).sort_values("Valor", ascending=False).head(8)
            
            # IA e Check de CNPJ na tabela
            if usar_ia:
                bar = st.progress(0, text="Processando IA e Sanções...")
                for i, (idx, row) in enumerate(df.iterrows()):
                    # Checa CNPJ da linha
                    if row['CNPJ']:
                        sancao = auditar_cnpj_gov(row['CNPJ'])
                        df.at[idx, "Status"] = "🔴 ALERTA" if sancao else "✅ OK"
                    
                    # Chama IA
                    df.at[idx, "IA"] = analisar_contrato_ia(row['Objeto'])
                    
                    bar.progress((i+1)/len(df))
                bar.empty()

            # --- MÉTRICAS ---
            c_val, c_qtd, c_risk = st.columns(3)
            c_val.metric("Valor Total", f"R$ {df['Valor'].sum():,.2f}")
            c_qtd.metric("Contratos", len(df))
            
            # Conta riscos (ignora erros)
            riscos = df[df['IA'].str.contains("ALTO", na=False)].shape[0]
            c_risk.metric("Riscos Altos", riscos, delta_color="inverse")

            st.write("---")
            
            # Cores
            def highlight_risk(val):
                if "ALTO" in str(val): return 'color: red; font-weight: bold'
                if "BAIXO" in str(val): return 'color: green'
                if "Erro" in str(val): return 'background-color: yellow; color: black'
                return ''
            
            def highlight_status(val):
                if "ALERTA" in str(val): return 'color: red; font-weight: bold'
                return 'color: green'

            st.dataframe(
                df.style.applymap(highlight_risk, subset=['IA'])
                        .applymap(highlight_status, subset=['Status'])
                        .format({"Valor": "R$ {:,.2f}"}),
                use_container_width=True
            )
            
        else:
            st.warning("Nenhum contrato encontrado ou erro na API do Portal.")