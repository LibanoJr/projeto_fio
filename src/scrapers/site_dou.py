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
        # Vamos direto para a página de consulta, onde tem a caixa grande
        self.BASE_URL_CONSULTA = "https://www.in.gov.br/consulta?q="

    def buscar_e_extrair(self, driver, termo):
        resultados = []
        try:
            # 1. Navega para a URL (isso carrega a página com a caixa de busca vazia)
            termo_safe = urllib.parse.quote(termo)
            url_final = f"{self.BASE_URL_CONSULTA}{termo_safe}&publish=true"
            
            self.logger.info(f"--- Acessando: '{termo}' ---")
            driver.get(url_final)
            
            # 2. PROCURA A CAIXA DE BUSCA GRANDE (DA SUA FOTO)
            # Na página de consulta, o input geralmente tem a classe 'field' ou está dentro de um form específico
            self.logger.info("Procurando caixa de pesquisa na página de resultados...")
            
            try:
                # Tenta seletores genéricos que funcionam nessa página de consulta
                caixa_busca = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "input.field, input[type='text'], input#search-bar"))
                )
                
                # 3. RE-FAZ A BUSCA (O "Re-Trigger")
                # Limpa o campo (que pode estar vazio ou com lixo)
                caixa_busca.click()
                caixa_busca.clear()
                
                # Digita devagar
                self.logger.info("Digitando termo novamente para forçar atualização...")
                caixa_busca.send_keys(termo)
                time.sleep(0.5)
                caixa_busca.send_keys(Keys.ENTER)
                
            except Exception as e:
                self.logger.warning(f"Não consegui redigitar na caixa: {e}")
                # Se falhar, segue tentando extrair caso a URL tenha funcionado milagrosamente
            
            # 4. AGUARDA RESULTADOS
            self.logger.info("Aguardando lista atualizar...")
            time.sleep(6) # Tempo para o Liferay recarregar a div de resultados
            
            # Scroll para garantir
            driver.execute_script("window.scrollTo(0, 400);")

            # 5. EXTRAÇÃO (Seletores validados)
            elementos = driver.find_elements(By.CSS_SELECTOR, "h5.title-marker a")
            
            # Fallback: pega todos os links se o layout mudar
            if not elementos:
                elementos = driver.find_elements(By.TAG_NAME, "a")

            for el in elementos:
                try:
                    link = el.get_attribute('href')
                    titulo = el.text.strip()
                    
                    # Filtro de segurança
                    if link and "/web/dou" in link:
                        titulo_limpo = titulo.replace('\n', ' ').replace('\r', '')
                        
                        if len(titulo_limpo) > 5:
                            if not any(r['link'] == link for r in resultados):
                                resultados.append({'titulo': titulo_limpo, 'link': link})
                except:
                    continue

        except Exception as e:
            self.logger.error(f"Erro geral: {e}")
            try:
                driver.save_screenshot(f"erro_final_{termo}.png")
            except:
                pass

        return resultados