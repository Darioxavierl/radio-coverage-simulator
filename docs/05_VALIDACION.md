# Validacion y Verificacion

**Versión:** 2026-05-08

## 1. Objetivo
Este documento resume como el proyecto valida la coherencia de sus calculos, modelos y salidas. La validacion abarca pruebas unitarias, integracion y verificacion de consistencia numerica.

## 2. Estrategia de Pruebas
- Pruebas unitarias por modelo de propagacion.
- Pruebas de integracion para el pipeline completo.
- Pruebas de consistencia de unidades.
- Pruebas de GPU y backend numerico.

## 3. Cobertura por Area

### 3.1 Modelos de Propagacion
Cada modelo cuenta con pruebas especificas para verificar formulas, rangos y valores esperados.

### 3.2 Motor de Calculo
Se verifica que el motor seleccione correctamente el backend y devuelva estructuras numericas compatibles con la GUI y el exportador.

### 3.3 Sistema de Terreno
Se revisa la carga correcta de raster, transformaciones espaciales y manejo de errores.

### 3.4 GUI y Flujo de Simulacion
Se validan la creacion de dialogos, el disparo de workers y la recepcion de resultados.

## 4. Tipos de Validacion
- **Verificacion funcional:** el sistema hace lo que dice hacer.
- **Verificacion numerica:** los resultados respetan formulas y unidades.
- **Verificacion de integracion:** los modulos cooperan sin romper contratos.
- **Verificacion de rendimiento:** la ejecucion es razonable en CPU o GPU.

## 5. Riesgos que se Detectan
- Unidades inconsistentes.
- Parametros fuera de rango.
- Seleccion incorrecta de modelo.
- Fallos en la carga de datos de terreno.
- Desalineacion entre resultados graficos y calculados.

## 6. Resultados Esperados
- Cobertura de pruebas clara por area.
- Repetibilidad de simulaciones con mismas entradas.
- Mismos resultados logicos aunque el backend cambie entre CPU y GPU, dentro del margen permitido.

## 7. Uso Recomendado
Antes de publicar resultados, ejecutar el conjunto de pruebas y revisar las salidas exportadas frente a los parametros de entrada.

## 8. Resumen
La validacion es parte central del proyecto porque asegura que el pipeline completo conserve coherencia desde la modelacion hasta la exportacion.

---

**Ver tambien:** [00_AUDITORIA_TECNICA.md](00_AUDITORIA_TECNICA.md)
