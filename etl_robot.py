import pandas as pd
import hashlib
import os
import shutil
import time
import ftplib
import io
from datetime import datetime
from supabase import create_client, Client
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

# LECTURA NATIVA DE SECRETOS BASE (Solo para acceder a Supabase)
import os
import toml

dir_base = os.path.dirname(os.path.abspath(__file__))
ruta_secretos = os.path.join(dir_base, ".streamlit", "secrets.toml")

try:
    with open(ruta_secretos, "r", encoding="utf-8") as f:
        SECRETS = toml.load(f)
except Exception as e:
    print(f"⚠️ Error fatal leyendo la bóveda secreta base: {e}")
    SECRETS = {}

# Soportar tanto formato plano como formato anidado bajo [default]
def_sec = SECRETS.get("default", {})
SUPABASE_URL = SECRETS.get("SUPABASE_URL", def_sec.get("SUPABASE_URL", "https://ewwdsiewmdwbxoiguoas.supabase.co"))
SUPABASE_KEY = SECRETS.get("SUPABASE_KEY", def_sec.get("SUPABASE_KEY", "CLAVE_OCULTA"))

print("🔌 Conectando a Supabase (Bóveda Central)...")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

print("📡 Consultando Directivas Estratégicas (DB Configuracion)...")
try:
    resp_conf = supabase.table("configuracion").select("*").eq("id", 1).execute()
    db_conf = resp_conf.data[0] if resp_conf.data else {}
except Exception as e:
    print(f"🚨 Error crítico leyendo la tabla 'configuracion': {e}")
    db_conf = {}

# ==========================================
# ⚙️ MODO DE EJECUCIÓN DEL ROBOT
# ==========================================
MODO_EJECUCION = str(db_conf.get("etl_modo", "LOCAL")).strip().upper()
print(f"🤖 Despertando ETL Robot (Modo Dinámico: {MODO_EJECUCION})...")

# ==========================================
# ⚙️ CONFIGURACIÓN GOOGLE DRIVE
# ==========================================
DRIVE_CREDENTIALS_FILE = "secret_key.json"
DRIVE_CARPETA_ORIGEN_ID = str(db_conf.get("drive_origen", "")).strip()
DRIVE_CARPETA_DESTINO_ID = str(db_conf.get("drive_destino", "")).strip()

# ==========================================
# ⚙️ CONFIGURACIÓN FTP / SFTP
# ==========================================
FTP_HOST = str(db_conf.get("ftp_host", "")).strip()
FTP_USER = str(db_conf.get("ftp_user", "")).strip()
FTP_PASS = str(db_conf.get("ftp_pass", "")).strip()
FTP_DIR_ORIGEN = str(db_conf.get("ftp_origen", "/pendientes/")).strip()
FTP_DIR_DESTINO = str(db_conf.get("ftp_destino", "/procesados/")).strip()

# Carpetas Temporales de Prueba (El robot siempre trabaja en RAM/Disco Local)
DIR_PENDIENTES = "temp_pendientes/"
DIR_PROCESADOS = "temp_procesados/"

os.makedirs(DIR_PENDIENTES, exist_ok=True)
os.makedirs(DIR_PROCESADOS, exist_ok=True)

# Helper igual al del sistema original
MESES_ORDEN = ["ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO", "JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE"]
MESES_MAP = {i+1: m for i, m in enumerate(MESES_ORDEN)}

def normalize_id_col(val):
    s = str(val).strip().upper()
    if s.endswith('.0'): s = s[:-2]
    if s in ['NAN', 'NAT', 'NONE', '']: return 'S/D'
    return s

