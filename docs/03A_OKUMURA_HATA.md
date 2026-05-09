# Modelo Okumura-Hata

**Versión:** 2026-05-08

## 1. Introduccion
El modelo Okumura-Hata es un modelo empirico clasico para estimacion de perdida de trayecto en ambientes urbanos, suburbanos y rurales. Esta basado en las mediciones de Okumura y formalizado por Hata para facilitar su uso analitico.

## 2. Rango de Validez
- Frecuencia tipica: aproximadamente 150 MHz a 1500 MHz.
- Distancias tipicas: 1 km a 20 km.
- Alturas de antena transmisora y receptora dentro del rango clasico del modelo.

## 3. Ecuacion Basica
La forma urbana clasica es:

$$
L_{50}(dB) = 69.55 + 26.16\log_{10}(f) - 13.82\log_{10}(h_b) - a(h_m)
+ \left[44.9 - 6.55\log_{10}(h_b)\right]\log_{10}(d)
$$

donde:
- $f$ esta en MHz
- $h_b$ es la altura de la antena base
- $h_m$ es la altura de la antena movil
- $d$ es la distancia en km
- $a(h_m)$ es el factor de correccion de altura del receptor

## 4. Correccion por Entorno
- **Urbano:** formula base.
- **Suburbano:** reduccion ajustada respecto al entorno urbano.
- **Rural/abierto:** correccion adicional para menor densidad de obstaculos.

## 5. Entradas
- Frecuencia
- Distancia
- Altura de antena base
- Altura de antena movil
- Tipo de entorno

## 6. Salidas
- Perdida media de trayecto
- Potencia recibida estimada
- Superficie de cobertura en el grid

## 7. Interpretacion
El modelo describe un comportamiento logaritmico con la distancia y penaliza alturas bajas de antena. Es muy util para escenarios macros y para una primera aproximacion de redes celulares.

## 8. Integracion
En el sistema, el modelo se invoca desde la capa de calculo y devuelve la perdida por celda del mapa de simulacion.

## 9. Limitaciones
- No captura de forma explicita difraccion compleja ni geometria detallada del terreno.
- Su exactitud depende de mantenerse dentro de su rango de validez.

---

**Ver tambien:** [03_MODELOS_PROPAGACION.md](03_MODELOS_PROPAGACION.md)
