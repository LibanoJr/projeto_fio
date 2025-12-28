import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Auditoria Gov Federal", page_icon="⚖️", layout="wide")
PORTAL_KEY = "d03ede6b6072b78e6df678b6800d4ba1"

# --- ÓRGÃOS ---
ORGAOS_SIAFI = {
    "Ministério da Saúde": "36000",
    "Ministério da Educação": "26000",
    "DNIT (Transportes)": "39252",
    "Polícia Federal": "30108",
    "Comando do Exército": "52121",
    "Ministério da Justiça": "30000",
    "Presidência da República": "20000"
}

# --- FUNÇÕES ---
def get_headers():
    return {
        "chave-api-dados": PORTAL_KEY,
        "Accept": "application/json"
    }

def limpar_string(texto):
    if not texto: return ""
    return "".join([c for c in str(texto) if c.isdigit()])

def safe_float(valor):
    try: return float(valor)
    except: return 0.0

# --- AUDITORIA (V39: ACEITA REGISTROS OCULTOS/FANTASMAS) ---
def auditar_cnpj_final(cnpj_alvo):
    resultados_reais = []
    
    cnpj_limpo_alvo = limpar_string(cnpj_alvo)
    raiz_alvo = cnpj_limpo_alvo[:8]
    
    bases = {
        "acordos-leniencia": "ACORDO DE LENIÊNCIA",
        "ceis": "INIDÔNEO (CEIS)",
        "cnep": "PUNIDO (CNEP)"
    }
    
    for endpoint, nome_base in bases.items():
        try:
            url = f"https://api.portaldatransparencia.gov.br/api-de-dados/{endpoint}"
            params = {"cnpjSancionado": cnpj_limpo_alvo, "pagina": 1}
            
            resp = requests.get(url, params=params, headers=get_headers(), timeout=10)
            
            if resp.status_code == 200:
                itens = resp.json()
                
                for item in itens:
                    # Tenta extrair dados
                    cnpj_item = ""
                    nome_item = "Nome não informado na API"
                    
                    try: 
                        sancionado = item.get('sancionado', {})
                        cnpj_item = sancionado.get('codigoFormatado') or item.get('pessoa', {}).get('cnpjFormatado')
                        nome_temp = sancionado.get('nome') or item.get('pessoa', {}).get('nome')
                        if nome_temp: nome_item = nome_temp
                    except: pass
                    
                    # LOGICA V39: O GRANDE FILTRO
                    match = False
                    
                    # 1. Se tiver CNPJ, compara a raiz (Isso limpa os lixos tipo 'Instituto Aprimorar')
                    if cnpj_item:
                        if limpar_string(cnpj_item)[:8] == raiz_alvo:
                            match = True
                    
                    # 2. SE FOR LENIÊNCIA E VIER VAZIO (O CASO NOVONOR)
                    # Se não tem CNPJ no item, mas veio na busca de Leniência, assumimos que é o alvo oculto.
                    elif nome_base == "ACORDO DE LENIÊNCIA" and not cnpj_item:
                        match = True
                        item['_aviso_oculto'] = True # Marca para avisar na tela

                    if match:
                        item['_origem'] = nome_base
                        item['_nome_exibicao'] = nome_item
                        resultados_reais.append(item)
                        
        except Exception:
            pass
            
    return resultados_reais

# --- CONTRATOS (SEM MEXER NA LÓGICA QUE FUNCIONA) ---
def buscar_contratos(codigo_orgao):
    lista_final = []
    dt_fim = datetime.now()
    dt_ini = dt_fim - timedelta(days=365)
    
    for pag in range(1, 4):
        params = {
            "dataInicial": dt_ini.strftime("%d/%m/%Y"),
            "dataFinal": dt_fim.strftime("%d/%m/%Y"),
            "codigoOrgao": codigo_orgao,
            "pagina": pag
        }
        try:
            r = requests.get("https://api.portaldatransparencia.gov.br/api-de-dados/contratos", 
                           params=params, headers=get_headers(), timeout=15)
            if r.status_code == 200:
                dados = r.json()
                if not dados: break
                lista_final.extend(dados)
            else: break
        except: break
    return lista_final

# --- INTERFACE ---
st.title("⚖️ Auditoria Gov Federal")
st.markdown("---")

aba1, aba2 = st.tabs(["🕵️ Auditoria CNPJ", "💰 Contratos"])

# --- ABA 1 ---
with aba1:
    st.header("Análise de Risco")
    col1, col2 = st.columns([3, 1])
    cnpj_input = col1.text_input("CNPJ:", value="05.144.757/0001-72")
    
    if col2.button("Verificar", type="primary"):
        # Identificação
        with st.spinner("Validando Receita..."):
            try:
                r = requests.get(f"https://minhareceita.org/{limpar_string(cnpj_input)}", timeout=3)
                if r.status_code == 200:
                    st.info(f"Empresa: **{r.json().get('razao_social')}**")
            except: pass

        # Auditoria
        with st.spinner("Analisando sanções..."):
            sancoes = auditar_cnpj_final(cnpj_input)
            
            st.divider()
            
            if sancoes:
                st.error(f"🚨 **ALERTA: {len(sancoes)} OCORRÊNCIAS CONFIRMADAS**")
                for s in sancoes:
                    # Tratamento visual para o registro fantasma
                    titulo = f"⚠️ {s['_origem']}"
                    if s.get('_aviso_oculto'):
                        titulo += " (DADOS PROTEGIDOS NA API)"
                    
                    with st.expander(titulo):
                        st.write(f"**Empresa:** {s['_nome_exibicao']}")
                        st.write(f"**Motivo:** {s.get('motivo') or s.get('situacaoAcordo')}")
                        st.write(f"**Órgão:** {s.get('orgaoSancionador', {}).get('nome')}")
                        if s.get('_aviso_oculto'):
                            st.caption("Nota: Este registro foi retornado pela API sem identificadores públicos, mas está vinculado à sua busca.")
            else:
                st.success("✅ **NADA CONSTA**")
                st.write(f"CNPJ {cnpj_input} limpo nas bases CEIS, CNEP e Leniência.")

# --- ABA 2 ---
with aba2:
    st.header("Monitor de Gastos Públicos")
    orgao_nome = st.selectbox("Órgão", list(ORGAOS_SIAFI.keys()))
    
    if st.button("Buscar Dados"):
        cod = ORGAOS_SIAFI[orgao_nome]
        with st.spinner(f"Consultando {orgao_nome}..."):
            raw = buscar_contratos(cod)
            
            if raw:
                dados_tab = []
                total = 0.0
                for item in raw:
                    val = safe_float(item.get('valorInicialCompra') or item.get('valorFinalCompra'))
                    total += val
                    dados_tab.append({
                        "Data": item.get('dataAssinatura'),
                        "Fornecedor": item.get('fornecedor', {}).get('nome', 'N/A')[:40],
                        "Objeto": item.get('objeto', 'N/A')[:80] + "...",
                        "Valor": val
                    })
                
                df = pd.DataFrame(dados_tab)
                c1, c2 = st.columns(2)
                c1.metric("Total (Amostra)", f"R$ {total:,.2f}")
                c2.metric("Qtd. Contratos", len(df))
                
                st.dataframe(
                    df.sort_values("Data", ascending=False).style.format({"Valor": "R$ {:,.2f}"}),
                    use_container_width=True, hide_index=True
                )
            else:
                st.warning(f"⚠️ A API não retornou contratos recentes para: {orgao_nome}")
                st.caption("Motivos possíveis: Órgão não publicou neste código SIAFI recentemente ou dados estão sob sigilo/atualização.")