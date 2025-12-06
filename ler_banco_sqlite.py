import sqlite3
import os

# O caminho do arquivo (geralmente fica na pasta data, ou na raiz)
# Se seu arquivo fio.db estiver solto na raiz, mude para "fio.db"
caminho_banco = "data/fio.db" 

if not os.path.exists(caminho_banco):
    # Tenta procurar na raiz se não achou na pasta data
    caminho_banco = "fio.db"

if os.path.exists(caminho_banco):
    print(f"📂 Lendo banco de dados: {caminho_banco}\n")
    
    # Conecta no arquivo binário
    conn = sqlite3.connect(caminho_banco)
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT * FROM publicacoes")
        linhas = cursor.fetchall()
        
        print(f"📊 TOTAL DE REGISTROS: {len(linhas)}")
        print("="*60)
        
        for linha in linhas:
            # linha é uma tupla: (id, fonte, data, termo, enviado, etc...)
            print(f"🆔 ID: {linha[0]}")
            print(f"🏛️ Fonte: {linha[1]}")
            print(f"📅 Data: {linha[2]}")
            print(f"🔍 Termo: {linha[3]}")
            print(f"📤 Enviado: {'Sim' if linha[4] else 'Não'}")
            print("-" * 60)
            
    except Exception as e:
        print(f"Erro ao ler tabela: {e}")
    finally:
        conn.close()
else:
    print("❌ Arquivo de banco de dados não encontrado.")