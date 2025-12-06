import sys
import os

# --- CORREÇÃO DE IMPORTAÇÃO (BLINDADA) ---
# Pega o caminho absoluto deste arquivo (src/teste_real.py)
current_dir = os.path.dirname(os.path.abspath(__file__))
# Adiciona o próprio 'src' ao caminho de busca do Python
sys.path.append(current_dir)
# Adiciona a raiz do projeto também (um nível acima)
sys.path.append(os.path.dirname(current_dir))
# -----------------------------------------

from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
import logging
import time

# Agora usamos um bloco try/catch para garantir que o import funcione
try:
    # Tenta importar como se estivesse rodando da raiz (python -m src.teste_real)
    from src.scrapers.site_dou import SiteDOU
except ImportError:
    try:
        # Tenta importar direto (caso a pasta src já esteja no path)
        from scrapers.site_dou import SiteDOU
    except ImportError as e:
        print(f"ERRO CRÍTICO DE IMPORTAÇÃO: {e}")
        print("Certifique-se de que o arquivo 'site_dou.py' existe dentro de 'src/scrapers/'")
        sys.exit(1)

# Configuração visual do log
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger('TESTE')

def configurar_driver():
    """Configura o Chrome com disfarce Anti-Robô"""
    options = webdriver.ChromeOptions()
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    service = ChromeService(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)

def main():
    # Lista de termos igual ao seu print
    termos_para_busca = ["OAB", "CPF", "Licitação"]
    
    print("\n🚀 INICIANDO TESTE REAL NO DOU...\n")
    
    driver = configurar_driver()
    scraper = SiteDOU(logger)
    
    try:
        for termo in termos_para_busca:
            print(f"🔎 Pesquisando: {termo}...")
            
            # Chama a busca
            resultados = scraper.buscar_e_extrair(driver, termo)
            
            if resultados:
                print(f"✅ Sucesso! Encontrados {len(resultados)} resultados.")
                for i, item in enumerate(resultados[:3]): 
                    print(f"   [Resultado #{i+1}]")
                    print(f"   📅 Data: 06/12/2025") 
                    print(f"   🔗 Link: {item['link']}")
                    print(f"   📄 Texto: {item['titulo']}")
                    print("-" * 50)
            else:
                print("❌ Nenhum resultado encontrado (ou bloqueio).")
            
            print("\n")
            
    except Exception as e:
        logger.error(f"Erro fatal: {e}")
    finally:
        print("🏁 Teste finalizado. Fechando navegador.")
        driver.quit()

if __name__ == "__main__":
    main()