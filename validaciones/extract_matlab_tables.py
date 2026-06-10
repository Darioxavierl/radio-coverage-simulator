"""
Script para extraer datos de tablas ITU-R P.1546-6 desde la implementación MATLAB oficial
y generar el código Python corregido para itu_r_p1546_tables.py

Tablas necesarias (según figure_rec en P1546FieldStrMixed.m):
  - exceltables{1}  = 100 MHz, 50% tiempo, Land
  - exceltables{9}  = 600 MHz, 50% tiempo, Land
  - exceltables{17} = 2000 MHz, 50% tiempo, Land

Fuente: itu/Matlab implementation of Recommendation ITU-R P.1546-6 - Ver 6.2/P1546FieldStrMixed.m
"""

import re
import numpy as np
from pathlib import Path

# ───────────────────────── CONFIGURACION ─────────────────────────
MATLAB_FILE = Path(r"g:\My Drive\Universidad\Tesis\itu\Matlab implementation of Recommendation ITU-R P.1546-6 - Ver 6.2\P1546FieldStrMixed.m")

# Distancias de referencia que usa nuestra implementación Python
TARGET_DISTANCES = [1, 2, 5, 10, 15, 20, 30, 50, 100, 200, 300, 500, 1000]
# Alturas de referencia (columnas 1-8 del MATLAB, no la columna 0 = h=0)
TARGET_HEIGHTS = [10, 20, 37.5, 75, 150, 300, 600, 1200]


def parse_matlab_exceltables(matlab_content: str) -> list[dict]:
    """
    Extrae las 24 tablas del array exceltables del código MATLAB.
    
    Formato MATLAB de cada tabla:
    [78, h1, h2, ..., 0;
     d1, E(d1,h1), E(d1,h2), ...;
     ...
     d78, ...;]
    
    Returns:
        Lista de 24 dicts: {'index': N, 'heights': [...], 'data': {dist: [E,...]}}
    """
    # Encontrar el bloque exceltables = {...}
    start_marker = "exceltables = ..."
    start_idx = matlab_content.find(start_marker)
    if start_idx == -1:
        raise ValueError("No se encontró 'exceltables = ...' en el archivo")
    
    # Buscar el inicio del bloque { 
    brace_start = matlab_content.find('{', start_idx)
    if brace_start == -1:
        raise ValueError("No se encontró '{' después de exceltables")
    
    # Buscar el cierre de la celda MATLAB
    depth = 0
    brace_end = -1
    for i in range(brace_start, min(brace_start + 200000, len(matlab_content))):
        if matlab_content[i] == '{':
            depth += 1
        elif matlab_content[i] == '}':
            depth -= 1
            if depth == 0:
                brace_end = i
                break
    
    if brace_end == -1:
        raise ValueError("No se encontró el cierre '}' de exceltables")
    
    block = matlab_content[brace_start+1:brace_end]
    print(f"Bloque exceltables encontrado: {len(block)} caracteres")
    
    # Estrategia: buscar todas las posiciones donde empieza una tabla [78,
    # El patrón '78,' en el primer elemento indica el número de filas
    # Cada tabla tiene formato [78,h1,h2,...;d1,...;d2,...;]
    
    # Encontrar todos los inicios de tablas con regex
    # Cada tabla empieza con '[' seguido de whitespace/newline* y '78,'
    table_starts = [m.start() for m in re.finditer(r'\[(?:\s*)78,', block)]
    print(f"Número de tablas encontradas: {len(table_starts)}")
    
    tables = []
    for t_idx, t_start in enumerate(table_starts):
        # Encontrar el fin de esta tabla (el ']' que la cierra)
        # Buscar el ']' que no está seguido de otro ']' ni precedido de ';'
        pos = t_start + 1
        bracket_depth = 1
        t_end = -1
        while pos < len(block):
            c = block[pos]
            if c == '[':
                bracket_depth += 1
            elif c == ']':
                bracket_depth -= 1
                if bracket_depth == 0:
                    t_end = pos
                    break
            pos += 1
        
        if t_end == -1:
            print(f"  Advertencia: No se encontró ']' para tabla {t_idx+1}")
            continue
        
        # Extraer contenido de la tabla (sin [ y ])
        table_content = block[t_start+1:t_end]
        
        # Dividir por ';' para obtener filas
        rows_str = table_content.split(';')
        
        # Primera fila: encabezado [78, h1, h2, ..., 0]
        try:
            header_vals = [float(x.strip()) for x in rows_str[0].strip().split(',') if x.strip()]
        except ValueError as e:
            print(f"  Error parseando encabezado tabla {t_idx+1}: {e}")
            continue
        
        if len(header_vals) < 9:
            print(f"  Advertencia: encabezado corto en tabla {t_idx+1}: {header_vals}")
            continue
        
        # header_vals[0] = 78, header_vals[1:9] = alturas [10,20,37.5,75,150,300,600,1200], header_vals[9] = 0
        heights = [float(h) for h in header_vals[1:9]]
        
        # Parsear filas de datos
        data_rows = {}
        for row_str in rows_str[1:]:
            row_str = row_str.strip()
            if not row_str:
                continue
            try:
                vals = [float(x.strip()) for x in row_str.split(',') if x.strip()]
            except ValueError:
                continue
            if len(vals) >= 9:
                dist = vals[0]
                e_values = vals[1:9]  # 8 alturas principales (excluye h=0)
                data_rows[dist] = e_values
        
        tables.append({
            'index': t_idx + 1,
            'heights': heights,
            'data': data_rows
        })
        
        # Mostrar info para tablas de interés
        if t_idx < 3 or t_idx in [8, 16]:
            print(f"\n  Tabla {t_idx+1}: {len(data_rows)} distancias, alturas={heights}")
            if 10.0 in data_rows:
                print(f"    d=10km: {[f'{v:.4f}' for v in data_rows[10.0]]}")
    
    return tables


