import google.generativeai as genai

# --- SUA CHAVE ---
API_KEY_GEMINI  = "AIzaSyDDeKfsFg8zXnwwl3sSCoO2KdrMIZoOTTY"
genai.configure(api_key=API_KEY_GEMINI)

print("🔍 Perguntando ao Google quais modelos você pode usar...\n")

try:
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(f"✅ Disponível: {m.name}")
except Exception as e:
    print(f"❌ Erro ao listar: {e}")