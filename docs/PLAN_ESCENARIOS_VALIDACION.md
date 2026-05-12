# Plan de Escenarios de Validacion
## Comparacion de mapas de calor con Atoll y benchmarking de aceleracion GPU

## 1. Objetivo
Definir un conjunto de escenarios reproducibles para:
1. Validar resultados de cobertura frente a Atoll.
2. Medir aceleracion CPU vs GPU por etapa y en tiempo total.
3. Obtener evidencia defendible para tesis con criterios cuantitativos.

## 2. Principios de comparabilidad con Atoll
1. Usar exactamente el mismo DEM y mismo sistema de coordenadas.
2. Igualar parametros radio: frecuencia, potencia, altura, ganancia, azimut, beamwidth.
3. Igualar modelo de propagacion y sus parametros dentro de lo posible.
4. Mantener la misma resolucion espacial y extension del area simulada.
5. Comparar en la misma metrica de salida, preferiblemente RSRP en dBm.
6. Congelar version de configuracion y registrar todo en metadata exportada.
7. Ejecutar cada escenario al menos 5 veces para separar variacion numerica de variacion operacional.

## 3. Metricas de validacion contra Atoll
Usar estas metricas en cada escenario:

| Metrica | Descripcion | Criterio recomendado |
|---|---|---|
| MAE dB | Error absoluto medio de RSRP punto a punto | <= 6 dB |
| RMSE dB | Error cuadratico medio de RSRP punto a punto | <= 8 dB |
| Bias dB | Promedio RF Tool - Atoll | entre -3 y +3 dB |
| Correlacion Pearson | Similitud espacial de patrones | >= 0.85 |
| Delta area cobertura | Diferencia en porcentaje de area sobre umbral (ej. -95 dBm) | <= 10% |

Nota: Los umbrales pueden ajustarse por entorno. En urbano denso puedes aceptar RMSE algo mayor que en escenario simple.

## 4. Protocolo de ejecucion para comparacion con Atoll
1. Preparar plantilla base de parametros.
2. Ejecutar escenario en RF Coverage Tool.
3. Exportar CSV y metadata JSON.
4. Ejecutar escenario equivalente en Atoll.
5. Exportar raster o tabla de puntos equivalente.
6. Reamostrar a grilla comun si difiere resolucion.
7. Calcular metricas MAE, RMSE, Bias, correlacion y area por umbral.
8. Documentar resultados y observaciones.

## 5. Escenarios de comparacion de mapas de calor (RF Tool vs Atoll)

### Escenario A1: Baseline monocelda omnidireccional
Razon: Caso minimo para validar consistencia global del modelo y pipeline sin complejidad de sectorizacion.

| Parametro | Configuracion |
|---|---|
| Numero de antenas | 1 |
| Geometria | Antena unica en zona central del ROI |
| Tipo de antena | Omnidireccional |
| Frecuencia | 900 MHz |
| Potencia Tx | 43 dBm |
| Altura Tx | 30 m AGL |
| Ganancia antena | 15 dBi |
| Modelo | Okumura-Hata |
| Entorno | Urban |
| Radio | 5 km |
| Resolucion | 300 |

### Escenario A2: Monocelda urbana COST-231
Razon: Validar sensibilidad a parametros urbanos explicitos y coherencia de gradiente radial en urbano denso.

| Parametro | Configuracion |
|---|---|
| Numero de antenas | 1 |
| Geometria | Antena central |
| Tipo de antena | Omnidireccional |
| Frecuencia | 1800 MHz |
| Potencia Tx | 43 dBm |
| Altura Tx | 35 m AGL |
| Ganancia antena | 17 dBi |
| Modelo | COST-231 |
| Entorno | Urban |
| Building height | 20 m |
| Street width | 15 m |
| Street orientation | 30 grados |
| Radio | 4 km |
| Resolucion | 400 |

### Escenario A3: Tricelda sectorizada
Razon: Validar forma lobular, orientacion de sectores y zonas de solape.

| Parametro | Configuracion |
|---|---|
| Numero de antenas | 3 |
| Geometria | Co-sitio con separacion angular |
| Tipo de antena | Direccional |
| Frecuencia | 1800 MHz |
| Potencia Tx por sector | 40 dBm |
| Altura Tx | 32 m AGL |
| Ganancia antena | 18 dBi |
| Azimut | 0, 120, 240 grados |
| Beamwidth horizontal | 65 grados |
| Modelo | COST-231 |
| Entorno | Urban |
| Building height | 18 m |
| Street width | 12 m |
| Radio | 4 km |
| Resolucion | 400 |

