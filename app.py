import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Auditoria Gov Federal", page_icon="⚖️", layout="wide")
PORTAL_KEY = "d03ede6b6072b78e6df678b6800d4ba1"

# --- LISTA DE ÓRGÃOS (SIAFI) ---
ORGAOS_SIAFI = {
    "Presidência da República": "20000",
    "Ministério da Saúde": "36000",
    "Ministério da Educação": "26000",
    "DNIT (Transportes)": "39252",
    "Polícia Federal": "30108",
    "Comando do Exército": "52121",
    "Ministério da Justiça": "30000"
}

# --- FUNÇÕES AUXILIARES ---
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

# --- AUDITORIA (LÓGICA REFINADA V38) ---
def auditar_cnpj_detalhado(cnpj_alvo, nome_alvo_tentativa=""):
    resultados_reais = []
    itens_descartados = [] # Para debug
    
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
                    # Tenta extrair dados de identificação do item
                    cnpj_item = ""
                    nome_item = ""
                    
                    # Vasculha o JSON em busca de identificadores
                    try: 
                        sancionado = item.get('sancionado', {})
                        cnpj_item = sancionado.get('codigoFormatado') or item.get('pessoa', {}).get('cnpjFormatado')
                        nome_item = sancionado.get('nome') or item.get('pessoa', {}).get('nome')
                    except: pass
                    
                    match_confirmado = False
                    motivo_descarte = "CNPJ não bateu"

                    # 1. Tenta match por Raiz do CNPJ
                    if cnpj_item:
                        raiz_item = limpar_string(cnpj_item)[:8]
                        if raiz_item == raiz_alvo:
                            match_confirmado = True
                    
                    # 2. Se falhar CNPJ, tenta match por Nome (primeira palavra)
                    if not match_confirmado and nome_item and nome_alvo_tentativa:
                        primeiro_nome_alvo = nome_alvo_tentativa.split()[0].upper()
                        primeiro_nome_item = str(nome_item).split()[0].upper()
                        if primeiro_nome_alvo in str(nome_item).upper():
                            # Match parcial de segurança (ex: NOVONOR match ODEBRECHT as vezes falha, mas tenta)
                            # Aqui somos conservadores: só aceita se CNPJ for nulo mas nome bater forte
                            if not cnpj_item: 
                                match_confirmado = True
                    
                    # Salva
                    item['_origem'] = nome_base
                    item['_nome_encontrado'] = nome_item
                    item['_cnpj_encontrado'] = cnpj_item
                    
                    if match_confirmado:
                        resultados_reais.append(item)
                    else:
                        item['_motivo_descarte'] = f"Raiz Alvo: {raiz_alvo} vs Encontrado: {limpar_string(cnpj_item)[:8]}"
                        itens_descartados.append(item)
                        
        except Exception as e:
            pass
            
    return resultados_reais, itens_descartados

# --- CONTRATOS (MANTIDO PERFEITO) ---
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

aba1, aba2 = st.tabs(["🕵️ Compliance (Auditoria)", "💰 Monitor de Gastos"])

# --- ABA 1: AUDITORIA ---
with aba1:
    st.header("Análise de Fornecedor")
    cnpj_input = st.text_input("CNPJ:", value="05.144.757/0001-72")
    
    if st.button("Verificar Antecedentes", type="primary"):
        nome_empresa = ""
        
        # 1. Receita Federal (Identificação)
        with st.spinner("Consultando Receita Federal..."):
            try:
                r = requests.get(f"https://minhareceita.org/{limpar_string(cnpj_input)}", timeout=3)
                if r.status_code == 200:
                    data_receita = r.json()
                    nome_empresa = data_receita.get('razao_social', '')
                    situacao = data_receita.get('descricao_situacao_cadastral', 'Desconhecida')
                    st.info(f"🏢 **{nome_empresa}** ({situacao})")
            except: 
                st.warning("⚠️ MinhaReceita indisponível, prosseguindo apenas com CNPJ.")

        # 2. Auditoria (CEIS/CNEP/Leniência)
        with st.spinner("Vasculhando listas de sanções..."):
            sancoes, descartados = auditar_cnpj_detalhado(cnpj_input, nome_empresa)
            
            st.divider()
            
            if sancoes:
                st.error(f"🚨 **ALERTA VERMELHO: {len(sancoes)} REGISTROS ENCONTRADOS**")
                for s in sancoes:
                    with st.expander(f"⚠️ {s['_origem']} - {s.get('dataPublicacao', 'S/ Data')}"):
                        st.write(f"**Empresa Citada:** {s['_nome_encontrado']}")
                        st.write(f"**CNPJ Citado:** {s['_cnpj_encontrado']}")
                        st.write(f"**Motivo:** {s.get('motivo') or s.get('situacaoAcordo')}")
                        st.write(f"**Órgão:** {s.get('orgaoSancionador', {}).get('nome')}")
            else:
                st.success(f"✅ **NADA CONSTA** para o CNPJ {cnpj_input}")
                st.caption("Nenhuma sanção ativa encontrada vinculada diretamente a esta raiz de CNPJ.")

            # --- DEBUG AREA (SÓ ABRA SE TIVER DUVIDA) ---
            if len(descartados) > 0:
                with st.expander("🛠️ Debug: Registros Ignorados (Falso Positivo?)"):
                    st.warning("Estes itens vieram da API mas foram filtrados por não baterem CNPJ exato.")
                    for d in descartados:
                        st.text(f"Origem: {d['_origem']}")
                        st.text(f"Nome: {d['_nome_encontrado']} | CNPJ: {d['_cnpj_encontrado']}")
                        st.text(f"Motivo Descarte: {d['_motivo_descarte']}")
                        st.divider()

# --- ABA 2: CONTRATOS ---
with aba2:
    st.header("Monitoramento Financeiro")
    orgao_nome = st.selectbox("Órgão", list(ORGAOS_SIAFI.keys()))
    
    if st.button("Carregar Contratos"):
        cod = ORGAOS_SIAFI[orgao_nome]
        with st.spinner(f"Baixando dados do {orgao_nome}..."):
            raw = buscar_contratos(cod)
            
            if raw:
                dados_tab = []
                total = 0.0
                for item in raw:
                    val = safe_float(item.get('valorInicialCompra') or item.get('valorFinalCompra'))
                    total += val
                    dados_tab.append({
                        "Data": item.get('dataAssinatura'),
                        "Fornecedor": item.get('fornecedor', {}).get('nome', '')[:40],
                        "Objeto": item.get('objeto', '')[:80] + "...",
                        "Valor": val
                    })
                
                df = pd.DataFrame(dados_tab)
                m1, m2 = st.columns(2)
                m1.metric("Total Analisado", f"R$ {total:,.2f}")
                m2.metric("Qtd. Contratos", len(df))
                
                st.dataframe(
                    df.sort_values("Data", ascending=False).style.format({"Valor": "R$ {:,.2f}"}),
                    use_container_width=True, hide_index=True
                )
            else:
                st.warning("Nenhum contrato recente encontrado.")