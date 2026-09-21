import os
import duckdb
import pandas as pd
import streamlit as st
import plotly.express as px

# Configuración inicial de la página
st.set_page_config(
    page_title="Data Warehouse - Analítica de Inscripciones",
    page_icon="📊",
    layout="wide"
)

# --- CONEXIÓN A DUCKDB ---
@st.cache_resource
def get_connection():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, 'data', 'warehouse.db')
    
    if not os.path.exists(db_path):
        st.error(f"❌ No se encontró el archivo de base de datos en: {db_path}")
        st.stop()
        
    return duckdb.connect(db_path, read_only=True)

con = get_connection()

# --- CARGAR DATOS CON DIAGNÓSTICO DE CACHÉ / TABLAS ---
try:
    df_all = con.execute("SELECT * FROM dim_inscripciones").df()
except Exception as e:
    # Diagnóstico en caso de que la conexión en caché no vea la nueva tabla
    try:
        tablas_existentes = con.execute("SHOW TABLES").df()
        lista_tablas = tablas_existentes['name'].tolist() if not tablas_existentes.empty else ["Ninguna"]
    except Exception:
        lista_tablas = ["No se pudieron consultar las tablas"]
    
    st.error("❌ No se encontró la tabla 'dim_inscripciones' en la base de datos cargada.")
    st.warning(f"📋 Tablas detectadas actualmente en DuckDB: {lista_tablas}")
    st.info("💡 **Solución requerida:** Haz clic en **'Manage app'** (abajo a la derecha en Streamlit Cloud) -> **'Reboot app'** para forzar la actualización de la base de datos.")
    st.stop()

# --- BARRA LATERAL: FILTROS DINÁMICOS ---
st.sidebar.title("⚙️ Filtros del DWH")

# 1. Filtro de Año
if 'Año' in df_all.columns and df_all['Año'].notna().any():
    años_disponibles = sorted([int(a) for a in df_all['Año'].dropna().unique()], reverse=True)
    opciones_año = ["Todos"] + [str(a) for a in años_disponibles]
else:
    opciones_año = ["Todos"]

año_sel = st.sidebar.selectbox("📅 Selecciona el Año", opciones_año)

# Filtrar dataframe por Año
df_filtrado = df_all.copy()
if año_sel != "Todos":
    df_filtrado = df_filtrado[df_filtrado['Año'] == int(año_sel)]

# 2. Filtro de Evento
if 'Evento' in df_filtrado.columns and df_filtrado['Evento'].notna().any():
    eventos_disponibles = sorted(df_filtrado['Evento'].dropna().unique().tolist())
    opciones_evento = ["Todos"] + eventos_disponibles
else:
    opciones_evento = ["Todos"]

evento_sel = st.sidebar.selectbox("🏆 Selecciona el Evento", opciones_evento)

if evento_sel != "Todos":
    df_filtrado = df_filtrado[df_filtrado['Evento'] == evento_sel]

# --- ENCABEZADO Y KPIS ---
st.title("📊 Panel Consolidado de Inscripciones")
st.markdown(f"**Filtros activos:** Año: `{año_sel}` | Evento: `{evento_sel}`")

col1, col2, col3, col4 = st.columns(4)

total_competidores = len(df_filtrado)
operadores_unicos = df_filtrado[df_filtrado['Operador'] != 'Sin Operador / Directo']['Operador'].nunique() if 'Operador' in df_filtrado.columns else 0
distancias_unicas = df_filtrado['Distancia'].nunique() if 'Distancia' in df_filtrado.columns else 0
eventos_activos = df_filtrado['Evento'].nunique() if 'Evento' in df_filtrado.columns else 0

col1.metric("👥 Total Competidores", f"{total_competidores:,}")
col2.metric("🏢 Operadores Únicos", operadores_unicos)
col3.metric("📏 Distancias / Tarifas", distancias_unicas)
col4.metric("🏆 Eventos Incluidos", eventos_activos)

st.divider()

