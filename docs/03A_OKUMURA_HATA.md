# Modelo Okumura-Hata: Documentación Técnica Exhaustiva

**Archivo fuente:** `src/core/models/traditional/okumura_hata.py`
**Clase:** `OkumuraHataModel`
**Versión:** 2026-05-08

---

## 1. Descripción del Modelo

El modelo Okumura-Hata es un modelo **empírico** de pérdida de propagación para sistemas móviles terrestres. Fue desarrollado en dos etapas:

- **Okumura (1968):** Realizó mediciones extensas de intensidad de campo en Tokio a varias frecuencias y distancias, generando curvas de referencia gráficas.
- **Hata (1980):** Ajustó ecuaciones matemáticas cerradas a las curvas de Okumura, haciéndolo computable y estandarizado en la recomendación CCIR 529.

### 1.1 Tipo de Modelo

| Aspecto | Descripción |
|---------|-------------|
| Tipo | Empírico estadístico (mediana de pérdida, 50% del tiempo) |
| Condición LOS/NLOS | No distingue (promediado estadístico) |
| Uso de terreno | Sí — altura efectiva sobre DEM |
| Vectorización | CPU (NumPy) / GPU (CuPy) via `self.xp` |

### 1.2 Rangos de Validez

| Parámetro | Mínimo | Máximo | Unidades |
|-----------|--------|--------|----------|
| Frecuencia | 150 | 1500 (ext. 2000) | MHz |
| Distancia | 1 | 20 | km |
| Altura TX (h_b) | 30 | 200 | m AGL |
| Altura móvil (h_m) | 1 | 10 | m AGL |

> **Nota:** Para frecuencias entre 1500 y 2000 MHz el modelo aplica automáticamente la extensión COST-231 Hata (ver §6).

---

## 2. Entrada y Salida del Método Principal

**Ubicación:** `okumura_hata.py`, método `calculate_path_loss()`

### 2.1 Parámetros de Entrada

```python
def calculate_path_loss(
    self,
    distances,        # np.ndarray, metros, shape (N,) o (H, W)
    frequency,        # float, MHz, rango válido 150-2000
    tx_height,        # float, metros AGL (above ground level)
    terrain_heights,  # np.ndarray, msnm (metros sobre nivel del mar), mismo shape que distances
    tx_elevation=0.0, # float, msnm — elevación del terreno en la ubicación del TX
    environment='Urban',   # str: 'Urban' | 'Suburban' | 'Rural'
    city_type='medium',    # str: 'large' | 'medium' — solo afecta entorno Urban
    mobile_height=None,    # float, metros AGL (default: 1.5 m)
    **kwargs
)
```

| Parámetro | Tipo | Unidades | Descripción |
|-----------|------|----------|-------------|
| `distances` | ndarray | m | Distancias Haversine desde TX a cada punto de la grilla |
| `frequency` | float | MHz | Frecuencia de portadora |
| `tx_height` | float | m AGL | Altura de antena sobre el suelo local del TX |
| `terrain_heights` | ndarray | msnm | Elevación del terreno en cada punto receptor (grilla 100×100) |
| `tx_elevation` | float | msnm | Elevación del suelo en el punto TX |
| `environment` | str | — | Tipo de entorno de propagación |
| `city_type` | str | — | Tamaño de ciudad (afecta `a(h_m)`) |
| `mobile_height` | float | m AGL | Altura del receptor (default 1.5 m) |

### 2.2 Salida

```python
# Retorna
path_loss  # np.ndarray, dB, mismo shape que distances
           # Valores típicos: 80–160 dB
           # Mayor dB → mayor atenuación → menor señal recibida
```

---

## 3. Integración con el Terreno (DEM)

El modelo usa el DEM para calcular la **altura efectiva de la antena base** h_b respecto al nivel promedio del área. Esto es fundamental porque la pérdida de propagación depende de cuánto se eleva el TX sobre el terreno circundante, no de su altura absoluta.

### 3.1 Fórmula de Altura Efectiva

$$h_{b,\text{eff}} = h_{\text{ant}} + h_{\text{elev,TX}} - \overline{h_{\text{terreno}}}$$

donde:
- $h_{\text{ant}}$ = `tx_height` — altura de la antena sobre el suelo local (AGL)
- $h_{\text{elev,TX}}$ = `tx_elevation` — cota absoluta del suelo en el punto TX (msnm)
- $\overline{h_{\text{terreno}}}$ = media de `terrain_heights` — elevación promedio del área de simulación

### 3.2 Clipping de Parámetros

```python
# Código real: okumura_hata.py, líneas 81-83
terrain_avg = self.xp.mean(terrain_heights)
hb_effective = tx_height + tx_elevation - terrain_avg
hb_effective = self.xp.maximum(hb_effective, 30.0)   # mínimo 30 m (límite del modelo)
hb_effective = self.xp.minimum(hb_effective, 200.0)  # máximo 200 m (límite del modelo)
```

