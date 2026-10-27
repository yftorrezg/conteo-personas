# 06 · Solución de problemas 🛠️

Busca tu síntoma en la tabla. Cada fila dice **qué pasa**, **por qué** y **qué hacer**.

## 🔌 No enciende / no aparece en la red

| Síntoma | Causa probable | Qué hacer |
|---|---|---|
| Ninguna luz al enchufar | Powerbank sin carga, cable defectuoso, powerbank con apagado automático por poco consumo | Prueba otro cable/cargador de 5 V 3 A; mantén la powerbank cargada; pulsa su botón |
| Luz roja pero la verde no parpadea | Tarjeta SD mal puesta o dañada | Apaga, reinserta la SD, enciende |
| `ping pi-conteo.local` falla | Aún arranca / red distinta / hotspot apagado | Espera 2 min; confirma que laptop y Pi están en `Yafer`; mira la IP en el celular |
| Aparece en el celular pero `.local` no resuelve | mDNS no funciona en esa red | Usa la **IP** directamente: `http://IP:5000` y `ssh pi@IP` |
| La Pi no se une al hotspot | Hotspot en 5 GHz o con otro nombre | Hotspot en **2.4 GHz**, nombre exacto `Yafer` |
| Dejó de responder tras cambiar de red | La laptop está en otra red | Conecta la laptop a la misma red; si no, espera ~2 min a que vuelva a una red conocida |

## 🌐 El dashboard no carga o va lento

| Síntoma | Causa | Qué hacer |
|---|---|---|
| Página en blanco / "no se puede acceder" | Programa caído o URL equivocada | `ssh pi@pi-conteo.local "systemctl is-active conteo"` → si no dice `active`: `sudo systemctl restart conteo` |
| Carga una página **vieja** con datos congelados | Pestaña abierta de otra red/IP | Cierra la pestaña y abre la URL actual; `Ctrl + F5` |
| Video con mucho retraso | WiFi débil | `ping -c 10 pi-conteo.local` → si `avg` > 100 ms: acerca la Pi al router/celular, usa **hotspot 2.4 GHz** o **cable Ethernet** |
| "EN PAUSA (nadie mira el dashboard…)" | Pausa automática | Se reactiva sola en ~5 s al abrir la página |
| "EN PAUSA (pausa manual)" | Se pulsó Pausar | Pulsa **Reanudar** |
| "EN PAUSA (enfriando la Pi)" | Pasó de 80 °C | Mejora la ventilación; espera a que baje de 70 °C |
| FPS muy bajos (< 3) | Pi caliente o sobrecargada | `top`; `vcgencmd measure_temp`; verifica que no haya dos programas corriendo |

## 📷 Cámara

| Síntoma | Causa | Qué hacer |
|---|---|---|
| Video negro | Cámara no detectada | Apaga y desenchufa; revisa la **cinta** (contactos hacia el lado correcto, bien insertada); enciende. Prueba `bash ~/conteo/pi/check_camera.sh` |
| `rpicam-vid no entregó imagen` en el log | Cinta floja / cámara ocupada por otro proceso | `sudo systemctl stop conteo`, luego `check_camera.sh` |
| Imagen muy oscura | Poca luz | Más luz; la IA pierde precisión con poca luz |
| Imagen al revés | Montaje de la cámara | Rota la cámara físicamente (o se puede añadir `--vflip` en `capture.py`) |

## 📏 Detecciones y números

| Síntoma | Causa | Qué hacer |
|---|---|---|
| No detecta a nadie | `CONF` muy alto / mala luz / persona muy pequeña | Bajar `CONF` a 0.35; acercarse; más luz |
| Detecta "personas" que no existen | `CONF` bajo | Subir `CONF` a 0.55 y `MIN_BOX_H` |
| La distancia no coincide con la cinta | Persona cortada, sentada, de otra estatura | Persona **de pie y de cuerpo completo** a > 2.5 m; recalibrar `K` (doc 04) |
| Marca `<` en la distancia | Persona cortada por el borde | Alejarse hasta verse completa; la distancia real es **menor** |
| Cuenta de más o de menos | Persona en el borde de la zona / oclusión | Subir `ZONE_HYST_M`; evitar personas pegadas |
| Los IDs cambian mucho | Oclusión, poca luz | Mejor luz y ángulo |
| "Personas distintas" crece mucho | El ID cambia al perderse y reaparecer alguien | Normal con oclusiones; pulsa **Reiniciar conteo** antes de cada prueba |

## 🌡️ Temperatura y energía

| Síntoma | Qué significa | Qué hacer |
|---|---|---|
| Temp > 70 °C | Poca ventilación | Conecta el **ventilador** (pines 4 y 6, doc 03 sección 9); quita obstáculos |
| `get_throttled` ≠ `0x0` | Fuente débil o calor | Otro cable/cargador de 5 V 3 A; ventilar |
| Se apaga sola | Powerbank sin carga o se corta por poco consumo | Powerbank cargada; probar otra |
| Disipador muy caliente al tacto | 60–65 °C se siente "ardiendo" pero es normal | Mide con `vcgencmd measure_temp`; si < 80 °C no hay peligro |

## 🔐 SSH

| Mensaje | Qué hacer |
|---|---|
| `Connection timed out` | Pi apagada o en otra red |
| `Permission denied` | Contraseña incorrecta (no se ve al teclear) |
| `REMOTE HOST IDENTIFICATION HAS CHANGED` | `ssh-keygen -R pi-conteo.local` y reintenta |
| `Could not resolve hostname` | Usa la IP del celular |

## 💾 SD dañada o Pi que no arranca más
Si la Pi **no arranca después de un apagón**, la tarjeta SD pudo corromperse. Se restaura con `pi/flash_sd.sh` (necesita la imagen del sistema en `os-image/` y `pi/wifi.env` con las redes). Por eso: **siempre** apagar con `sudo poweroff`.

## 🆘 Si nada funciona
Ve a **Plan B** en el [manual, sección 12](00_GUIA_PASO_A_PASO.md#12--plan-b-si-algo-falla): correr el sistema en la laptop con un video de prueba y mostrar las capturas de `docs/img/`.
