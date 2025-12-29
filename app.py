import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import os
import time
import google.generativeai as genai
from dotenv import load_dotenv

# --- 1. CONFIGURAÇÃO (SECRETS + LOCAL) ---
load_dotenv()

# Função robusta para pegar chaves (Funciona Local e na Nuvem)
def get_key(name):
    if hasattr(st, "secrets") and name in st.secrets:
        return st.secrets[name]
    return os.getenv(name)

PORTAL_KEY = get_key("PORTAL_KEY")
GEMINI_KEY = get_key("GEMINI_API_KEY")

# Configuração da IA
IA_DISPONIVEL = False
if GEMINI_KEY:
    try:
        # Usando o modelo 1.5-flash que é mais estável na nuvem que o PRO
        genai.configure(api_key=GEMINI_KEY)
        IA_DISPONIVEL = True
    except: pass

st.set_page_config(page_title="GovAudit Pro", page_icon="⚖️", layout="wide")

# --- 2. FUNÇÕES DE SUPORTE ---
def limpar_cnpj(valor):
    """Deixa apenas números"""
    return "".join([c for c in str(valor) if c.isdigit()])

def formatar_moeda(valor):
    try: return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except: return "R$ 0,00"

def get_headers():
    return {"chave-api-dados": PORTAL_KEY, "Accept": "application/json"}

# --- 3. IA (LÓGICA SIMPLES E FUNCIONAL) ---
def consultar_ia(texto_objeto):
    if not IA_DISPONIVEL: return "IA OFF"
    if not texto_objeto: return "-"
    
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        # Prompt direto para economizar tokens e ser rápido
        response = model.generate_content(
            f"Classifique o risco de corrupção deste objeto em uma palavra (ALTO, MÉDIO ou BAIXO): {texto_objeto}"
        )
        return response.text.strip().upper()
    except:
        return "ERRO/LIMIT"

# --- 4. LÓGICA CNPJ (O SEGREDO DO LOCALHOST) ---
def buscar_sancoes_raiz(cnpj_input):
    if not PORTAL_KEY: return []
    
    # PEGA A RAIZ (8 DÍGITOS)
    cnpj_limpo = limpar_cnpj(cnpj_input)
    raiz_alvo = cnpj_limpo[:8]
    
    lista_final = []
    
    # Bases para consultar
    endpoints = ["acordos-leniencia", "ceis", "cnep"]
    
    for endp in endpoints:
        try:
            # Truque: Buscamos na API usando o CNPJ completo ou a raiz (depende da API, vamos usar o limpo)
            url = f"https://api.portaldatransparencia.gov.br/api-de-dados/{endp}"
            params = {"cnpjSancionado": cnpj_limpo, "pagina": 1}
            
            r = requests.get(url, params=params, headers=get_headers(), timeout=8)
            
            if r.status_code == 200:
                itens = r.json()
                for item in itens:
                    # Tenta achar o CNPJ dentro do JSON bagunçado do governo
                    c_encontrado = ""
                    try: c_encontrado = item['sancionado']['codigoFormatado']
                    except: 
                        try: c_encontrado = item['pessoa']['cnpjFormatado']
                        except: pass
                    
                    # A MÁGICA: Compara só a RAIZ
                    if limpar_cnpj(c_encontrado).startswith(raiz_alvo):
                        item['_origem'] = endp
                        lista_final.append(item)
        except: pass
        
    return lista_final

# --- 5. BUSCA CONTRATOS ---
def buscar_contratos(orgao_cod):
    if not PORTAL_KEY: return []
    
    dt_fim = datetime.now()
    dt_ini = dt_fim - timedelta(days=365) # 1 ano atrás
    
    url = "https://api.portaldatransparencia.gov.br/api-de-dados/contratos"
    params = {
        "dataInicial": dt_ini.strftime("%d/%m/%Y"),
        "dataFinal": dt_fim.strftime("%d/%m/%Y"),
        "codigoOrgao": orgao_cod,
        "pagina": 1
    }
    
    try:
        r = requests.get(url, params=params, headers=get_headers(), timeout=10)
        if r.status_code == 200:
            return r.json()
    except: pass
    return []

# --- 6. INTERFACE (FRONTEND) ---
st.title("🛡️ Auditoria Gov (Versão Restaurada)")

tab1, tab2 = st.tabs(["🕵️ Checagem CNPJ", "📋 Auditoria Contratos"])

# ABA 1: CNPJ
with tab1:
    st.header("Consultar Histórico")
    col_in, col_btn = st.columns([3, 1])
    # Valor padrão Novonor
    cnpj_digitado = col_in.text_input("CNPJ", value="05.144.757/0001-72") 
    
    if col_btn.button("Verificar Ficha"):
        with st.spinner("Varrendo bases do governo..."):
            resultados = buscar_sancoes_raiz(cnpj_digitado)
        
        if resultados:
            st.error(f"🚨 ENCONTRADOS {len(resultados)} REGISTROS")
            st.write("Atenção: Registros encontrados na Raiz do CNPJ (Matriz/Filiais)")
            for res in resultados:
                origem = res.get('_origem', '').upper()
                motivo = res.get('motivo', 'Sem detalhes')
                st.warning(f"**{origem}**: {motivo}")
        else:
            st.success("✅ NADA CONSTA (CEIS/CNEP/LENIÊNCIA)")

# ABA 2: CONTRATOS + IA
with tab2:
    st.header("Análise Inteligente")
    orgaos = {
        "Ministério da Saúde": "36000",
        "Ministério da Educação": "26000",
        "Polícia Federal": "30108"
    }
    sel_orgao = st.selectbox("Selecione o Órgão", list(orgaos.keys()))
    
    if st.button("Buscar e Analisar"):
        dados = buscar_contratos(orgaos[sel_orgao])
        
        if dados:
            # Pega só os 5 maiores para ser rápido e não bloquear a IA
            dados.sort(key=lambda x: float(x.get('valorInicialCompra', 0) or 0), reverse=True)
            top_5 = dados[:5]
            
            tabela_final = []
            
            progresso = st.progress(0, text="Consultando IA...")
            
            for i, contrato in enumerate(top_5):
                obj = contrato.get('objeto', 'Sem objeto')
                valor = contrato.get('valorInicialCompra')
                
                # Pausa técnica para a IA não bloquear na nuvem (Cloud precisa disso)
                time.sleep(1.5) 
                risco = consultar_ia(obj)
                
                tabela_final.append({
                    "Valor": formatar_moeda(valor),
                    "Risco IA": risco,
                    "Objeto": obj
                })
                progresso.progress((i + 1) / len(top_5))
            
            progresso.empty()
            
            # Exibe tabela colorida
            df = pd.DataFrame(tabela_final)
            
            def cor_risco(val):
                color = 'white'
                if 'ALTO' in str(val): color = '#ff4b4b' # Vermelho
                elif 'MÉDIO' in str(val): color = '#ffa421' # Laranja
                elif 'BAIXO' in str(val): color = '#21c354' # Verde
                return f'color: {color}; font-weight: bold'

            st.dataframe(df.style.applymap(cor_risco, subset=['Risco IA']), use_container_width=True)
            
        else:
            st.warning("Nenhum contrato encontrado ou erro na API do Governo.")