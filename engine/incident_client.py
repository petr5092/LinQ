"""Durable HTTP handoff from the CV process to the API process."""
import base64
from datetime import datetime
import json
import logging
from pathlib import Path
import threading
from urllib.request import Request, urlopen
import uuid

import cv2

log = logging.getLogger(__name__)


def incident_payload(incident, frame, camera):
    height, width = frame.shape[:2]
    bbox = incident.bbox.clip(width, height) if incident.bbox else None
    severity = getattr(incident.severity, 'value', str(incident.severity)).upper()
    ppe = incident.metadata.get('ppe_type')
    event_type = f'no_{ppe}' if ppe else incident.rule_name
    return {
        'id': incident.incident_id, 'site_id': camera['site_id'],
        'camera_id': camera['camera_id'], 'zone': incident.zone_id or camera.get('zone', 'unassigned'),
        'title': incident.description[:200] or incident.rule_name,
        'time': datetime.fromtimestamp(incident.confirmed_at).astimezone().strftime('%H:%M:%S'),
        'severity': {'CRITICAL': 'critical', 'HIGH': 'warning', 'MEDIUM': 'warning', 'LOW': 'info'}.get(severity, 'warning'),
        'type': event_type, 'description': incident.description,
        'status': 'new', 'track_id': incident.track_id,
        'box': [bbox.x1 / width * 100, bbox.y1 / height * 100,
                bbox.width / width * 100, bbox.height / height * 100] if bbox else None,
    }


class IncidentClient:
    """Queue before sending; retain failed requests for restart, use stable event IDs."""
    def __init__(self, api_url, outbox, retry_seconds=5.0):
        self.api_url = api_url.rstrip('/') if api_url else None
        self.outbox = Path(outbox)
        self.outbox.mkdir(parents=True, exist_ok=True)
        self.retry_seconds = retry_seconds
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._thread = None

    def start(self):
        if self.api_url:
            self._thread = threading.Thread(target=self._run, name='cv-incident-delivery', daemon=True)
            self._thread.start()

    def submit(self, incident, frame, camera):
        ok, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if not ok:
            raise ValueError('Cannot encode incident snapshot')
        payload = {'incident': incident_payload(incident, frame, camera),
                   'jpeg_base64': base64.b64encode(jpeg.tobytes()).decode('ascii')}
        event_id = str(uuid.UUID(incident.incident_id))
        path = self.outbox / f'{event_id}.json'
        temporary = self.outbox / f'{event_id}.{uuid.uuid4().hex}.tmp'
        temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
        temporary.replace(path)
        self._wake.set()

    def flush(self):
        if not self.api_url:
            return
        for path in self.outbox.glob('*.json'):
            try:
                request = Request(f'{self.api_url}/worker/incidents', data=path.read_bytes(),
                                  headers={'Content-Type': 'application/json'}, method='POST')
                with urlopen(request, timeout=5) as response:
                    response.read()
                path.unlink()
            except Exception as error:
                log.warning('Incident delivery failed; retained %s: %s', path.name, error)
                break

    def _run(self):
        while not self._stop.is_set():
            self._wake.clear()
            self.flush()
            self._wake.wait(self.retry_seconds)

    def close(self):
        self._stop.set()
        self._wake.set()
        if self._thread:
            self._thread.join(timeout=6)

