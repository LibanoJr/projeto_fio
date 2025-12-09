import requests
import logging
import json

logger = logging.getLogger('Notifier')

def enviar_webhook(dados, url):
    """
    Envia o JSON da publicação para o sistema externo via POST.
    Requisito do PDF: Item 5 e 9.
    """
    if not url:
        logger.warning("⚠️ URL do Webhook não configurada. Pulanvo envio.")
        return

    headers = {'Content-Type': 'application/json'}
    
    # Prepara o payload (pacote) exatamente como pedido no PDF (Item 4)
    payload = {
        "fonte": "Diario Oficial da Uniao",
        "data_coleta": str(dados.get('data_captura')),
        "termo_encontrado": dados.get('termo'),
        "texto_publicacao": dados.get('conteudo'),
        "link_oficial": dados.get('link'),
        "identificador_unico": dados.get('link'), # Usando link como ID único
        # Campos extras minerados
        "cnpjs_encontrados": dados.get('cnpjs'),
        "valores_encontrados": dados.get('valores')
    }

    try:
        response = requests.post(url, data=json.dumps(payload, default=str), headers=headers, timeout=10)
        if response.status_code in [200, 201]:
            logger.info(f"🚀 Webhook enviado com sucesso para: {dados['titulo'][:30]}...")
        else:
            logger.error(f"❌ Falha no Webhook: {response.status_code} - {response.text}")
    except Exception as e:
        logger.error(f"❌ Erro ao enviar webhook: {e}")