import sys
import os
import schedule
import time
import logging
import yaml
from datetime import datetime

# -------------------------------------------------------------------------
# 🚨 BLOCO OBRIGATÓRIO (Tem que vir ANTES de importar qualquer coisa do src)
# Isso ensina o Python a olhar para a pasta raiz do projeto
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# -------------------------------------------------------------------------

# AGORA SIM podemos importar os módulos do projeto
from src.database import DatabaseHandler
from src.scrapers.site_dou import SiteDOU # <--- Importando o robô novo do DOU

# Configuração de Logs
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
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.join(base_dir, "config", "settings.yaml")
        with open(config_path, 'r') as stream:
            return yaml.safe_load(stream)
    except FileNotFoundError:
        return {}

def job():
    logger.info("--- Iniciando rotina de monitoramento ---")
    
    db = DatabaseHandler()

    # Lista de Robôs Ativos
    scrapers = [
        SiteDOU(db)  # Robô do Diário Oficial da União
    ]

    for bot in scrapers:
        try:
            bot_name = bot.__class__.__name__
            logger.info(f"Iniciando robô: {bot_name}")
            
            novas_publicacoes = bot.processar()
            
            if novas_publicacoes:
                logger.info(f"Sucesso! {len(novas_publicacoes)} novas publicações encontradas no {bot_name}.")
            else:
                logger.info(f"Nenhuma novidade no {bot_name}.")
            
        except Exception as e:
            logger.error(f"Erro ao executar robô {bot_name}: {e}")

    logger.info("--- Rotina finalizada ---")

if __name__ == "__main__":
    job() # Roda agora para testar
    
    # Mantém rodando
    while True:
        schedule.run_pending()
        time.sleep(60)