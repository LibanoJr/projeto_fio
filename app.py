import streamlit as st
import requests
import pandas as pd
import google.generativeai as genai
import os
import re  # O faxineiro de texto
from dotenv import load_dotenv
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
import io

# --- CONFIGURAÇÃO INICIAL ---
st.set_page_config(page_title="Auditoria IA - Gov", page_icon="⚖️", layout="wide")
load_dotenv()

# --- CHAVES DE API ---
API_KEY_GOVERNO = os.getenv("API_KEY_GOVERNO")
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# --- MEMÓRIA (SESSION STATE) ---
if 'dados_busca' not in st.session_state:
    st.session_state['dados_busca'] = None
if 'cnpj_atual' not in st.session_state:
    st.session_state['cnpj_atual'] = ""

# --- FUNÇÕES (O CÉREBRO) ---

def buscar_contratos():
    """Busca contratos recentes no Portal da Transparência"""
    url = "https://api.portaldatransparencia.gov.br/api-de-dados/contratos"
    headers = {"chave-api-dados": API_KEY_GOVERNO}
    # Buscando contratos do Ministério da Educação (cód 26000) como exemplo
    params = {
        "dataInicioVigencia": "01/01/2024",
        "dataFimVigencia": "31/12/2024",
        "codigoOrgao": "26000", 
        "pagina": 1
    }
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        if response.status_code == 200:
            return response.json()
        return []
    except:
        return []

def analisar_ia(texto_contrato):
    """Usa o Gemini para auditar o contrato"""
    modelo = genai.GenerativeModel("gemini-pro")
    prompt = f"""
    Aja como um auditor federal. Analise este objeto de contrato público:
    "{texto_contrato}"
    
    Responda curto:
    1. O objeto é claro?
    2. Há risco de sobrepreço ou descrição vaga?
    3. Veredito: (Normal / Suspeito)
    """
    try:
        return modelo.generate_content(prompt).text
    except:
        return "Erro na análise de IA."

def consultar_ficha_suja(cnpj_consulta):
    """Consulta CEIS com limpeza rigorosa do CNPJ"""
    # --- A CORREÇÃO DE OURO (REMOVE PONTOS E TRAÇOS) ---
    cnpj_limpo = re.sub(r'\D', '', cnpj_consulta) 
    
    url = "https://api.portaldatransparencia.gov.br/api-de-dados/ceis"
    headers = {"chave-api-dados": API_KEY_GOVERNO}
    params = {"cnpjSancionado": cnpj_limpo, "pagina": 1}
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        if response.status_code == 200:
            return response.json()
        return [] # Retorna lista vazia se der erro, pra não travar
    except:
        return []

