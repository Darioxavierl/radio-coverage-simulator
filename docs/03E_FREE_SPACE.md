# Modelo Free Space Path Loss: Documentación Técnica Exhaustiva

**Archivo fuente:** `src/core/models/traditional/free_space.py`
**Clase:** `FreeSpacePathLossModel`
**Versión:** 2026-05-08

---

## 1. Descripción del Modelo

El modelo **Free Space Path Loss (FSPL)** es el modelo de propagación más fundamental. Calcula la atenuación de una señal electromagnética que se propaga en un medio sin obstrucciones, sin reflexiones y sin absorción — las condiciones del espacio libre.

### 1.1 Fundamento Físico

La pérdida en espacio libre se deriva directamente de la geometría esférica: la potencia se distribuye uniformemente sobre la superficie de una esfera de radio $d$. El área de la esfera crece como $4\pi d^2$, de modo que la densidad de potencia cae con $d^{-2}$ (20 dB/década).

La fórmula completa derivada de la ecuación de Friis (1946) es:

$$\text{FSPL} = \left(\frac{4\pi d f}{c}\right)^2$$

En dB:

$$\text{FSPL}_{\text{dB}} = 20\,\log_{10}(d) + 20\,\log_{10}(f) + 20\,\log_{10}\!\left(\frac{4\pi}{c}\right)$$

### 1.2 Derivación de la Constante 32.45

El término constante $20\,\log_{10}(4\pi/c)$ depende de las unidades usadas para $d$ y $f$:

Si $d$ en **km** y $f$ en **MHz**:

$$20\,\log_{10}\!\left(\frac{4\pi}{3\times10^8}\right) + 20\,\log_{10}(10^3) + 20\,\log_{10}(10^6)$$

$$= 20\,\log_{10}(4.189\times10^{-8}) + 60 + 120$$

$$= 20\,\times(-7.378) + 180 = -147.56 + 180 = 32.44 \approx \boxed{32.45}$$

La constante 32.45 es matemáticamente exacta para $d$ en km y $f$ en MHz bajo las condiciones de espacio libre.

### 1.3 Tipo de Modelo

| Aspecto | Descripción |
|---------|-------------|
| Tipo | Determinístico — solución cerrada analítica |
| Condición LOS/NLOS | Solo LOS (sin obstrucciones) |
| Uso de terreno | No — completamente ignorado |
| Vectorización | CPU (NumPy) / GPU (CuPy) via `self.xp` |
| Uso típico | Referencia mínima de pérdida; lanzamiento de rayo LOS |

---

## 2. Rangos de Aplicación

| Parámetro | Descripción |
|-----------|-------------|
| Frecuencia | Cualquiera — sin limitación de modelo |
| Distancia | > 0 (protegido contra log(0) con mínimo 0.001 km) |
| Entorno | Solo válido en LOS sin obstrucciones |
| Altura TX/RX | No afecta el resultado |

> **Importante:** La FSPL es un **límite inferior** de pérdida. Ningún entorno real tiene pérdida menor que la FSPL. Todos los demás modelos deben dar valores ≥ FSPL para distancias equivalentes.

---

## 3. Entrada y Salida del Método Principal

**Ubicación:** `free_space.py`, método `calculate_path_loss()`

### 3.1 Parámetros de Entrada

```python
def calculate_path_loss(
    self,
    distances,         # np.ndarray, metros, shape (N,) o (H, W)
    frequency,         # float, MHz
    tx_height,         # float, metros AGL — IGNORADO
    terrain_heights,   # np.ndarray — IGNORADO
    tx_elevation=0.0,  # float — IGNORADO
    environment='Urban',  # str — IGNORADO
    **kwargs
)
```

**Nota:** `tx_height`, `terrain_heights`, `tx_elevation` y `environment` son aceptados por la firma para mantener **compatibilidad con la interfaz común** de todos los modelos, pero **no se usan en el cálculo**.

### 3.2 Salida

