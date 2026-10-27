# 05 · Guion de demo y preguntas probables 🎤

## ✅ Antes de la demo
Usa el checklist completo del [manual (sección 11)](00_GUIA_PASO_A_PASO.md#11--checklist-del-día-de-la-defensa). Lo esencial:
- [ ] Hotspot `Yafer` (2.4 GHz) encendido, laptop conectada
- [ ] Pi enchufada 5 min antes; `ping pi-conteo.local` responde
- [ ] Dashboard abierto: `http://pi-conteo.local:5000`
- [ ] Terminal con `ssh pi@pi-conteo.local` ya abierta (para mostrar que es real)
- [ ] **Reiniciar conteo** → todo en 0
- [ ] Una persona de ayuda, una **cinta métrica** y marcas a 2.5, 3 y 4 m
- [ ] Tablas de pruebas (doc 04) llenas
- [ ] Video de respaldo listo

## 🕐 Guion (7 min)
| Min | Qué decir / hacer |
|---|---|
| 0:00 | **Problema:** contar y localizar personas en un recinto **sin LiDAR**, con hardware barato |
| 0:30 | **Solución:** la cámara hace de sensor de rango virtual. Mostrar la sección "¿Cómo funciona?" del dashboard (5 pasos) |
| 1:30 | **Terminal en vivo:** `ssh pi@pi-conteo.local` → `systemctl is-active conteo` → `vcgencmd measure_temp` → `vcgencmd get_throttled`. *"Esto corre en la Raspberry, no en mi laptop."* |
| 2:30 | **Demo:** una persona entra al círculo → **Entradas +1**, aparece en el mapa. Sale → **Salidas +1**. Dos personas → IDs distintos |
| 4:00 | **Distancia:** la amiga se para a 3 m con la cinta → el dashboard marca ≈ 3.1 m |
| 5:00 | **Aforo:** entran más de 5 (o bajar `MAX_CAPACITY` en pruebas) → la tarjeta se pone roja |
| 5:30 | **Resultados:** tablas del doc 04 (error de distancia, acierto de conteo, FPS, temperatura) |
| 6:30 | **Limitaciones y mejoras** (ver abajo) |

## ❓ Preguntas probables y respuestas

| Pregunta | Respuesta |
|---|---|
| **¿Entrenaron la red?** | No. Usamos **YOLO11n preentrenado en COCO** (330 000 imágenes, incluye la clase `person`). Solo hacemos *inferencia*. Validamos la precisión midiendo en nuestro entorno |
| **¿Por qué YOLO11n y no uno más grande?** | La Raspberry Pi 4 tiene CPU modesta. La versión *nano* + formato **NCNN** da ≈ 6 FPS, suficiente para personas caminando |
| **¿Por qué no segmentación?** | Para contar y ubicar basta la caja. Segmentar duplica el costo sin mejorar el resultado |
| **¿Cómo evitan contar dos veces a la misma persona?** | **ByteTrack** le da un ID estable + **histéresis** de 0.4 m + exigir ≥ 3 cuadros de seguimiento. Cada ID cuenta solo al *cambiar* de dentro↔fuera |
| **¿Cómo sacan la distancia con una sola cámara?** | Modelo *pinhole*: `Z = K / altura_de_caja`. Cuanto más grande se ve la persona, más cerca. `K` sale de la focal (por el campo de visión de 54°) y una estatura de referencia (1.70 m) |
| **¿Qué precisión tiene?** | A 3 m con una persona de 1.63 m: 3.08 m (**+2.5 %**). Meta < 10–15 %. (citar doc 04) |
| **¿Y si la persona es más alta o más baja?** | El error es proporcional a la diferencia de estatura (≈ ±5 % por cada 8 cm). Se puede **recalibrar `K`** desde `/calibrate` |
| **¿Qué pasa si la persona está muy cerca o sentada?** | Sale cortada y la caja es más corta, así que **sobreestima** la distancia. Lo avisamos con `<` en pantalla. Es una limitación del método |
| **¿Qué diferencia hay con un LiDAR?** | LiDAR: mide distancia directa, 360°, no depende de la luz. Nosotros: campo de visión ~54°, depende de luz y calibración; ventaja: **costo** y **semántica** (sabe que es una *persona*) |
| **¿Qué es el "pseudo-LiDAR"?** | `virtual_scan()` produce un arreglo de rango por ángulo, igual que un `LaserScan` de ROS, a partir de la cámara |
| **¿Cuántos FPS?** | ≈ 5.5 – 6.8 en la Pi. Con ≥ 5 basta para caminar normal |
| **¿Y la temperatura / energía?** | 47–65 °C, `get_throttled = 0x0` (sin bajo voltaje). Tiene ventilador, pausa térmica a 80 °C |
| **¿Y la privacidad?** | No se guardan imágenes. Solo un CSV de eventos (hora, ID, distancia) |
| **¿Cómo lo integrarían a un robot?** | El `virtual_scan` ya tiene formato `LaserScan`; se publicaría en un tópico `/scan` de ROS |
| **¿Por qué usan un dashboard web?** | Se ve desde cualquier dispositivo sin instalar nada; Flask sirve video, mapa y datos |
| **¿Qué pasa si se cae la red?** | La Pi sigue contando (el programa es independiente); al volver la red, se ve de nuevo. Y arranca solo al encenderla (`systemd`) |

## 🚧 Limitaciones y mejoras futuras
| Limitación | Mejora posible |
|---|---|
| Distancia depende de la estatura | Estimar la estatura con la posición de los pies, o usar cámara de profundidad |
| Una sola cámara, ~54° de campo | Varias cámaras o lente gran angular |
| Oclusión (personas pegadas) | Mejor ángulo de cámara, modelo más grande |
| Poca luz | Iluminación IR / cámara NoIR |
| ~6 FPS | Acelerador (Coral/Hailo) o Pi 5 |
| Sin integración robótica | Publicar `/scan` en ROS 2 |
