import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import time
import os
from dotenv import load_dotenv
import google.generativeai as genai

# --- CONFIGURAÇÃO INICIAL E SEGURANÇA ---
st.set_page_config(page_title="GovAudit Pro + IA", page_icon="⚖️", layout="wide")
load_dotenv() # Carrega variáveis do arquivo .env

# Recupera chaves de forma segura
PORTAL_KEY = os.getenv("PORTAL_KEY")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")

# Configuração da IA (Google Gemini)
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)
else:
    # Aviso discreto no sidebar para não quebrar o layout
    st.sidebar.warning("⚠️ Chave GEMINI_API_KEY não encontrada no .env")

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

def checar_antecedentes(cnpj):
    res = auditar_cnpj_gov(cnpj)
    return "🔴 ALERTA" if len(res) > 0 else "🟢 OK"

# --- FUNÇÃO 2: ANÁLISE SEMÂNTICA COM IA (GEMINI) ---
def analisar_contrato_ia(objeto_texto):
    if not GEMINI_KEY: return "⚠️ S/ Chave"
    if not objeto_texto or len(objeto_texto) < 5: return "⚪ Vazio"
    
    try:
        # Prompt Otimizado
        prompt = f"""
        Você é um auditor. Analise o Objeto de Contrato abaixo e classifique o risco de 
        irregularidade/vaguidade. Responda APENAS: 'ALTO RISCO', 'MÉDIO RISCO' ou 'BAIXO RISCO'.
        Objeto: "{objeto_texto}"
        """
        
        # Tenta usar o modelo Flash (mais rápido e barato)
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        # Retorna o erro real para sabermos o que é (Ex: API Key invalida)
        erro_msg = str(e)
        if "API_KEY" in erro_msg: return "⚠️ Chave Inválida"
        if "429" in erro_msg: return "⚠️ Muitos Pedidos"
        return "⚠️ Erro Conexão"

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
st.title("🛡️ Auditoria Gov Federal + IA")
st.markdown("---")

aba1, aba2 = st.tabs(["🕵️ Auditoria (CNPJ)", "💰 Monitor + Inteligência Artificial"])

# --- ABA 1: CNPJ ---
with aba1:
    st.header("Verificação de Antecedentes (Base Governamental)")
    c1, c2 = st.columns([4, 1])
    cnpj_in = c1.text_input("CNPJ:", value="05.144.757/0001-72")
    c2.write(""); c2.write("") # Espaçador
    
    if c2.button("🔍 Verificar", type="primary", use_container_width=True):
        
        # 1. Recupera Nome da Empresa (Minha Receita) - RESTAURADO!
        with st.spinner("Buscando dados cadastrais..."):
            try:
                r_receita = requests.get(f"https://minhareceita.org/{limpar_string(cnpj_in)}", timeout=5)
                if r_receita.status_code == 200:
                    dados = r_receita.json()
                    razao = dados.get('razao_social', 'Nome não encontrado')
                    fantasia = dados.get('nome_fantasia', '')
                    nome_exibir = f"{razao} ({fantasia})" if fantasia else razao
                    st.info(f"🏢 **Empresa:** {nome_exibir}")
                else:
                    st.warning("⚠️ Não foi possível confirmar o nome da empresa na Receita Federal.")
            except:
                st.warning("⚠️ API da Receita Federal instável no momento.")

        # 2. Busca Sanções
        with st.spinner("Consultando listas de punidos (CEIS/CNEP)..."):
            sancoes = auditar_cnpj_gov(cnpj_in)
            st.divider()
            
            if sancoes: 
                st.error(f"🚨 **RISCO DETECTADO: {len(sancoes)} REGISTROS**")
                for s in sancoes:
                    st.write(f"⚠️ **{s['_origem']}**: {s.get('motivo') or s.get('situacaoAcordo') or 'Sem detalhes'}")
            else:
                st.success("✅ **NADA CONSTA** - Fornecedor sem sanções ativas.")

# --- ABA 2: CONTRATOS ---
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
            
            # --- PROCESSAMENTO IA ---
            if usar_ia:
                if not GEMINI_KEY:
                    st.error("❌ ERRO: Chave da IA não configurada no arquivo .env")
                else:
                    st.info("🧠 A IA está analisando os 5 maiores contratos...")
                    
                    df = df.sort_values("Valor", ascending=False)
                    top_idx = df.head(5).index 
                    
                    bar_ia = st.progress(0, text="Iniciando Auditoria IA...")
                    
                    for i, idx in enumerate(top_idx):
                        # 1. CNPJ
                        cnpj_alvo = df.at[idx, "CNPJ"]
                        if cnpj_alvo:
                            df.at[idx, "CNPJ Status"] = checar_antecedentes(cnpj_alvo)
                        
                        # 2. IA
                        texto = df.at[idx, "Objeto"]
                        parecer = analisar_contrato_ia(texto)
                        df.at[idx, "Parecer IA"] = parecer
                        
                        # Progresso
                        bar_ia.progress(int((i+1)/len(top_idx)*100), text=f"Analisando: {texto[:40]}...")
                        time.sleep(1) 
                    
                    bar_ia.empty()

            # Exibição
            c1, c2 = st.columns(2)
            c1.metric("Total Analisado", f"R$ {total:,.2f}")
            c2.metric("Contratos Encontrados", len(df))
            
            def cor_parecer(val):
                val = str(val).upper()
                if "ALTO" in val: return 'background-color: #ffcccc; color: #cc0000; font-weight: bold'
                if "BAIXO" in val: return 'color: green; font-weight: bold'
                if "MÉDIO" in val: return 'color: orange; font-weight: bold'
                if "ERRO" in val: return 'background-color: #eeeeee; color: #666666;'
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