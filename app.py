from flask import Flask, render_template, request, send_file
import os
from werkzeug.utils import secure_filename

from src.crop_paper import run_crop
from src.process_for_ocr_soft import run_preprocess_soft
from src.ocr_to_excel_separated import run_pipeline_for_flask

app = Flask(__name__)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@app.route("/", methods=["GET", "POST"])
def upload():
    if request.method == "POST":
        files = request.files.getlist("images")

        if not files or files[0].filename == "":
            return "❌ Aucune image sélectionnée", 400

        # Nettoyage uploads (sécurité)
        #for f in os.listdir(UPLOAD_DIR):
            #os.remove(os.path.join(UPLOAD_DIR, f))

        # Nettoyage des anciens crops et preprocess
        for d in ["paper_crops", "paper_preprocessed"]:
            if os.path.exists(d):
                for f in os.listdir(d):
                    os.remove(os.path.join(d, f))


        # 1. Sauvegarde + YOLO crop
        for file in files:
            filename = secure_filename(file.filename)
            image_path = os.path.join(UPLOAD_DIR, filename)
            file.save(image_path)

            # YOLO détecte et crop les papiers
            run_crop(image_path)

        # 2. Prétraitement OCR soft
        run_preprocess_soft()

        # 3. OCR → Excel
        excel_path = run_pipeline_for_flask()

        if not excel_path:
            return "❌ Aucun résultat OCR", 500

        return send_file(excel_path, as_attachment=True)

    return render_template("index.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
