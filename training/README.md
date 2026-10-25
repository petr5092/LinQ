# LenQsec CV — Дообучение детекторов и экспорт моделей под LinQ TPU

Модуль предназначен для подготовки датасетов, дообучения нейросетевых моделей детекции (YOLOv8/YOLO11) и экспорта оптимизированных ONNX-графов для последующей компиляции в бинарный формат отечественных ИИ-ускорителей **LinQ TPU (H1M)**.

Данный модуль **полностью автономен** и запускается на рабочей станции с графическим ускорителем (GPU / CUDA). Компиляция в формат LinQ TPU (`.tpu`) выполняется downstream-инструментами `linq_tools/compile_model.py`.

---

## 📁 Структура каталога датасета

Датасет формируется в стандартном формате YOLO:

```text
data/safety_dataset/
  data.yaml
  images/
    train/*.jpg
    val/*.jpg
    test/*.jpg
  labels/
    train/*.txt
    val/*.txt
    test/*.txt
```

Пример файла конфигурации `data.yaml`:

```yaml
path: .
train: images/train
val: images/val
test: images/test
names: [person, helmet, vest]
```

Разметка меток YOLO: `class_id x_center y_center width height` с нормализованными координатами от 0 до 1. Отсутствие текстового файла метки допускается для верифицированных негативных кадров (без нарушений).

> [!IMPORTANT]
> Для сценария контроля опасных зон без проверки СИЗ допустимо использовать одноклассовую конфигурацию `names: [person]`. Категорически запрещено переименовывать классы стандартных COCO-весов под классы СИЗ без фактического дообучения модели на предметном датасете охраны труда.
> Разделение на train/val/test должно производиться строго по отдельным видеороликам и камерам, чтобы исключить утечку соседних кадров между выборками.

---

## 🚀 Настройка и обучение на GPU-машине

1. Установите Python 3.11/3.12 и совместимый пакет **PyTorch с поддержкой CUDA**:  
   [Официальный гайд по установке PyTorch](https://pytorch.org/get-started/locally/).

2. Установите зависимости модуля обучения:
   ```bash
   python -m pip install -r training/requirements.txt
   ```

3. Проведите предварительную валидацию датасета:
   ```bash
   python -m training.validate_dataset --data data/safety_dataset/data.yaml
   ```

4. Запустите цикл обучения детектора:
   ```bash
   python -m training.train --data data/safety_dataset/data.yaml --weights yolov8s.pt --epochs 100 --imgsz 640 --batch 8 --device 0
   ```

5. Быстрая программная проверка пайплайна без обучения:
   ```bash
   python -m training.train --data data/safety_dataset/data.yaml --check-only
   ```

---

## 📤 Валидация и экспорт под LinQ TPU

После завершения обучения сохраняются веса `runs/linq/safety*/weights/best.pt` и файл манифеста.

1. Оценка качества на отложенной тестовой выборке и экспорт в ONNX:
   ```bash
   python -m training.evaluate_export --weights runs/linq/safety/weights/best.pt --data data/safety_dataset/data.yaml --split val --device 0 --export --out models/onnx/safety_yolov8.onnx
   python -m training.evaluate_export --weights runs/linq/safety/weights/best.pt --data data/safety_dataset/data.yaml --split test --device 0
   ```

2. **Требования к экспорту для чипа LinQ TPU**:
   * Размер пачки (batch): строго **1**;
   * Входное разрешение: статическое **$1 \times 3 \times 640 \times 640$** (динамические оси `dynamic_axes` запрещены);
   * Формат выхода: сырой выход детектирующей головы (detect head) без встроенного post-NMS;
   * Цветовое пространство: RGB, порядок NCHW, нормализация в диапазоне $[0, 1]$.

3. Инспекция экспортированного графа:
   ```bash
   python -m linq_tools.inspect_onnx models/onnx/safety_yolov8.onnx --out model_info.json
   ```

4. Компиляция в формат `.tpu` для ускорителя LinQ H1M:
   ```bash
   python -m linq_tools.compile_model --onnx models/onnx/safety_yolov8.onnx --calibration data/calibration --samples 50 --out models/tpu/safety_yolov8_h1m.tpu
   ```