### Escenario A4: Red de 5 sitios direccionales
Razon: Aproximar planificacion real, validar patron agregado multi-sitio y best-server espacial.

| Parametro | Configuracion |
|---|---|
| Numero de antenas | 5 sitios, 1 sector por sitio o 5 sectores independientes |
| Geometria | Distribucion en cruz o anillo irregular |
| Tipo de antena | Direccional |
| Frecuencia | 2100 MHz |
| Potencia Tx | 40 dBm |
| Altura Tx | 25 m AGL |
| Ganancia antena | 17 dBi |
| Azimut | Apuntando hacia zona de demanda y con solape moderado |
| Beamwidth | 65 a 90 grados |
| Modelo | COST-231 |
| Entorno | Urban/Suburban segun zona |
| Radio | 6 km |
| Resolucion | 500 |

### Escenario A5: Macro rural largo alcance
Razon: Validar comportamiento de cobertura extendida en entorno menos obstruido.

| Parametro | Configuracion |
|---|---|
| Numero de antenas | 1 |
| Tipo de antena | Omnidireccional |
| Frecuencia | 700 MHz |
| Potencia Tx | 46 dBm |
| Altura Tx | 45 m AGL |
| Ganancia antena | 15 dBi |
| Modelo | ITU-R P.1546 |
| Entorno | Rural |
| Terrain type | Mixed |
| Radio | 10 km |
| Resolucion | 300 |

### Escenario A6: Urbano 5G con 3GPP
Razon: Validar comportamiento probabilistico LOS/NLOS y robustez frente a alta frecuencia.

| Parametro | Configuracion |
|---|---|
| Numero de antenas | 3 |
| Tipo de antena | Direccional |
| Frecuencia | 3500 MHz |
| Potencia Tx | 38 dBm |
| Altura BS | 25 m |
| Altura UE | 1.5 m |
| Modelo | 3GPP TR 38.901 |
| Escenario | UMa |
| Uso de DEM | Activado |
| Radio | 3 km |
| Resolucion | 500 |

### Escenario A7: Sensibilidad de terreno
Razon: Medir cuanto cambia la cobertura por DEM, util para explicar diferencias con Atoll.

| Parametro | Configuracion |
|---|---|
| Base | Repetir A2 o A6 |
| Corrida 1 | Con DEM |
| Corrida 2 | Terreno plano |
| Comparacion | Delta de area por umbral y delta RMSE espacial |

### Escenario A8: Sensibilidad de orientacion en sectorial
Razon: Verificar que el modelo responde de forma coherente a cambios de azimut.

| Parametro | Configuracion |
|---|---|
| Numero de antenas | 1 direccional |
| Modelo | COST-231 |
| Frecuencia | 1800 MHz |
| Potencia Tx | 40 dBm |
| Azimut | 0, 45, 90, 135 grados en corridas separadas |
| Beamwidth | 65 grados |
| Resto | Igual en todas las corridas |

## 6. Escenarios de benchmark de aceleracion GPU
Objetivo: separar aceleracion RF real de costos de render, agregacion y overhead.

### Regla metodologica obligatoria
1. Warm-up: 1 corrida de descarte por modo.
2. Medicion: minimo 5 corridas por escenario en CPU y GPU.
3. Reporte principal: mediana.
4. Metricas a reportar:
   1. antenna_coverage_times_seconds
   2. antenna_render_times_seconds
   3. multi_antenna_aggregation_time_seconds
   4. total_execution_time_seconds

### Escenario G1: Monocelda baja carga
Razon: medir overhead base y detectar si GPU todavia no compensa en total.

| Parametro | Configuracion |
|---|---|
| Antenas | 1 omni |
| Modelo | COST-231 |
| Resolucion | 200 |
| Puntos | 40,000 |
| Esperado | GPU puede empatar o perder en total; comparar RF puro |

### Escenario G2: Monocelda media carga
Razon: identificar punto de cruce CPU-GPU.

