# Interfaz Gráfica: arquitectura real de la GUI

**Versión:** 2026-05-27

## 1. Propósito

La interfaz gráfica es la capa que conecta la configuración del proyecto con el pipeline de simulación y con la visualización cartográfica de resultados. La aplicación está construida con PyQt6 como framework de escritorio, mientras que el mapa se renderiza dentro de un `QWebEngineView` usando Leaflet y un puente `QWebChannel` entre Python y JavaScript.

La GUI no es solo una capa visual. En la implementación actual coordina cuatro tareas concretas:

1. Gestión del proyecto y su estado en memoria.
2. Edición de antenas y sitios desde paneles y diálogos.
3. Lanzamiento de simulaciones sin bloquear la ventana principal.
4. Presentación de resultados RF y LOS sobre el mapa interactivo.

---

## 2. Componentes principales

La interfaz se organiza alrededor de `MainWindow`, que compone el resto de widgets y conecta sus señales con los managers del dominio y el worker de simulación.

```
MainWindow
├─ MapWidget
│  ├─ QWebEngineView
│  ├─ MapBridge
│  └─ HTML/JavaScript Leaflet embebido
├─ ProjectPanel
├─ SimulationDialog
├─ AntennaPropertiesDialog
└─ SitePropertiesDialog
```

### 2.1 MainWindow

`MainWindow` es el orquestador de la GUI. Inicializa `ComputeEngine`, `AntennaManager`, `SiteManager`, `ProjectManager` y `CoverageCalculator`, crea la disposición general de la ventana, administra toolbars, menús, status bar y acopla el panel de proyecto al costado izquierdo.

También mantiene el estado operativo de la sesión actual:

- proyecto cargado o recién creado,
- terreno activo,
- modo de cómputo CPU/GPU,
- simulación en curso,
- últimos resultados disponibles para exportación.

Desde el punto de vista de diseño, `MainWindow` no implementa los modelos RF ni la lógica geoespacial. Su papel es coordinar eventos y mover datos entre UI, managers, worker y mapa.

### 2.2 MapWidget

`MapWidget` encapsula el mapa interactivo. Internamente usa `QWebEngineView` para renderizar una página HTML generada desde Python y `QWebChannel` para exponer un objeto `MapBridge` que actúa como interfaz entre ambos lados.

Este widget ofrece métodos públicos de más alto nivel, como:

- `set_mode()`
- `add_antenna()`
- `remove_antenna()`
- `update_antenna()`
- `show_coverage()`
- `clear_all_antennas()`
- `clear_coverage_layers()`
- `center_on_location()`
- `get_center()`

Es decir, la ventana principal no manipula directamente JavaScript ni objetos Leaflet. Lo hace mediante un widget Python que encapsula ese detalle.

### 2.3 ProjectPanel

`ProjectPanel` muestra la estructura del proyecto en forma de árbol. La versión actual ya no trabaja solo con una lista plana de antenas. Organiza el contenido en dos grupos:

- sitios, con sus antenas asociadas como nodos hijos,
- antenas independientes que no pertenecen a ningún sitio.

Además ofrece acciones contextuales como selección, apertura de propiedades, duplicación de antenas y eliminación de sitios o antenas. Esto vuelve más coherente el modelo visual del proyecto con el modelo de datos real que ya maneja entidades `Site` y relaciones `Site ↔ Antenna`.

### 2.4 Diálogos de edición y simulación

La edición detallada se distribuye en diálogos especializados:

- `AntennaPropertiesDialog` organiza parámetros generales, RF y patrón de radiación por pestañas.
- `SitePropertiesDialog` permite editar identificación, ubicación, características físicas, metadatos y asociación de antenas a un sitio.
- `SimulationDialog` concentra la configuración de la corrida: modelo de propagación, parámetros específicos por modelo, radio, resolución, override de frecuencia y estado del terreno cargado.

---

## 3. Tecnología del mapa y comunicación Python–JavaScript

La visualización cartográfica se implementa con Leaflet dentro de una página HTML embebida. El HTML se genera desde `_load_map_html()` en `MapWidget`, y luego se carga con `setHtml()` en el `QWebEngineView`.

La comunicación entre Python y JavaScript se realiza con `QWebChannel`, que registra un objeto `MapBridge`. Ese puente expone señales de Python hacia JavaScript y slots invocables desde el lado web hacia Python.

### 3.1 Señales Python → JavaScript

El puente emite comandos para:

- agregar, quitar y actualizar marcadores de antena,
- agregar capas RSRP visibles u ocultas,
- agregar capas LOS,
- registrar nombres legibles para overlays,
- almacenar rangos RSRP para la leyenda dinámica,
- cambiar modo del mapa,
- centrar el mapa,
- limpiar marcadores y capas,
- solicitar el centro actual de la vista.

Esto muestra que el puente no está limitado a “dibujar antenas”. También administra overlays, leyendas y sincronización de estado entre la interfaz Qt y el mapa Leaflet.

### 3.2 Eventos JavaScript → Python

Desde el mapa regresan al lado Python tres clases de eventos principales:

