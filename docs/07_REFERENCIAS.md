# Referencias Tecnicas

**Versión:** 2026-05-08

## 1. Referencias Normativas y de Modelo
- ITU-R P.1546: metodologia de prediccion punto-area para servicios terrestres.
- 3GPP TR 38.901: estudio de canal para escenarios 5G y LTE avanzados.
- Literatura clasica de Okumura-Hata para prediccion empirica urbana.
- Extensiones COST-231 para escenarios urbanos de mayor frecuencia.

## 2. Referencias de Implementacion
- Documentacion interna del proyecto en `docs/`.
- Pruebas automatizadas en `tests/`.
- Configuracion y parametros en `config/`.

## 3. Referencias de Herramientas
- NumPy para computo numerico en CPU.
- CuPy para aceleracion GPU cuando esta disponible.
- PyQt6 para interfaz grafica.
- rasterio y pyproj para lectura y transformacion geoespacial.
- matplotlib para visualizacion y heatmaps.

## 4. Referencias de Uso Interno
- [00_AUDITORIA_TECNICA.md](00_AUDITORIA_TECNICA.md): panorama general del sistema.
- [01_GUI.md](01_GUI.md): arquitectura de la interfaz.
- [02_CORE_COMPUTE.md](02_CORE_COMPUTE.md): motor de calculo.
- [03_MODELOS_PROPAGACION.md](03_MODELOS_PROPAGACION.md): catalogo de modelos.
- [04_INTERCONEXION.md](04_INTERCONEXION.md): integracion entre modulos.
- [05_EXPORTACION.md](05_EXPORTACION.md): salidas y formatos.
- [05_VALIDACION.md](05_VALIDACION.md): pruebas y verificaciones.
- [06_TERRENO.md](06_TERRENO.md): soporte geoespacial.

## 5. Observacion
Estas referencias sirven como base documental interna. Si el proyecto requiere una memoria academica o un anexo formal, se puede ampliar este archivo con bibliografia externa completa y formato de citacion estandar.
