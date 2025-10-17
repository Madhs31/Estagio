from openpyxl import Workbook
from datetime import datetime

def export_to_xls(dados):
    wb = Workbook()
    ws = wb.active
    ws.title = "Relatório"

    if not dados:
        ws.append(["Nenhum dado encontrado"])
        nome = f"relatorio_vazio_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        wb.save(nome)
        return nome

    # Cabeçalhos
    ws.append(list(dados[0].keys()))

    # Linhas
    for item in dados:
        ws.append(list(item.values()))

    nome = f"relatorio_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    wb.save(nome)
    return nome
