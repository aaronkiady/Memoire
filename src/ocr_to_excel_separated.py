# src/ocr_to_excel_separated.py

import os
import re
from datetime import datetime

import cv2
import easyocr
from openpyxl import Workbook


# ============================================================
# CONFIGURATION
# ============================================================

PREPROCESSED_DIR = "paper_preprocessed"
OUTPUT_DIR = "."

# Langues OCR
OCR_LANGUAGES = ["fr", "en"]

# CPU par défaut
USE_GPU = False


# ============================================================
# OUTILS TEXTE
# ============================================================

def normalize_text(text):
    """
    Nettoie légèrement un texte OCR sans détruire les informations.
    """
    if text is None:
        return ""

    text = str(text)

    # Espaces multiples
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def normalize_label(text):
    """
    Normalise un libellé pour faciliter sa détection.

    Exemples :
        "Nom :"       -> "nom"
        "NOM:"        -> "nom"
        "Matricule :" -> "matricule"
        "Affaire :"   -> "affaire"
    """
    text = normalize_text(text).lower()

    # Suppression des deux-points et caractères parasites
    text = re.sub(r"[:：]+", "", text)

    # OCR peut parfois lire des variantes
    text = text.replace("é", "e")
    text = text.replace("è", "e")
    text = text.replace("ê", "e")

    return text.strip()


def is_label(text):
    """
    Indique si le texte correspond à un de nos labels.
    """
    label = normalize_label(text)

    labels = {
        "nom",
        "matricule",
        "affaire",
        "site",
    }

    return label in labels


def is_matricule(text):
    """
    Vérifie si le texte ressemble à un matricule numérique.
    """
    text = normalize_text(text)

    # Exemple : 25424
    return bool(re.fullmatch(r"\d{3,10}", text))


def clean_value(text):
    """
    Nettoyage d'une valeur OCR.
    """
    text = normalize_text(text)

    # Suppression de ':' au début/à la fin
    text = text.strip(" :;|")

    return text.strip()


# ============================================================
# EXTRACTION DU NOM
# ============================================================

def extract_nom(texts):
    """
    Extrait le nom.

    IMPORTANT :
    Dans ton OCR, on obtient :

        ANTHONIO
        Nom :
        Matricule :
        25424
        Affaire :
        LOG
        ...

    Donc le nom est AVANT le label "Nom :".

    On privilégie :
        1. le texte immédiatement précédent "Nom"
        2. le premier texte plausible avant "Nom"
        3. un texte situé avant les autres labels
    """

    if not texts:
        return ""

    cleaned = [clean_value(t) for t in texts]

    # --------------------------------------------------------
    # 1. Chercher le label "Nom"
    # --------------------------------------------------------

    for i, text in enumerate(cleaned):

        if normalize_label(text) == "nom":

            # Le nom est généralement juste avant "Nom :"
            if i > 0:
                candidate = clean_value(cleaned[i - 1])

                if candidate and not is_label(candidate):
                    if not is_matricule(candidate):
                        return candidate

            # Si le texte précédent n'est pas exploitable,
            # chercher quelques positions avant.
            for j in range(i - 2, max(-1, i - 5), -1):

                if j < 0:
                    break

                candidate = clean_value(cleaned[j])

                if not candidate:
                    continue

                if is_label(candidate):
                    continue

                if is_matricule(candidate):
                    continue

                return candidate

    # --------------------------------------------------------
    # 2. Fallback
    # --------------------------------------------------------
    #
    # Si "Nom :" n'a pas été reconnu, le nom est très souvent
    # le premier texte OCR.
    # --------------------------------------------------------

    for text in cleaned:

        if not text:
            continue

        if is_label(text):
            continue

        if is_matricule(text):
            continue

        return text

    return ""


# ============================================================
# EXTRACTION DU MATRICULE
# ============================================================

