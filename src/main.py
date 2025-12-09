import logging
import time
import yaml # Requer: pip install pyyaml
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager

# Importações dos módulos do projeto
try:
    from scrapers.site_dou import SiteDOU
    from database import DatabaseManager
    from notifier import enviar_webhook
    from minerador import MineradorDados
    from ocr_handler import AIHandler # <--- NOVO: Importa a IA
except ImportError:
    from .scrapers.site_dou import SiteDOU
    from .database import DatabaseManager
    from .notifier import enviar_webhook
    from .minerador import MineradorDados
    from .ocr_handler import AIHandler

# Configuração de Logs
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Orquestrador')

def carregar_config():
    """Lê as configurações do arquivo YAML."""
    try:
        with open("config/settings.yaml", "r", encoding='utf-8') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        logger.error("Arquivo config/settings.yaml não encontrado! Usando padrões.")
        return None

def configurar_driver():
    options = webdriver.ChromeOptions()
    # Identidade de usuário real
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    # Estabilidade
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    
    # Anti-Detecção
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    service = ChromeService(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)

def main():
    logger.info("--- INICIANDO ROBÔ FIO (INTEGRADO COM IA) ---")
    
    # 1. Carrega Configurações
    config = carregar_config()
    
    # Define padrões caso o config falhe
    if config:
        termos_busca = config.get('termos_busca', [])
        webhook_url = config.get('webhook_url')
        limite = config.get('limite_por_termo', 5)
    else:
        # Fallback se não tiver arquivo config
        termos_busca = ['"OAB/SP"', '"Licitação"'] 
        webhook_url = None
        limite = 5
    
    # 2. Inicializa os Componentes
    db = DatabaseManager()
    driver = configurar_driver()
    scraper = SiteDOU(logger)
    minerador = MineradorDados()
    ai_bot = AIHandler() # <--- Inicializa o robô de IA
    
    try:
        for termo in termos_busca:
            logger.info(f"🔎 Buscando termo: {termo}")
            
            # Busca links (Navegação)
            links = scraper.buscar_links(driver, termo)
            
            # Aplica limite para não sobrecarregar
            links_filtrados = links[:limite]
            
            for item in links_filtrados:
                url = item['link']
                
                # Extrai texto bruto da página
                texto = scraper.extrair_texto_materia(driver, url)
                
                # --- LÓGICA DE FALLBACK COM IA ---
                # Se o texto for muito curto (< 150 chars), pode ser erro de carga ou imagem
                if len(texto) < 150:
                    logger.warning(f"⚠️ Texto curto ou sujo em {url}. Acionando IA Gemini...")
                    
                    # Tenta recuperar/resumir com IA
                    texto_ia = ai_bot.resumir_e_extrair(texto)
                    
                    if texto_ia:
                        texto = texto_ia # Substitui o texto ruim pelo da IA
                        logger.info("🤖 IA recuperou o conteúdo com sucesso!")
                    else:
                        logger.warning("❌ IA não conseguiu processar. Ignorando matéría.")
                        continue # Pula se nem a IA resolveu
                # ----------------------------------

                # Prepara dados
                dados = {
                    'termo': termo,
                    'titulo': item['titulo'],
                    'link': url,
                    'conteudo': texto
                }
                
                # Tenta salvar no banco (Retorna True se for NOVO)
                if db.salvar_publicacao(dados):
                    
                    # Se salvou (é novo), executa o pós-processamento:
                    
                    # A. Mineração (Regex para CNPJ e Valor)
                    cnpjs, valores = minerador.minerar_texto(texto)
                    
                    # B. Atualiza o banco com o que minerou
                    if cnpjs or valores:
                        db.atualizar_mineracao(url, cnpjs, valores) # Precisa ajustar minerador para aceitar URL ou pegar ID antes
                        dados['cnpjs'] = cnpjs
                        dados['valores'] = valores
                    
                    # C. Envia para o Webhook (Sistema Externo)
                    if webhook_url:
                        enviar_webhook(dados, webhook_url)
                    
                    time.sleep(1) # Pausa para não bloquear IP

    except Exception as e:
        logger.error(f"Erro fatal no orquestrador: {e}")
    finally:
        logger.info("Finalizando navegador...")
        driver.quit()

if __name__ == "__main__":
    main()