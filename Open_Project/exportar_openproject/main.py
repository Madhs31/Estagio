# main.py

import os
from datetime import datetime

# Define a API Key antes de importar o módulo
os.environ["OPENPROJECT_API_KEY"] = ""  # Coloque sua API Key

from openproject_api import get_work_packages_for_export
from export_xls import export_to_xls
# VVV IMPORTA A FUNÇÃO GRAPH VVV
from send_email import enviar_email_graph_com_anexo

print("=== Relatório Mensal do OpenProject (Todos os Work Packages) ===")

api_key = os.getenv('OPENPROJECT_API_KEY')
os.environ['OPENPROJECT_API_KEY'] = api_key

try:
    dados = get_work_packages_for_export()

    if not dados:
        print("\n Nenhum dado encontrado.")
    else:
        print(f"\n {len(dados)} work packages processados.")

    # 1. Exporta o arquivo
    arquivo = export_to_xls(dados)
    print(f"\n Relatório gerado: {arquivo}")

    # --- BLOCO PARA ENVIAR EMAIL VIA MICROSOFT GRAPH ---
    if dados:  # Só tenta enviar email se o relatório não estiver vazio
        print("Iniciando envio de email via Microsoft Graph API...")

        # Define o assunto e o corpo do email
        data_hoje = datetime.now().strftime('%d/%m/%Y')
        assunto = f"Relatório OpenProject - {data_hoje}"
        corpo = (
            f"Olá,\n\n"
            f"Segue em anexo o relatório de lançamentos do OpenProject gerado em {data_hoje}.\n\n"
            f"Este relatório contém {len(dados)} registros.\n\n"
            f"Atenciosamente,\nRobô de Relatórios"
        )

        # 2. Chama a função de envio do Graph API
        enviar_email_graph_com_anexo(assunto, corpo, arquivo)

    else:
        print("Nenhum dado encontrado, email não será enviado.")
    # ----------------------------------------------------

except Exception as e:
    print(f"\n Erro na execução: {e}")