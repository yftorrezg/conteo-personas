"""Dashboard web: video anotado, mapa cenital, contadores y gráfica."""
import json
import os
import threading
import time

import cv2
from flask import Flask, Response, jsonify, request

import config

app = Flask(__name__)


class Shared:
    lock = threading.Lock()
    video_jpg = b""
    raw_jpg = b""
    raw_t = 0.0
    reset = False
    last_seen = time.time()   # última vez que alguien miró el dashboard
    manual_pause = False
    boxes = []   # [{id, h (px), partial}] del último frame, para calibrar la distancia
    map_jpg = b""
    stats = {}
    history = []  # (t, ocupación)


shared = Shared()


def publish(video, map_img, stats, raw=None):
    ok1, v = cv2.imencode(".jpg", video, [cv2.IMWRITE_JPEG_QUALITY, 65])
    ok2, m = cv2.imencode(".jpg", map_img, [cv2.IMWRITE_JPEG_QUALITY, 70])
    with shared.lock:
        if ok1:
            shared.video_jpg = v.tobytes()
        if ok2:
            shared.map_jpg = m.tobytes()
        shared.stats = stats
        if raw is not None and time.time() - shared.raw_t > 1.0:
            ok3, r = cv2.imencode(".jpg", raw, [cv2.IMWRITE_JPEG_QUALITY, 90])
            if ok3:
                shared.raw_jpg, shared.raw_t = r.tobytes(), time.time()
        h = shared.history
        if not h or time.time() - h[-1][0] >= 1.0:
            h.append((time.time(), stats.get("occupancy", 0)))
            del h[:-300]


def _mjpeg(attr):
    while True:
        with shared.lock:
            jpg = getattr(shared, attr)
        if jpg:
            yield b"--f\r\nContent-Type: image/jpeg\r\n\r\n" + jpg + b"\r\n"
        time.sleep(0.07)


@app.route("/video")
def video():
    return Response(_mjpeg("video_jpg"), mimetype="multipart/x-mixed-replace; boundary=f")


@app.route("/map.jpg")
def map_jpg():
    with shared.lock:
        return Response(shared.map_jpg, mimetype="image/jpeg", headers={"Cache-Control": "no-store"})


@app.route("/map")
def map_view():
    return Response(_mjpeg("map_jpg"), mimetype="multipart/x-mixed-replace; boundary=f")


@app.route("/stats")
def stats():
    with shared.lock:
        out = dict(shared.stats)
        out["history"] = [[round(t), o] for t, o in shared.history[-120:]]
    return jsonify(out)


@app.before_request
def _touch():
    if request.path in ("/", "/stats", "/snapshot.jpg", "/calibrate"):
        shared.last_seen = time.time()


@app.route("/pause", methods=["POST"])
def pause():
    shared.manual_pause = True
    return jsonify(ok=True)


@app.route("/resume", methods=["POST"])
def resume():
    shared.manual_pause = False
    shared.last_seen = time.time()
    return jsonify(ok=True)


def set_stats(stats):
    with shared.lock:
        shared.stats = stats


@app.route("/snapshot.jpg")
def snapshot():
    with shared.lock:
        return Response(shared.raw_jpg, mimetype="image/jpeg")


@app.route("/reset", methods=["POST"])
def reset():
    with shared.lock:
        shared.reset = True
    return jsonify(ok=True)


@app.route("/calibration", methods=["POST"])
def save_calibration():
    d = request.get_json(force=True)
    img, world = d["image_pts"], d["world_pts"]
    if len(img) != 4 or len(world) != 4:
        return jsonify(ok=False, error="Se necesitan 4 puntos"), 400
    with open(config.CALIB_FILE, "w") as f:
        json.dump({"image_pts": img, "world_pts": world}, f, indent=2)
    return jsonify(ok=True)


@app.route("/boxes")
def boxes():
    k = config.load_dist_k()
    return jsonify(boxes=shared.boxes, k=k or config.K_DEFAULT, calibrated=k is not None)


@app.route("/calib_dist", methods=["POST", "DELETE"])
def calib_dist():
    """POST {points:[[dist_m, alto_caja_px], ...]} -> ajusta K (h = K/d) por mínimos cuadrados."""
    if request.method == "DELETE":
        if os.path.exists(config.DIST_CALIB_FILE):
            os.remove(config.DIST_CALIB_FILE)
        return jsonify(ok=True, k=config.K_DEFAULT)
    pts = request.get_json(force=True).get("points", [])
    pts = [(float(d), float(h)) for d, h in pts if float(d) > 0 and float(h) > 0]
    if not pts:
        return jsonify(ok=False, error="Sin puntos válidos"), 400
    inv = [1.0 / d for d, _ in pts]
    k = sum(h * i for (_, h), i in zip(pts, inv)) / sum(i * i for i in inv)
    with open(config.DIST_CALIB_FILE, "w") as f:
        json.dump({"k": k, "points": pts}, f, indent=2)
    return jsonify(ok=True, k=k)


