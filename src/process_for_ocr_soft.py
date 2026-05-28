import cv2
import os
import shutil

INPUT_DIR = "paper_crops"
OUTPUT_DIR = "paper_preprocessed"


def run_preprocess_soft():
    """
    Prétraitement OCR doux :
    - enlève la saleté du papier
    - évite le sur-contraste
    - respecte les écritures faibles
    """

    if not os.path.exists(INPUT_DIR):
        print("❌ paper_crops introuvable")
        return 0

    # Nettoyage du dossier de sortie
    shutil.rmtree(OUTPUT_DIR, ignore_errors=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    processed = 0

    for filename in os.listdir(INPUT_DIR):
        if not filename.lower().endswith((".jpg", ".png")):
            continue

        path = os.path.join(INPUT_DIR, filename)
        img = cv2.imread(path)

        if img is None:
            continue

        # 1. Grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # 2. Débruitage intelligent
        denoised = cv2.fastNlMeansDenoising(
            gray,
            h=15,
            templateWindowSize=7,
            searchWindowSize=21
        )

        # 3. CLAHE doux
        clahe = cv2.createCLAHE(
            clipLimit=1.8,
            tileGridSize=(8, 8)
        )
        enhanced = clahe.apply(denoised)

        # 4. Flou léger final
        final = enhanced
        
        output_path = os.path.join(
            OUTPUT_DIR,
            filename.rsplit(".", 1)[0] + "_clean.png"
        )

        cv2.imwrite(output_path, final)
        processed += 1

    print(f"🧼 Prétraitement OCR soft terminé ({processed} images)")
    return processed