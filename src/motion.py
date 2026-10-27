"""Velocidad y dirección por ID (las flechas rojas del esquema de la pizarra)."""
import time
from collections import defaultdict, deque

import config


class MotionEstimator:
    def __init__(self):
        self.hist = defaultdict(lambda: deque(maxlen=64))  # id -> (t, x, y)

    def update(self, positions, now=None):
        """positions: {id: (x, y)} en px o metros. Devuelve {id: (vx, vy)} por segundo."""
        now = now if now is not None else time.time()
        vel = {}
        for pid, (x, y) in positions.items():
            h = self.hist[pid]
            h.append((now, x, y))
            # usa solo la ventana reciente
            while len(h) > 2 and now - h[0][0] > config.VEL_WINDOW_S:
                h.popleft()
            if len(h) >= 3:
                t0, x0, y0 = h[0]
                dt = now - t0
                if dt > 0.2:
                    vel[pid] = ((x - x0) / dt, (y - y0) / dt)
        # limpia IDs que ya no existen
        for pid in list(self.hist):
            if pid not in positions and self.hist[pid] and now - self.hist[pid][-1][0] > 3:
                del self.hist[pid]
        return vel
