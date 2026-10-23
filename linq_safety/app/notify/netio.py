"""HTTP-вызовы на стандартной библиотеке. Прокси берутся из HTTPS_PROXY автоматически."""
import json
import urllib.error
import urllib.parse
import urllib.request
import uuid


class ApiError(Exception):
    def __init__(self, msg, code=None, retry_after=None):
        super().__init__(msg)
        self.code, self.retry_after = code, retry_after


def request(url, data=None, headers=None, timeout=40):
    """Возвращает (http_status, bytes). Бросает ApiError только при сетевых сбоях."""
    req = urllib.request.Request(url, data=data, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise ApiError(f"сеть недоступна: {getattr(e, 'reason', e)}") from None


def post_json(url, payload, timeout=40):
    return request(url, json.dumps(payload).encode(), {"Content-Type": "application/json"}, timeout)


def post_form(url, params, timeout=40):
    return request(url, urllib.parse.urlencode(params).encode(),
                   {"Content-Type": "application/x-www-form-urlencoded"}, timeout)


def post_multipart(url, fields, files, timeout=60):
    """fields: {имя: строка}; files: {имя_поля: (имя_файла, bytes)}."""
    b = uuid.uuid4().hex
    out = []
    for k, v in fields.items():
        out.append(f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    for k, (fn, data) in files.items():
        out.append(f'--{b}\r\nContent-Disposition: form-data; name="{k}"; filename="{fn}"\r\n'
                   f'Content-Type: image/jpeg\r\n\r\n'.encode() + data + b"\r\n")
    out.append(f"--{b}--\r\n".encode())
    return request(url, b"".join(out), {"Content-Type": f"multipart/form-data; boundary={b}"}, timeout)