def gerar_pdf_relatorio(cnpj, dados_sancoes):
    """Gera o PDF bonitão"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()

    elements.append(Paragraph(f"RELATÓRIO DE AUDITORIA", styles['Title']))
    elements.append(Paragraph(f"<b>CNPJ Investigado:</b> {cnpj}", styles['Normal']))
    elements.append(Spacer(1, 12))

    dados_tabela = [["Tipo de Sanção", "Órgão Sancionador", "Data"]]
    for item in dados_sancoes:
        tipo = item.get('tipoSancao', {}).get('descricaoResumida', 'N/A')[:50]
        orgao = item.get('orgaoSancionador', {}).get('nome', 'N/A')[:40]
        data = item.get('dataPublicacaoSancao', 'N/A')
        dados_tabela.append([tipo, orgao, data])

    tabela = Table(dados_tabela, colWidths=[200, 180, 80])
    tabela.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkred),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    elements.append(tabela)
    doc.build(elements)
    buffer.seek(0)
    return buffer

# --- INTERFACE (FRONTEND) ---

st.sidebar.title("👮‍♂️ Menu de Auditoria")

# Botão de Reset
if st.sidebar.button("🗑️ Nova Consulta (Limpar Tudo)"):
    st.session_state.clear()
    st.rerun()

# Menu de Navegação
opcao = st.sidebar.radio(
    "Escolha a ferramenta:",
    ["🔍 Analisar Contratos (IA)", "🚫 Consultar Ficha Suja (CNPJ)"]
)

st.title("🏛️ Sistema de Auditoria e Compliance Governamental")

# --- TELA 1: CONTRATOS (IA) ---
if opcao == "🔍 Analisar Contratos (IA)":
    st.header("Análise Inteligente de Contratos do MEC")
    st.markdown("A IA analisa contratos públicos recentes em busca de riscos.")
    
    if st.button("Buscar e Analisar Contratos Recentes"):
        with st.spinner("Conectando ao Portal da Transparência..."):
            dados = buscar_contratos()
        
        if len(dados) > 0:
            st.success(f"{len(dados)} contratos recuperados!")
            # Analisa apenas os 3 primeiros para não gastar muita cota da IA
            for contrato in dados[:3]:
                num = contrato.get('numero', 'S/N')
                val = contrato.get('valorInicialCompra', '0')
                obj = contrato.get('objeto', 'Sem descrição')
                
                with st.expander(f"📄 Contrato {num} - R$ {val}"):
                    st.write(f"**Objeto:** {obj}")
                    st.write("---")
                    st.subheader("🤖 Parecer da IA:")
                    with st.spinner("Auditando..."):
                        analise = analisar_ia(obj)
                        st.info(analise)
        else:
            st.warning("Nenhum contrato encontrado ou erro de conexão com o Governo.")

# --- TELA 2: BUSCA CNPJ (AGORA CORRIGIDA) ---
elif opcao == "🚫 Consultar Ficha Suja (CNPJ)":
    st.header("Investigação de Antecedentes (CEIS)")
    st.markdown("Verifique se uma empresa está na **Lista Negra** (CEIS).")
    
    with st.form("form_investigacao"):
        col1, col2 = st.columns([4, 1])
        with col1:
            # Pode digitar com ponto, traço, o que for. O código limpa!
            cnpj_input = st.text_input("Digite o CNPJ da empresa:")
        with col2:
            st.write("")
            st.write("")
            btn_investigar = st.form_submit_button("🕵️‍♂️ Investigar")
            
    if btn_investigar:
        # Limpeza visual para validação
        cnpj_limpo_check = re.sub(r'\D', '', cnpj_input)
        
        if len(cnpj_limpo_check) != 14:
            st.error(f"CNPJ inválido! Detectados {len(cnpj_limpo_check)} dígitos. Digite os 14 números.")
        else:
            with st.spinner("Varrendo bases de dados governamentais..."):
                # Limpa memória antiga
                st.session_state['dados_busca'] = None
                
                # Busca REAL
                resultados = consultar_ficha_suja(cnpj_input)
                
                st.session_state['dados_busca'] = resultados
                st.session_state['cnpj_atual'] = cnpj_input

    # Exibição dos Resultados
    if st.session_state['dados_busca'] is not None:
        # Garante que é o mesmo CNPJ
        if re.sub(r'\D', '', st.session_state['cnpj_atual']) == re.sub(r'\D', '', cnpj_input):
            sancoes = st.session_state['dados_busca']
            
            if len(sancoes) > 0:
                st.divider()
                st.error(f"🚨 ALERTA: {len(sancoes)} PROCESSOS ENCONTRADOS!")
                
                # Botão PDF
                pdf = gerar_pdf_relatorio(cnpj_input, sancoes)
                st.download_button("📥 Baixar Relatório PDF", data=pdf, file_name="auditoria.pdf", mime="application/pdf")
                
                # Detalhes na tela
                for i, item in enumerate(sancoes):
                    nome_orgao = item.get('orgaoSancionador', {}).get('nome', 'Órgão Desconhecido')
                    motivo = item.get('fundamentacao', [{}])[0].get('descricao', 'Sem detalhes')
                    with st.expander(f"Processo #{i+1} - {nome_orgao}"):
                        st.write(f"**Motivo:** {motivo}")
                        st.json(item) # Mostra dados técnicos se quiser ver
            else:
                st.divider()
                st.success(f"✅ NADA CONSTA. A empresa de CNPJ {cnpj_input} está LIMPA!")
                st.balloons()