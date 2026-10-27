"""Orquestación: captura -> detección+tracking -> conteo/mapa/movimiento -> dashboard."""
import argparse
import csv
import math
import os
import time

import cv2

import config
from capture import Capture
from counter import LineCounter, ZoneCounter
from detector import PersonTracker
from mapper import FloorMapper
from motion import MotionEstimator
from server import publish, set_stats, shared, start_server


def draw(frame, people, counter, vel_px, occupancy, alert, world, mapper):
    mobile = config.CAMERA_MODE != "fixed"
    if not mobile:
        cv2.line(frame, tuple(map(int, counter.p1)), tuple(map(int, counter.p2)), (0, 255, 255), 2)
    for p in people:
        x1, y1, x2, y2 = map(int, p.box)
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
        label = f"ID {p.id}"
        w = world.get(p.id)
        if w:
            label += f"  {'<' if mapper.is_partial(p) else ''}{math.hypot(*w):.1f} m"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
        ty = y1 if y1 - th - 8 >= 0 else y1 + th + 8   # etiqueta dentro de la caja si toca el borde superior
        cv2.rectangle(frame, (x1, ty - th - 8), (x1 + tw + 10, ty), (0, 160, 60), -1)
        cv2.putText(frame, label, (x1 + 5, ty - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)
        if p.id in vel_px:
            vx, vy = vel_px[p.id]
            cx, cy = map(int, p.center)
            n = (vx * vx + vy * vy) ** 0.5
            if n > 15:  # px/s: ignora jitter de personas quietas
                k = min(0.5, 70.0 / n)  # ~0.5 s de movimiento, máx 70 px
                cv2.arrowedLine(frame, (cx, cy), (int(cx + vx * k), int(cy + vy * k)),
                                (0, 0, 255), 3, tipLength=0.3)
    if mobile:
        text = f"EN ZONA {occupancy}   IN {counter.n_in}   OUT {counter.n_out}"
    else:
        text = f"IN {counter.n_in}   OUT {counter.n_out}   OCUP {occupancy}"
    h = frame.shape[0]
    bar = frame.copy()
    cv2.rectangle(bar, (0, h - 34), (frame.shape[1], h), (20, 20, 20), -1)
    cv2.addWeighted(bar, 0.65, frame, 0.35, 0, frame)
    cv2.putText(frame, text, (12, h - 11), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                (80, 80, 255) if alert else (255, 255, 255), 2)


IDLE_S = float(os.environ.get("PC_IDLE_S", 600))        # sin espectadores -> descanso
THERMAL_MAX = float(os.environ.get("PC_THERMAL_MAX", 0))  # 0 = desactivado (se activa en la Pi)
THERMAL_RESUME = THERMAL_MAX - 10


def cpu_temp():
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            return round(int(f.read()) / 1000.0, 1)
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default=config.SOURCE)
    ap.add_argument("--no-server", action="store_true")
    ap.add_argument("--save", help="guarda el video anotado (mp4)")
    ap.add_argument("--show", action="store_true", help="ventana local de OpenCV")
    args = ap.parse_args()

    os.makedirs(config.LOG_DIR, exist_ok=True)
    log_path = os.path.join(config.LOG_DIR, time.strftime("eventos_%Y%m%d_%H%M%S.csv"))
    log = open(log_path, "w", newline="")
    writer = csv.writer(log)
    writer.writerow(["timestamp", "evento", "id", "ocupacion_o_distancia_m"])

    cap = Capture(args.source)
    tracker = PersonTracker()
    mobile = config.CAMERA_MODE != "fixed"
    counter = ZoneCounter() if mobile else LineCounter(config.FRAME_W, config.FRAME_H)
    smooth = {}   # id -> (x, y) suavizado: la distancia por altura de caja es ruidosa
    mapper = FloorMapper()
    motion_px = MotionEstimator()
    motion_w = MotionEstimator()

    if not args.no_server:
        start_server()
        print(f"Dashboard: http://<ip-de-esta-maquina>:{config.PORT}")

    writer_v = None
    fps, t_prev, n = 0.0, time.time(), 0
    people, vel_px, world, vel_w = [], {}, {}, {}
    cooling, cap_open, last_t, temp = False, True, 0.0, None
    frames_seen, confirmed = {}, set()   # personas únicas (ID visto >= 5 frames)
    try:
        while True:
            # --- descanso: pausa manual, nadie mirando o Pi caliente (solo cámaras en vivo) ---
            if time.time() - last_t > 3:
                last_t = time.time()
                temp = cpu_temp()
                if THERMAL_MAX and temp is not None:
                    cooling = temp >= THERMAL_MAX or (cooling and temp > THERMAL_RESUME)
            reason = None
            if cap.kind != "file":
                if shared.manual_pause:
                    reason = "pausa manual"
                elif time.time() - shared.last_seen > IDLE_S:
                    reason = f"nadie mira el dashboard hace {int(IDLE_S // 60)} min"
                elif cooling:
                    reason = "enfriando la Pi"
            if reason:
                if cap_open:
                    cap.release()
                    cap_open = False
                    people, vel_px, world, vel_w = [], {}, {}, {}
                set_stats({"visible": 0, "in": counter.n_in, "out": counter.n_out,
                           "occupancy": counter.occupancy, "max": counter.max_occupancy,
                           "fps": 0, "alert": False, "mode": config.CAMERA_MODE, "unique": len(confirmed),
                           "zone": config.ZONE_RADIUS_M, "capacity": config.MAX_CAPACITY, "people": [],
                           "nearest": 0, "paused": True, "reason": reason, "temp": temp})
                time.sleep(0.5)
                continue
            if not cap_open:
                try:
                    cap = Capture(args.source)
                    cap_open = True
                    t_prev = time.time()
                except Exception as e:
                    print("No se pudo reabrir la cámara:", e)
                    time.sleep(2)
                    continue
            try:
                frame = cap.read()
            except Exception:
                frame = None
            if frame is None:
                if cap.kind == "file":
                    break  # fin del video de prueba
                print("Cámara perdida, reconectando...")
                if not cap.reconnect():
                    break
                continue

            n += 1
            if n % 15 == 0:
                mapper.reload_if_changed()
            if shared.reset:
                shared.reset = False
                counter.n_in = counter.n_out = counter.occupancy = counter.max_occupancy = 0
                frames_seen.clear(); confirmed.clear()
            if n % config.FRAME_SKIP == 0:
                people = tracker.update(frame)
                shared.boxes = [{"id": p.id, "h": round(p.box[3] - p.box[1], 1),
                                 "partial": bool(mapper.is_partial(p))} for p in people]
                now = time.time()
                vel_px = motion_px.update({p.id: p.center for p in people}, now)
                world = {}
                for p in people:
                    w = mapper.locate(p)
                    if w:
                        world[p.id] = w
                    frames_seen[p.id] = frames_seen.get(p.id, 0) + 1
                    if frames_seen[p.id] >= 5 and p.id not in confirmed:
                        confirmed.add(p.id)
                        writer.writerow([time.strftime("%H:%M:%S"), "NUEVA", p.id,
                                         round(math.hypot(*w), 2) if w else ""])
                        log.flush()
                for pid in list(smooth):
                    if pid not in world:
                        smooth.pop(pid)
                for pid, (x, y) in world.items():
                    ox, oy = smooth.get(pid, (x, y))
                    smooth[pid] = (0.6 * ox + 0.4 * x, 0.6 * oy + 0.4 * y)
                    world[pid] = smooth[pid]
                counter.update(people, world)
                vel_w = motion_w.update(world, now)
                for kind, pid in counter.events:
                    writer.writerow([time.strftime("%H:%M:%S"), kind, pid, counter.occupancy])
                    log.flush()

            raw = frame.copy()
            alert = counter.occupancy > config.MAX_CAPACITY
            draw(frame, people, counter, vel_px, counter.occupancy, alert, world, mapper)

            t = time.time()
            fps = 0.9 * fps + 0.1 * (1.0 / max(t - t_prev, 1e-6)) if fps else 1.0 / max(t - t_prev, 1e-6)
            t_prev = t
            map_img = mapper.render(world, vel_w, len(people))
            publish(frame, map_img, {
                "visible": len(people), "in": counter.n_in, "out": counter.n_out,
                "occupancy": counter.occupancy, "max": counter.max_occupancy,
                "fps": round(fps, 1), "alert": alert, "mode": config.CAMERA_MODE,
                "paused": False, "temp": temp,
                "unique": len(confirmed), "zone": config.ZONE_RADIUS_M, "capacity": config.MAX_CAPACITY,
                "people": [{"id": p.id, "d": round(math.hypot(*world[p.id]), 2), "partial": bool(mapper.is_partial(p))}
                           for p in people if p.id in world],
                "nearest": round(min((math.hypot(*w) for w in world.values()), default=0), 2),
            }, raw=raw)
            if args.save:
                if writer_v is None:
                    writer_v = cv2.VideoWriter(args.save, cv2.VideoWriter_fourcc(*"mp4v"), 15,
                                               (config.FRAME_W, config.FRAME_H))
                writer_v.write(frame)
            if args.show:
                cv2.imshow("conteo", frame)
                cv2.imshow("mapa", map_img)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
    except KeyboardInterrupt:
        pass
    finally:
        cap.release()
        if writer_v is not None:
            writer_v.release()
        log.close()
        print(f"IN={counter.n_in} OUT={counter.n_out} max={counter.max_occupancy}  log: {log_path}")


if __name__ == "__main__":
    main()
