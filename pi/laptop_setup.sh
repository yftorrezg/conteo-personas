#!/usr/bin/env bash
# Prepara una laptop (Arch/CachyOS) para ver el dashboard y para el plan B local. Una sola vez.
set -e
sudo pacman -S --needed --noconfirm python avahi nss-mdns openssh
sudo systemctl enable --now avahi-daemon
python -m venv ~/venvs/conteo
~/venvs/conteo/bin/pip install --upgrade pip
~/venvs/conteo/bin/pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
~/venvs/conteo/bin/pip install ultralytics opencv-python-headless flask ncnn
echo "Listo. Probar: cd src && ~/venvs/conteo/bin/python main.py --source ../videos/vtest.avi --show"
echo "Dashboard de la Pi: http://pi-conteo.local:5000"
