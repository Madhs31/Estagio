import requests
import json
import datetime
import os
import shutil
import time
from typing import Dict, List, Optional, Any
from requests.auth import HTTPBasicAuth

# ================= CONFIGURAÇÕES =================
OPENPROJECT_URL = ""
API_KEY = ""
BACKUP_DIR = "openproject_backups"
VERIFY_SSL = False
MAX_RETRIES = 3
RETRY_DELAY = 5

# ================= CLASSE PRINCIPAL =================
class OpenProjectBackup:
    def __init__(self, base_url: str, api_key: str, verify_ssl: bool = True):
        self.base_url = base_url.rstrip('/')
        self.api_v3_url = f"{self.base_url}/api/v3"
        self.auth = HTTPBasicAuth('apikey', api_key)
        self.verify_ssl = verify_ssl
        self.headers = {'Content-Type': 'application/json'}

        if not VERIFY_SSL:
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    def _make_request(self, method: str, url: str, **kwargs) -> Optional[requests.Response]:
        for attempt in range(MAX_RETRIES):
            try:
                response = requests.request(
                    method, url, auth=self.auth, headers=self.headers,
                    verify=self.verify_ssl, **kwargs
                )
                if response.status_code == 404:
                    print(f"AVISO: Endpoint não encontrado (404): {url}. O recurso pode não existir ou o módulo estar desabilitado.")
                    return None
                response.raise_for_status()
                return response
            except requests.exceptions.RequestException as e:
                print(f"Erro na tentativa {attempt + 1}/{MAX_RETRIES} para {url}: {e}")
                if attempt + 1 == MAX_RETRIES:
                    print(f"Falha ao acessar o endpoint {url} após {MAX_RETRIES} tentativas.")
                    return None
                time.sleep(RETRY_DELAY)
        return None

    def _get_paginated_collection(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> List[Dict]:
        collection = []
        offset = 1
        page_size = 100
        current_params = params.copy() if params else {}

        while True:
            current_params.update({'offset': offset, 'pageSize': page_size})
            response = self._make_request('get', f"{self.api_v3_url}{endpoint}", params=current_params)
            
            if not response: break
            data = response.json()
            elements = data.get('_embedded', {}).get('elements', [])
            if not elements: break
            
            collection.extend(elements)
            if len(elements) < page_size: break
            offset += 1
        return collection

    def get_full_work_package(self, wp_id: int) -> Optional[Dict]:
        response = self._make_request('get', f"{self.api_v3_url}/work_packages/{wp_id}")
        if not response: return None
        
        wp_data = response.json()
        
        activities_response = self._make_request('get', f"{self.api_v3_url}/work_packages/{wp_id}/activities")
        if activities_response:
            if '_embedded' not in wp_data:
                wp_data['_embedded'] = {}
            wp_data['_embedded']['activities'] = activities_response.json().get('_embedded', {}).get('elements', [])
        
        return wp_data

    def download_attachment(self, attachment: Dict, download_path: str):
        content_url = f"{self.base_url}{attachment['_links']['self']['href']}/content"
        file_name = attachment.get('fileName', f"attachment_{attachment['id']}")
        file_path = os.path.join(download_path, f"{attachment['id']}_{file_name}")

        response = self._make_request('get', content_url)
        if response and not os.path.exists(file_path):
            with open(file_path, 'wb') as f: f.write(response.content)
            print(f"   -> Anexo '{file_name}' baixado.")
        elif os.path.exists(file_path):
            print(f"   -> Anexo '{file_name}' já existe, pulando.")

    def create_backup(self) -> Optional[str]:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        temp_backup_path = os.path.join(BACKUP_DIR, f"backup_{timestamp}_temp")
        
        try:
            # --- MODIFICADO: Adicionado 'budgets' ---
            paths = {
                "base": temp_backup_path, 
                "projects": os.path.join(temp_backup_path, "projects"),
                "work_packages": os.path.join(temp_backup_path, "work_packages"),
                "attachments": os.path.join(temp_backup_path, "attachments"),
                "users": os.path.join(temp_backup_path, "users"),
                "schemas": os.path.join(temp_backup_path, "schemas"),
                "time_entries": os.path.join(temp_backup_path, "time_entries"),
                "budgets": os.path.join(temp_backup_path, "budgets"),
            }
            for path in paths.values(): os.makedirs(path, exist_ok=True)

            print("\nIniciando backup completo...")
            total_steps = 7 # --- MODIFICADO ---

            # 1. Backup de Schemas e Configurações Globais
            print(f"\n[1/{total_steps}] Fazendo backup das configurações globais (schemas, roles, groups...)...")
            
            # --- MODIFICADO: Adicionado '/cost_types' ---
            endpoints_to_save = [
                "/types", "/statuses", "/priorities", # Schemas básicos
                "/roles", "/custom_fields", "/groups", # Configurações de admin
                "/queries", "/news", # Dados globais
                "/cost_types" # Configuração de custos
            ]
            
            for endpoint in endpoints_to_save:
                schema_name = endpoint.strip('/')
                data = self._get_paginated_collection(endpoint)
                if data:
                    with open(os.path.join(paths["schemas"], f"{schema_name}.json"), 'w', encoding='utf-8') as f:
                        json.dump(data, f, indent=2, ensure_ascii=False)
                    print(f"- {schema_name.capitalize()} salvos ({len(data)} itens).")

            # 2. Backup de Usuários
            print(f"\n[2/{total_steps}] Fazendo backup dos usuários...")
            users = self._get_paginated_collection("/users")
            with open(os.path.join(paths["users"], "users.json"), 'w', encoding='utf-8') as f:
                json.dump(users, f, indent=2, ensure_ascii=False)
            print(f"- Total de {len(users)} usuários salvos.")
            
            # 3. Backup de Projetos e sub-recursos
            print(f"\n[3/{total_steps}] Fazendo backup dos projetos...")
            projects = self._get_paginated_collection("/projects")
            print(f"- {len(projects)} projetos encontrados.")
            for project in projects:
                project_id, project_identifier = project['id'], project['identifier']
                print(f"-- Processando projeto: {project['name']} (ID: {project_id})")
                
                project_dir = os.path.join(paths["projects"], f"{project_id}_{project_identifier}")
                os.makedirs(project_dir, exist_ok=True)

                details_resp = self._make_request('get', f"{self.api_v3_url}/projects/{project_id}")
                if not details_resp: continue
                
                project_details = details_resp.json()
                
                if '_embedded' not in project_details:
                    project_details['_embedded'] = {}
                
                # Salva sub-recursos do projeto
                project_details['_embedded']['memberships'] = self._get_paginated_collection(f"/projects/{project_id}/memberships")
                project_details['_embedded']['versions'] = self._get_paginated_collection(f"/projects/{project_id}/versions")
                project_details['_embedded']['categories'] = self._get_paginated_collection(f"/projects/{project_id}/categories")
                
                # --- ADICIONADO: Wiki ---
                print(f"   ... salvando Wiki pages")
                project_details['_embedded']['wiki_pages'] = self._get_paginated_collection(f"/projects/{project_id}/wiki_pages")
                
                # --- ADICIONADO: Fóruns e Mensagens ---
                print(f"   ... salvando Fóruns e Mensagens")
                forums = self._get_paginated_collection(f"/projects/{project_id}/forums")
                forums_with_messages = []
                for forum in forums:
                    forum_id = forum['id']
                    print(f"     -> salvando mensagens do fórum: {forum.get('name')}")
                    # A API de mensagens pode ser paginada, então usamos a função helper
                    forum['messages'] = self._get_paginated_collection(f"/forums/{forum_id}/messages")
                    forums_with_messages.append(forum)
                    
                project_details['_embedded']['forums_with_messages'] = forums_with_messages
                # --- FIM ADIÇÃO ---
                
                with open(os.path.join(project_dir, "project_details.json"), 'w', encoding='utf-8') as f:
                    json.dump(project_details, f, indent=2, ensure_ascii=False)

            # 4. Backup de Work Packages e Anexos
            print(f"\n[4/{total_steps}] Fazendo backup dos pacotes de trabalho...")
            all_wps = self._get_paginated_collection("/work_packages")
            print(f"- Encontrados {len(all_wps)} pacotes de trabalho. Buscando detalhes...")
            
            for i, wp in enumerate(all_wps):
                print(f"   Processando WP {wp['id']} ({i+1}/{len(all_wps)})...")
                wp_details = self.get_full_work_package(wp['id'])
                if wp_details:
                    with open(os.path.join(paths["work_packages"], f"wp_{wp['id']}.json"), 'w', encoding='utf-8') as f:
                        json.dump(wp_details, f, indent=2, ensure_ascii=False)
                    
                    attachments = wp_details.get('_embedded', {}).get('attachments', {}).get('elements', [])
                    if attachments:
                        att_dir = os.path.join(paths["attachments"], str(wp['id']))
                        os.makedirs(att_dir, exist_ok=True)
                        for attachment in attachments: self.download_attachment(attachment, att_dir)

            # 5. Backup de Registros de Tempo
            print(f"\n[5/{total_steps}] Fazendo backup dos registros de tempo...")
            time_entries = self._get_paginated_collection("/time_entries")
            with open(os.path.join(paths["time_entries"], "time_entries.json"), 'w', encoding='utf-8') as f:
                json.dump(time_entries, f, indent=2, ensure_ascii=False)
            print(f"- Total de {len(time_entries)} registros de tempo salvos.")

            # --- NOVO PASSO ---
            # 6. Backup de Orçamentos (Budgets)
            print(f"\n[6/{total_steps}] Fazendo backup dos orçamentos (budgets)...")
            budgets = self._get_paginated_collection("/budgets")
            if budgets:
                with open(os.path.join(paths["budgets"], "budgets.json"), 'w', encoding='utf-8') as f:
                    json.dump(budgets, f, indent=2, ensure_ascii=False)
                print(f"- Total de {len(budgets)} orçamentos salvos.")
            else:
                print("- Módulo de Orçamentos não habilitado ou sem dados.")
            # --- FIM DO NOVO PASSO ---

            # 7. Compactando
            print(f"\n[7/{total_steps}] Compactando arquivos de backup...")
            zip_filename = os.path.join(BACKUP_DIR, f"openproject_backup_{timestamp}")
            shutil.make_archive(zip_filename, 'zip', paths["base"])
            print(f"Backup concluído: {zip_filename}.zip")
            return f"{zip_filename}.zip"

        finally:
            if os.path.exists(temp_backup_path):
                shutil.rmtree(temp_backup_path)
                print("Pasta temporária removida.")
        return None

# ================= FUNÇÃO PRINCIPAL =================
def main():
    if not OPENPROJECT_URL or not API_KEY:
        print("ERRO: Configure as variáveis OPENPROJECT_URL e API_KEY no início do script.")
        return

    os.makedirs(BACKUP_DIR, exist_ok=True)
    backup_client = OpenProjectBackup(OPENPROJECT_URL, API_KEY, verify_ssl=VERIFY_SSL)
    
    backup_file = backup_client.create_backup()

    if backup_file and os.path.exists(backup_file):
        size_mb = os.path.getsize(backup_file) / (1024 * 1024)
        print(f"\n✅ Backup finalizado com sucesso!")
        print(f"Arquivo salvo em: {backup_file} ({size_mb:.2f} MB)")
    else:
        print("\nOcorreu um erro e o backup não pôde ser concluído.")

if __name__ == "__main__":
    main()