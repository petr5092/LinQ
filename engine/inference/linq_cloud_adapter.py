"""LinQ Cloud TPU Adapter over RabbitMQ AMQP.

Connects directly from the local inference engine / dashboard to the physical LinQ TPU
accelerator chip on the hackathon stand (10.0.114.30:5672).
Uses the official tpu_pycloud_format protocol for zero-copy tensor transport.
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from typing import Any, Dict, Optional

import numpy as np
import pika

try:
    from tpu_pycloud_format import (
        MESSAGE_ID_ATTR_NAME,
        RESPONSE_ROUTING_KEYS_ATTR_NAME,
        TARGET_URI_ATTR_NAME,
        PyTask,
        deserialize,
        serialize,
    )
    HAS_PYCLOUD = True
except ImportError:
    HAS_PYCLOUD = False

logger = logging.getLogger("linq.inference.cloud_adapter")


class CloudTPURuntime:
    """Callable runtime that sends NCHW input tensors to the physical LinQ TPU chip."""

    def __init__(
        self,
        program_path: str,
        host: Optional[str] = None,
        port: Optional[int] = None,
        exchange: Optional[str] = None,
        input_queue: Optional[str] = None,
        input_name: Optional[str] = None,
        output_name: Optional[str] = None,
        timeout: float = 30.0,
    ):
        if not HAS_PYCLOUD:
            raise RuntimeError(
                "tpu_pycloud_format is required for LinQ Cloud TPU. Install it in your environment."
            )

        self.host = host or os.getenv("LINQ_TPU_HOST", "10.0.114.30")
        self.port = port or int(os.getenv("LINQ_TPU_PORT", "5672"))
        self.exchange = exchange or os.getenv("LINQ_TPU_EXCHANGE", "tpu.direct")
        self.input_queue = input_queue or os.getenv("LINQ_TPU_INPUT_QUEUE", "input")
        self.input_name = input_name or os.getenv("LINQ_INPUT_NAME", "images")
        self.output_name = output_name or os.getenv("LINQ_OUTPUT_NAME", "output0")
        self.timeout = timeout
        self._closed = False

        # Format remote target URI for TPU worker
        # On stand, workers mount /auto/cache/hackathon73916/
        basename = os.path.basename(program_path)
        login = os.getenv("LINQ_STAND_LOGIN", "hackathon73916")
        self.remote_program_uri = f"file:///auto/cache/{login}/{basename}?raw=False"

        # Initialize persistent RabbitMQ connection
        self._connect()

    def _connect(self) -> None:
        credentials = pika.PlainCredentials(
            os.getenv("LINQ_RABBITMQ_USER", "guest"),
            os.getenv("LINQ_RABBITMQ_PASSWORD", "guest"),
        )
        parameters = pika.ConnectionParameters(
            host=self.host,
            port=self.port,
            credentials=credentials,
            connection_attempts=3,
            retry_delay=1.0,
            socket_timeout=self.timeout,
        )
        self.connection = pika.BlockingConnection(parameters)
        self.channel = self.connection.channel()

        # Unique reply queue for this runtime session
        session_id = uuid.uuid4().hex[:10]
        self.reply_queue = f"engine_reply_{session_id}"
        self.channel.queue_declare(queue=self.reply_queue, auto_delete=False, exclusive=True)
        self.channel.queue_bind(
            exchange=self.exchange,
            queue=self.reply_queue,
            routing_key=self.reply_queue,
        )
        logger.info(
            "Connected to LinQ Cloud TPU broker at %s:%d (reply queue: %s, target: %s)",
            self.host,
            self.port,
            self.reply_queue,
            self.remote_program_uri,
        )

    def __call__(self, tensor: np.ndarray) -> np.ndarray:
        if self._closed:
            raise RuntimeError("CloudTPURuntime is closed")

        if not isinstance(tensor, np.ndarray) or tensor.dtype != np.float32:
            tensor = np.asarray(tensor, dtype=np.float32)

        if tensor.ndim == 3:
            tensor = tensor[None]

        # Check channel health, reconnect if dropped
        if self.connection.is_closed or self.channel.is_closed:
            self._connect()

        task_id = uuid.uuid4().hex
        tensors = {self.input_name: tensor}
        payload = serialize(PyTask(tensors))

        headers = {
            TARGET_URI_ATTR_NAME: self.remote_program_uri,
            RESPONSE_ROUTING_KEYS_ATTR_NAME: json.dumps([self.reply_queue]),
            MESSAGE_ID_ATTR_NAME: task_id,
        }

        self.channel.basic_publish(
            exchange=self.exchange,
            routing_key=self.input_queue,
            body=payload,
            properties=pika.BasicProperties(headers=headers),
        )

        # Wait for hardware response
        started = time.monotonic()
        received_body: Optional[bytes] = None

        for method, properties, body in self.channel.consume(
            self.reply_queue, auto_ack=True, inactivity_timeout=0.5
        ):
            if method is None:
                if time.monotonic() - started > self.timeout:
                    raise TimeoutError(
                        f"Timed out after {self.timeout:.1f}s waiting for LinQ TPU inference response (task {task_id})"
                    )
                continue
            received_body = body
            self.channel.cancel()
            break

        if received_body is None:
            raise RuntimeError(f"No response received from LinQ TPU for task {task_id}")

        data, metadata, worker = deserialize(received_body)
        status_code = worker.get("status_code", -1)
        if status_code != 0:
            error_msg = worker.get("error_message", f"TPU error code {status_code}")
            raise RuntimeError(f"LinQ TPU hardware execution failed: {error_msg}")

        if self.output_name not in data:
            available = list(data.keys())
            if len(available) == 1:
                return data[available[0]]
            raise KeyError(
                f"Configured output {self.output_name!r} not in TPU outputs; available: {available}"
            )

        return data[self.output_name]

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            try:
                if hasattr(self, "channel") and self.channel.is_open:
                    self.channel.close()
                if hasattr(self, "connection") and self.connection.is_open:
                    self.connection.close()
            except Exception as e:
                logger.debug("Error while closing AMQP connection: %s", e)


def load(program_path: str) -> CloudTPURuntime:
    """Entry point for LinQTPUEngine."""
    return CloudTPURuntime(program_path)
