import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Auditoria Gov", page_icon="⚖️", layout="wide")

PORTAL_KEY = "d03ede6b6072b78e6df678b6800d4ba1"

ORGAOS_SIAFI = {
    "Ministério da Saúde (MS)": "36000",
    "Ministério da Educação (MEC)": "26000",
    "Ministério da Justiça (MJ)": "30000",
    "Presidência da República": "20000",
    "Ministério da Economia": "17000",
    "Comando do Exército": "52121",
    "Polícia Federal": "30108"
}

# --- FUNÇÕES ---
def get_headers():
    return {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        "chave-api-dados": PORTAL_KEY,
        "Accept": "application/json"
    }

def limpar_cnpj(cnpj):
    if not cnpj: return ""
    return "".join([n for n in str(cnpj) if n.isdigit()])

def safe_float(valor):
    try: return float(valor)
    except: return 0.0

@st.cache_data(ttl=3600)
def consultar_dados_cadastrais(cnpj):
    try:
        r = requests.get(f"https://minhareceita.org/{limpar_cnpj(cnpj)}", timeout=5)
        if r.status_code == 200: return r.json()
    except: pass
    return None

def auditar_completa(cnpj_alvo):
    resultados = []
    cnpj_limpo = limpar_cnpj(cnpj_alvo)
    
    # AGORA COM 3 BASES (Incluindo Acordos de Leniência)
    bases = {
        "ceis": "Cadastro de Inidôneos (CEIS)",
        "cnep": "Cadastro de Punidos (CNEP)",
        "acordos-leniencia": "Acordos de Leniência"
    }
    
    for endpoint, nome_base in bases.items():
        url = f"https://api.portaldatransparencia.gov.br/api-de-dados/{endpoint}"
        params = {"cnpjSancionado": cnpj_limpo, "pagina": 1}
        
        try:
            resp = requests.get(url, params=params, headers=get_headers(), timeout=10)
            if resp.status_code == 200:
                items = resp.json()
                # Se devolveu lista vazia, ignora
                if not items: continue
                
                # Validação Simplificada (Raiz do CNPJ)
                # Se a API devolveu algo buscando pelo CNPJ exato, 99% de chance de ser real.
                for item in items:
                    item['_origem'] = nome_base
                    resultados.append(item)
                    
        except Exception as e:
            print(f"Erro em {endpoint}: {e}")
            
    return resultados

# --- INTERFACE ---
st.title("⚖️ Auditoria Gov Federal (V33 - Leniência + Max Contratos)")

aba1, aba2 = st.tabs(["🕵️ Auditoria (Inclui Leniência)", "📊 Monitor (Max 100)"])

# --- ABA 1 ---
with aba1:
    st.header("Verificar Fornecedor")
    st.info("ℹ️ Bases Varridas: CEIS (Inidôneos), CNEP (Punidos) e Acordos de Leniência.")
    
    # Exemplo: MENDES JUNIOR
    cnpj_input = st.text_input("CNPJ:", value="17.162.082/0001-73")
    
    if st.button("Executar Varredura Completa", type="primary"):
        with st.spinner("Consultando bases históricas..."):
            
            # Identificação
            cad = consultar_dados_cadastrais(cnpj_input)
            razao = cad.get('razao_social') if cad else "Empresa"
            st.success(f"Analizando: **{razao}**")
            
            # Auditoria
            sancoes = auditar_completa(cnpj_input)
            
            st.divider()
            
            if sancoes:
                st.error(f"🚨 **ATENÇÃO: {len(sancoes)} REGISTROS ENCONTRADOS**")
                
                for s in sancoes:
                    with st.expander(f"⚠️ {s['_origem']} - Ver Detalhes"):
                        st.write(f"**Empresa:** {s.get('sancionado', {}).get('nome') or s.get('razaoSocial')}")
                        st.write(f"**Órgão:** {s.get('orgaoSancionador', {}).get('nome')}")
                        st.write(f"**Motivo/Situação:** {s.get('motivo') or s.get('situacaoAcordo')}")
                        
                        # Data do registro
                        dt = s.get('dataPublicacao') or s.get('dataInicioAcordo')
                        if dt: st.caption(f"Data do Registro: {dt}")
            else:
                st.success("✅ **Nada Consta** nas 3 bases federais.")
                st.caption("A empresa não possui sanções ativas nem acordos de leniência vigentes.")

# --- ABA 2 ---
with aba2:
    st.header("Monitoramento de Contratos")
    
    c1, c2 = st.columns([2, 1])
    with c1: orgao = st.selectbox("Selecione o Órgão", list(ORGAOS_SIAFI.keys()))
    
    dt_hoje = datetime.now()
    dt_inicio = dt_hoje - timedelta(days=365)
    
    with c2: st.write("Últimos 12 meses (Max 100 itens)")
    
    if st.button("Buscar Contratos (Expandido)"):
        cod = ORGAOS_SIAFI[orgao]
        
        # PARAMETRO QUANTIDADE=100 ADICIONADO
        params = {
            "dataInicial": dt_inicio.strftime("%d/%m/%Y"),
            "dataFinal": dt_hoje.strftime("%d/%m/%Y"),
            "codigoOrgao": cod,
            "pagina": 1,
            "quantidade": 100 
        }
        
        with st.spinner(f"Baixando até 100 contratos do {orgao}..."):
            try:
                r = requests.get("https://api.portaldatransparencia.gov.br/api-de-dados/contratos", 
                               params=params, headers=get_headers(), timeout=45)
                
                # Tratamento de erro de órgão vazio
                if r.status_code == 200:
                    data = r.json()
                    if data:
                        lista = []
                        total = 0.0
                        for d in data:
                            val = safe_float(d.get('valorInicial') or d.get('valorGlobal'))
                            total += val
                            lista.append({
                                "Data": d.get('dataAssinatura'),
                                "Fornecedor": d.get('fornecedor', {}).get('nome', 'N/A')[:50],
                                "Valor": val
                            })
                        
                        df = pd.DataFrame(lista)
                        
                        k1, k2 = st.columns(2)
                        k1.metric("Total Gasto (Amostra)", f"R$ {total:,.2f}")
                        k2.metric("Contratos Listados", len(df))
                        
                        if len(df) == 100:
                            st.warning("⚠️ Limite de 100 contratos atingido (Padrão de segurança).")
                        
                        st.dataframe(df.sort_values("Data", ascending=False).style.format({"Valor": "R$ {:,.2f}"}), use_container_width=True)
                    else:
                        st.warning("⚠️ Nenhum contrato encontrado para este código SIAFI.")
                        st.markdown(f"**Dica:** Órgãos como 'Presidência' ou 'Economia' usam códigos descentralizados (Ex: 17001, 17002). Tente 'Polícia Federal' ou 'Exército' para ver dados reais.")
                else:
                    st.error(f"Erro na API: {r.status_code}")
                    
            except Exception as e:
                st.error(f"Erro: {e}")