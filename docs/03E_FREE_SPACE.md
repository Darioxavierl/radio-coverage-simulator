# Modelo Free Space

**Versión:** 2026-05-08

## 1. Descripcion
El modelo Free Space es el caso ideal de propagacion en espacio libre. No considera reflexiones, difraccion, absorcion atmosferica ni obstrucciones. Se usa como base teorica y como referencia minima de perdida.

## 2. Ecuacion Fundamental
La perdida en espacio libre se define como:

$$
L_{FSPL}(dB) = 32.44 + 20\log_{10}(d_{km}) + 20\log_{10}(f_{MHz})
$$

Equivalentemente, en unidades SI:

$$
L_{FSPL}(dB) = 20\log_{10}\left(\frac{4\pi d}{\lambda}\right)
$$

donde $d$ es la distancia entre transmisor y receptor y $\lambda$ es la longitud de onda.

## 3. Entradas
- Distancia $d$
- Frecuencia $f$
- Potencia transmitida $P_{tx}$
- Ganancias de antena $G_{tx}, G_{rx}$

## 4. Salidas
- Perdida de trayecto total
- Potencia recibida estimada
- Valor base para comparacion con modelos mas complejos

## 5. Hipotesis y Limites
- Linea de vista perfecta.
- Medio homogeneo e isótropo.
- No modela el efecto del terreno ni el clutter.

## 6. Uso en el Sistema
Se utiliza como referencia rapida y como control de integridad de las unidades. Es util para validar el flujo de calculo antes de aplicar modelos empiricos mas complejos.

## 7. Relacion con otros modelos
Free Space define el limite teorico superior de cobertura. Otros modelos introducen penalizaciones adicionales respecto a este baseline.

## 8. Ejemplo Conceptual
Si la potencia transmitida aumenta o la distancia disminuye, el valor de $P_{rx}$ crece conforme a la relacion logaritmica inversa de la distancia.

---

**Ver tambien:** [03_MODELOS_PROPAGACION.md](03_MODELOS_PROPAGACION.md)
