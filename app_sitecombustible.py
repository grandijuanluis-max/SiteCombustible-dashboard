import streamlit as st
import pandas as pd
import folium
from folium.plugins import HeatMap
from streamlit_folium import folium_static, st_folium
import plotly.express as px
import plotly.graph_objects as go
import os
import json
import time
import hashlib
import gspread
import traceback
from google.oauth2.service_account import Credentials
from geopy.geocoders import Nominatim
from fpdf import FPDF
from datetime import datetime, date, timedelta

# ==========================================
# 📑 MOTOR DE EXPORTACIÓN CORPORATIVA (HELPER FUNCTIONS)
# ==========================================
import io

def generar_excel_corporativo(df_export, formato='xlsx'):
    output = io.BytesIO()
    if formato == 'xlsx' or formato == 'xls':
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_export.to_excel(writer, index=False, sheet_name='Datos_Inercia')
    else:
        df_export.to_csv(output, index=False)
    return output.getvalue()

def generar_pdf_corporativo(df_export, titulo_reporte, filtros_texto, modo="Completo"):
    pdf = FPDF()
    pdf.add_page()
    # --- Encabezado Institucional ---
    pdf.set_font("Arial", "B", 16)
    pdf.set_text_color(30, 58, 138) # Azul Corporativo
    pdf.cell(0, 10, "JUAN LUIS CORPORATIONS - SITECOMBUSTIBLE PRO", ln=True, align="C")
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, titulo_reporte.upper(), ln=True, align="C")
    pdf.line(10, 32, 200, 32)
    pdf.ln(5)

    # --- Subtítulo y Filtros (Izquierda) ---
    pdf.set_font("Arial", "B", 9)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 5, "FILTROS APLICADOS EN ORIGEN:", ln=True)
    pdf.set_font("Arial", "", 8)
    pdf.multi_cell(0, 5, filtros_texto)
    pdf.ln(5)

    if modo == "Completo":
        pdf.set_font("Arial", "I", 9)
        pdf.cell(0, 10, "(Gráfico visualizado en Dashboard - Reporte de Tabla Resumen)", ln=True)
    
    # --- Tabla de Datos ---
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font("Arial", "B", 8)
    pdf.set_text_color(0)
    
    cols = df_export.columns
    col_width = 190 / len(cols)
    for col in cols:
        pdf.cell(col_width, 8, str(col).upper(), 1, 0, 'C', True)
    pdf.ln()

    pdf.set_font("Arial", "", 8)
    for _, row in df_export.iterrows():
        for val in row:
            pdf.cell(col_width, 7, str(val), 1, 0, 'C')
        pdf.ln()

    # --- Pie de Página (Trazabilidad) ---
    pdf.set_y(-25)
    pdf.line(10, 270, 200, 270)
    pdf.set_font("Arial", "I", 7)
    now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    pdf.cell(0, 10, f"Emitido por: SiteCombustible Pro System | Usuario: Juan Luis Corporations | Emisión: {now}", align="L")
    pdf.cell(0, 10, f"Página {pdf.page_no()}", align="R")
    
    return pdf.output(dest='S').encode('latin-1')
    
# ==========================================
# ⚙️ CONFIGURACIÓN Y ESTILO CORPORATIVO
# ==========================================
st.set_page_config(page_title="SiteCombustible Pro - Juan Luis Corporations", page_icon="📊", layout="wide")

import base64
from pathlib import Path

def get_base64_of_bin_file(bin_file):
    with open(bin_file, 'rb') as f:
        data = f.read()
    return base64.b64encode(data).decode()

# Enrutar a la foto de Juan Luis (fondo.png). Si falta, usar Refinería de Unsplash como fallback.
local_img = "fondo.png"
if Path(local_img).exists():
    img_b64 = get_base64_of_bin_file(local_img)
    bg_img_str = f'url("data:image/png;base64,{img_b64}")'
else:
    bg_img_str = 'url("https://images.unsplash.com/photo-1518709268805-4e9042af9f23?q=80&w=2500")'

st.markdown(f"""
        <style>
        /* FONDO NIVEL DIOS ULTRA HD - CAPA BASE INQUEBRANTABLE (REFINERIA DE ORO NEGRO) */
        [data-testid="stAppViewContainer"],
        [data-testid="stFullScreenFrame"] {{
            background: linear-gradient(rgba(15, 23, 42, 0.40), rgba(15, 23, 42, 0.40)), {bg_img_str} no-repeat center center fixed !important;
            background-size: cover !important;
        }}
        
        /* HEADER TOTALMENTE INVISIBLE PARA NO ROMPER LA MAGIA */
        [data-testid="stHeader"] {{
            background-color: transparent !important;
        }}
        
        /* SIDEBAR DE CRISTAL OSCURO PERO MUY TRANSPARENTE */
        [data-testid="stSidebar"] {{
            background-color: rgba(15, 23, 42, 0.40) !important;
            backdrop-filter: blur(25px) !important;
            border-right: 1px solid rgba(255, 255, 255, 0.08) !important;
        }}
        
        /* CONTENT CENTRAL - GLASSMORPHISM SUPREMO (NEGRO AZULADO MUY TRANSPARENTE) */
        .main .block-container {{
            background-color: rgba(15, 23, 42, 0.45) !important;
            padding: 3rem !important;
            border-radius: 24px !important;
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.9) !important;
            backdrop-filter: blur(20px) !important;
            -webkit-backdrop-filter: blur(20px) !important;
            border: 1px solid rgba(255, 255, 255, 0.10) !important;
            margin-top: 1rem !important;
            margin-bottom: 2rem !important;
            color: #ffffff !important;
        }}
        
        /* TIPOGRAFÍA FUTURISTA / LIMPIA */
        .stApp, .block-container {{
            font-family: 'Inter', sans-serif;
            color: #ffffff;
        }}
        
        /* SIDEBAR Y NAVEGACIÓN - ALTO CONTRASTE */
        /* Asegurar lectura nítida de los radios y subtítulos que Streamlit oscurece por defecto */
        [data-testid="stSidebarNav"] *,
        [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] p,
        [data-testid="stSidebar"] h1,
        [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] h3 {{
            color: #ffffff !important;
            font-weight: 500 !important;
        }}
        

        

        /* ALERTAS (ST.INFO / ST.SUCCESS) Y BOTONES */
        [data-testid="stAlert"] * {{
            color: #ffffff !important;
            font-weight: 600 !important;
            text-shadow: 0px 1px 3px rgba(0,0,0,0.9) !important; /* Fuerza de lectura extrema */
        }}
        button[kind="primary"] {{
            background-color: rgba(255, 75, 75, 0.5) !important; /* Rojo puro pero translúcido (Glassmorphism) */
            border: 1px solid rgba(255, 255, 255, 0.25) !important;
            color: #ffffff !important;
        }}
        button[kind="primary"]:hover {{
            background-color: rgba(255, 75, 75, 0.8) !important;
            border: 1px solid rgba(255, 255, 255, 0.6) !important;
        }}
        button[kind="secondary"] {{
            background-color: rgba(15, 23, 42, 0.6) !important; /* Apagar el blanco quemado por defecto */
            border: 1px solid rgba(255, 255, 255, 0.3) !important;
            color: #ffffff !important;
        }}
        button[kind="secondary"]:hover {{
            background-color: rgba(15, 23, 42, 0.9) !important;
            border: 1px solid rgba(255, 255, 255, 0.6) !important;
            color: #ffffff !important;
        }}
        
        /* ETIQUETAS DE SELECTBOX Y RADIO BUTTONS: BLANCO EXTREMO PARA MAXIMA DESTAQUE */
        [data-testid="stRadio"] label p, 
        [data-testid="stSelectbox"] label p,
        div[role="radiogroup"] label div {{
            color: #ffffff !important;
            font-weight: 600 !important;
            text-shadow: 0px 1px 3px rgba(0,0,0,0.9) !important;
        }}
        
        /* EXPANDERS (MANTENER TRANSPARENCIA AL BRIRLOS Y NO PONERSE BLANCOS) */
        [data-testid="stExpander"] details, 
        [data-testid="stExpander"] summary {{
            background-color: rgba(15, 23, 42, 0.2) !important;
            border-radius: 8px !important;
            color: #ffffff !important;
        }}
        [data-testid="stExpander"] {{
            border: 1px solid rgba(255,255,255, 0.15) !important;
            background-color: transparent !important;
        }}
        div[data-testid="stExpanderDetails"] {{
            background-color: transparent !important;
        }}
        
        /* RESTAURACIÓN DEL MOTOR DE ÍCONOS DE STREAMLIT (MATERIAL SYMBOLS) */
        /* Al forzar 'Inter', rompimos las flechas del menú y los expanders. Esto lo repara: */
        span[class*="material-symbols-rounded"], 
        .stIcon, 
        i[class*="icon"],
        [class*="streamlit-expander-icon"] {{
            font-family: 'Material Symbols Rounded', 'Material Icons' !important;
            font-style: normal !important;
            font-variant: normal !important;
            text-transform: none !important;
            line-height: 1 !important;
        }}
        
        /* CORREGIR CONTRASTE DE LOS DESPLEGABLES (MULTISELECTS, SELECTBOXES) */
        div[data-baseweb="select"] > div {{
            background-color: #f8fafc !important; /* Fondo claro de la barra de busqueda */
            color: #0f172a !important;
        }}
        div[data-baseweb="select"] * {{
            color: #0f172a !important; /* Texto oscuro cuando escribimos */
        }}
        div[data-baseweb="popover"] * {{
            color: #0f172a !important; /* Fuerza Oscuro a TODA la lista interior (ej. CHACO) */
            font-weight: 600 !important;
        }}
        div[data-baseweb="menu"], div[data-baseweb="popover"] {{
            background-color: #f8fafc !important; /* Fondo claro de la lista desplegada */
        }}
        
        /* Píldoras elegidas en múltiple selección */
        span[data-baseweb="tag"] {{
            background-color: #1e3a8a !important;
        }}
        span[data-baseweb="tag"] * {{
            color: #ffffff !important; /* Fuerza el blanco de vuelta DENTRO de la píldora azul */
        }}
        
        footer {{visibility: hidden;}}
        </style>
    """, unsafe_allow_html=True)