**Ejemplo concreto:**
```
Sitio en Cuenca (montañoso):
  tx_height    = 15 m  (mástil sobre techo)
  tx_elevation = 2580 m (altitud del sitio sobre el nivel del mar)
  terrain_avg  = 2520 m (promedio del área de cobertura)

  h_b_eff = 15 + 2580 - 2520 = 75 m ✓ (dentro de rango 30-200 m)
```

### 3.3 Distancias 2D (Haversine)

El modelo usa distancias **horizontales** (2D) calculadas por Haversine en `CoverageCalculator`. No usa distancia 3D que incorpore diferencia de alturas — la variación de elevación queda absorbida en el término `h_b_eff`.

---

## 4. Ecuaciones Implementadas

### 4.1 Fórmula Base — Entorno Urbano

$$\boxed{L_{50,\text{urban}}(\text{dB}) = 69.55 + 26.16\,\log_{10}(f) - 13.82\,\log_{10}(h_b) - a(h_m) + \bigl[44.9 - 6.55\,\log_{10}(h_b)\bigr]\log_{10}(d)}$$

donde:
- $f$ = frecuencia en **MHz**
- $d$ = distancia en **km**
- $h_b$ = altura efectiva antena base en **metros** (ver §3)
- $a(h_m)$ = factor de corrección por altura del móvil (ver §4.2)

**Código real:**
```python
# okumura_hata.py, líneas 87-93
path_loss_urban = (
    69.55
    + 26.16 * self.xp.log10(frequency)
    - 13.82 * self.xp.log10(hb_effective)
    - a_hm
    + (44.9 - 6.55 * self.xp.log10(hb_effective)) * self.xp.log10(d_km)
)
```

**Justificación de constantes:**
- **69.55:** Término constante calibrado por Hata para ajustar mediciones de Okumura en zona urbana (Tokyo)
- **26.16·log₁₀(f):** Pérdida adicional por frecuencia — mayor f implica mayor atenuación
- **13.82·log₁₀(h_b):** Ganancia por altura TX — mayor mástil implica menor pérdida
- **[44.9 − 6.55·log₁₀(h_b)]·log₁₀(d):** Exponente de distancia dependiente de h_b — el exponente varía entre 36.5 (h_b=200m) y 44.9 (h_b=1m)

### 4.2 Factor de Corrección por Altura Móvil — a(h_m)

Este factor ajusta la pérdida según la altura del receptor. Hay dos formas según el tipo de ciudad:

#### Ciudades Grandes (city_type = 'large')

$$a(h_m) = \begin{cases}
8.29\,\bigl[\log_{10}(1.54\,h_m)\bigr]^2 - 1.1 & \text{si } f \leq 200\text{ MHz} \\[6pt]
3.2\,\bigl[\log_{10}(11.75\,h_m)\bigr]^2 - 4.97 & \text{si } f > 200\text{ MHz}
\end{cases}$$

#### Ciudades Pequeñas/Medianas (city_type = 'medium', default)

$$a(h_m) = \bigl(1.1\,\log_{10}(f) - 0.7\bigr)\,h_m - \bigl(1.56\,\log_{10}(f) - 0.8\bigr)$$

**Código real:**
```python
# okumura_hata.py, método _calculate_mobile_height_correction()
if city_type.lower() == 'large':
    if frequency <= 200:
        a_hm = 8.29 * (self.xp.log10(1.54 * hm))**2 - 1.1
    else:
        a_hm = 3.2 * (self.xp.log10(11.75 * hm))**2 - 4.97
else:
    # small/medium city (default)
    a_hm = (1.1 * self.xp.log10(frequency) - 0.7) * hm - \
           (1.56 * self.xp.log10(frequency) - 0.8)
```

**Ejemplo numérico (h_m = 1.5 m, f = 900 MHz, ciudad mediana):**
```
a(h_m) = (1.1·log10(900) - 0.7)·1.5 - (1.56·log10(900) - 0.8)
        = (1.1·2.954 - 0.7)·1.5 - (1.56·2.954 - 0.8)
        = (3.249 - 0.7)·1.5 - (4.608 - 0.8)
        = 2.549·1.5 - 3.808
        = 3.824 - 3.808
        = 0.016 dB
```

> Para h_m = 1.5 m el factor es casi cero — el modelo está calibrado a esta altura.

### 4.3 Corrección Entorno Suburbano

$$L_{\text{suburban}} = L_{\text{urban}} - 2\,\bigl[\log_{10}(f/28)\bigr]^2 - 5.4 \quad \text{[dB]}$$

**Código real:**
```python
# okumura_hata.py, líneas 96-100
correction = 2 * (self.xp.log10(frequency / 28.0))**2 + 5.4
path_loss = path_loss_urban - correction
```

