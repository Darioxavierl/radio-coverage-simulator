# Modelos de Propagación: Guía Comparativa y de Integración

**Directorio:** `src/core/models/`
**Versión:** 2026-05-08

---

## 1. Resumen de los 6 Modelos Implementados

| Modelo | Clase | Archivo | Tipo |
|--------|-------|---------|------|
| Free Space | `FreeSpacePathLossModel` | `traditional/free_space.py` | Determinístico analítico |
| Okumura-Hata | `OkumuraHataModel` | `traditional/okumura_hata.py` | Empírico estadístico |
| COST-231 W-I | `COST231WalfischIkegamiModel` | `traditional/cost231.py` | Semi-determinístico |
| **COST-231 Hata** | **`COST231HataModel`** | **`traditional/cost231_hata.py`** | **Empírico estadístico (4G LTE)** |
| ITU-R P.1546 | `ITUR_P1546Model` | `traditional/itu_r_p1546.py` | Empírico punto-a-área |
| 3GPP TR 38.901 | `ThreGPP38901Model` | `gpp_3gpp/three_gpp_38901.py` | Probabilístico estocástico |

---

## 2. Tabla Comparativa de Características Técnicas

| Característica | Free Space | Okumura-Hata | COST-231 W-I | **COST-231 Hata** | ITU-R P.1546 | 3GPP 38.901 |
|----------------|-----------|--------------|---------|-----------|-------------|-------------|
| **Frecuencia** | Sin límite | 150–2000 MHz | 800–2000 MHz | **1500–2000 MHz** | 30–4000 MHz | 500–100000 MHz (0.5–100 GHz) |
| **Distancia** | Sin límite | 1–20 km | 20 m–5 km | **0.02–5 km** | 1–1000 km (clipping a 1 km) | 10 m–10 km |
| **Distinción LOS/NLOS** | No | No | Sí (geométrico con fallback heurístico) | **No (empírico con validity_mask)** | **No binario** (TCA continuo §4.5) | Sí (probabilístico) |
| **Uso de DEM/terreno** | No | Sí (h_eff) | Sí (LOS geométrico + roughness local) | **Sí (h_eff con referencia de terreno)** | Sí (h_eff 3–15 km + TCA + clutter P.2108-1) | Opcional (knife-edge P.526 aditivo) |
| **Parámetros urbanos** | No | No | Sí (h_edif, w_calle, φ) | **Sí (C_m)** | No | No |
| **Escenarios** | Único | Urban/Suburban/Rural | Urban/Suburban/Rural | **Urban (medium/large)** | Urban/Suburban/Rural | UMa/UMi/RMa |
| **Altura TX relevante** | No | Sí (30–200 m) | Sí (30–200 m) | **Sí (30–200 m)** | Sí (10–3000 m) | Sí (por escenario) |
| **Unidades distancia interna** | km | km | km | **km** | km | **metros** |
| **Unidades frecuencia interna** | MHz | MHz | MHz | **MHz** | MHz | **GHz** (convierte de MHz) |

---

## 3. Tabla de Ecuaciones Clave

| Modelo | Ecuación principal | Constante clave |
|--------|-------------------|-----------------|
| Free Space | $20\log(d_{km}) + 20\log(f_{MHz}) + 32.45$ | 32.45 dB (derivado de Friis) |
| Okumura-Hata | $69.55 + 26.16\log(f) - 13.82\log(h_b) - a(h_m) + [44.9-6.55\log(h_b)]\log(d)$ | 69.55 dB |
| COST-231 W-I | $L_0 + L_{\text{rtd}} + L_{\text{msd}} + C_f$ | Lrtd con −16.9 dB |
| **COST-231 Hata** | **$46.3 + 33.9\log(f) - 13.82\log(h_b) - a(h_m) + [44.9-6.55\log(h_b)]\log(d) + C_m$** | **46.3 dB (vs 69.55 OH)** |
| ITU-R P.1546 | $PL = 139.3 + 20\log(f_{MHz}) - E(f,d,h_{eff}) + \Delta_{TCA} + \Delta_{clutter} + \Delta_{percentile}$ | 139.3 dB (conversión E→PL) |
| 3GPP 38.901 | $PL = P_{LOS}\cdot PL_{LOS}(d_{3D}, f_{GHz}) + (1-P_{LOS})\cdot PL_{NLOS}(d_{3D}, f_{GHz})$ | mezcla LOS/NLOS + `max(PL_LOS, PL'_NLOS)` |

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
├─ 800–1500 MHz (GSM, WiFi)
│     → Okumura-Hata (distancias > 1 km)
│     → COST-231 W-I (urban canyon, dist < 5 km)
│     → ITU-R P.1546 (largo alcance > 20 km)
├─ 1500–2000 MHz (4G LTE)
│     → COST-231 Hata (recomendado para 4G urban)
│     → Okumura-Hata (extrapolación válida)
│     → ITU-R P.1546 (largo alcance)
│     → 3GPP UMa/UMi (alternativa 5G-ready)
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
| Urban macro (4G LTE clásico) | COST-231 Hata | Optimizado para 1500-2000 MHz |
| Urban micro / small cells | 3GPP UMi o COST-231 Hata | Antenas bajo nivel de techos |
| Urban denso (calles, canyons) | COST-231 W-I | Incorpora geometría de calles |
| Rural/suburbano clásico | Okumura-Hata | Calibrado para estas condiciones |
| Rural largo alcance / broadcast | ITU-R P.1546 | Diseñado para ello |
| LOS ideal / microondas | Free Space | Único apropiado |

