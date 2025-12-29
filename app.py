import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import time
import os
from dotenv import load_dotenv
import google.generativeai as genai
from google.api_core import exceptions

# --- 1. CONFIGURAÇÃO ---
load_dotenv()

def get_secret(key_name):
    val = os.getenv(key_name)
    if val:
        return val
    if key_name in st.secrets:
        return st.secrets[key_name]
    return None

PORTAL_KEY = get_secret("PORTAL_KEY")
GEMINI_KEY = get_secret("GEMINI_API_KEY")

IA_ATIVA = False
if GEMINI_KEY:
    try:
        genai.configure(api_key=GEMINI_KEY)
        IA_ATIVA = True
    except:
        IA_ATIVA = False

st.set_page_config(page_title="GovAudit Pro", page_icon="⚖️", layout="wide")

# --- CSS VISUAL ---
st.markdown("""
    <style>
        .block-container {padding-top: 2rem;}
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        .stButton > button {width: 100%; margin-top: 29px;}
        [data-testid="stMetricValue"] {font-size: 1.5rem;}
    </style>
""", unsafe_allow_html=True)

# --- FUNÇÕES DE FORMATAÇÃO ---
def formatar_moeda_br(valor):
    if not valor:
        return "R$ 0,00"
    texto = f"R$ {valor:,.2f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")

def formatar_data_br(data_iso):
    if not data_iso:
        return ""
    try:
        data_obj = datetime.strptime(data_iso, "%Y-%m-%d")
        return data_obj.strftime("%d/%m/%Y")
    except:
        return data_iso

# --- DADOS ---
ORGAOS_SIAFI = {
    "Secretaria-Geral Presidência (Planalto)": "20101",
    "Ministério da Saúde": "36000",
    "Ministério da Educação": "26000",
    "DNIT (Transportes)": "39252",
    "Polícia Federal": "30108",
    "Comando do Exército": "52121",
    "Ministério da Justiça": "30000"
}

# --- FUNÇÕES DE BUSCA ---
def get_headers():
    return {
        "chave-api-dados": PORTAL_KEY,
        "Accept": "application/json"
    }

def limpar_string(texto):
    if not texto:
        return ""
    return "".join([c for c in str(texto) if c.isdigit()])

def safe_float(valor):
    try:
        return float(valor)
    except:
        return 0.0

# --- AUDITORIA CNPJ ---
@st.cache_data(ttl=3600)
def auditar_cnpj_detalhado(cnpj_alvo):
    resultados = []
    if not PORTAL_KEY:
        return []

    cnpj_limpo = limpar_string(cnpj_alvo)
    raiz_alvo = cnpj_limpo[:8]

    bases = {
        "acordos-leniencia": "Acordo Leniência",
        "ceis": "Inidôneos (CEIS)",
        "cnep": "Punidos (CNEP)"
    }

    for endpoint, nome_base in bases.items():
        try:
            url = f"https://api.portaldatransparencia.gov.br/api-de-dados/{endpoint}"
            params = {
                "cnpjSancionado": cnpj_limpo,
                "pagina": 1
            }
            resp = requests.get(url, params=params, headers=get_headers(), timeout=5)

            if resp.status_code == 200:
                itens = resp.json()
                for item in itens:
                    match = False
                    cnpj_item = ""

                    try:
                        sancionado = item.get('sancionado', {})
                        cnpj_item = sancionado.get('codigoFormatado') or item.get('pessoa', {}).get('cnpjFormatado')
                    except:
                        pass

                    if cnpj_item and limpar_string(cnpj_item)[:8] == raiz_alvo:
                        match = True
                    elif nome_base == "Acordo Leniência" and not cnpj_item:
                        match = True

                    if match:
                        item['_origem'] = nome_base
                        resultados.append(item)
        except:
            pass

    return resultados

def checar_risco_simples(cnpj):
    res = auditar_cnpj_detalhado(cnpj)
    return True if len(res) > 0 else False

# --- FUNÇÃO IA (CORRIGIDA E SEGURA) ---
def analisar_objeto_ia(objeto_texto):
    global IA_ATIVA

    if not IA_ATIVA:
        return "INDEFINIDO"

    if not objeto_texto:
        return "INDEFINIDO"

    try:
        model = genai.GenerativeModel('gemini-2.0-flash')

        prompt = f"""
        Analise o objeto de um contrato público.
        Responda APENAS com: ALTO, MÉDIO ou BAIXO.

        Considere ALTO se for genérico ou suspeito.

        Objeto: "{objeto_texto}"
        """

        response = model.generate_content(prompt)
        return response.text.strip().upper()

    except exceptions.ResourceExhausted:
        IA_ATIVA = False
        return "INDEFINIDO"

    except:
        return "INDEFINIDO"

