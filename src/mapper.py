"""Pseudo-LiDAR: de pixeles a metros en el piso (homografía) + mapa cenital.

Sistema de coordenadas del mundo (metros), con la cámara en el origen:
  x -> derecha de la cámara, y -> hacia adelante (profundidad).
La homografía H lleva el punto de los pies de cada persona (px) al piso (m).
"""
import math
import os

import cv2
import numpy as np

import config


class FloorMapper:
    def __init__(self):
        self.H = None
        self.calibrated = False
        self._mtime = None
        self.world_pts = []
        self.k = config.K_DEFAULT
        self._kmtime = None
        self.reload_if_changed()
        self.heat = np.zeros((config.MAP_SIZE, config.MAP_SIZE), np.float32)
        self.ppm = config.MAP_SIZE / (config.MAP_RANGE_M * 1.0)  # px por metro (eje y)

    def reload_if_changed(self):
        """Recarga calibration.json si cambió (se guarda desde /calibrate)."""
        try:
            km = os.path.getmtime(config.DIST_CALIB_FILE)
        except OSError:
            km = None
        if km != self._kmtime:
            self._kmtime = km
            self.k = config.load_dist_k() or config.K_DEFAULT
        try:
            m = os.path.getmtime(config.CALIB_FILE)
        except OSError:
            return
        if m == self._mtime:
            return
        calib = config.load_calibration()
        if calib is None:
            return
        img_pts, world_pts = calib
        H, _ = cv2.findHomography(np.array(img_pts, np.float32), np.array(world_pts, np.float32))
        if H is not None:
            self.H, self.calibrated, self._mtime = H, True, m
            self.world_pts = world_pts

    @staticmethod
    def is_partial(p):
        """Caja pegada al borde superior/inferior: persona cortada, la distancia es una cota."""
        return p.box[1] <= 3 or p.box[3] >= config.FRAME_H - 3

    def pinhole(self, p):
        """Posición (x lateral, y profundidad) en m con el modelo pinhole y la altura de la caja."""
        x1, y1, x2, y2 = p.box
        z = self.k / max(y2 - y1, 1.0)
        x = ((x1 + x2) / 2.0 - config.FRAME_W / 2.0) / config.FOCAL_PX * z
        return x, z

    def locate(self, p):
        """(x, y) en metros respecto a la cámara según el modo de trabajo."""
        if config.CAMERA_MODE == "fixed":
            return self.to_world(p.foot)
        return self.pinhole(p)

    def to_world(self, pt):
        """(px,py) -> (x_m, y_m) o None si no hay calibración."""
        if self.H is None:
            return None
        v = cv2.perspectiveTransform(np.array([[pt]], np.float32), self.H)[0][0]
        return float(v[0]), float(v[1])

    def _world_to_map(self, x, y):
        s = config.MAP_SIZE
        mx = int(s / 2 + x * self.ppm)
        my = int(s - 1 - y * self.ppm)
        return mx, my

    def virtual_scan(self, world_pts):
        """LaserScan virtual: rango mínimo (m) por ángulo; inf si no hay obstáculo."""
        n = config.SCAN_BINS
        ranges = [math.inf] * n
        half = config.FOV_DEG / 2.0
        for x, y in world_pts:
            ang = math.degrees(math.atan2(x, y))      # 0° = frente
            if abs(ang) > 90:
                continue
            idx = int((ang + 90) / 180 * (n - 1))
            ranges[idx] = min(ranges[idx], math.hypot(x, y))
        return ranges

    def render(self, people_world, velocities_world, ids_count):
        """people_world: {id:(x,y)}; velocities_world: {id:(vx,vy)} en m/s."""
        s = config.MAP_SIZE
        img = np.full((s, s, 3), 18, np.uint8)

        fixed = config.CAMERA_MODE == "fixed"
        # heatmap acumulado (solo cámara fija: con cámara móvil no tiene sentido)
        for x, y in (people_world.values() if fixed else ()):
            mx, my = self._world_to_map(x, y)
            if 0 <= mx < s and 0 <= my < s:
                cv2.circle(self.heat, (mx, my), 12, 1.0, -1)
        self.heat *= 0.9995
        hm = cv2.applyColorMap(
            np.clip(self.heat / max(self.heat.max(), 1e-6) * 255, 0, 255).astype(np.uint8),
            cv2.COLORMAP_INFERNO,
        )
        if fixed:
            img = cv2.addWeighted(img, 0.6, hm, 0.4, 0)

        # área del piso calibrada (el "entorno mapeado")
        if fixed and self.world_pts:
            poly = np.array([self._world_to_map(x, y) for x, y in self.world_pts], np.int32)
            cv2.polylines(img, [poly], True, (200, 160, 40), 2)

        # anillos de distancia (cada metro) y cono de visión
        cam = (s // 2, s - 1)
        for r in range(1, int(config.MAP_RANGE_M) + 1):
            cv2.circle(img, cam, int(r * self.ppm), (60, 60, 60), 1)
            cv2.putText(img, f"{r}m", (cam[0] + 4, cam[1] - int(r * self.ppm) + 12),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (120, 120, 120), 1)
        half = math.radians(config.FOV_DEG / 2.0)
        L = s * 1.2
        for sgn in (-1, 1):
            end = (int(cam[0] + sgn * L * math.sin(half)), int(cam[1] - L * math.cos(half)))
            cv2.line(img, cam, end, (90, 90, 90), 1)
        cv2.circle(img, cam, 6, (0, 255, 255), -1)

        if not fixed:
            ov = img.copy()
            cv2.circle(ov, cam, int(config.ZONE_RADIUS_M * self.ppm), (40, 140, 255), -1)
            img = cv2.addWeighted(ov, 0.12, img, 0.88, 0)
            cv2.circle(img, cam, int(config.ZONE_RADIUS_M * self.ppm), (40, 140, 255), 2)
            cv2.putText(img, f"zona {config.ZONE_RADIUS_M:g} m", (cam[0] + 6, cam[1] - int(config.ZONE_RADIUS_M * self.ppm) - 6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (40, 140, 255), 1)

        # rayos del scan virtual (como líneas LiDAR hacia cada persona)
        for pid, (x, y) in people_world.items():
            mx, my = self._world_to_map(x, y)
            cv2.line(img, cam, (mx, my), (0, 120, 0), 1)

        # personas y flechas de velocidad
        for pid, (x, y) in people_world.items():
            mx, my = self._world_to_map(x, y)
            cv2.circle(img, (mx, my), 9, (0, 255, 0), -1)
            cv2.putText(img, f"{pid}  {math.hypot(x, y):.1f}m", (mx + 10, my - 6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            if pid in velocities_world:
                vx, vy = velocities_world[pid]
                ex, ey = self._world_to_map(x + vx * config.ARROW_SECONDS,
                                            y + vy * config.ARROW_SECONDS)
                cv2.arrowedLine(img, (mx, my), (ex, ey), (0, 0, 255), 2, tipLength=0.3)

        if fixed and not self.calibrated:
            cv2.putText(img, "SIN CALIBRAR: abre /calibrate", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 255), 2)
        elif not fixed:
            cv2.putText(img, "Vista desde arriba (camara abajo)", (10, 24),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        cv2.putText(img, f"Personas: {ids_count}", (10, s - 12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        return img
