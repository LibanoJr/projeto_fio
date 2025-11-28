import time
# IMPORT ABSOLUTO (O jeito mais seguro)
from src.scrapers.base_scraper import BaseScraper

class SiteTeste(BaseScraper):
    def login(self):
        self.logger.info("Fingindo que estou fazendo login no site...")
        time.sleep(1)
        self.logger.info("Login realizado com sucesso (mentirinha)!")

    def buscar_publicacoes(self):
        self.logger.info("Varrendo a página em busca de processos...")
        
        resultados = [
            {
                "data_publicacao": "27/11/2025",
                "termo_encontrado": "SEU NOME",
                "numero_processo": "0000123-45.2025.8.26.0000",
                "texto_publicacao": "Publicação de teste encontrada pelo robô FIO.",
                "link_oficial": "http://tribunal.jus.br/processo/123",
                "identificador_unico": "hash_teste_001"
            },
            {
                "data_publicacao": "27/11/2025",
                "termo_encontrado": "EMPRESA X",
                "numero_processo": "9999999-99.2025.8.26.0000",
                "texto_publicacao": "Outra publicação de teste.",
                "link_oficial": "http://tribunal.jus.br/processo/999",
                "identificador_unico": "hash_teste_002"
            }
        ]
        return resultados