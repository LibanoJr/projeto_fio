# 🛡️ GovAudit Pro - Auditoria de Contratos Públicos com IA

O **GovAudit Pro** é uma ferramenta desenvolvida para o Trabalho de Conclusão de Curso (TCC) que utiliza Inteligência Artificial (Google Gemini) e dados abertos para auditar contratos públicos federais em busca de riscos e irregularidades.

## 🚀 Funcionalidades

* **🕵️ Análise de Fornecedores:** Verifica automaticamente o CNPJ de empresas em bases de sanções (CEIS, CNEP, Acordos de Leniência).
* **📊 Monitoramento de Contratos:** Busca contratos reais via API do Portal da Transparência.
* **🧠 IA Auditora:** Utiliza o modelo **Gemini 2.0 Flash** para ler o objeto do contrato e classificar o risco jurídico em:
    * 🔴 **ALTO** (Objetos vagos, genéricos ou suspeitos)
    * 🟠 **MÉDIO** (Atenção necessária)
    * 🟢 **BAIXO** (Objeto claro e bem definido)

## 🛠️ Tecnologias Utilizadas

* **Python 3.9+**
* **Streamlit** (Interface Web)
* **Google Gemini API** (Inteligência Artificial Generativa)
* **API Portal da Transparência** (Dados Governamentais)

---

## ⚙️ Como Rodar o Projeto

Siga os passos abaixo para executar a aplicação em sua máquina.

### 1. Clonar o Repositório
```bash
git clone [https://github.com/LibanoJr/projeto_fio.git](https://github.com/LibanoJr/projeto_fio.git)
cd projeto_fio

### 2. Criar Ambiente Virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

### 3. Instalar Dependências
pip install -r requirements.txt

### 4. Configurar Variáveis de Ambiente
Crie um arquivo `.env` na raiz do projeto com:
PORTAL_KEY=sua_chave_portal_transparencia
GEMINI_API_KEY=sua_chave_google_gemini

### 5. Executar a Aplicação
streamlit run app.py