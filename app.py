import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
import google.generativeai as genai

# --- CONFIGURAÇÃO INICIAL ---
st.set_page_config(page_title="GovAudit Pro + IA", page_icon="⚖️", layout="wide")
load_dotenv()

PORTAL_KEY = os.getenv("PORTAL_KEY")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")

if GEMINI_KEY:
    try:
        genai.configure(api_key=GEMINI_KEY)
    except:
        pass

# --- CSS (Visual Limpo) ---
st.markdown("""
    <style>
        .block-container {padding-top: 1.5rem;}
        div[data-testid="stMetricValue"] {font-size: 1.6rem;}
        .stButton>button {width: 100%; margin-top: 29px;}
    </style>
""", unsafe_allow_html=True)

# --- DADOS ---
ORGAOS_SIAFI = {
    "Secretaria-Geral Presidência (Planalto)": "20101",
    "Ministério da Saúde": "36000",
    "Ministério da Educação": "26000",
    "Polícia Federal": "30108",
    "Comando do Exército": "52121"
}

# --- FUNÇÕES ÚTEIS ---
def get_headers():
    return {"chave-api-dados": PORTAL_KEY, "Accept": "application/json"}

def limpar_string(texto):
    return "".join([c for c in str(texto) if c.isdigit()]) if texto else ""

def safe_float(valor):
    try: return float(valor)
    except: return 0.0

# --- 1. BUSCA NOME (DUPLA CHECAGEM) ---
def buscar_nome_empresa(cnpj):
    cnpj_limpo = limpar_string(cnpj)
    # Tentativa 1: BrasilAPI
    try:
        r = requests.get(f"https://brasilapi.com.br/api/cnpj/v1/{cnpj_limpo}", timeout=3)
        if r.status_code == 200:
            return r.json().get('razao_social')
    except: pass
    
    # Tentativa 2: MinhaReceita (Fallback)
    try:
        r = requests.get(f"https://minhareceita.org/{cnpj_limpo}", timeout=3)
        if r.status_code == 200:
            return r.json().get('razao_social')
    except: pass
    
    return "Nome Indisponível (Erro na API Pública)"

# --- 2. AUDITORIA CNPJ (RIGOROSA) ---
# Só marca erro se o CNPJ sancionado for IDÊNTICO ao buscado
@st.cache_data(ttl=3600)
def auditar_cnpj_gov(cnpj_alvo):
    resultados = [] 
    cnpj_limpo = limpar_string(cnpj_alvo)
    
    bases = {
        "acordos-leniencia": "Leniência (Corrupção)", 
        "ceis": "Inidôneos (CEIS)", 
        "cnep": "Punidos (CNEP)"
    }
    
    for endpoint, label in bases.items():
        try:
            url = f"https://api.portaldatransparencia.gov.br/api-de-dados/{endpoint}"
            params = {"cnpjSancionado": cnpj_limpo, "pagina": 1}
            r = requests.get(url, params=params, headers=get_headers(), timeout=5)
            
            if r.status_code == 200:
                itens = r.json()
                for item in itens:
                    # Verifica se o CNPJ retornado é REALMENTE o que buscamos
                    # A API as vezes retorna "raiz" parecida. Filtramos aqui.
                    cnpj_retornado = ""
                    try:
                        cnpj_retornado = item.get('sancionado', {}).get('codigoFormatado') or \
                                       item.get('pessoa', {}).get('cnpjFormatado')
                    except: pass
                    
                    if limpar_string(cnpj_retornado) == cnpj_limpo:
                        motivo = item.get('motivo') or "Sanção Ativa"
                        resultados.append({"origem": label, "motivo": motivo})
        except:
            pass 
            
    return resultados

# --- 3. IA GEMINI (TRY/EXCEPT ROBUSTO) ---
def analisar_contrato_ia(objeto_texto):
    if not GEMINI_KEY: return "⚠️ S/ Chave"
    if not objeto_texto: return "⚪ Vazio"
    
    prompt = f"""
    Analise o objeto do contrato: "{objeto_texto}"
    Responda APENAS: 'ALTO RISCO', 'MÉDIO RISCO' ou 'BAIXO RISCO'.
    """
    
    # Tenta Flash depois Pro
    modelos = ['gemini-1.5-flash', 'gemini-pro']
    
    for nome_modelo in modelos:
        try:
            model = genai.GenerativeModel(nome_modelo)
            response = model.generate_content(prompt)
            return response.text.strip()
        except:
            continue
            
    return "IA Indisponível"

