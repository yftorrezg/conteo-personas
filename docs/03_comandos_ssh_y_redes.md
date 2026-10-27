# 03 · Comandos, SSH y redes 🖥️

Chuleta rápida. Todo lo que necesitas teclear, con su explicación.
> 🔵 **[LAPTOP]** = se ejecuta en tu laptop. 🍓 **[PI]** = se ejecuta dentro de la Pi (después de `ssh`).

---

## 1. SSH (conectarse a la Pi)

| Acción | Comando |
|---|---|
| 🔵 Entrar | `ssh pi@pi-conteo.local` |
| 🔵 Entrar usando la IP | `ssh pi@10.194.180.215` |
| 🍓 Salir | `exit` |
| 🔵 Ejecutar un comando sin quedarte dentro | `ssh pi@pi-conteo.local "vcgencmd measure_temp"` |
| 🔵 Apagar | `ssh pi@pi-conteo.local "sudo poweroff"` |
| 🔵 Reiniciar la Pi | `ssh pi@pi-conteo.local "sudo reboot"` |

### Entrar sin contraseña (opcional, pero muy cómodo)
Se hace **una vez por laptop** con una llave:
```bash
# 1. Crear la llave (si no tienes; Enter a todo)
ssh-keygen -t ed25519
# 2. Copiarla a la Pi (te pide la contraseña esta vez)
ssh-copy-id pi@pi-conteo.local
# 3. Desde ahora entra sin pedir contraseña
ssh pi@pi-conteo.local
```
En Windows (PowerShell) no existe `ssh-copy-id`; usa en su lugar:
```powershell
type $env:USERPROFILE\.ssh\id_ed25519.pub | ssh pi@pi-conteo.local "cat >> ~/.ssh/authorized_keys"
```

### Errores típicos de SSH
| Mensaje | Causa y solución |
|---|---|
| `Could not resolve hostname pi-conteo.local` | La laptop no ve el nombre. Usa la **IP** (ver en el celular) o espera 1 min |
| `Connection timed out` | La Pi no está en la misma red / aún arranca / está apagada |
| `Permission denied` | Contraseña incorrecta (recuerda: no se ve al teclear) |
| `Host key verification failed` / `REMOTE HOST IDENTIFICATION HAS CHANGED` | Cambió la huella (tarjeta SD nueva). Ejecuta `ssh-keygen -R pi-conteo.local` y reintenta |

---

## 2. Dashboard y datos

| Acción | URL / comando |
|---|---|
| Dashboard | `http://pi-conteo.local:5000` |
| Calibración | `http://pi-conteo.local:5000/calibrate` |
| Datos en JSON | 🔵 `curl http://pi-conteo.local:5000/stats` |
| Solo el estado | 🔵 `curl -s http://pi-conteo.local:5000/stats \| python3 -c "import json,sys;d=json.load(sys.stdin);d.pop('history');print(d)"` |

---

## 3. El servicio `conteo` (el programa)

| Acción | Comando 🍓 |
|---|---|
| ¿Está corriendo? | `systemctl is-active conteo` |
| Estado detallado | `systemctl status conteo` (sal con `q`) |
| Iniciar | `sudo systemctl start conteo` |
| Parar | `sudo systemctl stop conteo` |
| Reiniciar | `sudo systemctl restart conteo` |
| Que NO arranque solo | `sudo systemctl disable conteo` |
| Que SÍ arranque solo | `sudo systemctl enable conteo` |
| Ver mensajes en vivo | `journalctl -u conteo -f` (sal con `Ctrl+C`) |
| Ver los últimos 50 mensajes | `journalctl -u conteo -n 50 --no-pager` |

---

## 4. Salud de la Pi

| Qué | Comando 🍓 | Valor bueno |
|---|---|---|
| Temperatura | `vcgencmd measure_temp` | < 70 °C |
| Energía | `vcgencmd get_throttled` | `0x0` |
| Frecuencia CPU | `vcgencmd measure_clock arm` | 1 800 000 000 (1.8 GHz) |
| CPU y procesos | `top` (salir `q`) | `python` ≈ 250 % trabajando |
| Memoria | `free -m` | `available` > 500 MB |
| Espacio en disco | `df -h /` | `Use%` < 80 % |
| Tiempo encendida | `uptime` | — |
| Mensajes de bajo voltaje | `dmesg \| grep -i under-voltage` | (sin salida) |

---

## 5. Red y WiFi