**Justificación:** En entornos suburbanos hay menos densidad de edificios y obstrucciones. La corrección es negativa (reduce la pérdida) y depende de la frecuencia — a 900 MHz el ajuste es ≈ −9.3 dB.

**Ejemplo a 900 MHz:**
```
correction = 2·[log10(900/28)]² + 5.4
           = 2·[log10(32.14)]² + 5.4
           = 2·[1.5073]² + 5.4
           = 2·2.272 + 5.4
           = 4.544 + 5.4 = 9.94 dB
→ L_suburban = L_urban − 9.94 dB
```

### 4.4 Corrección Entorno Rural

$$L_{\text{rural}} = L_{\text{urban}} - 4.78\,\bigl[\log_{10}(f)\bigr]^2 + 18.33\,\log_{10}(f) - 40.94 \quad \text{[dB]}$$

**Código real:**
```python
# okumura_hata.py, líneas 103-107
f_term = self.xp.log10(frequency)
correction = 4.78 * (f_term**2) - 18.33 * f_term + 40.94
path_loss = path_loss_urban - correction
```

**Ejemplo a 900 MHz:**
```
log10(900) = 2.954
correction = 4.78·(2.954)² − 18.33·2.954 + 40.94
           = 4.78·8.726 − 54.15 + 40.94
           = 41.71 − 54.15 + 40.94 = 28.5 dB
→ L_rural = L_urban − 28.5 dB
```

### 4.5 Extensión COST-231 para f > 1500 MHz

Para frecuencias entre 1500 y 2000 MHz el modelo original de Hata pierde precisión. El comité COST-231 extendió la fórmula añadiendo un factor de corrección metropolitano:

$$L = L_{\text{urban}}(f,d,h_b,h_m) + C_m$$

$$C_m = \begin{cases} 3 \text{ dB} & \text{entorno Urban, ciudad grande} \\ 0 \text{ dB} & \text{resto} \end{cases}$$

**Código real:**
```python
# okumura_hata.py, líneas 111-119
if frequency > 1500:
    if environment.lower() == 'urban' and city_type.lower() == 'large':
        Cm = 3.0
    else:
        Cm = 0.0
    path_loss = path_loss + Cm
```

---

## 5. Flujo de Cálculo Completo

```
Entrada: distances (m), frequency (MHz), tx_height (m),
         terrain_heights (msnm), tx_elevation (msnm),
         environment, city_type, mobile_height

     │
     ▼
┌────────────────────────────────────────────┐
│ 1. Validación de parámetros               │
│    (warnings si fuera de rango)           │
└────────────────────────────────────────────┘
     │
     ▼
┌────────────────────────────────────────────┐
│ 2. Conversión                             │
│    d_km = distances / 1000                │
│    d_km = max(d_km, 0.001)               │
└────────────────────────────────────────────┘
     │
     ▼
┌────────────────────────────────────────────┐
│ 3. Altura efectiva TX                     │
│    terrain_avg = mean(terrain_heights)    │
│    h_b = tx_height + tx_elev − terrain_avg│
│    h_b = clip(h_b, 30, 200)              │
└────────────────────────────────────────────┘
     │
     ▼
┌────────────────────────────────────────────┐
│ 4. Factor a(hm)                           │
│    ¿city_type == 'large'?                 │
│    ├─ SÍ: ¿f ≤ 200?                      │
│    │       ├─ SÍ: forma A (8.29·...)     │
│    │       └─ NO: forma B (3.2·...)      │
│    └─ NO: forma ciudad mediana           │
└────────────────────────────────────────────┘
     │
     ▼
┌────────────────────────────────────────────┐
│ 5. L_urban (fórmula base Hata)            │
│    69.55 + 26.16·log(f) - 13.82·log(h_b) │
│    − a_hm + [44.9 − 6.55·log(h_b)]·log(d)│
└────────────────────────────────────────────┘
     │
     ▼
┌────────────────────────────────────────────┐
│ 6. Corrección por entorno                 │
│    'Urban':    path_loss = L_urban        │
│    'Suburban': path_loss = L_urban − corr │
│    'Rural':    path_loss = L_urban − corr │
└────────────────────────────────────────────┘
     │
     ▼
┌────────────────────────────────────────────┐
│ 7. Extensión COST-231 (si f > 1500 MHz)  │
│    path_loss += Cm (0 o 3 dB)            │
└────────────────────────────────────────────┘
     │
     ▼
Salida: path_loss (dB), shape = shape(distances)
```

---

## 6. Ejemplo Numérico Completo

**Escenario:** Antena en Cuenca, entorno urbano, 900 MHz, ciudad mediana

