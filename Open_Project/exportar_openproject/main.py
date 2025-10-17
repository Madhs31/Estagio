import os

# Define a API Key antes de importar o módulo
os.environ["OPENPROJECT_API_KEY"] = ""

from openproject_api import get_work_packages_for_export, parse_month_to_range
from export_xls import export_to_xls

print("=== Relatório Mensal do OpenProject (Todos os Work Packages) ===")

api_key = os.getenv('OPENPROJECT_API_KEY')
os.environ['OPENPROJECT_API_KEY'] = api_key  

# Filtro de data sempre ativado
use_filtro = True

# Input de mês
mes_input = input("Mês do relatório (ex: 09/2025): ").strip()
date_range = parse_month_to_range(mes_input)

# Busca dados
try:
    dados = get_work_packages_for_export(date_range, use_filtro)
    
    if not dados:
        print("\n Nenhum dado encontrado.")
    else:
        print(f"\n {len(dados)} work packages processados.")
    
    # Exporta
    arquivo = export_to_xls(dados)
    print(f"\n Relatório gerado: {arquivo}")
    
except Exception as e:
    print(f"\n Erro na execução: {e}")
    print("Dicas: Tente 'n' no filtro de data para pegar tudo. Verifique permissões.")
