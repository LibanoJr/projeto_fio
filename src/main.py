import logging
import time
import json  # <--- 1. Adicionado para lidar com arquivos
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager

try:
    from scrapers.site_dou import SiteDOU
except ImportError:
    from .scrapers.site_dou import SiteDOU

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Orquestrador')

def configurar_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    service = ChromeService(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)

def main():
    logger.info("--- INICIANDO ROBÔ ---")
    termos_busca = ["OAB", "CPF", "Licitação"]
    driver = configurar_driver()
    
    try:
        scraper = SiteDOU(logger)
        
        for termo in termos_busca:
            logger.info(f"🔎 Processando: {termo}")
            
            if hasattr(scraper, 'buscar_e_extrair'):
                resultados = scraper.buscar_e_extrair(driver, termo)
            else:
                scraper.realizar_busca(driver, termo)
                resultados = scraper.extrair_resultados(driver)

            if resultados:
                logger.info(f"✅ SUCESSO! {len(resultados)} resultados.")
                
                # --- 2. SALVAR EM ARQUIVO PARA VOCÊ VER ---
                nome_arquivo = f"dados_{termo}.json"
                with open(nome_arquivo, 'w', encoding='utf-8') as f:
                    json.dump(resultados, f, ensure_ascii=False, indent=4)
                
                logger.info(f"💾 Arquivo salvo: {nome_arquivo} (Verifique na pasta do projeto)")
                # ------------------------------------------

            else:
                logger.warning(f"❌ 0 resultados para '{termo}'.")
            
            print("-" * 50)
            
    except Exception as e:
        logger.error(f"Erro fatal: {e}")
    finally:
        logger.info("Finalizando...")
        driver.quit()

if __name__ == "__main__":
    main()