MESES_ORDEN = ["ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO", "JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE"]
MESES_MAP = {i+1: m for i, m in enumerate(MESES_ORDEN)}

def robust_date_parse(serie_fechas):
    is_num = pd.to_numeric(serie_fechas, errors='coerce')
    # Protegido estrictamente contra OutOfBoundsDatetime (Pandas crashea de raíz con values > 80000 o muy ridículos al calcular desde 1899)
    mask_excel = is_num.notna() & (is_num > 30000) & (is_num < 80000)
    
    fechas_dt = pd.Series(pd.NaT, index=serie_fechas.index, dtype='datetime64[ns]')
    if mask_excel.any():
        # Forzar un errors='coerce' extra para seguridad absoluta
        fechas_dt[mask_excel] = pd.to_datetime(is_num[mask_excel], unit='D', origin='1899-12-30', errors='coerce')
        
    mask_str = ~mask_excel & serie_fechas.notna()
    if mask_str.any():
        s_str = serie_fechas[mask_str].astype(str).str.strip()
        
        # 1. Blindaje ISO 8601: Evitar que Pandas voltee los meses en los strings YYYY-MM-DD bajados de Google Sheets
        fechas_iso = pd.to_datetime(s_str, format='%Y-%m-%d', errors='coerce')
        
        # 2. Las que fallaron, seguro son Excel del usuario en DD/MM/YYYY, les forzamos dayfirst
        mask_falla_iso = fechas_iso.isna()
        if mask_falla_iso.any():
            fechas_iso[mask_falla_iso] = pd.to_datetime(s_str[mask_falla_iso], errors='coerce', dayfirst=True)
            
        # 3. Fallback genérico para mutantes sin formato
        mask_todavia = fechas_iso.isna()
        if mask_todavia.any():
            fechas_iso[mask_todavia] = pd.to_datetime(s_str[mask_todavia], errors='coerce')
            
        fechas_dt[mask_str] = fechas_iso
            
    return fechas_dt

def normalize_id_col(val):
    s = str(val).strip().upper()
    if s.endswith('.0'): s = s[:-2]
    if s in ['NAN', 'NAT', 'NONE', '']: return 'S/D'
    return s

