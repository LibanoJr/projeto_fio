# Projeto FIO - Robô de Monitoramento Jurídico

## 📋 Sobre o Projeto
Este projeto consiste em um robô (crawler) desenvolvido em Python para realizar consultas diárias em sites jurídicos (Diários Oficiais e Tribunais). O objetivo é filtrar publicações por termos específicos (OAB, CPF, CNPJ, nomes) e notificar um sistema externo via Webhook.

O sistema conta com:
- **Autenticação:** Suporte a login em áreas restritas.
- **Deduplicação:** Banco de dados local (SQLite) para garantir que a mesma publicação não seja enviada duas vezes.
- **Resiliência:** Sistema de logs e tratamento de erros.

## 🚀 Tecnologias
- Python 3.8+
- SQLite (Persistência de dados)
- Requests / BeautifulSoup (Scraping leve)
- Selenium (Scraping complexo)
- Schedule (Agendamento de tarefas)

## ⚙️ Configuração

### 1. Variáveis de Ambiente
Crie um arquivo `.env` na raiz do projeto com as credenciais dos sites:
```bash
SITE_TJSP_USER=seu_usuario
SITE_TJSP_PASS=sua_senha