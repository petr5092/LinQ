import unittest
import numpy as np

from engine.thermal.analyzer import ThermalZone, ThermalAnalyzer, ThermalMeasurement


class TestThermalZone(unittest.TestCase):
    def test_valid_zone(self):
        zone = ThermalZone.from_mapping({
            "zone_id": "z1",
            "name": "Zone 1",
            "roi": [0.1, 0.2, 0.8, 0.9],
            "max_temperature_c": 50.0,
            "clear_temperature_c": 45.0,
            "min_hot_pixels": 2,
            "min_frames": 3,
            "severity": "warning",
            "action": "Check unit",
        })
        self.assertEqual(zone.zone_id, "z1")
        self.assertEqual(zone.roi, (0.1, 0.2, 0.8, 0.9))
        self.assertEqual(zone.max_temperature_c, 50.0)
        self.assertEqual(zone.clear_temperature_c, 45.0)
        self.assertEqual(zone.min_hot_pixels, 2)
        self.assertEqual(zone.min_frames, 3)
        self.assertEqual(zone.severity, "warning")

    def test_invalid_roi(self):
        with self.assertRaises(ValueError):
            ThermalZone.from_mapping({"zone_id": "z1", "roi": [0.5, 0.5, 0.2, 0.8], "max_temperature_c": 50})
        with self.assertRaises(ValueError):
            ThermalZone.from_mapping({"zone_id": "z1", "roi": [-0.1, 0.0, 0.5, 0.5], "max_temperature_c": 50})
        with self.assertRaises(ValueError):
            ThermalZone.from_mapping({"zone_id": "z1", "roi": [0.0, 0.0, 1.2, 0.5], "max_temperature_c": 50})
        with self.assertRaises(ValueError):
            ThermalZone.from_mapping({"zone_id": "z1", "roi": [0.1, 0.2], "max_temperature_c": 50})

    def test_invalid_temperatures(self):
        with self.assertRaises(ValueError):
            ThermalZone.from_mapping({"zone_id": "z1", "roi": [0, 0, 1, 1], "max_temperature_c": 50, "clear_temperature_c": 55})
        with self.assertRaises(ValueError):
            ThermalZone.from_mapping({"zone_id": "z1", "roi": [0, 0, 1, 1], "max_temperature_c": 50, "clear_temperature_c": 50})

    def test_invalid_frames_or_pixels(self):
        with self.assertRaises(ValueError):
            ThermalZone.from_mapping({"zone_id": "z1", "roi": [0, 0, 1, 1], "max_temperature_c": 50, "min_hot_pixels": 0})
        with self.assertRaises(ValueError):
            ThermalZone.from_mapping({"zone_id": "z1", "roi": [0, 0, 1, 1], "max_temperature_c": 50, "min_frames": 0})

    def test_invalid_severity(self):
        with self.assertRaises(ValueError):
            ThermalZone.from_mapping({"zone_id": "z1", "roi": [0, 0, 1, 1], "max_temperature_c": 50, "severity": "danger"})


class TestThermalAnalyzer(unittest.TestCase):
    def setUp(self):
        self.zone_mapping = {
            "zone_id": "bearing",
            "name": "Motor Bearing",
            "roi": [0.25, 0.25, 0.75, 0.75],
            "max_temperature_c": 60.0,
            "clear_temperature_c": 50.0,
            "min_hot_pixels": 2,
            "min_frames": 3,
            "severity": "critical",
        }
        self.analyzer = ThermalAnalyzer([self.zone_mapping])

    def test_validate_frame_invalid(self):
        with self.assertRaises(ValueError):
            ThermalAnalyzer.validate_frame([[np.nan, 20.0], [20.0, 20.0]])
        with self.assertRaises(ValueError):
            ThermalAnalyzer.validate_frame([[3500.0, 20.0], [20.0, 20.0]])
        with self.assertRaises(ValueError):
            ThermalAnalyzer.validate_frame([[-300.0, 20.0], [20.0, 20.0]])
        with self.assertRaises(ValueError):
            ThermalAnalyzer.validate_frame(np.zeros((600, 100)))  # height > 512
        with self.assertRaises(ValueError):
            ThermalAnalyzer.validate_frame(np.zeros((100, 700)))  # width > 640
        with self.assertRaises(ValueError):
            ThermalAnalyzer.validate_frame(np.zeros((10, 10, 3)))  # 3D

    def test_debounce_and_hysteresis(self):
        # 40x40 matrix with cold background 25 C
        cold_frame = np.full((40, 40), 25.0, dtype=np.float32)
        
        # Frame 1: cold
        res = self.analyzer.process(cold_frame)
        self.assertFalse(res[0].alarm)
        self.assertFalse(res[0].alarm_started)

        # Hot frame: 5 hot pixels at 65 C (threshold is 60 C) inside ROI
        hot_frame = cold_frame.copy()
        hot_frame[15:18, 15:17] = 65.0  # 3x2 = 6 pixels inside [10:30, 10:30]

        # Frame 2 (Hot frame #1)
        res = self.analyzer.process(hot_frame)
        self.assertFalse(res[0].alarm)
        self.assertFalse(res[0].alarm_started)

        # Frame 3 (Hot frame #2)
        res = self.analyzer.process(hot_frame)
        self.assertFalse(res[0].alarm)
        self.assertFalse(res[0].alarm_started)

        # Frame 4 (Hot frame #3: debounced to min_frames=3)
        res = self.analyzer.process(hot_frame)
        self.assertTrue(res[0].alarm)
        self.assertTrue(res[0].alarm_started)

        # Frame 5 (Hot frame #4: persists alarm, but alarm_started is False)
        res = self.analyzer.process(hot_frame)
        self.assertTrue(res[0].alarm)
        self.assertFalse(res[0].alarm_started)

        # Hysteresis test:
        # Temperature drops below max_temperature_c (60 C) to 55 C (which is above clear_temperature_c 50 C)
        warm_frame = cold_frame.copy()
        warm_frame[15:18, 15:17] = 55.0
        res = self.analyzer.process(warm_frame)
        # Because 55 C > clear_temperature_c (50 C), alarm should remain active!
        self.assertTrue(res[0].alarm)
        self.assertFalse(res[0].alarm_started)

        # Temperature drops to 45 C (below clear_temperature_c 50 C)
        cooled_frame = cold_frame.copy()
        cooled_frame[15:18, 15:17] = 45.0
        res = self.analyzer.process(cooled_frame)
        # Alarm should clear!
        self.assertFalse(res[0].alarm)
        self.assertFalse(res[0].alarm_started)

    def test_analyzer_reset(self):
        hot_frame = np.full((40, 40), 70.0, dtype=np.float32)
        for _ in range(3):
            self.analyzer.process(hot_frame)
        self.assertTrue(self.analyzer.process(hot_frame)[0].alarm)
        self.analyzer.reset()
        # After reset, alarm must be cleared
        res = self.analyzer.process(np.full((40, 40), 20.0, dtype=np.float32))
        self.assertFalse(res[0].alarm)


if __name__ == "__main__":
    unittest.main()
