import requests
import json
import os
import urllib3
import datetime
import calendar

# Desabilita aviso de SSL inseguro 
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# URL base da API
OPENPROJECT_URL = ""

# API Key
API_KEY = os.getenv('OPENPROJECT_API_KEY')
if not API_KEY:
    raise ValueError("API Key é obrigatória! Defina OPENPROJECT_API_KEY no ambiente ou no main.py.")

# Cache para armazenar usuários
_users_cache = {}

def parse_month_to_range(month_input):
    # Esta função não é mais usada pelo fluxo principal, mas foi mantida
    try:
        parts = month_input.strip().split('/')
        if len(parts) != 2:
            parts = month_input.strip().split('-')
        if len(parts) != 2:
            raise ValueError("Formato inválido. Use MM/YYYY (ex: 09/2025).")
        
        month = int(parts[0])
        year = int(parts[1])
        if not (1 <= month <= 12):
            raise ValueError("Mês deve ser de 01 a 12.")
        
        start_date = datetime.datetime(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]
        end_date = datetime.datetime(year, month, last_day)
        
        start_str = start_date.strftime('%Y-%m-%d')
        end_str = end_date.strftime('%Y-%m-%d')
        
        print(f"Período calculado: {start_str} a {end_str}")
        return [start_str, end_str]
    
    except Exception as e:
        print(f"Erro ao processar mês '{month_input}': {e}. Usando mês atual.")
        now = datetime.datetime.now()
        year = now.year
        month = now.month
        start_date = datetime.datetime(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]
        end_date = datetime.datetime(year, month, last_day)
        start_str = start_date.strftime('%Y-%m-%d')
        end_str = end_date.strftime('%Y-%m-%d')
        print(f"Período default: {start_str} a {end_str}")
        return [start_str, end_str]

def build_filters(date_range):
    # Esta função não é mais usada pelo fluxo principal, mas foi mantida
    if not date_range or not date_range[0]:
        return None
    
    data_inicio = date_range[0]
    data_fim = date_range[1] if len(date_range) > 1 and date_range[1] else data_inicio
    
    filtros_api = []
    try:
        inicio_iso = f"{data_inicio}T00:00:00Z"
        fim_iso = f"{data_fim}T23:59:59Z"
        filtros_api.append({
            "createdAt": {
                "operator": "<>d",
                "values": [inicio_iso, fim_iso]
            }
        })
        print("Nota: Filtro aplicado em 'createdAt' entre período informado.")
    except ValueError:
        print("Aviso: Data inválida. Ignorando filtro.")
        return None
    
    print(f"Debug - Filtros gerados: {json.dumps(filtros_api, indent=2)}")
    return json.dumps(filtros_api)

def get_work_packages(date_range, use_date_filter=True):
    # Esta função não é usada pelo fluxo principal (get_work_packages_for_export)
    auth = ('apikey', API_KEY)
    url = f"{OPENPROJECT_URL}/work_packages"

    params = {"pageSize": 100, "offset": 0}
    if use_date_filter:
        filters_str = build_filters(date_range)
        if filters_str:
            params["filters"] = filters_str

    headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
    all_data = []
    total_count = 0

    try:
        while True:
            r = requests.get(url, headers=headers, params=params, auth=auth, verify=False)
            r.raise_for_status()
            response_json = r.json()
            data = response_json.get("_embedded", {}).get("elements", [])
            total_count = response_json.get("total", 0)

            all_data.extend(data)
            current_page = params['offset'] // 100 + 1
            print(f"Debug - Página {current_page}: {len(data)} itens, Total até agora: {len(all_data)} / {total_count}")

            if len(data) < params["pageSize"] or len(all_data) >= total_count:
                break
            params["offset"] += params["pageSize"]

        if all_data:
            print(f"Total de work packages no relatório: {len(all_data)}")
            print("Preview dos primeiros 3:")
            for i, wp in enumerate(all_data[:3]):
                print(f"  {i+1}. ID: {wp.get('id')}, Assunto: {wp.get('subject')[:50]}..., Status: {wp.get('_embedded', {}).get('status', {}).get('name', 'N/A')}")

        return all_data

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 400 and use_date_filter:
            print(f"Filtro de data rejeitado (400). Tentando sem filtro...")
            return get_work_packages(date_range, use_date_filter=False)  
        print(f"Erro HTTP: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Status: {e.response.status_code}")
            print(f"Resposta: {e.response.text[:500]}...")
        raise
    except Exception as e:
        print(f"Erro inesperado: {e}")
        raise

