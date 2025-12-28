import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Auditoria Gov Federal", page_icon="🇧🇷", layout="wide")
PORTAL_KEY = "d03ede6b6072b78e6df678b6800d4ba1"

# --- LISTA DE ÓRGÃOS ESTRATÉGICOS ---
ORGAOS_SIAFI = {
    "Ministério da Saúde": "36000",
    "Ministério da Educação": "26000",
    "DNIT (Transportes)": "39252",
    "Polícia Federal": "30108",
    "Comando do Exército": "52121",
    "Ministério da Justiça": "30000"
}

# --- FUNÇÕES ---
def get_headers():
    return {
        "chave-api-dados": PORTAL_KEY,
        "Accept": "application/json"
    }

def limpar_cnpj(cnpj):
    if not cnpj: return ""
    return "".join([n for n in str(cnpj) if n.isdigit()])

def safe_float(valor):
    try: return float(valor)
    except: return 0.0

# --- AUDITORIA INTELIGENTE ---
def auditar_cnpj(cnpj_alvo):
    resultados_filtrados = []
    cnpj_limpo_alvo = limpar_cnpj(cnpj_alvo)
    raiz_alvo = cnpj_limpo_alvo[:8] # 8 primeiros dígitos
    
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
                
                # --- O GRANDE FILTRO V37 ---
                # A API manda lixo (outras empresas). Aqui nós limpamos.
                for item in itens:
                    cnpj_encontrado = ""
                    
                    # Procura onde o CNPJ está escondido no JSON
                    try: cnpj_encontrado = item.get('sancionado', {}).get('codigoFormatado')
                    except: pass
                    
                    if not cnpj_encontrado:
                        try: cnpj_encontrado = item.get('pessoa', {}).get('cnpjFormatado')
                        except: pass
                        
                    # Verifica se bate com a Raiz do Alvo
                    if cnpj_encontrado:
                        raiz_encontrada = limpar_cnpj(cnpj_encontrado)[:8]
                        if raiz_encontrada == raiz_alvo:
                            item['_origem'] = nome_base
                            resultados_filtrados.append(item)
                            
        except Exception as e:
            pass # Segue o baile se uma base falhar
            
    return resultados_filtrados

# --- CONTRATOS COM VALORES REAIS ---
def buscar_contratos(codigo_orgao):
    lista_final = []
    dt_fim = datetime.now()
    dt_ini = dt_fim - timedelta(days=365) # 1 ano atrás
    
    # Busca até 3 páginas (aprox 45 contratos)
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
            else:
                break
        except: break
        
    return lista_final

# --- INTERFACE GRÁFICA ---
st.title("⚖️ Sistema de Auditoria Federal")
st.markdown("---")

aba1, aba2 = st.tabs(["🔍 Consultar CNPJ", "📊 Contratos Públicos"])

# --- ABA 1: CONSULTA ---
with aba1:
    st.header("Verificação de Compliance")
    st.info("O sistema consulta CEIS, CNEP e Acordos de Leniência. Resultados validados pela raiz do CNPJ.")
    
    col_input, col_btn = st.columns([3, 1])
    cnpj_input = col_input.text_input("CNPJ da Empresa:", value="05.144.757/0001-72")
    
    if col_btn.button("Analisar", type="primary"):
        st.write("")
        
        # 1. Identificação
        with st.spinner("Identificando empresa..."):
            try:
                r = requests.get(f"https://minhareceita.org/{limpar_cnpj(cnpj_input)}", timeout=3)
                if r.status_code == 200:
                    nome = r.json().get('razao_social', 'Nome não disponível')
                    st.success(f"Empresa: **{nome}**")
            except: pass

        # 2. Auditoria
        with st.spinner("Confrontando bases governamentais..."):
            ocorrencias = auditar_cnpj(cnpj_input)
            
            st.divider()
            
            if ocorrencias:
                st.error(f"🚨 **ALERTA: {len(ocorrencias)} RESTRIÇÕES ENCONTRADAS**")
                
                for oc in ocorrencias:
                    with st.expander(f"⚠️ {oc['_origem']} - Ver Detalhes"):
                        # Tenta extrair dados genéricos
                        orgao = oc.get('orgaoSancionador', {}).get('nome', 'Não informado')
                        motivo = oc.get('motivo') or oc.get('situacaoAcordo') or "Verificar processo"
                        data = oc.get('dataPublicacao') or oc.get('dataInicioAcordo')
                        
                        st.write(f"**Órgão Responsável:** {orgao}")
                        st.write(f"**Situação/Motivo:** {motivo}")
                        if data: st.write(f"**Data:** {data}")
            else:
                st.success("✅ **NADA CONSTA**")
                st.write(f"Nenhum registro desabonador encontrado para a raiz do CNPJ {cnpj_input}.")

# --- ABA 2: CONTRATOS ---
with aba2:
    st.header("Monitoramento Financeiro")
    
    orgao_key = st.selectbox("Selecione o Órgão Público", list(ORGAOS_SIAFI.keys()))
    
    if st.button("Carregar Dados Financeiros"):
        cod = ORGAOS_SIAFI[orgao_key]
        
        with st.spinner(f"Baixando contratos do {orgao_key}..."):
            raw = buscar_contratos(cod)
            
            if raw:
                processados = []
                total = 0.0
                
                for item in raw:
                    # CORREÇÃO V37: USANDO O CAMPO CERTO DESCOBERTO NO JSON
                    valor = safe_float(item.get('valorInicialCompra') or item.get('valorFinalCompra'))
                    
                    total += valor
                    processados.append({
                        "Data Assinatura": item.get('dataAssinatura'),
                        "Fornecedor": item.get('fornecedor', {}).get('nome', 'DESCONHECIDO')[:40],
                        "Objeto": item.get('objeto', '')[:60] + "...",
                        "Valor": valor
                    })
                
                df = pd.DataFrame(processados)
                
                # KPIs
                k1, k2 = st.columns(2)
                k1.metric("Volume Financeiro (Amostra)", f"R$ {total:,.2f}")
                k2.metric("Contratos Analisados", len(df))
                
                # Tabela
                st.dataframe(
                    df.sort_values("Data Assinatura", ascending=False).style.format({"Valor": "R$ {:,.2f}"}), 
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.warning("Nenhum contrato disponível na API para este órgão no período.")