def procesar_archivos():
    archivos_pendientes = [f for f in os.listdir(DIR_PENDIENTES) if f.lower().endswith(('.xlsx', '.xls', '.csv'))]
    
    if not archivos_pendientes:
        print("💤 No hay archivos nuevos descargados en la carpeta 'temp_pendientes/'. El robot no tiene nada que procesar.")
        return False, []

    print(f"🚀 Iniciando absorción de {len(archivos_pendientes)} archivos...")
    df_totales = []

    for archivo in archivos_pendientes:
        ruta_completa = os.path.join(DIR_PENDIENTES, archivo)
        print(f"📄 Leyendo: {archivo}...")
        
        try:
            if archivo.endswith('.csv'):
                df = pd.read_csv(ruta_completa, encoding='latin-1')
            else:
                df = pd.read_excel(ruta_completa, engine='openpyxl')
            
            # Estandarización de columnas
            df.columns = df.columns.astype(str).str.strip().str.lower()
            df = df.rename(columns={
                'importe': 'venta_total', 'total': 'venta_total', 'ventas': 'venta_total',
                'nnumero': 'numero', 'cantidad': 'volumen', 'ult_provee': 'proveedor', 'cod_bande': 'bandera'
            })
            df = df.loc[:, ~df.columns.duplicated()]

            # Columnas Requeridas de Textos
            text_cols = [
                'numero', 'codigo', 'detalle', 'formulario', 'fecha', 'cliente', 'condicion', 'nom_condi', 'codigocom', 
                'nombre', 'localidad', 'provincia', 'canal', 'categoria', 'canal_com', 'cod_activ', 'cod_canal', 
                'color', 'est_comerc', 'km', 'ramo', 'reventa', 'rubro', 'subrubro', 'tipo_comb', 'subti_comb', 
                'domicilio', 'c_postal', 'proveedor', 'bandera'
            ]
            for c in text_cols:
                if c not in df.columns: 
                    df[c] = "S/D"
                else:
                    df[c] = df[c].fillna("S/D").astype(str)

            # Normalización Estricta
            for c in ['formulario', 'numero', 'codigo', 'nombre']:
                if c in df.columns: df[c] = df[c].apply(normalize_id_col)

            # Matemáticas Financieras Seguras
            df["volumen"] = pd.to_numeric(df.get("volumen", 0), errors='coerce').fillna(0)
            df["precio"] = pd.to_numeric(df.get("precio", 0), errors='coerce').fillna(0)
            df["venta_total"] = pd.to_numeric(df.get("venta_total", df["precio"] * df["volumen"]), errors='coerce').fillna(df["precio"] * df["volumen"])

                        # Manejo de Fechas Indestructible para el Robot
            if 'fecha' in df.columns:
                # 1. Separamos los que son números puros de excel (ej. 45012)
                numericos = pd.to_numeric(df['fecha'].astype(str), errors='coerce')
                mask_num = numericos.notna() & (numericos > 30000)
                
                # 2. Asumimos lo normal (ya es fecha o es texto 'YYYY-MM-DD')
                fechas = pd.to_datetime(df['fecha'], errors='coerce') 
                
                # 3. Forzamos formato 1899 SOLO a los que eran números raros de Excel
                if mask_num.any():
                    fechas[mask_num] = pd.to_datetime(numericos[mask_num], unit='D', origin='1899-12-30', errors='coerce')
                
                # Guardamos las derivadas
                df['fecha_dt'] = fechas.dt.strftime('%Y-%m-%d')
                df['anio'] = fechas.dt.year.fillna(0).astype(int)
                df['mes'] = fechas.dt.month.fillna(0).astype(int).map(MESES_MAP).fillna("S/D")
            else:
                df['fecha_dt'] = "2000-01-01"
                df['anio'] = 0
                df['mes'] = "S/D"


            # HASHING ID ÚNICO (Regla de Oro JL)
            df['debug_str'] = df.apply(lambda r: f"{str(r.get('fecha_dt'))[:10]}_{str(r.get('formulario'))}_{str(r.get('numero'))}_{str(r.get('codigo'))}_{str(r.get('nombre'))}", axis=1)
            df['id_unique'] = df['debug_str'].apply(lambda x: hashlib.md5(x.encode()).hexdigest())
            
            df_totales.append(df)
            
        except Exception as e:
            print(f"❌ Error leyendo el archivo {archivo}: {e}")

    if not df_totales:
        return False, []

    # Fusión Maestra y Deduplicación en Memoria RAM
    print("🧠 Fusionando datos y limpiando duplicados temporales...")
    df_master = pd.concat(df_totales, ignore_index=True)
    df_master = df_master.drop_duplicates(subset=['id_unique'], keep='last')
    
    # Preparamos el Payload para la base de datos (Solo las columnas que existen en Supabase)
    cols_validas = [
        'id_unique', 'fecha_dt', 'anio', 'mes', 'precio', 'volumen', 'venta_total',
        'numero', 'codigo', 'detalle', 'formulario', 'fecha', 'cliente', 'condicion', 'nom_condi', 'codigocom', 
        'nombre', 'localidad', 'provincia', 'canal', 'categoria', 'canal_com', 'cod_activ', 'cod_canal', 
        'color', 'est_comerc', 'km', 'ramo', 'reventa', 'rubro', 'subrubro', 'tipo_comb', 'subti_comb', 
        'domicilio', 'c_postal', 'proveedor', 'bandera'
    ]
    
    df_upload = df_master[[c for c in cols_validas if c in df_master.columns]].copy()
    
    # Convertimos los NaN/NaT a None para que la base de datos PostgreSQL no tire error
    df_upload = df_upload.where(pd.notnull(df_upload), None)
    payload = df_upload.to_dict(orient='records')
    
    print(f"☁️ Disparando Upsert directo a Bóveda Supabase ({len(payload)} registros únicos detectados)...")
    
    try:
        # Aquí ocurre la magia: inserta si no existe, ignora si ya existe
        response = supabase.table('despachos_inercia').upsert(payload, on_conflict='id_unique').execute()
        print("✅ ¡Inyección de datos exitosa!")
        
        # Si todo salió bien, movemos los archivos leídos a la papelera/procesados locales
        for archivo in archivos_pendientes:
            ruta_origen = os.path.join(DIR_PENDIENTES, archivo)
            ruta_destino = os.path.join(DIR_PROCESADOS, archivo)
            shutil.move(ruta_origen, ruta_destino)
            print(f"📦 Archivo local {archivo} movido a 'temp_procesados/'")
            
        return True, archivos_pendientes
            
    except Exception as e:
        print(f"🚨 Falla Crítica escribiendo en la base de datos: {e}")
        return False, []