# --- BUSCA CONTRATOS ---
def buscar_contratos(codigo_orgao):
    if not PORTAL_KEY:
        return []

    lista = []
    dt_fim = datetime.now()
    dt_ini = dt_fim - timedelta(days=730)

    bar = st.progress(0, text="Buscando contratos...")

    for i in range(1, 4):
        try:
            params = {
                "dataInicial": dt_ini.strftime("%d/%m/%Y"),
                "dataFinal": dt_fim.strftime("%d/%m/%Y"),
                "codigoOrgao": codigo_orgao,
                "pagina": i
            }
            r = requests.get(
                "https://api.portaldatransparencia.gov.br/api-de-dados/contratos",
                params=params,
                headers=get_headers(),
                timeout=10
            )

            if r.status_code == 200:
                dados = r.json()
                if not dados:
                    break
                lista.extend(dados)
            else:
                break
        except:
            break

        bar.progress(i * 33)

    bar.empty()
    return lista

# --- INTERFACE ---
st.title("🛡️ Auditoria Gov Federal + IA")

aba1, aba2 = st.tabs(["🕵️ Checagem CNPJ", "📊 Auditoria Contratual"])

# --- ABA 1 ---
with aba1:
    st.header("Antecedentes do Fornecedor")
    col1, col2 = st.columns([4, 1])

    cnpj_input = col1.text_input("CNPJ Alvo:", value="05.144.757/0001-72")

    if col2.button("Verificar", type="primary"):
        sancoes = auditar_cnpj_detalhado(cnpj_input)

        if sancoes:
            st.error(f"🚨 {len(sancoes)} SANÇÕES ENCONTRADAS")
            for s in sancoes:
                st.write(f"""
                ❌ **{s['_origem']}**  
                Base oficial: Portal da Transparência
                """)
        else:
            st.success("✅ NADA CONSTA")

# --- ABA 2 ---
with aba2:
    st.header("Análise de Riscos")

    c1, c2 = st.columns([3, 1])
    orgao = c1.selectbox("Órgão:", list(ORGAOS_SIAFI.keys()))
    usar_ia = c2.toggle("Ativar IA", value=True)

    if st.button("Auditar"):
        raw = buscar_contratos(ORGAOS_SIAFI[orgao])

        if raw:
            raw.sort(
                key=lambda x: safe_float(x.get('valorInicialCompra') or x.get('valorFinalCompra')),
                reverse=True
            )

            top_10 = raw[:10]
            tabela = []
            total_val = 0

            bar = st.progress(0, text="Processando análise...")

            for i, item in enumerate(top_10):
                val = safe_float(item.get('valorInicialCompra') or item.get('valorFinalCompra'))
                total_val += val

                cnpj = item.get('fornecedor', {}).get('cnpjFormatado', '')
                obj = item.get('objeto', '')[:120]

                risco_ia = "INDEFINIDO"
                if usar_ia:
                    risco_ia = analisar_objeto_ia(obj)
                    time.sleep(1)

                status_cnpj = "🟢 OK"
                if cnpj and checar_risco_simples(cnpj):
                    status_cnpj = "🚨 ALERTA"

                tabela.append({
                    "Data": formatar_data_br(item.get('dataAssinatura')),
                    "Valor": formatar_moeda_br(val),
                    "Objeto": obj,
                    "CNPJ": cnpj,
                    "Risco IA": risco_ia,
                    "Status CNPJ": status_cnpj
                })

                bar.progress((i + 1) / len(top_10))

            bar.empty()

            df = pd.DataFrame(tabela)

            m1, m2, m3 = st.columns(3)
            m1.metric("Total Analisado", formatar_moeda_br(total_val))
            m2.metric("Contratos", len(raw))

            try:
                riscos = len(df[df['Risco IA'].str.contains("ALTO")])
                m3.metric("Riscos Altos", riscos, delta_color="inverse")
            except:
                m3.metric("Riscos Altos", 0)

            def style_risk(v):
                if "ALTO" in str(v):
                    return 'color: red; font-weight: bold'
                if "MÉDIO" in str(v):
                    return 'color: orange'
                if "BAIXO" in str(v):
                    return 'color: green'
                if "INDEFINIDO" in str(v):
                    return 'color: gray'
                return ''

            def style_cnpj(v):
                if "ALERTA" in str(v):
                    return 'color: red; font-weight: bold'
                return 'color: green'

            st.dataframe(
                df.style
                .applymap(style_risk, subset=['Risco IA'])
                .applymap(style_cnpj, subset=['Status CNPJ']),
                use_container_width=True,
                hide_index=True
            )

        else:
            st.warning("Sem dados para este órgão.")