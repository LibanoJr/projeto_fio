import sqlite3
import os

# Tenta achar o banco na pasta data ou na raiz
caminhos = ["data/fio.db", "fio.db"]
db_path = None

for c in caminhos:
    if os.path.exists(c):
        db_path = c
        break

if db_path:
    print(f"\n📂 Abrindo banco de dados: {db_path}")
    print("="*60)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Pega as últimas 5 publicações
        cursor.execute("SELECT termo_encontrado, data_coleta, link_oficial, texto_publicacao FROM publicacoes ORDER BY data_coleta DESC LIMIT 5")
        linhas = cursor.fetchall()
        
        if not linhas:
            print("📭 O banco de dados está vazio (ainda não salvou nada).")
        
        for i, linha in enumerate(linhas):
            print(f"📌 RESULTADO #{i+1}")
            print(f"🔎 Termo: {linha[0]}")
            print(f"📅 Data: {linha[1]}")
            print(f"🔗 Link: {linha[2]}")
            print(f"📝 Texto: {linha[3][:150]}...") # Mostra só o começo do texto
            print("-" * 60)
            
    except Exception as e:
        print(f"Erro ao ler: {e}")
    finally:
        conn.close()
else:
    print("❌ Arquivo de banco de dados (fio.db) não encontrado!")