CALIB_PAGE = """<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Calibración</title>
<style>body{margin:0;background:#0f1115;color:#e8e8e8;font-family:system-ui,sans-serif;padding:12px}
canvas{max-width:100%;border-radius:6px;cursor:crosshair}input{width:70px;background:#171a21;color:#fff;border:1px solid #444;border-radius:4px;padding:4px}
button{background:#2563eb;color:#fff;border:0;border-radius:6px;padding:8px 14px;margin:4px 4px 4px 0;font-size:15px}
.r{margin:4px 0}</style></head><body>
<h2>Distancia (modo móvil)</h2>
<p>Una persona <b>de pie y de cuerpo completo</b> (con esta cámara, desde ~2.5 m) se para a una distancia medida con cinta
(ej. 3, 4 y 5 m) → escribe la distancia → <b>Medir</b> (3 s, que no se mueva) → repite en otras distancias → <b>Guardar K</b>.</p>
<div id="dist"><input id="dd" value="3"> m <button onclick="medir()">Medir</button>
<button onclick="saveK()">Guardar K</button><button onclick="clrK()">Borrar medidas</button>
<button onclick="resetK()" style="background:#7a1c1c">Volver a teórica</button>
<div id="dmsg"></div><div id="dpts"></div></div>
<h2>Calibración del piso (4 puntos, solo modo fijo)</h2>
<p>1) Haz clic en 4 puntos marcados en el piso. 2) Escribe sus coordenadas en metros respecto a la cámara
(x: derecha +, izquierda −; y: hacia adelante). 3) Guardar.</p>
<canvas id="c" width="640" height="480"></canvas>
<div id="rows"></div>
<button onclick="refresh()">Actualizar foto</button><button onclick="clr()">Borrar puntos</button><button onclick="save()">Guardar</button>
<span id="msg"></span>
<script>
const c=document.getElementById('c'),g=c.getContext('2d');let pts=[],img=new Image();
img.onload=draw;function refresh(){img.src='/snapshot.jpg?'+Date.now()}refresh();
function draw(){g.drawImage(img,0,0,640,480);pts.forEach((p,i)=>{g.fillStyle='#0f0';g.beginPath();g.arc(p[0],p[1],6,0,7);g.fill();g.font='20px sans-serif';g.fillText(i+1,p[0]+8,p[1]-8)})}
c.onclick=e=>{if(pts.length>=4)return;const r=c.getBoundingClientRect();pts.push([Math.round((e.clientX-r.left)*640/r.width),Math.round((e.clientY-r.top)*480/r.height)]);rows();draw()}
function rows(){document.getElementById('rows').innerHTML=pts.map((p,i)=>`<div class="r">Punto ${i+1} (px ${p[0]},${p[1]}) → x <input id="x${i}" value="0"> m &nbsp; y <input id="y${i}" value="0"> m</div>`).join('')}
function clr(){pts=[];rows();draw()}
async function save(){if(pts.length!=4){msg.textContent=' Faltan puntos';return}
 const w=pts.map((_,i)=>[parseFloat(document.getElementById('x'+i).value),parseFloat(document.getElementById('y'+i).value)]);
 const r=await fetch('/calibration',{method:'POST',body:JSON.stringify({image_pts:pts,world_pts:w})});
 msg.textContent=r.ok?' ✔ Guardado (el mapa se actualiza solo)':' Error'}
const msg=document.getElementById('msg');
let dp=[],K=0;const dmsg=document.getElementById('dmsg');
const med=a=>{a=[...a].sort((x,y)=>x-y);return a[a.length>>1]};
async function medir(){const d=parseFloat(document.getElementById('dd').value);if(!(d>0)){dmsg.textContent='Distancia inválida';return}
 const hs=[];let part=0;dmsg.textContent='Midiendo...';
 for(let i=0;i<20;i++){const r=await (await fetch('/boxes')).json();K=r.k;
  const b=r.boxes.filter(x=>!x.partial).sort((a,b)=>b.h-a.h)[0];if(b)hs.push(b.h);else if(r.boxes.length)part++;
  await new Promise(r=>setTimeout(r,150))}
 if(hs.length<8){dmsg.textContent=part?'Persona cortada por el borde: aléjate hasta verla de cuerpo completo.':'No se detecta a nadie (¿en pausa?).';return}
 dp.push([d,med(hs)]);dmsg.textContent='Medida lista ('+hs.length+' muestras)';showK()}
function showK(){document.getElementById('dpts').innerHTML=dp.map(([d,h])=>`<div class="r">${d} m → caja ${h.toFixed(0)} px → K=${(d*h).toFixed(0)} (con K actual: ${(K/h).toFixed(2)} m)</div>`).join('')+'<div class="r">K actual: '+K.toFixed(0)+'</div>'}
function clrK(){dp=[];showK()}
async function saveK(){if(!dp.length){dmsg.textContent='Primero mide';return}
 const r=await (await fetch('/calib_dist',{method:'POST',body:JSON.stringify({points:dp})})).json();
 K=r.k;dmsg.textContent=r.ok?' ✔ K='+K.toFixed(0)+' guardado (se aplica solo)':' Error';showK()}
async function resetK(){const r=await (await fetch('/calib_dist',{method:'DELETE'})).json();K=r.k;dp=[];dmsg.textContent='Vuelto a K teórica';showK()}
fetch('/boxes').then(r=>r.json()).then(r=>{K=r.k;showK()});
</script></body></html>"""


@app.route("/calibrate")
def calibrate_page():
    return CALIB_PAGE


with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboard.html"), encoding="utf-8") as _f:
    PAGE = _f.read()


@app.route("/")
def index():
    return PAGE


def start_server():
    t = threading.Thread(
        target=lambda: app.run(host=config.HOST, port=config.PORT, threaded=True, use_reloader=False),
        daemon=True,
    )
    t.start()
