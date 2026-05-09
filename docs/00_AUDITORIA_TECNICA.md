# Auditoría Técnica y Baseline del Proyecto

**Fecha:** 2026-05-08

## 1. Resumen General
Este documento presenta una auditoría técnica del sistema de simulación de cobertura radioeléctrica, detallando la estructura de carpetas, módulos principales, dependencias, y el estado actual del código.

## 2. Estructura de Carpetas

```
AUDIT_REPORT.md
FASE_6_RESUMEN_EJECUTIVO.md
FUNCIONALIDADES_IMPLEMENTADAS.md
LICENSE.txt
README.md
requirements.txt
run.py
config/
    models_config.json
    settings.json
    antenna_patterns/
    locales/
        en.json
        es.json
data/
    exports/
    projects/
    terrain/
docs/
logs/
src/
    main.py
    core/
        antenna_manager.py
        compute_engine.py
        coverage_calculator.py
        project_manager.py
        site_manager.py
        terrain_loader.py
        models/
            base_model.py
            gpp_3gpp/
            traditional/
    models/
        antenna.py
        project.py
        site.py
    ui/
        main_window.py
        splash_screen.py
        dialogs/
        panels/
            project_panel.py
        widgets/
    utils/
        config_manager.py
        export_manager.py
        gpu_detector.py
        heatmap_generator.py
        logger.py
    workers/
        simulation_worker.py
tests/
```

## 3. Módulos Principales
- **src/main.py**: Punto de entrada principal.
- **src/core/**: Núcleo de lógica y cómputo.
- **src/models/**: Entidades de dominio (antena, proyecto, sitio).
- **src/ui/**: Interfaz gráfica (PyQt6).
- **src/utils/**: Utilidades y servicios auxiliares.
- **src/workers/**: Procesos en background (simulación).
- **tests/**: Pruebas unitarias e integración.

## 4. Dependencias Clave
- Python >=3.9 (probado hasta 3.12)
- PyQt6
- NumPy, CuPy
- rasterio, pyproj
- matplotlib

## 5. Estado de la Documentación
- `docs/`: Vacío (nueva documentación en construcción).
- `docs.bk/`: Documentación previa (legacy, para referencia).

## 6. Estado de Pruebas
- Pruebas unitarias e integración extensas en `tests/`.
- Cobertura por modelo y por integración.

## 7. Observaciones
- Arquitectura modular, separación clara entre GUI, núcleo de cómputo y modelos.
- Uso de workers para tareas pesadas.
- Soporte para múltiples modelos de propagación.
- Sistema de exportación y validación robusto.

## 8. Próximos Pasos
- Generar documentación técnica detallada por módulo (ver [INDEX.md](INDEX.md)).
- Incluir diagramas, ecuaciones y ejemplos de uso.

---

**Este archivo se actualiza en cada auditoría o cambio estructural relevante.**
