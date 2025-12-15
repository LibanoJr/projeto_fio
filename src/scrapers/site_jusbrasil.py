import logging
import re
import os
from selenium.webdriver.common.by import By

class SiteJusbrasil:
    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger(__name__)

    def analisar_perfil_com_abas(self, driver, url):
        resultados = []
        try:
            self.logger.info(f"   🚀 Abrindo: {url}")
            driver.get(url)
            
            # --- O MOMENTO DA VERDADE ---
            print("\n" + "🛑" * 40)
            print("   MODO DE ESPERA ATIVADO")
            print("   1. Vá no navegador agora.")
            print("   2. Se precisar logar, logue.")
            print("   3. CLIQUE na aba 'Processos'.")
            print("   4. Role até ver a lista de números.")
            print("   5. CLIQUE na aba 'Empresas' (opcional, se quiser pegar tbm).")
            print("   👉 Deixe a página exibindo o que você quer capturar.")
            print("   👉 VOLTE AQUI E APERTE [ENTER] PARA RASPAR IMEDIATAMENTE.")
            input("   [Aguardando seu comando...]")
            print("   ⚡️ RASPANDO DADOS AGORA...")
            print("🛑" * 40 + "\n")

            # 1. PEGAR TODO O CÓDIGO FONTE (HTML BRUTO)
            # Isso pega até o que está escondido nos links, não só o texto visível
            html_bruto = driver.page_source
            texto_visivel = driver.find_element(By.TAG_NAME, "body").text

            # 2. EXTRAÇÃO DE EMPRESAS (Pelo texto visível)
            empresas_set = set()
            termos_chave = ['LTDA', 'S.A.', 'S/A', 'CONDOMINIO', 'ASSOCIACAO', 'ESPÓLIO', 'MASSA FALIDA']
            
            # Divide o texto em linhas e procura padrões de empresa
            for linha in texto_visivel.split('\n'):
                linha_upper = linha.upper().strip()
                # Regras para validar se é empresa
                if len(linha_upper) > 5 and any(t in linha_upper for t in termos_chave):
                    if "JUSBRASIL" not in linha_upper and "LOGIN" not in linha_upper:
                        empresas_set.add(linha.strip())

            # 3. EXTRAÇÃO DE PROCESSOS (Pelo HTML Bruto + Regex)
            processos_set = set()
            
            # REGEX 1: Padrão CNJ Puro (ex: 0000000-00.0000.8.26.0000)
            padrao_cnj = re.findall(r'\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}', html_bruto)
            processos_set.update(padrao_cnj)
            
            # REGEX 2: Padrão Link Jusbrasil (ex: /processos/123456...)
            # Às vezes o número não tá formatado, mas tá na URL
            padrao_link = re.findall(r'processos\/(\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4})', html_bruto)
            processos_set.update(padrao_link)
            
            # ==========================================================
            # DIAGNÓSTICO (SALVA O HTML SE FALHAR)
            # ==========================================================
            if len(processos_set) == 0:
                print("   ⚠️ AVISO: Nenhum processo encontrado via Regex.")
                print("   📸 Salvando HTML para análise em 'debug_jusbrasil.html'...")
                with open("debug_jusbrasil.html", "w", encoding="utf-8") as f:
                    f.write(html_bruto)

            # ==========================================================
            # RELATÓRIO
            # ==========================================================
            lista_empresas = sorted(list(empresas_set))[:20]
            lista_processos = sorted(list(processos_set))

            print("\n" + "█"*50)
            print(f" RESULTADO FINAL")
            print("█"*50)
            
            print(f"\n🏢 EMPRESAS ({len(lista_empresas)}):")
            for e in lista_empresas: print(f"   ▫️ {e}")

            print(f"\n⚖️ PROCESSOS ({len(lista_processos)}):")
            for p in lista_processos: print(f"   🔹 {p}")
            
            print("\n" + "█"*50 + "\n")

            if lista_empresas or lista_processos:
                resumo = f"EMPRESAS:\n{', '.join(lista_empresas)}\n\nPROCESSOS:\n{', '.join(lista_processos)}"
                resultados.append({
                    'titulo': "Dossiê Manual Jusbrasil",
                    'link': url,
                    'resumo': resumo
                })

        except Exception as e:
            self.logger.error(f"Erro: {e}")

        return resultados