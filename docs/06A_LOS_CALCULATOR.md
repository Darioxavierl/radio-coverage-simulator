# LOSCalculator: Cálculo Geométrico de Línea de Visión (LOS)

**Archivo:** `src/utils/los_calculator.py`  
**Versión:** 2026-05-15  
**Clase:** `LOSCalculator`

---

## 1. Propósito

`LOSCalculator` determina, para cada píxel de la grilla de simulación, si existe visibilidad directa (Line-of-Sight, LOS) entre la antena transmisora y el punto receptor. La operación es **puramente geométrica**: no interviene ningún modelo de propagación radioeléctrica. El resultado se usa como capa de visualización independiente en el mapa y como entrada opcional al modelo 3GPP TR 38.901 (Modo 2 con difracción knife-edge).

---

## 2. Dependencias

| Dependencia | Función |
|---|---|
| `TerrainLoader.get_radial_profiles()` | Proveedor de perfiles de elevación DEM entre TX y cada punto RX de la grilla |
| NumPy | Vectorización de todos los cálculos (sin bucles Python) |
| matplotlib Agg | Renderizado de la imagen PNG resultado |

`LOSCalculator` **no** accede directamente al raster DEM; delega la lectura de elevaciones a `TerrainLoader`, que gestiona la transformación de coordenadas, el muestreo raster vectorizado y la extracción de perfiles radiales.

---

## 3. Fundamento Matemático

### 3.1 Definición de alturas absolutas

Sea el transmisor TX ubicado en coordenadas $(lat_{tx}, lon_{tx})$ con:

$$z_{tx} = z_{terreno,tx} + h_{agl}$$

donde $z_{terreno,tx}$ es la elevación del terreno en el transmisor [m ASL] y $h_{agl}$ es la altura de la antena sobre el terreno [m AGL].

Sea un punto receptor RX en coordenadas $(lat_{rx}, lon_{rx})$, con elevación del terreno:

$$z_{rx} = \text{profile}[-1]$$

obtenida del último muestra del perfil DEM entre TX y RX.

### 3.2 Línea de visión directa (geometría esférica simplificada)

La recta en el espacio de elevaciones que une TX con RX se parametriza como:

$$z_{los}(t) = z_{tx} + t \cdot (z_{rx} - z_{tx}), \quad t \in [0, 1]$$

El perfil se muestrea en `n_samples = 50` puntos equiespaciados:

$$t_j = \frac{j}{n_{samples} - 1}, \quad j = 0, 1, \ldots, n_{samples}-1$$

de modo que $t_0 = 0$ corresponde al TX y $t_{49} = 1$ corresponde al RX.

### 3.3 Criterio de bloqueo (NLOS)

Un punto receptor está en **sombra (NLOS)** si existe al menos un punto intermedio del perfil del terreno que supera la línea de visión directa:

$$\text{NLOS} \iff \exists\, j \in \{1, \ldots, n_{samples}-2\} \text{ tal que } \text{profile}_j > z_{los}(t_j)$$

Los extremos $j = 0$ (TX) y $j = n_{samples}-1$ (RX) se excluyen deliberadamente para evitar falsos positivos causados por discretización espacial del DEM y por el muestreo del perfil en sus extremos.

El punto receptor es **LOS** si y solo si:

$$\text{LOS} \iff \neg\, \text{NLOS}$$

### 3.4 Implementación vectorizada (NumPy)

Para una grilla de $N = H \times W$ puntos receptores, todos los cálculos se ejecutan simultáneamente:

```
profiles  → shape (N, n_samples)   # elevaciones DEM, de TerrainLoader
z_rx      → shape (N,)             # profiles[:, -1]
t         → shape (n_samples,)     # linspace(0, 1, n_samples)
z_los     → shape (N, n_samples)   # z_tx + t * (z_rx - z_tx)  [broadcasting]
obstructed→ shape (N,)  bool       # any(profiles[:,1:-1] > z_los[:,1:-1], axis=1)
los_flat  → shape (N,)  float32    # (~obstructed).astype(float32)
los_map   → shape (H, W) float32   # reshape de los_flat
```

No hay ningún bucle Python sobre puntos de la grilla; toda la comparación se realiza en una sola operación `np.any(..., axis=1)`.

---

## 4. Interfaz de la Clase

### 4.1 `compute_los_map()`

```python
def compute_los_map(
    tx_lat: float,
    tx_lon: float,
    tx_height_agl: float,
    tx_terrain_elev: float,
    grid_lats: np.ndarray,   # shape (H, W)
    grid_lons: np.ndarray,   # shape (H, W)
    terrain_loader: TerrainLoader,
    n_samples: int = 50
) -> np.ndarray  # float32, shape (H, W)
```

