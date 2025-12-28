import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import time

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Auditoria Gov Federal", page_icon="🏛️", layout="wide")
PORTAL_KEY = "d03ede6b6072b78e6df678b6800d4ba1"

# --- LISTA DE ÓRGÃOS ---
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

# --- MOTOR DE AUDITORIA (Retorna True se tiver problema) ---
def checar_antecedentes_rapido(cnpj_alvo):
    if not cnpj_alvo: return False
    
    cnpj_limpo = limpar_string(cnpj_alvo)
    raiz_alvo = cnpj_limpo[:8]
    bases = ["acordos-leniencia", "ceis", "cnep"]
    
    for endpoint in bases:
        try:
            url = f"https://api.portaldatransparencia.gov.br/api-de-dados/{endpoint}"
            params = {"cnpjSancionado": cnpj_limpo, "pagina": 1}
            resp = requests.get(url, params=params, headers=get_headers(), timeout=5)
            
            if resp.status_code == 200:
                itens = resp.json()
                for item in itens:
                    # Lógica do Fantasma e Raiz
                    cnpj_item = ""
                    try: 
                        sancionado = item.get('sancionado', {})
                        cnpj_item = sancionado.get('codigoFormatado') or item.get('pessoa', {}).get('cnpjFormatado')
                    except: pass
                    
                    # Se bate a raiz
                    if cnpj_item and limpar_string(cnpj_item)[:8] == raiz_alvo:
                        return True # SUJO
                    
                    # Se for Leniência Fantasma (Sem CNPJ mas retornou na busca)
                    if endpoint == "acordos-leniencia" and not cnpj_item:
                        return True # SUJO
        except: pass
    return False # LIMPO

# --- AUDITORIA DETALHADA (Para a Aba 1) ---
def auditar_cnpj_detalhado(cnpj_alvo):
    resultados = []
    cnpj_limpo = limpar_string(cnpj_alvo)
    raiz_alvo = cnpj_limpo[:8]
    
    bases = {"acordos-leniencia": "ACORDO DE LENIÊNCIA", "ceis": "INIDÔNEO (CEIS)", "cnep": "PUNIDO (CNEP)"}
    
    for endpoint, nome_base in bases.items():
        try:
            url = f"https://api.portaldatransparencia.gov.br/api-de-dados/{endpoint}"
            params = {"cnpjSancionado": cnpj_limpo, "pagina": 1}
            resp = requests.get(url, params=params, headers=get_headers(), timeout=10)
            
            if resp.status_code == 200:
                itens = resp.json()
                for item in itens:
                    cnpj_item = ""
                    nome_item = "Nome não informado"
                    try: 
                        sancionado = item.get('sancionado', {})
                        cnpj_item = sancionado.get('codigoFormatado') or item.get('pessoa', {}).get('cnpjFormatado')
                        nome_temp = sancionado.get('nome') or item.get('pessoa', {}).get('nome')
                        if nome_temp: nome_item = nome_temp
                    except: pass
                    
                    match = False
                    if cnpj_item:
                        if limpar_string(cnpj_item)[:8] == raiz_alvo: match = True
                    elif nome_base == "ACORDO DE LENIÊNCIA" and not cnpj_item:
                        match = True
                        item['_aviso_oculto'] = True 

                    if match:
                        item['_origem'] = nome_base
                        item['_nome_exibicao'] = nome_item
                        resultados.append(item)
        except: pass
    return resultados

# --- CONTRATOS ---
def buscar_contratos(codigo_orgao):
    lista_final = []
    dt_fim = datetime.now()
    dt_ini = dt_fim - timedelta(days=730)
    
    for pag in range(1, 4):
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
                lista_final.extend(dados)
            else: break
        except: break
    return lista_final

# --- INTERFACE ---
st.title("🏛️ Auditoria Governamental Integrada")
st.markdown("---")

aba1, aba2 = st.tabs(["🕵️ Análise de Risco (Individual)", "💰 Contratos & Compliance Cruzado"])

