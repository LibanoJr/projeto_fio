# =========================
# CÓDIGO COMPLETO AJUSTADO
# =========================

import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import time
import os
from dotenv import load_dotenv
import google.generativeai as genai
from google.api_core import exceptions

load_dotenv()

def get_secret(key_name):
    return os.getenv(key_name) or st.secrets.get(key_name)

PORTAL_KEY = get_secret("PORTAL_KEY")
GEMINI_KEY = get_secret("GEMINI_API_KEY")

IA_ATIVA = False
if GEMINI_KEY:
    try:
        genai.configure(api_key=GEMINI_KEY)
        IA_ATIVA = True
    except:
        IA_ATIVA = False

st.set_page_config("GovAudit Pro", "⚖️", layout="wide")

# -------------------------
# UTILIDADES
# -------------------------
def get_headers():
    return {"chave-api-dados": PORTAL_KEY, "Accept": "application/json"}

def limpar_string(txt):
    return "".join(c for c in str(txt) if c.isdigit())

def safe_float(v):
    try:
        return float(v)
    except:
        return 0.0

def formatar_moeda_br(v):
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def formatar_data_br(d):
    try:
        return datetime.strptime(d, "%Y-%m-%d").strftime("%d/%m/%Y")
    except:
        return ""

# -------------------------
# BUSCAR NOME DA EMPRESA
# -------------------------
@st.cache_data(ttl=86400)
def buscar_nome_empresa(cnpj):
    if not PORTAL_KEY:
        return ""

    try:
        url = "https://api.portaldatransparencia.gov.br/api-de-dados/empresas"
        params = {"cnpj": limpar_string(cnpj)}
        r = requests.get(url, params=params, headers=get_headers(), timeout=5)

        if r.status_code == 200:
            dados = r.json()
            if dados:
                return dados[0].get("nomeEmpresarial", "")
    except:
        pass
    return ""

# -------------------------
# SANÇÕES
# -------------------------
@st.cache_data(ttl=3600)
def auditar_cnpj_detalhado(cnpj):
    resultados = []
    raiz = limpar_string(cnpj)[:8]

    bases = {
        "acordos-leniencia": "Acordo de Leniência",
        "ceis": "CEIS",
        "cnep": "CNEP"
    }

    for ep, nome in bases.items():
        try:
            r = requests.get(
                f"https://api.portaldatransparencia.gov.br/api-de-dados/{ep}",
                params={"cnpjSancionado": limpar_string(cnpj)},
                headers=get_headers(),
                timeout=5
            )

            if r.status_code == 200:
                for item in r.json():
                    cnpj_item = limpar_string(
                        item.get("sancionado", {}).get("codigoFormatado", "")
                    )
                    if cnpj_item.startswith(raiz) or nome == "Acordo de Leniência":
                        item["_origem"] = nome
                        resultados.append(item)
        except:
            pass

    return resultados

def checar_risco_simples(cnpj):
    return len(auditar_cnpj_detalhado(cnpj)) > 0

# -------------------------
# IA
# -------------------------
def analisar_objeto_ia(obj):
    if not IA_ATIVA or not obj:
        return "INDEFINIDO"
    try:
        model = genai.GenerativeModel("gemini-2.0-flash")
        r = model.generate_content(
            f"Classifique o risco do contrato como ALTO, MÉDIO ou BAIXO:\n{obj}"
        )
        return r.text.strip().upper()
    except exceptions.ResourceExhausted:
        return "INDEFINIDO"
    except:
        return "INDEFINIDO"

# -------------------------
# CONTRATOS
# -------------------------
def buscar_contratos(orgao):
    lista = []
    fim = datetime.now()
    ini = fim - timedelta(days=730)

    for p in range(1, 10):
        try:
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
        except:
            break
    return lista

# -------------------------
# INTERFACE
# -------------------------
st.title("🛡️ GovAudit Pro")

aba1, aba2 = st.tabs(["Checagem CNPJ", "Auditoria Contratos"])

with aba1:
    cnpj = st.text_input("CNPJ:", "05.144.757/0001-72")
    if st.button("Verificar"):
        nome = buscar_nome_empresa(cnpj)
        sancoes = auditar_cnpj_detalhado(cnpj)

        if nome:
            st.info(f"🏢 **Empresa:** {nome}")

        if sancoes:
            st.error(f"🚨 {len(sancoes)} sanções encontradas")
            for s in sancoes:
                st.write(f"❌ {s['_origem']}")
        else:
            st.success("✅ Nada consta")

with aba2:
    ORGAOS = {
        "Secretaria-Geral Presidência (Planalto)": "20101"
    }

    orgao = st.selectbox("Órgão", ORGAOS.keys())

    if st.button("Auditar"):
        contratos = buscar_contratos(ORGAOS[orgao])

        tabela = []
        total = 0

        for item in contratos:
            val = safe_float(item.get("valorFinalCompra"))
            total += val

            cnpj = item.get("fornecedor", {}).get("cnpjFormatado", "")
            nome = buscar_nome_empresa(cnpj)

            tabela.append({
                "Data": formatar_data_br(item.get("dataAssinatura")),
                "Empresa": nome,
                "CNPJ": cnpj,
                "Valor": formatar_moeda_br(val),
                "Risco IA": analisar_objeto_ia(item.get("objeto", "")[:120]),
                "Status CNPJ": "🚨 ALERTA" if checar_risco_simples(cnpj) else "🟢 OK"
            })

        df = pd.DataFrame(tabela)

        st.metric("Contratos", len(contratos))
        st.metric("Total", formatar_moeda_br(total))

        st.dataframe(df, use_container_width=True)