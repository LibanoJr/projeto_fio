import logging
import time
import re
import random
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

class SiteJusbrasil:
    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger(__name__)
        # URL de Busca Processual (Mais limpa)
        self.BASE_URL = "https://www.jusbrasil.com.br/consulta-processual/busca?q="

    def rolagem_humana(self, driver):
        """Rola a página devagar para carregar elementos e simular humano."""
        try:
            total_height = int(driver.execute_script("return document.body.scrollHeight"))
            for i in range(1, total_height, random.randint(300, 700)):
                driver.execute_script(f"window.scrollTo(0, {i});")
                time.sleep(random.uniform(0.1, 0.3))
            # Volta pro topo rapidinho
            driver.execute_script("window.scrollTo(0, 0);")
        except: pass

    def buscar_links(self, driver, termo):
        resultados = []
        try:
            termo_url = termo.replace(' ', '+').replace('"', '')
            url_final = f"{self.BASE_URL}{termo_url}"
            
            self.logger.info(f"Navegando: {url_final}")
            driver.get(url_final)
            time.sleep(random.uniform(2, 4))

            # --- VERIFICAÇÃO DE LOGIN / CAPTCHA ---
            # Se o título for "Atenção" ou "Verificação", caiu no Captcha forte
            titulo = driver.title
            if "Just a moment" in titulo or "Atenção" in titulo or "Captcha" in titulo:
                print("\n" + "🚨" * 20)
                print("CAPTCHA DETECTADO! O robô vai esperar você resolver.")
                print("Resolva o desafio no navegador e depois VOLTE AQUI.")
                input("👉 Pressione ENTER quando a página liberar...")
            
            # --- TENTATIVA DE CLIQUE INTELIGENTE ---
            # Procura links na lista de resultados
            clicou = False
            try:
                # Procura links que tenham "/processos/nome/"
                # Isso evita clicar em links de diários oficiais ou jurisprudência aleatória
                links = driver.find_elements(By.XPATH, "//a[contains(@href, '/processos/nome/')]")
                
                for link in links:
                    texto_link = link.text.upper()
                    # Se o nome buscado está no link, é o nosso alvo
                    if termo.upper().replace('"', '') in texto_link:
                        self.logger.info(f"Clicando no perfil: {texto_link}")
                        link.click()
                        clicou = True
                        break
                
                if not clicou and links:
                    # Se não achou nome exato, clica no primeiro resultado de processo
                    self.logger.info("Nome exato não achado, clicando no 1º resultado de processo...")
                    links[0].click()
                    clicou = True
                    
            except Exception as e:
                self.logger.warning(f"Erro ao tentar clicar: {e}")

            # --- PAUSA DE SEGURANÇA (LOGIN) ---
            # Essa pausa é essencial na 1ª vez. Nas próximas, você pode só dar Enter direto.
            print("\n" + "🛑" * 30)
            print("VERIFIQUE O NAVEGADOR:")
            if not clicou:
                print("1. CLIQUE no nome da pessoa (se o robô não clicou).")
            print("2. IMPORTANTE: Faça LOGIN (Google/Email) para ver todos os dados.")
            print("3. Aguarde a página carregar totalmente.")
            input("👉 Pressione ENTER para extrair os dados...")
            print("🛑" * 30 + "\n")

            self.logger.info("Realizando rolagem para carregar dados escondidos...")
            self.rolagem_humana(driver)
            time.sleep(1)

            # --- EXTRAÇÃO VIA LEITURA DE TEXTO (FAIL-SAFE) ---
            try:
                texto_pagina = driver.find_element(By.TAG_NAME, "body").text
                linhas = texto_pagina.split('\n')
            except:
                self.logger.error("Página em branco ou travada.")
                return []

            stats = {
                'total': '0',
                'envolvido_como': [],
                'nomes_relacionados': []
            }

            # 1. Total (Lógica Otimizada)
            for linha in linhas[:50]:
                if "processos" in linha.lower() and any(c.isdigit() for c in linha):
                    # Ex: "Encontrados 100 Processos"
                    stats['total'] = linha.strip()
                    break

            # 2. Polos
            if "Requerente" in texto_pagina or "Autor" in texto_pagina: stats['envolvido_como'].append("Autor")
            if "Requerido" in texto_pagina or "Réu" in texto_pagina: stats['envolvido_como'].append("Réu")

            # 3. Empresas (Filtro Melhorado)
            ignorar = ["JUSBRASIL", "BUSCA", "LOGIN", "ENTRAR", "MENU", "CONSULTAR", "ADVOGADO", termo.upper()]
            sufixos = [' LTDA', ' S.A.', ' S/A', ' BANCO ', ' CONDOMINIO ', ' ASSOC', ' COOP']

            for linha in linhas:
                linha_up = linha.upper().strip()
                if len(linha_up) < 4: continue
                
                # Se for palavra proibida, pula
                if any(x in linha_up for x in ignorar): continue

                eh_empresa = any(s in linha_up for s in sufixos)
                tem_cnpj = re.search(r'\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}', linha)

                if (eh_empresa or tem_cnpj) and linha_up not in stats['nomes_relacionados']:
                    stats['nomes_relacionados'].append(linha.strip())

            stats['nomes_relacionados'] = stats['nomes_relacionados'][:15]

            # --- FORMATAÇÃO ---
            empresas_str = "\n   -> ".join(stats['nomes_relacionados']) if stats['nomes_relacionados'] else "Nenhuma detectada"
            
            resumo = (
                f"📊 RELATÓRIO OTIMIZADO\n"
                f"👤 Alvo: {termo}\n"
                f"🔢 Processos: {stats['total']}\n"
                f"⚖️ Polos: {', '.join(stats['envolvido_como'])}\n"
                f"🏢 Partes Relacionadas:\n   -> {empresas_str}"
            )

            resultados.append({
                'titulo': f"Dossiê: {termo}",
                'link': driver.current_url,
                'resumo_tela': resumo,
                'stats': stats
            })

        except Exception as e:
            self.logger.error(f"Erro Jusbrasil: {e}")

        return resultados

    def extrair_texto_materia(self, driver, url):
        return "Conteúdo extraído."