import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import time
import os
from dotenv import load_dotenv
import google.generativeai as genai
from google.api_core import exceptions

# ================= CONFIG =================
load_dotenv()

def get_secret(key):
    v = os.getenv(key)
    if v:
        return v
    if key in st.secrets:
        return st.secrets[key]
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

# ================= CSS =================
st.markdown("""
<style>
.block-container {padding-top: 2rem;}
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
[data-testid="stMetricValue"] {font-size: 1.5rem;}
</style>
""", unsafe_allow_html=True)

# ================= UTIL =================
def limpar_num(v):
    return "".join(c for c in str(v) if c.isdigit())

def safe_float(v):
    try:
        return float(v)
    except:
        return 0.0

def formatar_moeda(v):
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def formatar_data(d):
    if not d:
        return ""
    try:
        return datetime.strptime(d, "%Y-%m-%d").strftime("%d/%m/%Y")
    except:
        return d

# ================= ORGÃOS (COMPLETOS) =================
ORGAOS_SIAFI = {
    "Secretaria-Geral da Presidência da República (Planalto)": "20101",
    "Ministério da Saúde": "36000",
    "Ministério da Educação": "26000",
    "Ministério da Justiça e Segurança Pública": "30000",
    "Departamento Nacional de Infraestrutura de Transportes (DNIT)": "39252",
    "Polícia Federal": "30108",
    "Comando do Exército": "52121"
}

# ================= HEADERS =================
def get_headers():
    return {"chave-api-dados": PORTAL_KEY, "Accept": "application/json"}

# ================= CNPJ DETALHADO =================
@st.cache_data(ttl=3600)
def auditar_cnpj_detalhado(cnpj):
    resultados = []
    if not PORTAL_KEY:
        return []

    cnpj_limpo = limpar_num(cnpj)
    if len(cnpj_limpo) != 14:
        return []

    bases = {
        "ceis": "Cadastro de Inidôneos (CEIS)",
        "cnep": "Cadastro de Empresas Punidas (CNEP)",
        "acordos-leniencia": "Acordos de Leniência"
    }

    for endpoint, nome_base in bases.items():
        try:
            r = requests.get(
                f"https://api.portaldatransparencia.gov.br/api-de-dados/{endpoint}",
                params={"cnpjSancionado": cnpj_limpo, "pagina": 1},
                headers=get_headers(),
                timeout=6
            )
            if r.status_code == 200:
                for item in r.json():
                    item["_origem"] = nome_base
                    resultados.append(item)
        except:
            pass

    return resultados

# ================= RISCO =================
def risco_heuristico(texto):
    t = texto.lower()
    if len(t) < 60:
        return "ALTO"
    if any(x in t for x in ["prestação de serviços", "consultoria", "apoio técnico", "assessoria"]):
        return "MÉDIO"
    return "BAIXO"

def risco_ia_com_fallback(texto):
    if not texto:
        return "ALTO"

    if IA_ATIVA:
        try:
            model = genai.GenerativeModel("gemini-2.0-flash")
            r = model.generate_content(
                f"Classifique o risco do contrato. Responda apenas ALTO, MÉDIO ou BAIXO.\nObjeto: {texto}"
            )
            resp = r.text.strip().upper()
            if resp in ["ALTO", "MÉDIO", "BAIXO"]:
                return resp
        except:
            pass

    return risco_heuristico(texto)

# ================= CONTRATOS =================
def buscar_contratos(orgao):
    lista = []
    fim = datetime.now()
    ini = fim - timedelta(days=730)

    bar = st.progress(0, text="Buscando contratos...")
    for i in range(1, 6):
        try:
            r = requests.get(
                "https://api.portaldatransparencia.gov.br/api-de-dados/contratos",
                params={
                    "codigoOrgao": orgao,
                    "dataInicial": ini.strftime("%d/%m/%Y"),
                    "dataFinal": fim.strftime("%d/%m/%Y"),
                    "pagina": i
                },
                headers=get_headers(),
                timeout=10
            )
            if r.status_code != 200 or not r.json():
                break
            lista.extend(r.json())
            bar.progress(i / 5)
        except:
            break
    bar.empty()
    return lista

# ================= INTERFACE =================
st.title("🛡️ GovAudit Pro")

aba_auditoria, aba_cnpj = st.tabs([
    "📊 Auditoria Contratual",
    "🕵️ Checagem de CNPJ"
])

# ================= AUDITORIA =================
with aba_auditoria:
    orgao = st.selectbox("Órgão:", ORGAOS_SIAFI.keys())

    if st.button("Auditar"):
        contratos = buscar_contratos(ORGAOS_SIAFI[orgao])

        contratos.sort(
            key=lambda x: safe_float(x.get("valorInicialCompra") or x.get("valorFinalCompra")),
            reverse=True
        )

        top10 = contratos[:10]
        tabela = []
        total = 0

        for c in contratos:
            valor = safe_float(c.get("valorInicialCompra") or c.get("valorFinalCompra"))
            total += valor

            forn = c.get("fornecedor", {})
            nome = forn.get("nome", "")
            cnpj = forn.get("cnpjFormatado", "")
            objeto = c.get("objeto", "")[:150]

            risco = ""
            status = ""

            if c in top10:
                risco = risco_ia_com_fallback(objeto)
                status = "🚨 ALERTA" if auditar_cnpj_detalhado(cnpj) else "🟢 OK"

            tabela.append({
                "Data": formatar_data(c.get("dataAssinatura")),
                "Empresa": nome,
                "CNPJ": cnpj,
                "Valor": formatar_moeda(valor),
                "Objeto": objeto,
                "Risco": risco,
                "Status CNPJ": status
            })

        df = pd.DataFrame(tabela)

        c1, c2, c3 = st.columns(3)
        c1.metric("Total", formatar_moeda(total))
        c2.metric("Contratos", len(contratos))
        c3.metric("Riscos Altos", len(df[df["Risco"] == "ALTO"]))

        st.dataframe(df, use_container_width=True)

# ================= CNPJ =================
with aba_cnpj:
    st.header("Checagem de CNPJ")
    cnpj_input = st.text_input("CNPJ:")

    if st.button("Verificar"):
        res = auditar_cnpj_detalhado(cnpj_input)
        if res:
            st.error(f"🚨 {len(res)} OCORRÊNCIA(S) ENCONTRADA(S)")
            for r in res:
                st.write(f"• {r['_origem']}")
        else:
            st.success("🟢 NADA CONSTA")