import sqlite3
import re
import logging
# Importa o gerenciador do banco
try:
    from database import DatabaseManager
except ImportError:
    from src.database import DatabaseManager

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger('Minerador')

class MineradorDados:
    def __init__(self):
        self.db = DatabaseManager() # Conecta ao banco automaticamente
        
        self.regex_cnpj = r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}"
        self.regex_valor = r"R\$\s?[\d\.]+(?:,\d{2})?"

    def processar_banco(self):
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        # Pega publicações que ainda não foram mineradas (opcional) ou todas
        cursor.execute("SELECT id, titulo, conteudo FROM publicacoes WHERE conteudo IS NOT NULL")
        linhas = cursor.fetchall()
        
        logger.info(f"⛏️  Iniciando mineração e salvamento em {len(linhas)} registros...\n")
        
        atualizados = 0
        
        for id_pub, titulo, texto in linhas:
            lista_cnpjs = re.findall(self.regex_cnpj, texto)
            lista_valores = re.findall(self.regex_valor, texto)
            
            if lista_cnpjs or lista_valores:
                # Transforma lista em string para salvar no banco (ex: "CNPJ1, CNPJ2")
                str_cnpjs = ", ".join(list(set(lista_cnpjs))) if lista_cnpjs else None
                str_valores = ", ".join(lista_valores) if lista_valores else None
                
                # Salva no banco
                self.db.atualizar_mineracao(id_pub, str_cnpjs, str_valores)
                
                print(f"✅ ID {id_pub} Atualizado | {titulo[:40]}...")
                if str_cnpjs: print(f"   🏢 {str_cnpjs}")
                if str_valores: print(f"   💰 {str_valores}")
                print("-" * 30)
                
                atualizados += 1
        
        logger.info(f"\n💾 Sucesso! {atualizados} registros foram enriquecidos no banco de dados.")
        conn.close()

if __name__ == "__main__":
    minerador = MineradorDados()
    minerador.processar_banco()