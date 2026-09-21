import os
import duckdb
import pandas as pd

# Rutas de carpetas
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')
DB_PATH = os.path.join(DATA_DIR, 'warehouse.db')

# Lista de archivos a procesar (Si no usas alguno de EAF, borra la línea correspondiente)
archivos_eventos = [
    {'archivo': 'COPPEL.xlsx', 'nombre_evento': 'Coppel'},
    {
        'archivo': 'DESGLOSE FINAL SALUD RENAL 2026.xlsx',
        'nombre_evento': 'Salud Renal',
    },
    {'archivo': 'PASCUAL.xlsx', 'nombre_evento': 'Pascual'},
    {'archivo': 'WARRIORS.xlsx', 'nombre_evento': 'Warriors'},
    {'archivo': 'EAF OPERADORAS 2.xlsx', 'nombre_evento': 'EAF 2025'},
    {'archivo': 'EAF OPERADORAS 2025.xlsx', 'nombre_evento': 'EAF 2025'},
    {'archivo': 'EAF PÚBLICO EN GENERAL 2025.xlsx', 'nombre_evento': 'EAF 2025'},
    {'archivo': 'FIMSS 2025.xlsx', 'nombre_evento': 'FIMSS 2025'},
]

datos_consolidados = []

for item in archivos_eventos:
  file_path = os.path.join(DATA_DIR, item['archivo'])
  if not os.path.exists(file_path):
    file_path = os.path.join(BASE_DIR, item['archivo'])

  if not os.path.exists(file_path):
    print(f"⚠️ Archivo no encontrado: {item['archivo']}")
    continue

  print(f"\nProcesando {item['archivo']} desde: {file_path}")
  df = pd.read_excel(file_path)

  # Limpiar filas completamente vacías
  df = df.dropna(how='all')

  df_limpio = pd.DataFrame()

  # 1. ID Inscripción
  if 'NO. INSCRIPCIÓN' in df.columns:
    df_limpio['ID_Inscripcion'] = df['NO. INSCRIPCIÓN'].astype(str)
  elif 'LOCALIZADOR' in df.columns:
    df_limpio['ID_Inscripcion'] = df['LOCALIZADOR'].astype(str)
  else:
    df_limpio['ID_Inscripcion'] = [
        f'{item["nombre_evento"]}_{i+1}' for i in range(len(df))
    ]

  # Eliminar filas de TOTAL o resúmenes al final del Excel
  df_limpio = df_limpio[
      ~df_limpio['ID_Inscripcion'].str.upper().str.contains('TOTAL', na=False)
  ]
  df = df.loc[df_limpio.index]

  # 2. Evento
  df_limpio['Evento'] = item['nombre_evento']

  # 3. Fecha de inscripción
  col_fecha = [
      c
      for c in df.columns
      if 'FECHA' in str(c).upper() and 'INSCRIPCI' in str(c).upper()
  ]
  if col_fecha:
    fechas_dt = pd.to_datetime(df[col_fecha[0]], dayfirst=True, errors='coerce')
    df_limpio['Fecha_Inscripcion'] = fechas_dt.dt.strftime('%Y-%m-%d')
    df_limpio['Año'] = fechas_dt.dt.year
  else:
    df_limpio['Fecha_Inscripcion'] = None
    df_limpio['Año'] = None

  if '2025' in item['nombre_evento']:
    df_limpio['Año'] = df_limpio['Año'].fillna(2025)
  else:
    df_limpio['Año'] = df_limpio['Año'].fillna(2026)

  # 4. Obtención de Distancia / Tarifa / Modalidad
  dist_serie = None
  for col_candidate in ['DISTANCIA', 'MODALIDAD', 'TARIFA']:
    if col_candidate in df.columns:
      serie = (
          df[col_candidate]
          .astype(str)
          .str.strip()
          .replace(['nan', 'None', 'NaN', '<NA>', '', '-'], None)
      )
      if dist_serie is None:
        dist_serie = serie
      else:
        dist_serie = dist_serie.fillna(serie)

  if dist_serie is not None:
    df_limpio['Distancia'] = dist_serie
  else:
    df_limpio['Distancia'] = None

  # Imprimir los registros que no tienen distancia en la consola para identificarlos
  sin_dist = df_limpio[df_limpio['Distancia'].isna()]
  if not sin_dist.empty:
    for idx_row, r in sin_dist.iterrows():
      print(
          f"🔍 [REGISTRO SIN DISTANCIA] Evento: {item['nombre_evento']} | Fila"
          f" Excel aprox: {idx_row + 2} | ID_Inscripción: {r['ID_Inscripcion']}"
      )

  # 5. Operador
  if (
      'SELECCIONA TU EMPRESA' in df.columns
      and df['SELECCIONA TU EMPRESA'].notna().any()
  ):
    df_limpio['Operador'] = df['SELECCIONA TU EMPRESA']
  elif 'ORIGEN DE LA INSCRIPCIÓN' in df.columns:
    df_limpio['Operador'] = df['ORIGEN DE LA INSCRIPCIÓN']
  elif 'NOMBRE IMPORTACIÓN' in df.columns:
    df_limpio['Operador'] = df['NOMBRE IMPORTACIÓN']
  elif 'OPERADOR' in df.columns:
    df_limpio['Operador'] = df['OPERADOR']
  else:
    df_limpio['Operador'] = 'Sin Operador / Directo'

  # 6. Estandarización y Desglose estricto de distancias (Adulto / Infantil)
  registros_procesados = []
  for idx, row in df_limpio.iterrows():
    dist_raw = str(row['Distancia']).strip() if row['Distancia'] else ''
    dist_upper = dist_raw.upper()

    if 'ADULTO' in dist_upper and 'INFANTIL' in dist_upper:
      # Separar en 2 inscripciones
      r_adulto = row.copy()
      r_adulto['Distancia'] = 'Adulto'
      r_adulto['ID_Inscripcion'] = f"{row['ID_Inscripcion']}_Adulto"

      r_infantil = row.copy()
      r_infantil['Distancia'] = 'Infantil'
      r_infantil['ID_Inscripcion'] = f"{row['ID_Inscripcion']}_Infantil"

      registros_procesados.extend([r_adulto, r_infantil])
    elif 'INFANTIL' in dist_upper:
      r_norm = row.copy()
      r_norm['Distancia'] = 'Infantil'
      registros_procesados.append(r_norm)
    elif 'ADULTO' in dist_upper:
      r_norm = row.copy()
      r_norm['Distancia'] = 'Adulto'
      registros_procesados.append(r_norm)
    else:
      r_norm = row.copy()
      r_norm['Distancia'] = dist_raw if dist_raw else 'General'
      registros_procesados.append(r_norm)

  df_evento_final = pd.DataFrame(registros_procesados)
  datos_consolidados.append(df_evento_final)

if not datos_consolidados:
  print('❌ No se encontró ningún archivo de Excel para procesar.')
else:
  df_final = pd.concat(datos_consolidados, ignore_index=True)
  df_final['Distancia'] = df_final['Distancia'].replace(
      ['', 'None', 'nan', None], 'General'
  )
  df_final['Operador'] = df_final['Operador'].fillna('Sin Operador / Directo')
  df_final['Año'] = df_final['Año'].fillna(2026).astype(int)

  # Guardar en DuckDB
  os.makedirs(DATA_DIR, exist_ok=True)
  con = duckdb.connect(DB_PATH)
  con.execute('CREATE OR REPLACE TABLE inscripciones AS SELECT * FROM df_final')
  con.close()

  print('\n✅ Base de datos recreada con éxito en warehouse.db')