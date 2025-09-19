import requests
import json

# Configurações da instalação de origem
ORIGEM_URL = 'https://openproject-origem.com/api/v3/projects'
ORIGEM_TOKEN = 'SEU_TOKEN_ORIGEM'

# Configurações da instalação de destino
DESTINO_URL = 'https://openproject-destino.com/api/v3/projects'
DESTINO_TOKEN = 'SEU_TOKEN_DESTINO'

# Cabeçalhos para autenticação
def get_headers(token):
    return {
        'Content-Type': 'application/json',
        'X-OpenProject-API-Key': token
    }

# 1. Ler todos os projetos da instalação de origem
def ler_projetos():
    response = requests.get(ORIGEM_URL, headers=get_headers(ORIGEM_TOKEN))
    response.raise_for_status()
    projetos = response.json()['_embedded']['elements']
    print(f"{len(projetos)} projetos encontrados.")
    return projetos

# 2. Salvar os dados em um arquivo local
def salvar_em_json(projetos, nome_arquivo='projetos_origem.json'):
    with open(nome_arquivo, 'w', encoding='utf-8') as f:
        json.dump(projetos, f, ensure_ascii=False, indent=2)
    print(f"Projetos salvos em {nome_arquivo}")

# 3. Criar os projetos na instalação de destino
def criar_projetos(projetos):
    for projeto in projetos:
        payload = {
            "name": projeto['name'],
            "identifier": projeto['identifier'],
            "description": projeto.get('description', {"format": "plain", "raw": ""})
        }
        response = requests.post(DESTINO_URL, headers=get_headers(DESTINO_TOKEN), json=payload)
        if response.status_code == 201:
            print(f"✅ Projeto '{projeto['name']}' criado com sucesso.")
        else:
            print(f"❌ Erro ao criar '{projeto['name']}': {response.status_code} - {response.text}")

# Execução
if __name__ == '__main__':
    projetos = ler_projetos()
    salvar_em_json(projetos)
    criar_projetos(projetos)
