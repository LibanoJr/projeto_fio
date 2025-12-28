import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Auditoria Gov", page_icon="⚖️", layout="wide")

PORTAL_KEY = "d03ede6b6072b78e6df678b6800d4ba1"

# Adicionei a CGU que costuma ter dados limpos
ORGAOS_SIAFI = {
    "Ministério da Saúde": "36000",
    "Ministério da Educação": "26000",
    "DNIT (Transportes)": "39252",
    "Comando do Exército": "52121",
    "Polícia Federal": "30108",
    "Controladoria-Geral (CGU)": "20000"
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

# CORREÇÃO CRÍTICA PARA VALORES MONETÁRIOS
def converter_dinheiro(valor):
    if valor is None: return 0.0
    try:
        # Se já for número, retorna
        if isinstance(valor, (int, float)):
            return float(valor)
        
        # Se for string "1.500,00"
        v_str = str(valor).strip()
        if "," in v_str:
            v_str = v_str.replace(".", "").replace(",", ".")
        return float(v_str)
    except:
        return 0.0

def auditar_firewall(cnpj_alvo):
    resultados_reais = []
    cnpj_limpo_alvo = limpar_cnpj(cnpj_alvo)
    
    bases = ["ceis", "cnep", "acordos-leniencia"]
    
    for base in bases:
        url = f"https://api.portaldatransparencia.gov.br/api-de-dados/{base}"
        params = {"cnpjSancionado": cnpj_limpo_alvo, "pagina": 1}
        
        try:
            resp = requests.get(url, params=params, headers=get_headers(), timeout=10)
            if resp.status_code == 200:
                lista_suja = resp.json()
                for item in lista_suja:
                    # Tenta pegar CNPJ em vários lugares
                    cnpj_item = ""
                    try: cnpj_item = item.get('sancionado', {}).get('codigoFormatado')
                    except: pass
                    if not cnpj_item:
                        try: cnpj_item = item.get('pessoa', {}).get('cnpjFormatado')
                        except: pass
                    
                    # Validação Raiz
                    if limpar_cnpj(cnpj_item).startswith(cnpj_limpo_alvo[:8]):
                        item['_origem_formatada'] = base.upper().replace("-", " ")
                        resultados_reais.append(item)
        except: pass
            
    return resultados_reais

def buscar_contratos_loop(codigo_orgao):
    todos_contratos = []
    dt_fim = datetime.now()
    dt_ini = dt_fim - timedelta(days=365)
    
    progress = st.progress(0)
    for pag in range(1, 4): # Pega 3 páginas (aprox 45-50 itens)
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
                d = r.json()
                if not d: break
                todos_contratos.extend(d)
                progress.progress(pag * 33)
            else: break
        except: break
    
    progress.empty()
    return todos_contratos

# --- INTERFACE ---
st.title("⚖️ Auditoria Gov Federal (V35 Final)")

aba1, aba2 = st.tabs(["🕵️ Auditoria CNPJ", "📊 Monitor de Contratos"])

# --- ABA 1 ---
with aba1:
    st.header("Auditoria de Compliance")
    col1, col2 = st.columns([3, 1])
    cnpj_input = col1.text_input("CNPJ:", value="05.144.757/0001-72") # Já deixei a ODEBRECHT de padrão
    
    if col2.button("Verificar", type="primary"):
        st.write("") 
        
        # 1. Identificação
        try:
            r = requests.get(f"https://minhareceita.org/{limpar_cnpj(cnpj_input)}", timeout=3)
            nome = r.json().get('razao_social', 'Empresa não identificada')
            st.info(f"Analisando: **{nome}**")
        except: pass

        # 2. Varredura
        sancoes = auditar_firewall(cnpj_input)
        
        st.divider()
        if sancoes:
            st.error(f"🚨 **ALERTA VERMELHO: {len(sancoes)} OCORRÊNCIAS**")
            for s in sancoes:
                with st.expander(f"⚠️ {s['_origem_formatada']}"):
                    st.write(f"**Motivo:** {s.get('motivo') or s.get('situacaoAcordo')}")
                    st.write(f"**Órgão:** {s.get('orgaoSancionador', {}).get('nome')}")
        else:
            st.success("✅ **NADA CONSTA** - CNPJ Limpo")

# --- ABA 2 ---
with aba2:
    st.header("Contratos (Correção de Valores)")
    orgao = st.selectbox("Órgão", list(ORGAOS_SIAFI.keys()))
    
    if st.button("Carregar Contratos"):
        dados = buscar_contratos_loop(ORGAOS_SIAFI[orgao])
        
        if dados:
            # --- DEBUG PARA VOCÊ VER ---
            with st.expander("🛠️ Debug Técnico (Ver dados brutos do 1º item)"):
                st.json(dados[0])
            
            lista = []
            total = 0.0
            
            for d in dados:
                # Tenta pegar o valor em campos diferentes
                val_bruto = d.get('valorInicial') or d.get('valorGlobal') or d.get('valorContratado')
                valor_real = converter_dinheiro(val_bruto)
                
                total += valor_real
                lista.append({
                    "Data": d.get('dataAssinatura'),
                    "Fornecedor": d.get('fornecedor', {}).get('nome', 'N/A')[:40],
                    "Valor": valor_real
                })
            
            df = pd.DataFrame(lista)
            
            c1, c2 = st.columns(2)
            c1.metric("Total Gasto", f"R$ {total:,.2f}")
            c2.metric("Qtd. Contratos", len(df))
            
            st.dataframe(df.sort_values("Data", ascending=False).style.format({"Valor": "R$ {:,.2f}"}), use_container_width=True)
        else:
            st.warning("Nenhum contrato retornado para este órgão.")