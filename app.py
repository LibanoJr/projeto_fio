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
    headers = {"chave-api-dados": API_KEY_GOVERNO}
    params = {"dataInicioVigencia": "01/01/2024", "dataFimVigencia": "31/12/2024", "codigoOrgao": "26000", "pagina": 1}
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        return response.json() if response.status_code == 200 else []
    except:
        return []

def consultar_ficha_suja_force_brute(cnpj_alvo):
    """
    Tenta várias formas de pedir o dado para a API até ela respeitar o filtro.
    """
    cnpj_limpo = re.sub(r'\D', '', cnpj_alvo)
    if len(cnpj_limpo) != 14:
        return []

    cnpj_formatado = f"{cnpj_limpo[:2]}.{cnpj_limpo[2:5]}.{cnpj_limpo[5:8]}/{cnpj_limpo[8:12]}-{cnpj_limpo[12:]}"
    headers = {"chave-api-dados": API_KEY_GOVERNO, "accept": "application/json"}
    sancoes_confirmadas = []
    bases = ["ceis", "cnep"]

    with st.expander(f"🕵️ Log Técnico Detalhado ({cnpj_formatado})"):
        for base in bases:
            base_url = f"https://api.portaldatransparencia.gov.br/api-de-dados/{base}"
            sucesso_filtro = False # Flag para saber se a API obedeceu
            
            # --- ESTRATÉGIA "FORCE BRUTE": Tenta 3 variações de URL ---
            tentativas = [
                # 1. URL Montada Manualmente (Evita encode do requests)
                (f"{base_url}?cnpjSancionado={cnpj_formatado}&pagina=1", "Manual Formatado"),
                # 2. URL Manual Apenas Números
                (f"{base_url}?cnpjSancionado={cnpj_limpo}&pagina=1", "Manual Limpo"),
                # 3. Via Params (Padrão Requests - Encode %2F)
                (base_url, "Params Padrão") 
            ]

            for url_teste, metodo in tentativas:
                if sucesso_filtro: break # Se já funcionou, pula as outras tentativas
                
                try:
                    if metodo == "Params Padrão":
                        response = requests.get(url_teste, headers=headers, params={"cnpjSancionado": cnpj_formatado, "pagina": 1}, timeout=10)
                    else:
                        response = requests.get(url_teste, headers=headers, timeout=10)

                    if response.status_code == 200:
                        dados = response.json()
                        
                        # ANÁLISE DO RETORNO
                        if len(dados) == 0:
                            # Se voltou [], a API OBDECEU o filtro e não achou nada. SUCESSO.
                            st.write(f"✅ {base.upper()} ({metodo}): Filtro aceito. Retorno vazio (Limpo).")
                            sucesso_filtro = True
                        else:
                            # Se voltou dados, precisamos ver se é lixo ou ouro
                            match_count = 0
                            for item in dados:
                                # Extração segura do CNPJ
                                c_volta = (item.get('pessoa', {}).get('cnpjFormatado') or item.get('sancionado', {}).get('codigoFormatado') or "")
                                c_limpo_volta = re.sub(r'\D', '', str(c_volta))
                                
                                # Verifica Raiz (8 digitos)
                                if c_limpo_volta.startswith(cnpj_limpo[:8]):
                                    match_count += 1
                                    item['origem_dado'] = base.upper()
                                    if item not in sancoes_confirmadas:
                                        sancoes_confirmadas.append(item)
                            
                            if match_count > 0:
                                st.write(f"🚨 {base.upper()} ({metodo}): ALVO ENCONTRADO! ({match_count} sanções)")
                                sucesso_filtro = True
                            else:
                                # Se voltou 15 itens e nenhum bateu, a API ignorou o filtro. Tenta o próximo método.
                                st.write(f"⚠️ {base.upper()} ({metodo}): API ignorou filtro (Lista genérica). Tentando outro método...")

                except Exception as e:
                    st.write(f"❌ Erro em {metodo}: {e}")

            if not sucesso_filtro:
                st.write(f"⚠️ {base.upper()}: Falha em todas as tentativas de conexão.")

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

st.title("🏛️ Sistema de Compliance V4.0 (Force Brute)")

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
                nome_empresa = "Razão Social Não Disponível (CNPJ Baixado/Inativo)"
                st.warning("⚠️ Nome não encontrado. Prosseguindo com varredura de sanções.")
            else:
                st.success(f"🏢 Empresa Identificada: **{nome_empresa}**")
            
            st.session_state['nome_empresa_atual'] = nome_empresa
            st.session_state['cnpj_atual'] = cnpj_in

            with st.spinner("Varrendo Bases Governamentais (Modo Force Brute)..."):
                resultado_real = consultar_ficha_suja_force_brute(cnpj_in)
                st.session_state['dados_busca'] = resultado_real

    # EXIBIÇÃO
    if st.session_state['dados_busca'] is not None:
        sancoes = st.session_state['dados_busca']
        nome = st.session_state['nome_empresa_atual']
        
        st.divider()
        if len(sancoes) == 0:
            st.success(f"✅ NADA CONSTA (VALIDADO)")
            st.markdown(f"O CNPJ **{formatar_cnpj(st.session_state['cnpj_atual'])}** passou por todas as camadas de verificação e não possui sanções ativas.")
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