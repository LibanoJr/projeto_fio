import sqlite3
import logging
import os
from datetime import datetime

class DatabaseManager:
    def __init__(self, db_path="data/fio.db"):
        # Garante que a pasta data existe
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self.logger = logging.getLogger('Database')
        self.init_db()

    def get_connection(self):
        return sqlite3.connect(self.db_path)

    def init_db(self):
        """Cria a tabela se não existir."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Tabela robusta com campo CONTEUDO
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS publicacoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                termo_busca TEXT,
                titulo TEXT,
                link TEXT UNIQUE,
                conteudo TEXT,
                data_publicacao TEXT,
                data_captura DATETIME
            )
        ''')
        conn.commit()
        conn.close()

    def salvar_publicacao(self, dados):
        """Salva uma publicação no banco. Retorna True se salvou, False se já existia."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO publicacoes (termo_busca, titulo, link, conteudo, data_captura)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                dados.get('termo'),
                dados.get('titulo'),
                dados.get('link'),
                dados.get('conteudo', 'Conteúdo não extraído'),
                datetime.now()
            ))
            conn.commit()
            self.logger.info(f"💾 [NOVO] Salvo no banco: {dados['titulo'][:30]}...")
            return True
        except sqlite3.IntegrityError:
            self.logger.info(f"⚠️ [DUPLICADO] Já existe no banco: {dados['link']}")
            return False
        except Exception as e:
            self.logger.error(f"Erro ao salvar no banco: {e}")
            return False
        finally:
            conn.close()