def extract_matricule(texts):
    """
    Extrait le matricule.

    On cherche d'abord un nombre proche du label Matricule.

    Exemple :

        Matricule :
        25424

    ou éventuellement :

        25424
        Matricule :
    """

    if not texts:
        return ""

    cleaned = [clean_value(t) for t in texts]

    # --------------------------------------------------------
    # 1. Recherche autour du label
    # --------------------------------------------------------

    for i, text in enumerate(cleaned):

        if normalize_label(text) == "matricule":

            # Cas classique : valeur après le label
            for j in range(i + 1, min(len(cleaned), i + 4)):

                candidate = clean_value(cleaned[j])

                if is_matricule(candidate):
                    return candidate

            # Cas de ton OCR : valeur potentiellement avant
            for j in range(i - 1, max(-1, i - 4), -1):

                candidate = clean_value(cleaned[j])

                if is_matricule(candidate):
                    return candidate

    # --------------------------------------------------------
    # 2. Fallback : premier nombre plausible
    # --------------------------------------------------------

    for text in cleaned:

        if is_matricule(text):
            return text

    return ""


# ============================================================
# EXTRACTION DE L'AFFAIRE
# ============================================================

def extract_affaire(texts):
    """
    Extrait l'affaire.

    Exemple OCR :

        Affaire :
        LOG

    ou :

        LOG
        Affaire :

    On cherche donc des deux côtés du label.
    """

    if not texts:
        return ""

    cleaned = [clean_value(t) for t in texts]

    # --------------------------------------------------------
    # 1. Recherche autour du label
    # --------------------------------------------------------

    for i, text in enumerate(cleaned):

        if normalize_label(text) == "affaire":

            # Priorité à la valeur APRÈS le label
            for j in range(i + 1, min(len(cleaned), i + 4)):

                candidate = clean_value(cleaned[j])

                if not candidate:
                    continue

                if is_label(candidate):
                    continue

                if is_matricule(candidate):
                    continue

                # Éviter certains textes trop courts inutiles
                return candidate

            # Puis valeur AVANT le label
            for j in range(i - 1, max(-1, i - 4), -1):

                candidate = clean_value(cleaned[j])

                if not candidate:
                    continue

                if is_label(candidate):
                    continue

                if is_matricule(candidate):
                    continue

                return candidate

    return ""


# ============================================================
# EXTRACTION DU SITE
# ============================================================

def extract_site(texts):
    """
    Extrait le site.

    Exemple :

        BASE
        Site :

    ou :

        Site :
        BASE

    On cherche autour du label "Site".
    """

    if not texts:
        return ""

    cleaned = [clean_value(t) for t in texts]

    # --------------------------------------------------------
    # 1. Recherche autour du label
    # --------------------------------------------------------

    for i, text in enumerate(cleaned):

        if normalize_label(text) == "site":

            # Valeur après le label
            for j in range(i + 1, min(len(cleaned), i + 4)):

                candidate = clean_value(cleaned[j])

                if not candidate:
                    continue

                if is_label(candidate):
                    continue

                if is_matricule(candidate):
                    continue

                return candidate

            # Valeur avant le label
            for j in range(i - 1, max(-1, i - 4), -1):

                candidate = clean_value(cleaned[j])

                if not candidate:
                    continue

                if is_label(candidate):
                    continue

                if is_matricule(candidate):
                    continue

                return candidate

    # --------------------------------------------------------
    # 2. Fallback spécifique à ton format
    # --------------------------------------------------------
    #
    # Si "Site" n'est pas détecté mais que BASE est présent,
    # on peut le récupérer.
    # --------------------------------------------------------

    for text in cleaned:

        if text.upper() == "BASE":
            return text

    return ""


# ============================================================
# EXTRACTION COMPLETE
# ============================================================

def extract_fields(texts):
    """
    Extrait tous les champs depuis la liste OCR.
    """

    nom = extract_nom(texts)
    matricule = extract_matricule(texts)
    affaire = extract_affaire(texts)
    site = extract_site(texts)

    return {
        "Nom": nom,
        "Matricule": matricule,
        "Affaire": affaire,
        "Site": site,
    }


