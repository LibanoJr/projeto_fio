import requests
import pandas as pd
import google.generativeai as genai
import time

# --- SUAS CHAVES ---
API_KEY_GOVERNO = "d03ede6b6072b78e6df678b6800d4ba1"
API_KEY_GEMINI  = "AIzaSyDDeKfsFg8zXnwwl3sSCoO2KdrMIZoOTTY"

# Configuração da IA
genai.configure(api_key=API_KEY_GEMINI)
model = genai.GenerativeModel('gemini-flash-latest') 

def buscar_gastos():
    url = "https://api.portaldatransparencia.gov.br/api-de-dados/cartoes"
    headers = {"chave-api-dados": API_KEY_GOVERNO}
    params = {"mesExtratoInicio": "01/2024", "mesExtratoFim": "01/2024", "pagina": 1}
    
    print("⏳ Conectando ao Governo...")
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        return response.json() if response.status_code == 200 else []
    except:
        return []

def perguntar_ia(loja, valor):
    # Prompt mais rigoroso para padronizar
    prompt = f"""
    Analise o gasto de R$ {valor} na empresa '{loja}'.
    Classifique EXATAMENTE em uma destas categorias:
    [MATERIAL DE ESCRITÓRIO, ALIMENTAÇÃO, TECNOLOGIA, MANUTENÇÃO, HOTELARIA, TRANSPORTE, OUTROS].
    
    Responda APENAS o nome da categoria, sem explicações.
    """
    try:
        response = model.generate_content(prompt)
        return response.text.strip().upper() # Força letras maiúsculas
    except:
        return "ERRO IA"

# --- RELATÓRIO FINAL ---
print("\n--- 🕵️‍♂️ RELATÓRIO DE GASTOS PÚBLICOS ---")

dados = buscar_gastos()

if dados:
    print(f"✅ Analisando amostra de 5 despesas...\n")
    
    for i, item in enumerate(dados[:5]):
        loja = item['estabelecimento']['nome']
        valor = item['valorTransacao']
        data = item['dataTransacao']
        
        # IA trabalha aqui
        categoria = perguntar_ia(loja, valor)
        
        # Exibição Bonita
        print(f"📅 Data: {data}")
        print(f"🏢 Empresa:   {loja}")
        print(f"💰 Valor:     R$ {valor}")  # <--- VOLTOU!
        print(f"🏷️  CATEGORIA: {categoria}")
        print("-" * 40)
        
        time.sleep(4) # Pausa para não bloquear
else:
    print("Sem dados.")