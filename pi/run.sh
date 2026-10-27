#!/usr/bin/env bash
# Arranca el sistema en la Pi (cámara CSI + modelo NCNN).
cd "$(dirname "$0")/../src"
source ~/conteo-venv/bin/activate
export PC_SOURCE=${PC_SOURCE:-picam}
if python -c 'import ncnn' 2>/dev/null; then DEF=yolo11n_320_ncnn_model; else DEF=yolo11n.pt; fi
export PC_MODEL=${PC_MODEL:-$DEF}
export PC_IMGSZ=${PC_IMGSZ:-320}
export PC_THERMAL_MAX=${PC_THERMAL_MAX:-80}
exec python main.py "$@"
