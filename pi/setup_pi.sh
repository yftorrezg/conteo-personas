#!/usr/bin/env bash
# Se ejecuta UNA vez en la Pi. Instala dependencias en un venv aislado (~10-20 min).
set -e
cd "$(dirname "$0")/.."
sudo apt-get update
sudo apt-get install -y python3-venv python3-pip libopenblas0 libgomp1 avahi-daemon libgl1 libglib2.0-0
command -v rpicam-vid >/dev/null || sudo apt-get install -y rpicam-apps-lite || sudo apt-get install -y rpicam-apps
python3 -m venv ~/conteo-venv
source ~/conteo-venv/bin/activate
pip install --upgrade pip
# PyTorch solo-CPU (el de PyPI en ARM arrastra GBs de librerías CUDA inútiles)
pip install --retries 15 --timeout 60 torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install --retries 15 --timeout 60 ultralytics opencv-python-headless flask numpy
pip install ncnn || echo 'AVISO: no hay paquete ncnn; se usará yolo11n.pt (más lento)'
pip install lapx || true    # dependencia del tracker (alternativa a lap)
echo
echo "== Instalado. Probando cámara =="
bash pi/check_camera.sh || true