| Qué | Comando |
|---|---|
| 🍓 Ver mi IP | `hostname -I` |
| 🍓 Red WiFi actual y señal | `nmcli -t -f ACTIVE,SSID,SIGNAL,RATE,CHAN dev wifi \| grep "^yes"` |
| 🍓 Redes guardadas | `nmcli -t -f NAME,TYPE con show \| grep wireless` |
| 🍓 Pasar al hotspot | `sudo nohup sh -c "sleep 2; nmcli con up netplan-wlan0-Yafer" >/dev/null 2>&1 &` |
| 🍓 Pasar al WiFi de casa 2.4 GHz | `sudo nohup sh -c "sleep 2; nmcli con up netplan-wlan0-<NOMBRE-WIFI-CASA>" >/dev/null 2>&1 &` |
| 🔵 ¿La Pi responde? | `ping pi-conteo.local` (salir `Ctrl+C`) |
| 🔵 Calidad de la conexión | `ping -c 10 pi-conteo.local` → mira `avg` (menos de 50 ms = bien) |

**Cómo interpretar la señal WiFi:**
| Señal | Calidad |
|---|---|
| 80–100 % | Excelente |
| 60–79 % | Buena |
| < 55 % | Débil → habrá retraso en el video |

**Por qué el hotspot dio mejor resultado que el WiFi de casa:** el WiFi de casa en 5 GHz daba señal 52 % y *ping* de 250–1000 ms (lag). El hotspot a 2.4 GHz, cerca, dio 100 % y *ping* de ~17 ms. 5 GHz = más rápido pero atraviesa mal las paredes; 2.4 GHz = más lento pero más alcance.

⚠️ **Cuidado:** si cambias la Pi de red por SSH, **cambia la laptop a esa misma red primero**, o perderás el acceso.

---

## 6. Copiar archivos (SCP)

| Acción | Comando 🔵 |
|---|---|
| Laptop → Pi (un archivo) | `scp src/config.py pi@pi-conteo.local:~/conteo/src/` |
| Laptop → Pi (todo el código) | `scp -r src pi pi@pi-conteo.local:~/conteo/` |
| Pi → Laptop (registros) | `scp pi@pi-conteo.local:~/conteo/logs/*.csv .` |
| Pi → Laptop (una foto de la cámara) | `curl -o foto.jpg http://pi-conteo.local:5000/snapshot.jpg` |

---

## 7. Cámara

| Qué | Comando 🍓 |
|---|---|
| ¿La detecta? | `bash ~/conteo/pi/check_camera.sh` |
| Listar cámaras | `rpicam-hello --list-cameras` |
| Foto de prueba | `rpicam-still -n -t 1000 -o /tmp/prueba.jpg` |

> ⚠️ Si el servicio `conteo` está corriendo, **ocupa la cámara**. Para usar estos comandos antes haz `sudo systemctl stop conteo`.

---

## 8. Apagado seguro, resumen
```
 1. ssh pi@pi-conteo.local "sudo poweroff"
 2. esperar ~20 s (luz verde deja de parpadear)
 3. desenchufar la powerbank
```

---

## 9. 🔌 Conexión del ventilador (pines GPIO)

La Raspberry tiene 40 pines (2 filas × 20). El ventilador tiene 2 cables:

| Cable | Pin físico | Función |
|---|---|---|
| 🔴 Rojo | **4** (o el 2) | 5 V |
| ⚫ Negro | **6** | GND (tierra) |

```
 Con la Pi como en la foto (puertos USB a la derecha), los pines están junto al borde superior:

   fila del BORDE   (pares)    →  [2 ][4 ][6 ][8 ] ...    2 = 5V · 4 = 5V · 6 = GND
   fila INTERIOR    (impares)  →  [1 ][3 ][5 ][7 ] ...    1 = 3.3V
   (el pin 1 está en la esquina del lado de la tarjeta SD)
```
- ✅ **Siempre con la Pi apagada y desenchufada.**
- ✅ Verifica contando los pines en un dibujo oficial: <https://pinout.xyz> (también en `referencias/MANUAL RASPBERRY PI.pdf`).
- ⚠️ Si tu ventilador es de **3.3 V**, el rojo va al **pin 1**. Mira la etiqueta del ventilador.
- ⛔ Nunca conectes el rojo a un pin al azar.
- 💡 Si el ventilador gira y no hay otro problema, la temperatura con carga baja unos 10–20 °C.
