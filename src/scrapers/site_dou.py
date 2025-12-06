import logging
import urllib.parse
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class SiteDOU:
    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger(__name__)
        self.BASE_URL_CONSULTA = "https://www.in.gov.br/consulta?q="

    def extrair_texto_materia(self, driver, link):
        """
        Acessa o link da matéria e extrai o texto completo.
        """
        try:
            self.logger.info(f"📖 Lendo conteúdo: {link}")
            driver.get(link)
            
            # Espera o texto carregar (classe padrão do DOU é 'texto-dou')
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "texto-dou"))
                )
            except:
                # Se não achar a classe, tenta esperar pelo body
                time.sleep(3)

            # Estratégia: Pega todo o texto da div principal ou parágrafos
            try:
                # Tenta pegar a div específica de texto do DOU
                elemento_texto = driver.find_element(By.CLASS_NAME, "texto-dou")
                conteudo = elemento_texto.text
            except:
                # Fallback: Pega todos os parágrafos da página
                paragrafos = driver.find_elements(By.TAG_NAME, "p")
                conteudo = "\n".join([p.text for p in paragrafos if len(p.text) > 50])

            return conteudo if conteudo else "Texto não identificado."

        except Exception as e:
            self.logger.error(f"Erro ao ler matéria: {e}")
            return "Erro na extração."

    def buscar_links(self, driver, termo):
        """
        Faz a busca e retorna apenas a lista de links (sem entrar neles ainda).
        """
        resultados_preliminares = []
        try:
            # 1. Navegação (Re-Trigger Strategy)
            termo_safe = urllib.parse.quote(termo)
            url_final = f"{self.BASE_URL_CONSULTA}{termo_safe}&publish=true"
            
            self.logger.info(f"--- Buscando links para: '{termo}' ---")
            driver.get(url_final)
            
            # 2. Re-Trigger na caixa de busca
            try:
                caixa_busca = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "input.field, input#search-bar"))
                )
                caixa_busca.click()
                caixa_busca.clear()
                caixa_busca.send_keys(termo)
                time.sleep(0.5)
                caixa_busca.send_keys(Keys.ENTER)
            except Exception:
                pass # Se falhar, segue com o que tem
            
            # 3. Aguarda e Extrai Links
            time.sleep(5)
            driver.execute_script("window.scrollTo(0, 400);")

            elementos = driver.find_elements(By.CSS_SELECTOR, "h5.title-marker a")
            if not elementos:
                elementos = driver.find_elements(By.TAG_NAME, "a")

            for el in elementos:
                try:
                    link = el.get_attribute('href')
                    titulo = el.text.strip()
                    
                    if link and "/web/dou" in link:
                        titulo_limpo = titulo.replace('\n', ' ').replace('\r', '')
                        if len(titulo_limpo) > 5:
                            if not any(r['link'] == link for r in resultados_preliminares):
                                resultados_preliminares.append({'titulo': titulo_limpo, 'link': link})
                except:
                    continue
                    
        except Exception as e:
            self.logger.error(f"Erro na busca de links: {e}")

        return resultados_preliminares