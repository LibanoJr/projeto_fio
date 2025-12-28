import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import time
import os
from dotenv import load_dotenv
import google.generativeai as genai
from google.api_core import exceptions

# --- 1. CONFIGURAÇÃO E SEGURANÇA ---
load_dotenv()

def get_secret(key_name):
    val = os.getenv(key_name)
    if val: return val
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
    except: pass

st.set_page_config(page_title="GovAudit Pro", page_icon="⚖️", layout="wide")

# --- 2. CSS VISUAL ---
st.markdown("""
    <style>
        .block-container {padding-top: 2rem;}
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        .stButton > button {
            width: 100%;
            margin-top: 29px;
        }
    </style>
""", unsafe_allow_html=True)

# --- 3. DADOS AUXILIARES ---
ORGAOS_SIAFI = {
    "Secretaria-Geral Presidência (Planalto)": "20101",
    "Ministério da Saúde": "36000",
    "Ministério da Educação": "26000",
    "DNIT (Transportes)": "39252",
    "Polícia Federal": "30108",
    "Comando do Exército": "52121",
    "Ministério da Justiça": "30000"
}

# --- 4. FUNÇÕES DO SISTEMA ---
def get_headers():
    return {"chave-api-dados": PORTAL_KEY, "Accept": "application/json"}

def limpar_string(texto):
    if not texto: return ""
    return "".join([c for c in str(texto) if c.isdigit()])

def safe_float(valor):
    try: return float(valor)
    except: return 0.0

@st.cache_data(ttl=3600)
def auditar_cnpj_detalhado(cnpj_alvo):
    resultados = []
    if not PORTAL_KEY: return [] 
    
    cnpj_limpo = limpar_string(cnpj_alvo)
    raiz_alvo = cnpj_limpo[:8]
    bases = {"acordos-leniencia": "Acordo Leniência", "ceis": "Inidôneos (CEIS)", "cnep": "Punidos (CNEP)"}
    
    for endpoint, nome_base in bases.items():
        try:
            url = f"https://api.portaldatransparencia.gov.br/api-de-dados/{endpoint}"
            params = {"cnpjSancionado": cnpj_limpo, "pagina": 1}
            resp = requests.get(url, params=params, headers=get_headers(), timeout=5)
            if resp.status_code == 200:
                itens = resp.json()
                for item in itens:
                    cnpj_item = ""
                    nome_item = "Não informado"
                    try: 
                        sancionado = item.get('sancionado', {})
                        cnpj_item = sancionado.get('codigoFormatado') or item.get('pessoa', {}).get('cnpjFormatado')
                        nome_temp = sancionado.get('nome') or item.get('pessoa', {}).get('nome')
                        if nome_temp: nome_item = nome_temp
                    except: pass
                    
                    match = False
                    if cnpj_item and limpar_string(cnpj_item)[:8] == raiz_alvo: match = True
                    elif nome_base == "Acordo Leniência" and not cnpj_item:
                        match = True
                        item['_aviso_oculto'] = True

                    if match:
                        item['_origem'] = nome_base
                        item['_nome_exibicao'] = nome_item
                        resultados.append(item)
        except: pass
    return resultados

def checar_risco_simples(cnpj):
    res = auditar_cnpj_detalhado(cnpj)
    return True if len(res) > 0 else False

# --- Função de IA ---
def analisar_objeto_ia(objeto_texto):
    if not IA_ATIVA: return "IA Off"
    if not objeto_texto: return "Vazio"
    
    try:
        # ALTERADO AQUI: Usando 'gemini-pro' que é mais antigo e compatível
        model = genai.GenerativeModel('gemini-pro')
        
        prompt = f"""Analise o seguinte objeto de contrato público e retorne APENAS 'ALTO', 'MÉDIO' ou 'BAIXO' risco.
        Considere ALTO risco se for muito genérico, vago ou envolver valores suspeitos sem detalhamento.
        Objeto: '{objeto_texto}'"""
        
        response = model.generate_content(prompt)
        return response.text.strip().upper()
    
    except exceptions.ResourceExhausted:
        return "COTA IA EXCEDIDA" # Mensagem que vai aparecer na tabela
    except Exception as e:
        return f"ERRO"

# --- Busca de Contratos ---
def buscar_contratos(codigo_orgao):
    if not PORTAL_KEY: return []
    lista = []
    dt_fim = datetime.now()
    dt_ini = dt_fim - timedelta(days=730)
    
    bar = st.progress(0, text="Conectando ao Portal...")
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

# --- 5. INTERFACE PRINCIPAL ---
st.title("🛡️ Auditoria Gov Federal + IA")
st.markdown("---")

