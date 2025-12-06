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
    # User-Agent real
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    # Performance e Anti-Crash
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    
    # Anti-Robô
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    service = ChromeService(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)

def main():
    logger.info("--- INICIANDO ROBÔ COM BUSCA REFINADA ---")
    
    # --- AQUI ESTÁ A MÁGICA: BUSCAS ESPECÍFICAS ---
    # Use aspas duplas dentro da string para termos exatos
    # Use AND para combinar condições
    termos_busca = [
        # Exemplo 1: Quero saber de OAB, mas apenas da Seccional de SP
        '"OAB/SP" AND "Edital"',
        
        # Exemplo 2: Não quero qualquer CPF, quero avisos de irregularidade ou cancelamento
        '"CPF" AND "Cancelamento"',
        
        # Exemplo 3: Licitação apenas para compra de Computadores
        'Licitação AND "Aquisição de Computadores"'
    ]
    
    # Inicializa
    db = DatabaseManager()
    driver = configurar_driver()
    scraper = SiteDOU(logger)
    
    try:
        for termo in termos_busca:
            logger.info(f"🔎 Processando busca refinada: {termo}")
            
            # 1. Busca Links
            links_encontrados = scraper.buscar_links(driver, termo)
            logger.info(f"🔗 Encontrados {len(links_encontrados)} documentos relevantes.")
            
            # 2. Entra e Salva
            for i, item in enumerate(links_encontrados):
                # Pegando os 5 primeiros para teste rápido
                if i >= 5: break 

                url = item['link']
                
                # Extrai texto completo
                texto_completo = scraper.extrair_texto_materia(driver, url)
                
                # Pacote de dados
                dados_finais = {
                    'termo': termo,
                    'titulo': item['titulo'],
                    'link': url,
                    'conteudo': texto_completo
                }
                
                # Salva
                db.salvar_publicacao(dados_finais)
                time.sleep(1)

            print("-" * 50)
            
    except Exception as e:
        logger.error(f"Erro fatal: {e}")
    finally:
        logger.info("Finalizando...")
        driver.quit()

if __name__ == "__main__":
    main()