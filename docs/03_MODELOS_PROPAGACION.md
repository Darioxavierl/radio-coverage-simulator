# Modelos de Propagación: Guía Comparativa y de Integración

**Directorio:** `src/core/models/`
**Versión:** 2026-05-08

---

## 1. Resumen de los 5 Modelos Implementados

| Modelo | Clase | Archivo | Tipo |
|--------|-------|---------|------|
| Free Space | `FreeSpacePathLossModel` | `traditional/free_space.py` | Determinístico analítico |
| Okumura-Hata | `OkumuraHataModel` | `traditional/okumura_hata.py` | Empírico estadístico |
| COST-231 W-I | `COST231WalfischIkegamiModel` | `traditional/cost231.py` | Semi-determinístico |
| ITU-R P.1546 | `ITUR_P1546Model` | `traditional/itu_r_p1546.py` | Empírico punto-a-área |
| 3GPP TR 38.901 | `ThreGPP38901Model` | `gpp_3gpp/three_gpp_38901.py` | Probabilístico estocástico |

---

## 2. Tabla Comparativa de Características Técnicas

| Característica | Free Space | Okumura-Hata | COST-231 | ITU-R P.1546 | 3GPP 38.901 |
|----------------|-----------|--------------|---------|-------------|-------------|
| **Frecuencia** | Sin límite | 150–2000 MHz | 800–2000 MHz | 30–4000 MHz | 500–100000 MHz (0.5–100 GHz) |
| **Distancia** | Sin límite | 1–20 km | 20 m–5 km | 1–1000 km | 10 m–10 km |
| **Distinción LOS/NLOS** | No | No | Sí (heurístico) | Sí (radio horizon) | Sí (probabilístico) |
| **Uso de DEM/terreno** | No | Sí (h_eff) | Sí (h_eff + LOS) | Sí (h_eff + 3 tipos) | Opcional (Fresnel aprox.) |
| **Parámetros urbanos** | No | No | Sí (h_edif, w_calle, φ) | No | No |
| **Escenarios** | Único | Urban/Suburban/Rural | Urban/Suburban/Rural | Urban/Suburban/Rural | UMa/UMi/RMa |
| **Altura TX relevante** | No | Sí (30–200 m) | Sí (30–200 m) | Sí (10–3000 m) | Sí (por escenario) |
| **Unidades distancia interna** | km | km | km | km | **metros** |
| **Unidades frecuencia interna** | MHz | MHz | MHz | MHz | **GHz** (convierte de MHz) |

---

## 3. Tabla de Ecuaciones Clave

| Modelo | Ecuación principal | Constante clave |
|--------|-------------------|-----------------|
| Free Space | $20\log(d_{km}) + 20\log(f_{MHz}) + 32.45$ | 32.45 dB (derivado de Friis) |
| Okumura-Hata | $69.55 + 26.16\log(f) - 13.82\log(h_b) - a(h_m) + [44.9-6.55\log(h_b)]\log(d)$ | 69.55 dB |
| COST-231 | $L_0 + L_{\text{rtd}} + L_{\text{msd}} + C_f$ | Lrtd con −16.9 dB |
| ITU-R P.1546 | $L_0 + \Delta_h + \Delta_f + \Delta_{\text{env}}$ | k=4/3 para radio horizon |
| 3GPP 38.901 | $P_{LOS}\cdot PL_{LOS} + (1-P_{LOS})\cdot PL_{NLOS}$ | C2=−0.6 dB/m h_ue |

---

## 4. Guía de Selección de Modelo

### 4.1 Por Frecuencia

```
Frecuencia de operación:
├─ < 150 MHz (VHF bajo)
│     → ITU-R P.1546 (única opción válida en el sistema)
├─ 150–800 MHz (VHF/UHF bajo)
│     → Okumura-Hata (preferred)
│     → ITU-R P.1546 (alternativa)
├─ 800–2000 MHz (GSM, LTE, WiFi)
│     → Okumura-Hata (distancias > 1 km)
│     → COST-231 (urban canyon, dist < 5 km)
│     → ITU-R P.1546 (largo alcance > 20 km)
├─ 2000–4000 MHz (LTE-A, 5G sub-6)
│     → ITU-R P.1546 (hasta 4 GHz)
│     → 3GPP UMa/UMi (preferido para 5G)
└─ > 4000 MHz (mmWave 5G)
      → 3GPP 38.901 (único modelo válido)
      → Free Space (como referencia LOS)
```