```python
# Retorna
path_loss  # np.ndarray, dB, mismo shape que distances
           # Valores: siempre positivos, ≥ 20 dB para cualquier distancia/frecuencia realista
```

---

## 4. Ecuación Implementada

$$\boxed{\text{FSPL (dB)} = 20\,\log_{10}(d_{\text{km}}) + 20\,\log_{10}(f_{\text{MHz}}) + 32.45}$$

**Código real:**
```python
# free_space.py, método calculate_path_loss()

# Protección contra log(0): distancia mínima 0.001 km = 1 metro
d_km = self.xp.maximum(distances / 1000.0, 0.001)

fspl = (20.0 * self.xp.log10(d_km)
        + 20.0 * self.xp.log10(frequency)
        + 32.45)

return fspl
```

---

## 5. Protección contra log(0)

El modelo aplica una protección numérica para distancias cercanas a cero:

```python
d_km = self.xp.maximum(distances / 1000.0, 0.001)
#                                             ↑
#                             mínimo 0.001 km = 1 m
```

Sin esta protección, $\log_{10}(0) = -\infty$, lo que causaría `NaN` o `-inf` en el array de salida y corrompería los mapas de cobertura.

**Consecuencia:** Para distancias < 1 m, el modelo devuelve la FSPL a 1 m. A 900 MHz:
```
FSPL(1m) = 20·log10(0.001) + 20·log10(900) + 32.45
         = 20·(-3) + 59.09 + 32.45
         = -60 + 59.09 + 32.45
         = 31.54 dB
```

---

## 6. Flujo de Cálculo

```
Entrada: distances (m), frequency (MHz)
         [tx_height, terrain_heights, tx_elevation, environment: ignorados]

     │
     ▼
┌────────────────────────────────────────────┐
│ 1. Conversión metros → km                 │
│    d_km = distances / 1000                │
└────────────────────────────────────────────┘
     │
     ▼
┌────────────────────────────────────────────┐
│ 2. Protección log(0)                      │
│    d_km = max(d_km, 0.001)               │
└────────────────────────────────────────────┘
     │
     ▼
┌────────────────────────────────────────────┐
│ 3. Fórmula FSPL                          │
│    FSPL = 20·log10(d_km)                 │
│         + 20·log10(f_MHz)                │
│         + 32.45                          │
└────────────────────────────────────────────┘
     │
     ▼
Salida: fspl (dB), shape = shape(distances)
```

---

## 7. Tablas Numéricas de Referencia

### 7.1 FSPL por Distancia y Frecuencia

| d \ f | 900 MHz | 1800 MHz | 2100 MHz | 3500 MHz | 28 GHz |
|-------|---------|----------|----------|----------|--------|
| 100 m | 71.5 dB | 77.6 dB | 79.4 dB | 84.1 dB | 101.9 dB |
| 500 m | 85.9 dB | 92.0 dB | 93.8 dB | 98.5 dB | 116.4 dB |
| 1 km | 91.5 dB | 97.5 dB | 99.4 dB | 104.1 dB | 121.9 dB |
| 2 km | 97.5 dB | 103.6 dB | 105.4 dB | 110.1 dB | 127.9 dB |
| 5 km | 105.4 dB | 111.4 dB | 113.3 dB | 118.0 dB | 135.8 dB |
| 10 km | 111.5 dB | 117.5 dB | 119.4 dB | 124.1 dB | 141.9 dB |

### 7.2 Incremento por Duplicar Distancia (siempre 6 dB)

$$\text{FSPL}(2d) - \text{FSPL}(d) = 20\,\log_{10}(2) = 6.02 \text{ dB}$$

### 7.3 Incremento por Duplicar Frecuencia (siempre 6 dB)

$$\text{FSPL}(2f) - \text{FSPL}(f) = 20\,\log_{10}(2) = 6.02 \text{ dB}$$

---

## 8. Por Qué se Ignora el Terreno

El modelo Free Space **no** usa `terrain_heights` ni `tx_height` por razones conceptuales:

1. **Definición de Free Space:** El modelo asume que no hay obstrucciones entre TX y RX. Incorporar el terreno contradice esta premisa.

