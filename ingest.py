import pandas as pd
import duckdb
import os

def ejecutar_etl_multifuente():
    print("🚀 Iniciando ETL Multi-Fuente para EAF y FIMSS 2025...")
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.dirname(script_dir)
    archivos = os.listdir(base_dir)
    
    f_operadoras = None
    f_publico = None
    f_fimss = None
    
    for f in archivos:
        f_upper = f.upper()
        if f.endswith('.xlsx') and not f.startswith('~$'):
            if 'OPERADORAS' in f_upper:
                f_operadoras = os.path.join(base_dir, f)
            elif 'PUBLICO' in f_upper or 'PÚBLICO' in f_upper or 'GENERAL' in f_upper:
                f_publico = os.path.join(base_dir, f)
            elif 'FIMSS' in f_upper:
                f_fimss = os.path.join(base_dir, f)

    dfs = []
    
    # 1. Cargar EAF Operadoras
    if f_operadoras:
        df1 = pd.read_excel(f_operadoras)
        df1['evento_id'] = 1
        df1['nombre_evento'] = 'EAF 2025'
        df1['tipo_registro'] = 'Corporativo (Operadoras)'
        col_op = '¿A que Operadora perteneces?' if '¿A que Operadora perteneces?' in df1.columns else df1.columns[0]
        df1['operadora_origen'] = df1[col_op]
        df1['distancia_limpia'] = df1['Distancia'] if 'Distancia' in df1.columns else df1['TARIFA']
        dfs.append(df1)
        
    # 2. Cargar EAF Público General
    if f_publico:
        df2 = pd.read_excel(f_publico)
        df2['evento_id'] = 1
        df2['nombre_evento'] = 'EAF 2025'
        df2['tipo_registro'] = 'Público General'
        df2['operadora_origen'] = 'Público General'
        df2['distancia_limpia'] = df2['Distancia'] if 'Distancia' in df2.columns else df2['TARIFA']
        dfs.append(df2)

    # 3. Cargar FIMSS
    if f_fimss:
        df3 = pd.read_excel(f_fimss)
        df3['evento_id'] = 2
        df3['nombre_evento'] = 'FIMSS 2025'
        df3['tipo_registro'] = 'General IMSS'
        df3['operadora_origen'] = 'FIMSS / IMSS'
        # En FIMSS no existe la columna 'Distancia', asignamos 'TARIFA' (3K, 5K, 10K)
        df3['distancia_limpia'] = df3['TARIFA']
        dfs.append(df3)

    if not dfs:
        print("❌ Error: No se logró cargar ningún archivo Excel.")
        return

    df_raw = pd.concat(dfs, ignore_index=True)

    # --- LIMPIEZA DE CAMPOS ---
    if 'Genero' in df_raw.columns and 'Género' in df_raw.columns:
        df_raw['genero_limpio'] = df_raw['Género'].fillna(df_raw['Genero']).replace({'Desconocido': None})
    elif 'Género' in df_raw.columns:
        df_raw['genero_limpio'] = df_raw['Género'].replace({'Desconocido': None})
    else:
        df_raw['genero_limpio'] = df_raw['Genero'].replace({'Desconocido': None})

    talla_cols = [c for c in df_raw.columns if 'Talla' in c or 'talla' in c]
    df_raw['talla_playera'] = df_raw[talla_cols].bfill(axis=1).iloc[:, 0] if talla_cols else None

    cat_cols = [c for c in df_raw.columns if 'Categoria' in c or 'categoria' in c]
    df_raw['categoria_limpia'] = df_raw[cat_cols].bfill(axis=1).iloc[:, 0] if cat_cols else None

    df_raw['codigo_cupon_limpio'] = df_raw['CÓDIGO CUPÓN'] if 'CÓDIGO CUPÓN' in df_raw.columns else None

    if 'NÚMERO DE COMPETIDOR' in df_raw.columns and 'DORSAL' in df_raw.columns:
        df_raw['dorsal_limpio'] = df_raw['DORSAL'].fillna(df_raw['NÚMERO DE COMPETIDOR'])
    elif 'DORSAL' in df_raw.columns:
        df_raw['dorsal_limpio'] = df_raw['DORSAL']
    else:
        df_raw['dorsal_limpio'] = df_raw['NÚMERO DE COMPETIDOR']

    # --- DIMENSIONES ---
    df_eventos = df_raw[['evento_id', 'nombre_evento']].drop_duplicates().reset_index(drop=True)
    
    df_operadoras = pd.DataFrame({'nombre_operadora': df_raw['operadora_origen'].unique()}).dropna().reset_index()
    df_operadoras.columns = ['operadora_id', 'nombre_operadora']
    df_operadoras['operadora_id'] += 1

    df_cupones = pd.DataFrame({'codigo_cupon': df_raw['codigo_cupon_limpio'].dropna().unique()}).reset_index()
    df_cupones.columns = ['cupon_id', 'codigo_cupon']
    df_cupones['cupon_id'] += 1

    df_participantes = df_raw[['Nombre', 'Apellidos', 'genero_limpio', 'Fecha nacimiento', 'Email', 'Teléfono móvil']].drop_duplicates().reset_index(drop=True)
    df_participantes['participante_id'] = df_participantes.index + 1
    df_participantes.rename(columns={
        'Nombre': 'nombre', 'Apellidos': 'apellidos',
        'genero_limpio': 'genero', 'Fecha nacimiento': 'fecha_nacimiento',
        'Email': 'email', 'Teléfono móvil': 'telefono'
    }, inplace=True)

    # Relaciones
    df_raw = df_raw.merge(df_operadoras, left_on='operadora_origen', right_on='nombre_operadora', how='left')
    df_raw = df_raw.merge(df_cupones, left_on='codigo_cupon_limpio', right_on='codigo_cupon', how='left')
    df_raw = df_raw.merge(df_participantes, left_on=['Nombre', 'Apellidos', 'Email'], right_on=['nombre', 'apellidos', 'email'], how='left')

    # Hechos
    df_fact = pd.DataFrame({
        'dorsal': df_raw['dorsal_limpio'],
        'localizador': df_raw['LOCALIZADOR'],
        'no_inscripcion': df_raw['NO. INSCRIPCIÓN'],
        'evento_id': df_raw['evento_id'],
        'participante_id': df_raw['participante_id'],
        'operadora_id': df_raw['operadora_id'],
        'cupon_id': df_raw['cupon_id'],
        'tipo_registro': df_raw['tipo_registro'],
        'tarifa': df_raw['TARIFA'],
        'distancia': df_raw['distancia_limpia'],
        'categoria': df_raw['categoria_limpia'],
        'talla_playera': df_raw['talla_playera'],
        'fecha_inscripcion': pd.to_datetime(df_raw['FECHA DE INSCRIPCIÓN'], format='%d/%m/%Y', errors='coerce')
    })

    # --- CARGA EN DUCKDB ---
    db_dir = os.path.join(base_dir, 'data')
    os.makedirs(db_dir, exist_ok=True)
    db_path = os.path.join(db_dir, 'warehouse.db')
    
    con = duckdb.connect(db_path)
    con.execute("CREATE OR REPLACE TABLE dim_eventos AS SELECT * FROM df_eventos")
    con.execute("CREATE OR REPLACE TABLE dim_operadoras AS SELECT * FROM df_operadoras")
    con.execute("CREATE OR REPLACE TABLE dim_cupones AS SELECT * FROM df_cupones")
    con.execute("CREATE OR REPLACE TABLE dim_participantes AS SELECT * FROM df_participantes")
    con.execute("CREATE OR REPLACE TABLE fact_inscripciones AS SELECT * FROM df_fact")

    print(f"\n🎉 ¡ETL REGENERADO CON ÉXITO!")
    print(f"  • Registros cargados en Fact: {len(df_fact)}")
    con.close()

if __name__ == '__main__':
    ejecutar_etl_multifuente()