# ==========================================
# 🔐 GESTIÓN DE DATOS (HIGH PERFORMANCE)
# ==========================================
def get_gsheet_client():
    creds = Credentials.from_service_account_info(st.secrets["gsheets_creds"], 
            scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
    return gspread.authorize(creds)

from supabase import create_client, Client

@st.cache_data(show_spinner="Descargando Bóveda Central (Supabase)...")
def load_data():
    try:
        # Usar secrets de Streamlit si existen, sino usar las claves directamente
        url = st.secrets.get("SUPABASE_URL", "https://ewwdsiewmdwbxoiguoas.supabase.co")
        key = st.secrets.get("SUPABASE_KEY", "CLAVE_OCULTA_POR_SEGURIDAD")
        supabase: Client = create_client(url, key)
        
        response = supabase.table("despachos_inercia").select("*").execute()
        data_raw = response.data
        
        if not data_raw:
            df = pd.DataFrame()
        else:
            df = pd.DataFrame(data_raw)
            
        df.columns = df.columns.astype(str).str.strip().str.lower()
        
        if not df.empty:
            if 'fecha_dt' in df.columns:
                df['fecha_dt'] = pd.to_datetime(df['fecha_dt'], errors='coerce')
            elif 'fecha' in df.columns:
                df['fecha_dt'] = robust_date_parse(df['fecha'])
            else:
                df['fecha_dt'] = pd.NaT
                
            df['anio'] = df['fecha_dt'].dt.year.fillna(0).astype(int)
            df['mes'] = df['fecha_dt'].dt.month.fillna(0).astype(int).map(MESES_MAP).fillna("S/D")
            
            # Asegurar conversiones numéricas
            for col in ["volumen", "precio", "venta_total"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
                else:
                    df[col] = 0.0
            
            # Prevenir colapsos si no vienen las columnas
            for c in ['proveedor', 'localidad', 'provincia', 'formulario', 'numero', 'codigo', 'nombre', 'subti_comb', 'id_unique', 'bandera']:
                if c not in df.columns: df[c] = "S/D"
                else: df[c] = df[c].fillna("S/D")
                
            # Identidad robusta ya viene calculada desde ETL, asegurar unicidad
            if 'id_unique' in df.columns:
                df = df.drop_duplicates(subset=['id_unique'])
        else:
            # Asegurar todas las columnas requeridas para evitar KeyErrors
            df = pd.DataFrame(columns=[
                'id_unique', 'anio', 'mes', 'precio', 'volumen', 'venta_total', 'numero', 'codigo', 'detalle', 'formulario', 
                'fecha', 'cliente', 'condicion', 'codigocom', 'nombre', 'localidad', 'provincia', 'canal', 'categoria', 
                'canal_com', 'cod_activ', 'cod_canal', 'color', 'est_comerc', 'km', 'ramo', 'reventa', 'rubro', 'subrubro', 
                'tipo_comb', 'subti_comb', 'domicilio', 'c_postal', 'proveedor', 'bandera'
            ])
        return df
    except Exception as e: 
        import traceback
        st.error(f"Error mortal leyendo la base de Supabase: {e}")
        st.error(traceback.format_exc())
        return pd.DataFrame(columns=[
                'id_unique', 'anio', 'mes', 'precio', 'volumen', 'venta_total', 'numero', 'codigo', 'detalle', 'formulario', 
                'fecha', 'cliente', 'condicion', 'codigocom', 'nombre', 'localidad', 'provincia', 'canal', 'categoria', 
                'canal_com', 'cod_activ', 'cod_canal', 'color', 'est_comerc', 'km', 'ramo', 'reventa', 'rubro', 'subrubro', 
                'tipo_comb', 'subti_comb', 'domicilio', 'c_postal', 'proveedor', 'bandera'
            ])

def save_to_google_sheets(df_to_save, mode='full'):
    try:
        client = get_gsheet_client()
        sheet = client.open_by_key("1nUklyZe4ZDy4KWyz3yTT67w-gE5ysWjvzx7a0aLSrWc").sheet1
        
        # El archivo usa la nomenclatura original del excel nativamente
        df_export = df_to_save.copy()
        
        if 'fecha_dt' in df_export.columns:
            # Pedido expreso del usuario: Visualizar DD/MM/YYYY puramente en Google Sheets
            df_export['fecha'] = df_export['fecha_dt'].dt.strftime('%d/%m/%Y')
            
        headers = list(df_export.columns)
        
        df_final = df_export.copy()
        for col in headers:
            if col not in df_final.columns:
                df_final[col] = "S/D"
        df_final = df_final[headers]
        
        data_to_upload = df_final.fillna("S/D").astype(str).values.tolist()
        
        if mode == 'full':
            sheet.clear()
            data_to_upload = [headers] + data_to_upload
            sheet.append_rows(data_to_upload, value_input_option='USER_ENTERED')
        else:
            sheet.append_rows(data_to_upload, value_input_option='USER_ENTERED')
            
        return True
    except Exception as e: 
        import streamlit as st
        st.error(f"Error técnico de Base de Datos: {e}")
        return False

# --- PASARELA DE AUTENTICACION (RBAC) ---
def check_login():
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.user_perms = {}

    if not st.session_state.logged_in:
        with st.container():
            st.markdown("<br><br><h2 style='text-align: center;'>🔐 Acceso Clasificado</h2>", unsafe_allow_html=True)
            col1, col2, col3 = st.columns([1,2,1])
            with col2:
                with st.form("login_form"):
                    usr = st.text_input("Usuario o Email")
                    pwd = st.text_input("Contraseña", type="password")
                    submit = st.form_submit_button("Autorizar Conexión", type="primary", use_container_width=True)
                    
                    if submit:
                        try:
                            # Conectar a Supabase para el Login
                            url = st.secrets.get("SUPABASE_URL", "https://ewwdsiewmdwbxoiguoas.supabase.co")
                            key = st.secrets.get("SUPABASE_KEY", "CLAVE_OCULTA_POR_SEGURIDAD")
                            supabase: Client = create_client(url, key)
                            
                            response = supabase.table("usuarios").select("*").execute()
                            users_data = response.data
                            
                            found = False
                            for row in users_data:
                                # Normalización extrema: convierte todas las claves (nombres de columnas) a minúsculas sin espacios
                                r_norm = {str(k).strip().lower(): v for k, v in row.items()}
                                
                                user_val = str(r_norm.get('usuario', '')).strip().lower()
                                mail_val = str(r_norm.get('mails', r_norm.get('mail', r_norm.get('email', r_norm.get('correo', ''))))).strip().lower()
                                pwd_val = str(r_norm.get('password', r_norm.get('clave', r_norm.get('contraseña', '')))).strip()

                                if (usr.strip().lower() in [user_val, mail_val] and usr.strip() != "") and (pwd == pwd_val):
                                    found = True
                                    st.session_state.user_perms = {
                                        "ingesta": str(r_norm.get('ingesta', '')).strip().lower(),
                                        "vision": str(r_norm.get('vision', '')).strip().lower(),
                                        "inercia": str(r_norm.get('inercia', '')).strip().lower(),
                                        "mercado": str(r_norm.get('mercado', '')).strip().lower(),
                                        "copiloto": str(r_norm.get('copiloto', '')).strip().lower(),
                                        "admin": str(r_norm.get('admin', '')).strip().lower()
                                    }
                                    st.session_state.logged_in = True
                                    st.rerun()
                                    
                            if not found:
                                st.error("❌ Credenciales incorrectas o usuario inexistente.")
                                with st.expander("🛠️ Diagnóstico de Seguridad (Dev)", expanded=True):
                                    st.warning(f"Intentaste acceder con el texto exacto: '{usr}'")
                                    st.write("Tu tabla de Usuarios en Supabase dice exactamente esto:")
                                    for idx_r, r in enumerate(users_data):
                                        st.code(str(r), language="json")
                        except Exception as e:
                            st.error(f"Error conectando a la base de datos de usuarios (Supabase): {e}")
        st.stop() # CORTAFUEGOS: Bloquea la app entera si no hay login.

check_login()

# --- CARGA ---
if 'df_master' not in st.session_state:
    st.session_state.df_master = load_data()

df_master = st.session_state.df_master

# ==========================================
# 🖥️ FILTROS SIDEBAR
# ==========================================
st.sidebar.header("🕹️ Centro de Control")
if st.sidebar.button("🔄 Refrescar"): 
    st.cache_data.clear()
    st.session_state.df_master = load_data()
    st.rerun()

# Filtros Estáticos y Rango de Fechas
st.sidebar.markdown("### 📅 Filtro Temporal")

# Rango de fechas predefinido
# Anclamos "Hoy" al máximo registro real del dataset para evitar vacíos si el reloj del server está adelantado a la data.
hoy_server = date.today()
hoy = df_master['fecha_dt'].max().date() if not df_master.empty and pd.notna(df_master['fecha_dt'].max()) else hoy_server
if hoy > hoy_server: hoy = hoy_server # Cap límite
presets = ["Todo Histórico", "Hoy", "Este Mes", "Mes Anterior", "Este Año", "Personalizado"]
rango_sel = st.sidebar.selectbox("Período Rápido", presets)

fecha_inicio = None
fecha_fin = None

if rango_sel == "Hoy":
    fecha_inicio = fecha_fin = hoy
elif rango_sel == "Este Mes":
    fecha_inicio = hoy.replace(day=1)
    fecha_fin = hoy
elif rango_sel == "Mes Anterior":
    primer_dia_mes_actual = hoy.replace(day=1)
    fecha_fin = primer_dia_mes_actual - timedelta(days=1)
    fecha_inicio = fecha_fin.replace(day=1)
elif rango_sel == "Este Año":
    fecha_inicio = hoy.replace(month=1, day=1)
    fecha_fin = hoy
elif rango_sel == "Personalizado":
    # Asignamos límites min y max basados en el dataframe si es posible
    min_date = df_master['fecha_dt'].min().date() if not df_master.empty and pd.notna(df_master['fecha_dt'].min()) else hoy - timedelta(days=365)
    max_date = df_master['fecha_dt'].max().date() if not df_master.empty and pd.notna(df_master['fecha_dt'].max()) else hoy
    
    dates = st.sidebar.date_input("Seleccionar Rango", [min_date, max_date])
    if len(dates) == 2:
        fecha_inicio, fecha_fin = dates
    elif len(dates) == 1:
        fecha_inicio = fecha_fin = dates[0]

st.sidebar.markdown("---")
st.sidebar.markdown("### 🏷️ Filtros Operativos")
def get_list(col): return [] if df_master.empty or col not in df_master.columns else sorted([str(x) for x in df_master[col].unique() if pd.notna(x) and str(x) not in ["S/D", "nan"]])

sel_prov = st.sidebar.multiselect("Provincia", get_list('provincia'))
sel_loc = st.sidebar.multiselect("Localidad", get_list('localidad'))
sel_sub = st.sidebar.multiselect("Subtipo Combustible", get_list('subti_comb'))

dff = df_master.copy()

# Aplicar Filtro Temporal
if fecha_inicio and fecha_fin and not dff.empty and 'fecha_dt' in dff.columns:
    # Convertimos inicio y fin a datetime para la comparación
    start_dt = pd.to_datetime(fecha_inicio)
    end_dt = pd.to_datetime(fecha_fin) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1) # Incluir el final del día
    dff = dff[(dff['fecha_dt'] >= start_dt) & (dff['fecha_dt'] <= end_dt)]

# Aplicar Filtros Operativos
if sel_prov: dff = dff[dff['provincia'].astype(str).str.strip().str.upper().isin([str(x).strip().upper() for x in sel_prov])]
if sel_loc:  dff = dff[dff['localidad'].astype(str).str.strip().str.upper().isin([str(x).strip().upper() for x in sel_loc])]
if sel_sub:  dff = dff[dff['subti_comb'].astype(str).str.strip().str.upper().isin([str(x).strip().upper() for x in sel_sub])]

vol_tot_global = dff['volumen'].sum() if not dff.empty else 0
cli_tot_global = dff['nombre'].nunique() if not dff.empty else 0

# ==========================================
# 🏗️ ENRUTADOR PRINCIPAL (LANDING HUB)
# ==========================================
if 'app_page' not in st.session_state:
    st.session_state.app_page = "🌐 HUB PRINCIPAL"

def go_to(page):
    st.session_state.app_page = page

# Selector Visual Lateral
st.sidebar.markdown("---")
# Generación dinámica del menú basado en RBAC
perms = st.session_state.get('user_perms', {})
all_pages = ["🌐 HUB PRINCIPAL"]
if perms.get('ingesta') == 'si': all_pages.append("🚀 INGESTA & CARGA")
if perms.get('vision') == 'si': all_pages.append("🏠 VISIÓN EJECUTIVA")
if perms.get('inercia') == 'si': all_pages.append("📈 INERCIA TEMPORAL")
if perms.get('mercado') == 'si': all_pages.append("🍩 PODER DE MERCADO")
if perms.get('copiloto') == 'si': all_pages.append("🧠 COPILOTO ESTRATÉGICO")
if perms.get('admin') == 'si': all_pages.append("👥 GESTIÓN DE PERSONAL")

page_idx = all_pages.index(st.session_state.app_page) if st.session_state.app_page in all_pages else 0

selected_page = st.sidebar.radio("Navegación Nivel Dios", all_pages, index=page_idx)

# Si el usuario hace click manual en el radio, sincronizamos el state
if selected_page != st.session_state.app_page:
    st.session_state.app_page = selected_page
    st.rerun()

app_page = st.session_state.app_page

# --- TABLA DE ENRUTAMIENTO (ESTADO) ---
if app_page == "🌐 HUB PRINCIPAL":
    st.markdown("<h1 style='text-align: center; font-size: 3.5rem; color: #1e3a8a;'>⛽ SiteCombustible Neural Hub</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; font-size: 1.2rem; margin-bottom: 3rem;'>Selecciona un módulo operativo para comenzar el análisis.</p>", unsafe_allow_html=True)
    
    # Diseñamos Botoneras Gigantes Dinámicas (solo se ven los autorizados, empaquetados a la izquierda)
    modulos = []
    
    if perms.get('ingesta') == 'si':
        modulos.append({"title": "### 🚀 Ingesta de Datos\nSube los crudos y consolida el backend.", "btn": "Ir a Ingesta", "target": "🚀 INGESTA & CARGA", "style": st.info})
    if perms.get('vision') == 'si':
        modulos.append({"title": "### 🏠 Visión Ejecutiva\nKPIs resumidos, Grid y mandos.", "btn": "Ir a Visión", "target": "🏠 VISIÓN EJECUTIVA", "style": st.success})
    if perms.get('inercia') == 'si':
        modulos.append({"title": "### 📈 Inercia Temporal\nCiclos y empuje por volúmenes.", "btn": "Ir a Inercia", "target": "📈 INERCIA TEMPORAL", "style": st.warning})
    if perms.get('mercado') == 'si':
        modulos.append({"title": "### 🍩 Poder de Mercado\nDominancia Zonal, Share y Estrategia.", "btn": "Ir a Mercado", "target": "🍩 PODER DE MERCADO", "style": st.error})
    if perms.get('copiloto') == 'si':
        modulos.append({"title": "### 🧠 Copiloto Inteligente\nMotor predictivo AI y auditorías.", "btn": "Ir a Copiloto", "target": "🧠 COPILOTO ESTRATÉGICO", "style": st.info})
    if perms.get('admin') == 'si':
        modulos.append({"title": "### 👥 Gestión de Personal\nAdministrar usuarios y permisos.", "btn": "Ir a Administración", "target": "👥 GESTIÓN DE PERSONAL", "style": st.error})
        
    if not modulos:
        st.error("⚠️ Acceso Restringido: No tienes permisos asignados a ningún módulo. Contacta al administrador para que agregue un 'si' en tus columnas.")
    else:
        # Renderizamos iterando en filas de hasta 3 columnas
        for idx in range(0, len(modulos), 3):
            fila_mods = modulos[idx:idx+3]
            cols = st.columns(3)
            for i, mod in enumerate(fila_mods):
                with cols[i]:
                    mod["style"](mod["title"])
                    if st.button(mod["btn"], key=f"btn_{mod['target']}", type="primary", use_container_width=True):
                        go_to(mod["target"])
                        st.rerun()
            st.markdown("<br>", unsafe_allow_html=True)

# --- TAB 0: CARGA (CON GRISEADO DE BOTÓN) ---
if app_page == "🚀 INGESTA & CARGA":
    st.title("Ingesta SiteCombustible Pro")
    
    with st.expander("⚠️ Zona de Peligro (Admin)"):
        st.warning("El borrado manual desde Google Sheets a veces deja rastros ocultos o caché residual que contamina la base de datos (creando duplicados fantasmas con valores 'S/D'). Utiliza este botón para purgar todo y dejarla en 0 matemáticamente.")
        if st.button("💥 VACIAR BASE DE DATOS COMPLETA", type="primary"):
            with st.spinner("Purgando base de datos remota..."):
                client = get_gsheet_client()
                sheet = client.open_by_key("1nUklyZe4ZDy4KWyz3yTT67w-gE5ysWjvzx7a0aLSrWc").sheet1
                sheet.clear()
                cols = ['marca_temporal', 'id_unique', 'proveedor', 'localidad', 'provincia', 'formulario', 'numero', 'codigo', 'nombre', 'subti_comb', 'volumen', 'precio', 'venta_total', 'fecha', 'fecha_dt', 'anio', 'mes', 'bandera']
                sheet.append_row(cols)
                st.cache_data.clear()
                st.session_state.df_master = load_data()
                st.session_state.synced = False
            st.success("✅ Base de Datos aniquilada y reinstalada de cero. Sube tu archivo Excel.")
            time.sleep(2)
            st.rerun()
            
    up_file = st.file_uploader("Subir Archivo", type=["xlsx", "csv"])
    invertir_fechas = st.checkbox("🔄 Invertir Día y Mes Automáticamente (Marcar SÓLO si el archivo tomó los meses al revés, ej: Enero en vez del real Febrero)", value=False)
    
    if up_file:
        file_id = hashlib.md5(up_file.getvalue()).hexdigest()
        if "last_id" not in st.session_state or st.session_state.last_id != file_id:
            st.session_state.last_id = file_id; st.session_state.synced = False

        f_name = up_file.name.lower()
        if 'xls' in f_name: df_new = pd.read_excel(up_file, engine='openpyxl')
        else: df_new = pd.read_csv(up_file, encoding='latin-1', sep=None, engine='python', on_bad_lines='skip')
        
        df_new.columns = df_new.columns.astype(str).str.strip().str.lower()
        df_new = df_new.rename(columns={
            'importe': 'venta_total', 'total': 'venta_total', 'ventas': 'venta_total',
            'nnumero': 'numero', 'cantidad': 'volumen', 'ult_provee': 'proveedor', 'cod_bande': 'bandera'
        })
        df_new = df_new.loc[:, ~df_new.columns.duplicated()]
        
        # Blindaje: Inyección de columnas que podrían no venir en el Excel (SOLO STRING)
        for c in ['proveedor', 'localidad', 'provincia', 'formulario', 'numero', 'codigo', 'nombre', 'subti_comb', 'bandera']:
            if c not in df_new.columns: df_new[c] = "S/D"

        # Normalización Extremadamente Estricta pre-hashing para eliminar .0 rebeldes de Pandas
        for c in ['formulario', 'numero', 'codigo', 'nombre']:
            if c in df_new.columns: df_new[c] = df_new[c].apply(normalize_id_col)

        # Aseguramos columnas numéricas sin S/D de manera segura evitando Null Pointers
        if "volumen" in df_new.columns:
            df_new["volumen"] = pd.to_numeric(df_new["volumen"], errors='coerce').fillna(0)
        else:
            df_new["volumen"] = 0.0
            
        if "precio" in df_new.columns:
            df_new["precio"] = pd.to_numeric(df_new["precio"], errors='coerce').fillna(0)
        else:
            df_new["precio"] = 0.0
            
        if "venta_total" in df_new.columns:
            df_new["venta_total"] = pd.to_numeric(df_new["venta_total"], errors='coerce').fillna(df_new["precio"] * df_new["volumen"])
        else:
            df_new["venta_total"] = df_new["precio"] * df_new["volumen"]
        
        if 'fecha' in df_new.columns:
            df_new['fecha_dt'] = robust_date_parse(df_new['fecha'])
            
            if invertir_fechas:
                def swap_dm(d):
                    if pd.isnull(d): return d
                    try:
                        # Geometría inversa forzada
                        return d.replace(day=d.month, month=d.day)
                    except ValueError:
                        return d # Ignora colisiones si día es > 12 (ej 2020-01-25)
                df_new['fecha_dt'] = df_new['fecha_dt'].apply(swap_dm)
                
            df_new['anio'] = df_new['fecha_dt'].dt.year.fillna(0).astype(int)
            df_new['mes'] = df_new['fecha_dt'].dt.month.fillna(0).astype(int).map(MESES_MAP).fillna("S/D")
        
        # Identificador Único Estricto (Regla de Negocio JL: Fecha + Cliente + Producto + Formulario + NNumero)
        df_new['debug_str'] = df_new.apply(lambda r: f"{str(r.get('fecha_dt'))[:10]}_{str(r.get('formulario'))}_{str(r.get('numero'))}_{str(r.get('codigo'))}_{str(r.get('nombre'))}", axis=1)
        df_new['id_unique'] = df_new['debug_str'].apply(lambda x: hashlib.md5(x.encode()).hexdigest())
        
        # UI DIAGNOSTICO EN VIVO PARA EL USUARIO Y COMPROBACION DE GOOGLE SHEETS
        master_ids = set(df_master['id_unique']) if not df_master.empty and 'id_unique' in df_master.columns else set()
        df_new['ACCION_FUTURA'] = df_new['id_unique'].apply(lambda x: "🟢 SE ACTUALIZARÁ (Ya existe en Google Sheet)" if x in master_ids else "🟡 SE INSERTARÁ (Fila TOTALMENTE NUEVA)")
        
        bug_rows = df_new[df_new['numero'].astype(str).str.contains('1000019524', na=False)]
        if not bug_rows.empty:
            with st.expander("🚨 ESCÁNER FORENSE DEFINITIVO: Análisis del NNumero 1000019524", expanded=True):
                st.error("JL: Tienes razón. La caja verde me confunde. Si te dice 'INSERTARÁ', es porque cree que no existe. Busquemos en vivo a esta bestia directamente adentro del Google Sheets que tengo en Memoria Ram:")
                
                master_bug = df_master[df_master['numero'].astype(str).str.contains('1000019524', na=False)].copy()
                if not master_bug.empty:
                    master_bug['debug_str'] = master_bug.apply(lambda r: f"{str(r.get('fecha_dt'))[:10]}_{str(r.get('formulario'))}_{str(r.get('numero'))}_{str(r.get('codigo'))}_{str(r.get('nombre'))}", axis=1)
                
                c1, c2 = st.columns(2)
                cols_to_show = ['id_unique', 'debug_str', 'codigo', 'volumen']
                
                with c1:
                    st.warning("📥 CÓMO SE LEE EN EL EXCEL NUEVO:")
                    st.dataframe(bug_rows[[c for c in cols_to_show if c in bug_rows.columns]])
                    
                with c2:
                    st.info("☁️ CÓMO ESTÁ VIVIENDO AHORA MISMO EN GOOGLE SHEETS:")
                    if not master_bug.empty:
                        st.dataframe(master_bug[[c for c in cols_to_show if c in master_bug.columns]])
                    else:
                        st.error("🚨 ¡ATENCIÓN! La factura 1000019524 NO ESTÁ en el Google Sheets en este momento. El sistema la va a insertar por primera vez. (¿Quizás bajaste un PDF de visualización y asumiste que estaba en la base?).")

                
        # LOGICA DE UPSERT (Full Sync)
        # Combinamos la base vieja con el excel nuevo, eliminamos duplicados quedándonos con la versión del excel nuevo (last)
        df_merged = pd.concat([df_master, df_new]).drop_duplicates(subset=['id_unique'], keep='last')
        
        nuevos_reales = len(df_merged) - len(df_master)
        actualizados = len(df_new) - nuevos_reales
        
        if len(df_new) > 0:
            st.success(f"✅ Análisis completado: Se insertarán {nuevos_reales} fila(s) nueva(s) y se actualizarán {actualizados} fila(s) existente(s).")
            
            with st.expander("🕵️ Auditoría de Fechas Internas (Verificar Lectura)", expanded=True):
                st.info("Revisa esta tabla para confirmar que Pandas reconoció correctamente 'Enero' y 'Febrero'. Si ves 'NaT', el formato de Excel no es compatible con el estándar DD/MM/YYYY.")
                cols_check = [c for c in ['fecha', 'fecha_dt', 'anio', 'mes'] if c in df_new.columns]
                df_audit = df_new[cols_check].head(50).copy()
                if 'fecha_dt' in df_audit.columns: df_audit['fecha_dt'] = df_audit['fecha_dt'].dt.strftime('%d/%m/%Y')
                st.dataframe(df_audit.astype(str))
                st.dataframe(df_audit.astype(str))
            
            if len(df_master) == 0 and actualizados > 0:
                with st.expander(f"⚙️ Auditoría de Colisiones ({actualizados} Repetidas en tu Archivo)"):
                    st.warning("El motor matemático agrupó estas filas. Compara de a pares: verás que comparten EXACTAMENTE Fecha, Formulario, NNumero, Código y Nombre de Cliente. Como la regla de negocio es estricta, se conservó sólo una.")
                    dups = df_new[df_new.duplicated(subset=['id_unique'], keep=False)].sort_values('id_unique')
                    cols_dup = [c for c in ['fecha_dt', 'formulario', 'numero', 'codigo', 'nombre', 'volumen'] if c in dups.columns]
                    df_dups = dups[cols_dup].head(100).copy()
                    if 'fecha_dt' in df_dups.columns: df_dups['fecha_dt'] = df_dups['fecha_dt'].dt.strftime('%d/%m/%Y')
                    st.dataframe(df_dups.astype(str))
            
            
            label = "✅ Sincronizado (Upsert Total)" if st.session_state.synced else "🚀 Confirmar Sincronización Total (Full Sync)"
            if st.button(label, disabled=st.session_state.synced):
                with st.spinner(f"Planchando y reescribiendo la Base de Datos con {len(df_merged)} registros (tarda unos 5 seg)..."):
                    if save_to_google_sheets(df_merged, mode='full'):
                        st.session_state.synced = True; st.cache_data.clear()
                        st.session_state.df_master = load_data()
                        st.balloons(); time.sleep(1); st.rerun()
        else: st.warning("⚠️ El archivo subido está vacío.")

# --- TAB 1: DASHBOARD EJECUTIVO ---
if app_page == "🏠 VISIÓN EJECUTIVA":
    if not dff.empty:
        k1, k2, k3 = st.columns(3)
        k1.metric("Volumen Bruto (Total)", f"{vol_tot_global:,.0f}")
        k2.metric("Clientes Activos", cli_tot_global)
        k3.metric("Ventas Est. ($)", f"$ {dff['venta_total'].sum():,.0f}")
        
        st.subheader("📍 Concentración Geográfica (Mapa de Sensibilidad)")
        ag_map = dff.groupby(["localidad", "provincia"]).agg(vol=("volumen", "sum"), cli=("nombre", "nunique")).reset_index()
        def calc_score(r):
            s = ((r['vol'] / vol_tot_global) * 70) + ((r['cli'] / cli_tot_global) * 30)
            n = "Alta" if s >= 5.0 else "Media" if s >= 1.5 else "Baja"
            return s, n
        calc = ag_map.apply(calc_score, axis=1)
        ag_map['Score'], ag_map['Nivel'] = calc.apply(lambda x: x[0]), calc.apply(lambda x: x[1])

        import time
        import time
        # Diccionario In-Memory para velocidad extrema (TOP Localidades de Argentina)
        CACHE_DIRECTO_ARG = {
            "cordoba, cordoba": (-31.4167, -64.1833),
            "rosario, santa fe": (-32.9468, -60.6393),
            "mendoza, mendoza": (-32.8908, -68.8272),
            "san miguel de tucuman, tucuman": (-26.8300, -65.2038),
            "la plata, buenos aires": (-34.9214, -57.9545),
            "mar del plata, buenos aires": (-38.0004, -57.5562),
            "salta, salta": (-24.7821, -65.4232),
            "santa fe, santa fe": (-31.6215, -60.6973),
            "san juan, san juan": (-31.5375, -68.5364),
            "resistencia, chaco": (-27.4606, -58.9839),
            "neuquen, neuquen": (-38.9516, -68.0592),
            "formosa, formosa": (-26.1775, -58.1781),
            "santiago del estero, santiago del estero": (-27.7833, -64.2667),
            "corrientes, corrientes": (-27.4806, -58.8341),
            "san salvador de jujuy, jujuy": (-24.1856, -65.2979),
            "caba, ciudad autonoma de buenos aires": (-34.6037, -58.3816),
            "caba, buenos aires": (-34.6037, -58.3816),
            "bahia blanca, buenos aires": (-38.7183, -62.2663),
            "parana, entre rios": (-31.7333, -60.5333)
        }

        @st.cache_data(show_spinner=False)
        def geocode_cached(localidad, provincia):
            key = f"{localidad}, {provincia}".lower().strip()
            if key in CACHE_DIRECTO_ARG:
                return {"lat": CACHE_DIRECTO_ARG[key][0], "lon": CACHE_DIRECTO_ARG[key][1]}
            
            try:
                time.sleep(1.05) 
                geolocator = Nominatim(user_agent="sitecomb_vfinal_vmax")
                res = geolocator.geocode(f"{localidad}, {provincia}, Argentina")
                if res: return {"lat": res.latitude, "lon": res.longitude}
            except: pass
            return None

        # Expander a lo ancho de TODA la pantalla
        with st.expander("🗺️ Ver Mapa de Calor Geográfico (Motor Ultra-Rápido)", expanded=False):
            st.info("💡 Renderizado acelerado por inyección en Memoria Caché de RAM (Latencia esperada: 0.05 segundos).")
            if st.button("🚀 Renderizar Mapa Avanzado", key="btn_render_mapa"):
                with st.spinner("Levantando plano interactivo responsivo..."):
                    
                    top_locs = ag_map.sort_values("vol", ascending=False).head(35)
                    
                    m = folium.Map(location=[-35.4, -63.6], zoom_start=5, tiles='cartodbdark_matter')
                    m_data = []
                    
                    for _, r in top_locs.iterrows():
                        coords = geocode_cached(r['localidad'], r['provincia'])
                        if coords:
                            lat, lon, score = coords['lat'], coords['lon'], r['Score']
                            m_data.append([lat, lon, score])
                            
                            color_mk = "#ef4444" if score >= 5.0 else ("#eab308" if score >= 1.5 else "#3b82f6")
                            folium.CircleMarker(
                                location=[lat, lon],
                                radius=max(4, min(score * 2.5, 18)),
                                popup=f"<div style='min-width: 150px'><b>{r['localidad']} ({r['provincia']})</b><br><br>Volumen Total: <b>{r['vol']:,.0f} L</b><br>Score Riesgo/Centralidad: <b>{score:.1f}</b></div>",
                                tooltip=f"{r['localidad']}",
                                color=color_mk,
                                fill=True,
                                fill_color=color_mk,
                                fill_opacity=0.8,
                                weight=1
                            ).add_to(m)
                            
                    if m_data: 
                        HeatMap(m_data, radius=35, blur=25, min_opacity=0.4, gradient={0.2: '#0ea5e9', 0.6: '#eab308', 1.0: '#ef4444'}).add_to(m) 
                    
                    st_folium(m, use_container_width=True, height=550, returned_objects=[])
        
        st.subheader("🚦 Grilla Estratégica (Análisis de Mercado)")
        grid = ag_map.sort_values("Score", ascending=False)
        st.dataframe(grid.style.applymap(lambda v: 'background-color: #fee2e2' if v=='Alta' else ('background-color: #fef9c3' if v=='Media' else 'background-color: #dcfce7'), subset=['Nivel']), use_container_width=True)

        col_exp_grid, _ = st.columns([1, 2])
        with col_exp_grid.expander("📥 Exportar Grilla Estratégica", expanded=False):
            ex_g1, ex_g2 = st.columns(2)
            fmt_grid = ex_g1.selectbox("Formato", ["PDF", "XLSX"], key="exp_grid_fmt")
            str_fechas_g = f"{fecha_inicio} a {fecha_fin}" if fecha_inicio and fecha_fin else rango_sel
            txt_filtros_grid = f"Fechas: {str_fechas_g} | Prov: {sel_prov or 'Todas'}"
            
            if fmt_grid == "PDF":
                btn_pdf_grid = generar_pdf_corporativo(grid.head(50), "Reporte Grilla Estratégica", txt_filtros_grid, "Completo")
                st.download_button("Descargar Reporte PDF", btn_pdf_grid, "Grilla_Estrategica.pdf", "application/pdf")
            else:
                btn_xl_grid = generar_excel_corporativo(grid, "xlsx")
                st.download_button("Descargar Archivo XLSX", btn_xl_grid, "Grilla_Estrategica.xlsx")

# --- TAB 2: ANÁLISIS DE INERCIA TEMPORAL (MODIFICACIÓN QUIRÚRGICA) ---
if app_page == "📈 INERCIA TEMPORAL":
    if not dff.empty:
        st.subheader("📊 Inercia Temporal de Despacho")
        
        # Mando de granularidad sutil
        v_mode = st.radio("Escala Temporal:", ["Año", "Mes", "Semana"], horizontal=True, key="mando_temporal_v5")
        
        df_t = dff.copy().dropna(subset=['fecha_dt'])
        meses_abrev = {1:"Ene", 2:"Feb", 3:"Mar", 4:"Abr", 5:"May", 6:"Jun", 7:"Jul", 8:"Ago", 9:"Sep", 10:"Oct", 11:"Nov", 12:"Dic"}
        
        # Definir Límites Matemáticos del Espinazo Temporal (Relleno Continuo de Ceros)
        t_start = pd.to_datetime(fecha_inicio) if fecha_inicio else df_t['fecha_dt'].min()
        t_end = pd.to_datetime(fecha_fin) if fecha_fin else df_t['fecha_dt'].max()
        
        df_spine = pd.DataFrame()
        if not pd.isna(t_start) and not pd.isna(t_end):
            if v_mode == "Semana":
                spine_keys = pd.Series(pd.date_range(start=t_start, end=t_end, freq='D')).dt.to_period('W').dt.start_time.unique()
            elif v_mode == "Mes":
                spine_keys = pd.Series(pd.date_range(start=t_start, end=t_end, freq='D')).dt.to_period('M').dt.start_time.unique()
            else:
                spine_keys = list(range(t_start.year, t_end.year + 1))
            
            df_spine = pd.DataFrame({'sort_key': spine_keys})
            
            if v_mode == "Semana":
                anios = df_spine['sort_key'].dt.year
                if anios.nunique() == 1:
                    df_spine['eje_temporal'] = "S" + df_spine['sort_key'].dt.isocalendar().week.astype(str)
                else:
                    df_spine['eje_temporal'] = "S" + df_spine['sort_key'].dt.isocalendar().week.astype(str) + " '" + df_spine['sort_key'].dt.strftime("%y")
                lbl_eje = "Semana"
            elif v_mode == "Mes":
                anios = df_spine['sort_key'].dt.year
                if anios.nunique() == 1:
                    df_spine['eje_temporal'] = df_spine['sort_key'].dt.month.map(meses_abrev).astype(str)
                else:
                    df_spine['eje_temporal'] = df_spine['sort_key'].dt.month.map(meses_abrev).astype(str) + "-" + df_spine['sort_key'].dt.strftime("%y")
                lbl_eje = "Mes"
            else:
                df_spine['eje_temporal'] = df_spine['sort_key'].astype(str)
                lbl_eje = "Año"
        
        # Mapeo idéntico en el dataset real
        if v_mode == "Semana":
            df_t['sort_key'] = df_t['fecha_dt'].dt.to_period('W').dt.start_time
            if df_t['anio'].nunique() == 1: df_t['eje_temporal'] = "S" + df_t['fecha_dt'].dt.isocalendar().week.astype(str)
            else: df_t['eje_temporal'] = "S" + df_t['fecha_dt'].dt.isocalendar().week.astype(str) + " '" + df_t['fecha_dt'].dt.strftime("%y")
        elif v_mode == "Mes":
            df_t['sort_key'] = df_t['fecha_dt'].dt.to_period('M').dt.start_time
            if df_t['anio'].nunique() == 1: df_t['eje_temporal'] = df_t['fecha_dt'].dt.month.map(meses_abrev).astype(str)
            else: df_t['eje_temporal'] = df_t['fecha_dt'].dt.month.map(meses_abrev).astype(str) + "-" + df_t['fecha_dt'].dt.strftime("%y")
        else:
            df_t['sort_key'] = df_t['anio'].astype(int)
            df_t['eje_temporal'] = df_t['anio'].astype(str)

        # Texto de filtros para los reportes
        str_fechas = f"{fecha_inicio} a {fecha_fin}" if fecha_inicio and fecha_fin else rango_sel
        txt_filtros = f"Fechas: {str_fechas} | Localidad: {sel_loc or 'Todas'} | Subtipo: {sel_sub or 'Todos'}"

        # --- SECCIÓN 1: VOLUMEN TOTAL (Lógica API NamedAgg + Espinazo Cero) ---
        st.markdown("#### 1. Evolución del Volumen Total de la Empresa")
        e_vol_total_raw = df_t.groupby(['sort_key', 'eje_temporal']).agg(
            volumen=pd.NamedAgg(column="volumen", aggfunc="sum"),
            ventas=pd.NamedAgg(column="venta_total", aggfunc="sum")
        ).reset_index()

        if not df_spine.empty:
            e_vol_total = pd.merge(df_spine, e_vol_total_raw, on=['sort_key', 'eje_temporal'], how='left')
            e_vol_total['volumen'] = e_vol_total['volumen'].fillna(0)
            e_vol_total['ventas'] = e_vol_total['ventas'].fillna(0)
        else:
            e_vol_total = e_vol_total_raw
            
        e_vol_total = e_vol_total.sort_values("sort_key")

        # Gráfico con estética refinada y fondo holográfico
        fig1 = px.line(e_vol_total, x='eje_temporal', y='volumen', markers=True, template="plotly_dark", labels={'eje_temporal': lbl_eje})
        fig1.update_traces(line_color="#3b82f6", line_width=3, marker=dict(size=8, color="#60a5fa"))
        fig1.update_layout(height=400, margin=dict(t=20, b=20), hovermode="x unified",
                           paper_bgcolor='rgba(15, 23, 42, 0.85)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#ffffff', size=13))
        fig1.update_xaxes(type='category', categoryorder='array', categoryarray=e_vol_total['eje_temporal'].unique(), gridcolor='rgba(255,255,255,0.15)', tickfont=dict(color='#ffffff', size=13))
        fig1.update_yaxes(gridcolor='rgba(255,255,255,0.15)', tickfont=dict(color='#ffffff', size=13))
        st.plotly_chart(fig1, use_container_width=True)

        # Exportación Sutil (Expander)
        col_exp1, _ = st.columns([1, 2])
        with col_exp1.expander("📥 Exportar Reporte de Volumen", expanded=False):
            ex1, ex2 = st.columns(2)
            fmt1 = ex1.selectbox("Formato", ["PDF", "XLSX", "XLS"], key="f_exp_1")
            mod1 = ex2.radio("Contenido", ["Completo", "Solo Datos"], key="m_exp_1", horizontal=True)
            
            if fmt1 == "PDF":
                # Llamada segura a la función ahora que está definida arriba
                btn_data = generar_pdf_corporativo(e_vol_total, "Reporte Inercia Total", txt_filtros, mod1)
                st.download_button("Descargar Reporte PDF", btn_data, "Inercia_Total.pdf", "application/pdf")
            else:
                btn_xl = generar_excel_corporativo(e_vol_total, fmt1.lower())
                st.download_button(f"Descargar Archivo {fmt1}", btn_xl, f"Inercia_Total.{fmt1.lower()}")

        st.markdown("---")

        # --- SECCIÓN 2: EMPUJE POR PRODUCTO (Lógica API NamedAgg + Producto Cartesiano) ---
        st.markdown(f"#### 2. Empuje por Producto (Tendencia por {v_mode})")
        e_sub_raw = df_t.groupby(['sort_key', 'eje_temporal', 'subti_comb']).agg(
            volumen=pd.NamedAgg(column="volumen", aggfunc="sum")
        ).reset_index()

        if not df_spine.empty and not e_sub_raw.empty:
            subtipos_unicos = e_sub_raw['subti_comb'].unique()
            spine_cross = df_spine.assign(key=1).merge(pd.DataFrame({'subti_comb': subtipos_unicos, 'key': 1}), on='key').drop('key', axis=1)
            e_sub = pd.merge(spine_cross, e_sub_raw, on=['sort_key', 'eje_temporal', 'subti_comb'], how='left')
            e_sub['volumen'] = e_sub['volumen'].fillna(0)
        else:
            e_sub = e_sub_raw
            
        e_sub = e_sub.sort_values("sort_key")

        fig2 = px.line(e_sub, x='eje_temporal', y='volumen', color='subti_comb', markers=True, template="plotly_dark", labels={'eje_temporal': lbl_eje, 'subti_comb': 'Combustible'})
        fig2.update_layout(height=400, legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="right", x=1, font=dict(color='#ffffff', size=13), title=dict(font=dict(color='#ffffff', size=13))),
                           paper_bgcolor='rgba(15, 23, 42, 0.85)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#ffffff', size=13))
        # Conservamos el orden cronológico estricto ocultando el datetime
        cat_order_2 = e_sub[['sort_key', 'eje_temporal']].drop_duplicates().sort_values('sort_key')['eje_temporal']
        fig2.update_xaxes(type='category', categoryorder='array', categoryarray=cat_order_2, gridcolor='rgba(255,255,255,0.15)', tickfont=dict(color='#ffffff', size=13))
        fig2.update_yaxes(gridcolor='rgba(255,255,255,0.15)', tickfont=dict(color='#ffffff', size=13))
        st.plotly_chart(fig2, use_container_width=True)

        col_exp2, _ = st.columns([1, 2])
        with col_exp2.expander("📥 Exportar Reporte de Productos", expanded=False):
            ex3, ex4 = st.columns(2)
            fmt2 = ex3.selectbox("Formato", ["PDF", "XLSX", "XLS"], key="f_exp_2")
            mod2 = ex4.radio("Contenido", ["Completo", "Solo Datos"], key="m_exp_2", horizontal=True)
            
            if fmt2 == "PDF":
                btn_data2 = generar_pdf_corporativo(e_sub, "Reporte Tendencia Productos", txt_filtros, mod2)
                st.download_button("Descargar PDF ", btn_data2, "Tendencia_Productos.pdf", "application/pdf")
            else:
                btn_xl2 = generar_excel_corporativo(e_sub, fmt2.lower())
                st.download_button(f"Descargar {fmt2} ", btn_xl2, f"Tendencia_Productos.{fmt2.lower()}")

        st.markdown("---")

        # --- RANKING PROVINCIAL ---
        st.markdown("#### 3. Dominancia por Zona (Ranking Volumen)")
        r_prov = dff.groupby(['provincia', 'subti_comb']).agg(
            volumen=pd.NamedAgg(column="volumen", aggfunc="sum")
        ).reset_index()
        
        fig_prov = px.bar(r_prov, x='provincia', y='volumen', color='subti_comb', template="plotly_dark", labels={'provincia': 'Zona', 'volumen': 'Total', 'subti_comb': 'Combustible'})
        fig_prov.update_xaxes(categoryorder='total descending', gridcolor='rgba(255,255,255,0.15)', tickfont=dict(color='#ffffff', size=13))
        fig_prov.update_yaxes(gridcolor='rgba(255,255,255,0.15)', tickfont=dict(color='#ffffff', size=13))
        fig_prov.update_layout(margin=dict(t=20, b=20), legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="right", x=1, font=dict(color='#ffffff', size=13), title=dict(font=dict(color='#ffffff', size=13))), paper_bgcolor='rgba(15, 23, 42, 0.85)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#ffffff', size=13))
        st.plotly_chart(fig_prov, use_container_width=True)
        
        col_exp_prov, _ = st.columns([1, 2])
        with col_exp_prov.expander("📥 Exportar Reporte de Zona", expanded=False):
            ex_p1, ex_p2 = st.columns(2)
            fmt_prov = ex_p1.selectbox("Formato", ["PDF", "XLSX", "XLS"], key="f_exp_prov")
            mod_prov = ex_p2.radio("Contenido", ["Completo", "Solo Datos"], key="m_exp_prov", horizontal=True)
            
            if fmt_prov == "PDF":
                btn_pdf_prov = generar_pdf_corporativo(r_prov, "Reporte Dominancia por Zona", txt_filtros, mod_prov)
                st.download_button("Descargar Reporte PDF  ", btn_pdf_prov, "Dominancia_Zona.pdf", "application/pdf")
            else:
                btn_xl_prov = generar_excel_corporativo(r_prov, fmt_prov.lower())
                st.download_button(f"Descargar Archivo {fmt_prov}  ", btn_xl_prov, f"Dominancia_Zona.{fmt_prov.lower()}")
    else:
        st.warning("⚠️ No se encontraron despachos registrados para este cruce de fechas y filtros operativos.")
        
