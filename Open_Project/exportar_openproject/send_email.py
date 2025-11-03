# send_email_graph.py
import os
import requests
import base64
import msal  # Importa a biblioteca MSAL
from datetime import datetime

# ===================================================================
# CONFIGURAÇÕES OAUTH (Microsoft Graph) - (Conforme você forneceu)
# ===================================================================
CLIENT_ID = ""
TENANT_ID = "47522429-e2db-4354-9185-34ebe972474b"
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
SCOPE = ["https://graph.microsoft.com/.default"]

# IMPORTANTE: Configure o Client Secret como uma variável de ambiente
# antes de rodar o script.
# No seu terminal, execute:
# set GRAPH_CLIENT_SECRET=   (no Windows CMD)
# $env:GRAPH_CLIENT_SECRET="" (no PowerShell)
# export GRAPH_CLIENT_SECRET='' (no Linux/macOS)
CLIENT_SECRET = os.getenv("GRAPH_CLIENT_SECRET")

# --- Configurações de Email ---
# O email que está enviando (deve ser o usuário em nome do qual a app está autorizada)
EMAIL_SENDER_GRAPH = ""
# O(s) email(s) que vão receber
EMAIL_RECEIVERS_GRAPH = [""]
# -----------------------------------------------------------------


# ===================================================================
# AUTENTICAÇÃO OAUTH - (Sua função implementada)
# ===================================================================
def get_access_token():
    """
    Obtém um token de acesso usando o fluxo de Client Credentials.
    """
    if not CLIENT_SECRET:
        print("Erro Crítico: A variável de ambiente 'GRAPH_CLIENT_SECRET' não está definida.")
        print("Não é possível obter o token de acesso.")
        return None

    print("Obtendo token de acesso para o Microsoft Graph...")
    app = msal.ConfidentialClientApplication(
        client_id=CLIENT_ID,
        client_credential=CLIENT_SECRET,
        authority=AUTHORITY,
    )

    result = app.acquire_token_for_client(scopes=SCOPE)

    if result and "access_token" in result:
        print("Token de acesso obtido com sucesso.")
        return result["access_token"]
    else:
        print(f"Erro ao obter token: {result.get('error_description', 'Erro desconhecido')}")
        print("Verifique se o Client Secret está correto e se as permissões (Mail.Send) foram concedidas no Azure.")
        return None

# ===================================================================
# FUNÇÃO DE ENVIO DE EMAIL
# ===================================================================
def enviar_email_graph_com_anexo(assunto, corpo_texto, nome_arquivo_anexo):
    """
    Envia um email com anexo usando a API do Microsoft Graph.
    """
    access_token = get_access_token()
    if not access_token:
        print("Falha ao enviar email: Não foi possível obter o token de acesso.")
        return False

    if not os.path.exists(nome_arquivo_anexo):
        print(f"Erro: Arquivo de anexo não encontrado: {nome_arquivo_anexo}")
        return False

    try:
        # Ler o arquivo e codificar em Base64
        with open(nome_arquivo_anexo, "rb") as f:
            file_content = f.read()
        file_content_base64 = base64.b64encode(file_content).decode('utf-8')
        file_name = os.path.basename(nome_arquivo_anexo)

        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }

        # Montar a lista de destinatários
        to_recipients = [{"emailAddress": {"address": email}} for email in EMAIL_RECEIVERS_GRAPH]

        # Montar o payload do email com o anexo
        email_payload = {
            "message": {
                "subject": assunto,
                "body": {
                    "contentType": "Text",  # O corpo do main.py é texto simples
                    "content": corpo_texto
                },
                "toRecipients": to_recipients,
                "from": {
                    "emailAddress": {
                        "address": EMAIL_SENDER_GRAPH
                    }
                },
                "attachments": [
                    {
                        "@odata.type": "#microsoft.graph.fileAttachment",
                        "name": file_name,
                        "contentType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # Mime type para .xlsx
                        "contentBytes": file_content_base64
                    }
                ]
            },
            "saveToSentItems": "true"
        }

        graph_url = f"https://graph.microsoft.com/v1.0/users/{EMAIL_SENDER_GRAPH}/sendMail"

        print(f"Enviando email com anexo para {', '.join(EMAIL_RECEIVERS_GRAPH)} via Graph API...")
        response = requests.post(graph_url, headers=headers, json=email_payload)

        if response.status_code == 202:
            print("Email enviado com sucesso via Microsoft Graph API!")
            return True
        else:
            print(f"Erro ao enviar email: {response.status_code}")
            print(f"Resposta: {response.text}")
            return False

    except Exception as e:
        print(f"ERRO AO ENVIAR EMAIL (Graph API): {e}")
        return False