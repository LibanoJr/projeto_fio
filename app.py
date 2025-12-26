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
st.set_page_config(page_title="Auditoria Gov - Clean", page_icon="⚖️", layout="wide")
load_dotenv()

# Configuração de Chaves
API_KEY_GOVERNO = os.getenv("API_KEY_GOVERNO") or "d03ede6b6072b78e6df678b6800d4ba1"
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# --- FUNÇÕES AUXILIARES ---

def formatar_cnpj(cnpj_limpo):
    if not cnpj_limpo or len(cnpj_limpo) != 14: return cnpj_limpo
    return f"{cnpj_limpo[:2]}.{cnpj_limpo[2:5]}.{cnpj_limpo[5:8]}/{cnpj_limpo[8:12]}-{cnpj_limpo[12:]}"

def limpar_cnpj(cnpj):
    return re.sub(r'\D', '', str(cnpj))

def buscar_nome_receita(cnpj_limpo):
    """Busca o nome oficial na BrasilAPI para usar na pesquisa do Governo."""
    try:
        url = f"https://brasilapi.com.br/api/cnpj/v1/{cnpj_limpo}"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            dados = response.json()
            # Retorna Razão Social e o primeiro nome para busca (ex: BRAISCOMPANY)
            razao = dados.get('razao_social', '')
            primeiro_nome = razao.split()[0] if razao else ""
            return razao, primeiro_nome
    except:
        pass
    return None, None

def consultar_base_governo(nome_busca, cnpj_alvo_limpo, base):
    """
    Busca por NOME (mais confiável) e filtra o CNPJ no Python.
    """
    url = f"https://api.portaldatransparencia.gov.br/api-de-dados/{base}"
    headers = {"chave-api-dados": API_KEY_GOVERNO}
    
    # A mágica: Buscamos pelo NOME, não pelo CNPJ (que a API buga)
    params = {"nomeSancionado": nome_busca, "pagina": 1}
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        
        if response.status_code == 200:
            registros = response.json()
            encontrados = []
            
            # Filtragem Local (Onde o Python é melhor que a API)
            for item in registros:
                # Extrai CNPJ de qualquer campo possível do JSON
                cnpj_retorno = (item.get('pessoa', {}).get('cnpjFormatado') or 
                                item.get('sancionado', {}).get('codigoFormatado') or "")
                
                cnpj_retorno_limpo = limpar_cnpj(cnpj_retorno)
                
                # Compara os 8 primeiros dígitos (Raiz do CNPJ)
                if cnpj_retorno_limpo.startswith(cnpj_alvo_limpo[:8]):
                    item['origem'] = base.upper()
                    encontrados.append(item)
            
            return encontrados
            
    except Exception as e:
        st.error(f"Erro de conexão com {base.upper()}: {e}")
    
    return []

# --- GERAÇÃO DE PDF ---
def gerar_pdf_relatorio(cnpj, nome, sancoes):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()
    
    elements.append(Paragraph(f"RELATÓRIO DE COMPLIANCE", styles['Title']))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(f"<b>Empresa:</b> {nome}", styles['Normal']))
    elements.append(Paragraph(f"<b>CNPJ:</b> {formatar_cnpj(cnpj)}", styles['Normal']))
    elements.append(Spacer(1, 20))
    
    if not sancoes:
        elements.append(Paragraph("Nenhuma sanção ativa encontrada nas bases CEIS/CNEP.", styles['Normal']))
    else:
        data = [["Base", "Órgão", "Data Publicação", "Motivo"]]
        for s in sancoes:
            base = s.get('origem', 'GOV')
            orgao = s.get('orgaoSancionador', {}).get('nome', 'N/A')[:25]
            data_pub = s.get('dataPublicacaoSancao', '-')
            motivo = "Verificar Detalhes"
            if 'fundamentacao' in s and s['fundamentacao']:
                motivo = s['fundamentacao'][0].get('descricao', '')[:50]
            data.append([base, orgao, data_pub, motivo])

        t = Table(data, colWidths=[50, 130, 80, 240])
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

# --- INTERFACE ---
st.title("🔎 Auditoria Fiscal - Busca Reversa")

with st.form("form_busca"):
    col1, col2 = st.columns([3, 1])
    with col1:
        cnpj_input = st.text_input("Digite o CNPJ (com ou sem pontuação):")
    with col2:
        st.write("")
        st.write("")
        btn_buscar = st.form_submit_button("🛡️ Auditar Agora")

if btn_buscar:
    cnpj_limpo = limpar_cnpj(cnpj_input)
    
    if len(cnpj_limpo) != 14:
        st.warning("CNPJ inválido. Digite 14 números.")
    else:
        st.info(f"Iniciando varredura para CNPJ: {formatar_cnpj(cnpj_limpo)}")
        
        # 1. Identificação
        razao_social, termo_busca = buscar_nome_receita(cnpj_limpo)
        
        if not razao_social:
            st.error("CNPJ não encontrado na Receita Federal ou inativo. Não é possível buscar pelo nome.")
        else:
            st.success(f"🏢 Empresa: **{razao_social}**")
            st.caption(f"Estratégia: Buscando sanções para o termo '{termo_busca}' e validando CNPJ.")
            
            todas_sancoes = []
            
            # 2. Varredura CEIS
            with st.spinner("Consultando CEIS..."):
                res_ceis = consultar_base_governo(termo_busca, cnpj_limpo, "ceis")
                todas_sancoes.extend(res_ceis)
                
            # 3. Varredura CNEP
            with st.spinner("Consultando CNEP..."):
                res_cnep = consultar_base_governo(termo_busca, cnpj_limpo, "cnep")
                todas_sancoes.extend(res_cnep)

            # 4. Resultado Final
            st.divider()
            if not todas_sancoes:
                st.balloons()
                st.success("✅ NADA CONSTA")
                st.markdown(f"A empresa **{razao_social}** não possui registros ativos no CEIS ou CNEP.")
                
                # PDF Limpo
                pdf = gerar_pdf_relatorio(cnpj_limpo, razao_social, [])
                st.download_button("📥 Baixar Certidão Negativa (PDF)", pdf, "certidao_negativa.pdf", "application/pdf")
                
            else:
                st.error(f"🚨 ALERTA: {len(todas_sancoes)} REGISTROS ENCONTRADOS")
                
                # PDF Sujo
                pdf = gerar_pdf_relatorio(cnpj_limpo, razao_social, todas_sancoes)
                st.download_button("📥 Baixar Relatório de Sanções (PDF)", pdf, "relatorio_sancoes.pdf", "application/pdf")
                
                for sancao in todas_sancoes:
                    with st.expander(f"🔴 {sancao['origem']} - Data: {sancao.get('dataPublicacaoSancao')}"):
                        st.json(sancao)