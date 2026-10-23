import os, sys, tempfile, unittest
os.environ["LINQ_DATA"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from app import sources, detector, store, hub, pipeline
from app.models import Detection
from app.rules import point_in_poly, Context
from app.engine import Engine
from app.tracker import Tracker


def D(cls, box): return Detection(cls, .9, box)


class TrackerTest(unittest.TestCase):
    def test_keeps_id_while_moving(self):
        tr, ids = Tracker(), set()
        for i in range(20):
            ids |= {t.id for t in tr.update([D("person", (10 + 3 * i, 10, 50 + 3 * i, 120))], i * .1)}
        self.assertEqual(len(ids), 1)

    def test_keeps_id_when_falling(self):
        tr = Tracker()
        a = tr.update([D("person", (100, 200, 136, 310))], 0)[0].id
        b = tr.update([D("person", (60, 270, 170, 310))], .1)[0].id
        self.assertEqual(a, b)


class GeometryTest(unittest.TestCase):
    def test_polygon(self):
        sq = [(0, 0), (10, 0), (10, 10), (0, 10)]
        self.assertTrue(point_in_poly((5, 5), sq))
        self.assertFalse(point_in_poly((15, 5), sq))


class EngineTest(unittest.TestCase):
    def run_engine(self, frames, fps=10):
        eng, out = Engine(), []
        tracker = Tracker()
        for i, dets in enumerate(frames):
            t = i / fps
            tracks = tracker.update([d for d in dets if d.cls == "person"], t)
            out += eng.process(Context(t, (360, 640), tracks, dets, []))
        return out

    def test_short_violation_ignored(self):
        bad = [D("person", (100, 100, 136, 210)), D("no_helmet", (105, 100, 131, 126))]
        ok = [D("person", (100, 100, 136, 210))]
        self.assertEqual(self.run_engine([bad] * 8 + [ok] * 20), [])     # 0.8 с < 2 с

    def test_one_alert_for_long_violation(self):
        bad = [D("person", (100, 100, 136, 210)), D("no_helmet", (105, 100, 131, 126))]
        self.assertEqual(len(self.run_engine([bad] * 200)), 1)           # 20 с — одно оповещение

    def test_flicker_does_not_duplicate(self):
        bad = [D("person", (100, 100, 136, 210)), D("no_helmet", (105, 100, 131, 126))]
        ok = [D("person", (100, 100, 136, 210))]
        frames = ([bad] * 15 + [ok] * 5) * 6                              # пропадает на 0,5 с
        self.assertEqual(len(self.run_engine(frames)), 1)

    def test_fall_detected_standing_not(self):
        stand = [D("person", (100, 100, 136, 210))]
        lying = [D("person", (60, 170, 170, 210))]
        self.assertEqual(self.run_engine([stand] * 100), [])
        ev = self.run_engine([stand] * 10 + [lying] * 60)
        self.assertEqual([c.type for c, _ in ev], ["fall"])

    def test_absence_mode(self):
        from app.rules import NoHelmetRule
        eng = Engine(rules=[NoHelmetRule(mode="absence")])
        tracker, out = Tracker(), []
        for i in range(40):
            dets = [D("person", (100, 100, 136, 210))]
            out += eng.process(Context(i / 10, (360, 640), tracker.update(dets, i / 10), dets, []))
        self.assertEqual(len(out), 1)


class PostprocessTest(unittest.TestCase):
    def test_decode_both_layouts(self):
        names = ["person", "helmet"]
        # (1, 4+nc, N): один человек в центре letterbox-кадра 640x640
        out = np.zeros((1, 6, 50), np.float32)
        out[0, :, 0] = [320, 320, 100, 200, .9, .1]
        out[0, :, 1] = [322, 321, 102, 198, .8, .1]       # дубль -> уберёт NMS
        for o in (out, out.transpose(0, 2, 1)):
            dets = detector.decode_yolo(o, names, 1.0, 0, 0, (640, 640, 3), .35, .5)
            self.assertEqual(len(dets), 1)
            self.assertEqual(dets[0].cls, "person")
            self.assertAlmostEqual(dets[0].box[0], 270, delta=1)

    def test_letterbox_roundtrip(self):
        img = np.zeros((360, 640, 3), np.uint8)
        canvas, r, left, top = detector.letterbox(img, 640)
        self.assertEqual(canvas.shape, (640, 640, 3))
        self.assertAlmostEqual(r, 1.0)
        self.assertEqual(top, 140)


class EndToEnd(unittest.TestCase):
    def test_scenario_gives_one_alert_per_violation(self):
        zs = store.ZoneStore()
        zs.set("c", [{"name": "Склад", "points": sources.DEFAULT_ZONE}])
        st = store.EventStore()
        w = pipeline.CameraWorker("c", sources.SyntheticSource(realtime=False, max_frames=1200),
                                  detector.MockDetector(), st, hub.Hub(), zs)
        evs = []
        for f in w.source:
            evs += w.process_frame(f)
        kinds = sorted(e["type"] for e in evs)
        self.assertEqual(kinds, sorted(["fall", "no_helmet", "phone", "restricted_zone"] * 2))   # 2 цикла по 60 с
        self.assertTrue(all(e["latency_ms"] < 200 for e in evs))
        self.assertEqual(len(st.query(type="fall")), 2)
        eid = st.query()[0]["id"]
        self.assertEqual(st.set_status(eid, "false")["status"], "false")
        self.assertIsNone(st.set_status(eid, "bogus"))


if __name__ == "__main__":
    unittest.main()
