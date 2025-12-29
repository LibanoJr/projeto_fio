import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import time
import os
from dotenv import load_dotenv
import google.generativeai as genai
from google.api_core import exceptions

# ---------------- CONFIG ----------------
load_dotenv()

def get_secret(k):
    return os.getenv(k) or st.secrets.get(k)

PORTAL_KEY = get_secret("PORTAL_KEY")
GEMINI_KEY = get_secret("GEMINI_API_KEY")

IA_ATIVA = False
if GEMINI_KEY:
    try:
        genai.configure(api_key=GEMINI_KEY)
        IA_ATIVA = True
    except:
        pass

st.set_page_config("GovAudit Pro", "⚖️", layout="wide")

# ---------------- UTILS ----------------
def get_headers():
    return {"chave-api-dados": PORTAL_KEY, "Accept": "application/json"}

def limpar_string(t):
    return "".join(c for c in str(t) if c.isdigit())

def safe_float(v):
    try: return float(v)
    except: return 0.0

def moeda(v):
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def data_br(d):
    try: return datetime.strptime(d, "%Y-%m-%d").strftime("%d/%m/%Y")
    except: return ""

# ---------------- NOME EMPRESA ----------------
@st.cache_data(ttl=86400)
def buscar_nome_empresa(cnpj):
    try:
        r = requests.get(
            "https://api.portaldatransparencia.gov.br/api-de-dados/empresas",
            params={"cnpj": limpar_string(cnpj)},
            headers=get_headers(),
            timeout=5
        )
        if r.status_code == 200 and r.json():
            return r.json()[0].get("nomeEmpresarial", "")
    except:
        pass
    return "Nome não disponível na base pública"

# ---------------- SANÇÕES ----------------
@st.cache_data(ttl=3600)
def checar_sancoes(cnpj):
    raiz = limpar_string(cnpj)[:8]
    bases = ["ceis", "cnep", "acordos-leniencia"]

    for b in bases:
        try:
            r = requests.get(
                f"https://api.portaldatransparencia.gov.br/api-de-dados/{b}",
                params={"cnpjSancionado": limpar_string(cnpj)},
                headers=get_headers(),
                timeout=5
            )
            if r.status_code == 200:
                for i in r.json():
                    c = limpar_string(
                        i.get("sancionado", {}).get("codigoFormatado", "")
                    )
                    if c.startswith(raiz) or b == "acordos-leniencia":
                        return True
        except:
            pass
    return False

# ---------------- IA ----------------
def risco_ia(obj):
    if not IA_ATIVA or not obj:
        return "INDEFINIDO"
    try:
        model = genai.GenerativeModel("gemini-2.0-flash")
        r = model.generate_content(
            f"Classifique o risco como ALTO, MÉDIO ou BAIXO:\n{obj}"
        )
        return r.text.strip().upper()
    except exceptions.ResourceExhausted:
        return "INDEFINIDO"
    except:
        return "INDEFINIDO"

# ---------------- CONTRATOS ----------------
def buscar_contratos(orgao):
    fim = datetime.now()
    ini = fim - timedelta(days=730)
    lista = []

    for p in range(1, 10):
        r = requests.get(
            "https://api.portaldatransparencia.gov.br/api-de-dados/contratos",
            params={
                "codigoOrgao": orgao,
                "dataInicial": ini.strftime("%d/%m/%Y"),
                "dataFinal": fim.strftime("%d/%m/%Y"),
                "pagina": p
            },
            headers=get_headers(),
            timeout=10
        )
        if r.status_code != 200 or not r.json():
            break
        lista.extend(r.json())

    return lista

# ---------------- UI ----------------
st.title("🛡️ GovAudit Pro")

aba1, aba2 = st.tabs(["🕵️ Checagem CNPJ", "📊 Auditoria Contratual"])

# -------- ABA CNPJ --------
with aba1:
    cnpj = st.text_input("CNPJ Alvo:", "05.144.757/0001-72")
    if st.button("Verificar"):
        nome = buscar_nome_empresa(cnpj)
        st.info(f"🏢 **Empresa:** {nome}")

        if checar_sancoes(cnpj):
            st.error("🚨 SANÇÕES ENCONTRADAS")
        else:
            st.success("✅ NADA CONSTA")

# -------- ABA CONTRATOS --------
with aba2:
    ORGAOS = {"Secretaria-Geral Presidência (Planalto)": "20101"}
    orgao = st.selectbox("Órgão:", ORGAOS.keys())

    if st.button("Auditar"):
        contratos = buscar_contratos(ORGAOS[orgao])

        contratos.sort(
            key=lambda x: safe_float(
                x.get("valorFinalCompra") or x.get("valorInicialCompra")
            ),
            reverse=True
        )

        top_10 = contratos[:10]
        tabela = []
        total = 0

        bar = st.progress(0, text="Auditando contratos...")

        for i, c in enumerate(contratos):
            val = safe_float(c.get("valorFinalCompra") or c.get("valorInicialCompra"))
            total += val

            cnpj = c.get("fornecedor", {}).get("cnpjFormatado", "")
            nome = c.get("fornecedor", {}).get("nome", "")

            risco = ""
            status = ""

            if c in top_10:
                risco = risco_ia(c.get("objeto", "")[:120])
                status = "🚨 ALERTA" if checar_sancoes(cnpj) else "🟢 OK"
                time.sleep(1)

            tabela.append({
                "Data": data_br(c.get("dataAssinatura")),
                "Empresa": nome,
                "CNPJ": cnpj,
                "Valor": moeda(val),
                "Risco IA": risco,
                "Status CNPJ": status
            })

            bar.progress((i + 1) / len(contratos))

        bar.empty()

        df = pd.DataFrame(tabela)

        st.metric("Contratos", len(contratos))
        st.metric("Total Analisado", moeda(total))

        st.dataframe(df, use_container_width=True)