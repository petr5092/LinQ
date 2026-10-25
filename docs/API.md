# Спецификация REST API и WebSockets системы LenQsec

Документ содержит полную спецификацию программных интерфейсов платформы **LenQsec** (версия API: `v1`).

* **Базовый URL**: `http://<host>:<port>/api/v1`
* **Интерактивная документация Swagger UI**: `http://<host>:<port>/docs`
* **Спецификация OpenAPI (JSON)**: `http://<host>:<port>/openapi.json`
* **WebSockets шлюз**: `ws://<host>:<port>/ws/events`

---

## 1. Инциденты (Incidents API)

### 1.1. Получение списка инцидентов
`GET /api/v1/incidents`

**Параметры запроса (Query Params)**:
* `status` *(string, опционально)*: фильтр по статусу (`new`, `investigating`, `resolved`, `false_positive`).
* `severity` *(string, опционально)*: фильтр по критичности (`critical`, `warning`, `info`).
* `camera_id` *(string, опционально)*: идентификатор камеры (например, `CAM-01`).
* `site_id` *(string, опционально)*: идентификатор площадки (например, `north`).
* `limit` *(int, по умолчанию 50)*: лимит выборки.
* `offset` *(int, по умолчанию 0)*: смещение пагинации.

**Пример ответа (200 OK)**:
```json
[
  {
    "id": "inc-4a2b91c8-01",
    "title": "Нарушение границы опасной зоны",
    "description": "Сотрудник находится в зоне работы мостового крана",
    "camera_id": "CAM-01",
    "zone": "Опасная зона № 1",
    "site_id": "north",
    "incident_type": "danger_zone",
    "severity": "critical",
    "status": "new",
    "timestamp": "2026-10-25T12:30:15Z",
    "image": "storage/snapshots/2026-10-25/inc_4a2b91c8_CAM-01.jpg",
    "person_id": "EMP-4091",
    "person_name": "Иванов Алексей Петрович",
    "action_required": "Немедленно покинуть опасный периметр"
  }
]
```

---

### 1.2. Регистрация инцидента из CV-воркера
`POST /api/v1/worker/incidents`

Используется независимым CV-воркером для фиксации подтвержденного нарушения.

**Тело запроса (JSON)**:
```json
{
  "title": "Отсутствие защитной каски",
  "camera_id": "CAM-02",
  "incident_type": "no_helmet",
  "severity": "warning",
  "zone": "Сборочный цех",
  "site_id": "north",
  "timestamp": "2026-10-25T12:35:00Z",
  "action_required": "Надеть СИЗ головы",
  "snapshot_base64": "/9j/4AAQSkZJRgABAQEAYABgAAD..."
}
```

**Ответ (201 Created)**: возвращает созданный объект инцидента. При повторной фиксации того же правила на той же камере в течение 5 минут возвращается обновленная существующая запись (200 OK).

---

### 1.3. Смена статуса инцидента
`PATCH /api/v1/incidents/{incident_id}/status`

**Тело запроса (JSON)**:
```json
{
  "status": "investigating"
}
```
*(Допустимые значения статуса: `new`, `investigating`, `resolved`, `false_positive`).*

**Действие**: обновляет статус в БД, рассылает WebSocket-событие `INCIDENT_STATUS_UPDATED` и обновляет карточку в Telegram-боте.

---

### 1.4. Экспорт журнала инцидентов в CSV
`GET /api/v1/incidents/export/csv`

Отдает файл `lenqsec-incidents.csv` в кодировке UTF-8 с BOM для корректного открытия в MS Excel.

---

## 2. Камеры и видеопотоки (Cameras API)

### 2.1. Получение списка камер
`GET /api/v1/cameras`

Возвращает перечень зарегистрированных камер, их типы (`rgb` или `thermal`), статус онлайн/офлайн и привязку к цехам и площадкам.

---

### 2.2. Регистрация новой камеры
`POST /api/v1/cameras`

**Тело запроса (JSON)**:
```json
{
  "id": "CAM-03",
  "name": "Зона разгрузки автотранспорта",
  "zone": "Складской комплекс",
  "workshop": "Корпус Б",
  "site_id": "north",
  "camera_type": "rgb",
  "online": true,
  "fps": 15
}
```

---

### 2.3. Получение стоп-кадра и видеопотока камеры
* `GET /api/v1/cameras/{camera_id}/snapshot.jpg`: отдает актуальный стоп-кадр с камеры (Content-Type: `image/jpeg`).
* `GET /api/v1/cameras/{camera_id}/frame.jpg`: отдает последний кадр из `CameraHub` (поддерживает RGB и ИК-термограммы).
* `GET /api/v1/cameras/{camera_id}/stream.mjpg`: MJPEG-стрим живого видео для отображения в стандартном теге `<img>` браузера.

---

## 3. Радиометрические тепловизоры (Thermal API)

### 3.1. Приём радиометрической матрицы температур
`POST /api/v1/thermal/cameras/{camera_id}/frame`

**Тело запроса (JSON)**:
```json
{
  "captured_at": "2026-10-25T12:00:00Z",
  "temperatures": [
    [24.1, 24.3, 24.5],
    [25.0, 88.4, 91.2]
  ]
}
```

**Ответ (200 OK)**:
```json
{
  "camera_id": "THERMAL-01",
  "status": "processed",
  "measurements": [
    {
      "zone_id": "motor_bearing",
      "zone_name": "Подшипниковый узел привода",
      "max_temperature_c": 91.2,
      "threshold_c": 75.0,
      "alarm": true
    }
  ],
  "heatmap_jpeg_base64": "/9j/4AAQSkZJRg..."
}
```

---

### 3.2. Получение актуальной термограммы
`GET /api/v1/thermal/cameras/{camera_id}/heatmap.jpg`

Возвращает визуализированный JPEG-кадр термограммы (colormap Inferno) для операторского интерфейса без необходимости декодирования Base64.

---

### 3.3. История показаний тепловизора
`GET /api/v1/thermal/cameras/{camera_id}/readings?limit=60`

Возвращает агрегированные временные ряды максимальных температур по зонам для построения графиков телеметрии.

---

## 4. Разметка опасных зон (Zones API)

* `GET /api/v1/zones`: список размеченных зон с координатами полигонов.
* `POST /api/v1/zones`: создание новой полигональной зоны.
* `PUT /api/v1/zones/{zone_id}`: обновление геометрии полигона или порогов.
* `DELETE /api/v1/zones/{zone_id}`: удаление зоны.

**Формат координат полигона**: массив нормализованных точек `[[x1, y1], [x2, y2], ..., [xn, yn]]`, где $0 \le x, y \le 1$.

---

## 5. WebSockets-протокол (`/ws/events`)

Канал передачи оперативных событий диспетчеру в реальном времени.

### 5.1. Событие создания инцидента
```json
{
  "event": "INCIDENT_CREATED",
  "data": {
    "id": "inc-9b1c-02",
    "title": "Опасное сближение с техникой",
    "camera_id": "CAM-01",
    "severity": "critical",
    "timestamp": "2026-10-25T12:40:00Z",
    "image": "storage/snapshots/2026-10-25/inc_9b1c_CAM-01.jpg"
  }
}
```

### 5.2. Событие обновления статуса
```json
{
  "event": "INCIDENT_STATUS_UPDATED",
  "data": {
    "id": "inc-9b1c-02",
    "status": "investigating"
  }
}
```
