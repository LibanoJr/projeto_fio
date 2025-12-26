import streamlit as st
import requests
import os
import re
from dotenv import load_dotenv
import io
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Auditoria Gov V7", page_icon="🕵️", layout="wide")
load_dotenv()

# API Key Pública (fallback)
API_KEY_GOVERNO = os.getenv("API_KEY_GOVERNO") or "d03ede6b6072b78e6df678b6800d4ba1"

# --- FUNÇÕES ---

def limpar_string_cnpj(texto):
    """Remove pontuação e deixa apenas números."""
    return re.sub(r'\D', '', str(texto))

def formatar_cnpj(cnpj_limpo):
    if len(cnpj_limpo) != 14: return cnpj_limpo
    return f"{cnpj_limpo[:2]}.{cnpj_limpo[2:5]}.{cnpj_limpo[5:8]}/{cnpj_limpo[8:12]}-{cnpj_limpo[12:]}"

def obter_nome_limpo(cnpj):
    """
    Busca na BrasilAPI e limpa o nome para evitar que o CNPJ venha junto.
    Ex: '12345 EMPRESA X' vira 'EMPRESA X' e o termo vira 'EMPRESA'.
    """
    try:
        url = f"https://brasilapi.com.br/api/cnpj/v1/{cnpj}"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            dados = response.json()
            razao_bruta = dados.get('razao_social', '') or dados.get('nome_fantasia', '')
            
            # REMOVE NÚMEROS DO NOME (O PULO DO GATO)
            nome_sem_numeros = re.sub(r'\d+', '', razao_bruta).replace('.', '').replace('-', '').strip()
            
            # Pega o primeiro nome significativo (maior que 2 letras)
            partes = nome_sem_numeros.split()
            termo_busca = ""
            for p in partes:
                if len(p) > 2:
                    termo_busca = p
                    break
            
            return razao_bruta, termo_busca
    except:
        pass
    return None, None

def consultar_base_detalhada(termo_nome, cnpj_alvo_limpo, base):
    url = f"https://api.portaldatransparencia.gov.br/api-de-dados/{base}"
    headers = {"chave-api-dados": API_KEY_GOVERNO}
    params = {"nomeSancionado": termo_nome, "pagina": 1}
    
    log_tentativa = {"base": base, "termo": termo_nome, "retorno_api_qtd": 0, "matches": []}
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=15)
        
        if response.status_code == 200:
            dados = response.json()
            log_tentativa["retorno_api_qtd"] = len(dados)
            
            # Filtragem Inteligente
            for item in dados:
                # Tenta achar o CNPJ em vários lugares do JSON
                cnpj_encontrado = ""
                
                # 1. Tenta campo pessoa
                if 'pessoa' in item and 'cnpjFormatado' in item['pessoa']:
                    cnpj_encontrado = item['pessoa']['cnpjFormatado']
                
                # 2. Tenta campo sancionado
                elif 'sancionado' in item and 'codigoFormatado' in item['sancionado']:
                    val = item['sancionado']['codigoFormatado']
                    if len(val) > 11: # Filtra CPFs
                        cnpj_encontrado = val
                
                cnpj_item_limpo = limpar_string_cnpj(cnpj_encontrado)
                
                # COMPARAÇÃO (Raiz do CNPJ - 8 primeiros dígitos)
                match = False
                if cnpj_item_limpo.startswith(cnpj_alvo_limpo[:8]):
                    match = True
                
                # Salva para debug
                item_resumo = {
                    "nome_na_lista": item.get('sancionado', {}).get('nome', 'N/D'),
                    "cnpj_na_lista": cnpj_encontrado,
                    "match": match,
                    "dados_completos": item
                }
                
                if match:
                    log_tentativa["matches"].append(item_resumo)
                    
    except Exception as e:
        log_tentativa["erro"] = str(e)
        
    return log_tentativa

def gerar_pdf(cnpj, nome, logs):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()
    
    elements.append(Paragraph(f"DOSSIÊ DE AUDITORIA", styles['Title']))
    elements.append(Paragraph(f"<b>Alvo:</b> {nome}", styles['Normal']))
    elements.append(Paragraph(f"<b>CNPJ:</b> {formatar_cnpj(cnpj)}", styles['Normal']))
    elements.append(Spacer(1, 20))
    
    sanctions_found = []
    for log in logs:
        for m in log['matches']:
            sanctions_found.append(m)
            
    if not sanctions_found:
        elements.append(Paragraph("Certificamos que não foram encontradas sanções ativas baseadas nos filtros aplicados.", styles['Normal']))
    else:
        data = [["Nome na Lista", "CNPJ Vinculado", "Origem"]]
        for s in sanctions_found:
            data.append([
                s['nome_na_lista'][:30],
                s['cnpj_na_lista'],
                "Gov Federal"
            ])
        t = Table(data)
        t.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 1, colors.black)]))
        elements.append(t)
        
    doc.build(elements)
    buffer.seek(0)
    return buffer

