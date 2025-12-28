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

PORTAL_KEY = os.getenv("PORTAL_KEY")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")

# Tenta configurar a IA, se der erro, segue a vida sem ela
IA_DISPONIVEL = False
if GEMINI_KEY:
    try:
        genai.configure(api_key=GEMINI_KEY)
        IA_DISPONIVEL = True
    except:
        pass

# --- CSS (MANTENDO O QUE VOCÊ GOSTOU) ---
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

def safe_float(valor):
    try: return float(valor)
    except: return 0.0

def limpar_string(texto):
    return "".join([c for c in str(texto) if c.isdigit()]) if texto else ""

# --- AUDITORIA CNPJ (MODO SIMPLES - O QUE FUNCIONAVA) ---
# Sem validação de raiz complexa, sem loops infinitos.
# Bateu na API -> Voltou dados -> É erro.
@st.cache_data(ttl=3600)
def auditar_cnpj_gov(cnpj_alvo):
    resultados = []
    cnpj_limpo = limpar_string(cnpj_alvo)
    
    if len(cnpj_limpo) != 14: return [] # CNPJ inválido nem tenta

    bases = {
        "acordos-leniencia": "Leniência", 
        "ceis": "Inidôneos (CEIS)", 
        "cnep": "Punidos (CNEP)"
    }
    
    for endpoint, label in bases.items():
        try:
            url = f"https://api.portaldatransparencia.gov.br/api-de-dados/{endpoint}"
            # Busca EXATA pelo CNPJ
            r = requests.get(url, params={"cnpjSancionado": cnpj_limpo, "pagina": 1}, headers=get_headers(), timeout=5)
            if r.status_code == 200:
                dados = r.json()
                if len(dados) > 0:
                    # Se a lista não está vazia, tem sanção. Ponto.
                    item = dados[0]
                    motivo = "Registro encontrado na base de dados."
                    # Tenta pegar motivo se existir
                    if 'motivo' in item: motivo = item['motivo']
                    
                    resultados.append({"origem": label, "motivo": motivo})
        except:
            pass
    return resultados

# --- IA GEMINI (MODO DEBUG) ---
def analisar_contrato_ia(objeto_texto):
    if not IA_DISPONIVEL: return "Erro: Config/Chave"
    
    prompt = f"Analise risco jurídico (ALTO/MEDIO/BAIXO): {objeto_texto}"
    
    try:
        # Tenta o modelo padrão (Pro) que é mais compatível
        model = genai.GenerativeModel('gemini-pro')
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        erro = str(e)
        if "404" in erro: return "Erro: Modelo 404" # Precisa de pip install -U
        if "403" in erro: return "Erro: Chave Inválida"
        return "Erro IA"

# --- BUSCA CONTRATOS ---
def buscar_contratos(codigo_orgao):
    lista = []
    dt_fim = datetime.now()
    dt_ini = dt_fim - timedelta(days=730)
    
    status = st.empty()
    status.text("Buscando dados no Portal...")
    
    # Busca simplificada
    try:
        params = {
            "dataInicial": dt_ini.strftime("%d/%m/%Y"), 
            "dataFinal": dt_fim.strftime("%d/%m/%Y"),
            "codigoOrgao": codigo_orgao, 
            "pagina": 1 # Apenas pág 1 para garantir velocidade e não travar
        }
        r = requests.get("https://api.portaldatransparencia.gov.br/api-de-dados/contratos", 
                       params=params, headers=get_headers(), timeout=10)
        if r.status_code == 200:
            lista = r.json()
    except: 
        pass
        
    status.empty()
    return lista

# --- INTERFACE ---
st.title("🛡️ Auditoria Gov Federal (V52 Restaurada)")

# Seletores
col_sel1, col_sel2 = st.columns(2)
orgao_map = {
    "Presidência da República": "20101",
    "Ministério da Saúde": "36000",
    "Ministério da Educação": "26000",
    "Polícia Federal": "30108"
}
orgao_nome = col_sel1.selectbox("Órgão Público", list(orgao_map.keys()))
cod_orgao = orgao_map[orgao_nome]

tab1, tab2 = st.tabs(["🔎 Consulta CNPJ", "📊 Contratos e IA"])

# --- TAB 1: CNPJ ---
with tab1:
    c1, c2 = st.columns([3, 1])
    cnpj_input = c1.text_input("Digite o CNPJ", "00.000.000/0001-91") # Banco do Brasil (Limpo) para teste
    if c2.button("Verificar"):
        # Tenta pegar nome (opcional, se falhar não quebra)
        nome = "Empresa não identificada"
        try:
            r = requests.get(f"https://brasilapi.com.br/api/cnpj/v1/{limpar_string(cnpj_input)}", timeout=2)
            if r.status_code == 200: nome = r.json().get('razao_social')
        except: pass
        
        st.info(f"Empresa: {nome}")
        
        # Auditoria
        res = auditar_cnpj_gov(cnpj_input)
        if res:
            st.error(f"🚨 FORAM ENCONTRADAS {len(res)} SANÇÕES!")
            for r in res:
                st.write(f"❌ **{r['origem']}**: {r['motivo']}")
        else:
            st.success("✅ Nenhuma sanção ativa encontrada nas bases do governo.")

# --- TAB 2: CONTRATOS ---
with tab2:
    if st.button("Carregar Contratos e Analisar"):
        dados = buscar_contratos(cod_orgao)
        
        if dados and len(dados) > 0:
            # Prepara dados
            tabela = []
            for item in dados:
                tabela.append({
                    "Valor": safe_float(item.get('valorInicialCompra')),
                    "Objeto": item.get('objeto', 'N/A'),
                    "CNPJ": item.get('fornecedor', {}).get('cnpjFormatado', ''),
                    "Risco IA": "...",
                    "Status": "⚪"
                })
            
            df = pd.DataFrame(tabela).sort_values("Valor", ascending=False).head(8)
            
            # --- LOOP DE ANÁLISE ---
            bar = st.progress(0, text="Processando...")
            for i, (idx, row) in enumerate(df.iterrows()):
                # 1. CNPJ Check
                if row['CNPJ']:
                    check = auditar_cnpj_gov(row['CNPJ'])
                    df.at[idx, "Status"] = "🔴 ALERTA" if check else "✅ OK"
                
                # 2. IA Check
                df.at[idx, "Risco IA"] = analisar_contrato_ia(row['Objeto'])
                
                bar.progress((i+1)/len(df))
            bar.empty()
            
            # --- MÉTRICAS ---
            m1, m2, m3 = st.columns(3)
            m1.metric("Total Analisado", f"R$ {df['Valor'].sum():,.2f}")
            m2.metric("Qtd Contratos", len(df))
            riscos = df[df["Risco IA"].str.contains("ALTO", na=False)].shape[0]
            m3.metric("Riscos Altos", riscos)
            
            st.dataframe(df, use_container_width=True)
            
        else:
            st.warning("Nenhum contrato encontrado (Verifique a Chave do Portal ou o Órgão).")