# --- TAB 3: PODER DE MERCADO Y ESTRATEGIA GEOGRÁFICA ---
if app_page == "🍩 PODER DE MERCADO":
    if not dff.empty:
        st.subheader("🏭 Poder de Negociación por Proveedor")
        
        # 1. Preparación de datos con lógica NamedAgg (Certificada por API)
        prov_mix = dff.groupby(['proveedor', 'subti_comb']).agg(
            volumen=pd.NamedAgg(column="volumen", aggfunc="sum"),
            ventas=pd.NamedAgg(column="venta_total", aggfunc="sum")
        ).reset_index()

        str_fechas = f"{fecha_inicio} a {fecha_fin}" if fecha_inicio and fecha_fin else rango_sel
        txt_filtros_t3 = f"Fechas: {str_fechas} | Prov: {sel_prov or 'Todas'} | Sub: {sel_sub or 'Todos'}"

        # --- SECCIÓN 1: MIX POR PROVEEDOR (BARRA HORIZONTAL) ---
        st.markdown("#### 1. Concentración de Volumen por Proveedor")
        # El mayor volumen siempre arriba para lectura rápida
        fig_prov_2 = px.bar(
            prov_mix, 
            y='proveedor', 
            x='volumen', 
            color='subti_comb', 
            orientation='h', 
            template="plotly_dark",
            labels={'proveedor': 'Proveedor', 'volumen': 'Lts', 'subti_comb': 'Combustible'}
        )
        # Ordenamos: Mayor volumen ARRIBA de todo
        fig_prov_2.update_yaxes(categoryorder='total ascending', gridcolor='rgba(255,255,255,0.15)', tickfont=dict(color='#ffffff', size=12))
        fig_prov_2.update_layout(height=500, margin=dict(t=20, b=20), legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="right", x=1, font=dict(color='#ffffff', size=13), title=dict(font=dict(color='#ffffff', size=13))),
                               paper_bgcolor='rgba(15, 23, 42, 0.85)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#ffffff', size=13))
        fig_prov_2.update_xaxes(gridcolor='rgba(255,255,255,0.15)', tickfont=dict(color='#ffffff', size=13))
        st.plotly_chart(fig_prov_2, use_container_width=True)

        # BLOQUE DE EXPORTACIÓN SUTIL (Expander)
        col_exp3, _ = st.columns([1, 2])
        with col_exp3.expander("📥 Exportar Reporte de Proveedores", expanded=False):
            e_col1, e_col2 = st.columns(2)
            fmt_t3 = e_col1.selectbox("Formato de Reporte", ["PDF", "XLSX", "XLS"], key="fmt_t3_p1")
            mod_t3 = e_col2.radio("Nivel de Detalle", ["Completo", "Solo Datos"], key="mod_t3_p1", horizontal=True)
            
            if fmt_t3 == "PDF":
                btn_pdf_t3 = generar_pdf_corporativo(prov_mix, "Reporte Mix por Proveedor", txt_filtros_t3, mod_t3)
                st.download_button("Descargar Reporte PDF ", btn_pdf_t3, "Mix_Proveedores.pdf", "application/pdf")
            else:
                ext_t3 = fmt_t3.lower()
                btn_xl_t3 = generar_excel_corporativo(prov_mix, ext_t3)
                st.download_button(f"Descargar Archivo {fmt_t3} ", btn_xl_t3, f"Mix_Proveedores.{ext_t3}")

        st.markdown("---")

        # --- SECCIÓN 2: PARTICIPACIÓN GLOBAL (DONA) ---
        st.markdown("#### 2. Participación por Tipo de Producto")
        
        # Agrupamos solo por subtipo para el gráfico de torta
        mix_global = dff.groupby('subti_comb').agg(
            volumen=pd.NamedAgg(column="volumen", aggfunc="sum")
        ).reset_index()

        fig_pie = px.pie(
            mix_global, 
            values='volumen', 
            names='subti_comb', 
            hole=0.5,
            template="plotly_dark",
            labels={'subti_comb': 'Combustible', 'volumen': 'Lts'},
            color_discrete_sequence=px.colors.qualitative.Prism
        )
        fig_pie.update_traces(textinfo='percent+label', pull=[0.05, 0, 0, 0], marker=dict(line=dict(color='#ffffff', width=1)))
        fig_pie.update_layout(height=450, margin=dict(t=30, b=30), legend=dict(font=dict(color='#ffffff', size=13), title=dict(text='Combustible', font=dict(color='#ffffff', size=13))), paper_bgcolor='rgba(15, 23, 42, 0.85)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#ffffff', size=14))
        st.plotly_chart(fig_pie, use_container_width=True)

        st.markdown("---")
        st.markdown("#### 3. Batalla por el Dominio Territorial (Share de Banderas)")
        if 'bandera' in dff.columns:
            ag_bandera = dff.groupby(['bandera', 'subti_comb']).agg(volumen=("volumen", "sum")).reset_index()
            fig_bandera = px.bar(
                ag_bandera, y='bandera', x='volumen', color='subti_comb',
                orientation='h', template="plotly_dark",
                labels={'bandera': 'Marca / Bandera', 'volumen': 'Litros'}
            )
            fig_bandera.update_yaxes(categoryorder='total ascending', gridcolor='rgba(255,255,255,0.15)', tickfont=dict(color='#ffffff', size=12))
            fig_bandera.update_xaxes(gridcolor='rgba(255,255,255,0.15)', tickfont=dict(color='#ffffff', size=13))
            fig_bandera.update_layout(height=450, margin=dict(t=20, b=20), paper_bgcolor='rgba(15, 23, 42, 0.85)', plot_bgcolor='rgba(0,0,0,0)', legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="right", x=1))
            st.plotly_chart(fig_bandera, use_container_width=True)

        # Exportación sutil para el Mix Global
        col_exp4, _ = st.columns([1, 2])
        with col_exp4.expander("📥 Exportar Reporte de Mix Global", expanded=False):
            e_col3, e_col4 = st.columns(2)
            fmt_t3_pie = e_col3.selectbox("Formato de Salida", ["PDF", "XLSX"], key="fmt_t3_p2")
            if fmt_t3_pie == "PDF":
                btn_pdf_pie = generar_pdf_corporativo(mix_global, "Reporte Mix Global de Productos", txt_filtros_t3, "Completo")
                st.download_button("Descargar Reporte PDF  ", btn_pdf_pie, "Mix_Global.pdf", "application/pdf")
            else:
                btn_xl_pie = generar_excel_corporativo(mix_global, "xlsx")
                st.download_button("Descargar Archivo XLSX  ", btn_xl_pie, "Mix_Global.xlsx")
    else:
        st.warning("⚠️ No hay datos para analizar el Poder de Mercado.")

