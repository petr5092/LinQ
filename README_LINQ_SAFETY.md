# LenQsec: Инструкция быстрого запуска и оперативной проверки

> [!NOTE]
> Актуальный статус E2E-конвейера, проверенные замеры и чек-лист подготовки к защите находятся в документе [CV_HANDOFF.md](CV_HANDOFF.md).  
> Детальное описание архитектуры доступно в [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), а спецификация API — в [docs/API.md](docs/API.md).

---

## ⚡ Быстрый старт (локальная проверка)

```bash
# 1. Установка зависимостей
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 2. Применение миграций базы данных
alembic upgrade head

# 3. Запуск веб-сервиса и API LenQsec (порт 8000)
python run.py

# 4. Запуск CV Worker (с инференсом на CPU через ONNX или в режиме MOCK)
python run_worker.py --config configs/cv_engine.yaml --backend onnx_cpu --model models/onnx/safety_yolov8n.onnx
```

---

## 📱 Оперативные уведомления в Telegram

Бот работает через long polling: публичный IP-адрес и настройка webhook не требуются.  
1. Создайте бота в Telegram через `@BotFather` командой `/newbot`.
2. Укажите полученный токен в `.env`:
   ```dotenv
   LINQ_TG_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
   LINQ_PUBLIC_URL=http://localhost:3000
   ```
3. В чат дежурной смены приходят карточки нарушений:
   * Фотоснимок или термограмма с выделением зоны и нарушителя;
   * Название камеры, опасная зона, таймштамп события;
   * Тип нарушения и рекомендуемое действие для оператора;
   * Интерактивные кнопки прямого изменения статуса (`В работу`, `Ложное`, `Закрыть`).
4. Повторные срабатывания того же правила в течение 5 минут автоматически обновляют существующее сообщение, исключая заспамливание чата.

---

## 📋 Реализованные требования кейса LinQ

| Требование кейса | Реализация в системе LenQsec |
|---|---|
| Приём видеопотоков и файлов | `engine/sources/`: поддержка RTSP, WebRTC, файлов MP4, MJPEG и упорядоченных изображений |
| Распознавание нейросетью | `engine/inference/`: поддержка моделей YOLOv8/YOLO11, ONNX Runtime CPU и LinQ TPU (H1M) |
| Радиометрические тепловизоры | `app/routes/thermal.py`, `configs/thermal_cameras.yaml`: прием матриц °C, палитра, контроль порогов |
| Оперативное оповещение диспетчера | FastAPI REST API, WebSocket-рассылка в реальном времени, Telegram-бот с inline-кнопками |
| Подавление повторов и ложных тревог | `engine/deduplication/anti_spam.py`: temporal debounce ($N$ кадров) и cooldown по `Track ID` |
| Гарантированная доставка событий | `engine/incident_client.py`: Outbox pattern с дисковой очередью при потере соединения |
| Аппаратный инференс на LinQ TPU | `linq_adapter.py`, `bench.py`, `tools/stand_tpu_bridge.py` |
| Разметка опасных зон оператором | `engine/rules/danger_zone.py`, интерактивный полигональный редактор в веб-интерфейсе |
| Аналитика и сменные отчеты | Полноценный операторский веб-дашборд (React 19 + TypeScript), экспорт инцидентов в CSV |

Подробный чек-лист подготовки к защите и команды для LinQ TPU приведены в [CV_HANDOFF.md](CV_HANDOFF.md).
