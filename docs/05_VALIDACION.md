# Validacion y Verificacion

**Versión:** 2026-05-09

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

## 8. Validación Específica: 3GPP Modo 2 con Terreno (P.526)

### 8.1 Alcance
La validación del Modo 2 verifica que la corrección por terreno sea:
- Matemáticamente consistente con ITU-R P.526 (knife-edge).
- Numéricamente estable.
- Compatible con pipeline existente.
- Segura frente a entradas inválidas.

### 8.2 Casos de Prueba Implementados

Archivo de pruebas: `tests/test_3gpp_38901_complete.py`

| Caso | Objetivo | Criterio esperado |
|------|----------|-------------------|
| `test_terrain_shape_mismatch_raises` | Validar contrato de shape | `ValueError` si `terrain_heights.shape != distances.shape` |
| `test_flat_terrain_has_negligible_correction` | Verificar no penalización espuria | Corrección ~0 dB en terreno plano |
| `test_ridge_obstruction_increases_path_loss` | Verificar impacto físico con obstrucción | Corrección media significativa y acotada por `max_terrain_correction_db` |

### 8.3 Verificación Numérica

Ecuación validada en código:

$$v = h \sqrt{\frac{2(d_1 + d_2)}{\lambda d_1 d_2}}$$

$$L_d(v) =
\begin{cases}
0, & v \le -0.78 \\
6.9 + 20\log_{10}\left(\sqrt{(v-0.1)^2 + 1} + v - 0.1\right), & v > -0.78
\end{cases}$$

Pérdida final aplicada por terreno:

$$\Delta PL_{terrain} = L_d \cdot (1 - P_{LOS})$$

### 8.4 Resultado de Humo Ejecutado

Se ejecutó validación focalizada con `unittest` para la nueva clase de pruebas de terreno:
- 3/3 casos exitosos.
- Sin regresión en pruebas básicas y de consistencia del modelo 3GPP.

## 9. Resumen
La validación es parte central del proyecto porque asegura que el pipeline completo conserve coherencia desde la modelación hasta la exportación.

---

**Ver tambien:** [00_AUDITORIA_TECNICA.md](00_AUDITORIA_TECNICA.md)
