import logging
import os
import time
import google.generativeai as genai
from google.api_core import retry

class OCRHandler:
    def __init__(self):
        self.logger = logging.getLogger("OCRHandler")
        
        # Pega a chave do arquivo .env
        # api_key = os.getenv("GEMINI_API_KEY")
        api_key = "AIzaSyDbVrc61Vp_bKOSSKT6JmvD2o2jDM4GHD8"
        
        if not api_key:
            self.logger.warning("⚠️ Chave GEMINI_API_KEY não encontrada! O OCR não funcionará.")
        else:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel('gemini-1.5-flash')

    def extrair_texto(self, caminho_arquivo_ou_bytes, mime_type='application/pdf'):
        """
        Envia um arquivo (PDF ou Imagem) para o Gemini e retorna o texto extraído.
        """
        if not os.getenv("GEMINI_API_KEY"):
            self.logger.error("ERRO: Sem chave de API.")
            return "ERRO: Configure a GEMINI_API_KEY no arquivo .env"

        self.logger.info("Enviando imagem para leitura via IA (Gemini)...")
        
        try:
            if isinstance(caminho_arquivo_ou_bytes, str):
                if not os.path.exists(caminho_arquivo_ou_bytes):
                    return "ERRO: Arquivo de imagem não encontrado."
                
                # Sobe o arquivo para o Google
                arquivo_remoto = genai.upload_file(caminho_arquivo_ou_bytes, mime_type=mime_type)
            else:
                return "Erro: O sistema espera um caminho de arquivo."

            # Pede para a IA ler
            prompt = "Transcreva todo o texto desta imagem fielmente. Se for um jornal, leia o conteúdo."
            
            response = self.model.generate_content([prompt, arquivo_remoto])
            
            return response.text

        except Exception as e:
            self.logger.error(f"Erro na extração com Gemini: {e}")
            return ""