import requests
import json
import datetime
import os
import shutil
from typing import Dict, List, Optional, Any

# ================= CONFIGURAÇÕES =================
OPENPROJECT_URL = "http://localhost:8080/api/v3"  # Incluindo /api/v3
API_KEY = "082b0167b517e464b3629e06a6a35e687aae05b8bc028780b93e94df730d2c83"  # Chave da API
BACKUP_DIR = "openproject_backups"
VERIFY_SSL = False
BACKUP_SETTINGS = {
    'include_projects': True,
    'include_work_packages': True,
    'include_users': True,
    'max_retries': 3,
    'work_package_filters': None
}

# ================= CLASSE PRINCIPAL =================
class OpenProjectBackup:
    def __init__(self, base_url: str, api_key: str, verify_ssl: bool = True):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.verify_ssl = verify_ssl
        # Usando X-API-Key para autenticação
        self.headers = {
            'Content-Type': 'application/json',
            'X-API-Key': api_key
        }

    def _get_paginated_collection(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> List[Dict]:
        collection = []
        offset = 0
        page_size = 100
        current_params = params.copy() if params else {}

        while True:
            current_params.update({'offset': offset, 'pageSize': page_size})
            try:
                url = f"{self.base_url}{endpoint}" if not endpoint.startswith(self.base_url) else endpoint
                response = requests.get(url, headers=self.headers, params=current_params, verify=self.verify_ssl)

                if response.status_code == 401:
                    print("❌ Erro 401: Token inválido ou sem permissão.")
                    break
                if response.status_code != 200:
                    print(f"Erro de paginação {endpoint} (offset {offset}): {response.status_code}")
                    print(f"Resposta: {response.text[:500]}")
                    break

                data = response.json()
                elements = data.get('_embedded', {}).get('elements', [])
                if not elements:
                    break
                collection.extend(elements)
                if len(elements) < page_size:
                    break
                offset += page_size
            except requests.exceptions.RequestException as e:
                print(f"Erro ao acessar {endpoint}: {e}")
                break
        return collection

    def test_connection(self) -> bool:
        try:
            r = requests.get(f"{self.base_url}/projects", headers=self.headers, verify=self.verify_ssl)
            print(f"Status code: {r.status_code}")
            print(f"Resposta: {r.text[:500]}")
            return r.status_code == 200
        except Exception as e:
            print(f"Erro de conexão: {e}")
            return False

    def get_projects(self) -> List[Dict]:
        print("Buscando projetos...")
        return self._get_paginated_collection("/projects")

    def get_project_details(self, project_id: int) -> Dict:
        project_data = {}
        try:
            r = requests.get(f"{self.base_url}/projects/{project_id}", headers=self.headers, verify=self.verify_ssl)
            if r.status_code == 200:
                project_data['details'] = r.json()
            else:
                print(f"Erro detalhes projeto {project_id}: {r.status_code}")
        except Exception as e:
            print(f"Erro projeto {project_id}: {e}")

        project_data['work_packages'] = self._get_paginated_collection(f"/projects/{project_id}/work_packages")
        project_data['versions'] = self._get_paginated_collection(f"/projects/{project_id}/versions")
        project_data['members'] = self._get_paginated_collection(f"/projects/{project_id}/members")

        return project_data

    def get_work_packages(self, filters: Optional[List[Dict]] = None) -> List[Dict]:
        params = {}
        if filters:
            params['filters'] = json.dumps(filters)
        print("Buscando Work Packages...")
        return self._get_paginated_collection("/work_packages", params=params)

    def get_users(self) -> List[Dict]:
        print("Buscando usuários...")
        return self._get_paginated_collection("/users")

    def create_backup(self, backup_dir: str = "backups", wp_filters: Optional[List[Dict]] = None) -> str:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        temp_backup_path = os.path.join(backup_dir, f"openproject_backup_{timestamp}_temp")
        os.makedirs(temp_backup_path, exist_ok=True)

        print("Iniciando backup...")

        backup_data = {
            'metadata': {
                'backup_date': datetime.datetime.now().isoformat(),
                'openproject_url': self.base_url,
                'backup_version': '1.0'
            },
            'projects': self.get_projects(),
            'users': self.get_users(),
            'work_packages_filtered': self.get_work_packages(filters=wp_filters)
        }

        main_file = os.path.join(temp_backup_path, 'backup_data.json')
        with open(main_file, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, indent=2, ensure_ascii=False)

        projects_dir = os.path.join(temp_backup_path, 'projects')
        os.makedirs(projects_dir, exist_ok=True)

        for project in backup_data['projects']:
            project_id = project['id']
            print(f"Backup projeto: {project['name']} (ID {project_id})")
            details = self.get_project_details(project_id)
            project_file = os.path.join(projects_dir, f"project_{project_id}.json")
            with open(project_file, 'w', encoding='utf-8') as f:
                json.dump(details, f, indent=2, ensure_ascii=False)

        zip_file = shutil.make_archive(os.path.join(backup_dir, f"openproject_backup_{timestamp}"), 'zip', temp_backup_path)
        shutil.rmtree(temp_backup_path)
        print(f"Backup concluído: {zip_file}")
        return zip_file

# ================= FUNÇÃO PRINCIPAL =================
def main():
    if not OPENPROJECT_URL or not API_KEY:
        print("Configure OPENPROJECT_URL e API_KEY no script")
        return

    backup_client = OpenProjectBackup(OPENPROJECT_URL, API_KEY, verify_ssl=VERIFY_SSL)

    print("Testando conexão...")
    if not backup_client.test_connection():
        print("Falha na conexão com OpenProject!")
        return
    print("Conexão OK!")

    wp_filters = BACKUP_SETTINGS.get('work_package_filters')
    backup_file = backup_client.create_backup(BACKUP_DIR, wp_filters)

    size_mb = os.path.getsize(backup_file) / (1024*1024)
    print(f"Backup salvo: {backup_file} ({size_mb:.2f} MB)")

if __name__ == "__main__":
    main()
