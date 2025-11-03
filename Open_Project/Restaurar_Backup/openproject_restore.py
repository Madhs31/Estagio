import os
import json
import requests
import shutil
import urllib3
from zipfile import ZipFile
from requests.auth import HTTPBasicAuth

# =================  CONFIGURAÇÃO =================
# ATENÇÃO: Configurado para o seu ambiente localhost
OPENPROJECT_URL = "http://localhost:8080" 
API_KEY = "062003c042ae1642ede7c1fb07554e9b14bb97e2ebe41ebc509699b51165ca56" # Chave do seu script original
VERIFY_SSL = False # Mude para True se seu ambiente de destino tiver um SSL válido

BACKUP_FOLDER = "openproject_backups" 
UNZIPPED_FOLDER = os.path.join(BACKUP_FOLDER, "unzipped_backup")

# Desabilita avisos de SSL se VERIFY_SSL for False
if not VERIFY_SSL:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Encontra o arquivo de backup mais recente
BACKUP_FILE = None
try:
    files = [os.path.join(BACKUP_FOLDER, f) for f in os.listdir(BACKUP_FOLDER) if f.endswith(".zip")]
    if not files:
        raise FileNotFoundError(f"Nenhum arquivo .zip encontrado em '{BACKUP_FOLDER}'")
    # Usa o arquivo do seu log de erro como exemplo, mas busca o mais recente
    BACKUP_FILE = max(files, key=os.path.getmtime) 
    print(f"Arquivo de backup encontrado: {BACKUP_FILE}")
except Exception as e:
    print(f"ERRO ao encontrar arquivo de backup: {e}")
    exit()


HEADERS = {"Content-Type": "application/json"}
# Usa a autenticação correta (HTTPBasicAuth)
AUTH = HTTPBasicAuth('apikey', API_KEY)

# =================  FUNÇÕES AUXILIARES =================

def unzip_backup(zip_path, extract_path):
    print(f"Descompactando {zip_path} para {extract_path}...")
    if os.path.exists(extract_path): 
        print("Limpando pasta de descompactação antiga...")
        shutil.rmtree(extract_path)
    os.makedirs(extract_path, exist_ok=True)
    with ZipFile(zip_path, 'r') as zip_ref: 
        zip_ref.extractall(extract_path)
    print("Descompactação concluída.")

