import requests
import google.generativeai as genai
import time
from datetime import datetime
import os
from dotenv import load_dotenv

# Carrega as chaves do arquivo .env (o cofre)
load_dotenv()

# Pega as chaves de forma segura
API_KEY_GOVERNO = os.getenv("API_KEY_GOVERNO")
API_KEY_GEMINI  = os.getenv("API_KEY_GEMINI")

# Verifica se as chaves foram carregadas
if not API_KEY_GOVERNO or not API_KEY_GEMINI:
    print("❌ ERRO: Chaves de API não encontradas! Verifique o arquivo .env")
    exit()

# Configuração da IA
genai.configure(api_key=API_KEY_GEMINI)
model = genai.GenerativeModel('gemini-flash-latest')

# ... (O resto do código continua igualzinho para baixo) ...
def buscar_contratos_mec():
    url = "https://api.portaldatransparencia.gov.br/api-de-dados/contratos"
    headers = {"chave-api-dados": API_KEY_GOVERNO}
    params = {
        "dataInicioVigencia": "01/01/2024",
        "dataFimVigencia": "15/01/2024",
        "codigoOrgao": "26000", 
        "pagina": 1
    }
    print("⏳ Consultando API do Governo...")
    try:
        response = requests.get(url, headers=headers, params=params, timeout=20)
        if response.status_code == 200:
            dados = response.json()
            return [d for d in dados if d.get('objeto')]
        return []
    except:
        return []

def analisar_juridico(contrato):
    objeto = contrato.get('objeto', '')
    valor = contrato.get('valorInicial', 0)
    numero = contrato.get('numero', 'S/N')
    
    prompt = f"""
    Analise este contrato público (MEC).
    CONTRATO: {numero}
    VALOR: R$ {valor}
    OBJETO: "{objeto}"
    
    Sua tarefa:
    1. Resuma o objeto em 1 frase simples.
    2. Dê uma nota de CLAREZA (0-10).
    3. Identifique RISCOS (Ex: valor zerado, objeto vago, erros de português).
    
    Saída em Markdown:
    **Resumo:** ...
    **Clareza:** .../10
    **Análise de Risco:** ...
    """
    try:
        res = model.generate_content(prompt)
        return res.text.strip()
    except:
        return "Erro na IA"

def salvar_relatorio(texto):
    nome_arquivo = f"Relatorio_Auditoria_{datetime.now().strftime('%Y%m%d_%H%M')}.md"
    with open(nome_arquivo, "w", encoding="utf-8") as f:
        f.write(texto)
    print(f"\n📄 Relatório salvo com sucesso: {nome_arquivo}")

# --- EXECUÇÃO ---
print("\n--- 🎓 GERAÇÃO DE DOSSIÊ DE AUDITORIA ---")
contratos = buscar_contratos_mec()

if contratos:
    # Ordena por valor (maiores primeiro)
    contratos.sort(key=lambda x: x.get('valorInicial', 0), reverse=True)
    
    relatorio_final = f"# DOSSIÊ DE AUDITORIA AUTOMATIZADA\n"
    relatorio_final += f"**Data:** {datetime.now().strftime('%d/%m/%Y %H:%M')}\n"
    relatorio_final += f"**Alvo:** Ministério da Educação (MEC)\n"
    relatorio_final += "-" * 40 + "\n\n"
    
    print(f"✅ Encontrei {len(contratos)} contratos. Gerando dossiê dos 3 principais...")
    
    for item in contratos[:3]:
        analise = analisar_juridico(item)
        
        # Monta o texto para o arquivo
        bloco = f"## CONTRATO Nº {item.get('numero')}\n"
        bloco += f"**Valor:** R$ {item.get('valorInicial', 0):,.2f}\n"
        bloco += f"**Objeto Original:** *{item.get('objeto')}*\n\n"
        bloco += f"### 🧠 Parecer da IA:\n{analise}\n"
        bloco += "\n---\n\n"
        
        relatorio_final += bloco
        print(f"-> Contrato {item.get('numero')} analisado.")
        time.sleep(4)
        
    salvar_relatorio(relatorio_final)
else:
    print("❌ Falha ao buscar dados.")