def get_users():
    global _users_cache
    if _users_cache:
        return _users_cache
    
    auth = ('apikey', API_KEY)
    url = f"{OPENPROJECT_URL}/users"
    params = {"pageSize": 100, "offset": 0}
    headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
    all_users = {}
    
    try:
        while True:
            r = requests.get(url, headers=headers, params=params, auth=auth, verify=False)
            r.raise_for_status()
            response_json = r.json()
            users_data = response_json.get("_embedded", {}).get("elements", [])
            
            for user in users_data:
                user_id = user.get("id")
                if user_id:
                    all_users[str(user_id)] = { # Convertido ID para string para consistência
                        "id": user_id,
                        "name": user.get("name", ""),
                        "email": user.get("email", ""),
                        "login": user.get("login", "")
                    }
            
            if len(users_data) < params["pageSize"]:
                break
            params["offset"] += params["pageSize"]
        
        print(f"Total de usuários obtidos: {len(all_users)}")
        _users_cache = all_users
        return all_users
        
    except Exception as e:
        print(f"Erro ao obter usuários: {e}")
        return {}

def get_user_by_id(user_id):
    users = get_users()
    return users.get(str(user_id))

def get_work_package_cost_entries(work_package_id):

    # Obtém o custo total a partir das cost_entries do work package.

    try:
        url = f"{OPENPROJECT_URL}/work_packages/{work_package_id}/cost_entries"
        auth = ('apikey', API_KEY)
        headers = {'Accept': 'application/json'}
        r = requests.get(url, headers=headers, auth=auth, verify=False)
        if r.status_code != 200:
            return None
        data = r.json()
        elementos = data.get("_embedded", {}).get("elements", [])
        total = 0.0
        for e in elementos:
            valor = e.get("costs") or e.get("overallCosts")
            if valor:
                try:
                    total += float(str(valor).replace(",", "."))
                except:
                    pass
        return total if total > 0 else None
    except Exception as e:
        print(f"Erro ao buscar cost_entries para WP {work_package_id}: {e}")
        return None

