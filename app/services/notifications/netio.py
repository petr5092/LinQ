"""
Сетевое взаимодействие и интеграция с аппаратными реле NetIO (сирены, световые маяки).
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Dict, Optional, Tuple


class ApiError(Exception):
    """Исключение при вызове внешнего API уведомлений."""

    def __init__(self, message: str, code: Optional[int] = None, retry_after: Optional[int] = None) -> None:
        super().__init__(message)
        self.code = code
        self.retry_after = retry_after


def post_json(url: str, payload: dict, timeout: float = 30.0) -> Tuple[int, bytes]:
    """Отправка JSON POST запроса с использованием стандартной библиотеки."""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        retry_after = None
        hdr = e.headers.get("Retry-After")
        if hdr and hdr.isdigit():
            retry_after = int(hdr)
        err_msg = e.reason
        try:
            body = e.read().decode("utf-8")
            d = json.loads(body)
            err_msg = d.get("description", e.reason)
        except Exception:
            pass
        raise ApiError(f"HTTP {e.code}: {err_msg}", e.code, retry_after)
    except urllib.error.URLError as e:
        raise ApiError(f"Сетевая ошибка: {e.reason}")


def post_multipart(url: str, fields: dict, files: dict, timeout: float = 30.0) -> Tuple[int, bytes]:
    """Отправка multipart/form-data POST запроса для передачи изображений в Telegram."""
    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    lines = []

    for key, val in fields.items():
        lines.append(f"--{boundary}".encode("utf-8"))
        lines.append(f'Content-Disposition: form-data; name="{key}"'.encode("utf-8"))
        lines.append(b"")
        lines.append(str(val).encode("utf-8"))

    for key, (filename, content) in files.items():
        lines.append(f"--{boundary}".encode("utf-8"))
        lines.append(f'Content-Disposition: form-data; name="{key}"; filename="{filename}"'.encode("utf-8"))
        lines.append(b"Content-Type: image/jpeg")
        lines.append(b"")
        lines.append(content)

    lines.append(f"--{boundary}--".encode("utf-8"))
    lines.append(b"")
    body = b"\r\n".join(lines)

    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        retry_after = None
        hdr = e.headers.get("Retry-After")
        if hdr and hdr.isdigit():
            retry_after = int(hdr)
        err_msg = e.reason
        try:
            body = e.read().decode("utf-8")
            d = json.loads(body)
            err_msg = d.get("description", e.reason)
        except Exception:
            pass
        raise ApiError(f"HTTP {e.code}: {err_msg}", e.code, retry_after)
    except urllib.error.URLError as e:
        raise ApiError(f"Сетевая ошибка: {e.reason}")


class NetioClient:
    """Интерфейс к промышленному силовому реле NetIO для включения звуковой/световой сигнализации."""

    channel = "netio"

    def __init__(self, host: str, port: int = 80, username: str = "admin", password: str = "admin") -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.url = f"http://{host}:{port}/netio.json"

    def trigger_siren(self, output_id: int = 1, action: int = 4) -> bool:
        """
        action: 1 - включить, 0 - выключить, 4 - кратковременный импульс (pulse).
        """
        payload = {
            "Outputs": [
                {"ID": output_id, "Action": action}
            ]
        }
        try:
            post_json(self.url, payload, timeout=5.0)
            return True
        except Exception as e:
            print(f"[NetIO] Ошибка активации сирены: {e}")
            return False
