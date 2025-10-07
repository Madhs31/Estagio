import requests
import base64

# 🔑 Substitua pelo seu token de API pessoal (copiado de /my/access_token)
API_KEY = "082b0167b517e464b3629e06a6a35e687aae05b8bc028780b93e94df730d2c83"
URL = "http://localhost:8080/api/v3/projects"

# Cria o cabeçalho Authorization no formato Basic base64("apikey:api_token")
token_bytes = f"apikey:{API_KEY}".encode("utf-8")
encoded_token = base64.b64encode(token_bytes).decode("utf-8")

headers = {
    "Authorization": f"Basic {encoded_token}",
    "Content-Type": "application/json"
}

response = requests.get(URL, headers=headers)

print("Status:", response.status_code)
print("Resposta:", response.text)