def get_time_entries_corrigido():

    #Função adicionada para buscar os dados corretos (lançamentos de tempo) sem filtro de data.
    auth = ('apikey', API_KEY)
    url = f"{OPENPROJECT_URL}/time_entries"
    
    # REMOVIDO FILTRO DE DATA
    # filters = [{"spentOn": {"operator": "<>d", "values": date_range}}]
    
    # REMOVIDO "filters" DOS PARÂMETROS
    params = {"pageSize": 500, "offset": 1} 
    headers = {'Content-Type': 'application/json'}
    all_entries = []

    print("\nBuscando TODOS os lançamentos de tempo (time entries)...")
    try:
        while True:
            params['offset'] = (len(all_entries) // params['pageSize']) + 1
            r = requests.get(url, headers=headers, params=params, auth=auth, verify=False)
            r.raise_for_status()
            response_json = r.json()
            
            data = response_json.get("_embedded", {}).get("elements", [])
            total = response_json.get("total", 0)
            
            if not data: break

            all_entries.extend(data)
            print(f"  - Recebidos {len(data)} registros. Total: {len(all_entries)} de {total}")
            
            if len(all_entries) >= total: break

        print(f"Total de lançamentos no período: {len(all_entries)}")
        return all_entries
    except Exception as e:
        print(f"Erro ao buscar time_entries: {e}")
        return []

def get_work_package_details(wp_id):
    
    # Busca os detalhes completos de um work package específico, incluindo os custos.
    auth = ('apikey', API_KEY)
    url = f"{OPENPROJECT_URL}/work_packages/{wp_id}"
    headers = {'Content-Type': 'application/json'}
    try:
        r = requests.get(url, headers=headers, auth=auth, verify=False)
        r.raise_for_status()  # Lança um erro para status HTTP 4xx/5xx
        return r.json()
    except requests.exceptions.RequestException as e:
        # Silenciado o print para não poluir o console em caso de erro 404 (tarefa não encontrada)
        # print(f"  - Aviso: Não foi possível buscar detalhes para o WP ID {wp_id}. Erro: {e}")
        return None

# ==============================================================================
# FUNÇÃO MODIFICADA COM CACHE E PRINT DE PROGRESSO
# ==============================================================================
def get_work_packages_for_export(): # REMOVIDOS ARGUMENTOS
    # Esta é a chamada correta: busca os lançamentos de tempo (AGORA SEM FILTRO).
    raw_data_corrigida = get_time_entries_corrigido() # CHAMADA SEM ARGUMENTO
    
    if not raw_data_corrigida:
        print(" Nenhum dado para exportar. Verifique permissões da API Key.")
        return []
    
    users = get_users()
    
    resultado = []
    
    # --- OTIMIZAÇÃO ---
    # Cache para armazenar custos de WPs já buscados
    wp_cost_cache = {} 
    total_entries = len(raw_data_corrigida)
    print(f"\nIniciando processamento de {total_entries} registros...")
    # ------------------
    
    # O loop agora itera sobre os dados corretos (lançamentos de tempo).
    # Adicionado 'enumerate' para podermos mostrar o progresso
    for i, entry in enumerate(raw_data_corrigida):
        
        # --- MOSTRAR PROGRESSO ---
        # Mostra o progresso a cada 50 itens ou no último item
        if (i + 1) % 50 == 0 or (i + 1) == total_entries:
            print(f"  - Processando registro {i + 1} / {total_entries}...")
        # -------------------------

        links = entry.get("_links", {})
        
        data_correta = entry.get("spentOn", "")
        
        task_data = links.get("workPackage", {})
        task_number = task_data.get("href", "").split('/')[-1] if task_data.get("href") else ""
        subject = task_data.get("title", "N/A")
        pacote_trabalho = f"Task #{task_number}: {subject}"
        
        custo_total = "0,00 BRL"
        
        if task_number:
            # --- LÓGICA DE CACHE OTIMIZADA ---
            if task_number in wp_cost_cache:
                # 1. Se o custo já está no cache, usa ele
                custo_total = wp_cost_cache[task_number]
            else:
                # 2. Se não está, busca na API
                wp_details = get_work_package_details(task_number)
                if wp_details:
                    custo_total = wp_details.get("overallCosts", "0,00 BRL")
                
                # 3. Salva o resultado no cache (mesmo se falhou, salva "0,00 BRL")
                wp_cost_cache[task_number] = custo_total
            # ---------------------------------

        comentario_data = entry.get("comment", {})
        comentario = comentario_data.get("raw", "Sem comentário") if isinstance(comentario_data, dict) else ""

        user_name = links.get("user", {}).get("title", "Desconhecido")
        
        atividade = links.get("activity", {}).get("title", "Não especificada")
        projeto = links.get("project", {}).get("title", "Não especificado")
        
        horas = entry.get("hours", "PT0S").replace("PT", "")

        registro = {
            "DATA (GASTO)": data_correta,
            "USUÁRIO": user_name,
            "ATIVIDADE": atividade,
            "PACOTE DE TRABALHO": pacote_trabalho,
            "COMENTÁRIO": comentario,
            "LOGGED BY": user_name,
            "PROJETO": projeto,
            "HORAS": horas,
            "CUSTOS": custo_total # NOVO CAMPO ADICIONADO
        }
        
        resultado.append(registro)
    
    if resultado:
        print(f"\n {len(resultado)} registros prontos para exportação.")
    
    return resultado

# Bloco de execução para teste
if __name__ == '__main__':
    # Define o período desejado
    # periodo = parse_month_to_range("10/2025") # REMOVIDA LÓGICA DE DATA
    
    # Chama a função principal (que agora tem a lógica corrigida)
    dados_finais = get_work_packages_for_export() # CHAMADA SEM ARGUMENTO
    
    # Mostra uma prévia do resultado
    if dados_finais:
        print("\n--- PRÉVIA DOS 5 PRIMEIROS REGISTROS ---")
        for item in dados_finais[:5]:
            print(json.dumps(item, indent=2, ensure_ascii=False))