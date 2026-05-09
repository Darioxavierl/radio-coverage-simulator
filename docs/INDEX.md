# Índice General de Documentación

Este documento sirve como índice maestro para la documentación técnica del sistema de simulación de cobertura radioeléctrica. Cada sección enlaza a un archivo markdown dedicado, donde se detalla el funcionamiento, arquitectura, fundamentos teóricos y prácticos de cada componente.

## Fase 0: Baseline y Auditoría
- [00_AUDITORIA_TECNICA.md](00_AUDITORIA_TECNICA.md): Auditoría técnica, inventario de módulos, dependencias, estructura general.

## Fase 1: Interfaz Gráfica (GUI)
- [01_GUI.md](01_GUI.md): Arquitectura, flujos, paneles, widgets, interacción usuario.

## Fase 2: Núcleo de Cómputo
- [02_CORE_COMPUTE.md](02_CORE_COMPUTE.md): Motor de cómputo, abstracción NumPy/CuPy, workers, pipeline de simulación.

## Fase 3: Modelos de Propagación
- [03_MODELOS_PROPAGACION.md](03_MODELOS_PROPAGACION.md): Descripción general y fundamentos.
- [03A_OKUMURA_HATA.md](03A_OKUMURA_HATA.md): Modelo Okumura-Hata.
- [03B_COST231.md](03B_COST231.md): Modelo COST-231.
- [03C_ITU_R_P1546.md](03C_ITU_R_P1546.md): Modelo ITU-R P.1546.
- [03D_3GPP_38901.md](03D_3GPP_38901.md): Modelo 3GPP TR 38.901.
- [03E_FREE_SPACE.md](03E_FREE_SPACE.md): Modelo Free Space.

## Fase 4: Interconexión y Orquestación
- [04_INTERCONEXION.md](04_INTERCONEXION.md): Cómo se conectan los módulos, flujos de datos, dependencias.

## Fase 5: Exportación y Validación
- [05_EXPORTACION.md](05_EXPORTACION.md): Sistema de exportación, formatos soportados.
- [05_VALIDACION.md](05_VALIDACION.md): Validación, pruebas, cobertura, resultados.

## Fase 6: Terreno y Cartografía
- [06_TERRENO.md](06_TERRENO.md): Carga y manejo de terreno, raster, proyecciones.

## Fase 7: Glosario y Referencias
- [07_GLOSARIO.md](07_GLOSARIO.md): Glosario de términos técnicos.
- [07_REFERENCIAS.md](07_REFERENCIAS.md): Bibliografía y enlaces relevantes.

---

**Nota:** Cada archivo incluye diagramas, ecuaciones, ejemplos de código y referencias cruzadas según corresponda.