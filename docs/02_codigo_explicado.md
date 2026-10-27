# 02 · Código explicado 🧠

Todo el programa está en `src/`. Son ~1000 líneas repartidas en archivos pequeños; cada uno hace **una sola cosa**.

## 🗺️ Mapa general: qué pasa en cada cuadro de video

```
 capture.py ──▶ detector.py ──▶ mapper.py ──▶ counter.py ──▶ server.py ──▶ 🌐 navegador
 (imagen)       (personas+ID)   (metros)      (entra/sale)   (web)
                      │              ▲
                      └─ motion.py ──┘ (velocidad → flechas)

               main.py = el director de orquesta que llama a todos, en bucle
```

| Archivo | Una línea | Líneas aprox. |
|---|---|---|
| `main.py` | Bucle principal: une todo y publica resultados | 215 |
| `capture.py` | Lee imágenes de la cámara (CSI, USB o video) | 125 |
| `detector.py` | YOLO detecta personas + ByteTrack les pone ID | 55 |
| `mapper.py` | Convierte píxeles a metros y dibuja el mapa | 160 |
| `counter.py` | Cuenta entradas/salidas | 95 |
| `motion.py` | Calcula velocidad de cada persona | 30 |
| `server.py` | Servidor web Flask (video, mapa, estadísticas, calibración) | 200 |
| `dashboard.html` | Interfaz web (HTML + CSS + JS) | 250 |
| `config.py` | **Todos los parámetros ajustables** | 65 |

---

## 1. `config.py` — el panel de control ⚙️

Todo lo que se puede ajustar vive aquí. **Si quieres cambiar algo, empieza por este archivo.**

| Parámetro | Valor | Qué hace | Si lo subes… |
|---|---|---|---|
| `FRAME_W, FRAME_H` | 640, 480 | Tamaño de la imagen | más detalle, más lento |
| `IMGSZ` | 416 (en la Pi: 320) | Tamaño con que YOLO analiza | más preciso, más lento |
| `CONF` | 0.45 | Confianza mínima para aceptar una detección | menos falsos positivos, pierde gente |
| `MIN_BOX_H` | 40 px | Descarta cajas más pequeñas que esto | ignora objetos lejanos |
| `FRAME_SKIP` | 1 | Procesa 1 de cada N cuadros | más rápido, menos fluido |
| `CAMERA_MODE` | `"mobile"` | `mobile` = zona circular; `fixed` = línea de puerta | — |
| `ZONE_RADIUS_M` | 4.0 | Radio de la zona de conteo (m) | zona más grande |
| `ZONE_HYST_M` | 0.4 | Margen anti-ruido en el borde (m) | cuenta menos "rebotes" |
| `MIN_TRACK_FRAMES` | 3 | Cuadros mínimos de seguimiento para contar | más estricto |
| `MAX_CAPACITY` | 5 | Aforo máximo (alerta roja si se supera) | — |
| `PERSON_HEIGHT_M` | 1.70 | Estatura supuesta para estimar distancia | ver doc 04 |
| `FOV_DEG` | 54 | Campo de visión horizontal de la cámara | — |
| `VEL_WINDOW_S` | 1.0 | Ventana para calcular velocidad | flechas más suaves |
| `PORT` | 5000 | Puerto del servidor web | — |

Algunos se cambian **sin editar el archivo**, con variables de entorno (las usa `pi/run.sh`):
```bash
PC_SOURCE=picam     # fuente de video: picam | usb:0 | ruta/a/video.mp4
PC_MODEL=yolo11n_320_ncnn_model
PC_IMGSZ=320
PC_MODE=mobile
PC_THERMAL_MAX=80   # °C a los que se pausa para enfriar
PC_IDLE_S=600       # segundos sin nadie mirando el dashboard → descansa
```

**La focal en píxeles** se calcula con trigonometría a partir del campo de visión:
```python
FOCAL_PX = (FRAME_W / 2) / math.tan(math.radians(FOV_DEG / 2))   # = 628 px
K_DEFAULT = FOCAL_PX * PERSON_HEIGHT_M                           # = 1067 (m·px)
```

---

## 2. `capture.py` — los ojos 👁️

Clase `Capture`. Abstrae **tres fuentes** de imagen con la misma interfaz `read()`:

| Fuente | Valor de `--source` | Cómo lee |
|---|---|---|
| Cámara de la Pi | `picam` | Lanza el programa `rpicam-vid` y lee su salida MJPEG |
| Webcam USB | `usb:0` | `cv2.VideoCapture(0)` |
| Archivo de video | `ruta.mp4` | `cv2.VideoCapture(ruta)` |

