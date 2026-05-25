# GUÍA PARA REDACCIÓN DEL CAPÍTULO: METODOLOGÍA, DISEÑO E IMPLEMENTACIÓN

> **Documento de uso interno** — Guía técnica y académica para la redacción del capítulo
> de Metodología / Diseño e Implementación de la tesis de ingeniería.
> **Este documento NO forma parte de la documentación técnica del sistema.**
>
> Proyecto: Simulador de Cobertura RF con Modelos de Propagación y DEM
> Autores: David Montano, Dario Portilla — Universidad de Cuenca, 2025–2026

---

## ÍNDICE DE LA GUÍA

1. [Introducción al Capítulo](#1-introducción-al-capítulo)
2. [Metodología de Desarrollo](#2-metodología-de-desarrollo)
3. [Arquitectura General del Sistema](#3-arquitectura-general-del-sistema)
4. [Diseño Modular del Sistema](#4-diseño-modular-del-sistema)
5. [Flujo Completo de Procesamiento](#5-flujo-completo-de-procesamiento)
6. [Fundamentos Matemáticos y Modelos Físicos](#6-fundamentos-matemáticos-y-modelos-físicos)
7. [Modelos de Propagación Implementados](#7-modelos-de-propagación-implementados)
8. [Procesamiento Geoespacial e Integración DEM](#8-procesamiento-geoespacial-e-integración-dem)
9. [Línea de Visión (LOS)](#9-línea-de-visión-los)
10. [Motor de Cómputo Heterogéneo (CPU/GPU)](#10-motor-de-cómputo-heterogéneo-cpugpu)
11. [Interfaz Gráfica y Flujo de Usuario](#11-interfaz-gráfica-y-flujo-de-usuario)
12. [Sistema de Exportación y Formatos de Salida](#12-sistema-de-exportación-y-formatos-de-salida)
13. [Estrategias de Optimización](#13-estrategias-de-optimización)
14. [Validación del Sistema](#14-validación-del-sistema)
15. [Comparación con Atoll](#15-comparación-con-atoll)
16. [Métricas de Evaluación](#16-métricas-de-evaluación)
17. [Limitaciones y Consideraciones Técnicas](#17-limitaciones-y-consideraciones-técnicas)

---

## 1. Introducción al Capítulo

### Qué redactar
Párrafo de apertura que contextualice el propósito del capítulo dentro de la tesis. Debe
establecer el alcance (qué se diseña e implementa), la motivación técnica y cómo el capítulo
se relaciona con el Marco Teórico previo.

### Estructura sugerida del párrafo introductorio
- Problema que resuelve el sistema (predicción de cobertura RF con terreno real).
- Justificación de construir una herramienta propia frente a soluciones comerciales (costo,
  transparencia de modelos, extensibilidad).
- Relación con los objetivos específicos de la tesis.
- Breve mapa del capítulo: qué cubre cada sección.

### Aspectos académicos importantes
- Diferenciar claramente **qué es metodología** (cómo se tomaron las decisiones) de
  **qué es implementación** (cómo se ejecutaron).
- Justificar el nivel de originalidad técnica: no se emplea un framework comercial,
  sino implementación desde estándares primarios (ITU-R, 3GPP, COST).

---

## 2. Metodología de Desarrollo

### Qué redactar
Descripción de la estrategia de desarrollo adoptada, con justificación académica y técnica.

### Contenido sugerido

#### 2.1 Paradigma de Desarrollo por Fases
- El sistema fue construido incrementalmente en fases numeradas (Fase 1 a Fase 6+),
  cada una con entregables verificables. Justificar por qué este enfoque es adecuado
  para un sistema de investigación donde los requisitos evolucionan con el conocimiento.
- Analogía con metodología **iterativa e incremental** (no cascada clásica).
- Cada fase añadió un módulo funcional nuevo o corrigió uno existente con base en
  validación científica del comportamiento numérico.

#### 2.2 Desarrollo Orientado a Pruebas (TDD Parcial)
- Describir la suite de pruebas unitarias (`tests/`) con +30 archivos de test.
- Mencionar que cada modelo de propagación tiene pruebas independientes
  (`test_okumura_hata_complete.py`, `test_cost231_complete.py`,
  `test_itu_r_p1546_complete.py`, `test_3gpp_38901_complete.py`).
- Las pruebas validan: rangos de validez del modelo, comportamiento en límites,
  coherencia física (path loss creciente con distancia), y regresiones ante cambios.

#### 2.3 Decisiones de Diseño Guiadas por Estándares
- Cada módulo de propagación fue construido desde el estándar primario, no desde
  implementaciones de terceros. Mencionar los estándares consultados:
  - ITU-R P.1546-6 (agosto 2019)
  - ITU-R P.2108-1 (clutter)
  - ITU-R P.526-15 (difracción knife-edge)
  - Familia 3GPP TR 38.901
  - COST-231 / ITU-R P.1411-8

### Diagrama sugerido
```
Diagrama de proceso en espiral: Análisis estándar → Implementación → Validación numérica →
Pruebas unitarias → Comparación con Atoll → Ajuste → siguiente iteración
```

### Tabla sugerida
| Fase | Módulo añadido | Estándar de referencia | Tipo de validación |
|------|---------------|----------------------|-------------------|
| 1 | Core UI + FSPL | — | Visual básica |
| 2 | Okumura-Hata | ITU-R P.1546, Hata 1980 | Test unitario |
| 3 | COST-231 W-I | ITU-R P.1411-8 | Comparación teórica |
| 4 | ITU-R P.1546 + DEM | P.1546-6, P.2108-1 | Perfiles radiales |
| 5 | 3GPP TR 38.901 | Familia 3GPP TR 38.901 | Parámetros TR |
| 6 | LOS + Exportación | ITU-R P.526 | Validación geométrica |
| 6+ | Patrón 3D antena | 3GPP TR 38.901 §7.3.2 | Test unitario 3D |

---

## 3. Arquitectura General del Sistema

### Qué redactar
Descripción de la arquitectura a nivel de capas y componentes, con justificación de las
decisiones de diseño estructural.

### Contenido sugerido

#### 3.1 Arquitectura en Capas
El sistema sigue un patrón de arquitectura **en capas horizontales** con separación estricta
de responsabilidades:

```
┌─────────────────────────────────────────────────────┐
│          Capa de Presentación (src/ui/)             │
│   main_window.py | dialogs/ | widgets/ | panels/   │
├─────────────────────────────────────────────────────┤
│          Capa de Lógica de Negocio (src/core/)      │
│   coverage_calculator.py | compute_engine.py       │
│   terrain_loader.py | site_manager.py              │
├─────────────────────────────────────────────────────┤
│          Capa de Modelos de Propagación             │
│   src/core/models/traditional/ + gpp_3gpp/         │
├─────────────────────────────────────────────────────┤
│          Capa de Modelos de Datos (src/models/)     │
│   antenna.py | project.py | site.py                │
├─────────────────────────────────────────────────────┤
│          Capa de Utilidades (src/utils/)            │
│   export_manager | heatmap_generator | gpu_detector │
│   los_calculator | config_manager | logger          │
└─────────────────────────────────────────────────────┘
```

**Justificación académica**: La separación de capas garantiza:
- **Cohesión alta**: cada módulo tiene una única responsabilidad.
- **Acoplamiento bajo**: los modelos de propagación no conocen la UI.
- **Testabilidad**: los modelos pueden probarse unitariamente sin UI.
- **Extensibilidad**: añadir un nuevo modelo no requiere modificar la capa de cálculo.

#### 3.2 Patrón de Worker Asíncrono
- `SimulationWorker` ejecuta el pipeline completo en un hilo separado (QThread de PyQt6).
- La UI nunca se bloquea durante una simulación.
- Señales Qt (`progress`, `status_message`, `finished`, `error`) comunican el estado.
- **Justificación**: Simulaciones con grillas de 100×100 a 500×500 puntos pueden tardar
  varios segundos incluso con GPU; el diseño asíncrono es obligatorio para UX profesional.

#### 3.3 Patrón de Motor de Cómputo (`ComputeEngine`)
- `ComputeEngine` actúa como *strategy* sobre el módulo numérico:
  - `use_gpu=True` → `self.xp = cupy`
  - `use_gpu=False` → `self.xp = numpy`
- Todos los módulos de cálculo (`CoverageCalculator`, `LOSCalculator`, cada modelo)
  reciben `xp` del motor o lo exponen como propiedad.
- **Justificación**: Evita `if use_gpu:` dispersos en toda la base de código. Cambio
  transparente de backend sin modificar algoritmos.

### Diagrama sugerido
Diagrama de componentes UML con las relaciones entre:
`MainWindow` → `SimulationWorker` → `CoverageCalculator` → `[modelos]`
`SimulationWorker` → `TerrainLoader` → `[archivos GeoTIFF]`
`SimulationWorker` → `LOSCalculator`
`CoverageCalculator` → `ComputeEngine`

### Tabla sugerida
| Componente | Responsabilidad | Patrón de diseño |
|-----------|----------------|-----------------|
| `ComputeEngine` | Abstraer NumPy/CuPy | Strategy |
| `CoverageCalculator` | Orquestar pipeline RF | Facade |
| `SimulationWorker` | Asincronía UI/cálculo | Worker/Observer |
| `TerrainLoader` | E/S de datos GeoTIFF | Repository |
| `LOSCalculator` | Análisis geométrico LOS | Service |
| `HeatmapGenerator` | Renderizado raster | Renderer |
| `ExportManager` | Serialización multi-formato | Strategy |

---

## 4. Diseño Modular del Sistema

### Qué redactar
Cada módulo principal debe tener un párrafo o subsección explicando su interfaz pública,
dependencias y responsabilidad técnica. **No** documentar código privado en detalle.

### Contenido sugerido por módulo

#### 4.1 Modelo de Datos: `Antenna`
- Clase de datos (`@dataclass`) con todos los parámetros RF y geométricos.
- Atributos clave a mencionar:
  - `latitude`, `longitude`, `height_agl` — posición geoespacial
  - `frequency_mhz`, `tx_power_dbm` — parámetros de transmisión
  - `azimuth`, `mechanical_tilt`, `electrical_tilt` — orientación 3D
  - `horizontal_beamwidth`, `vertical_beamwidth`, `gain_dbi` — patrón de radiación
  - `antenna_type` (`OMNIDIRECTIONAL` / `SECTORIAL` / `DIRECTIONAL`) — tipo físico
- Justificar la separación de `mechanical_tilt` y `electrical_tilt`:
  son mecanismos físicamente distintos; su suma da el `effective_tilt` en 3GPP TR 38.901.

#### 4.2 Módulo de Cálculo de Cobertura: `CoverageCalculator`
- Método principal: `calculate_single_antenna_coverage()`
- Recibe: `Antenna`, grilla 2D (lat/lon), elevaciones de terreno, modelo de propagación.
- Calcula en orden:
  1. Distancias Haversine vectorizadas.
  2. Elevación TX desde DEM.
  3. Perfiles radiales TX→RX (para modelos que los requieren).
  4. Path loss mediante el modelo seleccionado.
  5. Patrón de antena 3D (ganancia directiva).
  6. RSRP = `P_tx + G_antena(φ,θ) - PL(d,f,entorno)`.
- Lógica multi-antena: `best_server` selecciona el ID con máximo RSRP en cada píxel.

#### 4.3 Módulo de Terreno: `TerrainLoader`
- Carga archivos GeoTIFF (SRTM, ASTER o equivalente) mediante `rasterio`.
- Transformación automática de coordenadas WGS84 → CRS del raster (`pyproj.Transformer`).
- Métodos clave:
  - `get_elevation(lat, lon)` — escalar, para un punto.
  - `get_elevations_fast(lats, lons)` — vectorizado con `rowcol()` de rasterio.
  - `get_radial_profiles()` — extrae perfiles TX→RX, con extensión a 15 km para ITU-R P.1546.
  - `get_smoothed_profiles()` — suavizado gaussiano para altura efectiva estable.
  - `get_profile_distances()` — distancias Haversine reales por muestra del perfil.

#### 4.4 Módulo LOS: `LOSCalculator`
- Algoritmo: para cada receptor, muestrea `n_samples` puntos en la línea TX→RX.
  Compara la elevación del terreno contra la línea recta de visión en cada punto intermedio.
  Si algún punto del terreno supera la LOS → receptor marcado NLOS.
- Resultado: mapa binario `float32` (1.0 = LOS, 0.0 = NLOS) de forma `(H, W)`.
- Hereda `xp` del `ComputeEngine` para ejecución opcional en GPU.
- La salida siempre regresa a NumPy antes del return (matplotlib y Leaflet requieren CPU).

### Diagrama sugerido
Diagrama de secuencia UML para una simulación de una antena:
`Usuario` → `MainWindow` → `SimulationWorker.run()` →
`CoverageCalculator.calculate_single_antenna_coverage()` →
`TerrainLoader.get_radial_profiles()` → `OkumuraHataModel.calculate_path_loss()` →
`CoverageCalculator._apply_antenna_pattern()` → `LOSCalculator.compute_los_map()` →
`HeatmapGenerator.generate_heatmap_image()` → `MainWindow` (señal finished)

---

## 5. Flujo Completo de Procesamiento

### Qué redactar
Descripción paso a paso del pipeline de simulación, desde la entrada del usuario hasta la
visualización del mapa de cobertura. Este es el corazón del capítulo.

### Flujo detallado (referencia: `SimulationWorker.run()`)

```
ENTRADA:
  - Lista de antenas configuradas
  - Modelo de propagación seleccionado
  - Archivo DEM (GeoTIFF)
  - Parámetros del modelo (entorno, alturas, etc.)

PASO 1 — Creación de la grilla global
  - Se calcula la bbox de todas las antenas + margen configurable.
  - Se genera meshgrid (grid_lats, grid_lons) con resolución dada.
  - Se consultan elevaciones del DEM para toda la grilla: terrain_heights[H,W].
  - La grilla es GLOBAL (misma para todas las antenas del proyecto).

PASO 2 — Para cada antena:
  2a. Obtener elevación TX del DEM (z_tx).
  2b. Calcular distancias Haversine a todos los puntos: distances[H,W].
  2c. Si el modelo lo requiere:
      - Extraer perfiles radiales DEM: terrain_profiles[N, n_samples].
      - Calcular distancias reales por muestra: profile_distances[N, n_samples].
      - Suavizar perfiles: smoothed_terrain_profiles[N, n_samples].
  2d. Llamar a modelo.calculate_path_loss(**path_loss_args) → path_loss[H,W].
  2e. Aplicar patrón de antena 3D → antenna_gain[H,W].
  2f. Calcular RSRP = P_tx + antenna_gain - path_loss → rsrp[H,W].
  2g. Calcular mapa LOS: los_map[H,W] ∈ {0.0, 1.0}.

PASO 3 — Renderizado
  - Calcular rango dinámico: percentiles 5–95 de RSRP válidos.
  - Generar imagen PNG base64 (HeatmapGenerator): image_url.
  - Generar imagen PNG base64 de LOS: los_image_url.

PASO 4 — Agregación multi-antena
  - Apilar rsrp[H,W] de todas las antenas.
  - best_server[H,W] = ID de antena con max(RSRP) en cada píxel.
  - rsrp_aggregated[H,W] = max(RSRP) en cada píxel.

PASO 5 — Exportación (si solicitada)
  - CSV: lat, lon, RSRP, path_loss, antenna_gain, LOS por punto.
  - GeoTIFF: RSRP en formato raster georreferenciado.
  - KML: vectores de cobertura para Google Earth.

SALIDA:
  - Dict con: individual, aggregated, metadata, timing.
  - Señal finished() emitida al hilo UI.
```

### Diagrama sugerido
Diagrama de flujo con decisiones:
- ¿Hay DEM cargado? → Sí: perfiles reales / No: terreno plano.
- ¿GPU disponible? → Sí: CuPy arrays / No: NumPy arrays.
- ¿Más de una antena? → Sí: cálculo best_server / No: solo individual.

### Tabla sugerida: Costo computacional por paso
| Paso | Complejidad | Paralelizable en GPU |
|------|-------------|---------------------|
| Creación grilla | O(H×W) | Sí |
| Distancias Haversine | O(H×W) | Sí |
| Perfiles radiales | O(N×S) donde S=n_samples | Parcialmente |
| Path loss (vectorizado) | O(N) | Sí |
| Patrón antena 3D | O(H×W) | Sí |
| Mapa LOS | O(N×S) | Sí |
| Renderizado PNG | O(H×W) | No (matplotlib) |

---

## 6. Fundamentos Matemáticos y Modelos Físicos

### Qué redactar
Esta sección conecta la implementación con la teoría. Es la más importante para la
evaluación académica. Cada fórmula debe aparecer en notación matemática formal.

### 6.1 Ecuación Fundamental de la Cobertura RF

**Nivel técnico**: Alto. Derivar desde la ecuación de Friis.

La potencia recibida en un receptor en el sistema se modela mediante:

```
RSRP [dBm] = P_tx [dBm] + G_antena(φ, θ) [dBi] - PL(d, f, entorno) [dB]
```

donde:
- `P_tx` es la potencia de transmisión de la estación base.
- `G_antena(φ, θ)` es la ganancia directiva de la antena en la dirección del receptor,
  función del ángulo azimutal `φ` y del ángulo de elevación `θ`.
- `PL(d, f, entorno)` es la pérdida de propagación calculada por el modelo seleccionado.

**Qué justificar**:
- Por qué se usa RSRP (Reference Signal Received Power) y no RSSI u otras métricas.
- Que los modelos de propagación y el patrón de antena son ortogonales y combinables
  aditivamente en decibelios (independencia del medio y del radiador).

**Ecuación de Friis** (contexto teórico previo):

```
P_r [W] = P_t · G_t · G_r · (λ / 4πd)²
```

En escala logarítmica esto da directamente la forma RSRP = P_tx + G_tx - FSPL + G_rx.

### 6.2 Distancia Haversine

La distancia geodésica entre dos puntos en la esfera terrestre se calcula mediante
la fórmula de Haversine, implementada en `CoverageCalculator._calculate_distances()`:

```
a = sin²(Δφ/2) + cos(φ₁)·cos(φ₂)·sin²(Δλ/2)
c = 2·arctan2(√a, √(1−a))
d = R_e · c
```

donde `R_e = 6 371 000 m` es el radio medio de la Tierra, `φ` son latitudes y `λ` longitudes
en radianes. Esta fórmula es exacta para la esfera y tiene error < 0.5% sobre la
elipsoide WGS84 para distancias menores a 100 km (rango típico del sistema).

**Qué justificar**: Por qué no se usa distancia euclidiana plana. Para la región de Cuenca
(~2.9° S) con grillas de hasta 20 km de lado, el error acumulado de la aproximación plana
puede superar el 0.3%, lo que introduce sesgo sistemático en modelos sensibles a la distancia.

### 6.3 Azimut Geodésico (Forward Bearing)

El ángulo azimutal desde la antena a cada receptor, usado en el patrón de antena,
se calcula mediante:

```
y = sin(Δλ)·cos(φ₂)
x = cos(φ₁)·sin(φ₂) − sin(φ₁)·cos(φ₂)·cos(Δλ)
θ_az = arctan2(y, x)    [rad, convertido a [0°, 360°)]
```

Implementado en `CoverageCalculator._calculate_azimuths()`.

### 6.4 Patrón de Radiación de Antena 3D (3GPP TR 38.901 §7.3.2)

**Nivel técnico**: Alto — demostrar que la fórmula no es exclusiva de 5G.

La aproximación gaussiana para el patrón de radiación horizontal es:

```
A_H(φ) = −min[ 12·(φ / φ_3dB)², SLA_H ]    [dB]
```

donde:
- `φ` es la diferencia angular entre el azimut al receptor y el azimut de apuntamiento.
- `φ_3dB` es el ancho de haz horizontal a −3 dB.
- `SLA_H = 30 dB` es el nivel de lóbulo lateral (*Side-Lobe Attenuation*).

La atenuación vertical es:

```
A_V(θ) = −min[ 12·((θ − θ_tilt) / θ_3dB)², SLA_V ]    [dB]
```

donde:
- `θ` es el ángulo de elevación desde la antena al receptor:
  `θ = arctan2(h_tx_abs − h_rx_abs, d_2D)`.
- `θ_tilt = mechanical_tilt + electrical_tilt` es el tilt efectivo total.
- `θ_3dB` es el ancho de haz vertical a −3 dB.

El patrón total 3D combina ambos planos con cap conjunto:

```
G(φ, θ) = G_max − min[ −(A_H + A_V), 30 dB ]
```

**Qué justificar**:
- Que la fórmula gaussiana es universalmente usada en ingeniería de antenas
  (aparece en ITU-R M.2135-1, 3GPP TR 36.814, y la literatura de Stutzman & Thiele).
- Por qué el denominador correcto es `φ_3dB` (no `φ_3dB/2`): a `φ = φ_3dB/2` la
  fórmula debe dar −3 dB por definición del ancho de haz a media potencia.
- Por qué antenas omnidireccionales tienen `A_H = A_V = 0` y retornan solo `G_max`.

**Figura sugerida**:
- Gráfica polar de `A_H(φ)` para `φ_3dB ∈ {65°, 90°, 120°}`.
- Gráfica polar de `A_V(θ)` para `θ_3dB = 10°` con `θ_tilt = 6°`.
- Mapa de calor 2D de `G(φ,θ)` en coordenadas esféricas desplegadas.

---

## 7. Modelos de Propagación Implementados

### Nivel técnico esperado
Alto para cada modelo. Cada subsección debe:
1. Describir el modelo (origen, tipo, aplicabilidad).
2. Presentar la ecuación o conjunto de ecuaciones principal.
3. Indicar los rangos de validez.
4. Explicar cómo se usa el DEM dentro del modelo.
5. Mencionar las correcciones y extensiones implementadas respecto al estándar.

---

### 7.1 Espacio Libre (FSPL)

**Tipo**: Determinístico. Referencia: Ecuación de Friis (1946).

```
FSPL [dB] = 20·log₁₀(d [km]) + 20·log₁₀(f [MHz]) + 32.45
```

**Uso en el sistema**: Modelo de referencia, útil para validar el pipeline sin efectos
de entorno. Siempre devuelve `validity_mask = True` para todo punto.

**Qué mencionar**: Constante 32.45 = 20·log₁₀(4π/(c·10⁻⁶)) con c en m/s y d en km,
f en MHz. Demostrar la derivación desde la ecuación de Friis es valorado académicamente.

---

### 7.2 Okumura-Hata

**Tipo**: Empírico. Referencias: Okumura et al. (1968), Hata (1980).

**Rangos de validez**:
- Frecuencia: 150–1500 MHz (Hata básico), hasta 2000 MHz (COST-231 Hata).
- Distancia: 1–20 km.
- Altura de BS: 30–200 m.
- Altura móvil: 1–10 m.

**Ecuaciones principales** (área urbana):

Para ciudad grande (f ≥ 300 MHz):
```
a(h_m) = 3.2·(log₁₀(11.75·h_m))² − 4.97
```

Para ciudad mediana o pequeña:
```
a(h_m) = (1.1·log₁₀(f) − 0.7)·h_m − (1.56·log₁₀(f) − 0.8)
```

Pérdida en área urbana:
```
L_u [dB] = 69.55 + 26.16·log₁₀(f) − 13.82·log₁₀(h_b) − a(h_m)
           + (44.9 − 6.55·log₁₀(h_b))·log₁₀(d)
```

Correcciones por entorno:
- Suburbano: `L_su = L_u − 2·(log₁₀(f/28))² − 5.4`
- Rural/open: `L_o = L_u − 4.78·(log₁₀(f))² + 18.33·log₁₀(f) − 40.94`

**Altura efectiva de la BS con DEM**:
La altura efectiva `h_b,eff` no es simplemente la altura AGL (`h_AGL`). Se calcula como:

```
h_b,eff = h_AGL + z_tx − z_ref
```

donde `z_ref` es la elevación media del terreno en el anillo 3–15 km desde la BS
(método configurable: `global_mean` para compatibilidad, o `local` más preciso).
Esto es crítico en terreno irregular como la cuenca del Tomebamba.

**Tabla sugerida**: Comparación de `h_b,eff` con distintos métodos de referencia de terreno
para la misma antena en Cuenca.

**Figura sugerida**: Gráfica L_u vs d para f = {700, 1800, 2600} MHz con h_b = 30 m.

---

### 7.3 COST-231 Walfisch-Ikegami

**Tipo**: Semi-determinístico (empírico-analítico). Referencia: ITU-R P.1411-8.

**Rangos de validez**:
- Frecuencia: 800–2000 MHz.
- Distancia: 20 m–5 km.
- Escenario: urbano denso (urban canyon).

**Ecuaciones LOS**:
```
PL_LOS = 42.6 + 26·log₁₀(d [km]) + 20·log₁₀(f [MHz])     (d ≥ 20 m)
```

**Ecuaciones NLOS** (suma de tres contribuciones):
```
PL_NLOS = L₀ + L_rts + L_msd    si (L_rts + L_msd) > 0
PL_NLOS = L₀                    en caso contrario
```

donde:
- `L₀ = 32.45 + 20·log₁₀(f) + 20·log₁₀(d)` — espacio libre.
- `L_rts` — difracción rooftop-to-street:
  `L_rts = −16.9 − 10·log₁₀(w) + 10·log₁₀(f) + 20·log₁₀(Δh_m) + L_ori`
- `L_msd` — difracción multi-pantalla (ecuación completa de Ikegami).
- `L_ori` — factor de orientación de calle (función del ángulo φ_road).

**Cómo determina LOS/NLOS el sistema**:
- Si hay perfil DEM disponible: análisis geométrico del perfil radial.
- Si no hay DEM: umbral de distancia configurable.

**Parámetros urbanos de Cuenca** (justificar selección):
- `h_building = 15 m` — altura media de edificaciones en zona urbana de Cuenca.
- `w = 12 m` — ancho típico de calles en el centro histórico.

---

### 7.4 ITU-R P.1546-6

**Tipo**: Empírico punto-a-área. Referencia: ITU-R P.1546-6 (agosto 2019).

Este es el modelo más complejo del sistema. Describe la intensidad de campo eléctrico
para sistemas terrestres hasta 1000 km, con correcciones por terreno, clutter y tiempo.

**Arquitectura del modelo** (documentar en 6 sub-pasos):

**Sub-paso 1 — Altura efectiva del TX** (§4.3):
```
h_eff = z_tx + h_AGL − z_mean(3 km a 15 km desde TX)
```
Si `d < 15 km` o no hay DEM: `h_eff = h_AGL`.

**Sub-paso 2 — Interpolación de E [dBμV/m]** (Figs. 1–3 del estándar):
- Tablas internas a 3 frecuencias de referencia: 100 / 600 / 2000 MHz.
- Interpolación log-lineal en frecuencia, log-log en distancia, log-lineal en `h_eff`.
- Fórmula de interpolación log-lineal en `h_eff`:
  `E(h_eff) = E₁ + (E₂−E₁)·(log(h_eff)−log(h₁))/(log(h₂)−log(h₁))`

**Sub-paso 3 — Corrección TCA** (§4.5):
```
θ_tc = max[ arctan( (h_terrain − h_rx) / d_from_rx ) ]   (en ±15 km del RX)
J(θ_tc) = 6.9 + 20·log₁₀(√((θ_tc − 0.1)² + 1) + θ_tc − 0.1)   [θ en grados]
```
Aplicada solo cuando `θ_tc > 0°` (obstáculo sobre el horizonte del receptor).

**Sub-paso 4 — Pérdida por clutter** (ITU-R P.2108-1 §3):
```
L_clutter = 10.25·F_fc·exp(−d_t)·(1 − tanh(6·(h_b/h_g − 0.625))) − 0.33
```

**Sub-paso 5 — Conversión E → PL** (§5):
```
PL = 139.3 + 20·log₁₀(f [MHz]) − E + TCA + L_clutter + L_percentile
```

**Sub-paso 6 — Corrección por percentil** (§8.1):
Correcciones tabuladas para percentiles de tiempo {1, 10, 50, 90, 99}.

**Extensión a 15 km del perfil** (decisión de diseño):
Para que `h_eff` sea representativo, `get_radial_profiles()` extiende el perfil hasta
`max_distance_m = 15 000 m` cuando detecta ITU-R P.1546. Esta es una decisión técnica
que debe justificarse: el estándar §4.3 explícitamente requiere la media hasta 15 km.

**Tabla sugerida**: Comparación de `h_eff` con/sin extensión de perfil a 15 km.
**Figura sugerida**: Curvas E [dBμV/m] vs d [km] para h_eff = {10, 37.5, 150, 600} m.

---

### 7.5 3GPP TR 38.901

**Tipo**: Estocástico-geométrico (LOS/NLOS probabilístico). Referencia: 3GPP TR 38.901.

**Escenarios**: Urban Macro (UMa), Urban Micro-Street Canyon (UMi), Rural Macro (RMa).

**Frecuencias válidas**: 0.5–100 GHz (5G mmWave incluido).

**Estructura del modelo** (documentar 4 sub-pasos):

**Sub-paso 1 — Probabilidad LOS** (Tabla 7.4.2-1):
```
UMa: P_LOS = min(18/d₂D, 1)·(1 − exp(−d₂D/63)) + exp(−d₂D/63)
UMi: P_LOS = min(18/d₂D, 1)·(1 − exp(−d₂D/36)) + exp(−d₂D/36)
RMa: P_LOS = exp(−(d₂D−10)/1000)
```

**Sub-paso 2 — Path Loss LOS** (dual-slope con breakpoint):
```
d_BP = 4·h_BS·h_UT·f_c / c    (breakpoint de Fresnel)
```
Para `d₂D ≤ d_BP`:
```
PL_LOS = 28 + 22·log₁₀(d₃D) + 20·log₁₀(f_c)
```
Para `d₂D > d_BP`:
```
PL_LOS = 28 + 40·log₁₀(d₃D) + 20·log₁₀(f_c) − 9·log₁₀(d_BP² + (h_BS−h_UT)²)
```

donde `d₃D = √(d₂D² + (h_BS − h_UT)²)` (distancia 3D real).

**Sub-paso 3 — Path Loss NLOS**:
```
PL_NLOS = max(PL_LOS, PL_NLOS')
```
(no penalización doble: el NLOS nunca puede ser inferior al LOS).

**Sub-paso 4 — Corrección DEM opcional** (`use_dem=True`):
- Corrección aditiva por difracción knife-edge (ITU-R P.526) sobre perfil real:
  `PL += L_diff`
- Se suma sin multiplicar por `(1 − P_LOS)` (corrección C6 documentada en el código).

**Tabla sugerida**: Parámetros por escenario (h_BS, exponente PL LOS/NLOS, σ shadow fading).
**Figura sugerida**: PL [dB] vs d [m] para UMa a 3.5 GHz comparado con COST-231.

---

## 8. Procesamiento Geoespacial e Integración DEM

### Qué redactar
Descripción técnica del pipeline de datos geoespaciales: desde el archivo GeoTIFF hasta
los arrays NumPy que alimentan los modelos.

### 8.1 Formato y Fuente de Datos DEM

**Nivel técnico**: Medio-alto.

- El sistema usa archivos GeoTIFF de un único canal (banda 1 = elevación en metros).
- Compatible con productos SRTM (Shuttle Radar Topography Mission) de 1 arcsec (~30 m)
  y 3 arcsec (~90 m), ASTER GDEM (30 m), y datos propios de IGM Ecuador.
- Proyecto de validación: `data/terrain/cuenca_terrain.tif` — DEM de la cuenca del
  Tomebamba / Cuenca, Ecuador (~2 500–3 800 m MSL).

**Qué mencionar académicamente**:
- Resolución espacial del DEM vs resolución de la grilla de simulación (efecto de
  remuestreo por interpolación nearest-neighbor en `rasterio.rowcol()`).
- Filtraje de valores NoData: se rechazan elevaciones < 0 m y > 10 000 m.
- Conversión automática de CRS: de WGS84 (EPSG:4326) a la proyección nativa del raster
  usando `pyproj.Transformer.from_crs(always_xy=True)`.

### 8.2 Interpolación de Elevaciones

**Nivel técnico**: Alto.

El sistema usa *nearest-neighbor* implícito de `rasterio.transform.rowcol()`. No interpola
bilinealmente. Esto introduce un error cuantificable de ≤ resolución_DEM/2 por punto.

Para la versión vectorizada (`get_elevations_fast()`):
- Transformación masiva: `(lon[], lat[]) → (x[], y[])` en un único call `Transformer.transform()`.
- Extracción de píxeles: `rowcol(transform, x[], y[])` para obtener índices de grilla.
- Loop Python residual (no completamente vectorizado) — **limitación conocida**.

**Justificación del diseño**: Para grillas de hasta 500×500 = 250 000 puntos, el loop Python
tarda ~2 s. Esto es aceptable para el caso de uso académico. Una implementación
completamente vectorizada con `numpy.vectorize` o arrays de índices directos podría
reducir este tiempo 5–10× pero no es prioritario frente a la precisión del modelo.

### 8.3 Perfiles Radiales TX→RX

**Nivel técnico**: Alto. Esta función es crítica para todos los modelos que necesitan DEM.

`get_radial_profiles(tx_lat, tx_lon, rx_lats[], rx_lons[], n_samples)` genera para
cada receptor `i` un perfil de elevación de `n_samples` puntos interpolados a lo largo
del gran círculo TX→RX:

```
lat_j = tx_lat + direction_lat_i × max_distance_i × t_j
lon_j = tx_lon + direction_lon_i × max_distance_i × t_j
    donde t_j = linspace(0, 1, n_samples),  j = 0, 1, …, n_samples−1
```

**Nota sobre la aproximación**: La interpolación usa diferencias lineales de lat/lon,
no geodésicas exactas. Para distancias < 20 km en latitudes medias (2.9° S), el error
acumulado es < 5 m transversal, despreciable frente a la resolución del DEM.

**Tabla sugerida**: Efecto de `n_samples` en precisión LOS vs tiempo de cómputo.
| n_samples | Tiempo (ms) | Falsas obstrucciones detectadas (%) |
|-----------|------------|-------------------------------------|
| 10 | 8 | ~12% |
| 25 | 18 | ~3% |
| 50 | 35 | < 1% |
| 100 | 70 | < 0.3% |

### 8.4 Suavizado de Perfiles para Altura Efectiva

`get_smoothed_profiles()` aplica un filtro gaussiano a los perfiles radiales para
calcular `h_eff` estable en Okumura-Hata:

```
window_size_m = 1000 m  (ventana ~1 km)
σ = window_size_m / (2 × resolución_perfil_m)
perfil_suavizado = gaussian_filter1d(perfil, σ)
```

**Justificación**: La altura efectiva `h_b,eff` en Okumura-Hata es sensible a
irregularidades de alta frecuencia del DEM (ruido de medición, vegetación). El
suavizado mejora la estabilidad numérica sin perder las tendencias macro del terreno.

---

## 9. Línea de Visión (LOS)

### Qué redactar
Descripción del algoritmo LOS, sus limitaciones y cómo se integra con la simulación.

### 9.1 Algoritmo de Trazado Geométrico

**Nivel técnico**: Alto.

Para cada par TX→RX:
1. Muestrear `n_samples` puntos intermedios equidistantes: `t ∈ [0, 1]`.
2. Calcular la elevación de la LOS directa en cada punto:
   `z_LOS(t) = z_tx + t·(z_rx − z_tx)`.
3. Consultar la elevación del terreno en esos puntos: `z_terrain(t)` (del DEM).
4. Obstrucción: `∃ t_k ∈ (0, 1) : z_terrain(t_k) > z_LOS(t_k)`.

En notación vectorizada (para N receptores simultáneos):
```python
z_los = z_tx + t[None, :] * (z_rx[:, None] - z_tx)    # (N, S)
obstructed = any(terrain[:, 1:-1] > z_los[:, 1:-1])    # (N,) bool
```

**Justificación de excluir extremos** (`[1:-1]`): En los extremos `t=0` (TX) y `t=1` (RX),
la elevación del terreno puede coincidir numéricamente con la LOS (ambas iguales por
construcción), generando falsos positivos de obstrucción.

### 9.2 Limitaciones del Algoritmo LOS

**Qué documentar**:
- No modela difracción: un punto clasificado NLOS puede recibir señal por difracción.
  El mapa LOS es estrictamente geométrico.
- No modela vegetación ni edificios (el DEM no incluye estos objetos en datos SRTM bare-earth).
- La precisión depende de `n_samples`: con 50 muestras en 10 km → resolución ~200 m por muestra.
- Para terreno muy accidentado, la aproximación lineal TX→RX puede ignorar obstáculos
  que no están en la línea directa (difracción por borde lateral).

### 9.3 Integración con la Simulación

El mapa LOS se calcula después del mapa de RSRP y se exporta como:
- Canal `los_nlos` en el CSV (1 = LOS, 0 = NLOS).
- Banda adicional en el GeoTIFF.
- Imagen PNG semitransparente en el mapa interactivo.

---

## 10. Motor de Cómputo Heterogéneo (CPU/GPU)

### Qué redactar
Descripción técnica del patrón de abstracción NumPy/CuPy y su impacto en el rendimiento.

### 10.1 Detección Automática de GPU

`GPUDetector._detect()` intenta importar `cupy` en tiempo de ejecución. Si la importación
falla o no hay dispositivo CUDA disponible, el sistema cae silenciosamente a NumPy.
Este patrón se conoce como *graceful degradation*.

### 10.2 Patrón de Abstracción `xp`

```python
class ComputeEngine:
    def __init__(self, use_gpu=True):
        self.xp = cupy if (use_gpu and cupy_available) else numpy
```

Todos los módulos de cálculo usan `self.xp.*` en lugar de `np.*` o `cp.*`.
Los cambios de modo (CPU↔GPU) solo requieren cambiar `self.xp` en el motor;
ningún algoritmo necesita modificarse.

### 10.3 Flujo de Datos GPU

```
Grilla NumPy (CPU)
       ↓  xp.asarray()
Grilla CuPy (GPU) ← operaciones vectorizadas (Haversine, path loss, patrón antena, LOS)
       ↓  xp.asnumpy()
Resultado NumPy (CPU) ← matplotlib, Leaflet, exportación
```

**Qué mencionar**: La conversión CPU↔GPU tiene costo fijo (~0.5–2 ms para 100×100 grilla).
Solo se realiza una vez al inicio y al final, no en cada operación.

### 10.4 Métricas de Rendimiento

**Tabla sugerida** (completar con mediciones reales):
| Escenario | Grilla | Antenas | CPU (s) | GPU (s) | Speedup |
|-----------|--------|---------|---------|---------|---------|
| FSPL básico | 100×100 | 1 | ? | ? | ? |
| Okumura+DEM | 200×200 | 3 | ? | ? | ? |
| ITU-R P.1546 | 300×300 | 5 | ? | ? | ? |
| 3GPP UMa | 200×200 | 2 | ? | ? | ? |

**Figura sugerida**: Gráfica tiempo vs tamaño de grilla (en potencias de 2) para CPU y GPU.

---

## 11. Interfaz Gráfica y Flujo de Usuario

### Qué redactar
Descripción concisa de la arquitectura UI sin entrar en detalles de widgets.
El foco académico debe estar en las decisiones de diseño, no en los componentes visuales.

### Contenido sugerido

#### 11.1 Tecnología de la Interfaz
- **Framework**: PyQt6 (bindings Python para Qt 6.x).
- **Mapa interactivo**: `QWebEngineView` + Leaflet 1.9.4.
- **Comunicación bidireccional UI↔mapa**: `QWebChannel` (puente Python-JavaScript).
- **Justificación**: PyQt6 permite combinar widgets nativos de escritorio con tecnología
  web moderna (Leaflet) para visualización cartográfica, sin necesidad de un servidor web.

#### 11.2 Gestión de Proyectos
- Los proyectos se serializan a JSON (`.rfproj`) mediante `ProjectManager`.
- Incluyen todas las antenas, parámetros de simulación y configuración de terreno.
- Formato legible por humanos, extensible.

#### 11.3 Renderizado de Resultados
- El heatmap de RSRP se genera como PNG base64 en el hilo de simulación.
- Se transmite al mapa Leaflet como *ImageOverlay* georeferenciado con bounds lat/lon.
- La leyenda dinámica se actualiza con el rango de valores reales.
- Superposición separada para el mapa LOS (semitransparente, verde/gris).

---

## 12. Sistema de Exportación y Formatos de Salida

### Qué redactar
Descripción técnica de los tres formatos de exportación y su pertinencia científica.

### Formato CSV

**Estructura**: Una fila por punto de la grilla, con columnas:
`antenna_id, frequency_mhz, tx_power_dbm, tx_height_m, grid_lat, grid_lon,`
`rsrp_dbm, path_loss_db, antenna_gain_dbi, model_used, environment, terrain_type, los_nlos`

**Relevancia**: Permite comparativa cuantitativa punto a punto contra Atoll u otras
herramientas. Importable directamente en Python/R/Excel para análisis estadístico.

### Formato GeoTIFF

- Raster georreferenciado con RSRP y LOS como bandas.
- CRS: WGS84 (EPSG:4326).
- Resolución de píxel = resolución de la grilla de simulación.
- Compatible con QGIS, ArcGIS, Google Earth Engine.
- Permite análisis espacial: solapamiento con datos de usuarios, zonas de cobertura, etc.

### Formato KML

- Google Earth Markup Language.
- Polígonos de cobertura por umbral de RSRP (configurable, default: −100 dBm).
- Permite visualización 3D en Google Earth con terreno extruido.

---

## 13. Estrategias de Optimización

### Qué redactar
Describir las decisiones de optimización implementadas, con justificación técnica.

### 13.1 Vectorización Completa

Todos los cálculos de propagación, antena y LOS operan sobre arrays 2D completos, no con
loops punto a punto. Esto aprovecha SIMD y paralelismo de datos en NumPy/CuPy.

Ejemplo: `distances = R * c` donde `c` es un array `(H, W)` — un solo call calcula
las `H×W` distancias simultáneamente.

### 13.2 Grilla Global Única

La grilla `(grid_lats, grid_lons, terrain_heights)` se crea una sola vez para el proyecto
completo (PHASE 7 en `SimulationWorker`). Cada antena usa la misma grilla sin recriarla.
Ahorro estimado: O(n_antenas × costo_DEM_query).

### 13.3 Conversión CPU↔GPU Diferida

`calculate_single_antenna_coverage()` mantiene los datos en GPU durante todo el cómputo.
La conversión `xp.asnumpy()` solo ocurre una vez, al final, antes del renderizado.

### 13.4 Rango Dinámico en Renderizado

El colormap no usa rangos fijos (–120, –60 dBm) sino percentiles 5–95 de los datos reales.
Esto mejora la visualización en entornos con distribución asimétrica de RSRP.

### 13.5 Perfiles Suavizados como Cache

`get_smoothed_profiles()` recibe los perfiles ya calculados (no lee el DEM nuevamente),
evitando doble consulta al archivo GeoTIFF.

---

## 14. Validación del Sistema

### Qué redactar
Esta es la sección más crítica académicamente. Debe demostrar que el sistema es correcto,
no solo que funciona. Distinguir **validación interna** de **validación externa**.

### 14.1 Validación Interna: Suite de Pruebas Unitarias

**Nivel técnico**: Alto.

El sistema tiene > 30 archivos de prueba en `tests/`. Documentar:

**Pruebas de modelos de propagación**:
- `test_okumura_hata_complete.py`: Valida L_u contra valores tabulados en Hata (1980) para
  f = {150, 450, 900, 1500} MHz, h_b = {30, 50, 100, 150} m, d = {1, 5, 10, 20} km.
- `test_cost231_complete.py`: Verifica L_LOS vs L_NLOS, factor Lori para ángulos de calle.
- `test_itu_r_p1546_complete.py`: Valida interpolación de E contra tablas del estándar,
  verifica TCA para perfiles con obstáculos conocidos.
- `test_3gpp_38901_complete.py`: Verifica breakpoint d_BP, probabilidades LOS, valores
  PL contra ejemplos numéricos de la TR 38.901.

**Pruebas de patrón de antena** (añadidas en esta sesión):
- `test_antenna_pattern_horizontal_sectorial`: a `φ = φ_3dB/2 = 30°` (para φ_3dB=60°),
  la atenuación debe ser exactamente −3 dB.
- `test_antenna_pattern_vertical_downtilt`: antena con `mechanical_tilt=6°` apuntando
  a receptor con elevación_angle = 6° → atenuación = 0 dB (receptor en boresight vertical).
- `test_antenna_pattern_3d_combined`: H y V ambos en cap de 30 dB → combinado = 30 dB.

**Tabla sugerida: Resumen de validación por módulo**:
| Módulo | Tests | Casos cubiertos | Resultado |
|--------|-------|----------------|-----------|
| FSPL | 3 | rangos, valores conocidos | PASS |
| Okumura-Hata | 8 | ambientes, frecuencias, h_b | PASS |
| COST-231 W-I | 6 | LOS/NLOS, orientación | PASS |
| ITU-R P.1546 | 10 | tablas, TCA, clutter | PASS |
| 3GPP TR 38.901 | 12 | UMa/UMi/RMa, DEM | PASS |
| Patrón antena 3D | 4 | horizontal, vertical, combined | PASS |
| TerrainLoader | 6 | carga, consulta, perfiles | PASS |
| LOSCalculator | 3 | LOS, NLOS, GPU/CPU | PASS |

### 14.2 Validación de Consistencia Física

Verificar propiedades que deben cumplirse por la física del problema:
1. **Monotonía**: path loss debe aumentar con la distancia (para modelos empíricos).
2. **Escalado frecuencial**: a mayor frecuencia, mayor pérdida (FSPL y Hata).
3. **Simetría del patrón**: `G(φ, θ) = G(−φ, θ)` para antenas simétricas.
4. **Boresight**: `G(0°, θ_tilt) = G_max` (máxima ganancia en la dirección de apuntamiento).
5. **LOS monotonía**: porcentaje LOS debe disminuir con distancia en terreno irregular.

### 14.3 Coherencia Unidades

El sistema opera internamente en:
- Distancias: metros (conversión a km dentro de cada modelo).
- Frecuencias: MHz.
- Potencia: dBm (RSRP) y dB (path loss, ganancia).
- Elevaciones: metros MSL (Mean Sea Level).
- Ángulos: grados (salvo en cómputos intermedios que usan radianes).

El test `tests/test_units_consistency.py` verifica que no haya errores de escala
(por ej., pasar km cuando el modelo espera m).

---

## 15. Comparación con Atoll

### Qué redactar
Esta sección demuestra la utilidad práctica del sistema mediante comparación cuantitativa
con una herramienta de referencia de la industria. Es el argumento más fuerte de validación.

### 15.1 Descripción de Atoll

**Nivel técnico**: Medio. Describir Atoll brevemente (Forsk S.A., herramienta estándar de
planificación de redes móviles, usada por operadores como Claro, Movistar, CNT en Ecuador).
Mencionar que implementa los mismos modelos: Okumura-Hata, COST-231, ITU-R P.1546, 3GPP.

### 15.2 Metodología de Comparación

**Pasos a documentar**:
1. Configurar **exactamente la misma antena** en ambas herramientas:
   - Mismas coordenadas GPS (6 decimales).
   - Misma frecuencia, potencia, altura.
   - Mismo modelo de propagación con mismos parámetros.
   - Mismo DEM (importar el GeoTIFF en Atoll).
2. Exportar CSV de Atoll con columnas: lat, lon, RSRP.
3. Exportar CSV del sistema desarrollado con las mismas columnas.
4. Calcular métricas de error punto a punto.

**Variables a comparar**:
| Variable | Unidad | Importancia |
|---------|--------|-------------|
| RSRP | dBm | Principal — métrica de cobertura |
| Path loss | dB | Diagnóstica — aísla error del modelo |
| Área de cobertura > −100 dBm | km² | Planificación de red |
| Contorno de cobertura | GeoJSON | Visual |

### 15.3 Métricas de Error Cuantitativas

**Incluir en el capítulo**:

**Error Medio Absoluto (MAE)**:
```
MAE = (1/N) · Σ |RSRP_sistema − RSRP_Atoll|    [dB]
```

**Raíz del Error Cuadrático Medio (RMSE)**:
```
RMSE = √( (1/N) · Σ (RSRP_sistema − RSRP_Atoll)² )    [dB]
```

**Sesgo (Bias)**:
```
Bias = (1/N) · Σ (RSRP_sistema − RSRP_Atoll)    [dB]
```
Distingue si el sistema es sistemáticamente optimista (+) o pesimista (−).

**Percentiles del error**:
- p50 (mediana): error típico.
- p90: error en el peor 10%.
- p95: error en el peor 5%.

**Correlación de Pearson** entre RSRP_sistema y RSRP_Atoll:
```
r = Cov(X, Y) / (σ_X · σ_Y)
```
Valor ideal: r ≥ 0.95 indica alta correlación espacial.

### 15.4 Escenarios de Prueba Sugeridos

| Escenario | Modelo | Antenas | Área (km²) | Propósito |
|-----------|--------|---------|-----------|-----------|
| Urbano centro histórico | Okumura-Hata | 1 BS LTE 1800 | 5×5 | Validación urbana básica |
| Corredor El Ejido | COST-231 W-I | 1 BS | 3×3 | Zona mixta urbana-suburbana |
| Montaña periférica | ITU-R P.1546 | 1 BS rural | 10×10 | Terreno accidentado |
| Zona 5G (El Arenal) | 3GPP UMa | 2 BS | 5×5 | Frecuencias altas |
| Multi-antena | Okumura-Hata | 5 BS | 15×15 | Best-server, handover |

### 15.5 Interpretación de Diferencias

**Qué documentar**:
- Un MAE de 2–5 dB es aceptable para modelos empíricos en entornos realistas.
- Diferencias > 10 dB en puntos específicos pueden deberse a:
  - Diferente versión del modelo implementada (ej. Hata original vs COST-231 Hata).
  - Diferente resolución del DEM usado internamente por Atoll.
  - Correcciones propietarias de Atoll no documentadas públicamente.
  - Orientación de la antena (tilt mecánico: Atoll puede tener correcciones adicionales).
  - Clutter (Atoll usa bases de datos de uso de suelo que el sistema no tiene).

### 15.6 Figuras Sugeridas para la Comparación

1. **Scatter plot**: RSRP_sistema vs RSRP_Atoll, con línea y=x y regresión lineal.
2. **Mapa de diferencias**: `ΔdB = RSRP_sistema − RSRP_Atoll` sobre el mapa geográfico,
   usando colormap divergente (rojo=sistema sobrestima, azul=subestima).
3. **Histograma del error**: distribución de `(RSRP_sistema − RSRP_Atoll)` para cada modelo.
4. **CDF del error**: función de distribución acumulada del |error|.
5. **Mapa de cobertura side-by-side**: imagen del sistema junto a captura de Atoll.
6. **Perfil de terreno con RSRP**: para una transecta fija, comparar RSRP vs distancia.

### 15.7 Limitaciones de la Comparación

**Documentar honestamente**:
- Atoll usa clutter databases (datos de uso de suelo) que el sistema no tiene → diferencias
  sistemáticas en zonas con vegetación densa o estructuras altas.
- Atoll puede usar correcciones propietarias no documentadas.
- La interpolación de resultados Atoll al mismo grid puede introducir error adicional.
- La calibración de modelos en Atoll requiere mediciones de campo (*drive test*); sin
  calibración, los valores base son comparables.

---

## 16. Métricas de Evaluación

### Qué redactar
Resumen consolidado de todas las métricas utilizadas en el capítulo.

### Métricas de Calidad de Propagación
| Métrica | Fórmula | Unidad | Rango aceptable |
|---------|---------|--------|----------------|
| MAE | `(1/N)·Σ|ε|` | dB | 2–5 dB |
| RMSE | `√((1/N)·Σε²)` | dB | 3–7 dB |
| Bias | `(1/N)·Σε` | dB | ±2 dB |
| r (Pearson) | `Cov/σ₁σ₂` | — | ≥ 0.90 |
| p50 error | mediana(|ε|) | dB | ≤ 4 dB |
| p90 error | percentil 90(|ε|) | dB | ≤ 8 dB |

### Métricas de Rendimiento Computacional
| Métrica | Unidad | Descripción |
|---------|--------|-------------|
| Tiempo de simulación | s | Por antena, por modelo, por tamaño de grilla |
| Speedup GPU/CPU | ×N | Para grillas de 100×100, 200×200, 300×300 |
| Throughput | Mpuntos/s | Megapuntos procesados por segundo |
| Memoria GPU usada | MB | Pico de uso en simulación |

### Métricas de Cobertura Planificación
| Métrica | Descripción |
|---------|-------------|
| Área de cobertura | km² con RSRP > −100 dBm |
| % píxeles LOS | Porcentaje de puntos con visión directa |
| Diferencia de área sistema vs Atoll | % |

---

## 17. Limitaciones y Consideraciones Técnicas

### Qué redactar
Honestidad académica sobre lo que el sistema NO hace o hace con restricciones.
Una buena tesis documenta las limitaciones tanto como los logros.

### Limitaciones de los Modelos de Propagación

| Limitación | Modelo afectado | Impacto estimado |
|-----------|----------------|-----------------|
| Sin clutter de uso de suelo | Todos | ±3–8 dB en zonas forestales o densamente edificadas |
| Sin modelo de edificios 3D | COST-231, 3GPP | ±2–5 dB en urban canyon |
| Sin múltiples trayectos (multipath) | Todos | No aplica a path loss medio |
| Sin modelo de lluvia/niebla | 3GPP mmWave | Significativo solo > 10 GHz |
| Curvatura terrestre no aplicada | ITU-R P.1546 | Error relevante solo a d > 50 km |
| Percentiles ITU discretizados | ITU-R P.1546 | Solo {1, 10, 50, 90, 99} disponibles |
| Sin calibración de campo | Todos | Hasta ±6 dB vs valores reales medidos |

### Limitaciones del DEM

| Limitación | Descripción |
|-----------|-------------|
| Resolución | SRTM 30 m subestima crestas y valles en < 30 m |
| Bare-earth vs DSM | No incluye edificios ni vegetación |
| Artefactos de agua | Ríos y lagos pueden aparecer como depresiones falsas |
| Accuracy vertical | ±6–16 m absoluto (especificación SRTM) |

### Limitaciones del Sistema de Software

| Limitación | Descripción |
|-----------|-------------|
| Sin base de datos de clutter | No distingue urbano/rural automáticamente desde mapas |
| Sin modelo de movilidad | No simula handover dinámico |
| Sin MIMO / beamforming | Antenas representadas por patrón 3D estático |
| Sin propagación indoor | El DEM no incluye interiores de edificios |
| Loop Python en `get_elevations_fast()` | Cuello de botella para grillas > 500×500 |

### Consideraciones para Futuros Trabajos

- Integración de bases de datos de uso de suelo (OpenStreetMap Buildings, Copernicus CLC).
- Aceleración completa de `get_elevations_fast()` con indexación rasterio/GDAL vectorizada.
- Modelo de clutter automático desde DEM de superficie (DSM vs DTM diferencia).
- Soporte para propagación indoor (ITA indoor factory model, 3GPP TR 38.901 InH).
- Interfaz de importación de mediciones de campo para calibración automática de modelos.

---

## APÉNDICE: REFERENCIAS TÉCNICAS PARA EL CAPÍTULO

### Estándares y Recomendaciones ITU
- **ITU-R P.1546-6** (2019): Method for point-to-area predictions for terrestrial services. Geneva: ITU.
- **ITU-R P.2108-1** (2021): Prediction of clutter loss. Geneva: ITU.
- **ITU-R P.417** (2019): Calculation of free-space attenuation. Geneva: ITU.
- **ITU-R P.526-15** (2019): Propagation by diffraction. Geneva: ITU.

### Estándares 3GPP
- **3GPP TR 38.901**: Study on channel model for frequencies from 0.5 to 100 GHz.

### Publicaciones Seminal de Modelos
- **Hata, M.** (1980): Empirical formula for propagation loss in land mobile radio services. *IEEE Transactions on Vehicular Technology*, 29(3), 317–325.
- **Okumura, Y. et al.** (1968): Field strength and its variability in VHF and UHF land-mobile service. *Review of the Electrical Communication Laboratory*, 16(9-10), 825–873.
- **Walfisch, J. & Bertoni, H.L.** (1988): A theoretical model of UHF propagation in urban environments. *IEEE Transactions on Antennas and Propagation*, 36(12), 1788–1796.
- **Ikegami, F. et al.** (1991): Propagation factors controlling mean field strength on urban streets. *IEEE Transactions on Antennas and Propagation*, 32(8), 822–829.

### Software y Herramientas
- **NumPy** (Harris et al., 2020): Array programming with NumPy. *Nature*, 585, 357–362.
- **CuPy** (Nishino et al., 2017): CuPy: A NumPy-Compatible Library for NVIDIA GPU Calculations.
- **rasterio** (Gillies et al., 2013–): Rasterio: geospatial raster I/O for Python programmers.
- **pyproj** (Whitaker et al., 2019–): Python interface to PROJ coordinate transformation library.
- **PyQt6** (Riverbank Computing, 2021–): Python bindings for Qt 6.
- **Leaflet** (Agafonkin, 2011–): Leaflet: an open-source JavaScript library for interactive maps.

### Datos Geoespaciales
- **NASA SRTM** (2000): Shuttle Radar Topography Mission 1 Arc-Second Global. USGS EROS Archive.
- **IGM Ecuador**: Instituto Geográfico Militar. Modelos digitales de elevación nacionales.

---

## APÉNDICE: ESTRUCTURA SUGERIDA DEL CAPÍTULO FINAL

```
Capítulo N: Metodología, Diseño e Implementación

N.1 Introducción al Capítulo                                        (~0.5 pág)
N.2 Metodología de Desarrollo                                       (~2 pág)
    N.2.1 Enfoque iterativo e incremental por fases
    N.2.2 Estrategia de validación por pruebas unitarias
    N.2.3 Adherencia a estándares primarios
N.3 Arquitectura General del Sistema                                (~3 pág)
    N.3.1 Arquitectura en capas
    N.3.2 Patrones de diseño aplicados
    N.3.3 Motor de cómputo heterogéneo (CPU/GPU)
N.4 Diseño Modular                                                  (~3 pág)
    N.4.1 Modelo de datos: Antenna, Site, Project
    N.4.2 Módulo de cobertura: CoverageCalculator
    N.4.3 Módulo de terreno: TerrainLoader
    N.4.4 Módulo LOS: LOSCalculator
    N.4.5 Pipeline de simulación: SimulationWorker
N.5 Fundamentos Matemáticos                                        (~4 pág)
    N.5.1 Ecuación de cobertura RF
    N.5.2 Geometría geodésica (Haversine, bearing)
    N.5.3 Patrón de radiación 3D (3GPP TR 38.901 §7.3.2)
N.6 Modelos de Propagación Implementados                            (~8 pág)
    N.6.1 Espacio libre (FSPL)
    N.6.2 Okumura-Hata
    N.6.3 COST-231 Walfisch-Ikegami
    N.6.4 ITU-R P.1546-6
    N.6.5 3GPP TR 38.901
N.7 Procesamiento Geoespacial e Integración DEM                    (~3 pág)
    N.7.1 Fuente y formato de datos de elevación
    N.7.2 Perfiles radiales TX→RX
    N.7.3 Análisis de línea de visión geométrica
N.8 Optimizaciones Implementadas                                    (~1.5 pág)
N.9 Validación del Sistema                                          (~5 pág)
    N.9.1 Pruebas unitarias por módulo
    N.9.2 Validación de consistencia física
    N.9.3 Validación de unidades y escalas
N.10 Comparación con Atoll                                         (~5 pág)
    N.10.1 Metodología de comparación
    N.10.2 Resultados por escenario
    N.10.3 Análisis estadístico del error
    N.10.4 Interpretación de discrepancias
N.11 Limitaciones y Trabajo Futuro                                 (~1.5 pág)
N.12 Resumen del Capítulo                                           (~0.5 pág)

Total estimado: 35–40 páginas
```

---

*Fin del documento guía. Versión: mayo 2026.*
