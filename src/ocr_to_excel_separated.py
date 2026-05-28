import easyocr
import cv2
import os
import pandas as pd
from datetime import datetime
import re
import numpy as np

INPUT_DIR = "paper_preprocessed"
CONFIDENCE_MIN = 0.3


def preprocess_image_for_ocr(img):
    """
    Prétraitement avancé de l'image pour améliorer la reconnaissance OCR
    """
    # Convertir en niveaux de gris si nécessaire
    if len(img.shape) == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray = img.copy()
    
    # 1. Redimensionnement (si image trop petite)
    height, width = gray.shape
    if height < 500 or width < 500:
        scale = max(1200 / height, 1200 / width)
        new_width = int(width * scale)
        new_height = int(height * scale)
        gray = cv2.resize(gray, (new_width, new_height), interpolation=cv2.INTER_CUBIC)
    
    # 2. Amélioration du contraste (CLAHE)
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8,8))
    enhanced = clahe.apply(gray)
    
    # 3. Réduction du bruit
    denoised = cv2.fastNlMeansDenoising(enhanced, None, 10, 7, 21)
    
    # 4. Neteté (sharpening)
    kernel = np.array([[-1,-1,-1],
                       [-1, 9,-1],
                       [-1,-1,-1]])
    sharpened = cv2.filter2D(denoised, -1, kernel)
    
    # 5. Binarisation adaptative (pour les textes sur fond variable)
    binary = cv2.adaptiveThreshold(sharpened, 255, 
                                   cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                   cv2.THRESH_BINARY, 11, 2)
    
    # Retourner plusieurs versions pour maximiser les chances
    return [gray, enhanced, denoised, sharpened, binary]


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
        "nom", "n0m", "norn", "nome", "non", "nomm", "n0n",
        "matricule", "matrcule", "matricuie", "matricu1e", "matricuIe",
        "affaire", "affare", "aftaire", "attaire", "affairee",
        "site", "s1te", "síte",
        "mlle", "mile"
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
        # MATRICULE & AFFAIRE
        # ======================
        digits = re.sub(r"\D", "", text)
        
        if digits.isdigit():
            # Matricule = 4-5 chiffres (parfois G suivi de chiffres)
            if 4 <= len(digits) <= 5 and not data["Matricule"]:
                data["Matricule"] = digits
                continue
            
            # Affaire = 6-7 chiffres ou 4-5 chiffres avec XT
            if (len(digits) >= 6 or (len(digits) >= 4 and 'xt' in low)) and not data["Affaire"]:
                data["Affaire"] = digits
                continue
            
            # Fallback pour les nombres de 5 chiffres
            if len(digits) == 5 and not data["Matricule"] and not data["Affaire"]:
                # Par défaut, c'est un matricule
                data["Matricule"] = digits
                continue

        # ======================
        # MATRICULE avec G (ex: G2103, G2304)
        # ======================
        g_match = re.search(r'[Gg](\d{3,5})', text)
        if g_match and not data["Matricule"]:
            data["Matricule"] = "G" + g_match.group(1)
            continue

        # ======================
        # SITE
        # ======================
        site_keywords = [
            "rn", "rn13", "rn 13", 
            "unops", 
            "gasyplast", "gasy plast",
            "ankorondrano", "helios",
            "vohilava", "manapatra", "Farafangana"
        ]
        
        low_clean = re.sub(r'[^a-z]', '', low)
        for keyword in site_keywords:
            keyword_clean = re.sub(r'[^a-z]', '', keyword)
            if keyword_clean in low_clean or keyword in low:
                data["Site"] = text
                break
        
        if data["Site"]:
            continue

        # ======================
        # NOM
        # ======================
        if (
            not data["Nom"]
            and len(text) <= 30
            and len(text) >= 3
            and not any(char.isdigit() for char in text)
            and not any(x in low for x in ['gps', 'camera', 'long', 'lat', 'egeco', 'stadium'])
        ):
            # Vérifier que c'est probablement un nom (majuscules ou première lettre majuscule)
            if text.isupper() or (text[0].isupper() and text[1:].islower()):
                data["Nom"] = text

    # ==========================
    # CORRECTIONS POST-TRAITEMENT
    # ==========================
    
    # Si le site contient des chiffres mal interprétés, nettoyer
    if data["Site"]:
        # Enlever les chiffres parasites
        data["Site"] = re.sub(r'\d+', '', data["Site"]).strip()
    
    # Si affaire contient "rn" ou "site", c'est une erreur
    if data["Affaire"] and ("RN" in data["Affaire"].upper() or "SITE" in data["Affaire"].upper()):
        data["Affaire"] = ""
    
    # Standardisation des sites
    site_mapping = {
        "rn13": "RN 13",
        "rn 13": "RN 13",
        "unops": "UNOPS",
        "gasyplast": "GASYPLAST",
        "gasy plast": "GASYPLAST",
        "helios": "HELIOS"
    }
    
    if data["Site"]:
        site_key = data["Site"].lower().replace(" ", "")
        if site_key in site_mapping:
            data["Site"] = site_mapping[site_key]

    return data

