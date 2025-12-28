import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import time
import os
from dotenv import load_dotenv
import google.generativeai as genai

# --- CONFIGURAÇÃO INICIAL E SEGURANÇA ---
st.set_page_config(page_title="GovAudit Pro + IA", page_icon="🤖", layout="wide")
load_dotenv() # Carrega variáveis do arquivo .env

# Recupera chaves de forma segura
PORTAL_KEY = os.getenv("PORTAL_KEY")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")

# Configuração da IA (Google Gemini)
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)
else:
    st.warning("⚠️ Chave GEMINI_API_KEY não encontrada no arquivo .env. A IA não funcionará.")

# --- CSS (Visual Polido) ---
st.markdown("""
    <style>
        .block-container {padding-top: 2rem;}
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        .stDataFrame {font-size: 0.9rem;}
    </style>
""", unsafe_allow_html=True)

# --- LISTA DE ÓRGÃOS ---
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
    resultados = []  # Variável criada em PORTUGUÊS
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
        
    return resultados # CORRIGIDO: Retornando a variável correta (antes estava 'results')

def checar_antecedentes(cnpj):
    res = auditar_cnpj_gov(cnpj)
    return "🔴 ALERTA" if len(res) > 0 else "🟢 OK"

# --- FUNÇÃO 2: ANÁLISE SEMÂNTICA COM IA (GEMINI) ---
def analisar_contrato_ia(objeto_texto):
    if not GEMINI_KEY: return "⚠️ S/ Chave"
    if not objeto_texto or len(objeto_texto) < 10: return "⚪ Insuficiente"
    
    try:
        # Prompt Otimizado para o TCC
        prompt = f"""
        Você é um auditor de conformidade pública. Analise o seguinte Objeto de Contrato:
        "{objeto_texto}"
        
        Classifique o risco de corrupção ou irregularidade baseada na descrição.
        Responda APENAS com uma das etiquetas abaixo:
        'ALTO RISCO' (se for muito genérico ou atípico)
        'MÉDIO RISCO' (se for vago mas comum)
        'BAIXO RISCO' (se for específico e claro)
        """
        
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return "⚠️ Erro IA"

# --- FUNÇÃO DE BUSCA (CONTRATOS) ---
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
st.title("🤖 GovAudit Pro + IA Gemini")
st.markdown("---")

aba1, aba2 = st.tabs(["🕵️ Auditoria (CNPJ)", "💰 Monitor + Inteligência Artificial"])

# --- ABA 1 ---
with aba1:
    st.header("Verificação de Antecedentes (Base Governamental)")
    c1, c2 = st.columns([4, 1])
    cnpj_in = c1.text_input("CNPJ:", value="05.144.757/0001-72")
    c2.write(""); c2.write("")
    if c2.button("🔍 Verificar", type="primary", use_container_width=True):
        with st.spinner("Consultando bases de sanções..."):
            sancoes = auditar_cnpj_gov(cnpj_in)
            st.divider()
            if sancoes: 
                st.error(f"🚨 **RISCO DETECTADO: {len(sancoes)} REGISTROS**")
                for s in sancoes:
                    st.write(f"⚠️ **{s['_origem']}**: {s.get('motivo') or 'Sem motivo detalhado'}")
            else:
                st.success("✅ **NADA CONSTA**")

# --- ABA 2 ---
with aba2:
    st.header("Análise Híbrida: Dados + IA Generativa")
    
    col_org, col_ia = st.columns([3, 1])
    orgao = col_org.selectbox("Órgão:", list(ORGAOS_SIAFI.keys()))
    usar_ia = col_ia.checkbox("Ativar Análise IA", value=True, help="Usa Google Gemini para ler os contratos")
    
    if st.button("🔎 Buscar e Analisar"):
        raw = buscar_contratos(ORGAOS_SIAFI[orgao])
        
        if raw:
            tabela = []
            total = 0.0
            
            # Prepara dados iniciais
            for item in raw:
                val = safe_float(item.get('valorInicialCompra') or item.get('valorFinalCompra'))
                total += val
                tabela.append({
                    "Data": formatar_data_br(item.get('dataAssinatura')),
                    "Valor": val,
                    "Fornecedor": item.get('fornecedor', {}).get('nome', 'N/A')[:30],
                    "CNPJ": item.get('fornecedor', {}).get('cnpjFormatado', ''),
                    "Objeto": item.get('objeto', 'N/A'),
                    "CNPJ Status": "⚪",
                    "Parecer IA": "⚪ Off"
                })
            
            df = pd.DataFrame(tabela)
            
            # --- O GRANDE MOMENTO: PROCESSAMENTO IA ---
            if usar_ia:
                st.info("🧠 A IA está analisando os contratos de maior valor (Aguarde)...")
                
                # Ordena e pega os top 5
                df = df.sort_values("Valor", ascending=False)
                top_idx = df.head(5).index 
                
                bar_ia = st.progress(0, text="Iniciando Auditoria IA...")
                
                for i, idx in enumerate(top_idx):
                    # 1. Checa CNPJ (Governo)
                    cnpj_alvo = df.at[idx, "CNPJ"]
                    if cnpj_alvo:
                        df.at[idx, "CNPJ Status"] = checar_antecedentes(cnpj_alvo)
                    
                    # 2. Análise IA (Gemini)
                    texto_contrato = df.at[idx, "Objeto"]
                    parecer = analisar_contrato_ia(texto_contrato)
                    df.at[idx, "Parecer IA"] = parecer
                    
                    # Atualiza barra
                    progresso = int((i + 1) / len(top_idx) * 100)
                    bar_ia.progress(progresso, text=f"Analisando contrato {i+1}/{len(top_idx)}...")
                    time.sleep(1) # Delay de segurança para a API
                
                bar_ia.empty()

            # Exibição Final
            c1, c2 = st.columns(2)
            c1.metric("Total Analisado", f"R$ {total:,.2f}")
            c2.metric("Contratos Encontrados", len(df))
            
            # Cores Condicionais
            def cor_parecer(val):
                val = str(val).upper()
                if "ALTO" in val: return 'background-color: #ffcccc; color: #cc0000; font-weight: bold'
                if "BAIXO" in val: return 'color: green; font-weight: bold'
                if "MÉDIO" in val: return 'color: orange; font-weight: bold'
                return ''
                
            def cor_cnpj(val):
                if "ALERTA" in str(val): return 'color: red; font-weight: bold'
                if "OK" in str(val): return 'color: green; font-weight: bold'
                return ''

            st.dataframe(
                df.style.applymap(cor_parecer, subset=['Parecer IA'])
                        .applymap(cor_cnpj, subset=['CNPJ Status'])
                        .format({"Valor": "R$ {:,.2f}"}),
                use_container_width=True, hide_index=True
            )
        else:
            st.warning("Sem dados recentes para este órgão.")