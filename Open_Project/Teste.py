import requests
import base64

# 🔑 Substitua pelo seu token de API pessoal (copiado de /my/access_token)
API_KEY = "c250944e08982a7af7211376d7d46712d6049f41a409c27065302ad28ce87406"
URL = "http://localhost:8080/api/v3"  # Exemplo de endpoint da API

# Cria o cabeçalho Authorization no formato Basic base64("apikey:api_token")
token_bytes = f"apikey:{API_KEY}".encode("utf-8")
encoded_token = base64.b64encode(token_bytes).decode("utf-8")

headers = {
    "Authorization": f"Basic {encoded_token}",
    "Content-Type": "application/json"
}

try:
    # Se você ainda estiver com problema de certificado SSL, use verify=False temporariamente
    response = requests.get(URL, headers=headers, verify=False)  # ⚠️ apenas para teste!
    
    print("Status:", response.status_code)
    print("Resposta:", response.json())  # Retorna já em formato JSON
except requests.exceptions.SSLError as ssl_err:
    print("Erro SSL:", ssl_err)
except requests.exceptions.RequestException as e:
    print("Erro na requisição:", e)
