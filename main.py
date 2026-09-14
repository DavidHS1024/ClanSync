import os
import time
import requests
import gspread
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

COC_TOKEN = os.getenv("COC_TOKEN")
SHEET_ID = os.getenv("SHEET_ID")
CLAN_TAG = os.getenv("CLAN_TAG")

# La API de Supercell requiere que el '#' del tag sea codificado como '%23' en la URL
if CLAN_TAG.startswith("#"):
    CLAN_TAG = CLAN_TAG.replace("#", "%23")
else:
    CLAN_TAG = "%23" + CLAN_TAG

def actualizar_asaltos():
    print("Iniciando la extracción de datos de Asaltos de la Capital...")
    
    # 1. Obtener datos de la API de Clash of Clans (usando RoyaleAPI Proxy)
    url = f"https://cocproxy.royaleapi.dev/v1/clans/{CLAN_TAG}/capitalraidseasons"
    headers = {
        "Authorization": f"Bearer {COC_TOKEN}",
        "Accept": "application/json"
    }
    
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"Error al conectar con la API: {response.status_code} - {response.text}")
        return
        
    data = response.json()
    
    # El índice 0 siempre contiene el fin de semana de asaltos más reciente
    latest_season = data['items'][0]
    members = latest_season.get('members', [])
    
    # Crear un diccionario para buscar rápidamente los aportes por Tag ID
    raid_stats = {}
    for member in members:
        raid_stats[member['tag']] = {
            'ataques': member['attacks'],
            'oro': member['capitalResourcesLooted']
        }
        
    print(f"Datos obtenidos. {len(raid_stats)} miembros participaron en el asalto.")

    # 2. Conectar a Google Sheets y preparar la inyección
    print("Conectando a Google Sheets...")
    import json
    try:
        google_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
        if google_json:
            # Entorno de producción (Railway)
            creds_dict = json.loads(google_json)
            gc = gspread.service_account_from_dict(creds_dict)
        else:
            # Entorno local (tu PC)
            gc = gspread.service_account(filename="google_credentials.json")
            
        sheet = gc.open_by_key(SHEET_ID)
        worksheet = sheet.worksheet("Asaltos_Capital")
    except Exception as e:
        print(f"Error al conectar con Google Sheets: {e}")
        return

    # Extraer todos los Tag IDs que tu fórmula de filtro generó en la columna A
    tags_en_hoja = worksheet.col_values(1)
    
    # Construir la matriz de datos para las columnas C (Ataques) y D (Oro)
    nuevos_datos = []
    
    # Iteramos desde el índice 1 para saltar la fila del encabezado ('Tag ID')
    for tag in tags_en_hoja[1:]:
        if tag in raid_stats:
            ataques = raid_stats[tag]['ataques']
            oro = raid_stats[tag]['oro']
            nuevos_datos.append([ataques, oro])
        else:
            # Si el miembro está en tu BD pero no atacó, registramos ceros
            nuevos_datos.append([0, 0])
            
    # 3. Inyectar los datos en bloque para evitar el límite de peticiones de Google
    if nuevos_datos:
        # Definimos el rango exacto, ej: C2:D51
        rango = f"C2:D{len(tags_en_hoja)}"
        worksheet.update(values=nuevos_datos, range_name=rango)
        print(f"¡Éxito! Se actualizaron {len(nuevos_datos)} filas en el rango {rango}.")
    else:
        print("No se generaron datos para actualizar.")

if __name__ == "__main__":
    actualizar_asaltos()