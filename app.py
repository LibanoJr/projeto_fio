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
        pass

st.set_page_config(
    page_title="GovAudit Pro",
    page_icon="⚖️",
    layout="wide"
)

# --- CSS ---
st.markdown("""
<style>
.block-container { padding-top: 2rem; }
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
.stButton > button { width: 100%; margin-top: 29px; }
[data-testid="stMetricValue"] { font-size: 1.5rem; }
</style>
""", unsafe_allow_html=True)

# --- FUNÇÕES AUX ---
def formatar_moeda_br(valor):
    if not valor:
        return "R$ 0,00"
    texto = f"R$ {valor:,.2f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")

def formatar_data_br(data_iso):
    if not data_iso:
        return ""
    try:
        return datetime.strptime(data_iso, "%Y-%m-%d").strftime("%d/%m/%Y")
    except:
        return data_iso

def limpar_string(texto):
    if not texto:
        return ""
    return "".join(c for c in str(texto) if c.isdigit())

def safe_float(valor):
    try:
        return float(valor)
    except:
        return 0.0

def get_headers():
    return {
        "chave-api-dados": PORTAL_KEY,
        "Accept": "application/json"
    }

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

# --- SANÇÕES ---
@st.cache_data(ttl=3600)
def auditar_cnpj_detalhado(cnpj_alvo):
    if not PORTAL_KEY:
        return []

    resultados = []
    cnpj_limpo = limpar_string(cnpj_alvo)
    raiz = cnpj_limpo[:8]

    bases = {
        "ceis": "CEIS – Inidôneos",
        "cnep": "CNEP – Punidos",
        "acordos-leniencia": "Acordos de Leniência"
    }

    for endpoint, nome in bases.items():
        try:
            url = f"https://api.portaldatransparencia.gov.br/api-de-dados/{endpoint}"
            params = {"cnpjSancionado": cnpj_limpo, "pagina": 1}
            r = requests.get(url, headers=get_headers(), params=params, timeout=8)

            if r.status_code != 200:
                continue

            for item in r.json():
                cnpj_item = ""
                try:
                    sancionado = item.get("sancionado", {})
                    cnpj_item = sancionado.get("codigoFormatado")
                except:
                    pass

                if cnpj_item and limpar_string(cnpj_item)[:8] == raiz:
                    item["_origem"] = nome
                    resultados.append(item)

        except:
            pass

    return resultados

def checar_risco_simples(cnpj):
    return len(auditar_cnpj_detalhado(cnpj)) > 0

# --- IA ---
def analisar_objeto_ia(texto):
    if not IA_ATIVA:
        return "IA OFF"
    if not texto:
        return "Vazio"

    try:
        model = genai.GenerativeModel("gemini-2.0-flash")
        prompt = f"""
Analise o objeto de um contrato público.
Responda APENAS: ALTO, MÉDIO ou BAIXO.

Objeto: "{texto}"
"""
        resp = model.generate_content(prompt)
        return resp.text.strip().upper()
    except exceptions.ResourceExhausted:
        return "COTA"
    except:
        return "ERRO"

# --- CONTRATOS ---
def buscar_contratos(cod_orgao):
    if not PORTAL_KEY:
        return []

    lista = []
    fim = datetime.now()
    ini = fim - timedelta(days=730)

    bar = st.progress(0, text="Buscando contratos...")
    for p in range(1, 4):
        try:
            params = {
                "codigoOrgao": cod_orgao,
                "dataInicial": ini.strftime("%d/%m/%Y"),
                "dataFinal": fim.strftime("%d/%m/%Y"),
                "pagina": p
            }
            r = requests.get(
                "https://api.portaldatransparencia.gov.br/api-de-dados/contratos",
                headers=get_headers(),
                params=params,
                timeout=10
            )
            if r.status_code != 200:
                break

            dados = r.json()
            if not dados:
                break

            lista.extend(dados)
            bar.progress(p / 3)
        except:
            break

    bar.empty()
    return lista

# =========================
# INTERFACE
# =========================
st.title("🛡️ GovAudit Pro")

# 👉 ORDEM CORRETA
aba_auditoria, aba_cnpj = st.tabs([
    "📊 Auditoria Contratual",
    "🕵️ Checagem de CNPJ"
])

# =========================
# ABA 1 — AUDITORIA
# =========================
with aba_auditoria:
    st.header("Auditoria de Contratos Federais")

    c1, c2 = st.columns([3, 1])
    orgao = c1.selectbox("Órgão:", ORGAOS_SIAFI.keys())
    usar_ia = c2.toggle("Ativar IA", value=True)

    if st.button("Auditar"):
        contratos = buscar_contratos(ORGAOS_SIAFI[orgao])

        if not contratos:
            st.warning("Sem contratos encontrados.")
        else:
            contratos.sort(
                key=lambda x: safe_float(x.get("valorFinalCompra") or x.get("valorInicialCompra")),
                reverse=True
            )
            top = contratos[:10]

            linhas = []
            total = 0

            bar = st.progress(0, text="Analisando...")
            for i, c in enumerate(top):
                valor = safe_float(c.get("valorFinalCompra") or c.get("valorInicialCompra"))
                total += valor

                cnpj = c.get("fornecedor", {}).get("cnpjFormatado", "")
                objeto = (c.get("objeto") or "")[:120]

                risco = analisar_objeto_ia(objeto) if usar_ia else "OFF"
                status = "🚨 ALERTA" if cnpj and checar_risco_simples(cnpj) else "🟢 OK"

                linhas.append({
                    "Data": formatar_data_br(c.get("dataAssinatura")),
                    "Valor": formatar_moeda_br(valor),
                    "Objeto": objeto,
                    "CNPJ": cnpj,
                    "Risco IA": risco,
                    "Status CNPJ": status
                })

                bar.progress((i + 1) / len(top))
                time.sleep(0.5)

            bar.empty()

            df = pd.DataFrame(linhas)

            m1, m2, m3 = st.columns(3)
            m1.metric("Total Analisado", formatar_moeda_br(total))
            m2.metric("Contratos", len(contratos))
            m3.metric("Risco Alto", len(df[df["Risco IA"] == "ALTO"]))

            st.dataframe(df, use_container_width=True, hide_index=True)

# =========================
# ABA 2 — CNPJ
# =========================
with aba_cnpj:
    st.header("Checagem de Antecedentes")

    col1, col2 = st.columns([4, 1])
    cnpj_input = col1.text_input("CNPJ:", value="")
    if col2.button("Verificar", type="primary"):
        sancoes = auditar_cnpj_detalhado(cnpj_input)

        if sancoes:
            st.error(f"🚨 {len(sancoes)} ocorrência(s) encontrada(s)")
            for s in sancoes:
                st.write(f"❌ {s['_origem']}")
        else:
            st.success("🟢 Nada consta")