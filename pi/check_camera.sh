#!/usr/bin/env bash
# Verifica que la cámara CSI es detectada y toma una foto de prueba.
CMD=$(command -v rpicam-hello || command -v libcamera-hello)
STILL=$(command -v rpicam-still || command -v libcamera-still)
[ -z "$CMD" ] && { echo "No hay rpicam-apps. Instala: sudo apt install -y rpicam-apps"; exit 1; }
$CMD --list-cameras
if $CMD --list-cameras 2>&1 | grep -q "Available cameras"; then
  $STILL -n -t 1000 --width 640 --height 480 -o /tmp/prueba.jpg && echo "OK: foto en /tmp/prueba.jpg"
else
  echo "CAMARA NO DETECTADA -> apaga la Pi, revisa la cinta (ver guía, sección 'Problemas')"; exit 1
fi
