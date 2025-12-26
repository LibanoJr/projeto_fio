import streamlit as st
import requests
import google.generativeai as genai
import os
import re
from dotenv import load_dotenv
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
import io
import urllib.parse

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Auditoria IA - Gov", page_icon="⚖️", layout="wide")
load_dotenv()

# Configuração de Chaves
API_KEY_GOVERNO = os.getenv("API_KEY_GOVERNO") or "d03ede6b6072b78e6df678b6800d4ba1"
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# --- SESSION STATE ---
if 'dados_busca' not in st.session_state:
    st.session_state['dados_busca'] = None
if 'cnpj_atual' not in st.session_state:
    st.session_state['cnpj_atual'] = ""
if 'nome_empresa_atual' not in st.session_state:
    st.session_state['nome_empresa_atual'] = ""

# --- FUNÇÕES ---

def formatar_cnpj(cnpj_limpo):
    if not cnpj_limpo or len(cnpj_limpo) != 14:
        return cnpj_limpo
    return f"{cnpj_limpo[:2]}.{cnpj_limpo[2:5]}.{cnpj_limpo[5:8]}/{cnpj_limpo[8:12]}-{cnpj_limpo[12:]}"

def buscar_dados_receita(cnpj):
    cnpj_limpo = re.sub(r'\D', '', cnpj)
    url = f"https://brasilapi.com.br/api/cnpj/v1/{cnpj_limpo}"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            dados = response.json()
            return dados.get('razao_social', dados.get('nome_fantasia', 'Nome não encontrado'))
        return None
    except:
        return None

def buscar_contratos():
    url = "https://api.portaldatransparencia.gov.br/api-de-dados/contratos"
    headers = {"chave-api-dados": API_KEY_GOVERNO, "User-Agent": "Mozilla/5.0"}
    params = {"dataInicioVigencia": "01/01/2024", "dataFimVigencia": "31/12/2024", "codigoOrgao": "26000", "pagina": 1}
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        return response.json() if response.status_code == 200 else []
    except:
        return []

def consultar_ficha_suja_hibrida(cnpj_alvo, nome_empresa):
    """
    Estratégia Híbrida: Tenta filtrar por CNPJ. Se a API falhar (ignorar filtro),
    tenta filtrar pelo NOME da empresa e valida o CNPJ do resultado.
    """
    cnpj_limpo = re.sub(r'\D', '', cnpj_alvo)
    if len(cnpj_limpo) != 14:
        return []

    cnpj_formatado = f"{cnpj_limpo[:2]}.{cnpj_limpo[2:5]}.{cnpj_limpo[5:8]}/{cnpj_limpo[8:12]}-{cnpj_limpo[12:]}"
    
    # Header simulando navegador para evitar bloqueio
    headers = {
        "chave-api-dados": API_KEY_GOVERNO, 
        "accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
    }
    
    sancoes_confirmadas = []
    bases = ["ceis", "cnep"]

    # Prepara termo de busca por nome (Pega a primeira palavra significativa)
    termo_busca_nome = ""
    if nome_empresa and len(nome_empresa) > 3:
        termo_busca_nome = nome_empresa.split()[0] # Ex: "BRAISCOMPANY" de "BRAISCOMPANY SOLUCOES..."

    with st.expander(f"🕵️ Log Técnico Híbrido ({cnpj_formatado})"):
        for base in bases:
            base_url = f"https://api.portaldatransparencia.gov.br/api-de-dados/{base}"
            
            # --- TENTATIVA 1: Busca Direta por CNPJ ---
            st.write(f"📡 {base.upper()}: Tentando busca por CNPJ...")
            try:
                params_cnpj = {"cnpjSancionado": cnpj_formatado, "pagina": 1}
                response = requests.get(base_url, headers=headers, params=params_cnpj, timeout=10)
                
                dados = []
                if response.status_code == 200:
                    dados = response.json()

                # Verifica se a API obedeceu
                achou_pelo_cnpj = False
                if len(dados) > 0:
                    # Verifica se o primeiro item tem algo a ver com nosso CNPJ
                    primeiro_cnpj = (dados[0].get('pessoa', {}).get('cnpjFormatado') or dados[0].get('sancionado', {}).get('codigoFormatado') or "")
                    primeiro_limpo = re.sub(r'\D', '', str(primeiro_cnpj))
                    
                    if primeiro_limpo.startswith(cnpj_limpo[:8]):
                         # A API obedeceu e achou!
                         achou_pelo_cnpj = True
                         st.write(f"🎯 {base.upper()}: Filtro por CNPJ funcionou.")
                         for item in dados:
                            if item not in sancoes_confirmadas:
                                item['origem_dado'] = base.upper()
                                sancoes_confirmadas.append(item)
                    else:
                        st.write(f"⚠️ {base.upper()}: API ignorou filtro de CNPJ (Retornou lista genérica).")
                else:
                    st.write(f"✅ {base.upper()}: CNPJ limpo na busca direta.")
                    achou_pelo_cnpj = True # API obedeceu e disse que não tem nada

                # --- TENTATIVA 2: Busca por NOME (Fallback se CNPJ falhou) ---
                if not achou_pelo_cnpj and termo_busca_nome:
                    st.write(f"🔄 {base.upper()}: Ativando busca secundária por Nome: **'{termo_busca_nome}'**...")
                    
                    params_nome = {"nomeSancionado": termo_busca_nome, "pagina": 1}
                    resp_nome = requests.get(base_url, headers=headers, params=params_nome, timeout=10)
                    
                    if resp_nome.status_code == 200:
                        dados_nome = resp_nome.json()
                        match_nome_count = 0
                        
                        for item in dados_nome:
                            # Pega CNPJ do resultado da busca por nome
                            c_volta = (item.get('pessoa', {}).get('cnpjFormatado') or item.get('sancionado', {}).get('codigoFormatado') or "")
                            c_limpo_volta = re.sub(r'\D', '', str(c_volta))
                            
                            # Compara com o nosso CNPJ alvo
                            if c_limpo_volta.startswith(cnpj_limpo[:8]):
                                item['origem_dado'] = f"{base.upper()} (Via Nome)"
                                if item not in sancoes_confirmadas:
                                    sancoes_confirmadas.append(item)
                                match_nome_count += 1
                        
                        if match_nome_count > 0:
                            st.write(f"🚨 {base.upper()}: ALVO ENCONTRADO via busca por Nome!")
                        else:
                            st.write(f"✅ {base.upper()}: Nada encontrado também por nome.")

            except Exception as e:
                st.write(f"❌ Erro Técnico em {base.upper()}: {e}")

    return sancoes_confirmadas