### 4.2 Por Distancia

```
Distancia a cubrir:
├─ < 20 m → Free Space (referencia únicamente)
├─ 20 m – 1 km → COST-231 (urban) o Free Space (LOS)
├─ 1 km – 5 km → Okumura-Hata, COST-231, 3GPP UMi
├─ 5 km – 20 km → Okumura-Hata, ITU-R P.1546
└─ > 20 km → ITU-R P.1546 (diseñado para largo alcance)
```

### 4.3 Por Tipo de Entorno

| Entorno | Modelo Recomendado | Razón |
|---------|-------------------|-------|
| Urban macro celular (LTE/5G) | 3GPP UMa | Estándar de industria 5G |
| Urban micro / small cells | 3GPP UMi | Antenas bajo nivel de techos |
| Urban denso (calles, canyons) | COST-231 | Incorpora geometría de calles |
| Rural/suburbano clásico | Okumura-Hata | Calibrado para estas condiciones |
| Rural largo alcance / broadcast | ITU-R P.1546 | Diseñado para ello |
| LOS ideal / microondas | Free Space | Único apropiado |

---

## 5. Interfaz Común — Cómo los Llama CoverageCalculator

Todos los modelos implementan la misma interfaz:

```python
path_loss = model.calculate_path_loss(
    distances,       # np.ndarray, metros
    frequency,       # float, MHz
    tx_height,       # float, m AGL
    terrain_heights, # np.ndarray, msnm
    tx_elevation,    # float, msnm (default 0.0)
    environment,     # str
    **model_params   # parámetros específicos del modelo
)
# → np.ndarray, dB, mismo shape que distances
```

**Código de CoverageCalculator:**
```python
# src/core/coverage_calculator.py

def _calculate_path_loss(self, antenna, grid_lats, grid_lons, terrain_heights):
    # 1. Distancias Haversine (siempre en metros)
    distances = self._haversine_distances(
        antenna.lat, antenna.lon, grid_lats, grid_lons
    )  # shape (H, W), en metros

    # 2. Elevación del sitio TX (interpolada del DEM)
    antenna_elevation = self._get_elevation(antenna.lat, antenna.lon)

    # 3. Argumentos comunes a todos los modelos
    path_loss_args = {
        'distances':       distances,
        'frequency':       antenna.frequency_mhz,
        'tx_height':       antenna.height_agl,
        'terrain_heights': terrain_heights,
        'tx_elevation':    antenna_elevation,
        'environment':     simulation_params.get('environment', 'Urban'),
    }

    # 4. Parámetros específicos del modelo seleccionado
    model_params = simulation_params.get('model_params', {})
    path_loss_args.update(model_params)

    # 5. Calcular — todos usan la misma llamada
    path_loss = self.propagation_model.calculate_path_loss(**path_loss_args)

    return path_loss   # dB, shape (H, W)

# 6. RSRP
rsrp = antenna.tx_power_dbm + antenna.tx_gain_dbi - path_loss
```

---

## 6. Conversiones de Unidades Internas

Cada modelo convierte las distancias (siempre recibidas en metros) a sus unidades internas:

| Modelo | Conversión interna | Código |
|--------|-------------------|--------|
| Free Space | `d_km = distances / 1000` | `free_space.py` |
| Okumura-Hata | `d_km = distances / 1000` | `okumura_hata.py` |
| COST-231 | `d_km = distances_flat / 1000` | `cost231.py` |
| ITU-R P.1546 | `d_km = distances_flat / 1000` | `itu_r_p1546.py` |
| 3GPP 38.901 | **Sin convertir — usa metros** | `three_gpp_38901.py` |

