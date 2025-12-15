import logging
import time
import os
import urllib3
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options

# --- SILENCIADOR DE AVISOS CHATOS ---
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
os.environ['WDM_LOG'] = '0' # Silencia logs do gerenciador de driver

try:
    from scrapers.site_jusbrasil import SiteJusbrasil
    from database import DatabaseManager
except ImportError:
    from .scrapers.site_jusbrasil import SiteJusbrasil
    from .database import DatabaseManager

logging.basicConfig(level=logging.INFO, format='%(message)s') # Formato limpo
logger = logging.getLogger('Orquestrador')

def configurar_driver():
    options = webdriver.ChromeOptions()
    
    # Caminho do Perfil (Para manter login)
    dir_path = os.getcwd()
    profile_path = os.path.join(dir_path, "chrome_perfil_jusbrasil")
    options.add_argument(f"user-data-dir={profile_path}")
    
    # Camuflagem e Configurações
    options.add_argument("--disable-blink-features=AutomationControlled") 
    options.add_experimental_option("excludeSwitches", ["enable-automation"]) 
    options.add_experimental_option('useAutomationExtension', False) 
    options.add_argument("--start-maximized")
    
    # SSL Fix
    os.environ['WDM_SSL_VERIFY'] = '0'

    try:
        service = ChromeService(ChromeDriverManager().install())
    except:
        service = ChromeService()

    driver = webdriver.Chrome(service=service, options=options)
    
    # Script Anti-Detecção
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    })
    
    return driver

def main():
    logger.info("\n" + "="*40)
    logger.info("   🤖 ROBÔ INICIADO - MODO SILENCIOSO")
    logger.info("="*40 + "\n")
    
    # --- LISTA DE ALVOS ---
    alvos = [
        {
            "nome": "Abboud Moussa Abboud",
            "url": "https://www.jusbrasil.com.br/nome/abboud-moussa-abboud/cpf-PQYnHBypz4G"
        },
        # Adicione o link EXATO do perfil do Libano aqui quando tiver
        # { "nome": "Libano Abboud", "url": "LINK_DO_PERFIL_DELE" } 
    ]

    db = DatabaseManager()
    driver = configurar_driver()
    scraper = SiteJusbrasil(logger)

    try:
        for alvo in alvos:
            logger.info(f"🎯 ALVO: {alvo['nome']}")
            resultados = scraper.analisar_perfil_com_abas(driver, alvo['url'])

            if resultados:
                for item in resultados:
                    db.salvar_publicacao({
                        'termo': alvo['nome'],
                        'titulo': item['titulo'],
                        'link': item['link'],
                        'conteudo': item['resumo']
                    })
            else:
                logger.warning("   ⚠️ Nada capturado.")

    except KeyboardInterrupt:
        logger.info("\n🛑 Parando...")
    finally:
        logger.info("👋 Fim da execução.")
        # driver.quit() # Pode descomentar se quiser fechar sozinho

if __name__ == "__main__":
    main()