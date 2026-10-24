
from pathlib import Path
import cv2
import random

DATASET = Path("data/safety_dataset")
IMAGES = DATASET / "images" / "train"
LABELS = DATASET / "labels" / "train"
OUTPUT = Path("data/annotation_preview")

CLASSES = ["person", "helmet", "vest"]
COLORS = [(255, 120, 0), (0, 220, 0), (0, 200, 255)]

OUTPUT.mkdir(parents=True, exist_ok=True)

images = [
    p for p in IMAGES.rglob("*")
    if p.suffix.lower() in {".jpg", ".jpeg", ".png"}
]

random.seed(42)
selected = random.sample(images, min(15, len(images)))

for image_path in selected:
    image = cv2.imread(str(image_path))
    if image is None:
        continue

    height, width = image.shape[:2]

    relative = image_path.relative_to(IMAGES)
    label_path = (LABELS / relative).with_suffix(".txt")

    if label_path.exists():
        for line in label_path.read_text().splitlines():
            values = line.split()
            if len(values) != 5:
                continue

            class_id = int(values[0])
            x, y, w, h = map(float, values[1:])

            x1 = int((x - w / 2) * width)
            y1 = int((y - h / 2) * height)
            x2 = int((x + w / 2) * width)
            y2 = int((y + h / 2) * height)

            color = COLORS[class_id]

            cv2.rectangle(
                image, (x1, y1), (x2, y2), color, 2
            )

            cv2.putText(
                image,
                CLASSES[class_id],
                (x1, max(20, y1 - 5)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                color,
                2
            )

    output_path = OUTPUT / image_path.name
    cv2.imwrite(str(output_path), image)

print(f"Saved {len(selected)} previews to {OUTPUT}")