# --- ABA 1 ---
with aba1:
    st.header("Consulta de Compliance")
    col1, col2 = st.columns([3, 1])
    cnpj_input = col1.text_input("CNPJ:", value="05.144.757/0001-72")
    
    if col2.button("Verificar", type="primary"):
        with st.spinner("Analisando sanções..."):
            try:
                r = requests.get(f"https://minhareceita.org/{limpar_string(cnpj_input)}", timeout=3)
                if r.status_code == 200: st.info(f"Razão Social: **{r.json().get('razao_social')}**")
            except: pass

            sancoes = auditar_cnpj_detalhado(cnpj_input)
            st.divider()
            
            if sancoes:
                st.error(f"🚨 **ALERTA: {len(sancoes)} OCORRÊNCIAS**")
                for s in sancoes:
                    titulo = f"⚠️ {s['_origem']}"
                    if s.get('_aviso_oculto'): titulo += " (Sigilo Parcial)"
                    with st.expander(titulo):
                        st.write(f"**Empresa:** {s['_nome_exibicao']}")
                        st.write(f"**Motivo:** {s.get('motivo') or s.get('situacaoAcordo')}")
            else:
                st.success("✅ **NADA CONSTA**")

# --- ABA 2 (O RADAR CRUZADO) ---
with aba2:
    st.header("Monitoramento de Contratos + Risco do Fornecedor")
    orgao_nome = st.selectbox("Selecione o Órgão:", list(ORGAOS_SIAFI.keys()))
    
    if st.button("Buscar e Analisar Risco"):
        cod = ORGAOS_SIAFI[orgao_nome]
        
        # 1. Busca Contratos
        with st.spinner(f"1/2 Baixando contratos da {orgao_nome}..."):
            raw = buscar_contratos(cod)
        
        if raw:
            dados_tab = []
            total = 0.0
            cnpjs_unicos = set()
            
            # Processa dados básicos
            for item in raw:
                val = safe_float(item.get('valorInicialCompra') or item.get('valorFinalCompra'))
                cnpj_fornecedor = item.get('fornecedor', {}).get('cnpjFormatado', '')
                
                total += val
                if cnpj_fornecedor: cnpjs_unicos.add(cnpj_fornecedor)
                
                dados_tab.append({
                    "Data": item.get('dataAssinatura'),
                    "Fornecedor": item.get('fornecedor', {}).get('nome', 'N/A')[:30],
                    "CNPJ": cnpj_fornecedor,
                    "Objeto": item.get('objeto', 'N/A')[:60] + "...",
                    "Valor": val,
                    "Risco": "❓" # Placeholder
                })
            
            # 2. Auditoria em Lote (Limitada para performance)
            st.info(f"Analisando antecedentes de {len(cnpjs_unicos)} empresas encontradas...")
            progress_bar = st.progress(0)
            
            status_map = {}
            for i, c in enumerate(cnpjs_unicos):
                # Atualiza barra de progresso
                progress_bar.progress((i + 1) / len(cnpjs_unicos))
                
                # Checa se é sujo
                is_sujo = checar_antecedentes_rapido(c)
                status_map[c] = "🔴 ALERTA" if is_sujo else "🟢 OK"
                
                # Pequena pausa para a API não bloquear
                time.sleep(0.1) 
            
            progress_bar.empty()
            
            # 3. Atualiza Tabela
            for linha in dados_tab:
                cnpj = linha["CNPJ"]
                linha["Risco"] = status_map.get(cnpj, "⚪ N/A")

            df = pd.DataFrame(dados_tab)
            
            # Métricas
            c1, c2, c3 = st.columns(3)
            c1.metric("Total Gasto", f"R$ {total:,.2f}")
            c2.metric("Contratos", len(df))
            qtd_risco = len(df[df["Risco"] == "🔴 ALERTA"])
            c3.metric("Fornecedores em Alerta", qtd_risco, delta_color="inverse" if qtd_risco > 0 else "normal")
            
            # Mostra Tabela Colorida
            def color_risk(val):
                color = '#ffcccc' if val == '🔴 ALERTA' else '#ccffcc' if val == '🟢 OK' else ''
                return f'background-color: {color}'

            st.dataframe(
                df.sort_values("Valor", ascending=False).style.applymap(color_risk, subset=['Risco']).format({"Valor": "R$ {:,.2f}"}),
                use_container_width=True, hide_index=True
            )
            
            if qtd_risco > 0:
                st.warning("⚠️ Atenção: Foram encontrados fornecedores com sanções vigentes nesta lista de contratos.")

        else:
            st.warning("Nenhum contrato encontrado.")