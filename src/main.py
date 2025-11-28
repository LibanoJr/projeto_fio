import sys
import os
import schedule
import time
import logging
import yaml
from datetime import datetime

# -------------------------------------------------------------------------
# 🚨 O SEGREDO ESTÁ AQUI: Configura as pastas ANTES de importar o resto
# Pega a pasta onde este arquivo está, sobe um nível e adiciona ao Python
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# -------------------------------------------------------------------------

# AGORA SIM podemos importar os arquivos do projeto sem erro
from src.database import DatabaseHandler
from src.scrapers.site_teste import SiteTeste

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
    """Lê as configurações do arquivo YAML"""
    try:
        # Garante que acha o arquivo mesmo rodando de pastas diferentes
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.join(base_dir, "config", "settings.yaml")
        
        with open(config_path, 'r') as stream:
            return yaml.safe_load(stream)
    except FileNotFoundError:
        logger.error("Arquivo config/settings.yaml não encontrado!")
        return {}

def job():
    """Esta é a função que roda todos os dias"""
    logger.info("--- Iniciando rotina de monitoramento ---")
    
    # Inicializa banco
    db = DatabaseHandler()

    # Lista de Robôs
    scrapers = [
        SiteTeste(db)  # Robô de teste ativado
    ]

    for bot in scrapers:
        try:
            bot_name = bot.__class__.__name__
            logger.info(f"Iniciando robô: {bot_name}")
            
            novas_publicacoes = bot.processar()
            
            if novas_publicacoes:
                logger.info(f"Sucesso! {len(novas_publicacoes)} novas publicações encontradas no {bot_name}.")
                # Aqui entra o envio para Webhook
            else:
                logger.info(f"Nenhuma novidade no {bot_name}.")
            
        except Exception as e:
            logger.error(f"Erro ao executar robô {bot_name}: {e}")

    logger.info("--- Rotina finalizada ---")

if __name__ == "__main__":
    # Carrega config
    config = carregar_config()
    horario = config.get("frequencia_cron", "08:00")
    
    logger.info(f"Robô FIO iniciado. Agendado para rodar às {horario}")
    
    # Agenda a execução
    schedule.every().day.at(horario).do(job)
    
    # --- MODO DE TESTE ---
    # Roda agora mesmo (sem esperar o horário) para você ver funcionando
    job() 

    # Mantém o robô acordado
    while True:
        schedule.run_pending()
        time.sleep(60)