# --- TAB 4: COPILOTO ESTRATÉGICO ---
if app_page == "🧠 COPILOTO ESTRATÉGICO":
    if not dff.empty:
        st.subheader("🧠 Inteligencia de Negocio & Análisis de Riesgo")
        
        # 1. Análisis Dinámico del Velocímetro Comercial (vs Período Anterior equivalente)
        v_actual = dff['volumen'].sum() if not dff.empty else 0
        df_master_ref = st.session_state.df_master
        
        if fecha_inicio and fecha_fin:
            # Período definido por el usuario (ej. 7 días, 1 mes, etc.)
            dias_delta = (pd.to_datetime(fecha_fin) - pd.to_datetime(fecha_inicio)).days + 1
            f_ant_inicio = pd.to_datetime(fecha_inicio) - pd.Timedelta(days=dias_delta)
            f_ant_fin = pd.to_datetime(fecha_inicio) - pd.Timedelta(days=1)
            
            df_ant = df_master_ref[(df_master_ref['fecha_dt'] >= f_ant_inicio) & (df_master_ref['fecha_dt'] <= f_ant_fin)]
            v_anterior = df_ant['volumen'].sum() if not df_ant.empty else 0
            
            periodo_act = f"{dias_delta} Días"
            txt_ref = f"{dias_delta} Días Previos"
        else:
            # Todo Histórico -> Comparamos el año actual en curso vs el año pasado completo
            anio_actual = date.today().year
            v_actual = dff[dff['anio'] == anio_actual]['volumen'].sum()
            v_anterior = dff[dff['anio'] == anio_actual - 1]['volumen'].sum()
            periodo_act = f"Año en curso"
            txt_ref = f"Año Anterior ({anio_actual - 1})"
            
        variacion = ((v_actual - v_anterior) / v_anterior) * 100 if v_anterior > 0 else 0
        
        if v_actual > 0 or v_anterior > 0:
            # ======= EL "VELOCÍMETRO" (GAUGE CHART) =======
            st.markdown("#### 🏎️ Tacómetro de Velocidad Comercial")
            c_gauge, c_txt = st.columns([1.5, 1])
            
            with c_gauge:
                fig_gauge = go.Figure(go.Indicator(
                    mode = "gauge+number+delta",
                    value = v_actual,
                    domain = {'x': [0, 1], 'y': [0, 1]},
                    title = {'text': f"Litros Vendidos ({periodo_act})", 'font': {'size': 20, 'color': 'white'}},
                    delta = {'reference': v_anterior, 'valueformat': ',.0f', 'position': "top", 'increasing': {'color': '#22c55e'}, 'decreasing': {'color': '#ef4444'}},
                    number = {'valueformat': ',.0f', 'font': {'color': 'white'}},
                    gauge = {
                        'axis': {'range': [None, max(v_actual, v_anterior) * 1.5], 'tickwidth': 1, 'tickcolor': "white"},
                        'bar': {'color': "#3b82f6", 'thickness': 0.25},
                        'bgcolor': "rgba(0,0,0,0)",
                        'borderwidth': 2,
                        'bordercolor': "gray",
                        'steps': [
                            {'range': [0, v_anterior * 0.8], 'color': 'rgba(239, 68, 68, 0.4)'}, # Zona Roja
                            {'range': [v_anterior * 0.8, v_anterior * 1.05], 'color': 'rgba(234, 179, 8, 0.4)'}, # Zona Amarilla
                            {'range': [v_anterior * 1.05, max(v_actual, v_anterior) * 1.5], 'color': 'rgba(34, 197, 94, 0.4)'} # Zona Verde
                        ],
                        'threshold': {
                            'line': {'color': "white", 'width': 4},
                            'thickness': 0.75,
                            'value': v_anterior
                        }
                    }
                ))
                fig_gauge.update_layout(height=350, margin=dict(l=20, r=20, t=50, b=20), paper_bgcolor='rgba(15, 23, 42, 0.85)', font={'color': "white"})
                st.plotly_chart(fig_gauge, use_container_width=True)

            with c_txt:
                st.info(f"**Interpretación Gerencial:** Mide tu rendimiento en bloque. Hoy estás **{abs(variacion):.2f}%** {'arriba' if variacion >=0 else 'abajo'} respecto a idéntico período previo ({txt_ref}).")
                if variacion > 5:
                    st.success("🚀 **Motor a tope:** El sector está ganando inercia con fuerza. ¡Asegurar stock suficiente!")
                elif variacion >= -5:
                    st.warning("⚖️ **Velocidad Crucero:** Manteniendo inercia de distribución estable.")
                else:
                    st.error("📉 **Alerta Desaceleración:** Caída prolongada de litros en las Mangueras. Sugerencia de inyectar crédito o promociones.")

        st.markdown("---")

        # 2. Alertas de Riesgo Hugo Rodano (Concentración Crítica)
        st.subheader("⚠️ Alertas de Fuga & Concentración")
        
        # --- AQUÍ ESTABA EL ERROR (CORREGIDO CON aggfunc=) ---
        ag_riesgo = dff.groupby(["localidad", "provincia"]).agg(
            volumen=pd.NamedAgg(column="volumen", aggfunc="sum"),
            clientes=pd.NamedAgg(column="nombre", aggfunc="nunique") # <-- CORREGIDO
        ).reset_index()
        
        # Umbral: Más del promedio de volumen pero con menos de 3 clientes (Dependencia peligrosa)
        vol_promedio = ag_riesgo['volumen'].mean() if not ag_riesgo.empty else 0
        riesgo_critico = ag_riesgo[(ag_riesgo['volumen'] > vol_promedio) & (ag_riesgo['clientes'] <= 2)]
        
        if not riesgo_critico.empty:
            st.error(f"Se detectaron {len(riesgo_critico)} zonas con Riesgo de Fuga por alta concentración.")
            
            # Limpiamos, ordenamos y traducimos los títulos para forzar mejor contraste
            show_df = riesgo_critico[['localidad', 'provincia', 'volumen', 'clientes']].sort_values("volumen", ascending=False)
            show_df.columns = ["LOCALIDAD", "PROVINCIA", "VOLUMEN (LTS)", "CANTIDAD CLIENTES"]
            
            # Aplicamos Pandas Styler SOLO al encabezado forzando con !important (Azul brillante y texto Blanco)
            sty_df = show_df.style.set_table_styles([{'selector': 'th', 'props': [('color', 'white !important'), ('background-color', '#2563eb !important'), ('font-weight', 'bold !important')]}])
            st.dataframe(sty_df, use_container_width=True)
            
            # Exportación Sutil de Alertas
            with st.expander("📥 Exportar Listado de Riesgos", expanded=False):
                col_r1, col_r2 = st.columns(2)
                fmt_r = col_r1.selectbox("Formato", ["PDF", "XLSX"], key="fmt_riesgo_vfinal")
                if fmt_r == "PDF":
                    btn_r = generar_pdf_corporativo(riesgo_critico, "Alertas de Riesgo por Concentracion", "Filtros Activos", "Solo Datos")
                    st.download_button("Descargar Reporte de Riesgos", btn_r, "Alertas_Riesgo.pdf", "application/pdf")
                else:
                    btn_rx = generar_excel_corporativo(riesgo_critico, "xlsx")
                    st.download_button("Descargar Excel de Riesgos", btn_rx, "Alertas_Riesgo.xlsx")
        else:
            st.success("✅ No se detectan zonas con concentración crítica de clientes en el filtro actual.")

        st.markdown("---")
        st.subheader("💸 Matriz de Exposición Financiera (Riesgo Crediticio)")
        if 'condicion' in dff.columns:
            # Primero ordenamos por Capital Comprometido (ventas) para extraer el Top 10 real
            ag_cond = dff.groupby(['condicion']).agg(
                volumen=("volumen", "sum"),
                ventas=("venta_total", "sum")
            ).reset_index().sort_values('ventas', ascending=False)
            
            # CSS para forzar el título del toggle a color BLANCO
            st.markdown('<style>div[data-testid="stToggle"] p {color: white !important; font-weight: 500;}</style>', unsafe_allow_html=True)
            
            mostrar_todas = st.toggle("Mostrar Top 10 -> Cargar Todas las Condiciones", value=False)
            if not mostrar_todas:
                ag_cond = ag_cond.head(10)
                
            fig_cond = px.bar(
                ag_cond, x='condicion', y='ventas', color='condicion',
                template="plotly_dark", 
                labels={'condicion': 'Condición de Pago', 'ventas': 'Capital Comprometido ($)'},
                text_auto='.3s'
            )
            fig_cond.update_yaxes(gridcolor='rgba(255,255,255,0.15)')
            # Ordenamos la gráfica de izquierda a derecha (ascendente)
            fig_cond.update_xaxes(categoryorder='total ascending', tickfont=dict(color='white'))
            fig_cond.update_layout(margin=dict(t=20), height=350, paper_bgcolor='rgba(15, 23, 42, 0.85)', plot_bgcolor='rgba(0,0,0,0)', showlegend=False)
            st.plotly_chart(fig_cond, use_container_width=True)

        st.markdown("---")

        # 3. Ranking Estratégico de Score (Top 20)
        st.subheader("🧠 Ranking de Relevancia Estratégica ($Score$)")
        v_gl = dff['volumen'].sum() if not dff.empty else 1
        c_gl = dff['nombre'].nunique() if not dff.empty else 1
        
        # Cálculo de Score dinámico
        ag_riesgo['Score'] = ((ag_riesgo['volumen'] / v_gl) * 70) + ((ag_riesgo['clientes'] / c_gl) * 30)
        top_20 = ag_riesgo.sort_values("Score", ascending=False).head(20)

        fig_score = px.bar(
            top_20, 
            x='Score', 
            y='localidad', 
            color='Score', 
            orientation='h',
            title="Top 20 Localidades por Potencial de Mercado",
            color_continuous_scale='RdYlGn',
            template="plotly_dark"
        )
        fig_score.update_yaxes(categoryorder='total ascending', gridcolor='rgba(255,255,255,0.15)', tickfont=dict(color='#ffffff', size=12)) # El más alto arriba
        fig_score.update_xaxes(gridcolor='rgba(255,255,255,0.15)', tickfont=dict(color='#ffffff', size=13))
        fig_score.update_layout(margin=dict(l=0, r=0, t=30, b=0), paper_bgcolor='rgba(15, 23, 42, 0.85)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#ffffff', size=13))
        st.plotly_chart(fig_score, use_container_width=True)

        # Exportación Sutil del Ranking
        with st.expander("📥 Exportar Ranking de Score", expanded=False):
            sc1, sc2 = st.columns(2)
            fmt_sc = sc1.selectbox("Formato ", ["PDF", "XLSX"], key="fmt_score_t4_vfinal")
            if fmt_sc == "PDF":
                btn_sc = generar_pdf_corporativo(top_20, "Ranking Estrategico de Score", "Top 20 Localidades", "Completo")
                st.download_button("Descargar Reporte de Score", btn_sc, "Ranking_Score.pdf", "application/pdf")
            else:
                btn_scx = generar_excel_corporativo(top_20, "xlsx")
                st.download_button("Descargar Excel de Score", btn_scx, "Ranking_Score.xlsx")
                
        st.markdown("---")
        st.subheader("🌲 Radiografía Sectorial (ADN del Cliente)")
        st.info("🧬 **Análisis de Impacto Productivo:** Este modelo circular mapea de qué industrias exactas depende tu facturación. El círculo central verde oscuro agrupa las áreas macro (ej. AGRO, TRANSPORTE), y al hacer click en él se despliegan los anillos exteriores que contienen los sub-rubros específicos. Te permite identificar instantáneamente el ADN comercial de tu negocio y dónde está apoyado el mayor volumen.")
        if 'rubro' in dff.columns and 'subrubro' in dff.columns:
            ag_rubro = dff.groupby(['rubro', 'subrubro']).agg(volumen=("volumen", "sum")).reset_index()
            # Limpiamos los S/D masivos si nublan el gráfico
            ag_rubro = ag_rubro[ag_rubro['rubro'] != "S/D"]
            if not ag_rubro.empty:
                fig_sun = px.sunburst(
                    ag_rubro, path=['rubro', 'subrubro'], values='volumen',
                    color='volumen', color_continuous_scale='Blues',
                    template="plotly_dark"
                )
                fig_sun.update_layout(margin=dict(t=20, l=0, r=0, b=0), height=550, paper_bgcolor='rgba(15, 23, 42, 0.85)', font={'color':'white'})
                st.plotly_chart(fig_sun, use_container_width=True)
            else:
                st.warning("No hay suficientes datos sectoriales ('Rubro') etiquetados en este Excel para trazar la Radiografía.")
    else:
        st.warning("⚠️ Sin datos para procesar en el Copiloto Estratégico.")

