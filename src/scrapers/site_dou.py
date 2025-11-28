import time
import os
import platform
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from src.scrapers.base_scraper import BaseScraper
from src.ocr_handler import OCRHandler

class SiteDOU(BaseScraper):
    def __init__(self, db_handler):
        super().__init__(db_handler)
        self.ocr = OCRHandler()
        self.driver = None

    def iniciar_driver(self):
        self.logger.info("Iniciando Google Chrome (Modo Nativo Selenium)...")
        
        options = webdriver.ChromeOptions()
        # options.add_argument("--headless") 
        options.add_argument("--window-size=1920,1080")
        
        # --- A SOLUÇÃO: SEM WEBDRIVER MANAGER ---
        # Apenas chamamos o Chrome direto. O Selenium 4.6+ acha ele sozinho.
        try:
            self.driver = webdriver.Chrome(options=options)
        except Exception as e:
            self.logger.error("Erro ao abrir Chrome nativo. Verifique se o Chrome está instalado.")
            raise e

    def login(self):
        pass 

    def buscar_publicacoes(self):
        resultados = []
        #termo_busca = "OAB" 
        termo_busca = "Portaria"
        
        try:
            self.iniciar_driver()
            
            url = f"https://www.in.gov.br/consulta/busca?q={termo_busca}"
            self.logger.info(f"Acessando: {url}")
            self.driver.get(url)

            # Espera até 20 segundos
            wait = WebDriverWait(self.driver, 20)
            wait.until(EC.presence_of_element_located((By.ID, "ab-list")))
            
            self.logger.info("Site carregado.")
            time.sleep(3) 

            screenshot_path = "temp_print_dou.png"
            self.driver.save_screenshot(screenshot_path)
            self.logger.info("Screenshot salva. Enviando para IA...")

            # IA
            texto_extraido = self.ocr.extrair_texto(screenshot_path, mime_type='image/png')
            
            if os.path.exists(screenshot_path):
                os.remove(screenshot_path)

            self.logger.info(f"--- LEITURA DA IA ---\n{texto_extraido[:300]}...\n----------------------")

            if termo_busca in texto_extraido:
                resultados.append({
                    "data_publicacao": "27/11/2025", 
                    "termo_encontrado": termo_busca,
                    "numero_processo": "Busca Geral DOU",
                    "texto_publicacao": texto_extraido,
                    "link_oficial": url,
                    "identificador_unico": str(hash(texto_extraido))
                })

        except Exception as e:
            self.logger.error(f"Erro: {e}")
        
        finally:
            if self.driver:
                self.driver.quit()
        
        return resultados