---

## 5. Interfaz Común — Cómo los Llama CoverageCalculator

Todos los modelos implementan la misma llamada pública desde `CoverageCalculator`, pero no todos retornan exactamente el mismo tipo intermedio. Algunos devuelven directamente un `ndarray`; otros retornan un `dict` con `path_loss` y metadatos de validez.

```python
result = model.calculate_path_loss(
    distances=distances,          # np.ndarray, metros
    frequency=antenna.frequency_mhz,
    tx_height=antenna.height_agl,
    tx_elevation=tx_elevation,
    terrain_heights=terrain_heights,
    **model_params
)

path_loss = result['path_loss'] if isinstance(result, dict) else result
```

**Código de CoverageCalculator:**
```python
# src/core/coverage_calculator.py
result = model.calculate_path_loss(**path_loss_args)
path_loss = result['path_loss'] if isinstance(result, dict) else result

antenna_gain = self._apply_antenna_pattern(...)
rsrp = antenna.tx_power_dbm + antenna_gain - path_loss
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

Los modelos que consumen DEM no comparten un único esquema de altura efectiva. Cada uno usa el terreno de manera distinta:

| Modelo | Uso del terreno en código |
|--------|---------------------------|
| Okumura-Hata | `h_b,eff = h_tx + z_tx - z_ref`, con `z_ref` configurable (`global_mean`, `local_annulus_mean`, `tx_local_mean`) |
| COST-231 W-I | terreno para LOS geométrico, `building_height` local estimado desde roughness y altura efectiva TX basada en promedio del terreno |
| COST-231 Hata | `h_b,eff = h_tx + z_tx - z_ref`, con los mismos métodos de referencia que Okumura-Hata |
| ITU-R P.1546 | `h_eff = h_tx + z_tx - z_mean(3–15 km)` cuando hay DEM y trayectos largos; si `d < 15 km`, usa `h_tx_AGL` |
| 3GPP 38.901 | no calcula `h_eff`; usa `h_bs`/`h_ue` y opcionalmente una corrección knife-edge aditiva sobre DEM |

---

## 8. Condición LOS/NLOS por Modelo

| Modelo | Método LOS/NLOS | Descripción |
|--------|----------------|-------------|
| Free Space | Ninguno | Asume siempre LOS perfecto |
| Okumura-Hata | Ninguno | Pérdida mediana L₅₀ (ambas condiciones) |
| COST-231 | Geométrico por perfil radial; fallback heurístico si no hay perfiles | LOS/NLOS por receptor |
| ITU-R P.1546 | TCA continuo: `ΔE = f(arctan(z_rel/d))` | Corrección gradual por punto |
| 3GPP 38.901 | Probabilístico: `P_LOS(d) = min(C1/d,1)·(1−e^{−d/C2}) + e^{−d/C2}` | Interpolación continua |

**Detalle de cada criterio:**

### COST-231 — Geométrico con fallback heurístico
```python
if terrain_profiles is not None:
    los_mask = self._calculate_los_nlos_geometric_vectorized(...)
else:
    los_mask = self._determine_los_nlos_legacy(...)
```

### P.1546 — TCA Continuo (sin LOS/NLOS binario)

P.1546 **no** implementa LOS/NLOS binario (`has_los_nlos = False`). En su lugar
aplica una corrección continua de Terrain Clearance Angle (§4.5) basada en la función $J(\theta)$ del estándar:

```python
theta_tc = max(theta_i_en_ventana_0_15_km_desde_RX)
t = theta_tc - 0.1
J_theta = 6.9 + 20 * log10(sqrt(t * t + 1) + t)
tca_db = where(theta_tc > 0.0, J_theta, 0.0)
```

Existe `_calculate_radio_horizon(h_tx, h_rx)` = `4.12 * (sqrt(h_tx) + sqrt(h_rx))` km,
pero es un método **informativo** que **no se invoca** en `calculate_path_loss`.

### 3GPP — Probabilístico
```python
P_LOS(d) = min(C1/d, 1) * (1 - exp(-d/C2)) + exp(-d/C2)
PL = P_LOS * PL_LOS + (1 - P_LOS) * PL_NLOS   # por punto