**Truco importante:** para la cámara de la Pi, un **hilo aparte** (`_reader`) lee las imágenes continuamente y guarda *solo la más reciente*. Así el análisis nunca procesa imágenes viejas → **no se acumula retraso**.
```python
with self._lock:
    self._frame = img        # siempre se sobrescribe: solo importa el último
```
También tiene `reconnect()`: si la cámara se desconecta, reintenta 10 veces.

---

## 3. `detector.py` — el cerebro de IA 🤖

```python
self.model = YOLO(config.MODEL, task="detect")       # carga la red neuronal

res = self.model.track(
    frame,
    persist=True,                 # recuerda IDs entre cuadros
    tracker="bytetrack.yaml",     # algoritmo de seguimiento
    classes=[0],                  # solo clase 0 = "person" (COCO)
    conf=config.CONF,             # confianza mínima
    imgsz=config.IMGSZ,
)
```
- **YOLO11n** = detección (¿dónde hay personas?). Es la versión *nano*: la más ligera.
- **ByteTrack** = seguimiento (¿es la misma persona del cuadro anterior?). Le asigna un **ID** estable.
- Cada resultado se guarda en un objeto `Person(id, box, conf)`:
  - `box` = (x1, y1, x2, y2) en píxeles
  - `foot` = punto centro-inferior (los pies)
  - `center` = centro de la caja

> 💡 **No se entrenó nada.** El modelo ya viene entrenado con COCO (330 000 imágenes, 80 clases). Solo se *usa*.

El modelo en la Pi está **exportado a NCNN** (`yolo11n_320_ncnn_model/`), un formato optimizado para procesadores ARM → ~2× más rápido que PyTorch en la Pi.

---

## 4. `mapper.py` — de píxeles a metros 📏

### La fórmula de distancia (modelo *pinhole*)
Una persona de altura real **H** a distancia **Z** aparece en la imagen con altura **h** píxeles:

```
        f · H                       K
Z  =  ─────────     →     Z  =  ─────────       donde  K = f · H
          h                         h
```
```python
def pinhole(self, p):
    x1, y1, x2, y2 = p.box
    z = self.k / max(y2 - y1, 1.0)                               # profundidad (m)
    x = ((x1 + x2) / 2.0 - config.FRAME_W / 2.0) / config.FOCAL_PX * z   # lateral (m)
    return x, z
```
- **Cuanto más grande se ve la caja, más cerca está.**
- `x` (lateral) sale de qué tan a un lado de la imagen está la persona.
- La distancia al sensor es `math.hypot(x, z)`.

**Ejemplo con números reales de nuestra prueba:** persona de 1.63 m a 3 m → su caja medía **347 px** → `Z = 1067 / 347 = 3.08 m` (error +2.5 %).

### Modo `fixed` (alternativo): homografía
Para una cámara fija en techo/pared, `FloorMapper` también implementa una **homografía** (matriz 3×3, `cv2.findHomography`) calibrada con 4 puntos del piso. Se usa el punto de los pies. Ver doc 01 sección 5.

### `render()` — el mapa cenital
Dibuja con OpenCV: anillos cada metro, cono de visión, círculo de la zona, puntos y flechas. Devuelve una imagen que el servidor publica.

### `virtual_scan()` — el "LiDAR virtual"
Devuelve un arreglo `ranges[ángulo]` (1 valor por grado) igual al `LaserScan` de ROS:
```python
ang = math.degrees(math.atan2(x, y))     # 0° = de frente
ranges[idx] = min(ranges[idx], math.hypot(x, y))
```

### Recarga en caliente
`reload_if_changed()` mira si cambió `dist_calib.json` o `calibration.json` y los recarga **sin reiniciar** el programa.

---

## 5. `counter.py` — el que cuenta 🔢

### `ZoneCounter` (modo móvil, el que usamos)
```python
d = math.hypot(x, y)                                   # distancia a la cámara
if   d < ZONE_RADIUS_M - ZONE_HYST_M: new = True       # claramente DENTRO  (< 3.6 m)
elif d > ZONE_RADIUS_M + ZONE_HYST_M: new = False      # claramente FUERA   (> 4.4 m)
else: continue                                         # zona gris: no decide nada
...
if prev is not None and prev != new and seen >= MIN_TRACK_FRAMES:
    # cambió de lado → ENTRADA (new=True) o SALIDA (new=False)
```
Cada ID recuerda si estaba dentro o fuera. **Solo cuenta cuando cambia** de estado, y **una sola vez** por cambio. `occupancy` = cuántos están dentro ahora.

### `LineCounter` (modo fijo)
Cuenta cruces de una **línea virtual** (ej. una puerta) con la misma idea de histéresis.

---

## 6. `motion.py` — hacia dónde va 🧭
Guarda las posiciones recientes de cada ID y calcula `velocidad = (posición_ahora − posición_hace_1s) / tiempo`. Esa velocidad dibuja la **flecha roja** en el video y en el mapa.

---

## 7. `server.py` + `dashboard.html` — la web 🌐
Flask es un servidor web mínimo. Estas son sus rutas:

