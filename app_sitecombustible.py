import streamlit as st
import pandas as pd
import folium
from folium.plugins import HeatMap
from streamlit_folium import folium_static
import plotly.express as px
import os
import json
import time
import hashlib
import gspread
import traceback
from google.oauth2.service_account import Credentials
from geopy.geocoders import Nominatim
from fpdf import FPDF
from datetime import datetime

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

IMG_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vTBV87XYOOdFbEXeTNNJHA5Dln1RZ3loFqsyEfjEn80yMj0MfDUdJRbwkSirXnc4t4fQN44HRfg56Yy/pub?output=png"

st.markdown(f"""
    <style>
    .stApp {{
        background: linear-gradient(rgba(255, 255, 255, 0.96), rgba(255, 255, 255, 0.96)), url("{IMG_URL}");
        background-size: cover; background-attachment: fixed;
    }}
    .stTabs [data-baseweb="tab-list"] {{ gap: 8px; }}
    .stTabs [data-baseweb="tab"] {{
        background-color: rgba(255, 255, 255, 0.7);
        border-radius: 5px 5px 0px 0px; padding: 10px 20px; font-weight: bold;
    }}
    </style>
    """, unsafe_allow_html=True)

MESES_ORDEN = ["ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO", "JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE"]
MESES_MAP = {i+1: m for i, m in enumerate(MESES_ORDEN)}

