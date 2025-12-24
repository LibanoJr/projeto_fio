import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("API_KEY_GOVERNO")

def raio_x_ceis():
    print("🕵️‍♂️ Investigando estrutura do CEIS...")
    
    # Vamos usar aquele mesmo CNPJ que você testou e deu resultado
    # (Vou usar um genérico aqui, mas o script vai pegar o que vier)
    cnpj_teste = "00452989000100" 
    
    url = "https://api.portaldatransparencia.gov.br/api-de-dados/ceis"
    headers = {"chave-api-dados": API_KEY}
    params = {"cnpjSancionado": cnpj_teste, "pagina": 1}
    
    try:
        resp = requests.get(url, headers=headers, params=params)
        dados = resp.json()
        
        if len(dados) > 0:
            print(f"✅ Encontrei {len(dados)} sanções!")
            
            print("\n" + "="*50)
            print("ESTRUTURA REAL DOS DADOS (JSON)")
            print("="*50)
            
            # Pega a primeira punição para vermos as chaves
            primeira_punicao = dados[0]
            
            # Imprime formatado para leitura fácil
            print(json.dumps(primeira_punicao, indent=4, ensure_ascii=False))
            
            print("\n" + "="*50)
            print("CHAVES DISPONÍVEIS:")
            print(list(primeira_punicao.keys()))
            
        else:
            print("❌ CNPJ não retornou dados neste teste.")
            
    except Exception as e:
        print(f"Erro: {e}")

if __name__ == "__main__":
    raio_x_ceis()