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

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Auditoria IA - Gov", page_icon="⚖️", layout="wide")
load_dotenv()

API_KEY_GOVERNO = "d03ede6b6072b78e6df678b6800d4ba1"
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
    """Transforma 12345678000199 em 12.345.678/0001-99"""
    if len(cnpj_limpo) != 14:
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
    headers = {"chave-api-dados": API_KEY_GOVERNO}
    params = {"dataInicioVigencia": "01/01/2024", "dataFimVigencia": "31/12/2024", "codigoOrgao": "26000", "pagina": 1}
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        return response.json() if response.status_code == 200 else []
    except:
        return []

def analisar_ia(texto):
    modelo = genai.GenerativeModel("gemini-pro")
    try:
        return modelo.generate_content(f"Auditoria resumida deste objeto de contrato: {texto}").text
    except:
        return "Erro IA."

def consultar_ficha_suja_blindada(cnpj_alvo):
    """
    Tenta com CNPJ limpo e CNPJ formatado (Estratégia Dupla).
    """
    cnpj_alvo_limpo = re.sub(r'\D', '', cnpj_alvo)
    cnpj_alvo_formatado = formatar_cnpj(cnpj_alvo_limpo)
    
    url = "https://api.portaldatransparencia.gov.br/api-de-dados/ceis"
    headers = {"chave-api-dados": API_KEY_GOVERNO}
    
    lista_final = []

    # TENTATIVA 1: Limpo
    try:
        params = {"cnpjSancionado": cnpj_alvo_limpo, "pagina": 1}
        response = requests.get(url, headers=headers, params=params, timeout=10)
        if response.status_code == 200:
            dados = response.json()
            for item in dados:
                cnpj_api = re.sub(r'\D', '', item.get('pessoa', {}).get('cnpjFormatado', ''))
                if cnpj_api == cnpj_alvo_limpo:
                    lista_final.append(item)
    except:
        pass

    # TENTATIVA 2: Formatado (Se 1 falhou)
    if not lista_final:
        try:
            params = {"cnpjSancionado": cnpj_alvo_formatado, "pagina": 1}
            response = requests.get(url, headers=headers, params=params, timeout=10)
            if response.status_code == 200:
                dados = response.json()
                for item in dados:
                    cnpj_api = re.sub(r'\D', '', item.get('pessoa', {}).get('cnpjFormatado', ''))
                    if cnpj_api == cnpj_alvo_limpo:
                        lista_final.append(item)
        except:
            pass

    return lista_final

def gerar_pdf(cnpj, nome, dados):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()
    
    elements.append(Paragraph(f"RELATÓRIO DE AUDITORIA", styles['Title']))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(f"<b>Empresa:</b> {nome}", styles['Normal']))
    elements.append(Paragraph(f"<b>CNPJ:</b> {cnpj}", styles['Normal']))
    elements.append(Spacer(1, 20))
    
    data = [["Sanção", "Órgão", "Data"]]
    for d in dados:
        tipo = d.get('tipoSancao',{}).get('descricaoResumida','Unknown')[:40]
        orgao = d.get('orgaoSancionador',{}).get('nome','Unknown')[:30]
        data_pub = d.get('dataPublicacaoSancao', '-')
        data.append([tipo, orgao, data_pub])
        
    t = Table(data, colWidths=[200, 180, 80])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.darkred),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 1, colors.black)
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

st.title("🏛️ Sistema de Compliance")

if opcao == "🔍 Analisar Contratos":
    if st.button("Buscar Contratos MEC"):
        contratos = buscar_contratos()
        if contratos:
            st.success(f"{len(contratos)} contratos recentes.")
            for c in contratos[:2]:
                with st.expander(f"Contrato R$ {c.get('valorInicialCompra')}"):
                    st.write(c.get('objeto'))
                    st.info(analisar_ia(c.get('objeto')))

elif opcao == "🚫 Consultar Empresa (CNPJ)":
    st.header("Investigação de CNPJ")
    
    with st.form("busca"):
        cnpj_in = st.text_input("CNPJ (Apenas números ou formatado):")
        btn = st.form_submit_button("Identificar e Investigar")
    
    if btn:
        if len(re.sub(r'\D','',cnpj_in)) != 14:
            st.error("CNPJ deve ter 14 dígitos.")
        else:
            # 1. TENTA IDENTIFICAR O NOME
            with st.spinner("Buscando cadastro..."):
                nome_empresa = buscar_dados_receita(cnpj_in)
            
            # SE FALHAR O NOME, NÃO PARA O CÓDIGO!
            if not nome_empresa:
                nome_empresa = "Razão Social Não Disponível (CNPJ Baixado/Antigo)"
                st.warning("⚠️ O nome da empresa não foi encontrado na base pública (possível CNPJ baixado). O sistema forçará a busca por sanções.")
            else:
                st.success(f"🏢 Empresa Identificada: **{nome_empresa}**")
            
            st.session_state['nome_empresa_atual'] = nome_empresa

            # 2. EXECUTA A BUSCA DE SANÇÕES (SEMPRE)
            with st.spinner("Varrendo Lista Negra do Governo..."):
                resultado_real = consultar_ficha_suja_blindada(cnpj_in)
                st.session_state['dados_busca'] = resultado_real
                st.session_state['cnpj_atual'] = cnpj_in

    # EXIBIÇÃO DOS RESULTADOS
    if st.session_state['dados_busca'] is not None:
        # Check de segurança (se o CNPJ da tela é o mesmo da memória)
        input_limpo = re.sub(r'\D','', cnpj_in)
        memoria_limpo = re.sub(r'\D','', st.session_state['cnpj_atual'])

        if input_limpo == memoria_limpo:
            sancoes = st.session_state['dados_busca']
            nome = st.session_state['nome_empresa_atual']
            
            if len(sancoes) == 0:
                st.divider()
                st.success(f"✅ NADA CONSTA")
                st.markdown(f"O CNPJ **{st.session_state['cnpj_atual']}** ({nome}) foi auditado e está limpo no CEIS.")
            else:
                st.divider()
                st.error(f"🚨 ALERTA VERMELHO: {len(sancoes)} SANÇÕES ENCONTRADAS!")
                st.write(f"**Entidade:** {nome}")
                
                # Gera PDF
                try:
                    pdf = gerar_pdf(st.session_state['cnpj_atual'], nome, sancoes)
                    st.download_button("📥 Baixar Dossiê Completo (PDF)", data=pdf, file_name="relatorio_auditoria.pdf")
                except:
                    st.warning("Não foi possível gerar o PDF, veja os dados abaixo.")

                # Lista detalhes
                for i, s in enumerate(sancoes):
                    with st.expander(f"🔴 Processo #{i+1}"):
                        st.write(f"**Motivo:** {s.get('fundamentacao',[{}])[0].get('descricao','-')}")
                        st.write(f"**Data:** {s.get('dataPublicacaoSancao','-')}")
                        st.json(s)