# ==========================================
# 📡 CONECTORES (LAS MANGUERAS DE DATOS)
# ==========================================

def get_drive_service():
    scopes = ['https://www.googleapis.com/auth/drive']
    creds = service_account.Credentials.from_service_account_file(DRIVE_CREDENTIALS_FILE, scopes=scopes)
    return build('drive', 'v3', credentials=creds)

def extraer_de_drive():
    try:
        drive_service = get_drive_service()
        # Buscar archivos en la carpeta de pendientes
        query = f"'{DRIVE_CARPETA_ORIGEN_ID}' in parents and trashed = false"
        results = drive_service.files().list(q=query, fields="nextPageToken, files(id, name)").execute()
        items = results.get('files', [])

        if not items:
            print("☁️ No se encontraron archivos nuevos en Google Drive.")
            return []

        print(f"☁️ Se encontraron {len(items)} archivos en Google Drive. Descargando...")
        archivos_descargados = []

        for item in items:
            request = drive_service.files().get_media(fileId=item['id'])
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
            
            # Guardar localmente
            ruta_local = os.path.join(DIR_PENDIENTES, item['name'])
            with open(ruta_local, 'wb') as f:
                f.write(fh.getvalue())
            archivos_descargados.append({"id": item['id'], "name": item['name']})
            print(f"   ⬇️ {item['name']} descargado exitosamente.")
            
        return archivos_descargados
    except Exception as e:
        print(f"🚨 Error conectando/descargando de Google Drive: {e}")
        return []

