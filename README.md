# 🏛️ PROJETO FIO: Auditor de Contratos Públicos com IA

> **Status:** ✅ Funcional (Fase de Análise Jurídica)

O **Projeto FIO** é uma ferramenta de auditoria automatizada que utiliza Inteligência Artificial Generativa (**Google Gemini**) para fiscalizar a integridade, clareza e riscos em contratos públicos federais.

Diferente de sistemas tradicionais que analisam apenas números, o FIO atua como um **Analista Jurídico Virtual**, lendo e interpretando o objeto dos contratos do **Portal da Transparência** para identificar inconsistências, descrições vagas ou irregularidades administrativas.

---

## 🚀 Funcionalidades

- **📡 Conexão Governamental:** Integração direta com a API do Portal da Transparência Federal.
- **🧠 Análise Semântica (NLP):** Uso do Google Gemini (LLM) para "ler" o juridiquês dos contratos.
- **🔍 Detecção de Riscos:**
  - Identificação de objetos genéricos ou obscuros.
  - Alerta para contratos com Valor R$ 0,00 (risco de falta de empenho ou erro de cadastro).
  - Verificação de datas e vigências suspeitas (ex: dados legados).
- **📄 Geração de Dossiê:** Criação automática de relatórios em formato Markdown prontos para apresentação.

---

## 🛠️ Tecnologias Utilizadas

- **Linguagem:** Python 3.x
- **Integração API:** `requests` (Consumo de API REST do Governo Federal)
- **Inteligência Artificial:** `google-generativeai` (Google Gemini Flash)
- **Estrutura de Dados:** JSON e Manipulação de Arquivos

---

## 📊 Exemplo de Auditoria Real

O sistema é capaz de gerar pareceres técnicos detalhados. Abaixo, um exemplo real de saída do sistema detectando uma inconsistência financeira:

> **CONTRATO Nº 322005 (MEC)**
>
> **Objeto:** *Fornecimento de energia elétrica tarifa horo-sazonal...*
> **Valor Declarado:** R$ 0,00
>
> **🧠 Parecer da IA:**
> **Risco Identificado (ALTO):** O valor zerado é inadequado para um serviço contínuo e oneroso (energia). Indica falha no cadastro ou falta de transparência orçamentária, impedindo a fiscalização do custo efetivo.

---

## ⚙️ Como Executar

### Pré-requisitos
- Python instalado.
- Chave de API do [Portal da Transparência](https://api.portaldatransparencia.gov.br/).
- Chave de API do [Google AI Studio](https://aistudio.google.com/).

### Instalação

1. Clone o repositório:
   ```bash
   git clone [https://github.com/seu-usuario/projeto-fio.git](https://github.com/seu-usuario/projeto-fio.git)