if not PORTAL_KEY:
    st.error("🚨 ERRO CRÍTICO: Chave do Portal não configurada")

aba1, aba2 = st.tabs(["🕵️ Checagem CNPJ", "📊 Auditoria de Contratos"])

with aba1:
    st.header("Investigação de Fornecedor")
    col1, col2 = st.columns([4, 1]) 
    cnpj_input = col1.text_input("CNPJ Alvo:", value="05.144.757/0001-72")
    
    if col2.button("Verificar Agora", type="primary"):
        with st.spinner("Consultando bases governamentais..."):
            try:
                r = requests.get(f"https://minhareceita.org/{limpar_string(cnpj_input)}", timeout=3)
                if r.status_code == 200: 
                    st.info(f"🏢 **Empresa:** {r.json().get('razao_social')}")
            except: pass

            sancoes = auditar_cnpj_detalhado(cnpj_input)
            
            st.divider()
            if sancoes:
                st.error(f"🚨 **ALERTA VERMELHO: {len(sancoes)} REGISTROS ENCONTRADOS**")
                for s in sancoes:
                    st.write(f"❌ **{s['_origem']}**: {s.get('motivo') or 'Sanção identificada'}")
            else:
                st.success("✅ **NADA CONSTA** - Fornecedor sem sanções ativas.")

with aba2:
    st.header("Monitoramento de Gastos & IA")
    
    c_input, c_ia = st.columns([3, 1])
    orgao_nome = c_input.selectbox("Órgão Público:", list(ORGAOS_SIAFI.keys()))
    usar_ia = c_ia.toggle("Ativar IA Gemini", value=True)
    
    if st.button("Buscar Dados"):
        cod = ORGAOS_SIAFI[orgao_nome]
        raw = buscar_contratos(cod)
        
        if raw:
            tabela = []
            total = 0.0
            
            for item in raw:
                val = safe_float(item.get('valorInicialCompra') or item.get('valorFinalCompra'))
                cnpj = item.get('fornecedor', {}).get('cnpjFormatado', '')
                data_crua = item.get('dataAssinatura', '')
                try: data_fmt = datetime.strptime(data_crua, "%Y-%m-%d").strftime("%d/%m/%Y")
                except: data_fmt = data_crua

                total += val
                tabela.append({
                    "Data": data_fmt,
                    "Valor": val,
                    "Objeto": item.get('objeto', '')[:120],
                    "CNPJ": cnpj,
                    "Risco IA": "⚪ N/A",
                    "Status CNPJ": "⚪"
                })
            
            df = pd.DataFrame(tabela)
            df = df.sort_values("Valor", ascending=False)
            
            prog_text = "IA Gemini analisando riscos..." if usar_ia else "Auditando..."
            bar_auditoria = st.progress(0, text=prog_text)
            
            limit = min(10, len(df))
            
            for i in range(limit):
                idx = df.index[i]
                row = df.loc[idx]
                
                if row['CNPJ']:
                    if checar_risco_simples(row['CNPJ']):
                        df.at[idx, "Status CNPJ"] = "🚨 ALERTA"
                    else:
                        df.at[idx, "Status CNPJ"] = "🟢 OK"
                
                if usar_ia:
                    df.at[idx, "Risco IA"] = analisar_objeto_ia(row['Objeto'])
                    time.sleep(1.0)
                
                bar_auditoria.progress((i + 1) / limit)
            
            bar_auditoria.empty()

            k1, k2, k3 = st.columns(3)
            k1.metric("Volume", f"R$ {total:,.2f}")
            k2.metric("Contratos", len(df))
            riscos_altos = len(df[df['Risco IA'].str.contains("ALTO", na=False)])
            k3.metric("Riscos Altos (IA)", riscos_altos, delta_color="inverse")
            
            def style_risk(v):
                if "ALTO" in str(v): return 'color: red; font-weight: bold'
                if "MÉDIO" in str(v): return 'color: orange; font-weight: bold'
                if "BAIXO" in str(v): return 'color: green'
                if "COTA" in str(v): return 'color: gray; font-style: italic'
                return ''
                
            def style_cnpj(v):
                if "ALERTA" in str(v): return 'background-color: #ffcccc; color: red; font-weight: bold'
                if "OK" in str(v): return 'color: green'
                return ''

            st.dataframe(
                df.style.applymap(style_risk, subset=['Risco IA'])
                        .applymap(style_cnpj, subset=['Status CNPJ'])
                        .format({"Valor": "R$ {:,.2f}"}),
                use_container_width=True,
                hide_index=True
            )
        else:
            st.warning("Nenhum dado encontrado.")