def run_pipeline_for_flask():
    reader = easyocr.Reader(['fr'], gpu=False)
    all_data = []
    files = sorted(os.listdir(INPUT_DIR))

    print("\n" + "="*60)
    print("🚀 EXTRACTION OCR AVEC PRÉTRAITEMENT AMÉLIORÉ")
    print("="*60)

    for file in files:
        if not file.endswith(".png"):
            continue

        path = os.path.join(INPUT_DIR, file)
        img = cv2.imread(path)

        if img is None:
            continue

        print(f"\n📄 Traitement: {file}")
        
        # ==========================================
        # AMÉLIORATION OCR : Multiples tentatives
        # ==========================================
        
        # Générer différentes versions de l'image
        img_versions = preprocess_image_for_ocr(img)
        
        all_texts = []
        best_results = []
        
        for version_name, version_img in zip(
            ["original", "contrast", "denoised", "sharp", "binary"], 
            img_versions
        ):
            # Paramètres adaptés selon la version
            if version_name == "binary":
                # Pour la version binarisée, utiliser paragraph=True
                # IMPORTANT: avec paragraph=True, EasyOCR retourne (bbox, text) seulement
                results = reader.readtext(
                    version_img,
                    detail=1,
                    paragraph=True,  # Groupe les textes proches
                    width_ths=0.5,
                    height_ths=0.5
                )
                # Gestion du cas paragraph=True (2 valeurs retournées)
                for item in results:
                    if len(item) == 2:  # Cas paragraph=True
                        bbox, text = item
                        conf = 0.8  # Confiance par défaut pour les paragraphs
                    else:  # Cas normal
                        bbox, text, conf = item
                    
                    if conf >= CONFIDENCE_MIN:
                        clean = text.strip()
                        if clean and len(clean) > 1:
                            all_texts.append((clean, conf, version_name))
            else:
                # Version standard (3 valeurs retournées)
                results = reader.readtext(
                    version_img,
                    detail=1,
                    paragraph=False,
                    width_ths=0.5,
                    height_ths=0.5
                )
                for bbox, text, conf in results:
                    if conf >= CONFIDENCE_MIN:
                        clean = text.strip()
                        if clean and len(clean) > 1:
                            all_texts.append((clean, conf, version_name))
        
        # Trier par confiance et dédoublonner
        all_texts.sort(key=lambda x: x[1], reverse=True)
        
        seen = set()
        unique_texts = []
        for text, conf, version in all_texts:
            if text not in seen:
                seen.add(text)
                unique_texts.append(text)
                best_results.append((text, conf, version))
        
        texts = unique_texts
        
        # Tri TOP -> BOTTOM (par position Y)
        # Pour avoir l'ordre correct, refaire OCR sur l'image originale pour les positions
        try:
            results_original = reader.readtext(
                img_versions[0],
                detail=1,
                paragraph=False
            )
            results_original = sorted(results_original, key=lambda x: x[0][0][1])
            texts_ordered = []
            for item in results_original:
                if len(item) == 3:
                    bbox, text, conf = item
                else:
                    bbox, text = item
                    conf = 0.8
                if conf >= CONFIDENCE_MIN and text in texts:
                    texts_ordered.append(text)
            texts = texts_ordered if texts_ordered else texts
        except Exception as e:
            print(f"   ⚠️ Erreur lors du tri: {e}")
            pass

        print(f"   📝 {len(texts)} texte(s) unique(s) détecté(s)")
        if texts:
            print(f"   📌 Aperçu: {texts[:5]}")

        paper_data = parse_paper_data(texts)
        paper_data["Texte_Brut"] = " | ".join(texts[:15])  # Limité pour lisibilité

        all_data.append(paper_data)

        print(f"   👤 Nom: {paper_data['Nom'] or '❌'}")
        print(f"   🆔 Matricule: {paper_data['Matricule'] or '❌'}")
        print(f"   📋 Affaire: {paper_data['Affaire'] or '❌'}")
        print(f"   📍 Site: {paper_data['Site'] or '❌'}")

    if not all_data:
        print("\n❌ Aucun résultat")
        return None

    df = pd.DataFrame(all_data)
    cols = ["Nom", "Matricule", "Affaire", "Site", "Texte_Brut"]
    df = df[cols]

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    excel_path = f"presence_{timestamp}.xlsx"

    with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name="Presences", index=False)
        worksheet = writer.sheets["Presences"]
        
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