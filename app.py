import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import os
import google.generativeai as genai
from dotenv import load_dotenv

# --- 1. CONFIGURAÇÃO ---
load_dotenv()

def get_secret(key_name):
    val = os.getenv(key_name)
    if val: return val
    if hasattr(st, "secrets") and key_name in st.secrets:
        return st.secrets[key_name]
    return None

PORTAL_KEY = get_secret("PORTAL_KEY")
GEMINI_KEY = get_secret("GEMINI_API_KEY")

IA_ATIVA = False
if GEMINI_KEY:
    try:
        genai.configure(api_key=GEMINI_KEY)
        IA_ATIVA = True
    except Exception as e:
        print(f"Erro IA: {e}")

st.set_page_config(page_title="GovAudit Pro", page_icon="⚖️", layout="wide")

# --- CSS ---
st.markdown("""
    <style>
        .block-container {padding-top: 2rem;}
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        .stButton > button {width: 100%; margin-top: 29px;}
        [data-testid="stMetricValue"] {font-size: 1.5rem;}
    </style>
""", unsafe_allow_html=True)

# --- FUNÇÕES ÚTEIS ---
def formatar_moeda_br(valor):
    if not valor: return "R$ 0,00"
    texto = f"R$ {valor:,.2f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")

def formatar_data_br(data_iso):
    if not data_iso: return ""
    try: return datetime.strptime(data_iso, "%Y-%m-%d").strftime("%d/%m/%Y")
    except: return data_iso

def get_headers():
    return {"chave-api-dados": PORTAL_KEY, "Accept": "application/json"}

def limpar_string(texto):
    if not texto: return ""
    return "".join([c for c in str(texto) if c.isdigit()])

def safe_float(valor):
    try: return float(valor)
    except: return 0.0

# --- CONSULTA NOME (BRASIL API) ---
@st.cache_data(ttl=86400)
def buscar_dados_receita(cnpj):
    cnpj_limpo = limpar_string(cnpj)
    if not cnpj_limpo: return None, None
    try:
        url = f"https://brasilapi.com.br/api/cnpj/v1/{cnpj_limpo}"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            dados = resp.json()
            return dados.get('razao_social', ''), dados.get('nome_fantasia', '')
    except: pass
    return None, None

# --- AUDITORIA CNPJ ---
@st.cache_data(ttl=3600)
def auditar_cnpj_detalhado(cnpj_alvo):
    resultados = []
    razao, fantasia = buscar_dados_receita(cnpj_alvo)
    nome_exibicao = razao if razao else "Nome não encontrado"
    if fantasia: nome_exibicao += f" ({fantasia})"
    
    if not PORTAL_KEY: return [], nome_exibicao
    
    cnpj_limpo = limpar_string(cnpj_alvo)
    raiz_alvo = cnpj_limpo[:8]
    bases = {"acordos-leniencia": "Acordo Leniência", "ceis": "Inidôneos (CEIS)", "cnep": "Punidos (CNEP)"}
    
    for endpoint, nome_base in bases.items():
        try:
            url = f"https://api.portaldatransparencia.gov.br/api-de-dados/{endpoint}"
            params = {"cnpjSancionado": cnpj_limpo, "pagina": 1}
            resp = requests.get(url, params=params, headers=get_headers(), timeout=5)
            if resp.status_code == 200:
                for item in resp.json():
                    if 'sancionado' in item or 'pessoa' in item: # Validação básica
                        item['_origem'] = nome_base
                        resultados.append(item)
        except: pass
        
    return resultados, nome_exibicao

def checar_risco_simples(cnpj):
    res, _ = auditar_cnpj_detalhado(cnpj)
    return True if len(res) > 0 else False

# --- IA EM LOTE (1 CHAMADA SÓ = VELOCIDADE MÁXIMA) ---
def analisar_lote_ia(lista_objetos):
    if not IA_ATIVA or not lista_objetos:
        return ["IA OFF"] * len(lista_objetos)
    
    # Monta um prompt único com todos os itens
    texto_lote = ""
    for i, obj in enumerate(lista_objetos):
        texto_lote += f"Item {i}: {obj}\n"
        
    prompt = f"""Analise a lista de objetos de contratos públicos abaixo quanto ao risco de corrupção ou imprecisão.
    Retorne APENAS uma lista separada por ponto e vírgula (;) com a classificação de cada um na ordem exata (ALTO, MÉDIO ou BAIXO).
    Não explique, apenas classifique.
    
    {texto_lote}"""
    
    try:
        model = genai.GenerativeModel('gemini-2.0-flash')
        response = model.generate_content(prompt)
        text = response.text.strip().replace("\n", "").replace(".", "")
        classificacoes = [x.strip().upper() for x in text.split(";")]
        
        # Garante que o tamanho da lista bate
        if len(classificacoes) < len(lista_objetos):
            classificacoes.extend(["ERRO"] * (len(lista_objetos) - len(classificacoes)))
        return classificacoes[:len(lista_objetos)]
        
    except Exception as e:
        return ["ERRO CONEXÃO"] * len(lista_objetos)

