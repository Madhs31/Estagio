import os
import json
import requests
from zipfile import ZipFile

# =================  CONFIGURAÇÃO =================
OPENPROJECT_URL = "http://localhost:8080"
API_KEY = "0b3dd576d292dbe81a0085d658c8b8b5d2d574a60747029d6ab36e48307d46d2"

BACKUP_FOLDER = "openproject_backups"

# Detecta automaticamente o primeiro arquivo .zip na pasta
BACKUP_FILE = None
for file in os.listdir(BACKUP_FOLDER):
    if file.endswith(".zip"):
        BACKUP_FILE = os.path.join(BACKUP_FOLDER, file)
        break

if BACKUP_FILE is None:
    raise FileNotFoundError("Nenhum arquivo .zip encontrado na pasta 'openproject_backups'")

print(f"Usando arquivo de backup: {os.path.abspath(BACKUP_FILE)}")

HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {API_KEY}"
}

# =================  FUNÇÕES =================
def load_backup(backup_path):
    if backup_path.endswith(".zip"):
        with ZipFile(backup_path, "r") as z:
            file_names = z.namelist()
            all_data = {}
            for f in file_names:
                if f.endswith(".json"):
                    with z.open(f) as file:
                        all_data[f.replace(".json", "")] = json.load(file)
            return all_data
    elif backup_path.endswith(".json"):
        with open(backup_path, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        raise ValueError("Formato de backup inválido. Use '.zip' ou '.json'")

def create_project(project):
    payload = {
        "name": project.get("name"),
        "identifier": project.get("identifier"),
        "description": {
            "format": "markdown",
            "raw": project.get("description", {}).get("raw", "")
        }
    }

    r = requests.post(f"{OPENPROJECT_URL}/api/v3/projects", headers=HEADERS, data=json.dumps(payload))
    if r.status_code == 201:
        print(f"Projeto criado: {payload['name']}")
        return r.json()
    else:
        print(f"Falha ao criar projeto {payload['name']}: {r.status_code} - {r.text}")
        return None

def create_work_package(project_id, wp):
    payload = {
        "subject": wp.get("subject", "Sem título"),
        "description": {
            "format": "markdown",
            "raw": wp.get("description", {}).get("raw", "")
        },
        "_links": {
            "project": {"href": f"/api/v3/projects/{project_id}"},
            "type": {"href": "/api/v3/types/1"}  # Tipo padrão de tarefa
        }
    }

    r = requests.post(f"{OPENPROJECT_URL}/api/v3/work_packages", headers=HEADERS, data=json.dumps(payload))
    if r.status_code == 201:
        print(f"Tarefa criada: {payload['subject']}")
    else:
        print(f"Erro ao criar tarefa: {r.status_code} - {r.text}")

# =================  EXECUÇÃO =================
def main():
    print("\n Iniciando restauração do backup...\n")
    data = load_backup(BACKUP_FILE)

    projects = data.get("projects", [])
    work_packages = data.get("work_packages", [])

    # Criar projetos
    project_map = {}
    for project in projects:
        new_project = create_project(project)
        if new_project:
            # Usar o ID original como chave para mapear corretamente as tarefas
            project_map[str(project["id"])] = new_project["id"]

    # Criar tarefas associadas
    for wp in work_packages:
        old_proj_id = wp["_links"]["project"]["href"].split("/")[-1]
        new_project_id = project_map.get(old_proj_id)
        if new_project_id:
            create_work_package(new_project_id, wp)
        else:
            print(f"Projeto antigo {old_proj_id} não encontrado no mapa. Tarefa {wp.get('subject')} ignorada.")

    print("\n Restauração concluída com sucesso!\n")

if __name__ == "__main__":
    main()
