import os
import duckdb
import pandas as pd
import streamlit as st
import plotly.express as px

# Configuración de la página
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
        st.error(f"❌ No se encontró la base de datos en: {db_path}")
        st.stop()
        
    return duckdb.connect(db_path, read_only=True)

con = get_connection()

# --- CARGAR DATOS GENERALES ---
df_all = con.execute("SELECT * FROM dim_inscripciones").df()

# --- FILTROS EN BARRA LATERAL ---
st.sidebar.title("⚙️ Filtros del DWH")

# 1. Filtro de Año
años_disponibles = sorted([int(a) for a in df_all['Año'].dropna().unique()], reverse=True)
opciones_año = ["Todos"] + [str(a) for a in años_disponibles]
año_sel = st.sidebar.selectbox("📅 Selecciona el Año", opciones_año)

# Filtrar dataframe por Año primero
df_filtrado = df_all.copy()
if año_sel != "Todos":
    df_filtrado = df_filtrado[df_filtrado['Año'] == int(año_sel)]

# 2. Filtro de Evento (Dinámico según el año)
eventos_disponibles = sorted(df_filtrado['Evento'].dropna().unique().tolist())
opciones_evento = ["Todos"] + eventos_disponibles
evento_sel = st.sidebar.selectbox("🏆 Selecciona el Evento", opciones_evento)

if evento_sel != "Todos":
    df_filtrado = df_filtrado[df_filtrado['Evento'] == evento_sel]

# --- ENCABEZADO ---
st.title("📊 Panel Consolidado de Inscripciones")
st.markdown(f"**Vista activa:** Año: `{año_sel}` | Evento: `{evento_sel}`")

# --- KPIS PRINCIPALES ---
col1, col2, col3, col4 = st.columns(4)

total_competidores = len(df_filtrado)
operadores_unicos = df_filtrado[df_filtrado['Operador'] != 'Sin Operador / Directo']['Operador'].nunique()
distancias_unicas = df_filtrado['Distancia'].nunique()
eventos_activos = df_filtrado['Evento'].nunique()

col1.metric("👥 Competidores", f"{total_competidores:,}")
col2.metric("🏢 Operadores Únicos", operadores_unicos)
col3.metric("📏 Distancias / Tarifas", distancias_unicas)
col4.metric("🏆 Eventos Incluidos", eventos_activos)

st.divider()

# --- PESTAÑAS DE VISUALIZACIÓN ---
tab1, tab2, tab3, tab4 = st.tabs(["👥 Competidores & Distancias", "🏢 Operadores", "📅 Fechas de Inscripción", "📋 Explorador de Datos"])

# TAB 1: Distancias
with tab1:
    st.subheader("Distribución de Competidores por Distancia / Modalidad")
    df_dist = df_filtrado['Distancia'].value_counts().reset_index()
    df_dist.columns = ['Distancia', 'Cantidad']
    
    fig_dist = px.bar(
        df_dist, 
        x='Distancia', 
        y='Cantidad', 
        text='Cantidad',
        color='Distancia',
        title="Número de Competidores por Distancia"
    )
    st.plotly_chart(fig_dist, use_container_width=True)

# TAB 2: Operadores
with tab2:
    st.subheader("Inscripciones por Operador / Origen")
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
        st.write("### Tabla de Operadores")
        st.dataframe(df_op, use_container_width=True)

# TAB 3: Fechas de Inscripción
with tab3:
    st.subheader("Evolución Temporal de las Inscripciones")
    if 'Fecha_Inscripcion' in df_filtrado.columns and df_filtrado['Fecha_Inscripcion'].notna().any():
        df_fecha = df_filtrado.groupby(df_filtrado['Fecha_Inscripcion'].dt.date).size().reset_index(name='Inscritos')
        fig_time = px.line(
            df_fecha, 
            x='Fecha_Inscripcion', 
            y='Inscritos', 
            title="Inscripciones Diarias",
            markers=True
        )
        st.plotly_chart(fig_time, use_container_width=True)
    else:
        st.info("No hay fechas de inscripción disponibles para la selección actual.")

# TAB 4: Explorador
with tab4:
    st.subheader("Vista Previa de Datos Anónimos en el DWH")
    st.dataframe(df_filtrado[['ID_Inscripcion', 'Evento', 'Año', 'Distancia', 'Operador', 'Fecha_Inscripcion']], use_container_width=True)

