"""Conteo por línea virtual con histéresis y confirmación por frames.

Idea: cada ID tiene un "lado confirmado" de la línea (+1 / -1). Solo se
actualiza cuando la persona se aleja de la línea más que LINE_BAND_PX, así el
ruido de la caja cerca de la línea no genera cruces falsos. Un cruce se cuenta
cuando el lado confirmado cambia, y solo una vez por cambio.
"""
import math

import config


class LineCounter:
    def __init__(self, frame_w, frame_h):
        (x1, y1), (x2, y2) = config.COUNT_LINE
        self.p1 = (x1 * frame_w, y1 * frame_h)
        self.p2 = (x2 * frame_w, y2 * frame_h)
        dx, dy = self.p2[0] - self.p1[0], self.p2[1] - self.p1[1]
        self.length = math.hypot(dx, dy)
        self.nx, self.ny = -dy / self.length, dx / self.length  # normal unitaria
        self.side = {}      # id -> lado confirmado
        self.seen = {}      # id -> nº de frames vistos
        self.n_in = 0
        self.n_out = 0
        self.max_occupancy = 0
        self.occupancy = 0   # se ajusta por evento y nunca baja de 0
        self.events = []    # (tipo, id) pendientes de loguear

    def signed_dist(self, pt):
        return (pt[0] - self.p1[0]) * self.nx + (pt[1] - self.p1[1]) * self.ny

    def update(self, people, world=None):
        self.events.clear()
        for p in people:
            self.seen[p.id] = self.seen.get(p.id, 0) + 1
            d = self.signed_dist(p.foot)
            if abs(d) < config.LINE_BAND_PX:
                continue  # zona de incertidumbre: no decide nada
            s = 1 if d > 0 else -1
            prev = self.side.get(p.id)
            if prev is None:
                self.side[p.id] = s
            elif prev != s:
                if self.seen[p.id] >= config.MIN_TRACK_FRAMES:
                    # lado - a lado + = entrada (convención; se invierte con COUNT_LINE)
                    if (s > 0) != config.INVERT_DIRECTION:
                        self.n_in += 1
                        self.occupancy += 1
                        self.events.append(("IN", p.id))
                    else:
                        self.n_out += 1
                        self.occupancy = max(0, self.occupancy - 1)
                        self.events.append(("OUT", p.id))
                self.side[p.id] = s
        self.max_occupancy = max(self.max_occupancy, self.occupancy)


class ZoneCounter:
    """Cuenta personas dentro de una zona circular (radio ZONE_RADIUS_M) alrededor de la cámara.

    Entrada = una persona pasa de fuera a dentro del radio; salida = al revés. Usa
    histéresis (ZONE_HYST_M) y exige MIN_TRACK_FRAMES de seguimiento para contar.
    `occupancy` = personas dentro de la zona AHORA (no acumulado, no deriva con el tiempo).
    """

    def __init__(self):
        self.state = {}     # id -> True si está dentro de la zona
        self.seen = {}
        self.n_in = 0
        self.n_out = 0
        self.occupancy = 0
        self.max_occupancy = 0
        self.events = []

    def update(self, people, world):
        self.events.clear()
        for pid, (x, y) in world.items():
            self.seen[pid] = self.seen.get(pid, 0) + 1
            d = math.hypot(x, y)
            if d < config.ZONE_RADIUS_M - config.ZONE_HYST_M:
                new = True
            elif d > config.ZONE_RADIUS_M + config.ZONE_HYST_M:
                new = False
            else:
                continue  # banda de incertidumbre
            prev = self.state.get(pid)
            if prev is not None and prev != new and self.seen[pid] >= config.MIN_TRACK_FRAMES:
                if new:
                    self.n_in += 1
                    self.events.append(("IN", pid))
                else:
                    self.n_out += 1
                    self.events.append(("OUT", pid))
            self.state[pid] = new
        self.occupancy = sum(1 for pid in world if self.state.get(pid))
        self.max_occupancy = max(self.max_occupancy, self.occupancy)
