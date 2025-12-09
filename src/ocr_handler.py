import os
import google.generativeai as genai
import logging
from dotenv import load_dotenv

# Carrega a senha do .env
load_dotenv()

logger = logging.getLogger('OCR_Handler')

class AIHandler:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            logger.warning("⚠️ API Key do Gemini não encontrada no .env! OCR desativado.")
            self.model = None
        else:
            genai.configure(api_key=api_key)
            # Usamos o modelo Flash que é rápido e barato (ou gratuito no tier free)
            self.model = genai.GenerativeModel('gemini-1.5-flash')

    def resumir_e_extrair(self, texto_bruto):
        """
        Usa IA para limpar textos sujos ou resumir conteúdos muito longos.
        Útil para quando o scraper pega lixo do HTML.
        """
        if not self.model: return None
        
        prompt = f"""
        Você é um assistente jurídico. Analise o texto abaixo extraído do Diário Oficial.
        1. Identifique se é uma licitação, portaria ou aviso.
        2. Extraia o valor monetário (se houver).
        3. Resuma o objeto em 1 frase.
        
        Texto: {texto_bruto[:4000]}
        
        Responda em JSON: {{ "tipo": "...", "valor": "...", "resumo": "..." }}
        """
        
        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            logger.error(f"Erro na IA: {e}")
            return None

    def ler_imagem_url(self, url_imagem):
        """
        Aqui entra a lógica pesada: Se o link for um PDF/Imagem, mandamos para o Gemini ler.
        (Esta função requer baixar o arquivo primeiro, o que é um passo extra).
        Por enquanto, vamos focar na limpeza do texto.
        """
        pass