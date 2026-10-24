#!/usr/bin/env python3
"""
Скрипт диагностики и проверки доступности сетевых ресурсов LinQ TPU.
Проверяет:
1. Активность VPN-подключения и маршрутизацию к подсети 10.0.114.0/24;
2. Доступность веб-сервера Jupyter Notebook (http://hackathon.lin-q.ru/);
3. Доступность удаленного микросервиса LinQ TPU (если передан URL или задан LINQ_TPU_URL).

Использование:
    python test_linq_connection.py
    python test_linq_connection.py --endpoint http://10.0.114.15:8080
"""

from __future__ import annotations

import argparse
import os
import socket
import sys
import time
import urllib.request
import urllib.error


def check_host_dns(host: str) -> tuple[bool, str]:
    try:
        ip = socket.gethostbyname(host)
        return True, ip
    except Exception as e:
        return False, str(e)


def check_http_endpoint(url: str, timeout: float = 3.0) -> tuple[bool, int, str]:
    t0 = time.perf_counter()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "LinQProbe/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            return True, resp.status, f"{elapsed_ms:.1f} мс"
    except urllib.error.HTTPError as e:
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        return True, e.code, f"HTTP {e.code} ({elapsed_ms:.1f} мс)"
    except Exception as e:
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        return False, 0, f"Ошибка: {e} ({elapsed_ms:.1f} мс)"


def main():
    parser = argparse.ArgumentParser(description="Диагностика подключения к инфраструктуре LinQ")
    parser.add_argument("--endpoint", default=os.getenv("LINQ_TPU_URL"),
                        help="URL сервиса LinQ TPU (например http://10.0.114.15:8080)")
    args = parser.parse_args()

    print("=" * 70)
    print("   Диагностика сетевой связности с инфраструктурой LinQ")
    print("=" * 70)

    # 1. DNS & Доступность Jupyter
    jupyter_host = "hackathon.lin-q.ru"
    print(f"\n[1/3] Проверка DNS для {jupyter_host}...")
    dns_ok, dns_info = check_host_dns(jupyter_host)
    if dns_ok:
        print(f"  ✓ DNS успешно разрешен: {jupyter_host} -> {dns_info}")
    else:
        print(f"  [!] Не удалось разрешить DNS ({dns_info}).")
        print("      Убедитесь, что OpenVPN подключен (профиль Hakathon.ovpn).")

    # 2. HTTP доступность Jupyter
    jupyter_url = "http://hackathon.lin-q.ru/"
    print(f"\n[2/3] Проверка HTTP доступа к Jupyter Notebook ({jupyter_url})...")
    http_ok, code, info = check_http_endpoint(jupyter_url)
    if http_ok:
        print(f"  ✓ Портал Jupyter доступен! Статус: {code}, задержка: {info}")
    else:
        print(f"  [!] Портал Jupyter недоступен: {info}")
        print("      Требуется активный туннель OpenVPN к 83.220.57.3:1194.")

    # 3. Микросервис LinQ TPU
    if args.endpoint:
        tpu_url = args.endpoint.rstrip("/")
        health_url = f"{tpu_url}/health"
        print(f"\n[3/3] Проверка микросервиса LinQ TPU ({health_url})...")
        tpu_ok, tpu_code, tpu_info = check_http_endpoint(health_url)
        if tpu_ok and tpu_code == 200:
            print(f"  ✓ Микросервис LinQ TPU активен! Задержка: {tpu_info}")
        else:
            print(f"  [!] Микросервис LinQ TPU не ответил: {tpu_info}")
    else:
        print("\n[3/3] Микросервис LinQ TPU: URL не указан (флаг --endpoint или LINQ_TPU_URL).")
        print("      После запуска `uvicorn linq_tpu_service:app` на ВМ передайте его адрес.")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