def extract_target_values(table: dict, target_distances: list, target_heights: list) -> np.ndarray:
    """
    Extrae valores de la tabla en las distancias y alturas objetivo.
    
    Args:
        table: dict con 'data' = {distance: [E_h1, E_h2, ...]}
        target_distances: lista de distancias objetivo [km]
        target_heights: lista de alturas objetivo [m]
    
    Returns:
        ndarray de shape (len(target_distances), len(target_heights))
    """
    table_heights = table['heights']
    table_data = table['data']
    
    # Crear array ordenado de distancias disponibles
    avail_dists = sorted(table_data.keys())
    
    result = np.zeros((len(target_distances), len(target_heights)))
    
    for i, d in enumerate(target_distances):
        # Verificar si la distancia está directamente disponible
        if d in table_data:
            row_values = table_data[d]
        else:
            # Interpolación log-lineal en distancia
            dists_arr = np.array(avail_dists)
            log_d = np.log(d)
            log_dists = np.log(dists_arr)
            idx = np.searchsorted(log_dists, log_d) - 1
            idx = np.clip(idx, 0, len(dists_arr) - 2)
            
            d_lo = dists_arr[idx]
            d_hi = dists_arr[idx + 1]
            alpha = (log_d - np.log(d_lo)) / (np.log(d_hi) - np.log(d_lo))
            alpha = np.clip(alpha, 0, 1)
            
            vals_lo = np.array(table_data[d_lo])
            vals_hi = np.array(table_data[d_hi])
            row_values = vals_lo * (1 - alpha) + vals_hi * alpha
        
        # Ahora interpolar en altura si es necesario
        for j, h in enumerate(target_heights):
            if h in table_heights:
                h_idx = table_heights.index(h)
                result[i, j] = row_values[h_idx]
            else:
                # Interpolación log-lineal en altura
                heights_arr = np.array(table_heights)
                log_h = np.log(h)
                log_heights = np.log(heights_arr)
                idx_h = np.searchsorted(log_heights, log_h) - 1
                idx_h = np.clip(idx_h, 0, len(heights_arr) - 2)
                
                h_lo = heights_arr[idx_h]
                h_hi = heights_arr[idx_h + 1]
                alpha_h = (log_h - np.log(h_lo)) / (np.log(h_hi) - np.log(h_lo))
                alpha_h = np.clip(alpha_h, 0, 1)
                
                result[i, j] = row_values[idx_h] * (1 - alpha_h) + row_values[idx_h + 1] * alpha_h
    
    return result


