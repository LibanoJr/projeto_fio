import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
import google.generativeai as genai

# --- 1. CONFIGURAÇÃO E SEGURANÇA (.ENV) ---
st.set_page_config(page_title="GovAudit Pro", page_icon="⚖️", layout="wide")
load_dotenv()

PORTAL_KEY = os.getenv("PORTAL_KEY")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")

# Configuração IA (Blindada contra erros)
IA_ATIVA = False
if GEMINI_KEY:
    try:
        genai.configure(api_key=GEMINI_KEY)
        IA_ATIVA = True
    except: pass

# --- CSS (Visual Limpo) ---
st.markdown("""
    <style>
        .block-container {padding-top: 1rem;}
        div[data-testid="stMetricValue"] {font-size: 1.5rem;}
        .stButton>button {width: 100%; margin-top: 28px;}
    </style>
""", unsafe_allow_html=True)

# --- FUNÇÕES AUXILIARES ---
def get_headers():
    return {"chave-api-dados": PORTAL_KEY, "Accept": "application/json"}

def safe_float(valor):
    try: return float(valor)
    except: return 0.0

def limpar_cnpj(texto):
    return "".join([c for c in str(texto) if c.isdigit()])

# --- 2. BUSCA INTELIGENTE DE NOME ---
def buscar_nome_empresa(cnpj):
    cnpj_limpo = limpar_cnpj(cnpj)
    # Tenta BrasilAPI (Melhor e Gratuita)
    try:
        r = requests.get(f"https://brasilapi.com.br/api/cnpj/v1/{cnpj_limpo}", timeout=3)
        if r.status_code == 200:
            return r.json()['razao_social']
    except: pass
    
    # Se falhar, tenta ReceitaWS (Fallback)
    try:
        r = requests.get(f"https://www.receitaws.com.br/v1/cnpj/{cnpj_limpo}", timeout=3)
        if r.status_code == 200:
            return r.json().get('nome')
    except: pass

    return "Nome Indisponível (Erro Conexão API)"

# --- 3. AUDITORIA CNPJ (COM FILTRO ANTI-FALSO POSITIVO) ---
@st.cache_data(ttl=3600)
def auditar_cnpj_gov(cnpj_alvo):
    resultados = []
    cnpj_limpo = limpar_cnpj(cnpj_alvo)
    
    # Bases Críticas (Ignora multas leves para não sujar CNPJ limpo)
    bases = {
        "acordos-leniencia": "ACORDO DE LENIÊNCIA (GRAVE)", 
        "ceis": "INIDÔNEO (CEIS)", 
        "cnep": "PUNIDO (CNEP)"
    }
    
    for endpoint, label in bases.items():
        try:
            url = f"https://api.portaldatransparencia.gov.br/api-de-dados/{endpoint}"
            params = {"cnpjSancionado": cnpj_limpo, "pagina": 1}
            r = requests.get(url, params=params, headers=get_headers(), timeout=5)
            
            if r.status_code == 200:
                dados = r.json()
                if len(dados) > 0:
                    # Só adiciona se tiver dados reais
                    item = dados[0]
                    # Filtra falsos positivos da API (às vezes ela retorna empresa parecida)
                    cnpj_retorno = item.get('sancionado', {}).get('codigoFormatado') or \
                                   item.get('pessoa', {}).get('cnpjFormatado') or ""
                    
                    if limpar_cnpj(cnpj_retorno) == cnpj_limpo:
                        resultados.append({"origem": label, "motivo": item.get('motivo', 'Sanção Ativa')})
        except: pass
            
    return resultados

# --- 4. IA GEMINI (COM CORREÇÃO PARA VERSÕES ANTIGAS) ---
def analisar_risco_ia(objeto):
    if not IA_ATIVA: return "Erro: Chave API"
    if not objeto: return "N/A"
    
    prompt = f"Analise juridicamente este objeto de licitação. Responda APENAS 'ALTO RISCO', 'MÉDIO RISCO' ou 'BAIXO RISCO': {objeto}"
    
    # Estratégia: Tenta modelo novo -> Falha -> Tenta modelo antigo
    modelos = ['gemini-1.5-flash', 'gemini-pro']
    
    for modelo in modelos:
        try:
            model = genai.GenerativeModel(modelo)
            response = model.generate_content(prompt)
            return response.text.strip().upper() # Garante maiúscula
        except:
            continue
            
    return "Erro: Atualize Pip"

