import streamlit as st
import requests
import pandas as pd
import google.generativeai as genai
import os
from dotenv import load_dotenv
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
import io

# --- CONFIGURAÇÃO INICIAL DA PÁGINA ---
st.set_page_config(page_title="Auditoria IA - Gov", page_icon="⚖️", layout="wide")
load_dotenv()

# --- CONFIGURAÇÃO DE CHAVES DE API ---
# Tenta pegar do sistema (Streamlit Cloud) ou do arquivo .env (Local)
API_KEY_GOVERNO = os.getenv("API_KEY_GOVERNO")
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# --- INICIALIZAÇÃO DA MEMÓRIA (SESSION STATE) ---
# Garante que os dados não sumam ao clicar em botões
if 'dados_busca' not in st.session_state:
    st.session_state['dados_busca'] = None
if 'cnpj_atual' not in st.session_state:
    st.session_state['cnpj_atual'] = ""

# --- FUNÇÕES DE BACKEND (O CÉREBRO DO SISTEMA) ---

def buscar_contratos():
    """Busca contratos recentes do MEC (Exemplo didático)"""
    url = "https://api.portaldatransparencia.gov.br/api-de-dados/contratos"
    headers = {"chave-api-dados": API_KEY_GOVERNO}
    params = {
        "dataInicioVigencia": "01/01/2024",
        "dataFimVigencia": "31/01/2024",
        "codigoOrgao": "26000", # Ministério da Educação
        "pagina": 1
    }
    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            return response.json()
        return []
    except:
        return []

def analisar_ia(texto_contrato):
    """Usa o Gemini para ler e auditar o objeto do contrato"""
    modelo = genai.GenerativeModel("gemini-pro")
    prompt = f"""
    Você é um auditor federal especializado em combate à corrupção.
    Analise o seguinte resumo de contrato público e aponte:
    1. O objeto do contrato é claro ou vago?
    2. Há riscos aparentes?
    3. Dê um veredito final: 'Parece Normal' ou 'Requer Atenção'.
    
    Texto do Contrato: {texto_contrato}
    """
    try:
        resposta = modelo.generate_content(prompt)
        return resposta.text
    except Exception as e:
        return "Erro na análise de IA."

def consultar_ficha_suja(cnpj_consulta):
    """Consulta o Cadastro de Empresas Inidôneas e Suspensas (CEIS)"""
    # Limpa pontuação do CNPJ
    cnpj_limpo = cnpj_consulta.replace(".", "").replace("/", "").replace("-", "")
    url = "https://api.portaldatransparencia.gov.br/api-de-dados/ceis"
    headers = {"chave-api-dados": API_KEY_GOVERNO}
    params = {"cnpjSancionado": cnpj_limpo, "pagina": 1}
    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            return response.json()
        return []
    except:
        return []