# ============================================================
# SUPPRESSION DES DOUBLONS OCR
# ============================================================

def remove_duplicate_texts(texts):
    """
    Supprime les doublons exacts en conservant l'ordre.
    """

    result = []
    seen = set()

    for text in texts:

        text = normalize_text(text)

        if not text:
            continue

        key = text.lower()

        if key in seen:
            continue

        seen.add(key)
        result.append(text)

    return result


# ============================================================
# OCR D'UNE IMAGE
# ============================================================

def run_ocr_on_image(reader, image_path):
    """
    Effectue l'OCR sur une image.

    Retourne uniquement les textes.
    """

    image = cv2.imread(image_path)

    if image is None:
        print(f"   ❌ Impossible de lire l'image : {image_path}")
        return []

    try:
        results = reader.readtext(
            image,
            detail=1,
            paragraph=False
        )

    except Exception as e:
        print(f"   ❌ Erreur OCR : {e}")
        return []

    texts = []

    for result in results:

        if not result:
            continue

        # EasyOCR detail=1 :
        # [bounding_box, text, confidence]
        if len(result) < 2:
            continue

        text = normalize_text(result[1])

        if not text:
            continue

        texts.append(text)

    return remove_duplicate_texts(texts)


# ============================================================
# CREATION EXCEL
# ============================================================

def create_excel(rows, output_path):
    """
    Crée le fichier Excel final.
    """

    workbook = Workbook()

    worksheet = workbook.active
    worksheet.title = "Présence"

    headers = [
        "Nom",
        "Matricule",
        "Affaire",
        "Site",
        "Image",
        "Texte_Brut",
    ]

    # --------------------------------------------------------
    # En-têtes
    # --------------------------------------------------------

    for column, header in enumerate(headers, start=1):

        cell = worksheet.cell(
            row=1,
            column=column,
            value=header
        )

        cell.font = cell.font.copy(bold=True)

    # --------------------------------------------------------
    # Données
    # --------------------------------------------------------

    for row_index, row_data in enumerate(rows, start=2):

        worksheet.cell(
            row=row_index,
            column=1,
            value=row_data.get("Nom", "")
        )

        worksheet.cell(
            row=row_index,
            column=2,
            value=row_data.get("Matricule", "")
        )

        worksheet.cell(
            row=row_index,
            column=3,
            value=row_data.get("Affaire", "")
        )

        worksheet.cell(
            row=row_index,
            column=4,
            value=row_data.get("Site", "")
        )

        worksheet.cell(
            row=row_index,
            column=5,
            value=row_data.get("Image", "")
        )

        worksheet.cell(
            row=row_index,
            column=6,
            value=row_data.get("Texte_Brut", "")
        )

    # --------------------------------------------------------
    # Largeur des colonnes
    # --------------------------------------------------------

    widths = {
        "A": 25,
        "B": 15,
        "C": 20,
        "D": 20,
        "E": 55,
        "F": 100,
    }

    for column, width in widths.items():
        worksheet.column_dimensions[column].width = width

    # --------------------------------------------------------
    # Figer la première ligne
    # --------------------------------------------------------

    worksheet.freeze_panes = "A2"

    # --------------------------------------------------------
    # Sauvegarde
    # --------------------------------------------------------

    workbook.save(output_path)

    return output_path


# ============================================================
# PIPELINE PRINCIPAL
# ============================================================

