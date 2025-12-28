import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import time

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Auditoria Gov", page_icon="⚖️", layout="wide")

PORTAL_KEY = "d03ede6b6072b78e6df678b6800d4ba1"

# Adicionei órgãos que TEM que ter contrato (DNIT, INSS)
ORGAOS_SIAFI = {
    "Ministério da Saúde": "36000",
    "Ministério da Educação": "26000",
    "DNIT (Transportes)": "39252",
    "INSS": "33201",
    "Polícia Federal": "30108",
    "Comando do Exército": "52121",
    "Ministério da Justiça": "30000"
}

# --- FUNÇÕES TÉCNICAS ---
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

# --- LÓGICA DO FIREWALL (AUDITORIA) ---
def auditar_firewall(cnpj_alvo):
    resultados_reais = []
    cnpj_limpo_alvo = limpar_cnpj(cnpj_alvo)
    
    # Bases: CEIS, CNEP e Acordos de Leniência
    bases = ["ceis", "cnep", "acordos-leniencia"]
    
    for base in bases:
        url = f"https://api.portaldatransparencia.gov.br/api-de-dados/{base}"
        params = {"cnpjSancionado": cnpj_limpo_alvo, "pagina": 1}
        
        try:
            resp = requests.get(url, params=params, headers=get_headers(), timeout=10)
            if resp.status_code == 200:
                lista_suja = resp.json()
                
                # O FIREWALL: Filtra item por item
                for item in lista_suja:
                    cnpj_item = ""
                    
                    # Tenta achar onde o governo escondeu o CNPJ nesse registro
                    try: cnpj_item = item.get('sancionado', {}).get('codigoFormatado')
                    except: pass
                    
                    if not cnpj_item:
                        try: cnpj_item = item.get('pessoa', {}).get('cnpjFormatado')
                        except: pass

                    # Só aceita se a RAIZ (8 primeiros dígitos) bater
                    # Isso aceita filial (0001, 0002) mas bloqueia outras empresas
                    cnpj_item_limpo = limpar_cnpj(cnpj_item)
                    
                    if cnpj_item_limpo.startswith(cnpj_limpo_alvo[:8]):
                        item['_origem_formatada'] = base.upper().replace("-", " ")
                        resultados_reais.append(item)
                        
        except Exception as e:
            pass
            
    return resultados_reais

# --- LÓGICA DE PAGINAÇÃO (CONTRATOS) ---
def buscar_contratos_loop(codigo_orgao):
    todos_contratos = []
    dt_fim = datetime.now()
    dt_ini = dt_fim - timedelta(days=365) # 1 Ano
    
    # Loop forçado: Pega página 1, 2, 3 e 4 (aprox 60 contratos)
    progress_bar = st.progress(0)
    
    for pag in range(1, 5):
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
                if not dados: break # Se vier vazio, para de tentar
                todos_contratos.extend(dados)
                progress_bar.progress(pag * 25)
            else:
                break
        except:
            break
            
    progress_bar.empty()
    return todos_contratos

# --- INTERFACE ---
st.title("⚖️ Auditoria Gov Federal (Versão Final)")

aba1, aba2 = st.tabs(["🕵️ Auditoria CNPJ", "📊 Monitor de Contratos"])

# --- ABA 1: AUDITORIA ---
with aba1:
    st.header("Compliance & Antecedentes")
    st.info("ℹ️ Sistema com validação estrita de CNPJ (Anti-Falso Positivo).")
    
    # Input
    col_in, col_btn = st.columns([3, 1])
    with col_in:
        cnpj_input = st.text_input("Digite o CNPJ:", placeholder="00.000.000/0000-00")
    with col_btn:
        st.write("") # Espaço
        st.write("") 
        btn_auditar = st.button("🔍 Verificar", type="primary")
    
    if btn_auditar and cnpj_input:
        if len(limpar_cnpj(cnpj_input)) != 14:
            st.warning("CNPJ parece incompleto.")
        else:
            with st.spinner("Confrontando bases (CEIS, CNEP, Leniência)..."):
                # 1. Busca Nome (MinhaReceita)
                try:
                    r_rec = requests.get(f"https://minhareceita.org/{limpar_cnpj(cnpj_input)}", timeout=5)
                    dados_rec = r_rec.json()
                    razao = dados_rec.get('razao_social') or "Razão Social não encontrada"
                    st.markdown(f"### 🏢 {razao}")
                except:
                    st.markdown("### 🏢 Empresa em análise")

                # 2. Auditoria Firewall
                sancoes = auditar_firewall(cnpj_input)
                
                st.divider()
                
                if len(sancoes) > 0:
                    st.error(f"🚨 **ALERTA: {len(sancoes)} RESTRIÇÕES ENCONTRADAS**")
                    st.caption("Estes registros conferem exatamente com a raiz do CNPJ informado.")
                    
                    for s in sancoes:
                        with st.expander(f"⚠️ {s['_origem_formatada']} - Ver Detalhes"):
                            st.write(f"**Órgão:** {s.get('orgaoSancionador', {}).get('nome')}")
                            st.write(f"**Motivo:** {s.get('motivo') or s.get('situacaoAcordo', 'Não informado')}")
                            data_ref = s.get('dataPublicacao') or s.get('dataInicioAcordo')
                            st.write(f"**Data:** {data_ref}")
                else:
                    st.success(f"✅ **NADA CONSTA**")
                    st.write(f"Nenhum registro ativo encontrado para o CNPJ {cnpj_input} nas listas de sanções ou leniência.")

# --- ABA 2: CONTRATOS ---
with aba2:
    st.header("Monitoramento de Contratos (Loop)")
    
    orgao_nome = st.selectbox("Selecione o Órgão", list(ORGAOS_SIAFI.keys()))
    
    if st.button("Buscar Contratos"):
        cod = ORGAOS_SIAFI[orgao_nome]
        
        with st.spinner(f"Coletando páginas de contratos do {orgao_nome}..."):
            raw_data = buscar_contratos_loop(cod)
            
            if raw_data:
                lista_formatada = []
                total = 0.0
                
                for d in raw_data:
                    valor = safe_float(d.get('valorInicial') or d.get('valorGlobal'))
                    total += valor
                    lista_formatada.append({
                        "Data Assinatura": d.get('dataAssinatura'),
                        "Fornecedor": d.get('fornecedor', {}).get('nome', 'DESCONHECIDO')[:40],
                        "Valor": valor
                    })
                
                df = pd.DataFrame(lista_formatada)
                
                # Métricas
                c1, c2 = st.columns(2)
                c1.metric("Total Gasto (Recente)", f"R$ {total:,.2f}")
                c2.metric("Contratos Analisados", len(df))
                
                st.dataframe(df.sort_values("Data Assinatura", ascending=False).style.format({"Valor": "R$ {:,.2f}"}), use_container_width=True)
            else:
                st.warning("⚠️ Nenhum contrato encontrado.")
                st.markdown("**Diagnóstico:** O órgão selecionado não reportou contratos no último ano ou está com instabilidade momentânea.")