```
Parámetros:
  frequency    = 900 MHz
  tx_height    = 30 m (AGL)
  tx_elevation = 2560 m (msnm)
  terrain_avg  = 2530 m (media de la grilla)
  environment  = 'Urban'
  city_type    = 'medium'
  mobile_height= 1.5 m
  distance     = 2.0 km (punto evaluado)

Paso 3 — h_b_eff:
  h_b = 30 + 2560 − 2530 = 60 m ✓ (30–200)

Paso 4 — a(h_m) para ciudad mediana, 900 MHz, h_m=1.5:
  a = (1.1·log10(900) − 0.7)·1.5 − (1.56·log10(900) − 0.8)
  a ≈ 0.016 dB

Paso 5 — L_urban a d=2 km, f=900 MHz, h_b=60 m:
  L = 69.55 + 26.16·log10(900) − 13.82·log10(60) − 0.016
      + (44.9 − 6.55·log10(60))·log10(2)
  L = 69.55 + 26.16·2.954 − 13.82·1.778 − 0.016
      + (44.9 − 6.55·1.778)·0.3010
  L = 69.55 + 77.27 − 24.57 − 0.016
      + (44.9 − 11.65)·0.3010
  L = 122.23 + 33.25·0.3010
  L = 122.23 + 10.01
  L = 132.2 dB

Paso 6 — Entorno urbano: sin corrección
  path_loss = 132.2 dB

Resultado:
  RSRP = P_tx + G_tx − path_loss
       = 40 + 14 − 132.2
       = −78.2 dBm  (señal buena en zona urbana)
```

---

## 7. Validaciones y Warnings

```python
# okumura_hata.py, método _validate_parameters()

if frequency < 150 or frequency > 2000:
    → warning: "Frecuencia {f}MHz fuera de rango válido (150-2000 MHz)"

if tx_height < 30 or tx_height > 200:
    → warning: "Altura de antena {h}m fuera de rango válido (30-200m)"

if mobile_height < 1 or mobile_height > 10:
    → warning: "Altura móvil {h}m fuera de rango válido (1-10m)"
```

Los warnings **no detienen** el cálculo — el sistema continúa con los valores dados. El clipping de `h_b_eff` a [30, 200] sí modifica el valor usado en la fórmula.

---

## 8. Cómo lo Invoca CoverageCalculator

```python
# src/core/coverage_calculator.py

# 1. Distancias Haversine (metros)
distances = self._calculate_distances(ant_lat, ant_lon, grid_lats, grid_lons)

# 2. Construir argumentos para el modelo
path_loss_args = {
    'distances':       distances,           # metros, shape (100, 100)
    'frequency':       antenna.frequency_mhz,
    'tx_height':       antenna.height_agl,
    'terrain_heights': terrain_heights,     # msnm, shape (100, 100)
    'tx_elevation':    antenna_elevation,   # msnm, escalar
}
path_loss_args.update(model_params)  # environment, city_type, mobile_height

# 3. Calcular path loss
path_loss = okumura_hata_model.calculate_path_loss(**path_loss_args)
# → ndarray shape (100, 100), valores en dB

# 4. RSRP
rsrp = antenna.tx_power_dbm + antenna.tx_gain_dbi - path_loss
```

---

## 9. Limitaciones del Modelo

| Limitación | Descripción |
|-----------|-------------|
| Sin distinción LOS/NLOS | Usa pérdida mediana estadística (L₅₀) — no distingue si hay línea de vista directa |
| Calibrado para Tokio | Las mediciones base son de Japón; para Cuenca puede haber diferencias |
| Distancia mínima 1 km | Para distancias menores el modelo no es representativo |
| No modela difracción específica | No calcula knife-edge ni obstrucciones individuales |
| h_b fuera de rango | Si h_b cae fuera de 30–200 m, se aplica clipping; resultado menos preciso |

---

## 10. Rendimiento Computacional

| Operación | NumPy (CPU) | CuPy (GPU) | Speedup |
|-----------|-------------|------------|---------|
| Grilla 100×100 (10k puntos) | ~15 ms | ~3 ms | ~5× |
| Grilla 200×200 (40k puntos) | ~55 ms | ~10 ms | ~5.5× |
| Cálculo a(hm) | ~2 ms | ~0.4 ms | ~5× |

La vectorización con `self.xp` permite aplicar las ecuaciones logarítmicas a los 10,000 puntos simultáneamente sin loops Python.

---

**Ver también:**
- [03B_COST231.md](03B_COST231.md) — extensión semi-determinística para urban canyon
- [03_MODELOS_PROPAGACION.md](03_MODELOS_PROPAGACION.md) — comparativa general de modelos
- [02_CORE_COMPUTE.md](02_CORE_COMPUTE.md) — vectorización NumPy/CuPy
- [06_TERRENO.md](06_TERRENO.md) — cómo se obtiene `terrain_heights`
