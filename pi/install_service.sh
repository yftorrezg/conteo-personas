#!/usr/bin/env bash
# Arranque automático al encender la Pi (útil para la demo). Ejecutar en la Pi.
set -e
U=$(whoami); D="$HOME/conteo"
sudo tee /etc/systemd/system/conteo.service >/dev/null <<UNIT
[Unit]
Description=Conteo de personas
After=network-online.target

[Service]
User=$U
WorkingDirectory=$D
ExecStart=/bin/bash $D/pi/run.sh
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
UNIT
sudo systemctl daemon-reload
sudo systemctl enable --now conteo
echo "Servicio activo. Logs: journalctl -u conteo -f"
