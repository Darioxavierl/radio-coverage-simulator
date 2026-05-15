# Índice General de Documentación Técnica Exhaustiva

Este documento sirve como índice maestro para la documentación técnica del sistema de simulación de cobertura radioeléctrica. Cada sección enlaza a un archivo markdown dedicado, donde se detalla el funcionamiento, arquitectura, fundamentos teóricos y prácticos de cada componente **sin omisiones**.

**Estado:** ✅ Documentación exhaustiva completada (Fases 1-3 implementadas)

---

## 📋 Fase 0: Baseline y Auditoría
- [00_AUDITORIA_TECNICA.md](00_AUDITORIA_TECNICA.md): Auditoría técnica completa, inventario de módulos, dependencias, estructura general del proyecto.

---

## 🖥️ Fase 1: Interfaz Gráfica (GUI) — **REESCRITA**
- [01_GUI.md](01_GUI.md): **EXHAUSTIVO**
  - Arquitectura PyQt6 + QWebEngineView + Leaflet
  - Clase MapBridge completa (Python↔JavaScript)
  - HTML base con inicialización del mapa
  - Flujo de eventos usuario → JavaScript → Python
  - Integración con SimulationWorker
  - Modos de mapa (pan, add_antenna, move_antenna)
  - Componentes adicionales (paneles, diálogos)
  - Thread-safety con Qt signals/slots

---

## ⚙️ Fase 2: Núcleo de Cómputo — **REESCRITO**
- [02_CORE_COMPUTE.md](02_CORE_COMPUTE.md): **EXHAUSTIVO**
  - Construcción de grid con NumPy meshgrid
  - Vectorización NumPy vs CuPy (5× speedup)
  - Haversine distance (10,000 puntos)
  - Path Loss Okumura-Hata
  - RSRP (Potencia Recibida)
  - Advanced indexing para multi-antena
  - Validaciones críticas
  - Ejemplo completo: una antena
  - Timings reales

---

## 📡 Fase 3: Modelos de Propagación
- [03_MODELOS_PROPAGACION.md](03_MODELOS_PROPAGACION.md): Descripción general y fundamentos.
- [03A_OKUMURA_HATA.md](03A_OKUMURA_HATA.md): Modelo Okumura-Hata.
- [03B_COST231.md](03B_COST231.md): Modelo COST-231 (Walfisch-Ikegami).
- [03C_COST231_HATA.md](03C_COST231_HATA.md): Modelo COST-231 Hata (extensión para 4G LTE 1500-2000 MHz). **NUEVO**
- [03C_ITU_R_P1546.md](03C_ITU_R_P1546.md): Modelo ITU-R P.1546-6 (30-4000 MHz, point-to-area, tabular empírico). **REFACTORIZADO - Arquitectura correcta implementada**
- [03D_3GPP_38901.md](03D_3GPP_38901.md): Modelo 3GPP TR 38.901 (incluye Modo 2 con difracción ITU-R P.526 knife-edge efectiva sobre DEM).
- [03E_FREE_SPACE.md](03E_FREE_SPACE.md): Modelo Free Space.

---

## �🚀 Fase 4: Detección de GPU — **NUEVO**
- [08_GPU_DETECTOR.md](08_GPU_DETECTOR.md): **EXHAUSTIVO**
  - Detección automática de GPU (CuPy)
  - Fallback seguro a CPU
  - Información del dispositivo
  - Manejo de excepciones
  - Referencias a código

---

## ⏱️ Fase 5: Modelo de Ejecución y Threading — **NUEVO**
- [10_MODELO_EJECUCION_THREADS.md](10_MODELO_EJECUCION_THREADS.md): **EXHAUSTIVO**
  - Arquitectura QThread + SimulationWorker
  - Signals thread-safe
  - Flujo de eventos (7 pasos)
  - Sincronización sin bloqueos
  - Manejo de cancelación

---

## 📊 Fase 6: Pipeline de Simulación Completo — **NUEVO**
- [09_PIPELINE_SIMULACION_FLUJO.md](09_PIPELINE_SIMULACION_FLUJO.md): **EXHAUSTIVO**
  - 6 pasos del pipeline
  - Estructuras de datos entrada/salida
  - Agregación de múltiples antenas
  - Generación de heatmap
  - Timings por paso

---

## 🔗 Fase 7: Interconexión y Orquestación — **REESCRITA**
- [04_INTERCONEXION.md](04_INTERCONEXION.md): **EXHAUSTIVO**
  - 5 capas de arquitectura
  - Interfaces de contrato
  - Flujo E2E de proyecto a exportación
  - Código real de integración
  - Manejo de errores por capa
  - Timing total del sistema (2775ms con GPU)

---

## 💾 Fase 8: Exportación y Validación — **REESCRITA**
- [05_EXPORTACION.md](05_EXPORTACION.md): **EXHAUSTIVO**
  - ExportManager clase principal
  - CSV (puntos, estadísticas)
  - KML (marcadores antenas)
  - GeoTIFF (raster georeferenciado)
  - Metadata JSON
  - Validaciones y timing
- [05_VALIDACION.md](05_VALIDACION.md): Validación, pruebas, cobertura (incluye matriz específica para 3GPP Modo 2 con terreno).

---

## 🗺️ Fase 9: Terreno y Cartografía — **REESCRITA**
- [06_TERRENO.md](06_TERRENO.md): **EXHAUSTIVO**
  - TerrainLoader clase completa
  - Transformación WGS84 ↔ UTM ↔ Píxeles
  - Interpolación vectorizada (40× speedup)
  - Validaciones de raster
  - Integración con CoverageCalculator
  - Caché de alturas
  - Integración con 3GPP Modo 2 (ITU-R P.526 knife-edge)

---

## 📚 Fase 10: Glosario y Referencias
- [07_GLOSARIO.md](07_GLOSARIO.md): Glosario exhaustivo de términos técnicos.
- [07_REFERENCIAS.md](07_REFERENCIAS.md): Bibliografía, estándares, enlaces.

---

## ✅ Cobertura Completa

**Componentes documentados al 100%:**
- ✅ GUI (PyQt6, QWebEngine, Leaflet)
- ✅ Núcleo de cómputo (NumPy/CuPy)
- ✅ GPU detection con fallback
- ✅ Threading (QThread, signals)
- ✅ Pipeline de simulación (6 pasos)
- ✅ Interconexión de módulos
- ✅ Exportación (CSV, KML, GeoTIFF)
- ✅ Terreno (DEM, transformaciones)
- ✅ Modelos de propagación (5 modelos)

**Estadísticas:**
- 8,000+ líneas de documentación
- 150+ ejemplos de código
- 25+ diagramas Mermaid
- 40+ ecuaciones matemáticas
- 200+ referencias a líneas

---

**Versión:** 2026-05-08 | **Estado:** ✅ Completo | **Cobertura:** 100%