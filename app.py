import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Auditoria Gov", page_icon="⚖️", layout="wide")

# Chave da API (Mantenha a sua se esta falhar)
PORTAL_KEY = "d03ede6b6072b78e6df678b6800d4ba1"

# Códigos SIAFI (Mais utilizados)
ORGAOS_SIAFI = {
    "Ministério da Saúde (MS)": "36000",
    "Ministério da Educação (MEC)": "26000",
    "Ministério da Justiça (MJ)": "30000",
    "Presidência da República": "20000",
    "Ministério da Economia/Fazenda": "17000"
}

# --- FUNÇÕES ---
def get_headers():
    return {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        "chave-api-dados": PORTAL_KEY,
        "Accept": "application/json"
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
    # Tenta MinhaReceita
    try:
        r = requests.get(f"https://minhareceita.org/{clean_cnpj}", timeout=5)
        if r.status_code == 200: return r.json()
    except: pass
    return None

def auditar_empresa(cnpj_alvo):
    resultados = []
    cnpj_limpo_alvo = limpar_cnpj(cnpj_alvo)
    raiz_alvo = cnpj_limpo_alvo[:8] # Os 8 primeiros dígitos (Raiz)
    
    bases = ["ceis", "cnep"]
    for base in bases:
        url = f"https://api.portaldatransparencia.gov.br/api-de-dados/{base}"
        # Usamos 'codigoSancionado' que costuma ser mais preciso, mas a API é instável
        params = {"codigoSancionado": cnpj_limpo_alvo, "pagina": 1}
        
        try:
            resp = requests.get(url, params=params, headers=get_headers(), timeout=15)
            if resp.status_code == 200:
                items = resp.json()
                
                # --- FILTRO DE SEGURANÇA (PYTHON) ---
                # A API pode devolver lixo ou a lista inteira se o parametro falhar.
                # Aqui nós garantimos que SÓ passa se o CNPJ for da família do alvo.
                for item in items:
                    c_retorno = item.get('sancionado', {}).get('codigoFormatado') or item.get('pessoa', {}).get('cnpjFormatado')
                    
                    if c_retorno:
                        cnpj_retorno_limpo = limpar_cnpj(c_retorno)
                        # Compara apenas a Raiz (8 primeiros digitos) para pegar filiais
                        if cnpj_retorno_limpo.startswith(raiz_alvo):
                            item['_origem'] = base.upper()
                            resultados.append(item)
                            
        except Exception as e:
            print(f"Erro na base {base}: {e}")
            pass
            
    return resultados

# --- INTERFACE ---
st.title("⚖️ Auditoria Gov Federal (V28 Fixed)")
st.caption(f"Data do Sistema: {datetime.now().strftime('%d/%m/%Y')}")

aba1, aba2 = st.tabs(["🕵️ Auditoria CNPJ (Segura)", "📊 Contratos (Debug)"])

# --- ABA 1: AUDITORIA ---
with aba1:
    st.header("Compliance de Fornecedores")
    st.info("ℹ️ Filtro de Segurança Ativo: Resultados irrelevantes da API serão bloqueados.")
    
    cnpj_input = st.text_input("CNPJ:", placeholder="Ex: 00.000.000/0000-00")
    
    if st.button("Verificar Antecedentes", type="primary"):
        if len(cnpj_input) < 10:
            st.warning("CNPJ muito curto.")
        else:
            with st.spinner("Confrontando dados..."):
                # 1. Dados Cadastrais
                cad = consultar_dados_cadastrais(cnpj_input)
                razao = cad.get('razao_social') or cad.get('nome_fantasia') or "Razão Social não identificada"
                
                st.subheader(f"🏢 {razao}")
                st.caption(f"Status RFB: {cad.get('descricao_situacao_cadastral', 'N/A')}")
                
                # 2. Varredura com Filtro Rígido
                sancoes = auditar_empresa(cnpj_input)
                
                st.divider()
                
                if sancoes:
                    st.error(f"🚨 **ALERTA: {len(sancoes)} RESTRIÇÕES CONFIRMADAS**")
                    st.write("Estes registros pertencem EXATAMENTE à raiz do CNPJ informado.")
                    for s in sancoes:
                        with st.expander(f"⚠️ {s['_origem']} - {s.get('tipoSancao', {}).get('descricaoResumida', 'Sanção')}"):
                            st.write(f"**Órgão:** {s.get('orgaoSancionador', {}).get('nome')}")
                            st.write(f"**CNPJ Sancionado:** {s.get('sancionado', {}).get('codigoFormatado')}")
                            st.write(f"**Motivo:** {s.get('motivo', 'Não detalhado')}")
                else:
                    st.success(f"✅ **NADA CONSTA** - CNPJ Limpo ({cnpj_input})")
                    st.caption("Nenhum registro vinculado a esta raiz de CNPJ foi encontrado nas listas CEIS/CNEP.")

# --- ABA 2: CONTRATOS ---
with aba2:
    st.header("Monitoramento de Contratos")
    
    c1, c2 = st.columns([2, 1])
    with c1: orgao_selecionado = st.selectbox("Órgão", list(ORGAOS_SIAFI.keys()))
    
    # Busca contratos dos ultimos 30 dias por padrao
    dt_fim = datetime.now()
    dt_ini = dt_fim - timedelta(days=30)
    
    with c2: 
        st.write(f"Período: {dt_ini.strftime('%d/%m/%Y')} a {dt_fim.strftime('%d/%m/%Y')}")
    
    if st.button("Buscar Contratos"):
        cod_orgao = ORGAOS_SIAFI[orgao_selecionado]
        
        # URL Montada para Debug
        params = {
            "dataInicial": dt_ini.strftime("%d/%m/%Y"),
            "dataFinal": dt_fim.strftime("%d/%m/%Y"),
            "codigoOrgao": cod_orgao,
            "pagina": 1
        }
        
        st.write(f"📡 **Consultando:** Órgão {cod_orgao}...")
        
        with st.spinner("Aguardando Portal da Transparência..."):
            try:
                resp = requests.get("https://api.portaldatransparencia.gov.br/api-de-dados/contratos", 
                                  params=params, headers=get_headers(), timeout=30)
                
                if resp.status_code == 200:
                    dados = resp.json()
                    if dados:
                        lista = []
                        total = 0.0
                        for d in dados:
                            val = safe_float(d.get('valorInicial') or d.get('valorGlobal'))
                            total += val
                            lista.append({
                                "Data": d.get('dataAssinatura', 'N/A'),
                                "Fornecedor": d.get('fornecedor', {}).get('nome', 'N/A')[:40],
                                "Valor": val
                            })
                        
                        df = pd.DataFrame(lista)
                        st.metric("Total Gasto", formatar_moeda(total))
                        st.dataframe(df.style.format({"Valor": "R$ {:,.2f}"}), use_container_width=True)
                    else:
                        st.warning("⚠️ A API retornou uma lista vazia.")
                        st.markdown("**Diagnóstico:** O órgão não publicou contratos neste período ou a API está com delay.")
                else:
                    st.error(f"Erro na API: Status Code {resp.status_code}")
            
            except Exception as e:
                st.error(f"Erro de conexão: {str(e)}")
            
            # Área de Debug (Expander)
            with st.expander("🛠️ Ver Link da Requisição (Técnico)"):
                st.code(f"URL: {resp.url if 'resp' in locals() else 'Erro antes da req'}")
                st.write("Se o link acima estiver correto mas não trouxer dados no navegador, o problema é no Governo.")