| Parametro | Configuracion |
|---|---|
| Antenas | 1 omni |
| Modelo | COST-231 |
| Resolucion | 500 |
| Puntos | 250,000 |
| Esperado | GPU gana en antenna_coverage_times_seconds |

### Escenario G3: Monocelda alta carga
Razon: maximizar calculo vectorial y observar escalamiento.

| Parametro | Configuracion |
|---|---|
| Antenas | 1 omni |
| Modelo | COST-231 o 3GPP |
| Resolucion | 800 |
| Puntos | 640,000 |
| Esperado | ventaja clara de GPU en RF puro |

### Escenario G4: Multiantena 5 celdas
Razon: amortizar warm-up y medir mejora acumulada.

| Parametro | Configuracion |
|---|---|
| Antenas | 5 direccionales |
| Modelo | COST-231 |
| Resolucion | 500 |
| Puntos por antena | 250,000 |
| Esperado | GPU gana en suma de coverage; render puede reducir ganancia total |

### Escenario G5: Multiantena 9 celdas
Razon: prueba de estres realista de planificacion.

| Parametro | Configuracion |
|---|---|
| Antenas | 9 direccionales |
| Modelo | COST-231 |
| Resolucion | 500 |
| Esperado | aceleracion RF estable, observar impacto de agregacion |

### Escenario G6: Impacto de modelo en rendimiento
Razon: cuantificar si la ganancia GPU depende del modelo.

| Parametro | Configuracion |
|---|---|
| Topologia | Misma de G4 |
| Modelos | Okumura-Hata, COST-231, ITU-R P.1546, 3GPP |
| Resolucion | 500 |
| Esperado | distinta ganancia por complejidad matematica del modelo |

### Escenario G7: Efecto del render
Razon: separar claramente calculo RF de visualizacion.

| Parametro | Configuracion |
|---|---|
| Base | Repetir G4 |
| Reporte | Coverage total, Render total, Total ejecucion |
| Esperado | render puede dominar parte del tiempo total |

## 7. KPIs de rendimiento GPU
Reportar por escenario:

| KPI | Formula |
|---|---|
| Speedup RF | S_RF = Mediana(CPU cobertura) / Mediana(GPU cobertura) |
| Speedup total | S_Total = Mediana(CPU total) / Mediana(GPU total) |
| Peso render | P_Render = Render total / Total ejecucion |
| Peso agregacion | P_Agg = Agregacion / Total ejecucion |
| Estabilidad | Coeficiente de variacion por etapa |

Criterios orientativos:
1. S_RF > 1.5 en escenarios medios y altos.
2. S_Total > 1.1 en multiantena media-alta.
3. Variacion de tiempos por etapa menor a 10% en corridas repetidas.

## 8. Plantilla de registro por escenario
Copiar esta tabla por cada escenario:

| Campo | Valor |
|---|---|
| ID escenario | A1, A2, G4, etc. |
| Objetivo | |
| Fecha | |
| Equipo | CPU, GPU, RAM, driver |
| Modelo | |
| Antenas | cantidad, tipo, azimut, beamwidth |
| Potencia y frecuencia | |
| Alturas | |
| Terreno | DEM o plano |
| Resolucion y radio | |
| Corridas CPU | n |
| Corridas GPU | n |
| Warm-up aplicado | si/no |
| MAE / RMSE / Bias / Corr | |
| Speedup RF / Total | |
| Observaciones | |

## 9. Riesgos de comparacion y como mitigarlos
1. Diferencias por calibracion interna entre herramientas.
Mitigacion: usar comparacion relativa y metricas espaciales, no solo valor puntual.
2. Diferencia de resolucion o reproyeccion.
Mitigacion: reamostrar a grilla comun y validar CRS.
3. Warm-up GPU distorsiona comparacion.
Mitigacion: descartar primera corrida y usar mediana.
4. Render influye en total.
Mitigacion: reportar siempre por etapa, no solo tiempo global.

## 10. Orden recomendado de ejecucion
1. Ejecutar A1, A2 y A3 para calibracion inicial con Atoll.
2. Ejecutar A4 y A6 para validacion operativa mas realista.
3. Ejecutar G1 a G3 para curva carga vs aceleracion.
4. Ejecutar G4 a G7 para validar ganancia en escenarios de red.
5. Consolidar resultados en una matriz final de aceptacion.
