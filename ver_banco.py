import sqlite3
import textwrap

def ver_dados():
    db_path = "data/fio.db"
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Agora buscamos também as colunas MINERADAS
        cursor.execute("SELECT id, titulo, link, cnpjs, valores FROM publicacoes WHERE cnpjs IS NOT NULL OR valores IS NOT NULL ORDER BY id DESC LIMIT 3")
        rows = cursor.fetchall()
        
        if not rows:
            print("📭 Nenhum dado minerado encontrado.")
            return

        print(f"\n{'='*60}")
        print(f"💎 DADOS ENRIQUECIDOS (MINERADOS)")
        print(f"{'='*60}")

        for id_pub, titulo, link, cnpjs, valores in rows:
            print(f"🆔 ID: {id_pub}")
            print(f"📄 Título: {titulo[:60]}...")
            print(f"🔗 Link: {link}")
            print("-" * 30)
            
            if cnpjs:
                print(f"🏢 CNPJs Extraídos:\n   {cnpjs}")
            else:
                print("🏢 CNPJs: (Nenhum)")
                
            if valores:
                print(f"💰 Valores Identificados:\n   {valores}")
            else:
                print("💰 Valores: (Nenhum)")
                
            print(f"{'='*60}\n")
            
        conn.close()
    except Exception as e:
        print(f"Erro: {e}")

if __name__ == "__main__":
    ver_dados()