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
    # 1. Preparação
    cnpj_limpo = re.sub(r'\D', '', cnpj_alvo)
    if len(cnpj_limpo) != 14:
        return []

    # CNPJ formatado é essencial para a API, mas a codificação da URL pode quebrar
    cnpj_formatado = f"{cnpj_limpo[:2]}.{cnpj_limpo[2:5]}.{cnpj_limpo[5:8]}/{cnpj_limpo[8:12]}-{cnpj_limpo[12:]}"
    
    headers = {"chave-api-dados": API_KEY_GOVERNO, "accept": "*/*"}
    sancoes_confirmadas = []
    bases = ["ceis", "cnep"]

    with st.expander(f"🕵️ Log Técnico ({cnpj_formatado})"):
        for base in bases:
            base_url = f"https://api.portaldatransparencia.gov.br/api-de-dados/{base}"
            
            # --- CORREÇÃO DE URL (A Mágica acontece aqui) ---
            # Construímos a URL manualmente para garantir que a "/" não vire "%2F"
            # e forçamos a string exata que o governo espera.
            url_final = f"{base_url}?cnpjSancionado={cnpj_formatado}&pagina=1"
            
            st.write(f"📡 Consultando **{base.upper()}**...")
            
            try:
                # Nota: Não usamos 'params=' aqui, usamos a url_final direta
                response = requests.get(url_final, headers=headers, timeout=15)
                
                if response.status_code == 200:
                    dados = response.json()
                    
                    # Se vier vazio, é SUCESSO (Empresa Limpa)
                    if len(dados) == 0:
                        st.write(f"✅ {base.upper()}: Base retornou 0 registros (Limpo).")
                    else:
                        # Se vier algo, precisamos ver se é o "lixo" padrão ou o nosso alvo
                        match_encontrado = False
                        for item in dados:
                            # Tenta extrair CNPJ de qualquer lugar do JSON
                            cnpj_voltou = (item.get('pessoa', {}).get('cnpjFormatado') or 
                                           item.get('sancionado', {}).get('codigoFormatado') or "")
                            
                            cnpj_voltou_limpo = re.sub(r'\D', '', str(cnpj_voltou))
                            
                            # Compara Raiz (8 primeiros) ou Tudo (14)
                            if cnpj_voltou_limpo == cnpj_limpo or (len(cnpj_voltou_limpo) >= 8 and cnpj_voltou_limpo[:8] == cnpj_limpo[:8]):
                                item['origem_dado'] = base.upper()
                                sancoes_confirmadas.append(item)
                                match_encontrado = True
                        
                        if match_encontrado:
                            st.write(f"🔴 **{base.upper()}:** Encontramos registros confirmados!")
                        else:
                            # Se retornou 15 mas nenhum bateu, a API ignorou o filtro
                            st.write(f"⚠️ {base.upper()}: API retornou lista genérica (Erro de filtro da API).")

                else:
                    st.write(f"⚠️ {base.upper()}: Erro {response.status_code}")
            except Exception as e:
                st.write(f"❌ Falha: {e}")

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
        
    t = Table(data, colWidths=[50, 150, 70, 200])
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

st.title("🏛️ Sistema de Compliance V3.0 (URL Fix)")

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
            with st.spinner("Buscando cadastro..."):
                nome_empresa = buscar_dados_receita(cnpj_in)
            
            if not nome_empresa:
                nome_empresa = "Razão Social Não Disponível"
                st.warning("⚠️ Nome não encontrado. O sistema buscará apenas sanções.")
            else:
                st.success(f"🏢 Empresa Identificada: **{nome_empresa}**")
            
            st.session_state['nome_empresa_atual'] = nome_empresa

            with st.spinner("Varrendo Bases Governamentais..."):
                resultado_real = consultar_ficha_suja_blindada(cnpj_in)
                st.session_state['dados_busca'] = resultado_real
                st.session_state['cnpj_atual'] = cnpj_in

   # EXIBIÇÃO
    if st.session_state['dados_busca'] is not None:
        input_limpo = re.sub(r'\D','', cnpj_in)
        memoria_limpo = re.sub(r'\D','', st.session_state['cnpj_atual'])

        if input_limpo == memoria_limpo:
            sancoes = st.session_state['dados_busca']
            nome = st.session_state['nome_empresa_atual']
            
            if len(sancoes) == 0:
                st.divider()
                st.success(f"✅ NADA CONSTA")
                st.markdown(f"O CNPJ **{formatar_cnpj(st.session_state['cnpj_atual'])}** foi auditado. Nenhuma sanção ativa encontrada.")
            else:
                st.divider()
                st.error(f"🚨 ALERTA VERMELHO: {len(sancoes)} SANÇÕES ENCONTRADAS!")
                st.markdown(f"**Empresa:** {nome}")
                st.markdown(f"**CNPJ Consultado:** {formatar_cnpj(st.session_state['cnpj_atual'])}")
                
                try:
                    pdf = gerar_pdf(st.session_state['cnpj_atual'], nome, sancoes)
                    st.download_button("📥 Baixar Dossiê (PDF)", data=pdf, file_name="relatorio_auditoria.pdf", mime='application/pdf')
                except Exception as e:
                    st.error(f"Erro ao gerar PDF: {e}")

                for i, s in enumerate(sancoes):
                    orgao = s.get('orgaoSancionador', {}).get('nome', 'Órgão não informado')
                    motivo = "Não detalhado"
                    if 'fundamentacao' in s and s['fundamentacao']:
                         motivo = s['fundamentacao'][0].get('descricao', '')
                    elif 'tipoSancao' in s:
                         motivo = s['tipoSancao'].get('descricaoResumida', '')

                    data_pub = s.get('dataPublicacaoSancao', '-')
                    origem = s.get('origem_dado', 'CEIS') 
                    
                    with st.expander(f"🔴 Sanção {i+1} ({origem}) - {orgao}"):
                        st.markdown(f"**Base de Dados:** {origem}")
                        st.markdown(f"**Data:** {data_pub}")
                        st.markdown(f"**Motivo:** {motivo}")