> **Importante:** El modelo 3GPP es el único que trabaja con distancias en **metros**. Sus ecuaciones `C0 + C1·log10(d_m)` están calibradas para metros, por eso los intercepts (C0) son más altos.

**Conversión de frecuencia:**

| Modelo | Frecuencia interna |
|--------|-------------------|
| Free Space, Okumura-Hata, COST-231, P.1546 | MHz (sin conversión) |
| 3GPP 38.901 | GHz (`f_ghz = frequency / 1000`) |

---

## 7. Patrón de Integración del Terreno

Todos los modelos que usan el DEM aplican el mismo patrón de altura efectiva:

$$h_{tx,\text{eff}} = h_{\text{ant}} + h_{\text{elev,TX}} - \overline{h_{\text{terreno}}}$$

donde $\overline{h_{\text{terreno}}} = \text{mean}(\texttt{terrain\_heights})$ es la elevación promedio de la grilla.

```python
# Patrón uniforme en Okumura-Hata, COST-231 e ITU-R P.1546
terrain_avg = self.xp.mean(terrain_heights_flat)
h_eff = tx_height + tx_elevation - terrain_avg
h_eff = self.xp.maximum(h_eff, h_min)   # clipping inferior
h_eff = self.xp.minimum(h_eff, h_max)   # clipping superior
```

| Modelo | h_min | h_max |
|--------|-------|-------|
| Okumura-Hata | 30 m | 200 m |
| COST-231 | 30 m | 200 m |
| ITU-R P.1546 | Sin clipping | Sin clipping |
| 3GPP 38.901 | N/A (usa h_bs configurable) | N/A |

---

## 8. Condición LOS/NLOS por Modelo

| Modelo | Método LOS/NLOS | Descripción |
|--------|----------------|-------------|
| Free Space | Ninguno | Asume siempre LOS perfecto |
| Okumura-Hata | Ninguno | Pérdida mediana L₅₀ (ambas condiciones) |
| COST-231 | Heurístico: `delta_h > 30 m` | LOS uniforme para toda la grilla |
| ITU-R P.1546 | Radio horizon: `d ≤ 4.12·√(h_tx·h_rx)/100` | LOS/NLOS por punto |
| 3GPP 38.901 | Probabilístico: `P_LOS(d) = min(C1/d,1)·(1−e^{−d/C2}) + e^{−d/C2}` | Interpolación continua |

**Detalle de cada criterio:**

### COST-231 — Heurístico de Altura
```python
delta_h = (tx_height + tx_elevation) - mean(terrain_heights)
los_mask[:] = (delta_h > 30.0)   # toda la grilla con mismo estado
```

### P.1546 — Radio Horizon
```python
d_ho = 4.12 * sqrt(h_tx * h_rx) / 100   # km
is_los = (distances_km <= d_ho)          # por punto
```

### 3GPP — Probabilístico
```python
P_LOS(d) = min(C1/d, 1) * (1 - exp(-d/C2)) + exp(-d/C2)
PL = P_LOS * PL_LOS + (1 - P_LOS) * PL_NLOS   # por punto
```

---

## 9. CPU/GPU Abstraction — Patrón Compartido

Todos los modelos usan el mismo patrón de abstracción NumPy/CuPy:

```python
class AnyPropagationModel:
    def __init__(self, config=None, compute_module=None):
        self.xp = compute_module if compute_module is not None else np
        # self.xp = np  → CPU
        # self.xp = cp  → GPU CuPy

    def calculate_path_loss(self, distances, ...):
        distances = self.xp.asarray(distances)   # mueve a GPU si xp=cp
        result = 20.0 * self.xp.log10(distances) # operación vectorizada
        return result                             # ndarray en CPU o GPU
```

El `ComputeEngine` en `src/core/compute_engine.py` decide qué `compute_module` pasar según disponibilidad de GPU.

---

## 10. Comparación Numérica de Pérdidas (escenario común)

**Configuración:** 900 MHz, entorno Urban, tx_height=30 m AGL, distancia=2 km

