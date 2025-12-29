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

# --- 5. AUDITORIA CNPJ (LÓGICA RAIZ - IGUAL LOCALHOST) ---
@st.cache_data(ttl=3600)
def auditar_cnpj_detalhado(cnpj_alvo):
    resultados = []
    
    razao, fantasia = buscar_dados_receita(cnpj_alvo)
    nome_exibicao = razao if razao else "Empresa não identificada"
    if fantasia: nome_exibicao += f" ({fantasia})"
    
    if not PORTAL_KEY: return [], nome_exibicao
    
    # PEGA A RAIZ (8 DÍGITOS) - ISSO QUE FAZIA FUNCIONAR NO LOCALHOST
    cnpj_limpo = limpar_string(cnpj_alvo)
    raiz_alvo = cnpj_limpo[:8] 
    
    bases = {"acordos-leniencia": "Acordo Leniência", "ceis": "Inidôneos (CEIS)", "cnep": "Punidos (CNEP)"}
    
    for endpoint, nome_base in bases.items():
        try:
            # Busca pelo CNPJ completo para filtrar na API
            url = f"https://api.portaldatransparencia.gov.br/api-de-dados/{endpoint}"
            params = {"cnpjSancionado": cnpj_limpo, "pagina": 1}
            
            # Se não achar pelo completo, tenta buscar pela raiz (para Leniência/Odebrecht geralmente precisa)
            # Mas a API do governo às vezes exige completo. Vamos manter a busca original e filtrar a resposta.
            
            resp = requests.get(url, params=params, headers=get_headers(), timeout=10)
            
            if resp.status_code == 200:
                itens = resp.json()
                for item in itens:
                    # EXTRAI O CNPJ DO ITEM RETORNADO
                    cnpj_item = ""
                    try:
                        if 'sancionado' in item:
                            cnpj_item = item['sancionado'].get('codigoFormatado', '')
                        elif 'pessoa' in item:
                            cnpj_item = item['pessoa'].get('cnpjFormatado', '')
                    except: pass
                    
                    # COMPARA APENAS A RAIZ (8 DIGITOS)
                    # Isso garante que se voce buscar a Filial 0001 e a sanção for na Matriz, ele acha.
                    # E elimina os "fantasmas" aleatórios que não tem nada a ver.
                    if limpar_string(cnpj_item)[:8] == raiz_alvo:
                        item['_origem'] = nome_base
                        resultados.append(item)
                        
        except: pass
        
    return resultados, nome_exibicao

def checar_risco_simples(cnpj):
    res, _ = auditar_cnpj_detalhado(cnpj)
    return True if len(res) > 0 else False

# --- 6. IA (MODELO PADRÃO 'gemini-pro') ---
def analisar_lote_ia(lista_objetos):
    if not IA_ATIVA or not lista_objetos:
        return ["IA OFF"] * len(lista_objetos)
    
    texto_lote = ""
    for i, obj in enumerate(lista_objetos):
        texto_lote += f"Item {i}: {obj}\n"
        
    prompt = f"""Analise a lista e classifique o risco de corrupção ou imprecisão APENAS como: 'ALTO', 'MÉDIO' ou 'BAIXO'.
    Retorne apenas as palavras separadas por ponto e vírgula (;). Exemplo: ALTO; BAIXO; MÉDIO
    
    {texto_lote}"""
    
    try:
        # USA O GEMINI-PRO (MODELO CLÁSSICO E ESTÁVEL)
        model = genai.GenerativeModel('gemini-pro')
        response = model.generate_content(prompt)
        
        if not response.text: return ["ERRO"] * len(lista_objetos)
            
        text = response.text.strip().replace("\n", "").replace(".", "")
        classificacoes = [x.strip().upper() for x in text.split(";")]
        
        if len(classificacoes) < len(lista_objetos):
            diff = len(lista_objetos) - len(classificacoes)
            classificacoes.extend(["-"] * diff)
            
        return classificacoes[:len(lista_objetos)]
        
    except Exception as e:
        return [f"ERRO IA"] * len(lista_objetos)

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
st.title("🛡️ GovAudit Pro - Stable")

aba1, aba2 = st.tabs(["🕵️ CNPJ", "📊 Contratos"])

with aba1:
    st.header("Checagem de Antecedentes")
    col1, col2 = st.columns([4, 1])
    # NOVONOR PARA TESTE
    cnpj_input = col1.text_input("CNPJ Alvo:", value="05.144.757/0001-72")
    
    if col2.button("Verificar", type="primary"):
        sancoes, nome = auditar_cnpj_detalhado(cnpj_input)
        
        st.subheader(f"🏢 {nome}")
        if sancoes:
            st.error(f"🚨 {len(sancoes)} SANÇÕES ENCONTRADAS")
            for s in sancoes:
                origem = s.get('_origem', 'Sanção')
                motivo = s.get('motivo', 'Motivo não detalhado na base')
                data = s.get('dataInicioSancao', 'Data N/A')
                st.write(f"❌ **{origem}** ({data}): {motivo}")
        else:
            st.success("✅ NADA CONSTA")

with aba2:
    st.header("Auditoria IA")
    c1, c2 = st.columns([3,1])
    orgao = c1.selectbox("Órgão:", list(ORGAOS_SIAFI.keys()))
    usar_ia = c2.toggle("Ativar IA", value=True)
    
    if st.button("Analisar"):
        raw = buscar_contratos(ORGAOS_SIAFI[orgao])
        if raw:
            raw.sort(key=lambda x: safe_float(x.get('valorInicialCompra')), reverse=True)
            top_10 = raw[:10]
            
            objs = [item.get('objeto', 'Indefinido')[:200] for item in top_10]
            riscos = ["-"] * len(top_10)
            
            if usar_ia:
                with st.spinner("IA Auditando..."):
                    riscos = analisar_lote_ia(objs)
            
            tabela = []
            total = 0
            for i, item in enumerate(top_10):
                v = safe_float(item.get('valorInicialCompra'))
                total += v
                c_cnpj = item.get('fornecedor', {}).get('cnpjFormatado', '')
                
                status_c = "🟢"
                # Verifica risco usando a mesma lógica da raiz
                if c_cnpj and checar_risco_simples(c_cnpj): status_c = "🚨"
                
                tabela.append({
                    "Valor": formatar_moeda_br(v),
                    "Risco": riscos[i],
                    "CNPJ": f"{status_c} {c_cnpj}",
                    "Objeto": item.get('objeto', '')[:100]
                })
                
            st.metric("Total", formatar_moeda_br(total))
            
            def colorir_risco(val):
                color = 'white'
                if 'ALTO' in str(val): color = 'red'
                elif 'MÉDIO' in str(val): color = 'orange'
                elif 'BAIXO' in str(val): color = 'green'
                return f'color: {color}; font-weight: bold'

            st.dataframe(pd.DataFrame(tabela).style.applymap(colorir_risco, subset=['Risco']), use_container_width=True)
        else:
            st.warning("Sem dados.")