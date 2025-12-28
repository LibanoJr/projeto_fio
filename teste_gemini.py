import os
from dotenv import load_dotenv
import google.generativeai as genai

# 1. Carrega as senhas
load_dotenv()
chave = os.getenv("GEMINI_API_KEY")

print(f"1. Verificando chave...")
if not chave:
    print("❌ ERRO: Chave não encontrada no arquivo .env!")
    exit()
print(f"✅ Chave encontrada: {chave[:5]}... (oculto)")

# 2. Configura a IA
print("2. Tentando conectar no Google...")
try:
    genai.configure(api_key=chave)
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    # 3. Faz uma pergunta teste
    print("3. Enviando pergunta teste...")
    response = model.generate_content("Responda apenas com a palavra 'FUNCIONOU' se você estiver me ouvindo.")
    
    print("-" * 30)
    print(f"RESPOSTA DA IA: {response.text}")
    print("-" * 30)
    print("✅ SUCESSO TOTAL! Sua IA está perfeita.")

except Exception as e:
    print("\n❌ DEU ERRO! Aqui está o motivo real:")
    print(e)