def run_pipeline_for_flask():
    """
    Fonction appelée par app.py :

        excel_path = run_pipeline_for_flask()

    Elle parcourt les images présentes dans :

        paper_preprocessed/

    puis effectue :

        Image
          ↓
        EasyOCR
          ↓
        Extraction Nom
        Extraction Matricule
        Extraction Affaire
        Extraction Site
          ↓
        Excel
    """

    print()
    print("=" * 60)
    print("🚀 EXTRACTION OCR AVEC PRÉTRAITEMENT AMÉLIORÉ")
    print("=" * 60)
    print()

    # --------------------------------------------------------
    # Vérification du dossier
    # --------------------------------------------------------

    if not os.path.exists(PREPROCESSED_DIR):

        print(
            f"❌ Dossier introuvable : {PREPROCESSED_DIR}"
        )

        return None

    # --------------------------------------------------------
    # Recherche des images
    # --------------------------------------------------------

    allowed_extensions = (
        ".png",
        ".jpg",
        ".jpeg",
        ".bmp",
        ".webp",
        ".tif",
        ".tiff",
    )

    image_files = []

    for filename in sorted(os.listdir(PREPROCESSED_DIR)):

        if filename.lower().endswith(allowed_extensions):

            image_files.append(filename)

    if not image_files:

        print(
            f"❌ Aucune image trouvée dans {PREPROCESSED_DIR}"
        )

        return None

    print(
        f"📸 {len(image_files)} image(s) à traiter"
    )

    print()

    # --------------------------------------------------------
    # Initialisation EasyOCR
    # --------------------------------------------------------

    print("🔄 Initialisation OCR...")

    try:

        reader = easyocr.Reader(
            OCR_LANGUAGES,
            gpu=USE_GPU
        )

    except Exception as e:

        print(
            f"❌ Impossible d'initialiser EasyOCR : {e}"
        )

        return None

    print("✅ OCR prêt")
    print()

    # --------------------------------------------------------
    # Résultats
    # --------------------------------------------------------

    rows = []

    # --------------------------------------------------------
    # Traitement image par image
    # --------------------------------------------------------

    for filename in image_files:

        image_path = os.path.join(
            PREPROCESSED_DIR,
            filename
        )

        print("-" * 60)
        print(f"📄 Traitement : {filename}")

        # ----------------------------------------------------
        # OCR
        # ----------------------------------------------------

        texts = run_ocr_on_image(
            reader,
            image_path
        )

        print(
            f"   📝 {len(texts)} texte(s) unique(s) détecté(s)"
        )

        if texts:

            print(
                f"   📌 Aperçu: {texts[:8]}"
            )

        else:

            print(
                "   ⚠️ Aucun texte détecté"
            )

        # ----------------------------------------------------
        # Extraction des champs
        # ----------------------------------------------------

        fields = extract_fields(texts)

        nom = fields["Nom"]
        matricule = fields["Matricule"]
        affaire = fields["Affaire"]
        site = fields["Site"]

        # ----------------------------------------------------
        # Logs
        # ----------------------------------------------------

        print(
            f"   👤 Nom: {nom}"
        )

        print(
            f"   🆔 Matricule: {matricule}"
        )

        print(
            f"   📋 Affaire: {affaire}"
        )

        print(
            f"   📍 Site: {site}"
        )

        # ----------------------------------------------------
        # Texte brut
        # ----------------------------------------------------

        texte_brut = " | ".join(texts)

        # ----------------------------------------------------
        # Ligne Excel
        # ----------------------------------------------------

        row = {
            "Nom": nom,
            "Matricule": matricule,
            "Affaire": affaire,
            "Site": site,
            "Image": filename,
            "Texte_Brut": texte_brut,
        }

        rows.append(row)

    # --------------------------------------------------------
    # Vérification
    # --------------------------------------------------------

    if not rows:

        print()
        print("❌ Aucun résultat OCR exploitable")
        return None

    # --------------------------------------------------------
    # Nom du fichier Excel
    # --------------------------------------------------------

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    output_filename = (
        f"presence_{timestamp}.xlsx"
    )

    output_path = os.path.join(
        OUTPUT_DIR,
        output_filename
    )

    # --------------------------------------------------------
    # Création Excel
    # --------------------------------------------------------

    create_excel(
        rows,
        output_path
    )

    print()
    print("=" * 60)
    print(
        f"✅ Excel créé : {output_filename}"
    )
    print("=" * 60)
    print()

    return output_path


# ============================================================
# EXECUTION DIRECTE
# ============================================================

if __name__ == "__main__":

    run_pipeline_for_flask()