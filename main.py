import os
import time
import requests
import gspread
import json
from dotenv import load_dotenv

load_dotenv()

COC_TOKEN = os.getenv("COC_TOKEN")
SHEET_ID = os.getenv("SHEET_ID")
CLAN_TAG = os.getenv("CLAN_TAG")

if CLAN_TAG.startswith("#"):
    CLAN_TAG = CLAN_TAG.replace("#", "%23")
else:
    CLAN_TAG = "%23" + CLAN_TAG

def obtener_cliente_sheets():
    """Conecta a Google Sheets en Local o Nube"""
    google_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
    if google_json:
        creds_dict = json.loads(google_json)
        return gspread.service_account_from_dict(creds_dict)
    else:
        return gspread.service_account(filename="google_credentials.json")

def sincronizar_miembros(gc, headers):
    """Módulo 1: Actualiza BD de Miembros"""
    print("\n--- 1. Sincronizando BD de Miembros ---")
    url = f"https://cocproxy.royaleapi.dev/v1/clans/{CLAN_TAG}"
    response = requests.get(url, headers=headers)
    
    if response.status_code != 200:
        print(f"Error al obtener clan: {response.status_code}")
        return
        
    datos_clan = response.json()
    miembros_api = {m['tag']: m for m in datos_clan.get('memberList', [])}
    
    mapa_rangos = {
        'leader': 'Líder',
        'coLeader': 'Colíder',
        'admin': 'Veterano',
        'member': 'Miembro'
    }
    
    worksheet_db = gc.open_by_key(SHEET_ID).worksheet("DB_Miembros")
    datos_db = worksheet_db.get_all_values()
    
    if not datos_db: return
        
    tags_en_db = {}
    
    for i, fila in enumerate(datos_db[1:]):
        if not fila: continue
        while len(fila) < 6:
            fila.append("")
            
        tag = fila[0]
        tags_en_db[tag] = True
        
        if tag in miembros_api:
            jugador = miembros_api[tag]
            fila[1] = jugador['name']
            fila[2] = mapa_rangos.get(jugador['role'], 'Miembro')
            fila[3] = str(jugador['townHallLevel'])
            fila[4] = "Activo"
        else:
            if fila[4] == "Activo":
                fila[4] = "Salió"
    
    for tag, jugador in miembros_api.items():
        if tag not in tags_en_db:
            datos_db.append([
                tag, jugador['name'], mapa_rangos.get(jugador['role'], 'Miembro'), 
                str(jugador['townHallLevel']), "Activo", ""
            ])
            
    worksheet_db.update(values=datos_db, range_name=f"A1:F{len(datos_db)}")
    print("¡Base de datos actualizada con éxito!")

def sincronizar_asaltos(gc, headers):
    """Módulo 2: Actualiza Asaltos de la Capital"""
    print("\n--- 2. Sincronizando Asaltos de la Capital ---")
    url = f"https://cocproxy.royaleapi.dev/v1/clans/{CLAN_TAG}/capitalraidseasons"
    response = requests.get(url, headers=headers)
    
    if response.status_code != 200: return
        
    data = response.json()
    latest_season = data['items'][0]
    
    raid_stats = {m['tag']: {'ataques': m['attacks'], 'oro': m['capitalResourcesLooted']} 
                  for m in latest_season.get('members', [])}
        
    worksheet_asaltos = gc.open_by_key(SHEET_ID).worksheet("Asaltos_Capital")
    tags_en_hoja = worksheet_asaltos.col_values(1)
    nuevos_datos = []
    
    for tag in tags_en_hoja[1:]:
        if tag in raid_stats:
            nuevos_datos.append([raid_stats[tag]['ataques'], raid_stats[tag]['oro']])
        else:
            nuevos_datos.append([0, 0])
            
    if nuevos_datos:
        rango = f"C2:D{len(tags_en_hoja)}"
        worksheet_asaltos.update(values=nuevos_datos, range_name=rango)
        print("¡Éxito! Asaltos actualizados.")

def sincronizar_guerra(gc, headers):
    """Módulo 3: Actualiza Guerra de Clanes"""
    print("\n--- 3. Sincronizando Guerra Actual ---")
    url = f"https://cocproxy.royaleapi.dev/v1/clans/{CLAN_TAG}/currentwar"
    response = requests.get(url, headers=headers)
    
    worksheet_guerra = gc.open_by_key(SHEET_ID).worksheet("Guerra_Actual")
    
    if response.status_code != 200:
        print("API de Guerra bloqueada (Registro de guerra oculto) o error de conexión.")
        return
        
    data = response.json()
    estado = data.get('state', 'notInWar')
    
    # Si no hay guerra, vaciamos las columnas de datos (dejando la B intacta para no borrar tu fórmula)
    if estado == 'notInWar':
        print("El clan no está en guerra. Limpiando tablero...")
        worksheet_guerra.batch_clear(["A2:A60", "C2:E60"])
        return
        
    print(f"Estado de la guerra: {estado.upper()}")
    
    miembros_guerra = data.get('clan', {}).get('members', [])
    # Ordenamos a los jugadores por su número de mapa (1, 2, 3...)
    miembros_guerra.sort(key=lambda x: x.get('mapPosition', 99))
    
    tags = []
    stats = []
    
    for miembro in miembros_guerra:
        tag = miembro['tag']
        ataques_lista = miembro.get('attacks', [])
        
        # Calcular totales
        ataques_realizados = len(ataques_lista)
        estrellas = sum(atk['stars'] for atk in ataques_lista)
        destruccion = sum(atk['destructionPercentage'] for atk in ataques_lista)
        
        tags.append([tag])
        stats.append([ataques_realizados, estrellas, destruccion])
        
    # Limpiamos los datos anteriores antes de insertar los nuevos
    worksheet_guerra.batch_clear(["A2:A60", "C2:E60"])
    
    # Inyectamos en dos bloques separados para saltarnos la columna B (donde está tu fórmula)
    if tags:
        worksheet_guerra.update(values=tags, range_name=f"A2:A{len(tags)+1}")
        worksheet_guerra.update(values=stats, range_name=f"C2:E{len(stats)+1}")
        print(f"¡Éxito! Plantilla de {len(tags)} jugadores en guerra inyectada.")

def flujo_principal():
    """Controlador que ejecuta todo secuencialmente"""
    headers = {
        "Authorization": f"Bearer {COC_TOKEN}",
        "Accept": "application/json"
    }
    
    try:
        gc = obtener_cliente_sheets()
    except Exception as e:
        print(f"Error crítico de conexión a Google Sheets: {e}")
        return
        
    sincronizar_miembros(gc, headers)
    time.sleep(3) # Pausa para que Sheets recalcule fórmulas
    sincronizar_asaltos(gc, headers)
    sincronizar_guerra(gc, headers)
    print("\n--- SINCRONIZACIÓN COMPLETADA ---")

if __name__ == "__main__":
    flujo_principal()