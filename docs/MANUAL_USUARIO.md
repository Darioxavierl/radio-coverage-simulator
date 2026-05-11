# Manual de Usuario — RF Coverage Tool

**Version:** 1.0  
**Fecha:** 2026-05-10  
**Aplicacion:** RF Coverage Tool v1.0

---

## Tabla de Contenidos

1. [Introduccion](#1-introduccion)
2. [Requisitos de hardware y software](#2-requisitos-de-hardware-y-software)
3. [Instalacion y primer arranque](#3-instalacion-y-primer-arranque)
4. [Vista general de la interfaz](#4-vista-general-de-la-interfaz)
5. [Gestion de proyectos](#5-gestion-de-proyectos)
6. [Gestion de antenas](#6-gestion-de-antenas)
7. [Importar datos de terreno](#7-importar-datos-de-terreno)
8. [Configurar y ejecutar una simulacion](#8-configurar-y-ejecutar-una-simulacion)
9. [Leer e interpretar los resultados](#9-leer-e-interpretar-los-resultados)
10. [Exportar resultados](#10-exportar-resultados)
11. [Configuracion general de la aplicacion](#11-configuracion-general-de-la-aplicacion)
12. [Glosario basico](#12-glosario-basico)

---

## 1. Introduccion

**RF Coverage Tool** es una aplicacion de escritorio para simular y visualizar la cobertura de senales de radio en un area geografica. Permite colocar antenas en un mapa real, configurar sus parametros tecnicos, seleccionar un modelo de propagacion y ejecutar una simulacion que produce un mapa de calor (heatmap) indicando la intensidad de senal en cada punto del area.

**Para que sirve:**
- Visualizar la cobertura de una o varias antenas sobre un mapa cartografico.
- Comparar distintos escenarios de planificacion de red cambiando posicion, potencia o modelo.
- Exportar los resultados para analisis posterior en herramientas de SIG o de oficina.
- Comparar el rendimiento de calculos con CPU vs GPU.

**A quien va dirigido:**  
Ingenieros de telecomunicaciones, estudiantes y planificadores de red que necesiten una herramienta rapida para evaluar escenarios de cobertura radioel?trica.

---

## 2. Requisitos de hardware y software

### Hardware minimo
- Procesador: Intel/AMD de doble nucleo, 2 GHz o superior.
- Memoria RAM: 4 GB (se recomiendan 8 GB para simulaciones de alta resolucion).
- Espacio en disco: 1 GB libre para archivos temporales y exportes.

### Hardware recomendado (aceleracion GPU)
- GPU NVIDIA con soporte CUDA 7.5 o superior (por ejemplo, GTX 900 series en adelante).
- Controladores NVIDIA actualizados.
- CUDA Toolkit 11.0 o superior instalado.

> **Nota:** La GPU es opcional. Si no se detecta una GPU compatible, la aplicacion trabaja en modo CPU sin ninguna configuracion adicional.

### Software
- Sistema operativo: Windows 10/11 de 64 bits.
- Python 3.9 o superior.
- Dependencias de Python instaladas segun `requirements.txt`.
- Conexion a Internet para cargar el mapa base (OpenStreetMap).

---

## 3. Instalacion y primer arranque

### 3.1 Instalacion de dependencias

Desde la carpeta raiz del proyecto, ejecutar en terminal:

```
pip install -r requirements.txt
```

### 3.2 Arranque de la aplicacion

Ejecutar desde la carpeta raiz:

```
python run.py
```

Al iniciar, aparece una pantalla de bienvenida (splash screen) que muestra el avance de carga:

1. Inicializando aplicacion.
2. Cargando configuracion.
3. Detectando hardware (GPU/CPU).
4. Cargando modelos de propagacion.
5. Preparando interfaz.

Despues de unos segundos, la pantalla de bienvenida se cierra y aparece la ventana principal de la aplicacion.

### 3.3 Indicador GPU/CPU

En la barra de estado inferior derecha se indica si la aplicacion detecto una GPU disponible:

- **Aceleracion: GPU** — la aplicacion usara la tarjeta grafica para los calculos.
- **Aceleracion: CPU** — la aplicacion usara el procesador central.

---

## 4. Vista general de la interfaz

La ventana principal esta organizada en cuatro zonas:

```
┌─────────────────────────────────────────────────────┐
│  Barra de menu   (Archivo / Editar / Antena / ...)  │
├──────────┬──────────────────────────────────────────┤
│ Toolbar  │                                          │
│ lateral  │          MAPA CENTRAL                    │
│ (modos)  │     (Leaflet / OpenStreetMap)            │
│          │                                          │
├──────────┤                                          │
│  Panel   │                                          │
│ Proyecto │                                          │
│ (dock)   │                                          │
├──────────┴──────────────────────────────────────────┤
│ Estado: Listo | Aceleracion: GPU | Lat: 0 Lon: 0 | [|||||] │
└─────────────────────────────────────────────────────┘
```

### 4.1 Mapa central
El mapa usa OpenStreetMap como capa base. Se puede navegar con el raton:
- **Arrastrar**: desplazar el mapa.
- **Rueda del raton**: hacer zoom acercando o alejando.

Al ejecutar una simulacion, el mapa muestra el heatmap de cobertura sobre la capa cartografica.

### 4.2 Toolbar lateral (modos de interaccion)
Situada a la izquierda, contiene botones para cambiar el modo activo del mapa:

| Boton | Modo | Accion |
|-------|------|--------|
| Navegar | PAN | Mover y hacer zoom en el mapa |
| Agregar Antena | ADD | Hacer clic en el mapa para colocar una antena |
| Mover | MOVE | Arrastrar una antena a otra posicion |
| Seleccionar | SELECT | Seleccionar una antena para editar sus propiedades |
| Simular | — | Lanzar la simulacion directamente |

### 4.3 Toolbar principal (superior)
Contiene acciones de proyecto (Nuevo, Abrir, Guardar), acceso a Configuracion y separadores.

### 4.4 Panel de proyecto (dock lateral izquierdo)
Muestra un arbol con los elementos del proyecto activo:
- Lista de antenas y sus propiedades resumidas.
- Acciones de contexto (seleccionar, eliminar).

### 4.5 Barra de estado (inferior)
- Izquierda: mensaje de estado actual ("Listo", "Calculando...", etc.).
- Centro-derecha: modo de aceleracion activo (GPU o CPU).
- Derecha: coordenadas del cursor sobre el mapa.
- Barra de progreso: visible durante una simulacion en curso.

---

## 5. Gestion de proyectos

Un proyecto agrupa todas las antenas, la configuracion de simulacion y los resultados en un archivo con extension `.rfproj`.

### 5.1 Crear nuevo proyecto
- Menu **Archivo > Nuevo Proyecto** o **Ctrl+N**.
- Se crea un proyecto vacio con el nombre "Nuevo Proyecto".

### 5.2 Abrir proyecto existente
- Menu **Archivo > Abrir Proyecto...** o **Ctrl+O**.
- Seleccionar un archivo `.rfproj` en el explorador de archivos.

### 5.3 Guardar proyecto
- Menu **Archivo > Guardar Proyecto** o **Ctrl+S**.
- Si el proyecto es nuevo, se pedira una ubicacion y nombre de archivo.
- Los proyectos se guardan en `data/projects/` por defecto.

### 5.4 Sobre los archivos .rfproj
Los archivos `.rfproj` son archivos de texto en formato JSON. Contienen la configuracion de antenas, sitios y parametros del proyecto. Se pueden abrir con cualquier editor de texto si se desea inspeccionar su contenido.

> **Consejo:** La aplicacion crea copias de seguridad automaticas antes de eliminar proyectos. Los backups se guardan en `data/projects/backups/`.

---

## 6. Gestion de antenas

### 6.1 Agregar una antena
1. Hacer clic en el boton **Agregar Antena** en la toolbar lateral (o menu **Antena > Agregar Antena**, Ctrl+A).
2. El cursor cambia al modo de colocacion.
3. Hacer clic en el mapa en la posicion deseada.
4. Aparece un marcador de antena en el mapa y la antena se agrega al panel de proyecto.

Cada antena nueva recibe valores por defecto que se pueden ajustar despues.

### 6.2 Editar propiedades de una antena
1. Seleccionar la antena en el panel de proyecto o hacer clic en su marcador en el mapa.
2. Menu **Antena > Propiedades...** (Ctrl+P) o doble clic sobre el marcador.
3. Se abre el dialogo de propiedades donde se pueden editar:

| Propiedad | Descripcion | Unidades |
|-----------|-------------|---------|
| Nombre | Nombre descriptivo de la antena | — |
| Latitud / Longitud | Posicion geografica | grados decimales |
| Frecuencia | Frecuencia de la portadora | MHz |
| Potencia de transmision (Tx) | Potencia total en la salida | dBm |
| Altura sobre el suelo (AGL) | Altura fisica de la antena | metros |
| Ganancia | Ganancia de la antena | dBi |
| Azimuth | Orientacion horizontal principal | grados (0=Norte) |
| Beamwidth horizontal | Apertura del haz horizontal | grados |
| Tipo | Omnidireccional o sectorial | — |

4. Hacer clic en **Aceptar** para guardar los cambios.

### 6.3 Mover una antena
- Activar el modo **Mover** en la toolbar lateral.
- Arrastrar el marcador de la antena a la nueva posicion en el mapa.

### 6.4 Eliminar una antena
- Seleccionar la antena y presionar **Supr** (Delete), o menu **Antena > Eliminar Antena**.
- La antena se elimina del mapa y del panel de proyecto.

### 6.5 Multiples antenas
Se pueden agregar tantas antenas como se necesite. Al simular con mas de una antena, la aplicacion calcula la cobertura individual de cada una y ademas genera un heatmap agregado mostrando la antena con mejor senal en cada punto del area.

---

## 7. Importar datos de terreno

La aplicacion puede usar un Modelo Digital de Elevacion (DEM) en formato GeoTIFF para incorporar el relieve del terreno en los calculos de cobertura.

### 7.1 Importar archivo de terreno
- Menu **Archivo > Importar Terreno...**
- Seleccionar un archivo `.tif` (GeoTIFF) de elevacion.
- La aplicacion cargara el archivo y mostrara un mensaje de confirmacion con el rango de elevacion detectado.

### 7.2 Terreno por defecto
Si existe el archivo `data/terrain/cuenca_terrain.tif`, la aplicacion lo carga automaticamente al iniciar.

### 7.3 Sin terreno (terreno plano)
Si no se carga ningun archivo de terreno, la aplicacion asume un terreno completamente plano (elevacion = 0 m en todos los puntos). Los resultados siguen siendo validos pero no reflejaran el efecto del relieve en la propagacion.

> **Consejo:** Para mayor precision en zonas montanosas, se recomienda usar un DEM con resolucion de al menos 30 metros (por ejemplo, datos SRTM de la NASA).

---

## 8. Configurar y ejecutar una simulacion

### 8.1 Abrir el dialogo de simulacion
- Menu **Simulacion > Ejecutar Simulacion** o tecla **F5**, o el boton **Simular** en la toolbar.

### 8.2 Parametros del dialogo de simulacion

#### Modelo de propagacion
Seleccionar el modelo segun el escenario:

| Modelo | Escenario tipico | Rango de frecuencia | Rango de distancia |
|--------|-----------------|--------------------|--------------------|
| Free Space | Referencia LOS sin obstrucciones | Cualquiera | Cualquiera |
| Okumura-Hata | Redes celulares urbanas/suburbanas/rurales | 150 – 2000 MHz | 1 – 20 km |
| COST-231 | Entornos urbanos densos | 800 – 2000 MHz | 20 m – 5 km |
| ITU-R P.1546 | Largo alcance, radiodifusion | 30 – 4000 MHz | 1 – 1000 km |
| 3GPP TR 38.901 | Redes 5G NR (UMa, UMi, Rural) | 500 MHz – 100 GHz | 10 m – 10 km |

> **Consejo:** Si no esta seguro, use Okumura-Hata para escenarios urbanos generales con frecuencias entre 150 y 2000 MHz.

#### Area de simulacion
- **Radio (km):** radio del area circular a simular alrededor del centro del despliegue de antenas.
- **Resolucion:** numero de puntos por lado de la grilla. Por ejemplo, 500 = 500x500 = 250.000 puntos. Mayor resolucion produce resultados mas detallados pero tarda mas.

#### Aceleracion de computo
- **Usar GPU:** activa el calculo en la tarjeta grafica si hay una disponible. Mas rapido para resoluciones altas o muchas antenas.
- **Usar CPU:** calculo en procesador central. Compatible con cualquier equipo.

#### Parametros especificos del modelo
Dependiendo del modelo seleccionado, aparecen campos adicionales como:
- Tipo de entorno (Urbano, Suburbano, Rural).
- Altura de edificios y ancho de calle (COST-231).
- Escenario y alturas de estacion base y terminal (3GPP).

### 8.3 Ejecutar la simulacion
1. Verificar que hay al menos una antena en el proyecto.
2. Configurar los parametros deseados.
3. Hacer clic en **Ejecutar** (o **Aceptar**).
4. La barra de progreso muestra el avance. Durante la simulacion la interfaz permanece activa.
5. Al terminar, el heatmap aparece sobre el mapa automaticamente.

### 8.4 Detener una simulacion en curso
- Menu **Simulacion > Detener Simulacion** (Ctrl+F5).

---

## 9. Leer e interpretar los resultados

### 9.1 Heatmap de cobertura
Al finalizar la simulacion, el mapa muestra una capa de colores sobre el area simulada. La escala de colores representa la potencia de senal recibida (RSRP) en cada punto:

| Color | RSRP aproximado | Calidad de senal |
|-------|----------------|-----------------|
| Rojo / naranja intenso | Mayor a -70 dBm | Excelente |
| Amarillo | -70 a -90 dBm | Buena |
| Verde | -90 a -100 dBm | Aceptable |
| Azul / violeta | -100 a -120 dBm | Debil |
| Sin color / transparente | Menor a -120 dBm | Sin cobertura |

> **Nota:** Los valores exactos de referencia dependen del tipo de red y terminal. Los valores indicados son orientativos para redes LTE.

### 9.2 Cobertura con multiples antenas
Cuando se simulan dos o mas antenas, la aplicacion genera:
- Un heatmap individual por antena (la cobertura que aportaria esa antena sola).
- Un heatmap agregado que muestra en cada punto la senal de la antena mas fuerte.

### 9.3 Menu Analisis
- Menu **Simulacion > Analisis de Cobertura...**: abre un panel con estadisticas de cobertura del area simulada.

---

## 10. Exportar resultados

Despues de ejecutar una simulacion, los resultados se pueden exportar en distintos formatos. Ir a menu **Archivo > Exportar**.

### 10.1 CSV + JSON
- **CSV:** tabla con todos los puntos de la grilla y sus valores (posicion, RSRP, perdida de trayecto, ganancia). Util para analisis en Excel o Python.
- **JSON (metadata):** archivo con parametros de la simulacion, modelo usado, tiempos de ejecucion y configuracion. Util para reproducibilidad y auditoria.

### 10.2 KML
- Archivo compatible con Google Earth y software SIG.
- Incluye el heatmap como capa de imagen georreferenciada.
- Se genera tambien una imagen PNG del heatmap separada.

### 10.3 GeoTIFF
- Raster georreferenciado con tres bandas: RSRP, perdida de trayecto y ganancia de antena.
- Compatible con QGIS, ArcGIS y otras herramientas SIG.

### 10.4 Donde se guardan los archivos
Los exportes se guardan por defecto en `data/exports/` con un nombre que incluye la fecha y hora de la simulacion. La ubicacion se puede cambiar en **Configuracion**.

---

## 11. Configuracion general de la aplicacion

Menu **Editar > Configuracion...** o el boton **Configuracion** en la toolbar principal.

### Opciones disponibles

| Opcion | Descripcion |
|--------|-------------|
| Usar GPU | Activar o desactivar aceleracion GPU. Cambia de modo en tiempo real. |
| Tema | Tema visual de la aplicacion (oscuro por defecto). |
| Zoom inicial del mapa | Nivel de zoom al abrir la aplicacion. |
| Centro del mapa | Coordenadas de la vista inicial del mapa. |
| Directorio de terreno | Carpeta donde buscar archivos DEM. |
| Directorio de exportes | Carpeta donde guardar los resultados exportados. |
| Nivel de log | Verbosidad del registro de eventos (INFO por defecto). |

Los cambios se aplican inmediatamente. La configuracion se guarda en `config/settings.json`.

---

## 12. Glosario basico

| Termino | Definicion |
|---------|------------|
| **Antena** | Dispositivo que transmite o recibe senales de radio. En la aplicacion representa una estacion base transmisora. |
| **AGL** | Above Ground Level — altura medida desde el nivel del suelo local. |
| **Cobertura** | Region del mapa donde la senal supera un nivel minimo aceptable. |
| **DEM** | Digital Elevation Model — modelo digital del terreno con datos de altitud. |
| **dBm** | Decibel-miliWatt — unidad de potencia de senal. Valores mas altos = senal mas fuerte. |
| **dBi** | Decibel isotrópico — unidad de ganancia de antena respecto a una antena isotropica de referencia. |
| **GeoTIFF** | Formato de imagen raster con informacion geografica integrada. |
| **GPU** | Unidad de procesamiento grafico usada para acelerar calculos numericos. |
| **Heatmap** | Mapa de calor: visualizacion donde el color representa la intensidad de un valor en cada punto. |
| **KML** | Keyhole Markup Language — formato de archivo geoespacial para Google Earth y SIG. |
| **Modelo de propagacion** | Metodo matematico para estimar la perdida de senal entre transmisor y receptor. |
| **Path Loss** | Perdida de trayecto — atenuacion total de la senal entre la antena y un punto receptor. |
| **RF** | Radio Frequency — frecuencias del espectro electromagnetico usadas en comunicaciones. |
| **RSRP** | Reference Signal Received Power — potencia de senal recibida, principal indicador de cobertura. |
| **Resolucion** | Numero de puntos de calculo por lado del area simulada. Mayor resolucion = mas detalle. |
| **Simulacion** | Proceso de calculo que estima la cobertura de senal en el area configurada. |
| **SIG** | Sistema de Informacion Geografica — herramienta para analisis de datos con componente espacial. |
| **Terreno plano** | Modo de simulacion donde se ignora la elevacion del terreno. |

---

*Manual generado el 2026-05-10. Para soporte tecnico referirse al Manual Tecnico (MANUAL_TECNICO.md).*
