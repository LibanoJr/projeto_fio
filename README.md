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
  - Verificação de datas e vigências suspeitas.
- **🛡️ Auditoria de Fornecedores:** Cruzamento automático de CNPJ com listas de sanções (CEIS/CNEP/Leniência).
- **📄 Relatórios Visuais:** Interface interativa para apresentação de dados.

---

## 🛠️ Tecnologias Utilizadas

- **Interface:** Streamlit (Python)
- **Integração API:** `requests` (Portal da Transparência & MinhaReceita)
- **Inteligência Artificial:** `google-generativeai` (Google Gemini 1.5 Flash / Pro)
- **Segurança:** `python-dotenv` (Gestão de chaves de API)

---

## 📊 Exemplo de Auditoria Real

O sistema é capaz de gerar pareceres técnicos detalhados. Abaixo, um exemplo real de saída do sistema detectando uma inconsistência:

> **CONTRATO (MEC)**
>
> **Objeto:** *Fornecimento de energia elétrica tarifa horo-sazonal...*
> **Valor Declarado:** R$ 0,00
>
> **🧠 Parecer da IA:**
> **Risco Identificado (ALTO):** O valor zerado é inadequado para um serviço contínuo e oneroso (energia). Indica falha no cadastro ou falta de transparência, impedindo a fiscalização do custo efetivo.

---

## ⚙️ Instalação e Execução

### Pré-requisitos
1. **Python 3.x** instalado.
2. Chave de API do **Portal da Transparência** (Cadastro no Fala.BR).
3. Chave de API do **Google AI Studio** (Gemini).

### Passo a Passo

1. **Clone o repositório:**
   ```bash
   git clone [https://github.com/LibanoJr/projeto_fio.git](https://github.com/LibanoJr/projeto_fio.git)
   cd projeto_fio