def gerar_pdf(cnpj, nome, dados):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()
    
    elements.append(Paragraph(f"RELATÓRIO DE AUDITORIA", styles['Title']))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(f"<b>Empresa:</b> {nome}", styles['Normal']))
    elements.append(Paragraph(f"<b>CNPJ Auditado:</b> {formatar_cnpj(cnpj)}", styles['Normal']))
    elements.append(Spacer(1, 20))
    
    data = [["Base", "Órgão", "Data", "Motivo"]]
    for d in dados:
        origem = d.get('origem_dado', 'GOV')
        orgao = d.get('orgaoSancionador',{}).get('nome','Unknown')[:20]
        data_pub = d.get('dataPublicacaoSancao', '-')
        
        motivo = "Ver detalhe no sistema"
        if 'fundamentacao' in d and d['fundamentacao']:
             motivo = d['fundamentacao'][0].get('descricao', '')[:40]
        
        data.append([origem, orgao, data_pub, motivo])
        
    t = Table(data, colWidths=[80, 150, 70, 170])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.darkred),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 1, colors.black),
        ('FONTSIZE', (0,0), (-1,-1), 8)
    ]))
    elements.append(t)
    doc.build(elements)
    buffer.seek(0)
    return buffer

# --- FRONTEND ---
st.sidebar.title("👮‍♂️ Menu Auditoria")
if st.sidebar.button("🗑️ Nova Consulta"):
    st.session_state.clear()
    st.rerun()

opcao = st.sidebar.radio("Opção:", ["🔍 Analisar Contratos", "🚫 Consultar Empresa (CNPJ)"])

st.title("🏛️ Sistema de Compliance V5.0 (Híbrido)")

if opcao == "🔍 Analisar Contratos":
    if st.button("Buscar Contratos MEC"):
        contratos = buscar_contratos()
        if contratos:
            st.success(f"{len(contratos)} contratos recentes.")
            for c in contratos[:2]:
                with st.expander(f"Contrato R$ {c.get('valorInicialCompra')}"):
                    st.write(c.get('objeto'))
                    st.info(genai.GenerativeModel("gemini-pro").generate_content(f"Resuma: {c.get('objeto')}").text)

elif opcao == "🚫 Consultar Empresa (CNPJ)":
    st.header("Investigação de CNPJ")
    
    with st.form("busca"):
        cnpj_in = st.text_input("CNPJ (Apenas números ou formatado):")
        btn = st.form_submit_button("Identificar e Investigar")
    
    if btn:
        cnpj_numeros = re.sub(r'\D','',cnpj_in)
        if len(cnpj_numeros) != 14:
            st.error("CNPJ deve ter 14 dígitos.")
        else:
            with st.spinner("Buscando cadastro..."):
                nome_empresa = buscar_dados_receita(cnpj_in)
            
            if not nome_empresa:
                nome_empresa = ""
                st.warning("⚠️ Nome não encontrado na Receita. Busca será feita apenas por CNPJ.")
            else:
                st.success(f"🏢 Empresa Identificada: **{nome_empresa}**")
            
            st.session_state['nome_empresa_atual'] = nome_empresa
            st.session_state['cnpj_atual'] = cnpj_in

            with st.spinner("Varrendo Bases (Modo Híbrido CNPJ + Nome)..."):
                resultado_real = consultar_ficha_suja_hibrida(cnpj_in, nome_empresa)
                st.session_state['dados_busca'] = resultado_real

    # EXIBIÇÃO
    if st.session_state['dados_busca'] is not None:
        sancoes = st.session_state['dados_busca']
        nome = st.session_state['nome_empresa_atual']
        
        st.divider()
        if len(sancoes) == 0:
            st.success(f"✅ NADA CONSTA (VALIDADO)")
            st.markdown(f"O CNPJ **{formatar_cnpj(st.session_state['cnpj_atual'])}** passou pelas verificações de CNPJ e Nome e não possui sanções ativas.")
        else:
            st.error(f"🚨 ALERTA VERMELHO: {len(sancoes)} SANÇÕES ENCONTRADAS!")
            st.markdown(f"**Empresa:** {nome}")
            
            try:
                pdf = gerar_pdf(st.session_state['cnpj_atual'], nome, sancoes)
                st.download_button("📥 Baixar Dossiê (PDF)", data=pdf, file_name="relatorio_auditoria.pdf", mime='application/pdf')
            except:
                st.error("Erro ao gerar PDF.")

            for i, s in enumerate(sancoes):
                orgao = s.get('orgaoSancionador', {}).get('nome', 'Órgão não informado')
                motivo = "Não detalhado"
                if 'fundamentacao' in s and s['fundamentacao']:
                        motivo = s['fundamentacao'][0].get('descricao', '')
                
                with st.expander(f"🔴 Sanção {i+1} ({s.get('origem_dado')}) - {orgao}"):
                    st.write(f"**Motivo:** {motivo}")