import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import time
import os
from dotenv import load_dotenv
import google.generativeai as genai

# ================= CONFIG =================
load_dotenv()

PORTAL_KEY = os.getenv("PORTAL_KEY")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")

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
[data-testid="stMetricValue"] {font-size: 1.4rem;}
</style>
""", unsafe_allow_html=True)

# ================= UTIL =================
def limpar_cnpj(cnpj):
    return "".join(c for c in str(cnpj) if c.isdigit())

def formatar_moeda(v):
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def formatar_data(d):
    if not d:
        return ""
    try:
        return datetime.strptime(d, "%Y-%m-%d").strftime("%d/%m/%Y")
    except:
        return d

def safe_float(v):
    try:
        return float(v)
    except:
        return 0.0

# ================= CNPJ (BRASILAPI) =================
def buscar_empresa_cnpj(cnpj):
    try:
        r = requests.get(
            f"https://brasilapi.com.br/api/cnpj/v1/{limpar_cnpj(cnpj)}",
            timeout=8
        )
        if r.status_code == 200:
            j = r.json()
            return j.get("razao_social") or j.get("nome_fantasia")
    except:
        pass
    return "Nome não informado nesta base"

# ================= SANÇÕES (CORRIGIDO) =================
def get_headers():
    return {"chave-api-dados": PORTAL_KEY, "Accept": "application/json"}

def checar_sancoes(cnpj):
    if not PORTAL_KEY:
        return False

    cnpj_limpo = limpar_cnpj(cnpj)
    if len(cnpj_limpo) != 14:
        return False

    hoje = datetime.now().date()
    bases = ["ceis", "cnep"]

    for base in bases:
        pagina = 1
        while True:
            try:
                r = requests.get(
                    f"https://api.portaldatransparencia.gov.br/api-de-dados/{base}",
                    params={
                        "cnpjSancionado": cnpj_limpo,
                        "pagina": pagina
                    },
                    headers=get_headers(),
                    timeout=10
                )

                if r.status_code != 200:
                    break

                dados = r.json()
                if not dados:
                    break

                for item in dados:
                    sanc = item.get("sancionado") or {}
                    cnpj_api = limpar_cnpj(sanc.get("codigoFormatado", ""))

                    if cnpj_api != cnpj_limpo:
                        continue

                    inicio = item.get("dataInicioSancao")
                    fim = item.get("dataFimSancao")

                    if not inicio or not fim:
                        continue

                    try:
                        dt_ini = datetime.strptime(inicio, "%Y-%m-%d").date()
                        dt_fim = datetime.strptime(fim, "%Y-%m-%d").date()
                    except:
                        continue

                    if dt_ini <= hoje <= dt_fim:
                        return True

                pagina += 1
            except:
                break

    return False

# ================= RISCO =================
def risco_heuristico(texto):
    t = texto.lower()
    if len(t) < 60:
        return "ALTO"
    if any(p in t for p in ["prestação de serviços", "consultoria", "assessoria"]):
        return "MÉDIO"
    return "BAIXO"

def risco_ia(texto):
    if not IA_ATIVA or not texto:
        return None
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        r = model.generate_content(
            f"Classifique o risco do contrato abaixo. Responda apenas com ALTO, MÉDIO ou BAIXO.\n\nObjeto: {texto}"
        )
        resp = r.text.strip().upper()
        if resp in ["ALTO", "MÉDIO", "BAIXO"]:
            return resp
    except:
        pass
    return None

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

aba1, aba2 = st.tabs(["🕵️ Checagem CNPJ", "📊 Auditoria Contratual"])

with aba1:
    st.header("Consulta de Empresa")

    cnpj_input = st.text_input("CNPJ:")
    buscar = st.button("Buscar CNPJ")

    if buscar:
        st.divider()

        cnpj_limpo = limpar_cnpj(cnpj_input)
        nome = buscar_empresa_cnpj(cnpj_input)

        st.write(f"🏢 **Empresa:** {nome}")

        resultado = "🟢 Nada consta"

        if len(cnpj_limpo) == 14:
            if checar_sancoes(cnpj_limpo):
                resultado = "🚨 Sanções encontradas"

        st.markdown(f"### {resultado}")

with aba2:
    st.header("Análise de Contratos")

    ORGAOS = {
        "Secretaria-Geral da Presidência": "20101",
        "Ministério da Saúde": "36000",
        "Ministério da Educação": "26000",
        "Ministério da Justiça": "30000",
        "Polícia Federal": "30108",
    }

    orgao = st.selectbox("Órgão:", ORGAOS.keys())

    if st.button("Auditar"):
        contratos = buscar_contratos(ORGAOS[orgao])
        contratos.sort(
            key=lambda x: safe_float(x.get("valorInicialCompra") or x.get("valorFinalCompra")),
            reverse=True
        )

        top10 = contratos[:10]
        tabela = []
        total = 0

        bar = st.progress(0, text="Analisando riscos...")
        for i, c in enumerate(contratos):
            valor = safe_float(c.get("valorInicialCompra") or c.get("valorFinalCompra"))
            total += valor

            fornecedor = c.get("fornecedor", {})
            nome = fornecedor.get("nome", "")
            cnpj = fornecedor.get("cnpjFormatado", "")
            objeto = c.get("objeto", "")[:150]

            risco = ""
            status = ""

            if c in top10:
                risco = risco_ia(objeto) or risco_heuristico(objeto)
                status = "🚨 ALERTA" if checar_sancoes(cnpj) else "🟢 OK"

            tabela.append({
                "Data": formatar_data(c.get("dataAssinatura")),
                "Empresa": nome,
                "CNPJ": cnpj,
                "Valor": formatar_moeda(valor),
                "Objeto": objeto,
                "Risco": risco,
                "Status CNPJ": status
            })

            bar.progress((i + 1) / len(contratos))

        bar.empty()

        df = pd.DataFrame(tabela)

        c1, c2, c3 = st.columns(3)
        c1.metric("Total Analisado", formatar_moeda(total))
        c2.metric("Contratos", len(contratos))
        c3.metric("Riscos Altos", len(df[df["Risco"] == "ALTO"]))

        st.dataframe(df, use_container_width=True)