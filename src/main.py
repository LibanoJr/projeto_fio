import logging
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager

try:
    from scrapers.site_dou import SiteDOU
    from database import DatabaseManager
except ImportError:
    from .scrapers.site_dou import SiteDOU
    from .database import DatabaseManager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
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
    logger.info("--- INICIANDO ROBÔ COM TERMOS CORRIGIDOS ---")
    
    # --- AJUSTE NA ESTRATÉGIA DE BUSCA ---
    # O site do governo não entende bem parênteses () ou OR.
    # Vamos usar FRASES EXATAS (entre aspas) que filtram muito bem.
    termos_busca = [
        # Busca exata pela seccional de SP (evita OAB de outros estados)
        '"OAB/SP"',
        
        # Em vez de apenas "Licitação" (que traz tudo), buscamos o objeto da compra
        '"Aquisição de Computadores"',
        
        # Termo composto específico
        '"Irregularidade no CPF"'
    ]
    
    # Limite de segurança (para não baixar o site todo)
    LIMITE_POR_TERMO = 5
    
    db = DatabaseManager()
    driver = configurar_driver()
    scraper = SiteDOU(logger)
    
    try:
        for termo in termos_busca:
            logger.info(f"🔎 Processando busca: {termo}")
            
            # 1. Busca Links
            links_encontrados = scraper.buscar_links(driver, termo)
            
            # Aplica o limite
            links_filtrados = links_encontrados[:LIMITE_POR_TERMO]
            
            logger.info(f"🔗 Encontrados {len(links_encontrados)} total. Processando os {len(links_filtrados)} mais recentes.")
            
            # 2. Entra e Salva
            for i, item in enumerate(links_filtrados):
                url = item['link']
                
                # Extrai texto completo
                texto_completo = scraper.extrair_texto_materia(driver, url)
                
                # Só salva se tiver conteúdo real
                if len(texto_completo) < 50:
                    continue

                dados_finais = {
                    'termo': termo,
                    'titulo': item['titulo'],
                    'link': url,
                    'conteudo': texto_completo
                }
                
                # Salva no banco (retorna True se for novidade)
                if db.salvar_publicacao(dados_finais):
                    # Só espera se realmente salvou algo (para agilizar)
                    time.sleep(1)

            print("-" * 50)
            
    except Exception as e:
        logger.error(f"Erro fatal: {e}")
    finally:
        logger.info("Finalizando...")
        driver.quit()

if __name__ == "__main__":
    main()