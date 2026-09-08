import streamlit as st
import duckdb
import pandas as pd
import plotly.express as px

# Configuración de la página
st.set_page_config(
    page_title="Data Warehouse - EAF & FIMSS 2025",
    page_icon="📊",
    layout="wide"
)

import os

# Conexión a DuckDB con ruta absoluta
@st.cache_resource
def get_connection():
    # Obtiene la ruta del directorio donde está app.py
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, 'data', 'warehouse.db')
    
    # Comprobar si existe el archivo
    if not os.path.exists(db_path):
        st.error(f"❌ No se encontró la base de datos en: {db_path}")
        st.info("Asegúrate de subir la carpeta 'data' con 'warehouse.db' a tu repositorio de GitHub.")
        st.stop()
        
    return duckdb.connect(db_path, read_only=True)

con = get_connection()

# --- BARRA LATERAL (FILTROS) ---
st.sidebar.title("🎛️ Filtros Globales")

# Obtener lista de eventos
df_eventos_lista = con.execute("SELECT evento_id, nombre_evento FROM dim_eventos").df()
opciones_evento = ["Todos los Eventos"] + list(df_eventos_lista['nombre_evento'])

evento_seleccionado = st.sidebar.selectbox("Seleccionar Evento:", opciones_evento)

# Construir cláusula WHERE
if evento_seleccionado == "Todos los Eventos":
    where_clause = ""
else:
    e_id = df_eventos_lista[df_eventos_lista['nombre_evento'] == evento_seleccionado]['evento_id'].values[0]
    where_clause = f"WHERE f.evento_id = {e_id}"

# --- ENCABEZADO ---
st.title("📊 Data Warehouse Local & Dashboard Analytics")
st.caption("Arquitectura Modern Data Stack Local | DuckDB + Streamlit (Coste 0 €)")

tab1, tab2, tab3 = st.tabs(["📈 KPIs y Analítica", "🔍 Explorador SQL", "📐 Modelo de Datos"])

# --- TAB 1: ANALÍTICA ---
with tab1:
    st.header(f"Resultados: {evento_seleccionado}")
    
    # KPIs dinámicos
    total_inscritos = con.execute(f"SELECT COUNT(*) FROM fact_inscripciones f {where_clause}").fetchone()[0]
    total_operadoras = con.execute(f"SELECT COUNT(DISTINCT operadora_id) FROM fact_inscripciones f {where_clause}").fetchone()[0]
    
    # Consulta de cupones corregida
    if where_clause:
        query_cupones = f"SELECT COUNT(DISTINCT cupon_id) FROM fact_inscripciones f {where_clause} AND cupon_id IS NOT NULL"
    else:
        query_cupones = "SELECT COUNT(DISTINCT cupon_id) FROM fact_inscripciones f WHERE cupon_id IS NOT NULL"
        
    total_cupones = con.execute(query_cupones).fetchone()[0]
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Inscritos", f"{total_inscritos:,}")
    col2.metric("Entidades / Operadoras", total_operadoras)
    col3.metric("Cupones Aplicados", total_cupones)    
    st.divider()
    
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        st.subheader("Distribución por Tipo de Registro")
        df_tipo = con.execute(f"""
            SELECT tipo_registro AS Tipo, COUNT(*) AS Cantidad
            FROM fact_inscripciones f
            {where_clause}
            GROUP BY tipo_registro
        """).df()
        fig_tipo = px.pie(df_tipo, names="Tipo", values="Cantidad", hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
        st.plotly_chart(fig_tipo, use_container_width=True)
        
    with col_chart2:
        st.subheader("Inscripciones por Distancia / Tarifa")
        df_dist = con.execute(f"""
            SELECT distancia AS Distancia, COUNT(*) AS Cantidad
            FROM fact_inscripciones f
            {where_clause}
            GROUP BY distancia
            ORDER BY Cantidad DESC
            LIMIT 7
        """).df()
        fig_dist = px.bar(df_dist, x="Distancia", y="Cantidad", color="Cantidad", text_auto=True)
        st.plotly_chart(fig_dist, use_container_width=True)

    st.divider()
    
    # Gráfica de Operadoras
    st.subheader("Top Operadoras / Organizaciones con más Participantes")
    df_op = con.execute(f"""
        SELECT o.nombre_operadora AS Operadora, COUNT(f.dorsal) AS Inscritos
        FROM fact_inscripciones f
        LEFT JOIN dim_operadoras o ON f.operadora_id = o.operadora_id
        {where_clause}
        GROUP BY o.nombre_operadora
        ORDER BY Inscritos DESC
        LIMIT 10
    """).df()
    fig_op = px.bar(df_op, x="Inscritos", y="Operadora", orientation='h', color="Inscritos", text_auto=True)
    st.plotly_chart(fig_op, use_container_width=True)

# --- TAB 2: EXPLORADOR SQL ---
with tab2:
    st.header("Consola de Consultas SQL (Solo Lectura)")
    st.write("Consulta directamente el motor DuckDB sobre la base unificada:")
    
    query_default = """SELECT e.nombre_evento, f.dorsal, p.nombre, p.apellidos, o.nombre_operadora, f.tarifa, f.distancia 
FROM fact_inscripciones f 
JOIN dim_eventos e ON f.evento_id = e.evento_id
JOIN dim_participantes p ON f.participante_id = p.participante_id 
LEFT JOIN dim_operadoras o ON f.operadora_id = o.operadora_id 
LIMIT 10;"""
    query = st.text_area("Consulta SQL:", value=query_default, height=140)
    
    if st.button("Ejecutar Consulta"):
        try:
            df_result = con.execute(query).df()
            st.success(f"Consulta ejecutada con éxito. Registros obtenidos: {len(df_result)}")
            st.dataframe(df_result, use_container_width=True)
        except Exception as e:
            st.error(f"Error en la consulta SQL: {e}")

# --- TAB 3: MODELO DE DATOS ---
with tab3:
    st.header("Arquitectura del Modelo Multi-Fuente")
    st.markdown("""
    * **`fact_inscripciones`**: Tabla de hechos unificada con 6,943 registros.
    * **`dim_eventos`**: Dimensión que unifica los eventos (`EAF 2025` y `FIMSS 2025`).
    * **`dim_participantes`**: Dimensión única con 6,924 perfiles deduplicados.
    * **`dim_operadoras`**: Empresas, instituciones y canales de registro.
    * **`dim_cupones`**: Catálogo de promociones aplicadas.
    """)
    st.subheader("Vista previa de la Tabla de Hechos Unificada")
    st.dataframe(con.execute("SELECT * FROM fact_inscripciones LIMIT 10").df())


