# 01 · Conceptos para estudiar

## 1. ¿Qué hace el sistema?
Una cámara + Raspberry Pi 4B detecta personas en un recinto cerrado, les da un ID, las cuenta (entradas/salidas/ocupación), estima hacia dónde se mueven (flechas rojas del esquema #4 de la pizarra) y las dibuja en un **mapa 2D visto desde arriba**, como lo haría un LiDAR. Todo se ve en una página web en vivo.

**Idea clave para el ingeniero:** no tenemos LiDAR, así que usamos la cámara como *sensor de rango virtual*: un LiDAR 2D devuelve "a qué distancia hay algo en cada ángulo"; nosotros calculamos lo mismo a partir de la posición de los pies de cada persona.

## 2. ¿Necesito miles de imágenes para entrenar? NO
- Usamos **YOLO11n preentrenado en COCO** (dataset de ~330k imágenes, 80 clases, una es `person`).
- Nosotros solo hacemos **inferencia** (usar el modelo ya entrenado). No hay entrenamiento.
- Entrenar/afinar (*fine-tuning*) solo valdría la pena si la cámara está en un ángulo raro (cenital puro) y falla; bastarían ~200–500 imágenes propias etiquetadas (Roboflow), no miles.

## 3. Términos que te preguntarán
| Término | Qué es | En este proyecto |
|---|---|---|
| **Clasificación** | Dice *qué* hay en toda la imagen | No se usa |
| **Detección** | Caja + clase + confianza por objeto | **Sí: YOLO, clase person** |
| **Segmentación** | Máscara pixel a pixel del objeto | No (más lenta, no aporta al conteo) |
| **Tracking** | Mantiene el mismo ID de una persona entre frames | **Sí: ByteTrack** |
| **YOLO** | "You Only Look Once": red neuronal que detecta en una sola pasada (rápida) | yolo11n = versión *nano*, la más ligera |
| **COCO** | Dataset estándar de detección | Origen de los pesos |
| **NCNN** | Motor de inferencia optimizado para ARM/móviles | Acelera YOLO en la Pi |
| **Homografía** | Matriz 3×3 que transforma puntos de un plano a otro | Imagen del piso → metros en el piso |
| **LaserScan** | Arreglo de distancias por ángulo (salida de un LiDAR 2D, mensaje de ROS) | Lo replicamos virtualmente |
| **Histéresis** | Zona muerta para evitar cambios por ruido | Banda alrededor de la línea de conteo |
| **FPS** | Cuadros procesados por segundo | Meta ≥ 5 en la Pi |

## 4. Pipeline paso a paso
1. **Captura** (`capture.py`): frame 640×480 de la cámara.
2. **Detección** (`detector.py`): YOLO devuelve cajas de `person` con confianza ≥ 0.45; se descartan cajas diminutas.
3. **Tracking** (ByteTrack, dentro de Ultralytics): asigna ID persistente. Usa también detecciones de baja confianza para no perder a alguien parcialmente tapado.
4. **Conteo** (`counter.py`): línea virtual. Cada ID recuerda su lado confirmado; si cambia de lado fuera de la banda de histéresis → cuenta IN u OUT una sola vez.
5. **Movimiento** (`motion.py`): velocidad = desplazamiento en la última ~1 s → flecha roja.
6. **Mapa** (`mapper.py`): punto de los pies → homografía → (x, y) metros → mapa cenital + scan virtual + heatmap.
7. **Dashboard** (`server.py`): Flask sirve video, mapa y estadísticas.

## 5. Cómo funciona la homografía (la parte "ingeniería")
El piso es un plano. Una cámara que mira un plano lo ve deformado por la perspectiva, pero esa deformación es exactamente una **homografía** `H` (3×3). Si conocemos 4 puntos del piso en pixeles y en metros, `cv2.findHomography` calcula `H`. Luego, para cualquier persona, tomamos el punto donde pisa (centro-inferior de su caja) y `H` nos da sus metros (x, y).
- **Limitación honesta:** solo es válido para puntos **en el piso**; por eso usamos los pies, no el centro de la caja.
- El error crece con la distancia (cada pixel representa más metros lejos de la cámara).

## 6. Por qué es "pseudo-LiDAR"
LiDAR 2D: gira un láser y mide distancia por ángulo → `ranges[ángulo]`.
Nosotros: para cada persona calculamos `ángulo = atan2(x, y)` y `rango = √(x²+y²)` y llenamos el mismo arreglo (`virtual_scan` en `mapper.py`). Misma salida, otro sensor. Diferencias a mencionar: campo de visión limitado (~62° vs 270°/360°), solo ve personas (no paredes), la precisión depende de la calibración.

## 7. Limitaciones (decirlas con franqueza suma puntos)
- Oclusión fuerte (personas pegadas) puede fusionar o perder IDs.
- Poca luz reduce precisión.
- Campo de visión de una sola cámara; un solo punto de entrada por cámara.
- La ocupación = entradas − salidas: si alguien ya estaba dentro al arrancar, se arranca en 0 (se puede inicializar a mano).

---

## 8. Modo móvil: el que usamos en la demo
Además de la línea de puerta (modo `fixed`), el proyecto tiene el modo **`mobile`**, que es el activo por defecto (`CAMERA_MODE = "mobile"`). No necesita calibrar el piso.

| | Modo `fixed` | Modo `mobile` (el nuestro) |
|---|---|---|
| Distancia | Homografía imagen→piso (4 puntos) | **Modelo pinhole**: `Z = K / altura de caja` |
| Conteo | Cruce de una **línea** | Cruce de un **círculo de 4 m** |
| Cuándo | Cámara fija en una puerta | Cámara en mesa/robot, vista frontal |
| Calibración | 4 puntos del piso | 1–3 distancias medidas con cinta |

**Modelo pinhole (cámara estenopeica):** una persona de altura real `H` a distancia `Z` se proyecta con altura `h` píxeles: `h = f·H / Z`. Despejando: `Z = f·H / h = K / h`.
- `f` (focal en píxeles) = `(ancho/2) / tan(FOV/2)` = 320 / tan(27°) ≈ **628 px**.
- Supone una estatura `H = 1.70 m` → `K = 1067`.

**Limitaciones propias de este modo:** si la persona está **sentada, cortada por el borde o es mucho más alta/baja que 1.70 m**, la distancia sale con error. Ver [doc 04](04_calibracion_y_pruebas.md).

**"Entrada a zona"** = pasar de fuera del círculo de 4 m a dentro (con margen de 0.4 m y ≥ 3 cuadros de seguimiento). **"Salida de zona"** = lo contrario. **"En zona ahora"** = cuántos hay dentro en este instante.
