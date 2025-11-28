import logging
import requests
from abc import ABC, abstractmethod
from datetime import datetime

class BaseScraper(ABC):
    def __init__(self, db_handler):
        """
        Inicializa o scraper com conexão ao banco e sessão HTTP padrão.
        """
        self.db = db_handler
        self.session = requests.Session()
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Define um User-Agent padrão para evitar bloqueios simples
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        })

    @abstractmethod
    def login(self):
        """
        Método obrigatório: Lógica de autenticação.
        """
        pass

    @abstractmethod
    def buscar_publicacoes(self):
        """
        Método obrigatório: Deve retornar uma LISTA de dicionários.
        """
        pass

    def processar(self):
        """
        Método principal que orquestra: Login -> Busca -> Filtro -> Deduplicação
        """
        novas_publicacoes = []
        
        try:
            self.logger.info("Iniciando login...")
            self.login()
            
            self.logger.info("Buscando publicacoes...")
            resultados_brutos = self.buscar_publicacoes()
            
            for item in resultados_brutos:
                # Gera o ID único (Hash)
                id_unico = str(item.get('identificador_unico') or hash(item.get('texto_publicacao', '')))
                
                # Deduplicação
                if self.db.ja_processado(id_unico):
                    self.logger.debug(f"Publicação {id_unico} já processada. Pulando.")
                    continue
                
                # Monta o objeto final
                publicacao = {
                    "fonte": self.__class__.__name__,
                    "data_coleta": datetime.now().isoformat(),
                    "data_publicacao": item.get('data_publicacao'),
                    "termo_encontrado": item.get('termo_encontrado'),
                    "numero_processo": item.get('numero_processo'),
                    "texto_publicacao": item.get('texto_publicacao'),
                    "link_oficial": item.get('link_oficial'),
                    "identificador_unico": id_unico
                }
                
                # Salva no banco
                if self.db.salvar_publicacao(publicacao):
                    novas_publicacoes.append(publicacao)
                    self.logger.info(f"Nova publicação encontrada: {id_unico}")

        except Exception as e:
            self.logger.error(f"Erro fatal durante execução: {str(e)}", exc_info=True)
        
        return novas_publicacoes