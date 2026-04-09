from ultralytics import YOLO
import cv2
import os

MODEL_PATH = "runs/detect/train/weights/best.pt"
CONF_THRESHOLD = 0.4

model = YOLO(MODEL_PATH) 

def run_crop(image_path):
    output_dir = "paper_crops"
    os.makedirs(output_dir, exist_ok=True)

    img = cv2.imread(image_path)
    if img is None:
        return 0

    results = model(img, conf=CONF_THRESHOLD)
    boxes = results[0].boxes

    if not boxes:
        return 0

    base_name = os.path.splitext(os.path.basename(image_path))[0]
    count = 0

    for i, box in enumerate(boxes):
        x1, y1, x2, y2 = map(int, box.xyxy[0])
        crop = img[y1:y2, x1:x2]

        output_path = os.path.join(
            output_dir,
            f"{base_name}_paper_{i+1}.jpg"
        )
        cv2.imwrite(output_path, crop)
        count += 1

    return count
