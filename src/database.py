import sqlite3
import os
from datetime import datetime

class DatabaseHandler:
    def __init__(self, db_name="fio.db"):
        # Garante que o banco seja criado na pasta 'data' na raiz do projeto
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.db_path = os.path.join(base_dir, "data", db_name)
        
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        self._criar_tabela()

    def _criar_tabela(self):
        # Cria a tabela se não existir
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS publicacoes (
                id_unico TEXT PRIMARY KEY,
                fonte TEXT,
                data_coleta TEXT,
                termo_encontrado TEXT,
                enviado INTEGER DEFAULT 0
            )
        ''')
        self.conn.commit()

    def ja_processado(self, id_unico):
        # Verifica se o hash/ID já existe no banco
        self.cursor.execute("SELECT 1 FROM publicacoes WHERE id_unico = ?", (id_unico,))
        return self.cursor.fetchone() is not None

    def salvar_publicacao(self, dados):
        try:
            # Tenta inserir. Se o ID já existir, vai dar erro e cair no except
            self.cursor.execute('''
                INSERT INTO publicacoes (id_unico, fonte, data_coleta, termo_encontrado, enviado)
                VALUES (?, ?, ?, ?, 1)
            ''', (
                dados['identificador_unico'], 
                dados['fonte'], 
                datetime.now().isoformat(),
                dados.get('termo_encontrado', '')
            ))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False # Já existia, retorna Falso