# --- 4. BUSCA CONTRATOS ---
def buscar_contratos(codigo_orgao):
    lista = []
    dt_fim = datetime.now()
    dt_ini = dt_fim - timedelta(days=730)
    
    placeholder = st.empty()
    bar = placeholder.progress(0, text="Conectando ao Portal...")
    
    # Limita a 2 páginas para ser mais rápido e dar menos erro
    for i, pag in enumerate(range(1, 3)):
        bar.progress((i+1)*50, text=f"Lendo Portal da Transparência (Pág {pag})...")
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
    placeholder.empty()
    return lista

# --- INTERFACE ---
st.title("🛡️ Auditoria Gov Federal + IA (Estável)")
st.markdown("---")

tab1, tab2 = st.tabs(["🔎 Auditoria CNPJ", "📊 Painel de Contratos"])

# --- ABA 1 ---
with tab1:
    st.header("Checagem de Fornecedor")
    c1, c2 = st.columns([3, 1])
    cnpj_input = c1.text_input("CNPJ:", "05.144.757/0001-72")
    if c2.button("Verificar", type="primary"):
        
        # 1. Nome
        nome = buscar_nome_empresa(cnpj_input)
        if "Indisponível" in nome:
            st.warning(f"⚠️ {nome} (Mas a auditoria foi feita)")
        else:
            st.info(f"🏢 **Empresa:** {nome}")
            
        # 2. Sanções
        st.write("🕵️ Cruzando dados com listas de punições...")
        sancoes = auditar_cnpj_gov(cnpj_input)
        
        st.divider()
        if sancoes:
            st.error(f"🚨 **ALERTA: {len(sancoes)} RESTRIÇÃO(ÕES) ENCONTRADA(S)**")
            for s in sancoes:
                st.write(f"❌ **{s['origem']}**: {s['motivo']}")
        else:
            st.success("✅ **NADA CONSTA** - Fornecedor sem sanções ativas.")

# --- ABA 2 ---
with tab2:
    st.header("Monitoramento de Contratos")
    col_org, col_ia = st.columns([3, 1])
    orgao = col_org.selectbox("Órgão:", list(ORGAOS_SIAFI.keys()))
    usa_ia = col_ia.toggle("IA Analisa Riscos", value=True)
    
    if st.button("Carregar Contratos"):
        dados = buscar_contratos(ORGAOS_SIAFI[orgao])
        
        if dados:
            # Processa dados iniciais
            df_list = []
            for item in dados:
                df_list.append({
                    "Valor": safe_float(item.get('valorInicialCompra')),
                    "Objeto": item.get('objeto', 'Objeto não informado'),
                    "CNPJ": item.get('fornecedor', {}).get('cnpjFormatado', ''),
                    "Risco IA": "...",
                    "Status CNPJ": "⚪"
                })
            
            # Ordena e pega Top 10
            df = pd.DataFrame(df_list).sort_values("Valor", ascending=False).head(10)
            
            # Loop de Análise (IA + CNPJ)
            if usa_ia:
                bar_ia = st.progress(0, text="IA analisando contratos...")
                for i, (idx, row) in enumerate(df.iterrows()):
                    # CNPJ
                    if row['CNPJ']:
                        # Reusa a função rigorosa
                        res = auditar_cnpj_gov(row['CNPJ'])
                        df.at[idx, "Status CNPJ"] = "🔴 ALERTA" if res else "🟢 OK"
                    
                    # IA
                    df.at[idx, "Risco IA"] = analisar_contrato_ia(row['Objeto'])
                    
                    # Atualiza barra seguramente
                    bar_ia.progress((i+1)/len(df))
                bar_ia.empty()
            
            # --- MÉTRICAS (KPIs) ---
            m1, m2, m3 = st.columns(3)
            val_total = df['Valor'].sum()
            qtd_risco = df[df['Risco IA'].str.contains("ALTO", na=False)].shape[0]
            
            m1.metric("Valor Total (Amostra)", f"R$ {val_total:,.2f}")
            m2.metric("Contratos", len(df))
            m3.metric("Riscos Altos (IA)", qtd_risco, delta_color="inverse")
            
            st.divider()

            # --- TABELA FINAL ---
            def color_ia(v):
                if "ALTO" in str(v): return 'color: red; font-weight: bold; background-color: #ffe6e6'
                if "BAIXO" in str(v): return 'color: green; font-weight: bold'
                return ''
                
            def color_cnpj(v):
                if "ALERTA" in str(v): return 'color: red; font-weight: bold'
                return 'color: green'

            st.dataframe(
                df.style.applymap(color_ia, subset=['Risco IA'])
                        .applymap(color_cnpj, subset=['Status CNPJ'])
                        .format({"Valor": "R$ {:,.2f}"}),
                use_container_width=True
            )
            
        else:
            st.warning("Nenhum contrato recente encontrado para este órgão.")