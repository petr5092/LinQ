"""Правила нарушений — плагины.

Чтобы добавить новый тип нарушения, напишите класс с @register и методом
evaluate(ctx) -> list[Candidate]. Больше нигде ничего менять не нужно:
подтверждение по времени, подавление повторов, журнал и интерфейс подхватят его сами.
"""
from dataclasses import dataclass, field

from . import config

RULES = {}


def register(cls):
    RULES[cls.type] = cls
    return cls


@dataclass
class Candidate:
    track_id: int
    type: str
    box: tuple
    zone: str = None


@dataclass
class Context:
    t: float
    shape: tuple                 # (h, w)
    tracks: list
    dets: list                   # все детекции кадра
    zones: list = field(default_factory=list)   # [{"name", "poly": [(x, y), ...]}] в пикселях


class Rule:
    type = "base"
    label = ""
    severity = "medium"          # critical | high | medium | low
    DEFAULTS = {}

    def __init__(self, **overrides):
        self.p = {**self.DEFAULTS, **config.RULE_PARAMS.get(self.type, {}), **overrides}
        self.confirm_s = self.p.get("confirm_s", 2.0)

    def evaluate(self, ctx):
        raise NotImplementedError


def center(b):
    return (b[0] + b[2]) / 2, (b[1] + b[3]) / 2


def inside(pt, box):
    return box[0] <= pt[0] <= box[2] and box[1] <= pt[1] <= box[3]


def point_in_poly(pt, poly):
    x, y, ok = pt[0], pt[1], False
    for i in range(len(poly)):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % len(poly)]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            ok = not ok
    return ok


def is_lying(tr, aspect):
    w, h = tr.size
    return h > 0 and w / h > aspect


def _still(tr, t, window_s):
    pts = [p for p in tr.hist if t - p[0] <= window_s]
    if not pts or t - pts[0][0] < window_s * 0.8:
        return False
    size = max(pts[-1][3], pts[-1][4])
    span = max(max(p[1] for p in pts) - min(p[1] for p in pts),
               max(p[2] for p in pts) - min(p[2] for p in pts))
    return span < 0.35 * size


@register
class FallRule(Rule):
    type, label, severity = "fall", "Падение или неподвижность", "critical"

    def evaluate(self, ctx):
        return [Candidate(tr.id, self.type, tr.box) for tr in ctx.tracks
                if is_lying(tr, self.p["aspect"]) and _still(tr, ctx.t, self.p["still_s"])]


@register
class RestrictedZoneRule(Rule):
    type, label, severity = "restricted_zone", "Вход в опасную зону", "high"

    def evaluate(self, ctx):
        out = []
        for tr in ctx.tracks:
            foot = ((tr.box[0] + tr.box[2]) / 2, tr.box[3])
            for z in ctx.zones:
                if point_in_poly(foot, z["poly"]):
                    out.append(Candidate(tr.id, self.type, tr.box, z["name"]))
        return out


class _PPERule(Rule):
    pos_cls = neg_cls = ""
    min_h_frac = 0.15            # слишком мелких людей не оцениваем: средства защиты не видны

    def region(self, b):
        raise NotImplementedError

    def evaluate(self, ctx):
        out = []
        for tr in ctx.tracks:
            w, h = tr.size
            if h < self.min_h_frac * ctx.shape[0] or is_lying(tr, 1.0):
                continue
            reg = self.region(tr.box)
            near = [d for d in ctx.dets if inside(center(d.box), reg)]
            if self.p.get("mode") == "absence":
                bad = not any(d.cls == self.pos_cls for d in near)
            else:
                bad = any(d.cls == self.neg_cls for d in near)
            if bad:
                out.append(Candidate(tr.id, self.type, tr.box))
        return out


@register
class NoHelmetRule(_PPERule):
    type, label, severity = "no_helmet", "Нет каски", "medium"
    pos_cls, neg_cls = "helmet", "no_helmet"

    def region(self, b):
        w, h = b[2] - b[0], b[3] - b[1]
        return b[0] - 0.1 * w, b[1] - 0.1 * h, b[2] + 0.1 * w, b[1] + 0.3 * h


@register
class NoVestRule(_PPERule):
    type, label, severity = "no_vest", "Нет сигнального жилета", "medium"
    pos_cls, neg_cls = "vest", "no_vest"

    def region(self, b):
        w, h = b[2] - b[0], b[3] - b[1]
        return b[0] - 0.1 * w, b[1] + 0.2 * h, b[2] + 0.1 * w, b[1] + 0.75 * h


@register
class PhoneRule(Rule):
    type, label, severity = "phone", "Телефон при работе", "low"

    def evaluate(self, ctx):
        out = []
        for tr in ctx.tracks:
            b = tr.box
            w, h = tr.size
            reg = (b[0] - 0.15 * w, b[1], b[2] + 0.15 * w, b[1] + 0.75 * h)
            if any(d.cls == "phone" and inside(center(d.box), reg) for d in ctx.dets):
                out.append(Candidate(tr.id, self.type, tr.box))
        return out


def build_rules():
    return [cls() for cls in RULES.values()]