- clic sobre el mapa,
- movimiento de un marcador de antena,
- selección de un marcador,
- actualización del centro y zoom de la vista.

En el código actual estos eventos se reciben mediante slots como `on_map_click`, `on_antenna_moved`, `on_antenna_selected` y `on_map_center`, y luego se reemiten como señales Qt normales dentro de `MapWidget`.

Esta capa intermedia simplifica la arquitectura porque `MainWindow` se conecta al widget Python, no directamente a callbacks JavaScript.

---

## 4. Modo de interacción en el mapa

El mapa no funciona solo como visor pasivo. Implementa varios modos de interacción definidos en `MapMode`:

- `PAN`
- `ADD_ANTENNA`
- `MOVE_ANTENNA`
- `SELECT`
- `MEASURE`

En la lógica JavaScript embebida, los modos que tienen comportamiento explícito hoy son sobre todo `pan`, `add_antenna` y `move_antenna`. Cuando el usuario activa el modo de agregar antena desde toolbar o menú, `MainWindow` llama a `map_widget.set_mode(MapMode.ADD_ANTENNA)` y actualiza la barra de estado. El siguiente clic sobre el mapa genera la señal `antenna_placed(lat, lon)`.

Luego `MainWindow.on_antenna_placed()` crea la antena mediante `AntennaManager.create_antenna_at_location()`, la recupera desde el manager y la dibuja en el mapa con `map_widget.add_antenna(...)`. Después el widget vuelve automáticamente a modo `PAN`.

Eso significa que la creación interactiva de antenas se resuelve con un flujo de dos etapas:

1. La UI activa un modo de captura espacial.
2. El clic geográfico se transforma en una nueva entidad del dominio.

---

## 5. Gestión visual del proyecto: antenas, sitios y persistencia

Una de las diferencias más importantes respecto a versiones anteriores es la integración explícita entre antenas, sitios y persistencia del proyecto.

### 5.1 Sitios y antenas asociadas

`ProjectPanel.refresh()` construye el árbol con un nodo raíz de sitios y otro para antenas independientes. Cada sitio contiene como hijos las antenas cuyos IDs aparecen en `site.antenna_ids`. Esto no es solo una decisión visual: refleja el modelo actual de negocio, donde una antena puede estar asociada a un sitio o quedar libre.

Cuando el usuario crea o edita un sitio mediante `SitePropertiesDialog`, la interfaz permite marcar qué antenas pertenecen a ese sitio. Al confirmar el diálogo, el panel y `SiteManager` actualizan la relación bidireccional entre `Site.antenna_ids` y `antenna.site_id`.

### 5.2 Persistencia del proyecto

`ProjectManager` guarda y carga proyectos `.rfproj` en formato JSON. En la versión actual no se persisten solo antenas y nombre del proyecto. También se almacenan:

- sitios,
- centro y zoom del mapa,
- archivo de terreno asociado,
- configuración de simulación.

Antes de guardar, `MainWindow._update_project_before_save()` actualiza la estructura `Project` con el contenido real de `AntennaManager`, `SiteManager` y la vista actual del mapa. De esta manera, al reabrir el proyecto no solo se recupera el inventario de entidades, sino también el contexto espacial de trabajo.

---

## 6. Configuración de la simulación desde la GUI

La simulación se inicia desde `MainWindow.run_simulation()`. Antes de lanzar el worker, la aplicación abre `SimulationDialog`, que funciona como interfaz de configuración técnica de la corrida.

Este diálogo ya incorpora una cantidad considerable de lógica integrada al sistema:

- selección del modelo de propagación,
- grupos de parámetros específicos para Okumura-Hata, COST-231 Walfisch-Ikegami, COST-231 Hata, ITU-R P.1546 y 3GPP TR 38.901,
- radio y resolución del área de simulación,
- override opcional de frecuencia,
- verificación de si existe DEM cargado y presentación de estadísticas básicas del terreno.

La relevancia de esto en la tesis es que la GUI no se limita a pedir “un modelo” y “un radio”. La interfaz ya incorpora conocimiento del dominio RF, porque adapta la configuración visible al modelo elegido y transmite esa estructura al worker mediante `dialog.get_config()`.

---

## 7. Ejecución asíncrona y respuesta de la interfaz

Para no bloquear la ventana principal, `MainWindow` ejecuta la simulación en un `QThread` separado y mueve ahí un `SimulationWorker`. El patrón es el típico de Qt: el hilo principal conserva la UI y el worker emite señales de progreso, estado, finalización o error.

El flujo real es:

1. `MainWindow` crea `QThread` y `SimulationWorker`.
2. Mueve el worker al hilo secundario.
3. Conecta `progress`, `status_message`, `finished` y `error`.
4. Inicia el hilo.
5. La UI actualiza barra de progreso y mensajes sin bloquearse.

Este diseño tiene una consecuencia importante en términos de experiencia de usuario: la aplicación puede seguir respondiendo mientras el núcleo RF calcula distancias, pérdidas, capas RSRP y mapas LOS.

---

## 8. Presentación de resultados en el mapa

Cuando `SimulationWorker` termina, `MainWindow.on_simulation_finished()` recibe un diccionario `results` y lo conserva para exportaciones posteriores. Luego actualiza el mapa mediante `MapWidget.show_coverage()`.

