"""Mide el tiempo medio por etapa y los FPS reales. Uso: python benchmark.py [--source ..] [--n 100]"""
import argparse
import time

import config
from capture import Capture
from counter import LineCounter
from detector import PersonTracker
from mapper import FloorMapper

ap = argparse.ArgumentParser()
ap.add_argument("--source", default=config.SOURCE)
ap.add_argument("--n", type=int, default=100)
a = ap.parse_args()

cap, trk = Capture(a.source), PersonTracker()
cnt, mp = LineCounter(config.FRAME_W, config.FRAME_H), FloorMapper()
t = {"captura": 0.0, "deteccion+tracking": 0.0, "conteo+mapa": 0.0}
for _ in range(5):                       # calentamiento
    trk.update(cap.read())
done = 0
t0 = time.time()
for _ in range(a.n):
    s = time.time(); f = cap.read(); t["captura"] += time.time() - s
    if f is None:
        break
    s = time.time(); p = trk.update(f); t["deteccion+tracking"] += time.time() - s
    s = time.time(); cnt.update(p); mp.render({}, {}, len(p)); t["conteo+mapa"] += time.time() - s
    done += 1
total = time.time() - t0
print(f"modelo={config.MODEL} imgsz={config.IMGSZ} frames={done}")
for k, v in t.items():
    print(f"  {k:20s} {v / done * 1000:7.1f} ms")
print(f"  FPS reales: {done / total:.1f}")
cap.release()
