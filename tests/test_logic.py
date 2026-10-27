"""Pruebas de la lógica sin cámara ni YOLO. Ejecutar:  python tests/test_logic.py"""
import json
import os
import sys
from dataclasses import dataclass

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import config
from counter import LineCounter


@dataclass
class P:
    id: int
    foot: tuple


def walk(c, pid, ys, x=300):
    for y in ys:
        c.update([P(pid, (x, y))])


def test_cruce_ida_y_vuelta():
    c = LineCounter(640, 480)
    walk(c, 1, range(100, 400, 25))
    assert (c.n_in, c.n_out, c.occupancy) == (1, 0, 1)
    walk(c, 1, range(400, 100, -25))
    assert (c.n_in, c.n_out, c.occupancy) == (1, 1, 0)


def test_ruido_sobre_la_linea_no_cuenta():
    c = LineCounter(640, 480)
    walk(c, 2, [250, 258, 270, 262, 268, 255, 266] * 4)
    assert (c.n_in, c.n_out) == (0, 0)


def test_dos_personas_sentidos_opuestos():
    c = LineCounter(640, 480)
    for a, b in zip(range(100, 420, 20), range(420, 100, -20)):
        c.update([P(1, (200, a)), P(2, (400, b))])
    assert (c.n_in, c.n_out) == (1, 1)


def test_ocupacion_nunca_negativa():
    c = LineCounter(640, 480)
    walk(c, 3, range(400, 100, -25))
    assert c.n_out == 1 and c.occupancy == 0


def test_invertir_direccion():
    config.INVERT_DIRECTION = True
    c = LineCounter(640, 480)
    walk(c, 1, range(100, 400, 25))
    config.INVERT_DIRECTION = False
    assert (c.n_in, c.n_out) == (0, 1)


def test_homografia_exacta_en_puntos_de_calibracion():
    import mapper
    img = [[200, 300], [440, 300], [500, 450], [140, 450]]
    world = [[-1, 4], [1, 4], [1, 2], [-1, 2]]
    old = config.CALIB_FILE
    config.CALIB_FILE = "/tmp/_calib_test.json"
    json.dump({"image_pts": img, "world_pts": world}, open(config.CALIB_FILE, "w"))
    m = mapper.FloorMapper()
    for p, w in zip(img, world):
        x, y = m.to_world(tuple(p))
        assert abs(x - w[0]) < 1e-3 and abs(y - w[1]) < 1e-3
    s = m.virtual_scan([(0, 3)])
    assert len(s) == config.SCAN_BINS and min(s) == 3.0
    os.remove(config.CALIB_FILE)
    config.CALIB_FILE = old


def test_zona_entra_y_sale():
    from counter import ZoneCounter
    z = ZoneCounter()
    for d in [7, 6.5, 6, 5.5, 5, 4.6, 4.2, 3.5, 3, 2.5]:      # se acerca: cruza el radio de 4 m
        z.update([], {1: (0, d)})
    assert (z.n_in, z.n_out, z.occupancy) == (1, 0, 1)
    for d in [3, 3.5, 4.2, 4.6, 5, 6]:                         # se aleja
        z.update([], {1: (0, d)})
    assert (z.n_in, z.n_out, z.occupancy) == (1, 1, 0)


def test_zona_ruido_en_el_borde_no_cuenta():
    from counter import ZoneCounter
    z = ZoneCounter()
    for d in [5, 5, 5, 5] + [3.9, 4.1, 3.8, 4.2, 4.0] * 6:    # oscila dentro de la histéresis
        z.update([], {1: (0, d)})
    assert (z.n_in, z.n_out) == (0, 0)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("OK ", name)
    print("TODAS LAS PRUEBAS PASARON")