# --- PESTAÑAS DE VISUALIZACIÓN ---
tab1, tab2, tab3, tab4 = st.tabs(["👥 Competidores & Distancias", "🏢 Operadores", "📅 Fechas de Inscripción", "📋 Explorador de Datos"])

# TAB 1: Distancias
with tab1:
    st.subheader("Distribución de Competidores por Distancia / Modalidad")
    if 'Distancia' in df_filtrado.columns and not df_filtrado.empty:
        df_dist = df_filtrado['Distancia'].value_counts().reset_index()
        df_dist.columns = ['Distancia', 'Cantidad']
        
        fig_dist = px.bar(
            df_dist, 
            x='Distancia', 
            y='Cantidad', 
            text='Cantidad',
            color='Distancia',
            title="Competidores por Distancia / Tarifa"
        )
        st.plotly_chart(fig_dist, use_container_width=True)
    else:
        st.info("No hay datos de distancia para la selección actual.")

# TAB 2: Operadores
with tab2:
    st.subheader("Inscripciones por Operador / Origen")
    if 'Operador' in df_filtrado.columns and not df_filtrado.empty:
        df_op = df_filtrado['Operador'].value_counts().reset_index()
        df_op.columns = ['Operador', 'Cantidad']
        
        col_op1, col_op2 = st.columns([2, 1])
        with col_op1:
            fig_op = px.pie(
                df_op, 
                names='Operador', 
                values='Cantidad', 
                title="Proporción por Operador",
                hole=0.4
            )
            st.plotly_chart(fig_op, use_container_width=True)
        with col_op2:
            st.write("### Detalle por Operador")
            st.dataframe(df_op, use_container_width=True)
    else:
        st.info("No hay datos de operadores para la selección actual.")

# TAB 3: Fechas de Inscripción
with tab3:
    st.subheader("Evolución Temporal de las Inscripciones")
    if 'Fecha_Inscripcion' in df_filtrado.columns and df_filtrado['Fecha_Inscripcion'].notna().any():
        df_filtrado['Fecha_DT'] = pd.to_datetime(df_filtrado['Fecha_Inscripcion'], errors='coerce')
        df_fecha = df_filtrado.dropna(subset=['Fecha_DT']).groupby(df_filtrado['Fecha_DT'].dt.date).size().reset_index(name='Inscritos')
        df_fecha.columns = ['Fecha', 'Inscritos']
        
        fig_time = px.line(
            df_fecha, 
            x='Fecha', 
            y='Inscritos', 
            title="Inscripciones Diarias",
            markers=True
        )
        st.plotly_chart(fig_time, use_container_width=True)
    else:
        st.info("No hay fechas de inscripción válidas para la selección actual.")

# --- Pestaña 4: Exploración de datos ---
with tab4:
  st.subheader('Exploración de datos')

  # Copia del DataFrame filtrado para la vista
  df_exploracion = df_filtrado.copy()

  # 1. Quitar la columna auxiliar 'Fecha_DT' para que no aparezca repetida
  if 'Fecha_DT' in df_exploracion.columns:
    df_exploracion = df_exploracion.drop(columns=['Fecha_DT'])

  # 2. Formatear 'Fecha_Inscripcion' como texto simple (AAAA-MM-DD) para ocultar las horas
  if 'Fecha_Inscripcion' in df_exploracion.columns:
    df_exploracion['Fecha_Inscripcion'] = pd.to_datetime(
        df_exploracion['Fecha_Inscripcion'], errors='coerce'
    ).dt.strftime('%Y-%m-%d')

  # 3. Reiniciar el índice para que comience en 1
  df_exploracion = df_exploracion.reset_index(drop=True)
  df_exploracion.index = df_exploracion.index + 1

  # Mostrar la tabla limpia
  st.dataframe(df_exploracion, use_container_width=True)

  # Botón de descarga CSV
  csv = df_exploracion.to_csv(index=False).encode('utf-8')
  st.download_button(
      label='📥 Descargar datos filtrados (CSV)',
      data=csv,
      file_name='datos_inscripciones.csv',
      mime='text/csv',
  )