def generate_python_table_code(name: str, freq: int, matrix: np.ndarray, 
                                 distances: list, heights: list) -> str:
    """Genera código Python para una tabla de referencia ITU."""
    lines = []
    lines.append(f"# Tabla {freq} MHz (extraída de MATLAB ITU-R P.1546-6 v6.2, tabla 50%/Land)")
    lines.append(f"TABLE_{freq}_MHZ = {{")
    
    for i, d in enumerate(distances):
        h_values = ", ".join(f"{h}: {matrix[i, j]:.4f}" for j, h in enumerate(heights))
        lines.append(f"    {d}: {{{h_values}}},")
    
    lines.append("}")
    return "\n".join(lines)


def main():
    print("=" * 60)
    print("Extractor de Tablas ITU-R P.1546-6 desde MATLAB oficial")
    print("=" * 60)
    
    # Leer el archivo MATLAB
    print(f"\nLeyendo: {MATLAB_FILE}")
    content = MATLAB_FILE.read_text(encoding='utf-8', errors='replace')
    print(f"Archivo leído: {len(content)} caracteres, {content.count(chr(10))} líneas")
    
    # Parsear las tablas
    print("\n--- Parseando exceltables ---")
    tables = parse_matlab_exceltables(content)
    
    if len(tables) < 17:
        print(f"ERROR: Solo se encontraron {len(tables)} tablas, se esperaban al menos 17")
        return
    
    # Extraer tablas de interés (indexadas desde 0)
    table_100_50 = tables[0]   # índice 0 = tabla MATLAB 1
    table_600_50 = tables[8]   # índice 8 = tabla MATLAB 9
    table_2000_50 = tables[16] # índice 16 = tabla MATLAB 17
    
    print(f"\n--- Tablas a extraer ---")
    print(f"Tabla 1  (100 MHz, 50%, Land): índice Python {0}, "
          f"distancias disponibles: {sorted(table_100_50['data'].keys())[:5]}...")
    print(f"Tabla 9  (600 MHz, 50%, Land): índice Python {8}, "
          f"distancias disponibles: {sorted(table_600_50['data'].keys())[:5]}...")
    print(f"Tabla 17 (2000 MHz, 50%, Land): índice Python {16}, "
          f"distancias disponibles: {sorted(table_2000_50['data'].keys())[:5]}...")
    
    # Verificar con valor conocido del log de validación ITU
    # flat_10km: d=10km, h_eff=100m, 900 MHz → paso 11: E=69.4618 dBμV/m
    print("\n--- Verificación cruzada ---")
    print("Condición: d=10km, h=100m, 900 MHz, 50%, Land")
    print("Esperado (log ITU): E ≈ 69.46 dBμV/m")
    
    # Extraer valores en d=10km para alturas cercanas a 100m
    if 10 in table_600_50['data']:
        e600_10km = table_600_50['data'][10]
        h_arr = table_600_50['heights']
        print(f"\n600 MHz, d=10km: h={h_arr} → E={[f'{v:.2f}' for v in e600_10km]}")
        # Interpolar a h=100m
        log_75 = np.log(75); log_150 = np.log(150); log_100 = np.log(100)
        idx75 = h_arr.index(75); idx150 = h_arr.index(150)
        alpha = (log_100 - log_75) / (log_150 - log_75)
        e600_h100 = e600_10km[idx75]*(1-alpha) + e600_10km[idx150]*alpha
        print(f"  Interpolado en h=100m: E_600 = {e600_h100:.4f} dBμV/m")
    
    if 10 in table_2000_50['data']:
        e2000_10km = table_2000_50['data'][10]
        h_arr = table_2000_50['heights']
        print(f"\n2000 MHz, d=10km: h={h_arr} → E={[f'{v:.2f}' for v in e2000_10km]}")
        log_75 = np.log(75); log_150 = np.log(150); log_100 = np.log(100)
        idx75 = h_arr.index(75); idx150 = h_arr.index(150)
        alpha = (log_100 - log_75) / (log_150 - log_75)
        e2000_h100 = e2000_10km[idx75]*(1-alpha) + e2000_10km[idx150]*alpha
        print(f"  Interpolado en h=100m: E_2000 = {e2000_h100:.4f} dBμV/m")
    
    # Interpolación a 900 MHz
    fw = np.log(900/600) / np.log(2000/600)
    e900 = e600_h100*(1-fw) + e2000_h100*fw
    print(f"\nInterpolado a 900 MHz (fw={fw:.4f}): E = {e900:.4f} dBμV/m")
    print(f"Referencia ITU log: 69.46 dBμV/m  →  Diferencia: {e900-69.46:.2f} dB")
    
    # ─── Generar matrices corregidas ───
    print("\n--- Generando matrices corregidas ---")
    
    mat_100 = extract_target_values(table_100_50, TARGET_DISTANCES, TARGET_HEIGHTS)
    mat_600 = extract_target_values(table_600_50, TARGET_DISTANCES, TARGET_HEIGHTS)
    mat_2000 = extract_target_values(table_2000_50, TARGET_DISTANCES, TARGET_HEIGHTS)
    
    print("\nE_TABLE_100 (corrected) [dBμV/m]:")
    print(f"  d=10km: {mat_100[3]}")
    print("\nE_TABLE_600 (corrected) [dBμV/m]:")
    print(f"  d=10km: {mat_600[3]}")
    print("\nE_TABLE_2000 (corrected) [dBμV/m]:")
    print(f"  d=10km: {mat_2000[3]}")
    
    # ─── Generar código Python para reemplazo ───
    print("\n--- Generando código Python ---")
    
    code_100 = generate_python_table_code("TABLE_100", 100, mat_100, TARGET_DISTANCES, TARGET_HEIGHTS)
    code_600 = generate_python_table_code("TABLE_600", 600, mat_600, TARGET_DISTANCES, TARGET_HEIGHTS)
    code_2000 = generate_python_table_code("TABLE_2000", 2000, mat_2000, TARGET_DISTANCES, TARGET_HEIGHTS)
    
    output_path = Path(r"g:\My Drive\Universidad\Tesis\validaciones\tablas_corregidas.py")
    output_path.write_text(
        "# Tablas ITU-R P.1546-6 extraídas del MATLAB oficial (50%/Land)\n"
        "# Generadas por validaciones/extract_matlab_tables.py\n"
        "# Fuente: exceltables{1}, {9}, {17} de P1546FieldStrMixed.m\n\n"
        + code_100 + "\n\n" + code_600 + "\n\n" + code_2000 + "\n"
    )
    print(f"\nTablas guardadas en: {output_path}")
    
    # ─── Comparación antes/después para condición de verificación ───
    print("\n--- Resumen de corrección ---")
    print(f"{'Condición':<30} {'ANTES (Python)':<18} {'DESPUÉS (MATLAB)':<18} {'Δ'}")
    print("-" * 80)
    
    # d=10km, h=75m, 600 MHz
    old_600_10_75 = 130.4  # Valor actual en TABLE_600_MHZ[10][75]
    new_600_10_75 = mat_600[3, 3]  # distancia índice 3 (d=10km), altura índice 3 (h=75m)
    print(f"{'600MHz d=10km h=75m':<30} {old_600_10_75:<18.1f} {new_600_10_75:<18.2f} {new_600_10_75-old_600_10_75:.1f} dB")
    
    # d=10km, h=75m, 100 MHz
    old_100_10_75 = 124.0  # Valor actual en TABLE_100_MHZ[10][75]
    new_100_10_75 = mat_100[3, 3]
    print(f"{'100MHz d=10km h=75m':<30} {old_100_10_75:<18.1f} {new_100_10_75:<18.2f} {new_100_10_75-old_100_10_75:.1f} dB")
    
    # d=10km, h=75m, 2000 MHz
    old_2000_10_75 = 140.0  # Valor actual
    new_2000_10_75 = mat_2000[3, 3]
    print(f"{'2000MHz d=10km h=75m':<30} {old_2000_10_75:<18.1f} {new_2000_10_75:<18.2f} {new_2000_10_75-old_2000_10_75:.1f} dB")
    
    print("\n✓ Extracción completada exitosamente")
    print(f"  Las tablas corregidas están en: {output_path}")
    print(f"  Próximo paso: reemplazar TABLE_100/600/2000_MHZ en")
    print(f"  src/core/models/traditional/itu_r_p1546_tables.py")


if __name__ == "__main__":
    main()
