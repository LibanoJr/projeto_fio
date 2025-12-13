import logging
import time
import yaml
import random
import os  # <--- [NOVO] Necessário para achar a pasta do computador
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options

# Importações (mantemos todas para evitar erro de import, mas só usaremos Jusbrasil)
try:
    from scrapers.site_dou import SiteDOU
    from scrapers.site_tjsp import SiteTJSP
    from scrapers.site_jusbrasil import SiteJusbrasil
    from database import DatabaseManager
    from notifier import enviar_webhook
    from minerador import MineradorDados
    from ocr_handler import AIHandler
except ImportError:
    from .scrapers.site_dou import SiteDOU
    from .scrapers.site_tjsp import SiteTJSP
    from .scrapers.site_jusbrasil import SiteJusbrasil
    from .database import DatabaseManager
    from .notifier import enviar_webhook
    from .minerador import MineradorDados
    from .ocr_handler import AIHandler

# Configuração de Logs
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Orquestrador')

def carregar_config():
    try:
        with open("config/settings.yaml", "r", encoding='utf-8') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        return None

def configurar_driver():
    options = webdriver.ChromeOptions()
    
    # --- [NOVO] CONFIGURAÇÃO PARA SALVAR O LOGIN ---
    # Isso cria uma pasta na mesma raiz do seu script para salvar os cookies/sessão
    dir_path = os.getcwd()
    profile_path = os.path.join(dir_path, "chrome_perfil_jusbrasil")
    options.add_argument(f"user-data-dir={profile_path}")
    # -----------------------------------------------

    # --- BLINDAGEM BÁSICA ---
    options.add_argument('--ignore-certificate-errors')
    options.add_argument('--ignore-ssl-errors')
    options.add_argument("--disable-popup-blocking")
    options.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
    
    # Performance e Anti-Detecção
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)

    service = ChromeService(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)

def main():
    logger.info("--- A INICIAR ROBÔ FIO (MODO APENAS JUSBRASIL) ---")
    
    # 1. Configurações
    config = carregar_config()
    webhook_url = config.get('webhook_url') if config else None
    
    # --- FORÇANDO A BUSCA PARA O TESTE ---
    termos_busca = ["Abboud Moussa Abboud"] 
    logger.info(f"🎯 Termo fixado para teste: {termos_busca}")

    # 2. Inicializar Banco
    db = DatabaseManager()
    minerador = MineradorDados()
    
    logger.info("Abrindo navegador...")
    driver = configurar_driver()
    
    scrapers_ativos = []
    
    # --- ❌ DOU (DESATIVADO) ---
    # try: scrapers_ativos.append(SiteDOU(logger))
    # except: pass

    # --- ✅ JUSBRASIL (ATIVADO) ---
    try: 
        scrapers_ativos.append(SiteJusbrasil(logger))
    except Exception as e:
        logger.error(f"Erro ao carregar Jusbrasil: {e}")

    # --- ❌ TJ-SP (DESATIVADO) ---
    # try: scrapers_ativos.append(SiteTJSP(logger))
    # except: pass

    try:
        for scraper in scrapers_ativos:
            nome_robo = scraper.__class__.__name__
            logger.info(f"🚀 A RODAR SCRAPER: {nome_robo}")

            for termo in termos_busca:
                logger.info(f"🔎 {nome_robo} a buscar: '{termo}'")
                
                try:
                    # Busca
                    resultados = scraper.buscar_links(driver, termo)
                except Exception as e:
                    logger.error(f"Erro na busca do {nome_robo}: {e}")
                    continue

                if not resultados:
                    logger.info(f"Nenhum resultado encontrado no {nome_robo} para {termo}.")
                    continue
                
                for item in resultados:
                    try:
                        # No Jusbrasil, o resumo_tela já contém as estatísticas (Total, Ativo, Passivo)
                        texto_conteudo = item.get('resumo_tela', '')
                        
                        print("\n" + "="*40)
                        print(f"📄 RESULTADO JUSBRASIL PARA: {termo}")
                        print(texto_conteudo)
                        print("="*40 + "\n")

                        dados = {
                            'termo': termo,
                            'titulo': item['titulo'],
                            'link': item['link'],
                            'conteudo': texto_conteudo
                        }
                        
                        # Salva
                        if db.salvar_publicacao(dados):
                            # Se tiver estatísticas extras de empresas
                            if 'stats' in item and 'nomes_relacionados' in item['stats']:
                                empresas = item['stats']['nomes_relacionados']
                                if empresas:
                                    logger.info(f"🏢 Empresas/Nomes Relacionados: {empresas}")
                            
                            # Envia Webhook se configurado
                            if webhook_url:
                                enviar_webhook(dados, webhook_url)
                            
                        time.sleep(3)

                    except Exception as e_item:
                        logger.error(f"Erro ao processar item: {e_item}")

            print("-" * 50)

    except KeyboardInterrupt:
        logger.info("Operação interrompida.")
    finally:
        logger.info("Fechando navegador...")
        try: driver.quit()
        except: pass

if __name__ == "__main__":
    main()