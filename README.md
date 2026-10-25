# LenQsec: Интеллектуальная система контроля промышленной безопасности и охраны труда

[![Tests](https://img.shields.io/badge/tests-221%20passed-brightgreen.svg)](tests/)
[![Hardware](https://img.shields.io/badge/accelerator-LinQ%20TPU%20(H1M)-blue.svg)](docs/HACKATHON_LINQ_SPECS.md)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688.svg)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/frontend-React%2019%20%7C%20TypeScript-61dafb.svg)](frontend/)

> **Проверенный статус E2E-конвейера и команды запуска:** см. [CV_HANDOFF.md](CV_HANDOFF.md).  
> Все 221 модульный и интеграционный тест успешно проходят в изолированном окружении.  
> Сервис поддерживает работу в режимах `LINQ_TPU` (отечественный чип H1M), `ONNX_CPU` и `MOCK`.  
> Бэкенд и операторский интерфейс запускаются командой `python run.py`, независимый CV-воркер — `python run_worker.py`.

**LenQsec** — комплексная программно-аппаратная платформа видеоаналитики и интеллектуального контроля промышленной безопасности, предупреждения травматизма и мониторинга охраны труда (ОТ и ТБ) на промышленных предприятиях с аппаратным ускорением инференса на российских ИИ-ускорителях **LinQ TPU (платформа H1M)**.

Проект разработан в рамках хакатона **«Открой Моспром»** (кейс LinQ).

---

## 📌 Архитектурные возможности LenQsec

### 1. Аппаратное ускорение на отечественных чипах LinQ TPU
* Интеграция с тензорными процессорами LinQ через нативный драйвер `pytpu` и профиль `TPU_H1M`.
* Поддержка статического квантования нейросетей (FP19 с библиотекой `fp19_exp` и INT8) через компилятор `tpu_framework`.
* Модульный **Hardware Abstraction Layer (HAL)**: единый программный интерфейс `BaseInferenceEngine` с прозрачным переключением между `LINQ_TPU`, локальным `ONNX_CPU` и симулятором `MOCK`.
* Высокоскоростной мост `tools/stand_tpu_bridge.py` и автономный пакет развертывания `linq_deploy_bundle/` для работы с удаленным облачным стендом LinQ.

### 2. Движок правил промышленной безопасности (Safety Rules Engine)
* **Полигональные опасные зоны**: проверка нахождения опорной точки человека (стоп) внутри произвольных многоугольников операторской разметки (`Shapely.polygon.contains`).
* **Контроль ношения СИЗ (каски, сигнальные жилеты)**: распознавание отсутствия обязательной экипировки в рабочих зонах.
* **Фиксация падений и неподвижности**: детекция резкого изменения геометрического соотношения рамки ($w/h > 1.2$, горизонтальное положение тела) в сочетании с околонулевой скоростью трека более 2–3 секунд.
* **Предупреждение опасного сближения с техникой**: постоянный мониторинг евклидовой дистанции между персоналом и подвижной складской/цеховой техникой (погрузчики, кары).
* **Модульный реестр правил (`RULE_REGISTRY`)**: декларативное добавление новых правил охраны труда в `engine/rules/registry.py` без изменения ядра конвейера.

### 3. Радиометрический тепловизионный контроль (Thermal Monitoring)
* Поддержка матричных тепловизоров: регулярный приём матриц температур в градусах Цельсия напрямую из SDK камер (`POST /api/v1/thermal/cameras/{camera_id}/frame`).
* Зональный контроль температур: задание критических порогов (`max_temperature_c`), температур сброса тревоги (`clear_temperature_c`) и порогов срабатывания в `configs/thermal_cameras.yaml`.
* Генерация радиометрических термограмм (colormap Inferno/Jet) и прямая отдача JPEG в веб-интерфейс (`/api/v1/thermal/cameras/{camera_id}/heatmap.jpg`).
* Автоматическая фиксация инцидентов типа `environment` с сохранением термограммы в доказательную базу.
* Валидация на лабораторном наборе данных OSF (`data/thermal/osf_sample/`).

### 4. Подавление ложных тревог и анти-спам (Temporal Debounce & Cooldown)
* **Temporal Debounce**: фиксация инцидента осуществляется только при устойчивом подтверждении нарушения в течение $N$ кадров подряд (защита от случайных артефактов детекции).
* **Cooldown по `Track ID`**: алгоритм ByteTrack отслеживает динамику перемещения; одно продолжающееся нарушение порождает строго одно оповещение диспетчеру.
* **5-минутное окно слияния**: повторные фиксации того же типа нарушения на камере обновляют существующую открытую карточку инцидента и сообщение в Telegram, предотвращая лавину оповещений.
* **Гарантированная доставка (Outbox Pattern)**: дисковая очередь `engine/incident_client.py` сохраняет инциденты и стоп-кадры при потере сетевого соединения с последующей фоновой синхронизацией.

### 5. Каналы оперативного оповещения
* **Telegram-бот с интерактивным управлением**: оперативные карточки нарушений с фото/термограммой, метаданными и inline-кнопками для смены статуса прямо из чата смены.
* **WebSockets Broadcast**: мгновенное push-обновление операторского дашборда (`/ws/events`).
* **Python SDK корпоративных мессенджеров**: класс-адаптер `BaseMessengerAdapter` для бесшовного подключения корпоративных чатов предприятия.

### 6. Операторский веб-интерфейс диспетчера (LenQsec Web UI)
* Разработан на **React 19, TypeScript, Vite, Tailwind CSS**.
* Многокамерный видеомониторинг (RTSP, WebRTC/go2rtc, MJPEG, термограммы) с динамическим оверлеем bounding box'ов.
* Интерактивный редактор полигонов зон непосредственно на живом кадре камеры.
* Журнал инцидентов с гибкими фильтрами по времени, критичности, типу нарушения, цеху и статусу расследования.
* Карточка инцидента с доказательной базой: стоп-кадр нарушения, таймштамп, СКУД-данные сотрудника, рекомендуемое действие и контакты дежурного мастера.
* Аналитический дашборд статистики нарушений по сменам и участкам с экспортом отчетов в CSV.

---

## 📂 Структура репозитория LenQsec

```text
LinQproject/
├── configs/                     # Конфигурационные файлы зон, CV-движка и тепловизоров
│   ├── cv_engine.yaml           # Параметры трекинга, порогов и правил ТБ
│   ├── cv_person.yaml           # Облегченная конфигурация контроля опасной зоны
│   └── thermal_cameras.yaml     # Зоны и температурные пороги тепловизоров
├── docs/                        # Полная техническая документация проекта LenQsec
│   ├── ARCHITECTURE.md          # Детальная архитектура системы и контракты потоков данных
│   ├── API.md                   # Спецификация REST API и WebSocket-протокола
│   ├── THERMAL_GUIDE.md         # Руководство по интеграции радиометрических тепловизоров
│   ├── DEPLOYMENT.md            # Руководство по развертыванию (Docker, Edge, Stand)
│   ├── OPERATOR_GUIDE.md        # Руководство оператора диспетчерского центра
│   └── HACKATHON_LINQ_SPECS.md  # Спецификация LinQ TPU и сетевого стенда
├── models/                      # Нейросетевые артефакты
│   ├── onnx/                    # Экспортированные модели ONNX (статичный shape [1, 3, 640, 640])
│   └── tpu/                     # Скомпилированные бинарные программы LinQ TPU (.tpu)
├── engine/                      # Ядро компьютерного зрения (CV Engine)
│   ├── inference/               # Hardware Abstraction Layer (LinQ TPU, ONNX, Mock)
│   ├── tracking/                # Трекер объектов во времени (ByteTrack)
│   ├── rules/                   # Правила охраны труда (зоны, СИЗ, падения, сближение)
│   ├── deduplication/           # Защита от дублей, Debounce и Cooldown
│   └── incident_client.py       # Отказоустойчивый Outbox-клиент регистрации инцидентов
├── linq_tools/                  # Утилиты инспекции ONNX, квантования и компиляции под LinQ TPU
├── app/                         # Бэкенд-сервис на FastAPI
│   ├── routes/                  # Маршруты API (инциденты, камеры, тепловизоры, аналитика)
│   ├── db/                      # Модели данных SQLAlchemy и сессии БД
│   ├── services/                # Бизнес-логика, Camera Hub, уведомления, воркеры
│   └── storage/                 # Слой хранения стоп-кадров (Local Disk, S3 / MinIO)
├── frontend/                    # Веб-интерфейс диспетчера (React 19, TypeScript, Vite)
├── training/                    # Модуль дообучения детектора YOLOv8 и экспорта под LinQ TPU
├── tests/                       # Набор модульных и интеграционных тестов (221 тест)
├── run.py                       # Точка входа запуска бэкенда FastAPI
├── run_worker.py                # Точка входа независимого CV-воркера видеоаналитики
├── linq_adapter.py              # Официальный адаптер рантайма LinQ TPU
├── docker-compose.yml           # Стек контейнеризации (PostgreSQL, Backend)
├── Dockerfile                   # Образ бэкенда с зависимостями OpenCV и CV Engine
└── start.ps1 / start.bat        # Скрипты быстрого запуска системы на рабочей станции
```

---

## 🚀 Быстрый старт

### Вариант 1. Локальный запуск (разработка и проверка)

#### 1. Подготовка окружения
```bash
# Клонирование и переход в проект
cd LinQproject

# Создание и активация виртуального окружения
python -m venv .venv
# Windows (PowerShell):
.\.venv\Scripts\Activate.ps1
# Linux / macOS:
source .venv/bin/activate

# Установка зависимостей
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

#### 2. Конфигурация параметров
Скопируйте шаблон переменных окружения:
```bash
cp .env.example .env
```
*(При необходимости укажите токен Telegram-бота `LINQ_TG_TOKEN` для получения оперативных уведомлений).*

#### 3. Инициализация базы данных
```bash
alembic upgrade head
```

#### 4. Запуск сервиса LenQsec Backend
```bash
python run.py
```
* Веб-интерфейс доступен по адресу: `http://localhost:8000` (или `http://localhost:3000` при запуске dev-сервера фронтенда).
* Интерактивная документация Swagger API: `http://localhost:8000/docs`.

#### 5. Запуск процесса видеоаналитики (CV Worker)
В отдельном терминале запустите обработку видеопотока:
```bash
# Режим инференса ONNX на CPU:
python run_worker.py --config configs/cv_engine.yaml --backend onnx_cpu --model models/onnx/safety_yolov8n.onnx

# Либо режим инференса на LinQ TPU:
python run_worker.py --config configs/cv_engine.yaml --backend linq_tpu --model models/tpu/safety_yolov8_h1m.tpu
```

---

### Вариант 2. Запуск в Docker Compose

Для развертывания полного стека с СУБД PostgreSQL 16:
```bash
# 1. Запуск базы данных и бэкенда
docker compose up -d postgres
docker compose run --rm backend alembic upgrade head
docker compose up --build
```

---

### Вариант 3. Быстрый запуск одной командой (Windows)

Для автоматического запуска Backend, Frontend и видеомоста go2rtc:
```powershell
.\start.ps1
```
Для запуска в автономном режиме без Node.js:
```powershell
.\start.ps1 -Standalone
```

---

## 🧪 Запуск тестов и верификация

Все тесты запускаются с помощью `pytest` в изолированном тестовом окружении:
```powershell
.\.venv\Scripts\python.exe -m pytest -v
```
Результат верификации: **221 passed, 0 failed**.

---

## 🌡️ Интеграция радиометрических тепловизоров

Тепловизоры в LenQsec интегрированы в общий контур камер, инцидентов и дашборда. При первом запуске в системе уже зарегистрирована тестовая камера `THERMAL-OSF-TEST`.

1. **Регистрация промышленного тепловизора (`POST /api/v1/cameras`)**:
```json
{
  "id": "THERMAL-01",
  "name": "Тепловизор привода конвейера №2",
  "zone": "Цех № 1",
  "workshop": "Корпус А",
  "site_id": "north",
  "camera_type": "thermal",
  "online": true,
  "fps": 10
}
```

2. **Передача радиометрической матрицы температур (`POST /api/v1/thermal/cameras/{camera_id}/frame`)**:
```python
import requests

# Передача двумерного массива температур в °C напрямую из SDK тепловизора
requests.post(
    "http://127.0.0.1:8000/api/v1/thermal/cameras/THERMAL-01/frame",
    json={"temperatures": temperature_matrix_celsius.tolist()},
    timeout=3,
).raise_for_status()
```

3. **Проверка на реальном образце OSF**:
```bash
python tools/replay_thermal_csv.py data/thermal/osf_sample/Beef_LR_38_20_30.csv --repeats 7 --interval 1
```

---

## 🧩 Добавление новых правил безопасности

Все правила безопасности и сигнатуры инцидентов сосредоточены в `engine/rules/registry.py`. Для создания нового сценария контроля:

1. Создайте класс-наследник `BaseRule` в директории `engine/rules/` и реализуйте метод `evaluate(tracks, frame_meta)`, возвращающий список нарушений `RuleViolation`.
2. Зарегистрируйте правило в словаре `RULE_REGISTRY`: укажите фабрику правила, заголовок инцидента, тип и рекомендуемое действие для оператора.
3. Добавьте юнит-тесты в `tests/`.

---

## 💬 Подключение корпоративных мессенджеров

Создайте Python-модуль с адаптером, унаследованным от `BaseMessengerAdapter` (`app/services/notifications`):

```python
import os
from app.services.notifications import BaseMessengerAdapter

class EnterpriseChatAdapter(BaseMessengerAdapter):
    channel = "enterprise_chat"

    def __init__(self, manager):
        self.endpoint = os.environ["CORP_CHAT_ENDPOINT"]
        self.token = os.environ["CORP_CHAT_TOKEN"]

    def send_alert(self, subscriber, event, snapshot_path=None):
        # Отправка нового инцидента в чат смены
        ...
        return message_id, "card"

    def update_alert(self, delivery, event):
        # Обновление существующего сообщения при смене статуса или повторном нарушении
        ...

def create_adapter(manager):
    adapter = EnterpriseChatAdapter(manager)
    manager.store.upsert_subscriber(adapter.channel, "shift-safety", "Дежурная смена ОТ", "channel")
    return adapter
```

В `.env` укажите фабрику адаптера:
```dotenv
LINQ_MESSENGER_ADAPTERS=my_plugin:create_adapter
CORP_CHAT_ENDPOINT=https://chat.company.local/api
CORP_CHAT_TOKEN=secret_token
```

---

## 🛠️ Спецификация платформы LinQ TPU
* **Аппаратный профиль**: `TPU_H1M` (платформа `h1m`).
* **Арифметика чипа**: Аппаратные вычисления с плавающей точкой **FP19** и целочисленное квантование **INT8**.
* **Пайплайн компиляции**: `PyTorch (.pt) -> ONNX (статичный shape 640x640) -> tpu_framework (квантование O1/O5) -> .tpu`.
* **Рантайм инференса**: Библиотека `pytpu` (`/dev/tpu*`).
* **Подробное руководство**: см. [docs/HACKATHON_LINQ_SPECS.md](docs/HACKATHON_LINQ_SPECS.md) и [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

---

## 📚 Документация проекта

* 🏗️ [Архитектура и потоки данных системы](docs/ARCHITECTURE.md)
* 📡 [Полная спецификация REST API и WebSockets](docs/API.md)
* 🌡️ [Руководство по тепловизионному мониторингу](docs/THERMAL_GUIDE.md)
* 🚢 [Инструкция по развертыванию (Edge, Docker, Cloud TPU)](docs/DEPLOYMENT.md)
* 🖥️ [Руководство оператора диспетчерского центра](docs/OPERATOR_GUIDE.md)
* 🎯 [Инструкция сдачи и CV-контракт](CV_HANDOFF.md)
* 🤖 [Архитектурный контракт агентов](AGENTS.md)
