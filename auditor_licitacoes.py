import requests
import google.generativeai as genai
import time

# --- SUAS CHAVES ---
API_KEY_GOVERNO = "d03ede6b6072b78e6df678b6800d4ba1"
API_KEY_GEMINI  = "AIzaSyDDeKfsFg8zXnwwl3sSCoO2KdrMIZoOTTY"

# Configuração da IA
genai.configure(api_key=API_KEY_GEMINI)
model = genai.GenerativeModel('gemini-flash-latest')

def buscar_contratos_mec():
    # MUDANÇA: Endpoint de CONTRATOS (Mais estável que licitações)
    url = "https://api.portaldatransparencia.gov.br/api-de-dados/contratos"
    headers = {"chave-api-dados": API_KEY_GOVERNO}
    
    # ESTRATÉGIA:
    # 1. codigoOrgao = 26000 (Ministério da Educação - Sempre tem contratos bons)
    # 2. Período: Janeiro de 2024 (Início de ano letivo, muitas compras)
    params = {
        "dataInicioVigencia": "01/01/2024",
        "dataFimVigencia": "15/01/2024",
        "codigoOrgao": "26000", 
        "pagina": 1
    }
    
    print("⏳ Conectando ao MEC (Buscando Contratos)...")
    try:
        response = requests.get(url, headers=headers, params=params, timeout=20)
        
        if response.status_code == 200:
            dados = response.json()
            # Filtra apenas contratos com descrição (Objeto)
            lista_valida = [d for d in dados if d.get('objeto')]
            return lista_valida
        else:
            print(f"❌ Erro Governo: {response.status_code}")
            return []
    except Exception as e:
        print(f"❌ Erro de Conexão: {e}")
        return []

def analisar_juridico_contrato(objeto, valor):
    # Prompt focado em Análise Contratual
    prompt = f"""
    Atue como Auditor de Contratos Públicos. Analise:
    
    OBJETO DO CONTRATO: "{objeto}"
    VALOR: R$ {valor}
    
    Sua missão:
    1. Traduza o "Juridiquês" para português simples.
    2. O objeto está claro ou vago? (Dê uma nota de 0 a 10 de clareza).
    3. Há algum termo estranho ou atípico?
    
    Responda no formato:
    RESUMO: ...
    CLAREZA: .../10
    PARECER: ...
    """
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except:
        return "Erro na IA"

# --- EXECUÇÃO ---
print("\n--- 🎓 AUDITORIA DE CONTRATOS (MEC) ---")

contratos = buscar_contratos_mec()

if contratos:
    print(f"✅ Encontrei {len(contratos)} contratos assinados. Auditando os 3 maiores...\n")
    
    # DICA: Vamos ordenar pelos valores mais altos para pegar os mais polêmicos?
    # (O código abaixo tenta ordenar, se der erro ele pega os primeiros mesmo)
    try:
        contratos.sort(key=lambda x: x.get('valorInicial', 0), reverse=True)
    except:
        pass

    for i, item in enumerate(contratos[:3]):
        
        # Extração segura
        numero = item.get('numero', 'S/N')
        objeto = item.get('objeto', 'Sem descrição')
        valor = item.get('valorInicial', 0)
        unidade = item.get('unidadeGestora', {}).get('nome', 'MEC')
        
        print(f"📄 CONTRATO: {numero}")
        print(f"🏫 UNIDADE: {unidade}")
        print(f"💰 VALOR: R$ {valor:,.2f}")
        print(f"📝 DESCRIÇÃO: {objeto[:120]}...") 
        
        print("\n🧠 ANÁLISE JURÍDICA:")
        print(analisar_juridico_contrato(objeto, valor))
        
        print("-" * 50)
        time.sleep(5) 
else:
    print("❌ Nenhum contrato encontrado com esses filtros.")