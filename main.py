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
    """Módulo 3: Actualiza Guerra con Historial Dinámico"""
    print("\n--- 3. Sincronizando Guerra Actual ---")
    url = f"https://cocproxy.royaleapi.dev/v1/clans/{CLAN_TAG}/currentwar"
    response = requests.get(url, headers=headers)
    
    if response.status_code != 200: 
        return
        
    data = response.json()
    estado = data.get('state', 'notInWar')
    
    # 1. EVITAR BORRAR EN PREPARACIÓN
    if estado in ['notInWar', 'preparation']:
        print(f"Estado: {estado}. Congelando historial (No hay ataques nuevos).")
        return
        
    # Generar Identificador Único (Fecha de término, ej: "20260920T1530")
    end_time_raw = data.get('endTime', 'Desconocido')
    war_id = f"Fin:{end_time_raw[:13]}" 
    
    worksheet_guerra = gc.open_by_key(SHEET_ID).worksheet("Guerra_Actual")
    all_data = worksheet_guerra.get_all_values()
    
    if len(all_data) < 2: return
        
    headers_hoja = all_data[0]
    
    # Verificar si es una guerra nueva comparando la celda C1
    es_guerra_nueva = False
    if len(headers_hoja) < 3 or war_id not in headers_hoja[2]:
        es_guerra_nueva = True
        
    miembros_guerra = {m['tag']: m for m in data.get('clan', {}).get('members', [])}
    nuevos_datos_cde = []
    
    # 2. PROCESAR DATOS CON ALINEACIÓN PERFECTA (Mapeo 1:1 con las filas)
    for i in range(1, len(all_data)):
        tag = all_data[i][0]
        if not tag:
            nuevos_datos_cde.append(["", "", ""])
            continue
            
        if tag in miembros_guerra:
            ataques_lista = miembros_guerra[tag].get('attacks', [])
            ataques = len(ataques_lista)
            estrellas = sum(atk['stars'] for atk in ataques_lista)
            destr = sum(atk['destructionPercentage'] for atk in ataques_lista)
            nuevos_datos_cde.append([ataques, estrellas, destr])
        else:
            # Jugador en la BD pero no participa en esta guerra
            nuevos_datos_cde.append(["-", "-", "-"])
            
    # Encabezados con salto de línea para que se vea elegante en Sheets
    encabezados_cde = [[f"Ataques\n{war_id}", f"Estrellas\n{war_id}", f"Destr.\n{war_id}"]]
    
    # 3. EL DESPLAZAMIENTO HORIZONTAL (Historial)
    if es_guerra_nueva:
        print(f"Nueva guerra detectada ({war_id}). Empujando historial a la derecha...")
        matriz_actualizada = []
        
        # Juntar nuevos encabezados con los antiguos
        encabezados_historicos = headers_hoja[2:] if len(headers_hoja) > 2 else []
        matriz_actualizada.append(encabezados_cde[0] + encabezados_historicos)
        
        # Juntar nuevos datos con los datos históricos fila por fila
        for i, nueva_fila_cde in enumerate(nuevos_datos_cde):
            fila_historica = all_data[i+1][2:] if len(all_data[i+1]) > 2 else []
            matriz_actualizada.append(nueva_fila_cde + fila_historica)
            
        # Inyectar toda la matriz masiva empezando desde C1
        worksheet_guerra.update(values=matriz_actualizada, range_name="C1")
    else:
        print("Día de batalla en curso. Actualizando ataques...")
        # Si es la misma guerra, solo sobreescribimos C, D y E para no saturar internet
        worksheet_guerra.update(values=nuevos_datos_cde, range_name=f"C2:E{len(nuevos_datos_cde)+1}")
        
    print("¡Historial de guerra sincronizado!")

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