| Ruta | Qué devuelve |
|---|---|
| `/` | La página del dashboard (`dashboard.html`) |
| `/video` | Video en vivo (flujo MJPEG) |
| `/map` y `/map.jpg` | Mapa cenital |
| `/stats` | Números en JSON (visibles, entradas, salidas, personas, FPS, temperatura…) |
| `/boxes` | Alturas de caja actuales (para calibrar) |
| `/calibrate` | Página de calibración |
| `/calib_dist` | Guarda/borra la calibración de distancia |
| `/pause`, `/resume`, `/reset` | Botones del dashboard |
| `/snapshot.jpg` | Una foto cruda (para calibrar el piso) |

Puedes ver los datos crudos que consume el dashboard:
```bash
curl http://pi-conteo.local:5000/stats
```
El dashboard (JavaScript) pide `/stats` **dos veces por segundo** y actualiza los números en pantalla. El video y el mapa llegan como imágenes.

**Sin internet:** todo el CSS y JS está dentro de `dashboard.html`. No usa CDNs, así que funciona aunque la red no tenga salida a internet.

---

## 8. `main.py` — el director 🎬
Pseudocódigo del bucle principal:

```
al arrancar: abrir cámara, cargar YOLO, iniciar servidor web, crear archivo CSV

repetir siempre:
    si hay pausa (manual / nadie mira / Pi caliente): soltar cámara y esperar
    leer un cuadro
    cada FRAME_SKIP cuadros:
        personas = YOLO + ByteTrack(cuadro)          # detector.py
        posición en metros de cada una               # mapper.locate()
        suavizar la posición (promedio 60/40)        # evita saltos por ruido
        contar entradas/salidas                      # counter.update()
        calcular velocidades                         # motion.py
        escribir eventos en el CSV
    dibujar cajas/etiquetas sobre el cuadro          # draw()
    dibujar el mapa                                  # mapper.render()
    publicar todo al servidor web                    # server.publish()
```
**Suavizado:** la distancia por altura de caja es ruidosa, así que se promedia: `nuevo = 0.6·anterior + 0.4·medida`.

**Protecciones:**
- ⏸️ **Pausa por inactividad:** nadie mirando el dashboard 10 min → suelta la cámara.
- 🌡️ **Protección térmica:** a 80 °C pausa hasta bajar de 70 °C.
- 📷 **Reconexión** automática de la cámara.

---

## 9. `pi/` — scripts de la Raspberry

| Script | Qué hace | Cuándo |
|---|---|---|
| `run.sh` | Activa el entorno y arranca `main.py` con la cámara y el modelo NCNN | Lo llama el servicio |
| `install_service.sh` | Crea el servicio `conteo` (arranque automático al encender) | Una vez |
| `setup_pi.sh` | Instala Python, PyTorch, Ultralytics, OpenCV, Flask, NCNN | Una vez |
| `check_camera.sh` | Verifica que la cámara es detectada y toma una foto de prueba | Si hay dudas de la cámara |
| `deploy.sh` | Copia `src/` y `pi/` desde la laptop a la Pi (`scp`) | Cada vez que cambies código |
| `flash_sd.sh` | Prepara una SD nueva con todo (usuario, WiFi, proyecto) | Si cambias de SD |
| `laptop_setup.sh` | Prepara la laptop (Arch/CachyOS) | Una vez, opcional |

### El servicio `conteo` (por qué arranca solo)
`systemd` es el gestor de servicios de Linux. El archivo `/etc/systemd/system/conteo.service` dice:
```ini
[Service]
User=pi
WorkingDirectory=/home/pi/conteo
ExecStart=/bin/bash /home/pi/conteo/pi/run.sh
Restart=always          # si se cae, se reinicia solo
RestartSec=3
[Install]
WantedBy=multi-user.target    # se inicia al encender la Pi
```

---

## 10. `tests/test_logic.py` — pruebas automáticas ✅
Prueban la lógica **sin cámara ni IA** (conteo, histéresis, homografía, etc.):
```bash
python tests/test_logic.py
```
Requiere tener OpenCV instalado (`pip install opencv-python-headless`).

---

## 🔁 Cómo actualizar el código en la Pi
1. Edita el archivo en tu laptop (por ejemplo `src/config.py`).
2. Cópialo a la Pi:
   ```bash
   scp src/config.py pi@pi-conteo.local:~/conteo/src/
   ```
3. Reinicia el programa:
   ```bash
   ssh pi@pi-conteo.local "sudo systemctl restart conteo"
   ```
4. Espera ~15 s y recarga el dashboard (`Ctrl + F5`).

> ⚠️ Haz siempre una **copia de seguridad** antes: `ssh pi@pi-conteo.local "cp -r ~/conteo/src ~/conteo/src_backup"`.
