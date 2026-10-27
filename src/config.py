"""Parámetros centrales del sistema. Todo lo ajustable vive aquí."""
import json
import math
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CALIB_FILE = os.path.join(BASE_DIR, "calibration.json")
LOG_DIR = os.path.join(BASE_DIR, "..", "logs")

# --- Fuente de video ---------------------------------------------------------
# "picam"      -> cámara CSI (picamera2)
# "usb:0"      -> webcam USB / integrada (índice 0)
# "ruta.mp4"   -> archivo de video (pruebas y plan B de la demo)
SOURCE = os.environ.get("PC_SOURCE", "usb:0")
FRAME_W, FRAME_H = 640, 480

# --- Detección ---------------------------------------------------------------
# En laptop: "yolo11n.pt". En Pi: exportar a NCNN -> "yolo11n_ncnn_model"
MODEL = os.environ.get("PC_MODEL", "yolo11n.pt")
IMGSZ = int(os.environ.get("PC_IMGSZ", 416))
CONF = 0.45            # umbral de confianza
MIN_BOX_H = 40         # px: descarta cajas diminutas (falsos positivos)
FRAME_SKIP = 1         # procesa 1 de cada N frames (subir a 2 si la Pi va lenta)

# --- Conteo ------------------------------------------------------------------
# Línea virtual en coordenadas normalizadas (x, y) de 0 a 1.
COUNT_LINE = ((0.0, 0.55), (1.0, 0.55))
INVERT_DIRECTION = False  # True si IN/OUT salen al revés en tu instalación
LINE_BAND_PX = 14      # histéresis: banda a cada lado de la línea
MIN_TRACK_FRAMES = 3   # frames mínimos de un ID antes de poder contarlo
MAX_CAPACITY = 5       # aforo máximo -> alerta

# --- Mapa cenital / pseudo-LiDAR ---------------------------------------------
MAP_SIZE = 480         # px del mapa cuadrado
MAP_RANGE_M = 6.0      # alcance del mapa en metros (cámara abajo al centro)
SCAN_BINS = 180        # resolución angular del LaserScan virtual (1 bin/grado)
FOV_DEG = 54.0         # Pi Camera Rev 1.3 (OV5647): ~54° horizontal
FOCAL_PX = (FRAME_W / 2) / math.tan(math.radians(FOV_DEG / 2))  # distancia focal en píxeles

# "mobile": cámara en mano / sobre un robot. Distancia y ángulo de cada persona
#           con la altura de su caja (modelo pinhole), sin calibrar y sin línea.
# "fixed" : cámara fija en un paso. Línea de conteo IN/OUT + homografía al piso.
CAMERA_MODE = os.environ.get("PC_MODE", "mobile")
ZONE_RADIUS_M = 4.0     # modo móvil/mesa: zona circular alrededor de la cámara donde se cuenta
ZONE_HYST_M = 0.4       # histéresis (m) para no contar por el ruido de la distancia
PERSON_HEIGHT_M = 1.70  # estatura supuesta para estimar la distancia
# Constante K = distancia(m) * alto_de_caja(px). Se mide en /calibrate (sección "Distancia")
# y se guarda en dist_calib.json; si no existe se usa la teórica FOCAL_PX * PERSON_HEIGHT_M.
DIST_CALIB_FILE = os.path.join(BASE_DIR, "dist_calib.json")
K_DEFAULT = FOCAL_PX * PERSON_HEIGHT_M

# --- Movimiento --------------------------------------------------------------
VEL_WINDOW_S = 1.0     # ventana para estimar velocidad
ARROW_SECONDS = 1.0    # la flecha muestra el desplazamiento esperado en 1 s

# --- Servidor ----------------------------------------------------------------
HOST = "0.0.0.0"
PORT = 5000


def load_calibration():
    """Devuelve (puntos_imagen, puntos_mundo_m) o None si no hay calibración."""
    if not os.path.exists(CALIB_FILE):
        return None
    with open(CALIB_FILE) as f:
        d = json.load(f)
    return d["image_pts"], d["world_pts"]


def load_dist_k():
    """K de calibración de distancia (m*px) o None si no hay."""
    try:
        with open(DIST_CALIB_FILE) as f:
            return float(json.load(f)["k"])
    except (OSError, ValueError, KeyError):
        return None