# ==========================================
# 🔐 GESTIÓN DE DATOS (HIGH PERFORMANCE)
# ==========================================
def get_gsheet_client():
    creds = Credentials.from_service_account_info(st.secrets["gsheets_creds"], 
            scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
    return gspread.authorize(creds)

@st.cache_data(show_spinner="Actualizando Base Central...")
def load_data():
    try:
        client = get_gsheet_client()
        sheet = client.open_by_key("1nUklyZe4ZDy4KWyz3yTT67w-gE5ysWjvzx7a0aLSrWc").sheet1
        df = pd.DataFrame(sheet.get_all_records())
        df.columns = df.columns.str.strip().str.lower()
        df = df.rename(columns={'cliente': 'nombre', 'detalle': 'subti_comb', 'articulo': 'codigo'})
        if not df.empty:
            df['fecha_dt'] = pd.to_datetime(df.get('fecha'), errors='coerce')
            df['anio'] = df['fecha_dt'].dt.year.fillna(0).astype(int)
            df['mes'] = df['fecha_dt'].dt.month.map(MESES_MAP)
            df["cantidad"] = pd.to_numeric(df.get("cantidad"), errors='coerce').fillna(0)
            # Solo pisar venta_total si no viene del excel, permitiendo conservar el dato duro
            if 'venta_total' not in df.columns:
                df["venta_total"] = df["precio"] * df["cantidad"]
            
            # Prevenir colapsos si el archivo subido no tenía las columnas esperadas por los gráficos
            for c in ['ult_provee', 'localidad', 'provincia', 'formulario', 'nnumero', 'codigo', 'nombre', 'subti_comb', 'venta_total']:
                if c not in df.columns: df[c] = "S/D"
                
            # Identidad robusta usando fecha_dt formateada para evitar asimetrías
            df['id_unique'] = df.apply(lambda r: hashlib.md5(f"{str(r.get('fecha_dt'))[:10]}_{str(r.get('formulario'))}_{str(r.get('nnumero'))}_{str(r.get('codigo'))}_{str(r.get('nombre'))}".encode()).hexdigest(), axis=1)
            df = df.drop_duplicates(subset=['id_unique'])
        else:
            # Asegurar todas las columnas requeridas para evitar KeyErrors
            df = pd.DataFrame(columns=['id_unique', 'anio', 'mes', 'localidad', 'provincia', 'subti_comb', 'cantidad', 'venta_total', 'nombre', 'fecha', 'fecha_dt', 'formulario', 'nnumero', 'codigo', 'ult_provee', 'precio'])
        return df
    except Exception as e: 
        import traceback
        import streamlit as st
        st.error(f"Error mortal leyendo la base en la nube: {e}")
        st.error(traceback.format_exc())
        return pd.DataFrame(columns=['id_unique', 'anio', 'mes', 'localidad', 'provincia', 'subti_comb', 'cantidad', 'venta_total', 'nombre', 'fecha', 'fecha_dt', 'formulario', 'nnumero', 'codigo', 'ult_provee', 'precio'])

def save_to_google_sheets(df_to_save, mode='full'):
    try:
        client = get_gsheet_client()
        sheet = client.open_by_key("1nUklyZe4ZDy4KWyz3yTT67w-gE5ysWjvzx7a0aLSrWc").sheet1
        
        # Mapear los nombres internos al formato original de tu excel
        reverse_names = {'nombre': 'cliente', 'subti_comb': 'detalle', 'codigo': 'articulo'}
        df_export = df_to_save.rename(columns=reverse_names)
        
        if 'fecha_dt' in df_export.columns:
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

def get_list(col): return [] if df_master.empty or col not in df_master.columns else sorted([str(x) for x in df_master[col].unique() if pd.notna(x) and str(x) != "S/D" and str(x) != "nan"], reverse=(col=='anio'))

sel_anio = st.sidebar.multiselect("Año", get_list('anio'))
sel_mes = st.sidebar.multiselect("Mes", MESES_ORDEN)
sel_loc = st.sidebar.multiselect("Localidad", get_list('localidad'))
sel_prov = st.sidebar.multiselect("Provincia", get_list('provincia'))
sel_sub = st.sidebar.multiselect("Subtipo Combustible", get_list('subti_comb'))

dff = df_master.copy()
if sel_anio: dff = dff[dff['anio'].astype(str).isin(sel_anio)]
if sel_mes:  dff = dff[dff['mes'].astype(str).isin(sel_mes)]
if sel_loc:  dff = dff[dff['localidad'].astype(str).isin(sel_loc)]
if sel_prov: dff = dff[dff['provincia'].astype(str).isin(sel_prov)]
if sel_sub:  dff = dff[dff['subti_comb'].astype(str).isin(sel_sub)]

vol_tot_global = dff['cantidad'].sum() if not dff.empty else 0
cli_tot_global = dff['nombre'].nunique() if not dff.empty else 0

# ==========================================
# 🏗️ TABS (FILOSOFÍA DE EMBUDO)
# ==========================================
t0, t1, t2, t3, t4 = st.tabs([
    "🚀 INICIO & CARGA", 
    "🏠 VISIÓN EJECUTIVA", 
    "📈 ANÁLISIS DE INERCIA TEMPORAL", 
    "🍩 PODER DE MERCADO", 
    "🧠 COPILOTO ESTRATÉGICO"
])

# --- TAB 0: CARGA (CON GRISEADO DE BOTÓN) ---
with t0:
    st.title("Ingesta SiteCombustible Pro")
    up_file = st.file_uploader("Subir Archivo", type=["xlsx", "csv"])
    if up_file:
        file_id = hashlib.md5(up_file.getvalue()).hexdigest()
        if "last_id" not in st.session_state or st.session_state.last_id != file_id:
            st.session_state.last_id = file_id; st.session_state.synced = False

        f_name = up_file.name.lower()
        if 'xls' in f_name: df_new = pd.read_excel(up_file, engine='openpyxl')
        else: df_new = pd.read_csv(up_file, encoding='latin-1', sep=None, engine='python', on_bad_lines='skip')
        
        df_new.columns = df_new.columns.str.strip().str.lower()
        df_new = df_new.rename(columns={'cliente': 'nombre', 'detalle': 'subti_comb', 'articulo': 'codigo', 'importe': 'venta_total', 'total': 'venta_total', 'ventas': 'venta_total'})
        df_new = df_new.loc[:, ~df_new.columns.duplicated()]
        
        # Blindaje: Inyección de columnas que podrían no venir en el Excel
        for c in ['ult_provee', 'localidad', 'provincia', 'formulario', 'nnumero', 'codigo', 'nombre', 'subti_comb', 'venta_total']:
            if c not in df_new.columns: df_new[c] = "S/D"
        
        if 'fecha' in df_new.columns:
            df_new['fecha_dt'] = pd.to_datetime(df_new['fecha'], errors='coerce')
            df_new['anio'] = df_new['fecha_dt'].dt.year.fillna(0).astype(int)
            df_new['mes'] = df_new['fecha_dt'].dt.month.map(MESES_MAP)
        
        df_new['id_unique'] = df_new.apply(lambda r: hashlib.md5(f"{str(r.get('fecha_dt'))[:10]}_{str(r.get('formulario'))}_{str(r.get('nnumero'))}_{str(r.get('codigo'))}_{str(r.get('nombre'))}".encode()).hexdigest(), axis=1)
        
        # LOGICA DE UPSERT (Full Sync)
        # Combinamos la base vieja con el excel nuevo, eliminamos duplicados quedándonos con la versión del excel nuevo (last)
        df_merged = pd.concat([df_master, df_new]).drop_duplicates(subset=['id_unique'], keep='last')
        
        nuevos_reales = len(df_merged) - len(df_master)
        actualizados = len(df_new) - nuevos_reales
        
        if len(df_new) > 0:
            st.success(f"✅ Análisis completado: Se insertarán {nuevos_reales} fila(s) nueva(s) y se actualizarán {actualizados} fila(s) existente(s).")
            st.dataframe(df_new.head(5).astype(str))
            
            label = "✅ Sincronizado (Upsert Total)" if st.session_state.synced else "🚀 Confirmar Sincronización Total (Full Sync)"
            if st.button(label, disabled=st.session_state.synced):
                with st.spinner(f"Planchando y reescribiendo la Base de Datos con {len(df_merged)} registros (tarda unos 5 seg)..."):
                    if save_to_google_sheets(df_merged, mode='full'):
                        st.session_state.synced = True; st.cache_data.clear()
                        st.session_state.df_master = load_data()
                        st.balloons(); time.sleep(1); st.rerun()
        else: st.warning("⚠️ El archivo subido está vacío.")

# --- TAB 1: VISIÓN EJECUTIVA ---
with t1:
    if not dff.empty:
        k1, k2, k3 = st.columns(3)
        k1.metric("Volumen Bruto (Total)", f"{vol_tot_global:,.0f}")
        k2.metric("Clientes Activos", cli_tot_global)
        k3.metric("Ventas Est. ($)", f"$ {dff['venta_total'].sum():,.0f}")
        
        st.subheader("📍 Concentración Geográfica (Mapa de Sensibilidad)")
        ag_map = dff.groupby(["localidad", "provincia"]).agg(vol=("cantidad", "sum"), cli=("nombre", "nunique")).reset_index()
        def calc_score(r):
            s = ((r['vol'] / vol_tot_global) * 70) + ((r['cli'] / cli_tot_global) * 30)
            n = "Alta" if s >= 5.0 else "Media" if s >= 1.5 else "Baja"
            return s, n
        calc = ag_map.apply(calc_score, axis=1)
        ag_map['Score'], ag_map['Nivel'] = calc.apply(lambda x: x[0]), calc.apply(lambda x: x[1])

        if 'geo' not in st.session_state: st.session_state.geo = {}
        geolocator = Nominatim(user_agent="sitecomb_vfinal_v50")
        for _, r in ag_map.sort_values("vol", ascending=False).head(20).iterrows():
            k = f"{r['localidad']}, {r['provincia']}"
            if k not in st.session_state.geo:
                try: res = geolocator.geocode(f"{k}, Argentina"); st.session_state.geo[k] = {"lat": res.latitude, "lon": res.longitude}
                except: pass

        m_data = [[st.session_state.geo[k]['lat'], st.session_state.geo[k]['lon'], r['Score']] 
                  for _, r in ag_map.iterrows() if (k := f"{r['localidad']}, {r['provincia']}") in st.session_state.geo]
        
        m = folium.Map(location=[-38.4, -63.6], zoom_start=5, tiles='cartodb positron')
        if m_data: HeatMap(m_data, radius=25, blur=20, min_opacity=0.3).add_to(m) 
        folium_static(m, width=1150)
        
        st.subheader("🚦 Grilla Estratégica (Análisis de Mercado)")
        grid = ag_map.sort_values("Score", ascending=False)
        st.dataframe(grid.style.applymap(lambda v: 'background-color: #fee2e2' if v=='Alta' else ('background-color: #fef9c3' if v=='Media' else 'background-color: #dcfce7'), subset=['Nivel']), use_container_width=True)

        if st.button("⬇️ Descargar Reporte PDF Corporativo"):
            pdf = FPDF(); pdf.add_page(); pdf.set_font("Arial", "B", 16)
            pdf.cell(0, 10, "SITECOMBUSTIBLE PRO - REPORTE EJECUTIVO", ln=True, align="C")
            pdf.line(10, 25, 200, 25); pdf.ln(8)
            pdf.set_font("Arial", "B", 10); pdf.cell(0, 8, f"Filtros: A:{sel_anio} | M:{sel_mes} | P:{sel_prov}", ln=True)
            pdf.ln(5); pdf.cell(60, 8, "Localidad", 1); pdf.cell(60, 8, "Provincia", 1); pdf.cell(40, 8, "Score", 1); pdf.ln()
            for _, r in grid.head(25).iterrows():
                pdf.set_font("Arial", "", 9); pdf.cell(60, 7, str(r['localidad'])[:28], 1); pdf.cell(60, 7, str(r['provincia'])[:28], 1); pdf.cell(40, 7, f"{r['Score']:.2f}", 1, 1)
            st.download_button("Descargar PDF", data=pdf.output(dest='S').encode('latin-1'), file_name="Reporte_BI_SiteCombustible.pdf")

# --- TAB 2: ANÁLISIS DE INERCIA TEMPORAL (MODIFICACIÓN QUIRÚRGICA) ---
with t2:
    if not dff.empty:
        st.subheader("📊 Inercia Temporal de Despacho")
        
        # Mando de granularidad sutil
        v_mode = st.radio("Escala Temporal:", ["Año", "Mes", "Semana"], horizontal=True, key="mando_temporal_v5")
        
        df_t = dff.copy().dropna(subset=['fecha_dt'])
        if v_mode == "Semana":
            df_t['eje_temporal'] = df_t['fecha_dt'].dt.to_period('W').dt.start_time
            lbl_eje = "Semana"
        elif v_mode == "Mes":
            df_t['eje_temporal'] = df_t['fecha_dt'].dt.to_period('M').dt.start_time
            lbl_eje = "Mes"
        else:
            df_t['eje_temporal'] = df_t['anio'].astype(int)
            lbl_eje = "Año"

        # Texto de filtros para los reportes
        txt_filtros = f"Año: {sel_anio or 'Todos'} | Mes: {sel_mes or 'Todos'} | Localidad: {sel_loc or 'Todas'} | Subtipo: {sel_sub or 'Todos'}"

        # --- SECCIÓN 1: VOLUMEN TOTAL (Lógica API NamedAgg) ---
        st.markdown("#### 1. Evolución del Volumen Total de la Empresa")
        e_vol_total = df_t.groupby('eje_temporal').agg(
            volumen=pd.NamedAgg(column="cantidad", aggfunc="sum"),
            ventas=pd.NamedAgg(column="venta_total", aggfunc="sum")
        ).reset_index().sort_values("eje_temporal")

        # Gráfico con estética refinada
        fig1 = px.line(e_vol_total, x='eje_temporal', y='volumen', markers=True, template="plotly_white")
        fig1.update_traces(line_color="#1e3a8a", line_width=2, marker=dict(size=6))
        fig1.update_layout(height=400, margin=dict(t=20, b=20), hovermode="x unified")
        st.plotly_chart(fig1, use_container_width=True)

        # Exportación Sutil (Expander)
        with st.expander("📥 Exportar Reporte de Volumen", expanded=False):
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

        # --- SECCIÓN 2: EMPUJE POR PRODUCTO (Lógica API NamedAgg) ---
        st.markdown(f"#### 2. Empuje por Producto (Tendencia por {v_mode})")
        e_sub = df_t.groupby(['eje_temporal', 'subti_comb']).agg(
            volumen=pd.NamedAgg(column="cantidad", aggfunc="sum")
        ).reset_index().sort_values("eje_temporal")

        fig2 = px.line(e_sub, x='eje_temporal', y='volumen', color='subti_comb', markers=True, template="plotly_white")
        fig2.update_layout(height=400, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        st.plotly_chart(fig2, use_container_width=True)

        with st.expander("📥 Exportar Reporte de Productos", expanded=False):
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
            volumen=pd.NamedAgg(column="cantidad", aggfunc="sum")
        ).reset_index()
        
        fig_prov = px.bar(r_prov, x='provincia', y='volumen', color='subti_comb', template="plotly_white")
        fig_prov.update_xaxes(categoryorder='total descending')
        st.plotly_chart(fig_prov, use_container_width=True)
        
# --- TAB 3: PODER DE MERCADO (LOGICA CERTIFICADA & EXPORTABLE) ---
with t3:
    if not dff.empty:
        st.subheader("🏭 Poder de Negociación por Proveedor")
        
        # 1. Preparación de datos con lógica NamedAgg (Certificada por API)
        prov_mix = dff.groupby(['ult_provee', 'subti_comb']).agg(
            volumen=pd.NamedAgg(column="cantidad", aggfunc="sum"),
            ventas=pd.NamedAgg(column="venta_total", aggfunc="sum")
        ).reset_index()

        # Texto de filtros para los reportes corporativos
        txt_filtros_t3 = f"Año: {sel_anio or 'Todos'} | Mes: {sel_mes or 'Todos'} | Prov: {sel_prov or 'Todas'} | Sub: {sel_sub or 'Todos'}"

        # --- SECCIÓN 1: MIX POR PROVEEDOR (BARRA HORIZONTAL) ---
        st.markdown("#### 1. Concentración de Volumen por Proveedor")
        # El mayor volumen siempre arriba para lectura rápida
        fig_prov = px.bar(
            prov_mix, 
            y='ult_provee', 
            x='volumen', 
            color='subti_comb', 
            orientation='h', 
            template="plotly_white",
            labels={'ult_provee': 'Proveedor', 'volumen': 'Volumen (Lts)', 'subti_comb': 'Producto'}
        )
        # Ordenamos: Mayor volumen ARRIBA de todo
        fig_prov.update_yaxes(categoryorder='total ascending')
        fig_prov.update_layout(height=500, margin=dict(t=20, b=20), legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        st.plotly_chart(fig_prov, use_container_width=True)

        # BLOQUE DE EXPORTACIÓN SUTIL (Expander)
        with st.expander("📥 Exportar Reporte de Proveedores", expanded=False):
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
            volumen=pd.NamedAgg(column="cantidad", aggfunc="sum")
        ).reset_index()

        fig_pie = px.pie(
            mix_global, 
            values='volumen', 
            names='subti_comb', 
            hole=0.5,
            template="plotly_white",
            color_discrete_sequence=px.colors.qualitative.Prism
        )
        fig_pie.update_traces(textinfo='percent+label', pull=[0.05, 0, 0, 0])
        fig_pie.update_layout(height=450, margin=dict(t=30, b=30))
        st.plotly_chart(fig_pie, use_container_width=True)

        # Exportación sutil para el Mix Global
        with st.expander("📥 Exportar Reporte de Mix Global", expanded=False):
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

# --- TAB 4: COPILOTO ESTRATÉGICO (VERSIÓN FINAL RECTIFICADA) ---
with t4:
    if not dff.empty:
        st.subheader("🧠 Inteligencia de Negocio & Análisis de Riesgo")
        
        # 1. Análisis de Aceleración Comercial (MoM)
        # Usamos NamedAgg para garantizar que la sumatoria sea la correcta
        mom_data = dff.groupby(['anio', 'mes']).agg(
            volumen=pd.NamedAgg(column="cantidad", aggfunc="sum")
        ).reset_index()

        if len(mom_data) >= 2:
            # Obtenemos los últimos dos periodos cargados
            v_actual = mom_data.iloc[-1]['volumen']
            v_anterior = mom_data.iloc[-2]['volumen']
            periodo_act = f"{mom_data.iloc[-1]['mes']} {mom_data.iloc[-1]['anio']}"
            
            variacion = ((v_actual - v_anterior) / v_anterior) * 100 if v_anterior > 0 else 0
            
            c1, c2 = st.columns([1, 2])
            with c1:
                st.metric(
                    label=f"Aceleración Comercial ({periodo_act})", 
                    value=f"{v_actual:,.0f} Lts", 
                    delta=f"{variacion:.2f}% vs Mes Ant."
                )
            with c2:
                st.info(f"**Interpretación Gerencial:** El despacho presenta una variación del **{variacion:.2f}%**. "
                        "Un valor positivo indica que el camión está ganando tracción; un valor negativo es una "
                        "alerta de enfriamiento que requiere revisión de precios o promociones.")

        st.markdown("---")

        # 2. Alertas de Riesgo Hugo Rodano (Concentración Crítica)
        st.subheader("⚠️ Alertas de Fuga & Concentración")
        
        # --- AQUÍ ESTABA EL ERROR (CORREGIDO CON aggfunc=) ---
        ag_riesgo = dff.groupby(["localidad", "provincia"]).agg(
            volumen=pd.NamedAgg(column="cantidad", aggfunc="sum"),
            clientes=pd.NamedAgg(column="nombre", aggfunc="nunique") # <-- CORREGIDO
        ).reset_index()
        
        # Umbral: Más del promedio de volumen pero con menos de 3 clientes (Dependencia peligrosa)
        vol_promedio = ag_riesgo['volumen'].mean() if not ag_riesgo.empty else 0
        riesgo_critico = ag_riesgo[(ag_riesgo['volumen'] > vol_promedio) & (ag_riesgo['clientes'] <= 2)]
        
        if not riesgo_critico.empty:
            st.error(f"Se detectaron {len(riesgo_critico)} zonas con Riesgo de Fuga por alta concentración.")
            st.dataframe(riesgo_critico.sort_values("volumen", ascending=False), use_container_width=True)
            
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

        # 3. Ranking Estratégico de Score (Top 20)
        st.subheader("🧠 Ranking de Relevancia Estratégica ($Score$)")
        v_gl = dff['cantidad'].sum() if not dff.empty else 1
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
            template="plotly_white"
        )
        fig_score.update_yaxes(categoryorder='total ascending') # El más alto arriba
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
    else:
        st.warning("⚠️ Sin datos para procesar en el Copiloto Estratégico.")