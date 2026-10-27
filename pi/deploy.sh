#!/usr/bin/env bash
# Uso (desde la laptop):  ./pi/deploy.sh usuario@IP_DE_LA_PI
# Copia el proyecto (código + modelo NCNN ya exportado) a la Pi.
set -e
DEST="${1:?Uso: ./pi/deploy.sh usuario@IP}"
cd "$(dirname "$0")/.."
ssh "$DEST" "mkdir -p ~/conteo"
scp -r src pi requirements.txt "$DEST":~/conteo/
echo "Copiado. Ahora en la Pi:  cd ~/conteo && bash pi/setup_pi.sh"
