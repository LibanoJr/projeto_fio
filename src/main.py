import sys
import os
import schedule
import time
import logging
import yaml
from datetime import datetime

# Adiciona o diretório raiz ao path para o Python achar os módulos
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import DatabaseHandler
# No futuro, importaremos os robôs reais aqui (ex: from src.scrapers.site_tjsp import SiteTJSP)

# Configuração de Logs (Salva em arquivo e mostra na tela)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/fio.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("Orquestrador")

def carregar_config():
    """Lê as configurações do arquivo YAML"""
    try:
        with open("config/settings.yaml", 'r') as stream:
            return yaml.safe_load(stream)
    except FileNotFoundError:
        logger.error("Arquivo config/settings.yaml não encontrado!")
        return {}

def job():
    """Esta é a função que roda todos os dias"""
    logger.info("--- Iniciando rotina de monitoramento ---")
    config = carregar_config()
    db = DatabaseHandler()

    # Lista de Robôs (Por enquanto vazia)
    scrapers = [] 

    if not scrapers:
        logger.warning("Nenhum robô configurado na lista 'scrapers'. Nada a fazer.")
    
    for bot in scrapers:
        try:
            bot_name = bot.__class__.__name__
            logger.info(f"Iniciando robô: {bot_name}")
            
            novas_publicacoes = bot.processar()
            
            if novas_publicacoes:
                logger.info(f"Sucesso! {len(novas_publicacoes)} novas publicações encontradas no {bot_name}.")
                # TODO: Aqui entrará a função de enviar para o Webhook
            
        except Exception as e:
            logger.error(f"Erro ao executar robô: {e}")

    logger.info("--- Rotina finalizada ---")

if __name__ == "__main__":
    # Carrega config para pegar o horário
    config = carregar_config()
    horario = config.get("frequencia_cron", "08:00")
    
    logger.info(f"Robô FIO iniciado. Agendado para rodar às {horario}")
    
    # Agenda a execução diária
    schedule.every().day.at(horario).do(job)
    
    # --- MODO DE TESTE ---
    # Roda uma vez agora mesmo para você ver funcionando
    job() 

    # Loop infinito (mantém o programa acordado esperando a hora certa)
    while True:
        schedule.run_pending()
        time.sleep(60)