| Modelo | PL (dB) | Diferencia vs FSPL |
|--------|---------|-------------------|
| Free Space | 97.5 | — (referencia) |
| Okumura-Hata | ~136 | +38.5 dB |
| COST-231 (NLOS) | ~140 | +42.5 dB |
| ITU-R P.1546 | ~130 | +32.5 dB |
| 3GPP UMa (probabilístico) | ~145 | +47.5 dB |

> La FSPL siempre da la pérdida más baja (cota inferior). Los modelos reales añaden pérdidas por reflexión, difracción y absorción.

---

## 11. Diagrama de Arquitectura

```
CoverageCalculator._calculate_path_loss()
    │
    │  distances (m), frequency (MHz), tx_height (m),
    │  terrain_heights (msnm), tx_elevation (msnm), environment
    │
    ├──► FreeSpacePathLossModel.calculate_path_loss()
    │    └─ FSPL = 32.45 + 20·log(d_km) + 20·log(f)
    │
    ├──► OkumuraHataModel.calculate_path_loss()
    │    ├─ h_eff = tx_height + tx_elev − mean(terrain)
    │    └─ L = 69.55 + 26.16·log(f) − 13.82·log(h_eff) − a(hm) + ...
    │
    ├──► COST231WalfischIkegamiModel.calculate_path_loss()
    │    ├─ h_eff = tx_height + tx_elev − mean(terrain)
    │    ├─ los_mask = (h_eff − mean_terrain > 30m)
    │    └─ PL = L0 + Lrtd + Lmsd[NLOS] + Cf
    │
    ├──► ITUR_P1546Model.calculate_path_loss()
    │    ├─ h_eff = tx_height + tx_elev − mean(terrain)
    │    ├─ d_ho = 4.12·√(h_tx·h_rx)/100
    │    ├─ is_los = (d_km ≤ d_ho)
    │    └─ PL = L0 + Δh + Δf + Δenv
    │
    └──► ThreGPP38901Model.calculate_path_loss()
         ├─ f_ghz = frequency / 1000
         ├─ P_LOS(d_m) = min(C1/d,1)·(1−e^−d/C2) + e^−d/C2
         ├─ PL_LOS = C0 + C1·log10(d_m) + 20·log10(f_ghz)
         ├─ PL_NLOS = C0 + C1·log10(d_m) + 20·log10(f_ghz) + C2·(h_ue−1.5)
         └─ PL = P_LOS·PL_LOS + (1−P_LOS)·PL_NLOS
              │
              └─ [opcional] + terrain_correction (Fresnel aprox.)

    ↓
rsrp = P_tx + G_tx − path_loss   [dBm]
```

---

## 12. Documentación Detallada de Cada Modelo

| Documento | Modelo | Contenido |
|-----------|--------|-----------|
| [03A_OKUMURA_HATA_v2.md](03A_OKUMURA_HATA_v2.md) | Okumura-Hata | 7 ecuaciones, a(hm), Urban/Suburban/Rural, COST-231 ext. |
| [03B_COST231_v2.md](03B_COST231_v2.md) | COST-231 | L0, Lrtd, Lori, Lmsd, Cf, LOS/NLOS, geometría urban canyon |
| [03C_ITU_R_P1546_v2.md](03C_ITU_R_P1546_v2.md) | ITU-R P.1546 | L0, Δh, Δf, Δenv, radio horizon, 3 tipos de terreno |
| [03D_3GPP_38901_v2.md](03D_3GPP_38901_v2.md) | 3GPP TR 38.901 | P_LOS, PL_LOS, PL_NLOS, UMa/UMi/RMa, corrección Fresnel |
| [03E_FREE_SPACE_v2.md](03E_FREE_SPACE_v2.md) | Free Space | Derivación 32.45, FSPL, tablas de referencia |

---

**Ver también:**
- [02_CORE_COMPUTE.md](02_CORE_COMPUTE.md) — vectorización NumPy/CuPy
- [06_TERRENO.md](06_TERRENO.md) — fuente y formato del DEM
- [04_PIPELINE_SIMULACION.md](04_PIPELINE_SIMULACION.md) — flujo completo de simulación