# --- TAB EXTRA: GESTIÓN DE PERSONAL (ADMIN RBAC) ---
if app_page == "👥 GESTIÓN DE PERSONAL":
    st.markdown("<h2 style='color:#ffffff'>👥 Panel de Control de Administradores</h2>", unsafe_allow_html=True)
    st.info("💡 Desde aquí podés crear nuevas credenciales para que tu equipo acceda a la plataforma.")
    
    with st.form("form_alta_usuario", clear_on_submit=True):
        col1, col2 = st.columns(2)
        n_user = col1.text_input("Usuario (Nombre de acceso corto)")
        n_mail = col2.text_input("Email Corporativo")
        n_pass = st.text_input("Contraseña Temporal", type="password")
        
        st.markdown("### 🔑 Permisos Asignados al Usuario")
        p_ing = st.checkbox("🚀 INGESTA & CARGA (Permitir subir archivos)")
        p_vis = st.checkbox("🏠 VISIÓN EJECUTIVA (Acceso al HUB Principal)")
        p_ine = st.checkbox("📈 INERCIA TEMPORAL (Acceso al Histórico)")
        p_mer = st.checkbox("🍩 PODER DE MERCADO (Mapas y Market Share)")
        p_cop = st.checkbox("🧠 COPILOTO (Motor Neuronal y Predicciones)")
        p_adm = st.checkbox("👑 MODO DIOS (Puede crear/borrar otros usuarios)")
        
        btn_crear = st.form_submit_button("Crear Nueva Credencial", type="primary", use_container_width=True)
        
        if btn_crear:
            if not n_user.strip() or not n_pass.strip():
                st.error("❌ El Usuario y la Contraseña son obligatorios.")
            else:
                try:
                    url = st.secrets.get("SUPABASE_URL", "https://ewwdsiewmdwbxoiguoas.supabase.co")
                    key = st.secrets.get("SUPABASE_KEY", "CLAVE_OCULTA_POR_SEGURIDAD")
                    supabase = create_client(url, key)
                    
                    nuevo_registro = {
                        "usuario": n_user.strip(),
                        "mail": n_mail.strip(),
                        "password": n_pass.strip(),
                        "ingesta": "si" if p_ing else "no",
                        "vision": "si" if p_vis else "no",
                        "inercia": "si" if p_ine else "no",
                        "mercado": "si" if p_mer else "no",
                        "copiloto": "si" if p_cop else "no",
                        "admin": "si" if p_adm else "no"
                    }
                    
                    res_alta = supabase.table("usuarios").insert(nuevo_registro).execute()
                    st.success(f"✅ ¡Usuario '{n_user}' creado exitosamente en la bóveda! Ya puede iniciar sesión.")
                    st.balloons()
                except Exception as e:
                    st.error(f"🚨 Falla crítica guardando en Supabase: {e}")