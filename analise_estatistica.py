import requests
import pandas as pd
import os
from dotenv import load_dotenv

# --- CONFIGURAÇÃO ---
load_dotenv()
API_KEY = os.getenv("API_KEY_GOVERNO")

def extrair_dados_finais():
    print("📥 [1/3] Extraindo dados da UFPA (Jan/Fev 2024)...")
    url = "https://api.portaldatransparencia.gov.br/api-de-dados/contratos"
    headers = {"chave-api-dados": API_KEY}
    
    params = {
        "dataInicioVigencia": "01/01/2024",
        "dataFimVigencia": "29/02/2024", 
        "codigoOrgao": "26239", # UFPA
        "pagina": 1
    }
    
    lista_contratos = []
    # Vamos pegar 3 páginas para ter volume
    for pag in range(1, 4):
        params['pagina'] = pag
        try:
            resp = requests.get(url, headers=headers, params=params)
            if resp.status_code == 200:
                dados = resp.json()
                lista_contratos.extend(dados)
                print(f"   -> Página {pag}: {len(dados)} contratos.")
            else:
                break
        except Exception as e:
            print(f"Erro na página {pag}: {e}")
            
    return lista_contratos

def processar_dados(dados_brutos):
    print("🧹 [2/3] Organizando tabela...")
    
    if not dados_brutos:
        return pd.DataFrame()

    df = pd.DataFrame(dados_brutos)
    
    # 1. Seleciona as colunas CERTAS que descobrimos
    colunas_interesse = ['numero', 'dataAssinatura', 'valorInicialCompra', 'objeto', 'fornecedor']
    
    # Garante que as colunas existem
    for col in colunas_interesse:
        if col not in df.columns:
            df[col] = None
            
    df_final = df[colunas_interesse].copy()
    
    # 2. Extrai o nome do Fornecedor (que vem dentro de um dicionário)
    df_final['Nome_Fornecedor'] = df['fornecedor'].apply(lambda x: x.get('nome') if isinstance(x, dict) else 'N/A')
    df_final['CNPJ_Fornecedor'] = df['fornecedor'].apply(lambda x: x.get('cnpjFormatado') if isinstance(x, dict) else 'N/A')
    
    # 3. Converte o VALOR (Agora com o nome certo e sem gambiarra de vírgula)
    # Como vimos no teste, o dado já vem "36172.8", então é só converter direto.
    df_final['valorInicialCompra'] = pd.to_numeric(df_final['valorInicialCompra'], errors='coerce').fillna(0.0)
    
    # Renomeia para ficar bonito no Excel
    df_final = df_final.rename(columns={'valorInicialCompra': 'Valor_Contrato'})
    
    # Remove a coluna complexa de fornecedor antiga
    del df_final['fornecedor']
    
    return df_final

def gerar_relatorio(df):
    print("📊 [3/3] Calculando estatísticas...")
    
    if df.empty:
        print("❌ Sem dados.")
        return

    # Separação para estatística
    df_zerados = df[df['Valor_Contrato'] == 0]
    df_reais = df[df['Valor_Contrato'] > 0]

    stats = {
        "Total de Contratos": len(df),
        "Contratos Zerados (R$ 0,00)": len(df_zerados),
        "Contratos Válidos": len(df_reais),
        "Soma Total dos Valores": df['Valor_Contrato'].sum(),
        "Maior Contrato Único": df['Valor_Contrato'].max(),
        "Média dos Contratos Válidos": df_reais['Valor_Contrato'].mean()
    }
    
    print("\n" + "="*40)
    print("RESUMO PARA O TCC")
    print("="*40)
    
    print(f"Quantidade Total: {stats['Total de Contratos']}")
    print(f"Soma Total: R$ {stats['Soma Total dos Valores']:,.2f}")
    print(f"Maior Contrato: R$ {stats['Maior Contrato Único']:,.2f}")
    
    # Salva o arquivo final
    arquivo = "dados_processados_tcc.csv"
    df.to_csv(arquivo, index=False)
    print(f"\n💾 SUCESSO! Arquivo '{arquivo}' gerado.")
    print("👉 Abra este arquivo no Excel para conferir.")

if __name__ == "__main__":
    dados = extrair_dados_finais()
    tabela = processar_dados(dados)
    gerar_relatorio(tabela)