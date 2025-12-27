import streamlit as st
import requests
import pandas as pd
from datetime import datetime, date, timedelta

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Auditoria Gov", page_icon="⚖️", layout="wide")

PORTAL_KEY = "d03ede6b6072b78e6df678b6800d4ba1"

ORGAOS_SIAFI = {
    "Ministério da Saúde (MS)": "36000",
    "Ministério da Educação (MEC)": "26000",
    "Ministério da Justiça (MJ)": "30000",
    "Presidência da República": "20000",
    "Ministério da Defesa (MD)": "52000"
}

# --- FUNÇÕES ---
def get_headers():
    return {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        "chave-api-dados": PORTAL_KEY
    }

def formatar_moeda(valor):
    try:
        if not valor: return "R$ 0,00"
        return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except: return "R$ 0,00"

def safe_float(valor):
    try: return float(valor)
    except: return 0.0

def limpar_cnpj(cnpj):
    if not cnpj: return ""
    return "".join([n for n in str(cnpj) if n.isdigit()])

@st.cache_data(ttl=3600)
def consultar_dados_cadastrais(cnpj):
    clean_cnpj = limpar_cnpj(cnpj)
    headers = {'User-Agent': 'Mozilla/5.0'} 
    
    # 1. BrasilAPI
    try:
        r = requests.get(f"https://brasilapi.com.br/api/cnpj/v1/{clean_cnpj}", headers=headers, timeout=3)
        if r.status_code == 200: return r.json()
    except: pass
    
    # 2. MinhaReceita
    try:
        r = requests.get(f"https://minhareceita.org/{clean_cnpj}", headers=headers, timeout=5)
        if r.status_code == 200: return r.json()
    except: pass
    
    return None

def auditar_empresa(cnpj_alvo):
    resultados = []
    cnpj_limpo_alvo = limpar_cnpj(cnpj_alvo)
    raiz_alvo = cnpj_limpo_alvo[:8] # Pega os 8 primeiros dígitos
    
    bases = ["ceis", "cnep"]
    
    for base in bases:
        # Busca pela RAIZ para garantir que pegamos tudo do grupo
        url = f"https://api.portaldatransparencia.gov.br/api-de-dados/{base}"
        params = {"cnpjSancionado": cnpj_limpo_alvo, "pagina": 1}
        
        try:
            resp = requests.get(url, params=params, headers=get_headers(), timeout=15)
            if resp.status_code == 200:
                items = resp.json()
                for item in items:
                    c_retorno = item.get('sancionado', {}).get('codigoFormatado') or item.get('pessoa', {}).get('cnpjFormatado')
                    
                    # COMPARAÇÃO INTELIGENTE (Raiz com Raiz)
                    if c_retorno:
                        clean_retorno = limpar_cnpj(c_retorno)
                        if clean_retorno[:8] == raiz_alvo: # Se a raiz bater, é alerta!
                            item['_origem'] = base.upper()
                            resultados.append(item)
        except: pass
            
    return resultados

# --- INTERFACE ---
st.title("⚖️ Auditoria Gov Federal")

aba1, aba2 = st.tabs(["🕵️ Auditoria CNPJ", "📊 Monitoramento de Gastos"])

# --- ABA 1: AUDITORIA ---
with aba1:
    st.header("Compliance de Fornecedores")
    cnpj_input = st.text_input("CNPJ:", placeholder="Ex: 00.000.000/0000-00")
    
    if st.button("Verificar Antecedentes", type="primary"):
        if len(cnpj_input) < 10:
            st.warning("CNPJ inválido.")
        else:
            with st.spinner("Varrendo bases do governo (CEIS/CNEP)..."):
                cad = consultar_dados_cadastrais(cnpj_input)
                
                # Tratamento para evitar o "None"
                if cad:
                    razao = cad.get('razao_social') or cad.get('nome_fantasia') or "Razão Social Não Localizada"
                    sit = cad.get('descricao_situacao_cadastral') or "Situação Não Informada"
                else:
                    razao = "Empresa não identificada na base pública"
                    sit = "Verifique a digitação"

                c1, c2 = st.columns([3, 1])
                c1.info(f"🏢 **{razao}**")
                
                if "ATIVA" in sit.upper(): c2.success(f"RFB: {sit}")
                else: c2.warning(f"RFB: {sit}")
                
                sancoes = auditar_empresa(cnpj_input)
                st.divider()
                
                if sancoes:
                    st.error(f"🚨 **ALERTA VERMELHO: {len(sancoes)} Restrições Encontradas (Raiz do CNPJ)**")
                    for s in sancoes:
                        with st.expander(f"{s['_origem']} - {s.get('tipoSancao', {}).get('descricaoResumida', 'Sanção')}"):
                            st.write(f"**Órgão:** {s.get('orgaoSancionador', {}).get('nome')}")
                            st.write(f"**Motivo:** {s.get('motivo', 'Não detalhado')}")
                            st.caption(f"CNPJ Sancionado: {s.get('sancionado', {}).get('codigoFormatado')}")
                else:
                    st.success("✅ **NADA CONSTA** - CNPJ Limpo.")

# --- ABA 2: CONTRATOS ---
with aba2:
    st.header("Monitor de Contratos")
    
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1: orgao_selecionado = st.selectbox("Órgão", list(ORGAOS_SIAFI.keys()))
    
    # Datas pré-definidas para garantir retorno (últimos 90 dias do ano vigente)
    dt_final = date.today()
    dt_inicial = dt_final - timedelta(days=90)
    
    with c2: data_ini = st.date_input("Início", dt_inicial, format="DD/MM/YYYY")
    with c3: data_fim = st.date_input("Fim", dt_final, format="DD/MM/YYYY")
    
    if st.button("Buscar Dados", type="primary"):
        cod_orgao = ORGAOS_SIAFI[orgao_selecionado]
        params = {
            "dataInicial": data_ini.strftime("%d/%m/%Y"),
            "dataFinal": data_fim.strftime("%d/%m/%Y"),
            "codigoOrgao": cod_orgao,
            "pagina": 1
        }
        
        with st.spinner("Acessando Portal da Transparência..."):
            resp = requests.get("https://api.portaldatransparencia.gov.br/api-de-dados/contratos", 
                              params=params, headers=get_headers(), timeout=30)
            
            dados = resp.json() if resp.status_code == 200 else []
            
            if dados:
                lista = []
                total = 0.0
                for d in dados:
                    val = d.get('valorInicial') or d.get('valorGlobal') or 0
                    val_float = safe_float(val)
                    total += val_float
                    lista.append({
                        "Data": d.get('dataAssinatura', 'N/A'),
                        "Fornecedor": d.get('fornecedor', {}).get('nome', 'N/A')[:40],
                        "Valor": val_float
                    })
                
                df = pd.DataFrame(lista)
                k1, k2 = st.columns(2)
                k1.metric("Total Gasto", formatar_moeda(total))
                k2.metric("Contratos", len(df))
                
                st.dataframe(df.style.format({"Valor": "R$ {:,.2f}"}), use_container_width=True, hide_index=True)
            else:
                st.warning("Nenhum contrato encontrado. Tente aumentar o período de busca.")