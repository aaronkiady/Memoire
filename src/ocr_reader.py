import easyocr
import cv2
import os

INPUT_DIR = "paper_preprocessed"
CONFIDENCE_MIN = 0.3

reader = easyocr.Reader(
    ['fr'],
    gpu=False
)

for file in os.listdir(INPUT_DIR):
    if not file.endswith(".png"):
        continue

    path = os.path.join(INPUT_DIR, file)
    img = cv2.imread(path)

    results = reader.readtext(
        img,
        detail=1,
        paragraph=False
    )

    print(f"\n📄 {file}")
    print("-" * 40)

    if len(results) == 0:
        print("❌ Aucun texte détecté")
        continue

    for bbox, text, conf in results:
        if conf >= CONFIDENCE_MIN:
            clean_text = text.strip()
            print(f"✔ {clean_text}  ({conf:.2f})")
