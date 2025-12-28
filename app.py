import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import time
import os
from dotenv import load_dotenv
import google.generativeai as genai

# --- CONFIGURAÇÃO INICIAL ---
st.set_page_config(page_title="GovAudit Pro + IA", page_icon="⚖️", layout="wide")
load_dotenv()

# Recupera chaves
PORTAL_KEY = os.getenv("PORTAL_KEY")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")

# Configuração da IA
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)
else:
    st.warning("⚠️ Chave GEMINI_API_KEY ausente.")

# --- CSS ---
st.markdown("""
    <style>
        .block-container {padding-top: 2rem;}
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        .stDataFrame {font-size: 0.9rem;}
    </style>
""", unsafe_allow_html=True)

# --- ÓRGÃOS ---
ORGAOS_SIAFI = {
    "Secretaria-Geral Presidência (Planalto)": "20101",
    "Ministério da Saúde": "36000",
    "Ministério da Educação": "26000",
    "DNIT (Transportes)": "39252",
    "Polícia Federal": "30108",
    "Comando do Exército": "52121",
    "Ministério da Justiça": "30000"
}

# --- FUNÇÕES ---
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

# --- AUDITORIA CNPJ ---
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

# --- IA GEMINI (MODO DEBUG) ---
def analisar_contrato_ia(objeto_texto):
    if not GEMINI_KEY: return "⚠️ S/ Chave"
    if not objeto_texto or len(objeto_texto) < 5: return "⚪ Vazio"
    
    try:
        # Prompt Curto e Direto
        prompt = f"""
        Analise este objeto de contrato público: "{objeto_texto}"
        Responda APENAS: 'ALTO RISCO', 'MÉDIO RISCO' ou 'BAIXO RISCO'.
        """
        
        # Trocamos para 'gemini-pro' que é mais estável se o 'flash' falhar
        model = genai.GenerativeModel('gemini-pro')
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        # MODO DEBUG: Retorna o erro exato para lermos na tela
        erro = str(e)
        if "404" in erro: return "Erro: Modelo ñ achado"
        if "429" in erro: return "Erro: Cota Excedida"
        if "API_KEY" in erro: return "Erro: Chave Inválida"
        return f"Erro: {erro[:20]}..." # Mostra o começo do erro técnico

# --- BUSCA CONTRATOS ---
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
st.title("🛡️ Auditoria Gov Federal + IA (V46.3 Debug)")
st.markdown("---")

aba1, aba2 = st.tabs(["🕵️ Auditoria (CNPJ)", "💰 Monitor + IA"])

# --- ABA 1 ---
with aba1:
    st.header("Verificação de Antecedentes")
    c1, c2 = st.columns([4, 1])
    cnpj_in = c1.text_input("CNPJ:", value="05.144.757/0001-72")
    c2.write(""); c2.write("")
    if c2.button("🔍 Verificar", type="primary"):
        with st.spinner("Checando Receita e Sanções..."):
            try:
                r_receita = requests.get(f"https://minhareceita.org/{limpar_string(cnpj_in)}", timeout=5)
                if r_receita.status_code == 200:
                    d = r_receita.json()
                    st.info(f"🏢 **{d.get('razao_social')}**")
            except: pass

            sancoes = auditar_cnpj_gov(cnpj_in)
            st.divider()
            if sancoes: 
                st.error(f"🚨 **RISCO: {len(sancoes)} REGISTROS**")
                for s in sancoes: st.write(f"⚠️ {s['_origem']}: {s.get('motivo','Sem detalhes')}")
            else: st.success("✅ NADA CONSTA")

# --- ABA 2 ---
with aba2:
    st.header("Análise de Contratos + Parecer IA")
    col_org, col_ia = st.columns([3, 1])
    orgao = col_org.selectbox("Órgão:", list(ORGAOS_SIAFI.keys()))
    usar_ia = col_ia.checkbox("Ativar IA", value=True)
    
    if st.button("🔎 Buscar"):
        raw = buscar_contratos(ORGAOS_SIAFI[orgao])
        if raw:
            tabela = []
            for item in raw:
                val = safe_float(item.get('valorInicialCompra') or item.get('valorFinalCompra'))
                tabela.append({
                    "Valor": val,
                    "Objeto": item.get('objeto', 'N/A'),
                    "CNPJ": item.get('fornecedor', {}).get('cnpjFormatado', ''),
                    "Parecer IA": "⚪ Aguardando",
                    "CNPJ Status": "⚪"
                })
            
            df = pd.DataFrame(tabela).sort_values("Valor", ascending=False).head(7) # Pegar top 7
            
            # IA PROCESSAMENTO
            if usar_ia:
                st.info("🧠 IA Analisando (Modelo: Gemini-Pro)...")
                bar_ia = st.progress(0)
                
                for i, idx in enumerate(df.index):
                    # CNPJ
                    cnpj = df.at[idx, "CNPJ"]
                    if cnpj: df.at[idx, "CNPJ Status"] = checar_antecedentes(cnpj)
                    
                    # IA
                    txt = df.at[idx, "Objeto"]
                    df.at[idx, "Parecer IA"] = analisar_contrato_ia(txt)
                    
                    bar_ia.progress(int((i+1)/len(df)*100))
                    time.sleep(1)
                bar_ia.empty()

            # ESTILIZAÇÃO
            def cor_parecer(v):
                v = str(v).upper()
                if "ALTO" in v: return 'background-color: #ffcccc; color: #900'
                if "ERRO" in v: return 'background-color: #ffffcc; color: #333' # Amarelo se der erro
                if "BAIXO" in v: return 'color: green'
                return ''

            st.dataframe(
                df.style.applymap(cor_parecer, subset=['Parecer IA'])
                        .format({"Valor": "R$ {:,.2f}"}),
                use_container_width=True
            )
        else: st.warning("Sem dados.")