2. **Uso correcto en este sistema:** La FSPL se usa como:
   - Referencia de límite inferior para otros modelos
   - Cálculo rápido de cobertura en condiciones LOS ideal
   - Componente $L_0$ (baseline) dentro de P.1546 y COST-231

3. **Compatibilidad de interfaz:** Los parámetros `tx_height`, `terrain_heights` etc. se aceptan pero se ignoran mediante `**kwargs`. Esto permite que `CoverageCalculator` llame a todos los modelos con la misma firma sin casos especiales.

---

## 9. Cuándo Usar Free Space

| Caso de Uso | Recomendado |
|-------------|-------------|
| LOS punto-a-punto microondas | ✓ Modelo adecuado |
| Cálculo de presupuesto de enlace teórico | ✓ |
| Referencia mínima de atenuación | ✓ |
| Cobertura satelital | ✓ |
| Celular en entorno urbano/rural | ✗ Subestima pérdida real |
| Predicción de cobertura realista | ✗ Prefiere Okumura-Hata / P.1546 |
| Distancias < 100 m en interior | ✗ Prefiere modelos de indoor |

---

## 10. Ejemplo de Cálculo Completo

**Escenario:** Enlace LOS microondas, 2.4 GHz, 3 km

```python
import numpy as np
from src.core.models.traditional.free_space import FreeSpacePathLossModel

model = FreeSpacePathLossModel()

distances = np.array([3000.0])   # metros
frequency = 2400.0               # MHz

fspl = model.calculate_path_loss(
    distances=distances,
    frequency=frequency,
    tx_height=30,           # ignorado
    terrain_heights=np.array([2500.0]),  # ignorado
)

print(f"FSPL = {fspl[0]:.1f} dB")
```

**Cálculo manual:**
```
d_km = 3000 / 1000 = 3.0 km
f    = 2400 MHz

FSPL = 20·log10(3.0) + 20·log10(2400) + 32.45
     = 20·0.477 + 20·3.380 + 32.45
     = 9.54 + 67.60 + 32.45
     = 109.6 dB

→ Si P_tx = 30 dBm, G_tx = G_rx = 10 dBi:
  P_rx = 30 + 10 + 10 − 109.6 = −59.6 dBm
```

---

## 11. Relación con los Demás Modelos

La FSPL es el **punto de partida** de los otros modelos:

| Modelo | Relación con FSPL |
|--------|-------------------|
| COST-231 | Usa FSPL como `L_base`; suma Lrtd + Lmsd + Cf |
| ITU-R P.1546 | Usa FSPL como `L_0`; suma Δh + Δf + Δenv |
| Okumura-Hata | No deriva de FSPL, pero produce valores similares en LOS |
| 3GPP TR 38.901 | No usa FSPL; intercept C0 absorbe el término constante |

---

## 12. Cómo lo Invoca CoverageCalculator

```python
# src/core/coverage_calculator.py

path_loss_args = {
    'distances':       distances,         # metros
    'frequency':       antenna.frequency_mhz,
    'tx_height':       antenna.height_agl,     # aceptado pero ignorado
    'terrain_heights': terrain_heights,         # aceptado pero ignorado
    'tx_elevation':    antenna_elevation,       # aceptado pero ignorado
}
path_loss = free_space_model.calculate_path_loss(**path_loss_args)

# RSRP = P_tx + G_tx − FSPL  (límite superior teórico de RSRP)
rsrp = antenna.tx_power_dbm + antenna.tx_gain_dbi - path_loss
```

---

**Ver también:**
- [03_MODELOS_PROPAGACION.md](03_MODELOS_PROPAGACION.md) — comparativa general de modelos
- [03A_OKUMURA_HATA.md](03A_OKUMURA_HATA.md) — primera mejora sobre FSPL para entornos reales
- [03C_ITU_R_P1546.md](03C_ITU_R_P1546.md) — modelo punto-área empírico ITU (tablas, no usa FSPL como baseline)
