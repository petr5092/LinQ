import json
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

BASE_URL = "http://localhost:8000/api/v1"


def make_request(method: str, path: str, data: dict | None = None):
    url = f"{BASE_URL}{path}"
    headers = {"Content-Type": "application/json"}
    payload = json.dumps(data).encode("utf-8") if data is not None else None
    req = Request(url, data=payload, headers=headers, method=method)
    try:
        with urlopen(req, timeout=5) as resp:
            content = resp.read().decode("utf-8")
            return resp.status, json.loads(content) if content else {}
    except HTTPError as exc:
        err_body = exc.read().decode("utf-8")
        try:
            parsed = json.loads(err_body)
        except Exception:
            parsed = {"raw": err_body}
        return exc.code, parsed


class TestThermalAPIIntegration(unittest.TestCase):
    def test_camera_not_found(self):
        status, data = make_request("POST", "/thermal/cameras/NON-EXISTENT/frame", {"temperatures": [[20.0]]})
        self.assertEqual(status, 404)
        self.assertIn("detail", data)

    def test_camera_not_thermal(self):
        status, data = make_request("POST", "/thermal/cameras/CAM-01/frame", {"temperatures": [[20.0]]})
        self.assertEqual(status, 409)
        self.assertIn("thermal", data["detail"])

    def test_invalid_temperature_payload(self):
        # Non-rectangular
        status, data = make_request("POST", "/thermal/cameras/THERMAL-OSF-TEST/frame", {
            "temperatures": [[20.0, 21.0], [20.0]]
        })
        self.assertEqual(status, 422)

        # Empty
        status, data = make_request("POST", "/thermal/cameras/THERMAL-OSF-TEST/frame", {
            "temperatures": []
        })
        self.assertEqual(status, 422)

    def test_valid_frame_ingestion_and_query(self):
        # Send a 10x10 matrix with normal temperature 20.0 C
        matrix = [[20.0 for _ in range(10)] for _ in range(10)]
        status, data = make_request("POST", "/thermal/cameras/THERMAL-OSF-TEST/frame", {
            "temperatures": matrix
        })
        self.assertEqual(status, 200)
        self.assertEqual(data["camera_id"], "THERMAL-OSF-TEST")
        self.assertEqual(data["width"], 10)
        self.assertEqual(data["height"], 10)
        self.assertEqual(data["minimum_temperature_c"], 20.0)
        self.assertEqual(data["maximum_temperature_c"], 20.0)
        self.assertTrue(len(data["measurements"]) > 0)

        # Verify GET /latest returns frame including heatmap
        status, latest = make_request("GET", "/thermal/cameras/THERMAL-OSF-TEST/latest")
        self.assertEqual(status, 200)
        self.assertEqual(latest["camera_id"], "THERMAL-OSF-TEST")
        self.assertTrue("heatmap_jpeg_base64" in latest)
        self.assertTrue(len(latest["heatmap_jpeg_base64"]) > 100)

        # Verify GET /readings
        status, readings = make_request("GET", "/thermal/cameras/THERMAL-OSF-TEST/readings")
        self.assertEqual(status, 200)
        self.assertIsInstance(readings, list)
        self.assertTrue(len(readings) > 0)


if __name__ == "__main__":
    unittest.main()