# --- FRONTEND ---
st.title("🕵️ Auditoria V7 - Modo Detetive")
st.markdown("---")

col_in, col_btn = st.columns([3, 1])
with col_in:
    cnpj_digitado = st.text_input("CNPJ Alvo:", placeholder="Apenas números")
with col_btn:
    st.write("")
    st.write("")
    consultar = st.button("🔍 Investigar")

if consultar:
    cnpj_limpo = limpar_string_cnpj(cnpj_digitado)
    
    if len(cnpj_limpo) != 14:
        st.error("CNPJ Inválido (Necessário 14 dígitos)")
    else:
        # 1. Identificação e Limpeza de Nome
        with st.spinner("Identificando empresa..."):
            razao_social, termo_busca = obter_nome_limpo(cnpj_limpo)
        
        if not razao_social:
            st.warning("CNPJ não encontrado na base pública (BrasilAPI).")
            termo_busca = ""
        else:
            st.success(f"🏢 **{razao_social}**")
            st.info(f"🔎 Termo limpo usado na busca: **'{termo_busca}'**")
        
        # 2. Varredura com Logs
        if termo_busca:
            logs_gerais = []
            bases = ["ceis", "cnep"]
            total_matches = 0
            
            with st.status("Executando Varredura...", expanded=True):
                for base in bases:
                    st.write(f"📡 Conectando base **{base.upper()}**...")
                    resultado = consultar_base_detalhada(termo_busca, cnpj_limpo, base)
                    logs_gerais.append(resultado)
                    
                    matches = len(resultado['matches'])
                    total_matches += matches
                    
                    if matches > 0:
                        st.error(f"🚨 {base.upper()}: {matches} sanções confirmadas!")
                    elif resultado['retorno_api_qtd'] > 0:
                        st.warning(f"⚠️ {base.upper()}: {resultado['retorno_api_qtd']} registros com nome similar, mas CNPJ diferente.")
                    else:
                        st.success(f"✅ {base.upper()}: Nenhum registro encontrado para o nome.")

            # 3. Resultado Final
            st.divider()
            
            if total_matches == 0:
                st.balloons()
                st.success("✅ NADA CONSTA (CONFIRMADO)")
                st.write(f"O sistema buscou por **'{termo_busca}'**, analisou os retornos e nenhum CNPJ bateu com **{formatar_cnpj(cnpj_limpo)}**.")
            else:
                st.error(f"🚨 ALERTA: {total_matches} SANÇÕES ATIVAS")
                for log in logs_gerais:
                    for m in log['matches']:
                        with st.expander(f"🛑 Detalhe: {m['nome_na_lista']}"):
                            st.json(m['dados_completos'])
            
            # 4. Botão PDF e Link Externo
            col1, col2 = st.columns(2)
            with col1:
                pdf = gerar_pdf(cnpj_limpo, razao_social, logs_gerais)
                st.download_button("📥 Baixar Relatório Técnico", pdf, "dossie_v7.pdf", "application/pdf")
            with col2:
                link_gov = f"https://www.portaltransparencia.gov.br/busca?termo={termo_busca}"
                st.link_button("🔗 Verificar no Site Oficial (Contraprova)", link_gov)

        else:
            st.error("Não foi possível extrair um nome válido para busca.")

# --- AREA DE DEBUG (Onde vemos a verdade) ---
if 'logs_gerais' in locals() and logs_gerais:
    with st.expander("🛠️ Log Técnico Bruto (Para Debug)"):
        st.write("Isso mostra o que a API devolveu ANTES do Python filtrar:")
        for log in logs_gerais:
            st.write(f"--- Base: {log['base']} ---")
            st.write(f"Itens recebidos da API: {log['retorno_api_qtd']}")
            if log['retorno_api_qtd'] > 0 and log['retorno_api_qtd'] < 10:
                st.json(log) # Mostra JSON se forem poucos itens