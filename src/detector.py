"""Detección de personas (YOLO preentrenado en COCO) + tracking ByteTrack."""
from dataclasses import dataclass

from ultralytics import YOLO

import config


@dataclass
class Person:
    id: int
    box: tuple      # x1, y1, x2, y2 en px
    conf: float

    @property
    def foot(self):
        """Punto de contacto con el piso (centro-inferior de la caja)."""
        x1, y1, x2, y2 = self.box
        return ((x1 + x2) / 2.0, y2)

    @property
    def center(self):
        x1, y1, x2, y2 = self.box
        return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)


class PersonTracker:
    def __init__(self):
        self.model = YOLO(config.MODEL, task="detect")

    def update(self, frame):
        """Devuelve lista de Person con ID persistente para este frame."""
        res = self.model.track(
            frame,
            persist=True,
            tracker="bytetrack.yaml",
            classes=[0],              # 0 = person en COCO
            conf=config.CONF,
            imgsz=config.IMGSZ,
            verbose=False,
        )[0]
        people = []
        if res.boxes is None or res.boxes.id is None:
            return people
        for xyxy, tid, c in zip(
            res.boxes.xyxy.cpu().numpy(),
            res.boxes.id.cpu().numpy().astype(int),
            res.boxes.conf.cpu().numpy(),
        ):
            x1, y1, x2, y2 = (float(v) for v in xyxy)
            if (y2 - y1) < config.MIN_BOX_H:
                continue
            people.append(Person(int(tid), (x1, y1, x2, y2), float(c)))
        return people
