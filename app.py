import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import os
import google.generativeai as genai
from dotenv import load_dotenv

# --- 1. CONFIGURAÇÃO (SECRETS) ---
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
    except: pass

st.set_page_config(page_title="GovAudit Pro", page_icon="⚖️", layout="wide")

# --- 2. CSS ---
st.markdown("""
    <style>
        .block-container {padding-top: 2rem;}
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        .stButton > button {width: 100%; margin-top: 29px;}
        [data-testid="stMetricValue"] {font-size: 1.5rem;}
    </style>
""", unsafe_allow_html=True)

# --- 3. UTILITÁRIOS ---
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

# --- 4. CONSULTA NOME (BRASIL API) ---
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

# --- 5. AUDITORIA CNPJ (COM TRAVA DE SEGURANÇA) ---
@st.cache_data(ttl=3600)
def auditar_cnpj_detalhado(cnpj_alvo):
    resultados = []
    
    # Busca nome
    razao, fantasia = buscar_dados_receita(cnpj_alvo)
    nome_exibicao = razao if razao else "Empresa não identificada"
    if fantasia: nome_exibicao += f" ({fantasia})"
    
    if not PORTAL_KEY: return [], nome_exibicao
    
    cnpj_limpo_alvo = limpar_string(cnpj_alvo)
    # Bases: CEIS, CNEP e Acordos
    bases = {"acordos-leniencia": "Acordo Leniência", "ceis": "Inidôneos (CEIS)", "cnep": "Punidos (CNEP)"}
    
    for endpoint, nome_base in bases.items():
        try:
            url = f"https://api.portaldatransparencia.gov.br/api-de-dados/{endpoint}"
            params = {"cnpjSancionado": cnpj_limpo_alvo, "pagina": 1}
            
            resp = requests.get(url, params=params, headers=get_headers(), timeout=8)
            
            if resp.status_code == 200:
                itens = resp.json()
                for item in itens:
                    # --- TRAVA DE SEGURANÇA RÍGIDA ---
                    # Verifica se o CNPJ que veio da API é REALMENTE o que pedimos
                    cnpj_retornado = ""
                    try:
                        if 'sancionado' in item:
                            cnpj_retornado = item['sancionado'].get('codigoFormatado', '')
                        elif 'pessoa' in item:
                            cnpj_retornado = item['pessoa'].get('cnpjFormatado', '')
                    except: pass
                    
                    # Só adiciona se o número bater exatamente
                    if limpar_string(cnpj_retornado) == cnpj_limpo_alvo:
                        item['_origem'] = nome_base
                        resultados.append(item)
        except: pass
        
    return resultados, nome_exibicao

def checar_risco_simples(cnpj):
    res, _ = auditar_cnpj_detalhado(cnpj)
    return True if len(res) > 0 else False

# --- 6. IA EM LOTE (MODELO ESTÁVEL 1.5) ---
def analisar_lote_ia(lista_objetos):
    if not IA_ATIVA or not lista_objetos:
        return ["IA OFF"] * len(lista_objetos)
    
    texto_lote = ""
    for i, obj in enumerate(lista_objetos):
        texto_lote += f"Item {i}: {obj}\n"
        
    prompt = f"""Classifique os itens abaixo APENAS como: 'ALTO', 'MÉDIO' ou 'BAIXO' quanto a risco de imprecisão ou corrupção.
    Responda em uma linha única separada por ponto e vírgula (;). Exemplo: ALTO; BAIXO; MÉDIO.
    
    {texto_lote}"""
    
    try:
        # VOLTANDO PARA O MODELO ESTÁVEL (1.5)
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)
        
        if not response.text: return ["ERRO VAZIO"] * len(lista_objetos)
            
        text = response.text.strip().replace("\n", "").replace(".", "")
        classificacoes = [x.strip().upper() for x in text.split(";")]
        
        # Ajuste de tamanho
        if len(classificacoes) < len(lista_objetos):
            diff = len(lista_objetos) - len(classificacoes)
            classificacoes.extend(["-"] * diff)
            
        return classificacoes[:len(lista_objetos)]
        
    except Exception as e:
        # Retorna o erro no primeiro item para debug visual se precisar
        return [f"ERRO: {str(e)[:15]}"] + ["ERRO"] * (len(lista_objetos)-1)

# --- 7. BUSCA CONTRATOS ---
ORGAOS_SIAFI = {
    "Planalto": "20101", "Saúde": "36000", "Educação": "26000", 
    "DNIT": "39252", "Polícia Federal": "30108", "Justiça": "30000"
}

def buscar_contratos(codigo_orgao):
    if not PORTAL_KEY: return []
    lista = []
    dt_fim = datetime.now()
    dt_ini = dt_fim - timedelta(days=730)
    
    with st.spinner("Buscando contratos..."):
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

# --- 8. UI ---
st.title("🛡️ GovAudit Pro - Correção Final")

aba1, aba2 = st.tabs(["🕵️ CNPJ", "📊 Contratos"])

with aba1:
    st.header("Checagem de Antecedentes")
    col1, col2 = st.columns([4, 1])
    cnpj_input = col1.text_input("CNPJ Alvo:", value="05.144.757/0001-72")
    
    if col2.button("Verificar", type="primary"):
        sancoes, nome = auditar_cnpj_detalhado(cnpj_input)
        
        st.subheader(f"🏢 {nome}")
        if sancoes:
            st.error(f"🚨 {len(sancoes)} REGISTROS CONFIRMADOS")
            for s in sancoes:
                origem = s.get('_origem', 'Sanção')
                motivo = s.get('motivo', 'Motivo não detalhado na base')
                data = s.get('dataInicioSancao', '')
                st.write(f"❌ **{origem}** {data}: {motivo}")
        else:
            st.success("✅ NADA CONSTA (CEIS, CNEP, LENIÊNCIA)")
            st.caption("Verificação realizada com filtro estrito de CNPJ.")

with aba2:
    st.header("Auditoria IA")
    c1, c2 = st.columns([3,1])
    orgao = c1.selectbox("Órgão:", list(ORGAOS_SIAFI.keys()))
    usar_ia = c2.toggle("Ativar IA (v1.5 Stable)", value=True)
    
    if st.button("Analisar"):
        raw = buscar_contratos(ORGAOS_SIAFI[orgao])
        if raw:
            raw.sort(key=lambda x: safe_float(x.get('valorInicialCompra')), reverse=True)
            top_10 = raw[:10]
            
            objs = [item.get('objeto', 'Indefinido')[:200] for item in top_10]
            
            riscos = ["-"] * len(top_10)
            if usar_ia:
                with st.spinner("IA Analisando risco..."):
                    riscos = analisar_lote_ia(objs)
            
            tabela = []
            total = 0
            for i, item in enumerate(top_10):
                v = safe_float(item.get('valorInicialCompra'))
                total += v
                c_cnpj = item.get('fornecedor', {}).get('cnpjFormatado', '')
                
                status_c = "🟢"
                if c_cnpj and checar_risco_simples(c_cnpj): status_c = "🚨"
                
                tabela.append({
                    "Valor": formatar_moeda_br(v),
                    "Risco": riscos[i],
                    "CNPJ": f"{status_c} {c_cnpj}",
                    "Objeto": item.get('objeto', '')[:100]
                })
                
            st.metric("Total", formatar_moeda_br(total))
            st.dataframe(pd.DataFrame(tabela), use_container_width=True)
        else:
            st.warning("Sem dados.")