def mover_en_drive(archivos_drive):
    try:
        drive_service = get_drive_service()
        for archivo in archivos_drive:
            # Obtener el archivo para saber sus padres actuales
            file = drive_service.files().get(fileId=archivo['id'], fields='parents').execute()
            previous_parents = ",".join(file.get('parents'))
            
            # Mover a procesados
            drive_service.files().update(
                fileId=archivo['id'],
                addParents=DRIVE_CARPETA_DESTINO_ID,
                removeParents=previous_parents,
                fields='id, parents'
            ).execute()
            print(f"   🚚 D-Mover: {archivo['name']} movido a Procesados en Drive.")
    except Exception as e:
        print(f"🚨 Error moviendo archivos en Drive: {e}")

def extraer_de_ftp():
    try:
        print(f"🌐 Conectando al servidor FTP {FTP_HOST}...")
        ftp = ftplib.FTP(FTP_HOST)
        ftp.login(FTP_USER, FTP_PASS)
        ftp.cwd(FTP_DIR_ORIGEN)
        
        archivos = ftp.nlst()
        archivos_descargados = []
        
        for arch in archivos:
            if arch.lower().endswith(('.csv', '.xlsx', '.xls')):
                ruta_local = os.path.join(DIR_PENDIENTES, arch)
                with open(ruta_local, 'wb') as fb:
                    ftp.retrbinary(f'RETR {arch}', fb.write)
                archivos_descargados.append(arch)
                print(f"   ⬇️ {arch} descargado desde FTP.")
                
        ftp.quit()
        return archivos_descargados
    except Exception as e:
        print(f"🚨 Error conectando/descargando del FTP: {e}")
        return []

def borrar_de_ftp(archivos_ftp):
    try:
        ftp = ftplib.FTP(FTP_HOST)
        ftp.login(FTP_USER, FTP_PASS)
        for arch in archivos_ftp:
            # Opción: Borrar el archivo directamente u operarlo (renombrar)
            try:
                # Opcional: moverlo usando rename si hay carpeta procesados:
                ftp.rename(f"{FTP_DIR_ORIGEN}{arch}", f"{FTP_DIR_DESTINO}{arch}")
                print(f"   🚚 F-Mover: {arch} movido a {FTP_DIR_DESTINO} en servidor FTP.")
            except:
                ftp.delete(f"{FTP_DIR_ORIGEN}{arch}")
                print(f"   🗑️ F-Borrar: {arch} eliminado del servidor FTP de origen.")
        ftp.quit()
    except Exception as e:
        print(f"🚨 Error moviendo/borrando en FTP: {e}")

# ==========================================
# 🚀 EJECUCIÓN DEL FLUJO MAESTRO
# ==========================================

if __name__ == "__main__":
    print(f"🤖 Despertando ETL Robot (Modo: {MODO_EJECUCION})...")
    
    archivos_nube = []
    
    # 1. Extracción (EL)
    if MODO_EJECUCION == 'DRIVE':
        archivos_nube = extraer_de_drive()
    elif MODO_EJECUCION == 'FTP':
        archivos_nube = extraer_de_ftp()
        
    # 2. Transformación y Carga (TL)
    exito, procesados_localmente = procesar_archivos()
    
    # 3. Limpieza Remota
    if exito:
        if MODO_EJECUCION == 'DRIVE' and archivos_nube:
            print("🧽 Limpiando carpeta origen en Google Drive...")
            mover_en_drive(archivos_nube)
        elif MODO_EJECUCION == 'FTP' and archivos_nube:
            print("🧽 Limpiando carpeta origen en el servidor FTP...")
            # En FTP la variable iteraba nombres de strings
            borrar_de_ftp(archivos_nube)
            
    print("🏁 Procedimiento nocturno finalizado.")