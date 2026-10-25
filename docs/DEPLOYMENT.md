# Руководство по развертыванию платформы LenQsec

Документ описывает требования к окружению, варианты развертывания и регламент эксплуатации системы **LenQsec** в промышленных условиях.

---

## 1. Системные требования

| Компонент | Минимальные требования | Рекомендуемые требования |
|---|---|---|
| **Операционная система** | Ubuntu 22.04 LTS / Windows 11 | Ubuntu 22.04 LTS (для Edge и TPU) |
| **Процессор (CPU)** | 4 ядра (x86_64 или ARM64) | 8+ ядер Intel Xeon / AMD EPYC |
| **Оперативная память (RAM)** | 8 ГБ | 16+ ГБ |
| **Дисковое пространство** | 20 ГБ SSD | 100+ ГБ NVMe (хранение снапшотов) |
| **ИИ-ускоритель** | CPU (инференс ONNX) | **LinQ TPU (архитектура H1M)** |
| **Python** | 3.12+ | 3.12.11 (соответствует LinQ SDK) |

---

## 2. Варианты развертывания

### Вариант А: Контейнерное развертывание (Docker Compose)
Рекомендуется для центральных серверов предприятий и локальных контуров диспетчерских.

1. **Клонирование репозитория и настройка `.env`**:
   ```bash
   git clone https://github.com/petr5092/LinQ.git lenqsec
   cd lenqsec/LinQproject
   cp .env.example .env
   # Отредактируйте .env (укажите пароли БД и токены уведомлений)
   ```

2. **Запуск базы данных PostgreSQL и применение миграций**:
   ```bash
   docker compose up -d postgres
   docker compose run --rm backend alembic upgrade head
   ```

3. **Запуск полного стека**:
   ```bash
   docker compose up -d --build
   ```

4. **Проверка состояния сервисов**:
   ```bash
   docker compose ps
   docker compose logs -f backend
   ```

---

### Вариант Б: Автономное развертывание на Edge-устройстве (Bare-Metal / Systemd)
Используется на встраиваемых промышленных компьютерах в цехах и узлах с платами **LinQ TPU**.

1. **Создание изолированного окружения**:
   ```bash
   python3.12 -m venv /opt/lenqsec/.venv
   source /opt/lenqsec/.venv/bin/activate
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

2. **Создание systemd-сервиса для бэкенда (`/etc/systemd/system/lenqsec-backend.service`)**:
   ```ini
   [Unit]
   Description=LenQsec Backend Service
   After=network.target

   [Service]
   Type=simple
   User=lenqsec
   WorkingDirectory=/opt/lenqsec/LinQproject
   EnvironmentFile=/opt/lenqsec/LinQproject/.env
   ExecStart=/opt/lenqsec/.venv/bin/python run.py
   Restart=always
   RestartSec=5

   [Install]
   WantedBy=multi-user.target
   ```

3. **Создание systemd-сервиса для CV-воркера (`/etc/systemd/system/lenqsec-worker.service`)**:
   ```ini
   [Unit]
   Description=LenQsec CV Worker (LinQ TPU)
   After=lenqsec-backend.service

   [Service]
   Type=simple
   User=lenqsec
   WorkingDirectory=/opt/lenqsec/LinQproject
   EnvironmentFile=/opt/lenqsec/LinQproject/.env
   ExecStart=/opt/lenqsec/.venv/bin/python run_worker.py --config configs/cv_engine.yaml --backend linq_tpu --model models/tpu/safety_yolov8_h1m.tpu
   Restart=always
   RestartSec=5

   [Install]
   WantedBy=multi-user.target
   ```

4. **Активация и запуск**:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable --now lenqsec-backend lenqsec-worker
   ```

---

### Вариант В: Развертывание на удаленном стенде LinQ (Jupyter / VPN)

1. Подключитесь к сети стенда через OpenVPN (`Hakathon.ovpn`).
2. Откройте веб-интерфейс Jupyter стенда: `http://hackathon.lin-q.ru/`.
3. Загрузите архив автономного пакета `linq_deploy_bundle.zip` в рабочую папку `~/work/`.
4. Распакуйте и запустите автономный скрипт инициализации:
   ```bash
   unzip linq_deploy_bundle.zip -d linq_deploy_bundle
   cd linq_deploy_bundle
   chmod +x setup.sh
   ./setup.sh
   ```
5. Запустите сетевой сервис TPU-инференса для внешней панели:
   ```bash
   nohup uvicorn linq_tpu_service:app --host 0.0.0.0 --port 8080 > tpu_service.log 2>&1 &
   ```

---

## 3. Таблица переменных окружения (`.env`)

| Переменная | По умолчанию | Описание |
|---|---|---|
| `INFERENCE_BACKEND` | `ONNX_CPU` | Движок инференса: `LINQ_TPU`, `ONNX_CPU`, `MOCK` |
| `ONNX_MODEL_PATH` | `models/onnx/safety_yolov8n.onnx` | Путь к весам ONNX |
| `TPU_MODEL_PATH` | `models/tpu/safety_yolov8_h1m.tpu` | Путь к скомпилированной программе LinQ TPU |
| `DATABASE_URL` | `postgresql+psycopg2://...` | Строка подключения к СУБД |
| `STORAGE_TYPE` | `local` | Тип хранилища снапшотов: `local` или `s3` |
| `S3_ENDPOINT_URL` | `https://storage.yandexcloud.net` | Адрес S3 совместимого хранилища |
| `S3_BUCKET_NAME` | `lenqsec-snapshots` | Имя бакета для стоп-кадров нарушений |
| `LINQ_TG_TOKEN` | - | Токен Telegram-бота диспетчерской |
| `CAMERA_SOURCE` | `storage/demo_videos/construction_safety.mp4` | Источник видео (RTSP URL, путь к файлу) |
| `DEBOUNCE_FRAMES`| `15` | Количество кадров подтверждения нарушения |
| `COOLDOWN_SECONDS`| `300` | Время блокировки повторных алертов по объекту (сек) |

---

## 4. Регламент резервного копирования и мониторинга

* **БД**: регулярный дамп базы PostgreSQL:
  ```bash
  docker exec -t lenqsec_postgres pg_dump -U postgres lenqsec | gzip > backup_lenqsec_$(date +%Y%m%d).sql.gz
  ```
* **Снапшоты нарушений**: при использовании локального хранилища директория `storage/snapshots` монтируется на выделенный том или синхронизируется в S3 объектное хранилище.
* **Healthcheck**: проверка доступности сервиса выполняется запросом:
  `GET http://localhost:8000/docs` или `GET http://localhost:8000/api/v1/cameras`.
