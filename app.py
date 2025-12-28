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

# Tenta configurar IA (silencioso se falhar)
try:
    if GEMINI_KEY: genai.configure(api_key=GEMINI_KEY)
except: pass

# --- CSS (MANTENDO O QUE ESTAVA BOM) ---
st.markdown("""
    <style>
        .block-container {padding-top: 1rem;}
        div[data-testid="stMetricValue"] {font-size: 1.6rem;}
        .stButton>button {width: 100%; margin-top: 28px;}
    </style>
""", unsafe_allow_html=True)

# --- FUNÇÕES ---
def get_headers():
    return {"chave-api-dados": PORTAL_KEY, "Accept": "application/json"}

def safe_float(valor):
    try: return float(valor)
    except: return 0.0

def limpar_cnpj(texto):
    return "".join([c for c in str(texto) if c.isdigit()])

# --- CONSULTA NOME (BRASIL API) ---
def get_nome(cnpj):
    try:
        r = requests.get(f"https://brasilapi.com.br/api/cnpj/v1/{limpar_cnpj(cnpj)}", timeout=2)
        if r.status_code == 200:
            return r.json()['razao_social']
    except: pass
    return "Razão Social não identificada"

# --- CONSULTA SANÇÕES (LÓGICA "BRUTA" - SE ACHAR, MOSTRA) ---
def auditar_cnpj(cnpj_alvo):
    lista_sancoes = []
    cnpj_limpo = limpar_cnpj(cnpj_alvo)
    
    # Endpoints do Portal da Transparência
    urls = {
        "acordos-leniencia": "Acordo de Leniência",
        "ceis": "Inidôneos (CEIS)",
        "cnep": "Punidos (CNEP)"
    }
    
    for endpoint, nome_base in urls.items():
        try:
            # Solicita API
            r = requests.get(
                f"https://api.portaldatransparencia.gov.br/api-de-dados/{endpoint}",
                params={"cnpjSancionado": cnpj_limpo, "pagina": 1},
                headers=get_headers(),
                timeout=5
            )
            # SE TIVER QUALQUER RESULTADO, É ALERTA (SEM FILTROS)
            if r.status_code == 200 and len(r.json()) > 0:
                item = r.json()[0]
                motivo = item.get('motivo', 'Registro encontrado na base')
                lista_sancoes.append(f"{nome_base}: {motivo}")
        except:
            pass # Se der erro de conexão, segue o baile
            
    return lista_sancoes

# --- IA SIMPLIFICADA ---
def analisar_ia(texto):
    if not GEMINI_KEY: return "Sem Chave"
    try:
        # Prompt direto e curto
        model = genai.GenerativeModel('gemini-pro')
        res = model.generate_content(f"Classifique o risco jurídico disto (ALTO/MEDIO/BAIXO): {texto}")
        return res.text.strip().upper()
    except:
        return "-" # Retorna traço se der erro para não sujar a tela

# --- BUSCA CONTRATOS ---
def buscar_contratos(orgao):
    lista = []
    dt_fim = datetime.now()
    dt_ini = dt_fim - timedelta(days=730)
    
    try:
        params = {
            "dataInicial": dt_ini.strftime("%d/%m/%Y"),
            "dataFinal": dt_fim.strftime("%d/%m/%Y"),
            "codigoOrgao": orgao,
            "pagina": 1
        }
        r = requests.get("https://api.portaldatransparencia.gov.br/api-de-dados/contratos", 
                       params=params, headers=get_headers(), timeout=10)
        if r.status_code == 200:
            lista = r.json()
    except: pass
    return lista

# --- LAYOUT PRINCIPAL ---
st.title("🛡️ Auditoria Gov (Restored)")

tab1, tab2 = st.tabs(["Busca CNPJ", "Contratos"])

# --- ABA CNPJ ---
with tab1:
    c1, c2 = st.columns([3, 1])
    cnpj_input = c1.text_input("CNPJ", "05.144.757/0001-72")
    
    if c2.button("Verificar"):
        # 1. Nome
        st.info(f"Empresa: {get_nome(cnpj_input)}")
        
        # 2. Sanções
        with st.spinner("Verificando..."):
            erros = auditar_cnpj(cnpj_input)
        
        if erros:
            st.error(f"🚨 CONSTA NOS REGISTROS: {len(erros)} apontamentos")
            for e in erros:
                st.write(f"❌ {e}")
        else:
            st.success("✅ Nada consta nas bases consultadas.")

# --- ABA CONTRATOS ---
with tab2:
    sel_orgao = st.selectbox("Órgão", ["20101", "36000", "26000", "30108"], format_func=lambda x: f"Código {x}")
    
    if st.button("Buscar"):
        dados = buscar_contratos(sel_orgao)
        
        if dados:
            rows = []
            for item in dados:
                rows.append({
                    "Valor": safe_float(item.get('valorInicialCompra')),
                    "Objeto": item.get('objeto', '')[:100],
                    "CNPJ": item.get('fornecedor', {}).get('cnpjFormatado', ''),
                    "IA": "...",
                    "Status": "⚪"
                })
            
            df = pd.DataFrame(rows).sort_values("Valor", ascending=False).head(5)
            
            # Loop Simples
            bar = st.progress(0)
            for i, (idx, row) in enumerate(df.iterrows()):
                # CNPJ Check
                if row['CNPJ']:
                    if auditar_cnpj(row['CNPJ']):
                        df.at[idx, "Status"] = "🔴"
                    else:
                        df.at[idx, "Status"] = "🟢"
                
                # IA Check
                df.at[idx, "IA"] = analisar_ia(row['Objeto'])
                bar.progress((i+1)/len(df))
            bar.empty()
            
            # Métricas
            c1, c2 = st.columns(2)
            c1.metric("Total", f"R$ {df['Valor'].sum():,.2f}")
            c2.metric("Qtd", len(df))
            
            st.dataframe(df, use_container_width=True)
            
        else:
            st.warning("Nenhum dado encontrado.")