def load_data(base_data_path, data_type):
    """
    Carrega dados da estrutura de backup específica.
    """
    print(f"Carregando dados para '{data_type}'...")
    all_items = []
    all_attachments = [] # Apenas para work_packages
    
    main_folder_path = os.path.join(base_data_path, data_type)

    if not os.path.exists(main_folder_path):
        print(f"AVISO: Pasta principal '{main_folder_path}' não encontrada.")
        if data_type == 'work_packages': return [], []
        return []

    try:
        # --- Lógica para 'users', 'time_entries', 'budgets' (arquivos JSON únicos) ---
        if data_type in ['users', 'time_entries', 'budgets']:
            json_file = os.path.join(main_folder_path, f"{data_type}.json")
            if os.path.exists(json_file):
                with open(json_file, 'r', encoding='utf-8') as f:
                    all_items = json.load(f)
            else:
                print(f"AVISO: Arquivo '{json_file}' não encontrado.")
        
        # --- Lógica para 'projects' (subpastas com 'project_details.json') ---
        elif data_type == 'projects':
            for item_name in os.listdir(main_folder_path):
                item_path = os.path.join(main_folder_path, item_name)
                if os.path.isdir(item_path):
                    json_to_load = os.path.join(item_path, 'project_details.json')
                    if os.path.exists(json_to_load):
                        with open(json_to_load, 'r', encoding='utf-8') as f:
                            all_items.append(json.load(f))
        
        # --- Lógica para 'work_packages' (arquivos wp_ID.json) ---
        elif data_type == 'work_packages':
            for item_name in os.listdir(main_folder_path):
                if item_name.startswith('wp_') and item_name.endswith('.json'):
                    json_to_load = os.path.join(main_folder_path, item_name)
                    with open(json_to_load, 'r', encoding='utf-8') as f:
                        wp_data = json.load(f)
                        all_items.append(wp_data)
                        
                        # Extrai anexos de dentro do JSON do WP
                        attachments = wp_data.get('_embedded', {}).get('attachments', {}).get('elements', [])
                        if attachments:
                            all_attachments.extend(attachments)
        
        # --- Lógica para 'schemas' (múltiplos JSONs) ---
        elif data_type == 'schemas':
             for item_name in os.listdir(main_folder_path):
                if item_name.endswith('.json'):
                    json_to_load = os.path.join(main_folder_path, item_name)
                    with open(json_to_load, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        all_items.append({"schema_name": item_name.replace('.json', ''), "data": data})
        
        else:
            print(f"AVISO: Tipo de dado '{data_type}' não possui lógica de carregamento definida.")
            
    except Exception as e:
        print(f"ERRO fatal ao carregar dados para '{data_type}': {e}")

    print(f"Encontrados {len(all_items)} itens para '{data_type}'.")
    
    if data_type == 'work_packages':
        # Seu log mostrou 0 anexos, o que está correto se não havia anexos.
        print(f"Encontrados {len(all_attachments)} anexos no total (extraídos dos WPs).")
        return all_items, all_attachments
        
    return all_items


def get_system_map(endpoint):
    """Busca um mapa de {nome: href} para um endpoint (ex: types, statuses, roles)."""
    url = f"{OPENPROJECT_URL}/api/v3/{endpoint}"
    try:
        r = requests.get(url, auth=AUTH, verify=VERIFY_SSL)
        r.raise_for_status()
        return {item['name']: item['_links']['self']['href'] for item in r.json()["_embedded"]["elements"]}
    except requests.exceptions.RequestException as e:
        # --- MODIFICADO ---: Não imprime o erro completo, apenas a falha.
        print(f"Falha ao buscar dados de '{endpoint}': {e}")
        # Retorna um mapa vazio em caso de falha (como o 404)
        return {} 

def get_existing_data_map(endpoint, key_field='login'):
    """Busca dados existentes e mapeia por um campo chave (ex: 'login' para usuários, 'identifier' para projetos)."""
    print(f"Buscando {endpoint} existentes no sistema...")
    url = f"{OPENPROJECT_URL}/api/v3/{endpoint}"
    params = {"pageSize": 500}
    try:
        r = requests.get(url, auth=AUTH, params=params, verify=VERIFY_SSL)
        r.raise_for_status()
        elements = r.json()["_embedded"]["elements"]
        print(f"{len(elements)} {endpoint} existentes encontrados.")
        return {item[key_field]: item for item in elements}
    except requests.exceptions.RequestException as e:
        print(f"AVISO: Não foi possível buscar {endpoint}: {e}")
        return {}

# ================= FUNÇÕES DE CRIAÇÃO (Sem alterações) =================

def create_user(user):
    payload = {
        "login": user.get("login"),
        "firstName": user.get("firstName"),
        "lastName": user.get("lastName"),
        "email": user.get("email"),
        "status": "active",
        "password": "SenhaPadraoRestauracao123!"
    }
    url = f"{OPENPROJECT_URL}/api/v3/users"
    r = requests.post(url, headers=HEADERS, auth=AUTH, json=payload, verify=VERIFY_SSL)
    if r.status_code == 201:
        print(f" Usuário criado: {payload['login']}"); return r.json()
    else:
        print(f" Falha ao criar usuário {payload['login']}: {r.status_code} - {r.text}"); return None

def create_project(project):
    payload = {
        "name": project.get("name"),
        "identifier": project.get("identifier"),
        "description": {"raw": project.get("description", {}).get("raw", "")}
    }
    url = f"{OPENPROJECT_URL}/api/v3/projects"
    r = requests.post(url, headers=HEADERS, auth=AUTH, json=payload, verify=VERIFY_SSL)
    if r.status_code == 201:
        print(f" Projeto criado: {payload['name']}")
        return r.json()
    else:
        print(f" Falha ao criar projeto {payload['name']} (Identifier: {payload['identifier']}): {r.status_code} - {r.text}")
        return None

def create_project_membership(new_project_id, membership, user_map, role_map_by_name):
    try:
        old_user_id = int(membership["_links"]["principal"]["href"].split("/")[-1])
        new_user_obj = user_map.get(old_user_id)
        if not new_user_obj:
            print(f"  AVISO: Membro (ID antigo {old_user_id}) não encontrado no mapa. Pulando.")
            return

        role_hrefs = []
        for role in membership.get("_embedded", {}).get("roles", []):
            role_href = role_map_by_name.get(role["name"])
            if role_href:
                role_hrefs.append({"href": role_href})
            else:
                print(f"  AVISO: Papel '{role['name']}' não encontrado no sistema de destino. Pulando papel.")
        
        if not role_hrefs:
            print(f"  AVISO: Nenhum papel válido encontrado para o membro {new_user_obj['login']}. Pulando.")
            return

        payload = {
            "_links": {
                "principal": {"href": new_user_obj["_links"]["self"]["href"]},
                "roles": role_hrefs
            }
        }
        url = f"{OPENPROJECT_URL}/api/v3/projects/{new_project_id}/memberships"
        r = requests.post(url, headers=HEADERS, auth=AUTH, json=payload, verify=VERIFY_SSL)
        
        if r.status_code == 201:
            print(f"  Membro '{new_user_obj['login']}' adicionado ao projeto.")
        else:
            print(f"  Falha ao adicionar membro '{new_user_obj['login']}': {r.status_code} - {r.text}")
            
    except Exception as e:
        print(f"  ERRO inesperado ao adicionar membro: {e}")

def create_work_package(wp, project_href, type_href, status_href, assignee_href=None):
    payload = {
        "subject": wp.get("subject", "Sem título"),
        "description": {"raw": wp.get("description", {}).get("raw", "")},
        "startDate": wp.get("startDate"),
        "dueDate": wp.get("dueDate"),
        "estimatedTime": wp.get("estimatedTime"),
        "_links": {
            "project": {"href": project_href},
            "type": {"href": type_href},
            "status": {"href": status_href},
        }
    }
    if assignee_href: 
        payload["_links"]["assignee"] = {"href": assignee_href}
    
    url = f"{OPENPROJECT_URL}/api/v3/work_packages"
    r = requests.post(url, headers=HEADERS, auth=AUTH, json=payload, verify=VERIFY_SSL)
    if r.status_code == 201:
        print(f" Tarefa criada: {payload['subject']}"); return r.json()
    else:
        print(f" Erro ao criar tarefa '{payload['subject']}': {r.status_code} - {r.text}"); return None

# Esta função não será chamada se o módulo for ignorado, mas a mantemos aqui
def create_time_entry(entry, project_href, wp_href, user_href, activity_href_map):
    activity_name = entry["_links"]["activity"]["title"]
    new_activity_href = activity_href_map.get(activity_name)
    if not new_activity_href:
        print(f"  AVISO: Atividade de tempo '{activity_name}' não encontrada no destino. Usando padrão.")
        if not activity_href_map:
            print(f"  ERRO: Nenhuma atividade de tempo configurada no sistema. Pulando registro {entry['id']}.")
            return None
        new_activity_href = next(iter(activity_href_map.values()))

    payload = {
        "spentOn": entry.get("spentOn"),
        "hours": entry.get("hours"),
        "comment": {"raw": entry.get("comment", {}).get("raw", "")},
        "_links": {
            "project": {"href": project_href},
            "workPackage": {"href": wp_href},
            "user": {"href": user_href},
            "activity": {"href": new_activity_href}
        }
    }
    url = f"{OPENPROJECT_URL}/api/v3/time_entries"
    r = requests.post(url, headers=HEADERS, auth=AUTH, json=payload, verify=VERIFY_SSL)
    if r.status_code == 201:
        print(f"  Registro de tempo criado ({payload['hours']} em {payload['spentOn']})")
        return r.json()
    else:
        print(f"  Falha ao criar registro de tempo: {r.status_code} - {r.text}")
        return None

def upload_attachment(new_wp_id, attachment_info, base_data_path):
    try:
        file_name = attachment_info.get("fileName")
        attachment_id = attachment_info.get("id")
        old_wp_id = attachment_info["_links"]["container"]["href"].split("/")[-1]
        backup_file_name = f"{attachment_id}_{file_name}"
        file_path = os.path.join(base_data_path, "attachments", str(old_wp_id), backup_file_name)
        
        if not os.path.exists(file_path):
            print(f" Anexo não encontrado no backup: {file_path}")
            file_path_alt = os.path.join(base_data_path, "attachments", str(old_wp_id), file_name)
            if not os.path.exists(file_path_alt):
                print(f"   -> Tentativa 2 falhou: {file_path_alt}. Pulando anexo.")
                return
            else:
                print(f"   -> AVISO: Encontrado anexo com nome alternativo (sem ID prefixado).")
                file_path = file_path_alt
        
        url = f"{OPENPROJECT_URL}/api/v3/work_packages/{new_wp_id}/attachments"
        
        with open(file_path, 'rb') as f:
            files = {'file': (file_name, f, attachment_info.get("contentType", "application/octet-stream"))}
            r = requests.post(url, auth=AUTH, files=files, verify=VERIFY_SSL)
            
            if r.status_code == 201:
                print(f"✅ Anexo '{file_name}' enviado para tarefa {new_wp_id}")
            else:
                print(f" Falha ao enviar anexo '{file_name}': {r.status_code} - {r.text}")
                
    except Exception as e:
        print(f" ERRO inesperado ao processar anexo {attachment_info.get('id')}: {e}")

# =================  EXECUÇÃO PRINCIPAL =================
def main():
    print("\n Iniciando restauração completa do backup...\n")
    unzip_backup(BACKUP_FILE, UNZIPPED_FOLDER)

    base_data_path = UNZIPPED_FOLDER
    try:
        subfolders = [d for d in os.listdir(UNZIPPED_FOLDER) if os.path.isdir(os.path.join(UNZIPPED_FOLDER, d))]
        if len(subfolders) == 1:
            base_data_path = os.path.join(UNZIPPED_FOLDER, subfolders[0])
        elif len(subfolders) > 1:
            # Este aviso apareceu no seu log. Está correto.
            print("AVISO: Múltiplas pastas encontradas, usando a pasta raiz (comportamento esperado).")
        else:
             print("AVISO: Nenhuma subpasta encontrada, usando a pasta raiz.")
    except Exception as e:
        print(f"AVISO: Não foi possível determinar a subpasta de backup, usando a pasta raiz. Erro: {e}")
    
    print(f"Pasta de dados do backup sendo usada: {base_data_path}")

    # --- Carregando dados do backup ---
    users_data = load_data(base_data_path, "users")
    projects_data = load_data(base_data_path, "projects")
    work_packages_data, attachments_data = load_data(base_data_path, "work_packages")
    time_entries_data = load_data(base_data_path, "time_entries")

    print("\nBuscando mapas do sistema de DESTINO (Tipos, Status, Papéis, Atividades)...")
    type_map_by_name = get_system_map("types")
    status_map_by_name = get_system_map("statuses")
    role_map_by_name = get_system_map("roles") # Necessário para membros
    
    # --- MODIFICAÇÃO INICIADA ---
    # Verifica mapas essenciais
    if not all([type_map_by_name, status_map_by_name, role_map_by_name]):
        print("\n CRÍTICO: Não foi possível obter mapas essenciais (tipos, status, papéis) do sistema de destino. Abortando.")
        return
    
    # Verifica mapa opcional (Time Tracking)
    skip_time_entries = False
    activity_map_by_name = get_system_map("time_tracking/activities") # Necessário para registros de tempo
    
    # Se o mapa de atividades vier vazio (devido ao erro 404), ativa a bandeira para pular.
    if not activity_map_by_name:
        print("\n*******************************************************************************")
        print("AVISO: Não foi possível buscar o mapa de 'atividades' (time_tracking/activities).")
        print("       Isso geralmente significa que o módulo 'Registro de Tempo e Custos' não está")
        print(f"       habilitado ou não existe no sistema de destino ({OPENPROJECT_URL}).")
        print("       A restauração de REGISTROS DE TEMPO será IGNORADA.")
        print("*******************************************************************************\n")
        skip_time_entries = True
    # --- MODIFICAÇÃO CONCLUÍDA ---

    print("\n--- Iniciando criação de usuários ---")
    existing_users = get_existing_data_map("users", key_field='login')
    user_map = {} # Mapeia {ID_ANTIGO: Objeto_NOVO_USUARIO}
    
    for user in users_data:
        user_login = user.get("login")
        if user_login in existing_users:
            print(f"Usuário '{user_login}' já existe. Usando o existente.")
            user_map[user["id"]] = existing_users[user_login]
        else:
            new_user = create_user(user)
            if new_user: user_map[user["id"]] = new_user

    print("\n--- Iniciando criação de projetos e membros ---")
    existing_projects = get_existing_data_map("projects", key_field='identifier')
    project_map = {} # Mapeia {ID_ANTIGO: Objeto_NOVO_PROJETO}
    
    for project in projects_data:
        project_identifier = project.get("identifier")
        new_project_obj = None
        
        if project_identifier in existing_projects:
            print(f"Projeto '{project.get('name')}' (Identifier: {project_identifier}) já existe. Usando o existente.")
            new_project_obj = existing_projects[project_identifier]
            project_map[project["id"]] = new_project_obj
        else:
            new_project_obj = create_project(project)
            if new_project_obj:
                project_map[project["id"]] = new_project_obj
        
        if new_project_obj:
            new_project_id = new_project_obj['id']
            print(f"  ... Restaurando membros para o projeto '{new_project_obj['name']}'")
            memberships = project.get('_embedded', {}).get('memberships', [])
            for member in memberships:
                create_project_membership(new_project_id, member, user_map, role_map_by_name)
            
            print(f"  ... AVISO: Restauração de Wiki, Fóruns, Versões e Categorias não implementada.")

    print("\n--- Iniciando criação de tarefas ---")
    wp_map = {} # Mapeia {ID_ANTIGO_WP: ID_NOVO_WP}
    wp_href_map = {} # Mapeia {ID_ANTIGO_WP: Href_NOVO_WP}
    
    for wp in work_packages_data:
        try:
            old_proj_id = int(wp["_links"]["project"]["href"].split("/")[-1])
        except (KeyError, TypeError, ValueError):
            print(f"AVISO: Tarefa {wp.get('id')} não tem um link de projeto válido. Pulando.")
            continue
            
        new_project_obj = project_map.get(old_proj_id) 
        
        if not new_project_obj: 
            print(f"AVISO: Projeto ID {old_proj_id} não foi encontrado no mapa. Tarefa '{wp.get('subject')}' será ignorada.")
            continue
            
        type_name = wp["_links"]["type"]["title"]
        status_name = wp["_links"]["status"]["title"]
        new_type_href = type_map_by_name.get(type_name)
        new_status_href = status_map_by_name.get(status_name)
        
        if not new_type_href or not new_status_href:
            print(f"Tipo ('{type_name}') ou Status ('{status_name}') não encontrado no sistema de destino. Tarefa '{wp.get('subject')}' ignorada.")
            continue
        
        new_assignee_href = None
        if "assignee" in wp["_links"] and wp["_links"]["assignee"]["href"]:
            try:
                old_assignee_id = int(wp["_links"]["assignee"]["href"].split("/")[-1])
                new_user_obj = user_map.get(old_assignee_id)
                if new_user_obj:
                    new_assignee_href = new_user_obj["_links"]["self"]["href"]
                else:
                    print(f"Responsável ID {old_assignee_id} não encontrado. Taref- '{wp.get('subject')}' será criada sem responsável.")
            except (KeyError, TypeError, ValueError):
                 print(f"Link de responsável inválido. Tarefa '{wp.get('subject')}' será criada sem responsável.")
        
        new_wp = create_work_package(wp, 
                                     project_href=new_project_obj["_links"]["self"]["href"],
                                     type_href=new_type_href, 
                                     status_href=new_status_href, 
                                     assignee_href=new_assignee_href)
        
        if new_wp:
            wp_map[wp["id"]] = new_wp["id"]
            wp_href_map[wp["id"]] = new_wp["_links"]["self"]["href"]
            
    print("\n--- Iniciando upload de anexos ---")
    if not attachments_data:
        print("Nenhum anexo encontrado nos dados do backup para carregar.")
        
    for attachment in attachments_data:
        try:
            old_wp_id = int(attachment["_links"]["container"]["href"].split("/")[-1])
        except (KeyError, TypeError, ValueError):
            print(f"AVISO: Anexo {attachment.get('id')} não tem um link de container válido. Pulando.")
            continue

        new_wp_id = wp_map.get(old_wp_id)
        if new_wp_id:
            upload_attachment(new_wp_id, attachment, base_data_path)
        else:
            print(f"Tarefa (ID antigo {old_wp_id}) para anexo '{attachment['fileName']}' não encontrada. Anexo ignorado.")

    # --- MODIFICAÇÃO INICIADA ---
    # Só executa este bloco se o módulo de time tracking foi encontrado
    if not skip_time_entries:
        print("\n--- Iniciando criação de Registros de Tempo ---")
        for entry in time_entries_data:
            try:
                old_proj_id = int(entry["_links"]["project"]["href"].split("/")[-1])
                old_wp_id = int(entry["_links"]["workPackage"]["href"].split("/")[-1])
                old_user_id = int(entry["_links"]["user"]["href"].split("/")[-1])
            except (KeyError, TypeError, ValueError) as e:
                print(f"AVISO: Registro de tempo {entry.get('id')} tem links inválidos ({e}). Pulando.")
                continue

            new_project_obj = project_map.get(old_proj_id)
            new_wp_href = wp_href_map.get(old_wp_id)
            new_user_obj = user_map.get(old_user_id)

            if not all([new_project_obj, new_wp_href, new_user_obj]):
                print(f"AVISO: Não foi possível mapear Projeto/WP/Usuário para o registro de tempo {entry['id']}. Pulando.")
                continue
            
            create_time_entry(entry, 
                              project_href=new_project_obj["_links"]["self"]["href"],
                              wp_href=new_wp_href,
                              user_href=new_user_obj["_links"]["self"]["href"],
                              activity_href_map=activity_map_by_name)
    else:
        print("\n--- Criação de Registros de Tempo IGNORADA (módulo não encontrado) ---")
    # --- MODIFICAÇÃO CONCLUÍDA ---

    print("\n--- AVISOS FINAIS ---")
    print("AVISO: A restauração de Orçamentos (Budgets), Wiki, Fóruns, Versões, Categorias e outros Schemas (Tipos de Custo, etc.) não foi implementada neste script.")
    print("\nRestauração concluída!\n")

if __name__ == "__main__":
    main()