# Si use_dem=True:
PL = PL + L_diff   # corrección knife-edge aditiva, no ponderada por (1 - P_LOS)
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
    │    ├─ h_eff = h_tx + z_tx − z_mean(3-15km)        [§4.3]
    │    ├─ E = interpolar_3D(f, d, h_eff)              [tablas 100/600/2000 MHz]
    │    ├─ TCA = max(arctan(z_rel/d))                  [§4.5 continuo]
    │    ├─ ΔE = TCA_corr + clutter_P2108               [P.2108-1]
    │    └─ PL = 139.3 + 20·log(f) − E + ΔE            [§8.1]
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
    _apply_antenna_pattern()          ← correccion independiente del modelo
    G_antena(φ, θ) = G_max + A_H(φ) + A_V(θ)  [patron 3D]

    ↓
rsrp = P_tx + G_antena(φ, θ) − path_loss   [dBm]
```

> **Independencia del patron de antena:** La correccion de ganancia azimutal y vertical se aplica identicamente sobre cualquier modelo de propagacion. El modelo calcula cuanto atenua el medio; el patron de antena calcula cuanto atenua la direccion. Se combinan de forma aditiva en dBm.

---

## 12. Patron de Radiacion de Antena

### 12.1 Fundamento y universalidad

El patron de antena modela como el hardware distribuye la potencia en el espacio. Las ecuaciones son la aproximacion gaussiana del estandar **3GPP TR 38.901 \u00a77.3.2**, equivalente a la de 3GPP TR 36.814 (LTE, 2010) e ITU-R M.2135 (2009). No son exclusivas de 5G; el estandar 3GPP es la referencia canonica para la misma formula que aplica a cualquier tipo de antena sectorial o direccional.

### 12.2 Patron horizontal

$$A_H(\phi) = -\min\!\left[12\left(\frac{\phi}{\phi_{3dB}}\right)^2,\ 30\right] \text{ dB}$$

- $\phi$: angulo azimutal entre el punto receptor y el azimuth de la antena
- $\phi_{3dB}$: `horizontal_beamwidth` — apertura a −3 dB (HPBW completo)
- Para omnidireccional: $A_H = 0$ dB

### 12.3 Patron vertical

$$A_V(\theta) = -\min\!\left[12\left(\frac{\theta - \theta_{tilt}}{\theta_{3dB}}\right)^2,\ 30\right] \text{ dB}$$

- $\theta = \arctan(\Delta h / d_{2D})$: angulo de elevacion TX→RX (positivo = RX por debajo del TX)
- $\theta_{tilt} = \theta_{mech} + \theta_{elec}$: tilt efectivo total
- $\theta_{3dB}$: `vertical_beamwidth`

### 12.4 Patron total 3D

$$G(\phi, \theta) = G_{max} - \min\!\left[-(A_H(\phi) + A_V(\theta)),\ 30\right] \text{ dB}$$

Implementado en `CoverageCalculator._apply_antenna_pattern()`. Requiere `distances` y `terrain_heights` para el patron vertical; si no se proporcionan, aplica solo $A_H$ (modo retrocompatible).

---

## 13. Documentación Detallada de Cada Modelo

| Documento | Modelo | Contenido |
|-----------|--------|-----------|
| [03A_OKUMURA_HATA.md](03A_OKUMURA_HATA.md) | Okumura-Hata | 7 ecuaciones, a(hm), Urban/Suburban/Rural, COST-231 ext. |
| [03B_COST231.md](03B_COST231.md) | COST-231 W-I | L0, Lrtd, Lori, Lmsd, Cf, LOS/NLOS, geometría urban canyon |
| [03C_ITU_R_P1546.md](03C_ITU_R_P1546.md) | ITU-R P.1546 | pipeline 5 pasos: h_eff, tablas ITU, TCA §4.5, clutter P.2108-1, conversión E→PL |
| [03D_3GPP_38901.md](03D_3GPP_38901.md) | 3GPP TR 38.901 | P_LOS, PL_LOS, PL_NLOS, UMa/UMi/RMa, corrección Fresnel |
| [03E_FREE_SPACE.md](03E_FREE_SPACE.md) | Free Space | Derivación 32.45, FSPL, tablas de referencia |

---

**Ver también:**
- [02_CORE_COMPUTE.md](02_CORE_COMPUTE.md) — vectorización NumPy/CuPy
- [06_TERRENO.md](06_TERRENO.md) — fuente y formato del DEM
- [04_PIPELINE_SIMULACION.md](04_PIPELINE_SIMULACION.md) — flujo completo de simulación