**Retorna:** array float32 `(H, W)` donde `1.0` = LOS y `0.0` = sombra (NLOS).

**Caso especial:** si `terrain_loader` es `None` o no tiene datos cargados, devuelve un array de unos (todo-LOS) y registra un warning en el logger.

### 4.2 `generate_los_image()`

```python
def generate_los_image(
    los_map: np.ndarray,  # float32, shape (H, W)
    alpha: float = 0.7
) -> str
```

Genera una imagen PNG del mapa LOS codificada en base64 como data URL (`data:image/png;base64,...`). En caso de error, devuelve `""`.

**Codificación de colores:**

| Valor | Color | Hex | Significado |
|---|---|---|---|
| `1.0` | Verde | `#00aa44` | LOS — visibilidad directa |
| `0.0` | Naranja | `#ff6600` | Sombra — bloqueado por el terreno |

El canal alfa de cada píxel se fija al valor del parámetro `alpha` (transparencia global). El fondo del área sin datos es completamente transparente (`alpha = 0`).

---

## 5. Integración en el Pipeline de Simulación

`LOSCalculator` se instancia **una sola vez** dentro de `SimulationWorker.run()`, antes del bucle de antenas:

```python
los_calc = LOSCalculator()
```

Por cada antena en el bucle:

```python
los_map = los_calc.compute_los_map(
    tx_lat, tx_lon, tx_height_agl, terrain_elev_tx,
    grid_lats, grid_lons, terrain_loader
)
los_image_url = los_calc.generate_los_image(los_map)

individual[antenna_id]['los_map'] = los_map
individual[antenna_id]['los_image_url'] = los_image_url
```

El mapa LOS **agregado** (visibilidad de cualquier antena) se calcula tras el bucle:

```python
stack_los_maps = np.stack([r['los_map'] for r in individual.values()], axis=0)
agg_los_map = np.max(stack_los_maps, axis=0)  # 1.0 si al menos una antena tiene LOS
agg_los_image_url = los_calc.generate_los_image(agg_los_map)
```

### Diagrama de flujo

```
SimulationWorker.run()
    │
    ├─ los_calc = LOSCalculator()
    │
    ├─ Para cada antena:
    │       ├─ terrain_loader.get_radial_profiles(...)  →  profiles (N, 50)
    │       ├─ compute_los_map(...)                     →  los_map (H, W) float32
    │       ├─ generate_los_image(los_map)              →  los_image_url (base64 PNG)
    │       └─ guarda en individual[antenna_id]
    │
    └─ Agregado:
            ├─ np.max(stack_los_maps, axis=0)           →  agg_los_map
            └─ generate_los_image(agg_los_map)          →  agg_los_image_url
```

---

## 6. Visualización en el Mapa (Leaflet)

Las imágenes LOS se registran como `L.imageOverlay` en el mapa Leaflet a través de la señal `MapBridge.add_los_layer`. Todas las capas LOS **inician ocultas** (sin `.addTo(map)`); el usuario las activa desde el panel de control de capas. Cuando el usuario activa una capa LOS, el listener `map.on('overlayadd', ...)` en `MapWidget` muestra la leyenda estática verde/naranja mediante `showLOSLegend()`.

Ver `src/ui/widgets/map_widget.py` → sección `addLOSLayer()` y `showLOSLegend()`.

---

## 7. Limitaciones Conocidas

| Limitación | Impacto | Alternativa |
|---|---|---|
| Depende de la resolución del DEM | A menor resolución, menor precisión del límite LOS/NLOS | Cargar DEM de mayor resolución (ALOS 12.5m, SRTM 30m) |
| No modela difracción | Un obstáculo bloquea totalmente aunque haya difracción real | Usar 3GPP TR 38.901 Modo 2 con P.526 knife-edge |
| Curvatura terrestre ignorada | Error < 1% para distancias < 50 km | Añadir corrección $-k \cdot d^2$ si se usan distancias > 50 km |
| `n_samples = 50` fijo | Perfiles muy largos pueden perder obstrucciones pequeñas | Aumentar `n_samples` al llamar `compute_los_map()` |
| Sin zona de Fresnel | Un obstáculo justo bajo la línea directa puede no detectarse | Implementar radio de Fresnel $r_1 = \sqrt{\lambda d_1 d_2 / d}$ |

---

## 8. Tests

```
tests/test_los_calculator.py  (incluido en tests/test_terrain_loader.py sección LOS)
```

Casos verificados:
- **Terreno plano a 0 m**: todo LOS (`los_map.all() == True`)
- **Montaña de 500 m en el punto medio de cada perfil**: todo sombra (`(los_map == 0.0).all()`)
- **`terrain_loader = None`**: devuelve array de unos y registra warning
- **`generate_los_image()`**: retorna string no vacío con prefijo `data:image/png;base64,`
