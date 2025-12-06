import os
import sqlite3

caminho_banco = "data/fio.db"

# 1. Tenta apagar o arquivo fisicamente via Python (mais seguro que rm)
if os.path.exists(caminho_banco):
    try:
        os.remove(caminho_banco)
        print("🗑️ Banco de dados antigo deletado com sucesso.")
    except Exception as e:
        print(f"⚠️ Não consegui deletar o arquivo: {e}")

# 2. Força a recriação usando o código novo
try:
    # Importa a classe que acabamos de atualizar
    from src.database import DatabaseHandler
    
    db = DatabaseHandler()
    print("✅ Novo banco criado com a coluna 'link_oficial'.")
    
    # Validação
    cursor = db.conn.cursor()
    cursor.execute("PRAGMA table_info(publicacoes)")
    colunas = [col[1] for col in cursor.fetchall()]
    
    if "link_oficial" in colunas:
        print("🏆 SUCESSO! A coluna 'link_oficial' está presente.")
    else:
        print("❌ ERRO: A coluna ainda não apareceu. Verifique o arquivo src/database.py")
        
except ImportError:
    print("❌ Erro: Não consegui importar src.database. Verifique se está na raiz do projeto.")