# --- 5. BUSCA CONTRATOS (SIAFI) ---
def buscar_contratos(orgao_cod):
    lista = []
    # Data dinâmica (últimos 3 anos para garantir dados)
    dt_fim = datetime.now()
    dt_ini = dt_fim - timedelta(days=365*2)
    
    try:
        params = {
            "dataInicial": dt_ini.strftime("%d/%m/%Y"),
            "dataFinal": dt_fim.strftime("%d/%m/%Y"),
            "codigoOrgao": orgao_cod,
            "pagina": 1 # Apenas pág 1 para não travar
        }
        r = requests.get("https://api.portaldatransparencia.gov.br/api-de-dados/contratos", 
                       params=params, headers=get_headers(), timeout=8)
        if r.status_code == 200:
            lista = r.json()
    except: pass
    return lista

# --- INTERFACE ---
st.title("🛡️ Sistema de Auditoria de Contratos (TCC)")

tab1, tab2 = st.tabs(["🔍 Consulta Fornecedor", "📊 Análise de Contratos"])

# ABA 1: FORNECEDOR
with tab1:
    c1, c2 = st.columns([3, 1])
    cnpj_input = c1.text_input("CNPJ", "05.144.757/0001-72") # Novonor
    
    if c2.button("Verificar"):
        # 1. Nome
        with st.spinner("Buscando dados na Receita..."):
            nome = buscar_nome_empresa(cnpj_input)
        st.info(f"🏢 **Razão Social:** {nome}")
        
        # 2. Sanções
        with st.spinner("Auditando bases de sanções..."):
            erros = auditar_cnpj_gov(cnpj_input)
        
        st.write("---")
        if erros:
            st.error(f"🚨 **ALERTA:** Foram encontradas {len(erros)} restrições graves!")
            for e in erros:
                st.write(f"❌ **{e['origem']}**: {e['motivo']}")
        else:
            st.success("✅ **CNPJ LIMPO:** Nenhuma sanção de inidoneidade ou leniência encontrada.")

# ABA 2: CONTRATOS
with tab2:
    mapa_orgaos = {
        "Presidência da República": "20101",
        "Ministério da Saúde": "36000", 
        "Polícia Federal": "30108"
    }
    sel_orgao = st.selectbox("Selecione o Órgão", list(mapa_orgaos.keys()))
    
    if st.button("Carregar Dados"):
        dados = buscar_contratos(mapa_orgaos[sel_orgao])
        
        if dados:
            tabela = []
            for item in dados:
                tabela.append({
                    "Valor": safe_float(item.get('valorInicialCompra')),
                    "Objeto": item.get('objeto', 'N/A')[:120] + "...",
                    "CNPJ": item.get('fornecedor', {}).get('cnpjFormatado', ''),
                    "IA": "...",
                    "Status": "⚪"
                })
            
            # Pega os 5 maiores (mais rápido)
            df = pd.DataFrame(tabela).sort_values("Valor", ascending=False).head(5)
            
            # Barra de progresso real
            bar = st.progress(0, text="IA analisando riscos...")
            
            for i, (idx, row) in enumerate(df.iterrows()):
                # Check CNPJ
                if row['CNPJ']:
                    if auditar_cnpj_gov(row['CNPJ']):
                        df.at[idx, "Status"] = "🔴 ALERTA"
                    else:
                        df.at[idx, "Status"] = "🟢 Regular"
                
                # Check IA
                df.at[idx, "IA"] = analisar_risco_ia(row['Objeto'])
                
                bar.progress((i+1)/len(df))
            bar.empty()
            
            # KPIs
            k1, k2, k3 = st.columns(3)
            k1.metric("Total Analisado", f"R$ {df['Valor'].sum():,.2f}")
            k2.metric("Contratos", len(df))
            k3.metric("Riscos Altos", df[df['IA'].str.contains("ALTO", na=False)].shape[0])
            
            # Tabela Colorida
            def color_ia(val):
                if "ALTO" in str(val): return 'color: red; font-weight: bold'
                if "BAIXO" in str(val): return 'color: green; font-weight: bold'
                return ''
                
            st.dataframe(df.style.applymap(color_ia, subset=['IA']), use_container_width=True)
            
        else:
            st.warning("Não foi possível obter dados do Portal no momento.")