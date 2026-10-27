"""Abstracción de la cámara: CSI (rpicam-vid), USB o archivo de video.

En la Pi la cámara CSI se lee con `rpicam-vid` (viene con Raspberry Pi OS) que
entrega un flujo MJPEG por stdout. Un hilo lector descarta frames viejos para
que el análisis siempre vea el más reciente (sin retraso acumulado).
"""
import shutil
import subprocess
import threading
import time

import cv2
import numpy as np

import config

SOI, EOI = b"\xff\xd8", b"\xff\xd9"


class Capture:
    def __init__(self, source=config.SOURCE):
        self.source = source
        self.kind = "picam" if source == "picam" else ("usb" if source.startswith("usb:") else "file")
        self.proc = None
        self.cam = None
        self._frame = None
        self._lock = threading.Lock()
        self._run = False
        self._open()

    # --- apertura --------------------------------------------------------
    def _open(self):
        if self.kind == "picam":
            exe = shutil.which("rpicam-vid") or shutil.which("libcamera-vid")
            if exe is None:
                raise RuntimeError("No se encontró rpicam-vid (¿Raspberry Pi OS con cámara habilitada?)")
            cmd = [exe, "-t", "0", "--nopreview", "--codec", "mjpeg", "--flush",
                   "--width", str(config.FRAME_W), "--height", str(config.FRAME_H),
                   "--framerate", "15", "-o", "-"]
            self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0)
            self._run = True
            threading.Thread(target=self._reader, daemon=True).start()
            for _ in range(100):  # espera hasta 5 s al primer frame
                if self._frame is not None:
                    return
                time.sleep(0.05)
            raise RuntimeError("rpicam-vid no entregó imagen (cable de cinta / cámara no detectada)")
        arg = int(self.source.split(":")[1]) if self.kind == "usb" else self.source
        self.cam = cv2.VideoCapture(arg)
        if self.kind == "usb":
            self.cam.set(cv2.CAP_PROP_FRAME_WIDTH, config.FRAME_W)
            self.cam.set(cv2.CAP_PROP_FRAME_HEIGHT, config.FRAME_H)
        if not self.cam.isOpened():
            raise RuntimeError(f"No se pudo abrir la fuente: {self.source}")

    def _reader(self):
        buf = b""
        out = self.proc.stdout
        while self._run:
            chunk = out.read(65536)
            if not chunk:
                break
            buf += chunk
            while True:
                a = buf.find(SOI)
                b = buf.find(EOI, a + 2) if a >= 0 else -1
                if a < 0 or b < 0:
                    if a < 0 and len(buf) > 1:
                        buf = buf[-1:]
                    break
                jpg, buf = buf[a:b + 2], buf[b + 2:]
                img = cv2.imdecode(np.frombuffer(jpg, np.uint8), cv2.IMREAD_COLOR)
                if img is not None:
                    with self._lock:
                        self._frame = img
        self._run = False

    # --- lectura ---------------------------------------------------------
    def read(self):
        """Frame BGR FRAME_W x FRAME_H, o None si la fuente terminó/falló."""
        if self.kind == "picam":
            if not self._run and self._frame is None:
                return None
            if not self._run:       # el proceso murió
                return None
            while self._run:
                with self._lock:
                    f, self._frame = self._frame, None
                if f is not None:
                    return f
                time.sleep(0.005)
            return None
        ok, frame = self.cam.read()
        if not ok:
            return None
        return cv2.resize(frame, (config.FRAME_W, config.FRAME_H))

    def reconnect(self):
        self.release()
        for _ in range(10):
            try:
                self._open()
                return True
            except Exception:
                self.release()
                time.sleep(1.0)
        return False

    def release(self):
        self._run = False
        try:
            if self.proc is not None:
                self.proc.terminate()
                self.proc.wait(timeout=3)
        except Exception:
            pass
        self.proc = None
        try:
            if self.cam is not None:
                self.cam.release()
        except Exception:
            pass
        self.cam = None
        self._frame = None
