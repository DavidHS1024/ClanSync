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
    """Función unificada para conectar a Google Sheets en Local o Nube"""
    google_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
    if google_json:
        creds_dict = json.loads(google_json)
        return gspread.service_account_from_dict(creds_dict)
    else:
        return gspread.service_account(filename="google_credentials.json")

def sincronizar_miembros(gc, headers):
    """Actualiza la BD de Miembros: Soft Delete, Altas y Cambios de Rango"""
    print("1. Sincronizando Base de Datos de Miembros...")
    url = f"https://cocproxy.royaleapi.dev/v1/clans/{CLAN_TAG}"
    response = requests.get(url, headers=headers)
    
    if response.status_code != 200:
        print(f"Error al obtener lista del clan: {response.status_code}")
        return
        
    datos_clan = response.json()
    # Crear un diccionario rápido de la API
    miembros_api = {m['tag']: m for m in datos_clan.get('memberList', [])}
    
    mapa_rangos = {
        'leader': 'Líder',
        'coLeader': 'Colíder',
        'admin': 'Veterano',
        'member': 'Miembro'
    }
    
    worksheet_db = gc.open_by_key(SHEET_ID).worksheet("DB_Miembros")
    datos_db = worksheet_db.get_all_values()
    
    if not datos_db:
        return
        
    tags_en_db = {}
    
    # 1.1 Mapear existentes: Actualizar rangos o aplicar Soft Delete
    for i, fila in enumerate(datos_db[1:]): # Saltar el encabezado
        if not fila: continue
        
        # Rellenar columnas vacías para evitar errores de índice
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
                fila[4] = "Salió" # Soft Delete
                print(f"Baja detectada: {fila[1]} ha sido marcado como Salió.")
    
    # 1.2 Detectar Altas: Agregar miembros completamente nuevos
    for tag, jugador in miembros_api.items():
        if tag not in tags_en_db:
            nueva_fila = [
                tag,
                jugador['name'],
                mapa_rangos.get(jugador['role'], 'Miembro'),
                str(jugador['townHallLevel']),
                "Activo"
                ""
            ]
            datos_db.append(nueva_fila)
            print(f"Alta detectada: {jugador['name']} agregado a la base de datos.")
            
    # 1.3 Inyectar actualización masiva a la DB
    worksheet_db.update(values=datos_db, range_name=f"A1:F{len(datos_db)}")
    print("¡Base de datos actualizada con éxito!")

def actualizar_asaltos():
    """Flujo principal del script ETL"""
    headers = {
        "Authorization": f"Bearer {COC_TOKEN}",
        "Accept": "application/json"
    }
    
    try:
        gc = obtener_cliente_sheets()
    except Exception as e:
        print(f"Error crítico al conectar con Google Sheets: {e}")
        return
        
    # Fase 1: Auditar y emparejar la base de datos
    sincronizar_miembros(gc, headers)
    
    # Pausa de ingeniería: Google Sheets tarda ~2 segundos en recalcular 
    # las fórmulas FILTER después de que inyectamos los nuevos miembros.
    print("Esperando 3 segundos para el recálculo de fórmulas de Sheets...")
    time.sleep(3)
    
    # Fase 2: Sincronizar Asaltos
    print("2. Iniciando extracción de datos de Asaltos de la Capital...")
    url_raids = f"https://cocproxy.royaleapi.dev/v1/clans/{CLAN_TAG}/capitalraidseasons"
    response = requests.get(url_raids, headers=headers)
    
    if response.status_code != 200:
        print(f"Error en API de Asaltos: {response.status_code}")
        return
        
    data = response.json()
    latest_season = data['items'][0]
    
    raid_stats = {}
    for member in latest_season.get('members', []):
        raid_stats[member['tag']] = {
            'ataques': member['attacks'],
            'oro': member['capitalResourcesLooted']
        }
        
    sheet = gc.open_by_key(SHEET_ID)
    worksheet_asaltos = sheet.worksheet("Asaltos_Capital")
    
    # Extraer la lista dinámica generada por el FILTER (Alineación perfecta)
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
        print(f"¡Éxito! Asaltos actualizados en el rango {rango}.")

if __name__ == "__main__":
    actualizar_asaltos()