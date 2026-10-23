"""Превращает «условие выполняется в этом кадре» в «одно подтверждённое оповещение».

1. Нарушение подтверждается, только если длится confirm_s секунд подряд
   (случайный кадр тревогу не вызывает).
2. На один (человек, тип, зона) приходит одно оповещение, пока нарушение не прекратится
   больше чем на gap_s.
3. Если трек потерялся из-за перекрытия и появился снова с новым ID на том же месте,
   повтор подавляется (защита от дублей).
"""
from . import config
from .rules import build_rules


class Engine:
    def __init__(self, rules=None, **cfg):
        c = {**config.ENGINE, **cfg}
        self.gap_s, self.dedup_s, self.dedup_dist = c["gap_s"], c["dedup_s"], c["dedup_dist"]
        self.rules = {r.type: r for r in (rules or build_rules())}
        self.since, self.last, self.fired, self.recent = {}, {}, set(), []
        self.active_tracks = set()

    def process(self, ctx):
        t, seen, out = ctx.t, set(), []
        self.active_tracks = set()
        for rule in self.rules.values():
            for c in rule.evaluate(ctx):
                key = (c.track_id, c.type, c.zone)
                seen.add(key)
                self.active_tracks.add(c.track_id)
                self.since.setdefault(key, t)
                self.last[key] = t
                if key not in self.fired and t - self.since[key] >= rule.confirm_s:
                    self.fired.add(key)
                    if self._is_new(c, ctx):
                        out.append((c, rule))
        for key in [k for k in self.last if k not in seen and t - self.last[k] > self.gap_s]:
            self.since.pop(key, None)
            self.last.pop(key)
            self.fired.discard(key)
        return out

    def _is_new(self, c, ctx):
        t, W = ctx.t, ctx.shape[1]
        cx = (c.box[0] + c.box[2]) / 2
        alive = {tr.id for tr in ctx.tracks}
        self.recent = [r for r in self.recent if t - r["t"] <= self.dedup_s]
        for r in self.recent:
            if (r["type"], r["zone"]) == (c.type, c.zone) and r["tid"] not in alive \
                    and abs(r["cx"] - cx) < self.dedup_dist * W:
                r.update(t=t, tid=c.track_id, cx=cx)    # то же нарушение, сменился ID
                return False
        self.recent.append({"type": c.type, "zone": c.zone, "tid": c.track_id, "cx": cx, "t": t})
        return True