def gerar_pdf_relatorio(cnpj, dados_sancoes):
    """Gera um PDF profissional com os dados da auditoria"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()

    # Cabeçalho do PDF
    elements.append(Paragraph(f"RELATÓRIO DE AUDITORIA DE COMPLIANCE", styles['Title']))
    elements.append(Spacer(1, 12))
    
    elements.append(Paragraph(f"<b>Alvo da Investigação (CNPJ):</b> {cnpj}", styles['Normal']))
    elements.append(Paragraph(f"<b>Total de Sanções Encontradas:</b> {len(dados_sancoes)}", styles['Normal']))
    elements.append(Paragraph(f"<b>Data do Relatório:</b> 23/12/2025", styles['Normal']))
    elements.append(Spacer(1, 20))

    # Tabela de Dados
    dados_tabela = [["Tipo de Sanção", "Órgão Sancionador", "Data"]]
    
    for item in dados_sancoes:
        tipo = item.get('tipoSancao', {}).get('descricaoResumida', 'N/A')
        # Corta textos muito longos
        tipo_curto = (tipo[:50] + '...') if len(tipo) > 50 else tipo
        
        orgao = item.get('orgaoSancionador', {}).get('nome', 'N/A')
        orgao_curto = (orgao[:40] + '...') if len(orgao) > 40 else orgao
        
        data = item.get('dataPublicacaoSancao', 'N/A')
        dados_tabela.append([tipo_curto, orgao_curto, data])

    # Estilização da Tabela (Cores e Bordas)
    tabela = Table(dados_tabela, colWidths=[220, 180, 80])
    tabela.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkred),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    
    elements.append(tabela)
    elements.append(Spacer(1, 20))
    elements.append(Paragraph("Este documento foi gerado automaticamente pelo Sistema de Auditoria com IA.", styles['Italic']))

    doc.build(elements)
    buffer.seek(0)
    return buffer

# --- INTERFACE VISUAL (FRONTEND) ---

st.sidebar.title("👮‍♂️ Menu de Auditoria")
opcao = st.sidebar.radio(
    "Escolha a ferramenta:",
    ["🔍 Analisar Contratos (IA)", "🚫 Consultar Ficha Suja (CNPJ)"]
)

st.title("🚀 VERSÃO NOVA - AGORA VAI")

# --- TELA 1: AUDITORIA DE CONTRATOS ---
if opcao == "🔍 Analisar Contratos (IA)":
    st.header("Análise Inteligente de Contratos do MEC")
    st.markdown("A IA analisa contratos públicos recentes e identifica riscos de fraude.")
    
    if st.button("Buscar e Analisar Contratos Recentes"):
        with st.spinner("Conectando ao Portal da Transparência..."):
            dados = buscar_contratos()
        if len(dados) > 0:
            st.success(f"{len(dados)} contratos encontrados!")
            for contrato in dados[:3]: # Analisa os 3 primeiros
                with st.expander(f"Contrato: {contrato.get('numero', 'S/N')} - R$ {contrato.get('valorInicialCompra', '0')}"):
                    objeto = contrato.get('objeto', 'Sem descrição')
                    st.write(f"**Objeto:** {objeto}")
                    st.write("---")
                    st.subheader("🤖 Parecer da IA:")
                    with st.spinner("A IA está lendo o contrato..."):
                        analise = analisar_ia(objeto)
                        st.markdown(analise)
        else:
            st.warning("Nenhum contrato encontrado ou erro na API.")

# --- TELA 2: DASHBOARD DE COMPLIANCE (COM CORREÇÃO DE BUG) ---
elif opcao == "🚫 Consultar Ficha Suja (CNPJ)":
    st.header("Investigação de Antecedentes (CEIS)")
    st.markdown("Consulte se uma empresa está na **Lista Negra** (CEIS) e visualize o perfil de risco.")
    
    # --- ÁREA DE BUSCA COM FORMULÁRIO (Previne bugs de digitação) ---
    with st.form("form_investigacao"):
        col_input, col_btn = st.columns([4, 1])
        with col_input:
            cnpj_input = st.text_input("Digite o CNPJ (apenas números):", max_chars=14)
        with col_btn:
            st.write("") # Espaçamento
            st.write("")
            botao_investigar = st.form_submit_button("🕵️‍♂️ Investigar")
    
    # Lógica de processamento (Só roda se apertar o botão)
    if botao_investigar:
        if len(cnpj_input) < 14:
            st.error("Digite um CNPJ válido com 14 dígitos.")
        else:
            with st.spinner(f"Varrendo bancos de dados..."):
                # Limpa a memória anterior
                st.session_state['dados_busca'] = None
                # Busca novos dados
                resultados = consultar_ficha_suja(cnpj_input)
                # Salva na memória
                st.session_state['dados_busca'] = resultados
                st.session_state['cnpj_atual'] = cnpj_input

    # --- ÁREA DE EXIBIÇÃO DE RESULTADOS ---
    if st.session_state['dados_busca'] is not None:
        # Verifica se o CNPJ da memória é o mesmo da tela
        if st.session_state['cnpj_atual'] == cnpj_input:
            sancoes = st.session_state['dados_busca']
            cnpj_atual = st.session_state['cnpj_atual']

            if len(sancoes) > 0:
                # --- GERADOR DE PDF ---
                pdf_bytes = gerar_pdf_relatorio(cnpj_atual, sancoes)
                
                st.divider()
                # Barra de Alerta e Download
                col_kpi1, col_kpi2 = st.columns([3, 1])
                with col_kpi1:
                    st.error(f"🚨 ALERTA MÁXIMO: {len(sancoes)} SANÇÕES ENCONTRADAS!")
                with col_kpi2:
                    st.download_button(
                        label="📄 Baixar Laudo PDF",
                        data=pdf_bytes,
                        file_name=f"laudo_{cnpj_atual}.pdf",
                        mime="application/pdf"
                    )
                
                # --- DASHBOARD VISUAL ---
                # Prepara dados para os gráficos
                df = pd.DataFrame(sancoes)
                df['Orgao_Nome'] = df['orgaoSancionador'].apply(lambda x: x.get('nome') if isinstance(x, dict) else 'Desconhecido')
                df['Tipo_Sancao'] = df['tipoSancao'].apply(lambda x: x.get('descricaoResumida') if isinstance(x, dict) else 'Outros')
                
                # KPIs Numéricos
                c1, c2, c3 = st.columns(3)
                c1.metric("Total de Processos", len(sancoes))
                c2.metric("Órgãos Diferentes", df['Orgao_Nome'].nunique())
                c3.metric("Punição Mais Comum", df['Tipo_Sancao'].mode()[0] if not df.empty else "N/A")
                
                st.divider()
                
                # Gráficos Lado a Lado
                g1, g2 = st.columns(2)
                with g1:
                    st.subheader("🏛️ Quem puniu?")
                    st.bar_chart(df['Orgao_Nome'].value_counts())
                with g2:
                    st.subheader("⚖️ Tipos de Pena")
                    st.bar_chart(df['Tipo_Sancao'].value_counts(), color="#FF4B4B")
                
                # Lista Detalhada
                st.subheader("📂 Detalhamento dos Processos")
                for i, punicao in enumerate(sancoes):
                    tipo_pena = punicao.get('tipoSancao', {}).get('descricaoResumida', 'Sanção Genérica')
                    orgao = punicao.get('orgaoSancionador', {}).get('nome', 'Órgão Desconhecido')
                    data = punicao.get('dataPublicacaoSancao', 'Data N/A')
                    detalhe = punicao.get('fundamentacao', [{}])[0].get('descricao', 'Sem detalhes.')
                    
                    with st.expander(f"Processo #{i+1}: {tipo_pena}"):
                        st.write(f"**Órgão:** {orgao}")
                        st.write(f"**Data:** {data}")
                        st.info(detalhe)

            else:
                # Caso a empresa esteja limpa
                st.divider()
                st.success(f"✅ NADA CONSTA PARA O CNPJ {cnpj_atual}. Empresa Limpa!")
                st.balloons()