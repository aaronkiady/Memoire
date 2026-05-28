import easyocr
import cv2
import os
import pandas as pd
from datetime import datetime
import re

INPUT_DIR = "paper_preprocessed"
CONFIDENCE_MIN = 0.3


def clean_text(text):
    return text.strip().replace(":", "").replace("|", "")

def parse_paper_data(texts):

    data = {
        "Nom": "",
        "Matricule": "",
        "Affaire": "",
        "Site": ""
    }

    # Nettoyage
    cleaned = []

    for t in texts:

        txt = (
            t.strip()
            .replace(":", "")
            .replace("|", "")
        )

        if txt:
            cleaned.append(txt)

    # ==========================
    # MOTS À IGNORER
    # ==========================

    labels = [
        "nom",
        "matricule",
        "matrcule",
        "matricuie",
        "affaire",
        "affare",
        "aftaire",
        "attaire",
        "site"
    ]

    # ==========================
    # ANALYSE
    # ==========================

    for i, text in enumerate(cleaned):

        low = text.lower()

        # Ignore labels
        if low in labels:
            continue

        # ======================
        # MATRICULE
        # ======================

        digits = re.sub(r"\D", "", text)

        if digits.isdigit():

            # Matricule = généralement 5 chiffres
            if len(digits) == 5 and not data["Matricule"]:
                data["Matricule"] = digits
                continue

            # Affaire = autre nombre
            if len(digits) >= 5 and not data["Affaire"]:
                data["Affaire"] = digits
                continue

        # ======================
        # SITE
        # ======================

        if (
            "rn" in low
            or "helios" in low
            or "ankorondrano" in low
        ):

            data["Site"] = text
            continue

        # ======================
        # NOM
        # ======================

        if (
            not data["Nom"]
            and len(text) <= 25
            and not any(char.isdigit() for char in text)
        ):

            data["Nom"] = text

    return data

def run_pipeline_for_flask():

    reader = easyocr.Reader(['fr'], gpu=False)

    all_data = []

    files = sorted(os.listdir(INPUT_DIR))

    for file in files:

        if not file.endswith(".png"):
            continue

        path = os.path.join(INPUT_DIR, file)

        img = cv2.imread(path)

        if img is None:
            continue

        # OCR
        results = reader.readtext(
            img,
            detail=1,
            paragraph=False,
            width_ths=0.7,
            height_ths=0.7
        )

        # Tri TOP -> BOTTOM
        results = sorted(results, key=lambda x: x[0][0][1])

        texts = []

        for bbox, text, conf in results:

            if conf >= CONFIDENCE_MIN:

                clean = text.strip()

                if clean:
                    texts.append(clean)

        print("\n====================")
        print(file)
        print(texts)

        paper_data = parse_paper_data(texts)

        paper_data["Image"] = file
        paper_data["Texte_Brut"] = " | ".join(texts)

        all_data.append(paper_data)

        print("Nom:", paper_data["Nom"])
        print("Matricule:", paper_data["Matricule"])
        print("Affaire:", paper_data["Affaire"])
        print("Site:", paper_data["Site"])

    if not all_data:
        print("❌ Aucun résultat")
        return None

    df = pd.DataFrame(all_data)

    cols = [
        "Nom",
        "Matricule",
        "Affaire",
        "Site",
        "Image",
        "Texte_Brut"
    ]

    df = df[cols]

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    excel_path = f"presence_{timestamp}.xlsx"

    with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:

        df.to_excel(
            writer,
            sheet_name="Presences",
            index=False
        )

        worksheet = writer.sheets["Presences"]

        # Auto largeur
        for column in worksheet.columns:

            max_length = 0

            column_letter = column[0].column_letter

            for cell in column:

                try:
                    value = str(cell.value)

                    if len(value) > max_length:
                        max_length = len(value)

                except:
                    pass

            adjusted_width = min(max_length + 5, 60)

            worksheet.column_dimensions[column_letter].width = adjusted_width

    print(f"\n✅ Excel créé : {excel_path}")

    return excel_path


if __name__ == "__main__":
    run_pipeline_for_flask()