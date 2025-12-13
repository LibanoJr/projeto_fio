import logging
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class SiteTJSP:
    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger(__name__)
        # Vamos entrar pela HOME PAGE da Jurisprudência, não pelo form direto
        self.BASE_URL = "https://esaj.tjsp.jus.br/cjsp/"

    def buscar_links(self, driver, termo):
        resultados = []
        try:
            self.logger.info(f"--- Acessando TJ-SP (Home): '{termo}' ---")
            driver.get(self.BASE_URL)
            time.sleep(5) # Espera generosa para carregamento e cookies

            # --- DEBUG: Salva o que ele está vendo logo de cara ---
            driver.save_screenshot("debug_tjsp_entrada.png")

            # 1. Verifica se estamos na página certa procurando o Título ou Logo
            if "Jurisprudência" not in driver.title and "TJSP" not in driver.title:
                self.logger.error("❌ Título da página estranho. Pode ser bloqueio.")
                with open("erro_tjsp_source.html", "w", encoding="utf-8") as f:
                    f.write(driver.page_source)
                return []

            # 2. Procura a caixa de busca (Tentativa por seletores visuais)
            # O ID 'dados.buscaInteiroTeor' é o padrão, mas às vezes carrega 'prec' ou 'search'
            campo_busca = None
            try:
                # Tenta o seletor mais comum da Home de Jurisprudência
                campo_busca = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "input#dados\\.buscaInteiroTeor, input[name='dados.buscaInteiroTeor']"))
                )
            except:
                self.logger.warning("Campo principal não achado. Tentando pegar a 'Pesquisa Livre' genérica...")
                # Tenta pegar qualquer textarea ou input grande
                inputs = driver.find_elements(By.TAG_NAME, "input")
                for inp in inputs:
                    # Pega inputs de texto que estejam visíveis
                    if inp.get_attribute("type") == "text" and inp.is_displayed():
                        campo_busca = inp
                        break
            
            if not campo_busca:
                self.logger.error("❌ FALHA CRÍTICA: Caixa de busca invisível.")
                return []

            # 3. Digita e Pesquisa
            self.logger.info("Digitando termo...")
            campo_busca.click()
            campo_busca.clear()
            campo_busca.send_keys(termo)
            time.sleep(1)
            
            # Clica no botão (Geralmente tem texto 'Consultar' ou 'Pesquisar')
            try:
                # Tenta achar botão pelo texto (mais seguro que ID)
                driver.find_element(By.XPATH, "//input[@value='Consultar']").click()
            except:
                driver.find_element(By.CLASS_NAME, "botaoConsultar").click()
            
            # 4. Aguarda tabela de resultados
            self.logger.info("Aguardando carregamento da lista...")
            time.sleep(5)
            
            # Verifica se achou algo
            if "Não foram encontrados registros" in driver.page_source:
                self.logger.info("TJ-SP retornou 0 resultados.")
                return []

            # 5. Extração (Tabela Padrão)
            # A classe das linhas costuma ser 'fundamento-juridico' ou apenas linhas de tabela
            linhas = driver.find_elements(By.CSS_SELECTOR, "tr.fundamentoJuridico")
            
            if not linhas:
                # Fallback: pega tabela genérica se o layout mudar
                tabela = driver.find_elements(By.ID, "div-resultado-consulta")
                if tabela:
                    linhas = tabela[0].find_elements(By.TAG_NAME, "tr")

            self.logger.info(f"Encontrados {len(linhas)} itens brutos.")

            for i, linha in enumerate(linhas):
                if i >= 5: break
                try:
                    texto_resumo = linha.text.strip()
                    if len(texto_resumo) < 20: continue # Pula linhas vazias

                    # Cria link fake pois o TJSP usa javascript:abrirDoc()
                    link_fake = f"https://esaj.tjsp.jus.br/cjsp/doc_fake_{hash(texto_resumo)}"
                    
                    # Tenta achar link real de download se houver
                    try:
                        link_real = linha.find_element(By.CSS_SELECTOR, "a[title='Visualizar Inteiro Teor']").get_attribute("href")
                        if link_real: link_fake = link_real
                    except: pass

                    resultados.append({
                        'titulo': f"Processo TJ-SP: {termo}",
                        'link': link_fake,
                        'resumo_tela': texto_resumo
                    })
                except: continue

        except Exception as e:
            self.logger.error(f"Erro TJ-SP: {e}")
            driver.save_screenshot("erro_tjsp_final.png")

        return resultados

    def extrair_texto_materia(self, driver, url):
        return "Conteúdo capturado via resumo da listagem (Inteiro Teor requer PDF)."