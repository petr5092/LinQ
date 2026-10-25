"""High-speed client adapter for the LinQ Stand TPU Bridge.

Optimizations:
1. Client-side letterbox to 640x640: reduces JPEG payload from ~100 KB to ~28 KB (3.5x reduction in bandwidth).
2. Persistent AMQP consumer: eliminates queue consume/cancel protocol roundtrips on every frame.
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

try:
    import pika
except ImportError:  # pragma: no cover
    pika = None

from engine.inference.base import (
    BaseInferenceEngine,
    BoundingBox,
    Detection,
    InferenceMetrics,
    InferenceResult,
)

logger = logging.getLogger("linq.inference.fast_bridge")


def client_letterbox(img: np.ndarray, target_size=(640, 640)) -> Tuple[np.ndarray, Dict[str, Any]]:
    """Letterbox image to 640x640 with aspect ratio preservation."""
    h, w = img.shape[:2]
    tw, th = target_size
    scale = min(tw / w, th / h)
    nw, nh = max(1, int(round(w * scale))), max(1, int(round(h * scale)))
    resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LINEAR)
    left = (tw - nw) // 2
    top = (th - nh) // 2
    padded = cv2.copyMakeBorder(
        resized, top, th - nh - top, left, tw - nw - left,
        cv2.BORDER_CONSTANT, value=(114, 114, 114)
    )
    meta = {
        "scale": scale,
        "pad_left": left,
        "pad_top": top,
        "orig_w": w,
        "orig_h": h,
    }
    return padded, meta


class LinQFastBridgeEngine(BaseInferenceEngine):
    """Optimized client engine communicating with the LinQ Stand TPU Bridge over RabbitMQ."""

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        login: str = "hackathon73916",
        conf_threshold: float = 0.20,
        iou_threshold: float = 0.45,
        jpeg_quality: int = 80,
        timeout: float = 10.0,
        **kwargs: Any,
    ):
        super().__init__(
            model_path=f"bridge://{login}",
            conf_threshold=conf_threshold,
            iou_threshold=iou_threshold,
            input_size=(640, 640),
            class_names=None,
        )
        self.host = host or os.getenv("LINQ_TPU_HOST", "10.0.114.30")
        self.port = port or int(os.getenv("LINQ_TPU_PORT", "5672"))
        self.login = login
        self.bridge_in_queue = f"{self.login}.bridge_in"
        self.jpeg_quality = jpeg_quality
        self.timeout = timeout
        self.is_emulated = False
        self._connected = False
        self._pending_replies: Dict[str, bytes] = {}

        self._connect()

    def _connect(self) -> None:
        if pika is None:
            raise RuntimeError("pika is required for LinQFastBridgeEngine. Install it with 'pip install pika'.")
        credentials = pika.PlainCredentials(
            os.getenv("LINQ_RABBITMQ_USER", "guest"),
            os.getenv("LINQ_RABBITMQ_PASSWORD", "guest"),
        )
        params = pika.ConnectionParameters(
            host=self.host,
            port=self.port,
            credentials=credentials,
            connection_attempts=3,
            retry_delay=1.0,
            socket_timeout=self.timeout,
        )
        self.connection = pika.BlockingConnection(params)
        self.channel = self.connection.channel()

        # Dedicated exclusive reply queue for this client instance
        self.reply_queue = f"client_reply_{uuid.uuid4().hex[:10]}"
        self.channel.queue_declare(queue=self.reply_queue, auto_delete=False, exclusive=True)

        # Set up single persistent consumer with callback
        self.channel.basic_consume(
            queue=self.reply_queue,
            on_message_callback=self._on_response,
            auto_ack=True,
        )

        self._connected = True
        self.is_loaded = True
        logger.info(
            "Connected to LinQ Stand Bridge at %s:%d (reply queue: %s, persistent consumer active)",
            self.host, self.port, self.reply_queue
        )

    def _on_response(self, channel, method, properties, body):
        corr_id = properties.correlation_id
        if corr_id:
            self._pending_replies[corr_id] = body

    def _ensure_connected(self) -> None:
        if not self._connected or self.connection.is_closed or self.channel.is_closed:
            self._connect()

    def load(self, model_path: Optional[str] = None) -> None:
        self.is_loaded = True

    def preprocess(self, frame: np.ndarray) -> Tuple[np.ndarray, Dict[str, Any]]:
        return client_letterbox(frame, self.input_size)

    def postprocess(self, raw_output: Any, meta: Dict[str, Any]) -> List[Detection]:
        if isinstance(raw_output, list):
            return raw_output
        return []

    def infer(self, image: np.ndarray) -> InferenceResult:
        t0 = time.monotonic()
        self._ensure_connected()

        orig_shape = image.shape
        t_prep_start = time.monotonic()

        # 1. Letterbox locally to 640x640
        padded_640, meta = client_letterbox(image, self.input_size)

        # 2. Compress the compact 640x640 frame to JPEG (only ~25-35 KB!)
        encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality]
        success, enc = cv2.imencode(".jpg", padded_640, encode_params)
        if not success:
            raise ValueError("Failed to encode letterboxed frame to JPEG")
        jpeg_bytes = enc.tobytes()
        t_prep_end = time.monotonic()
        prep_ms = (t_prep_end - t_prep_start) * 1000.0

        # 3. Publish to bridge input queue with letterbox metadata in headers
        corr_id = uuid.uuid4().hex
        t_net_start = time.monotonic()

        properties = pika.BasicProperties(
            reply_to=self.reply_queue,
            correlation_id=corr_id,
            content_type="image/jpeg",
            headers={
                "conf_threshold": str(self.conf_threshold),
                "iou_threshold": str(self.iou_threshold),
                "is_letterboxed": "true",
                "scale": str(meta["scale"]),
                "pad_left": str(meta["pad_left"]),
                "pad_top": str(meta["pad_top"]),
                "orig_w": str(meta["orig_w"]),
                "orig_h": str(meta["orig_h"]),
            },
        )
        self.channel.basic_publish(
            exchange="",
            routing_key=self.bridge_in_queue,
            body=jpeg_bytes,
            properties=properties,
        )

        # 4. Wait for response via persistent consumer event loop (sub-millisecond event polling)
        while corr_id not in self._pending_replies:
            if time.monotonic() - t_net_start > self.timeout:
                raise TimeoutError(f"Bridge response timed out after {self.timeout}s (corr_id={corr_id})")
            self.connection.process_data_events(time_limit=0.005)

        received_payload = self._pending_replies.pop(corr_id)

        t_post_start = time.monotonic()
        res_data = json.loads(received_payload.decode("utf-8"))
        if res_data.get("status") != "ok":
            raise RuntimeError(f"Stand bridge error: {res_data.get('error')}")

        raw_detections = res_data.get("detections", [])
        detections: List[Detection] = []
        for d in raw_detections:
            b = d["bbox"]
            detections.append(Detection(
                class_id=int(d["class_id"]),
                class_name=str(d["class_name"]),
                confidence=float(d["confidence"]),
                bbox=BoundingBox(x1=b[0], y1=b[1], x2=b[2], y2=b[3]),
            ))

        t_end = time.monotonic()
        post_ms = (t_end - t_post_start) * 1000.0
        total_ms = (t_end - t0) * 1000.0
        net_and_tpu_ms = (t_post_start - t_net_start) * 1000.0

        metrics = InferenceMetrics(
            preprocess_time_ms=prep_ms,
            inference_time_ms=net_and_tpu_ms,
            postprocess_time_ms=post_ms,
            total_time_ms=total_ms,
            fps=(1000.0 / total_ms) if total_ms > 0 else 0.0,
            backend_name="LINQ_FAST_BRIDGE",
        )

        return InferenceResult(
            detections=detections,
            metrics=metrics,
            original_shape=orig_shape,
        )

    def close(self) -> None:
        if self._connected:
            self._connected = False
            try:
                self.channel.queue_delete(queue=self.reply_queue)
            except Exception:
                pass
            try:
                self.connection.close()
            except Exception:
                pass