Aquí la integración es más rica de lo que parece a primera vista.

### 8.1 Capas individuales y capa agregada

La interfaz registra primero las coberturas individuales de cada antena como capas disponibles pero ocultas al inicio. Después muestra por defecto la capa agregada, si existe. Si no hay agregada, utiliza la primera individual como fallback visible.

Este comportamiento tiene sentido operativo: en despliegues multiantena, el usuario ve de entrada la cobertura global, pero puede activar o desactivar capas individuales desde el control de overlays de Leaflet.

### 8.2 Leyenda dinámica y overlays LOS

Cada capa RSRP guarda su rango `vmin/vmax`, que luego se usa para actualizar la leyenda dinámica cuando el usuario activa una capa concreta. Además, si la simulación incluye `los_image_url`, `MapWidget.show_coverage()` registra una capa LOS separada para ese mismo identificador.

En el lado JavaScript esto se materializa en tres estructuras principales:

- `coverageLayers` para overlays RSRP,
- `losLayers` para overlays de visibilidad,
- `overlayNames` y `rsrpRanges` para presentar nombres legibles y leyendas consistentes.

El resultado es un panel de capas donde RSRP y LOS no están mezclados en una sola imagen, sino tratados como overlays distintos y activables por el usuario.

### 8.3 Renderizado realmente usado

El heatmap no se genera en Leaflet ni mediante teselas dinámicas. `SimulationWorker` produce imágenes PNG codificadas en base64 usando `HeatmapGenerator`, y `MapWidget` las inserta en el mapa como `L.imageOverlay(...)` georreferenciado con los límites de la grilla. La misma idea se aplica a la capa LOS.

Eso explica por qué la GUI puede combinar un stack de escritorio con una visualización geográfica moderna sin introducir un servidor web intermedio.

---

## 9. Flujo de usuario principal

Desde el punto de vista funcional, el flujo más representativo de la aplicación puede resumirse así:

1. El usuario crea o abre un proyecto.
2. La GUI restaura el centro del mapa, las antenas, los sitios y el archivo de terreno si existe.
3. El usuario agrega antenas desde el mapa, edita sus propiedades o las organiza dentro de sitios desde el panel.
4. Si hace falta, importa un DEM.
5. Abre `SimulationDialog`, selecciona modelo y parámetros.
6. Ejecuta la simulación sin bloquear la ventana.
7. Inspecciona la cobertura agregada y las capas individuales RSRP/LOS en el mapa.
8. Exporta resultados a CSV, GeoTIFF o KML.

Este flujo es importante porque muestra que la interfaz no está separada del proceso de ingeniería. Toda la aplicación fue pensada como una herramienta operativa donde edición, simulación, visualización y exportación forman parte de una misma sesión de trabajo.

---

## 10. Consideraciones técnicas y limitaciones actuales

La documentación de GUI también debe dejar claras algunas restricciones reales del código actual.

La primera es que el mapa trabaja con HTML embebido generado desde Python. Esto simplifica la distribución de la aplicación, pero hace que una parte importante del comportamiento Leaflet esté escrita como cadena HTML/JavaScript dentro de `MapWidget`, lo que vuelve más difícil su mantenimiento que si estuviera separado en archivos estáticos.

La segunda es que la interfaz visualiza coberturas como imágenes georreferenciadas, no como capas vectoriales ni como raster dinámico progresivo. Esto es suficiente para el caso de uso del sistema, pero condiciona la forma en que se manipulan overlays y leyendas.

La tercera es que no todas las acciones visibles en la UI representan todavía un flujo completo equivalente. Por ejemplo, el camino principal de creación de antenas plenamente integrado es el modo de colocación sobre el mapa, mientras que otras rutas secundarias de creación desde panel todavía no concentran la misma lógica operativa.

La cuarta es que la interfaz depende de un conjunto coordinado de señales entre `MainWindow`, `MapWidget`, `ProjectPanel`, managers y worker. Esa arquitectura mejora modularidad, pero también exige que la documentación permanezca alineada con el código, porque pequeños cambios en nombres de señales o en el flujo de overlays afectan de inmediato el comportamiento observable.

---

## 11. Resumen

La GUI del sistema no debe entenderse solo como una capa estética. En la implementación actual funciona como un subsistema de integración entre el dominio RF, la cartografía interactiva y el ciclo de vida completo del proyecto. `MainWindow` coordina managers y simulación; `ProjectPanel` representa la estructura lógica de sitios y antenas; `SimulationDialog` traduce parámetros del dominio a configuración ejecutable; y `MapWidget` convierte los resultados numéricos en overlays cartográficos interactivos sobre Leaflet.

Por eso, al redactar la tesis, la interfaz conviene presentarla como una decisión de arquitectura que vuelve operable el simulador: permite editar entidades espaciales, lanzar simulaciones sin bloqueo, visualizar resultados multi-capa y conservar el estado del proyecto en un formato persistente. Esa es, en la práctica, la capa que transforma un conjunto de modelos y algoritmos en una herramienta usable.
