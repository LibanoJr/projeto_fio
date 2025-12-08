import sqlite3
import logging
import os
from datetime import datetime

class DatabaseManager:
    def __init__(self, db_path="data/fio.db"):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self.logger = logging.getLogger('Database')
        self.init_db()

    def get_connection(self):
        return sqlite3.connect(self.db_path)

    def init_db(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Cria a tabela básica
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS publicacoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                termo_busca TEXT,
                titulo TEXT,
                link TEXT UNIQUE,
                conteudo TEXT,
                cnpjs TEXT,    -- NOVA COLUNA
                valores TEXT,  -- NOVA COLUNA
                data_publicacao TEXT,
                data_captura DATETIME
            )
        ''')
        
        # --- MIGRAÇÃO AUTOMÁTICA (Para não precisar apagar o banco) ---
        # Tenta adicionar as colunas caso o banco já exista sem elas
        try:
            cursor.execute("ALTER TABLE publicacoes ADD COLUMN cnpjs TEXT")
            cursor.execute("ALTER TABLE publicacoes ADD COLUMN valores TEXT")
        except sqlite3.OperationalError:
            pass # Colunas já existem, segue o jogo

        conn.commit()
        conn.close()

    def salvar_publicacao(self, dados):
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
                dados.get('conteudo'),
                datetime.now()
            ))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        except Exception as e:
            self.logger.error(f"Erro ao salvar: {e}")
            return False
        finally:
            conn.close()

    # --- NOVA FUNÇÃO PARA ATUALIZAR DADOS MINERADOS ---
    def atualizar_mineracao(self, id_pub, cnpjs, valores):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                UPDATE publicacoes 
                SET cnpjs = ?, valores = ?
                WHERE id = ?
            ''', (cnpjs, valores, id_pub))
            conn.commit()
        finally:
            conn.close()