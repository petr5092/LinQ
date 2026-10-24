# LinQ Safety Guard: инструкция запуска

> [!NOTE]
> Актуальная инструкция CV-конвейера, проверенный статус, команды CPU/TPU и чек-лист сдачи находятся в документе [CV_HANDOFF.md](CV_HANDOFF.md).

## Быстрый старт (локальная проверка)

```bash
# 1. Установка зависимостей
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 2. Запуск бэкенда FastAPI
python run.py

# 3. Запуск CV Worker (с инференсом на CPU через ONNX или в режиме MOCK)
python run_worker.py --config configs/cv_engine.yaml --backend onnx_cpu --model models/onnx/safety_yolov8n.onnx
```

## Уведомления в Telegram

Бот работает через long polling: публичный адрес и webhook не нужны. Токены хранятся в `.env` (образец — `.env.example`).
В чат смены приходят нарушения: кадр с выделенным человеком, камера, зона, время, тип нарушения и интерактивные кнопки изменения статуса.

## Что реализовано из требований кейса

| Требование | Где |
|---|---|
| Приём видеопотоков и файлов | `engine/sources/`: файл, RTSP, последовательность изображений |
| Распознавание нейросетью | `engine/inference/` (YOLOv8/v9/v11, ONNX Runtime, LinQ TPU) |
| Оповещение с кадром, камерой, временем, типом | FastAPI REST API, WebSocket-рассылка, Telegram-бот |
| Подавление повторов и дедупликация | `engine/deduplication/anti_spam.py` с temporal debounce |
| Отказоустойчивая доставка событий | `engine/incident_client.py` (Outbox pattern с дисковой очередью) |
| Инференс на LinQ TPU с замерами | `linq_adapter.py`, `bench.py` |
| Разметка опасных зон | `engine/rules/danger_zone.py`, конфигурации в `configs/cv_engine.yaml` |

Подробный чек-лист подготовки к защите и команды для LinQ TPU приведены в [CV_HANDOFF.md](CV_HANDOFF.md).