# --- BUSCA CONTRATOS ---
ORGAOS_SIAFI = {
    "Planalto": "20101", "Saúde": "36000", "Educação": "26000", 
    "DNIT": "39252", "Polícia Federal": "30108", "Justiça": "30000"
}

def buscar_contratos(codigo_orgao):
    if not PORTAL_KEY: return []
    lista = []
    dt_fim = datetime.now()
    dt_ini = dt_fim - timedelta(days=730) # 2 anos
    
    with st.spinner("Buscando dados no Portal da Transparência..."):
        for i in range(1, 4):
            try:
                params = {"dataInicial": dt_ini.strftime("%d/%m/%Y"), "dataFinal": dt_fim.strftime("%d/%m/%Y"), "codigoOrgao": codigo_orgao, "pagina": i}
                r = requests.get("https://api.portaldatransparencia.gov.br/api-de-dados/contratos", params=params, headers=get_headers(), timeout=10)
                if r.status_code == 200:
                    dados = r.json()
                    if not dados: break
                    lista.extend(dados)
                else: break
            except: break
    return lista

# --- UI PRINCIPAL ---
st.title("🛡️ GovAudit Pro - Turbo")

aba1, aba2 = st.tabs(["🕵️ CNPJ", "📊 Contratos (Lote)"])

with aba1:
    st.header("Checagem de Antecedentes")
    col1, col2 = st.columns([4, 1])
    # VOLTADO PARA O CNPJ ORIGINAL
    cnpj_input = col1.text_input("CNPJ Alvo:", value="05.144.757/0001-72") 
    
    if col2.button("Verificar", type="primary"):
        with st.spinner("Consultando bases..."):
            sancoes, nome = auditar_cnpj_detalhado(cnpj_input)
        
        st.subheader(f"🏢 {nome}")
        if sancoes:
            st.error(f"🚨 {len(sancoes)} SANÇÕES ENCONTRADAS")
            for s in sancoes:
                st.write(f"❌ **{s.get('_origem')}**: {s.get('motivo', 'Sem motivo')}")
        else:
            st.success("✅ Nada consta (CEIS/CNEP/Leniência)")

with aba2:
    st.header("Auditoria em Massa (IA Otimizada)")
    c1, c2 = st.columns([3,1])
    orgao = c1.selectbox("Órgão:", list(ORGAOS_SIAFI.keys()))
    usar_ia = c2.toggle("Ativar IA (Modo Rápido)", value=True)
    
    if st.button("Analisar Contratos"):
        raw = buscar_contratos(ORGAOS_SIAFI[orgao])
        if raw:
            # Pega os top 10 maiores valores
            raw.sort(key=lambda x: safe_float(x.get('valorInicialCompra')), reverse=True)
            top_10 = raw[:10]
            
            # PREPARAÇÃO PARA IA (LOTE)
            lista_objetos = [item.get('objeto', 'Indefinido')[:200] for item in top_10]
            riscos_ia = ["-"] * len(top_10)
            
            if usar_ia:
                with st.spinner("IA processando todos os itens de uma vez..."):
                    riscos_ia = analisar_lote_ia(lista_objetos)
            
            tabela = []
            total_val = 0
            
            for i, item in enumerate(top_10):
                val = safe_float(item.get('valorInicialCompra'))
                total_val += val
                cnpj = item.get('fornecedor', {}).get('cnpjFormatado', '')
                
                status_cnpj = "🟢 OK"
                if cnpj and checar_risco_simples(cnpj): status_cnpj = "🚨 ALERTA"
                
                tabela.append({
                    "Valor": formatar_moeda_br(val),
                    "Objeto": item.get('objeto', '')[:100] + "...",
                    "CNPJ": cnpj,
                    "Risco IA": riscos_ia[i],
                    "Status CNPJ": status_cnpj
                })
            
            # EXIBIÇÃO
            m1, m2 = st.columns(2)
            m1.metric("Total Analisado", formatar_moeda_br(total_val))
            m2.metric("Contratos", len(top_10))
            
            df = pd.DataFrame(tabela)
            
            def cor_risco(val):
                color = 'green'
                if 'ALTO' in str(val): color = 'red'
                elif 'MÉDIO' in str(val): color = 'orange'
                return f'color: {color}; font-weight: bold'

            st.dataframe(
                df.style.applymap(cor_risco, subset=['Risco IA']),
                use_container_width=True, hide_index=True
            )
        else:
            st.warning("Nenhum contrato encontrado.")