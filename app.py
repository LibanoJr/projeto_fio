import streamlit as st
import requests
import os
import re
import urllib3
from dotenv import load_dotenv
import io
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet

# Desativa avisos de SSL inseguro (Necessário para APIs Gov.br)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Auditoria V8 - Raw", page_icon="☢️", layout="wide")
load_dotenv()

API_KEY = os.getenv("API_KEY_GOVERNO") or "d03ede6b6072b78e6df678b6800d4ba1"

# --- FUNÇÕES ---

def limpar_cnpj(cnpj):
    return re.sub(r'\D', '', str(cnpj))

def formatar_cnpj(cnpj):
    c = limpar_cnpj(cnpj)
    if len(c) != 14: return c
    return f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}"

def get_company_name(cnpj):
    try:
        url = f"https://brasilapi.com.br/api/cnpj/v1/{cnpj}"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            # Retorna Razão Social e Nome Fantasia
            return data.get('razao_social', ''), data.get('nome_fantasia', '')
    except:
        pass
    return None, None

def consultar_api_gov_brute(termo_busca, tipo_busca, base):
    """
    tipo_busca: 'cnpj' ou 'nome'
    """
    url = f"https://api.portaldatransparencia.gov.br/api-de-dados/{base}"
    
    headers = {
        "chave-api-dados": API_KEY,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "application/json"
    }
    
    params = {"pagina": 1}
    
    if tipo_busca == 'cnpj':
        # Tenta enviar formatado, pois a doc pede, mas a API é chata
        cnpj_fmt = formatar_cnpj(termo_busca)
        params["cnpjSancionado"] = cnpj_fmt
    else:
        params["nomeSancionado"] = termo_busca

    try:
        # verify=False é CRUCIAL para evitar erro de SSL silencioso do Gov.br
        response = requests.get(url, headers=headers, params=params, timeout=20, verify=False)
        return response
    except Exception as e:
        return str(e)

def analisar_resultados(lista_resultados, cnpj_alvo_limpo):
    matches = []
    if not isinstance(lista_resultados, list):
        return []
        
    for item in lista_resultados:
        # Extrai CNPJ de onde estiver
        c_formatado = item.get('pessoa', {}).get('cnpjFormatado') or \
                      item.get('sancionado', {}).get('codigoFormatado') or ""
        
        c_limpo = limpar_cnpj(c_formatado)
        
        # Match flexível (8 primeiros dígitos)
        if c_limpo and cnpj_alvo_limpo.startswith(c_limpo[:8]):
            matches.append(item)
        elif not c_limpo:
             # Se não tem CNPJ no item, mas o nome é idêntico (caso raro)
             matches.append(item)
             
    return matches

# --- FRONTEND ---
st.title("☢️ Auditoria V8: Diagnóstico Total")
st.markdown("Nesta versão, desativei a segurança SSL e vamos testar múltiplas chaves.")

col1, col2 = st.columns([3, 1])
with col1:
    cnpj_input = st.text_input("CNPJ Alvo:", value="")
with col2:
    st.write("")
    st.write("")
    btn = st.button("Executar Varredura")

if btn and cnpj_input:
    cnpj_limpo = limpar_cnpj(cnpj_input)
    st.write(f"🔧 Iniciando para CNPJ: **{formatar_cnpj(cnpj_limpo)}**")
    
    # 1. Pegar Nome
    razao, fantasia = get_company_name(cnpj_limpo)
    nomes_para_testar = []
    if razao: nomes_para_testar.append(razao.split()[0]) # Primeiro nome
    if fantasia: nomes_para_testar.append(fantasia.split()[0])
    
    st.info(f"📋 Cadastro encontrado: **{razao}** ({fantasia})")
    
    bases = ["ceis", "cnep"]
    encontrado_geral = False
    
    st.divider()
    
    for base in bases:
        st.subheader(f"📡 Base: {base.upper()}")
        
        # --- ESTRATÉGIA 1: BUSCA POR CNPJ ---
        resp = consultar_api_gov_brute(cnpj_limpo, 'cnpj', base)
        
        if isinstance(resp, str):
            st.error(f"Erro de conexão: {resp}")
        else:
            dados = resp.json()
            url_usada = resp.url
            status = resp.status_code
            
            matches = analisar_resultados(dados, cnpj_limpo)
            
            if matches:
                st.error(f"🚨 ALVO ENCONTRADO VIA CNPJ! ({len(matches)} registros)")
                st.json(matches)
                encontrado_geral = True
            else:
                st.write(f"🔹 Busca CNPJ retornou {len(dados)} itens genéricos (Falha de filtro da API).")
                with st.expander("Ver JSON Bruto (CNPJ)"):
                    st.code(dados)

        # --- ESTRATÉGIA 2: BUSCA POR NOME (BACKUP) ---
        if not encontrado_geral and nomes_para_testar:
            termo = nomes_para_testar[0] # Pega o primeiro nome (Ex: BRAISCOMPANY)
            st.write(f"🔄 Tentando busca por nome: **'{termo}'**")
            
            resp_nome = consultar_api_gov_brute(termo, 'nome', base)
            
            if not isinstance(resp_nome, str):
                dados_nome = resp_nome.json()
                matches_nome = analisar_resultados(dados_nome, cnpj_limpo)
                
                if matches_nome:
                    st.error(f"🚨 ALVO ENCONTRADO VIA NOME! ({len(matches_nome)} registros)")
                    st.json(matches_nome)
                    encontrado_geral = True
                else:
                    st.success(f"✅ Busca por nome '{termo}' retornou {len(dados_nome)} itens, mas nenhum bateu com o CNPJ alvo.")
                    with st.expander(f"Ver JSON Bruto (Nome: {termo})"):
                        st.json(dados_nome)

    st.divider()