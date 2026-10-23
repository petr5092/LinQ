"""Лёгкий IoU-трекер: даёт стабильный ID человеку между кадрами."""
from collections import deque
from math import hypot


def iou(a, b):
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    ua = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / ua if ua > 0 else 0.0


class Track:
    def __init__(self, tid, box, t):
        self.id = tid
        self.box = box
        self.hits = 0
        self.last_t = t
        self.seen = -1
        self.hist = deque(maxlen=300)   # (t, cx, cy, w, h)
        self.push(box, t)

    def push(self, box, t):
        self.box, self.last_t = box, t
        w, h = box[2] - box[0], box[3] - box[1]
        self.hist.append((t, box[0] + w / 2, box[1] + h / 2, w, h))

    @property
    def size(self):
        return self.box[2] - self.box[0], self.box[3] - self.box[1]


class Tracker:
    def __init__(self, iou_thr=0.25, max_age_s=1.5):
        self.iou_thr, self.max_age = iou_thr, max_age_s
        self.tracks, self.next_id, self.frame_no = [], 1, 0

    def update(self, dets, t):
        self.frame_no += 1
        pairs = []
        for ti, tr in enumerate(self.tracks):
            for di, d in enumerate(dets):
                s = iou(tr.box, d.box)
                if s < self.iou_thr:
                    # быстрое изменение формы (падение): сопоставляем по близости центров
                    cx1, cy1 = (tr.box[0] + tr.box[2]) / 2, (tr.box[1] + tr.box[3]) / 2
                    cx2, cy2 = (d.box[0] + d.box[2]) / 2, (d.box[1] + d.box[3]) / 2
                    near = hypot(cx1 - cx2, cy1 - cy2) < 0.5 * max(tr.size[1], d.box[3] - d.box[1])
                    s = 0.1 if near else 0.0
                if s > 0:
                    pairs.append((s, ti, di))
        used_t, used_d = set(), set()
        for s, ti, di in sorted(pairs, reverse=True):
            if ti in used_t or di in used_d:
                continue
            used_t.add(ti)
            used_d.add(di)
            tr = self.tracks[ti]
            tr.push(dets[di].box, t)
            tr.hits += 1
            tr.seen = self.frame_no
        for di, d in enumerate(dets):
            if di not in used_d:
                tr = Track(self.next_id, d.box, t)
                tr.seen = self.frame_no
                self.next_id += 1
                self.tracks.append(tr)
        self.tracks = [tr for tr in self.tracks if t - tr.last_t <= self.max_age]
        return [tr for tr in self.tracks if tr.seen == self.frame_no]
