"""
Application Flask - Système OCR Présence avec authentification
"""
from flask import Flask, render_template, request, send_file, redirect, url_for, flash
from flask_login import LoginManager, login_required, current_user
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import os

# Modèles et blueprints
from src.models import db, User
from src.auth import auth_bp
from src.routes import main_bp

# Modules de traitement
from src.crop_paper import run_crop
from src.process_for_ocr_soft import run_preprocess_soft
from src.ocr_to_excel_separated import run_pipeline_for_flask

# ============================================================
# CHARGEMENT DES VARIABLES D'ENVIRONNEMENT
# ============================================================
load_dotenv()

# ============================================================
# CRÉATION DE L'APPLICATION
# ============================================================
app = Flask(__name__)

# ============================================================
# CONFIGURATION
# ============================================================
app.config['SECRET_KEY'] = os.getenv(
    'SECRET_KEY',
    'dev-secret-key-change-in-production-123456789'
)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
    'DATABASE_URL',
    'sqlite:///users.db'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50 MB max

# Création des dossiers nécessaires
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs("paper_crops", exist_ok=True)
os.makedirs("paper_preprocessed", exist_ok=True)

# ============================================================
# INITIALISATION DE LA BASE DE DONNÉES
# ============================================================
db.init_app(app)

# ============================================================
# CONFIGURATION DE FLASK-LOGIN
# ============================================================
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Veuillez vous connecter pour accéder à cette page.'
login_manager.login_message_category = 'warning'


@login_manager.user_loader
def load_user(user_id):
    """Charge l'utilisateur depuis la session"""
    return User.query.get(int(user_id))


# ============================================================
# ENREGISTREMENT DES BLUEPRINTS
# ============================================================
app.register_blueprint(auth_bp)
app.register_blueprint(main_bp)


# ============================================================
# ROUTE D'UPLOAD (PROTÉGÉE - ADMIN UNIQUEMENT)
# ============================================================
@app.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    """
    Route d'upload et traitement des photos
    Accessible uniquement aux utilisateurs connectés (admin recommandé)
    """
    # Vérifier que l'utilisateur est admin
    if not current_user.is_admin():
        flash('Accès refusé : vous devez être administrateur', 'error')
        return redirect(url_for('main.dashboard'))
    
    if request.method == "POST":
        files = request.files.getlist("images")

        if not files or files[0].filename == "":
            flash('Aucune image sélectionnée', 'error')
            return redirect(url_for('main.upload'))

        # Nettoyage des anciens crops et preprocess
        for d in ["paper_crops", "paper_preprocessed"]:
            if os.path.exists(d):
                for f in os.listdir(d):
                    try:
                        os.remove(os.path.join(d, f))
                    except:
                        pass

        # ==========================================
        # 1. Sauvegarde + YOLO crop
        # ==========================================
        for file in files:
            filename = secure_filename(file.filename)
            if not filename:
                continue
            image_path = os.path.join(UPLOAD_DIR, filename)
            file.save(image_path)

            # YOLO détecte et crop les papiers
            try:
                run_crop(image_path)
            except Exception as e:
                print(f"Erreur YOLO: {e}")
                continue

        # ==========================================
        # 2. Prétraitement OCR soft
        # ==========================================
        try:
            run_preprocess_soft()
        except Exception as e:
            print(f"Erreur prétraitement: {e}")
            flash('Erreur lors du prétraitement', 'error')
            return redirect(url_for('main.upload'))

        # ==========================================
        # 3. OCR → Excel
        # ==========================================
        try:
            excel_path = run_pipeline_for_flask()
        except Exception as e:
            print(f"Erreur OCR: {e}")
            flash('Erreur lors de l\'OCR', 'error')
            return redirect(url_for('main.upload'))

        if not excel_path or not os.path.exists(excel_path):
            flash('Aucun résultat OCR', 'error')
            return redirect(url_for('main.upload'))

        # ==========================================
        # 4. Enregistrer dans l'historique
        # ==========================================
        try:
            from src.models import UploadHistory
            history = UploadHistory(
                user_id=current_user.id,
                filename=f"{len(files)} fichier(s)",
                excel_path=excel_path,
                nb_images=len(files),
                nb_personnes=0
            )
            db.session.add(history)
            db.session.commit()
        except Exception as e:
            print(f"Erreur historique: {e}")

        # ==========================================
        # 5. Envoyer le fichier Excel
        # ==========================================
        flash('Fichier Excel généré avec succès !', 'success')
        return send_file(excel_path, as_attachment=True)

    # GET : afficher le formulaire d'upload
    return render_template("upload.html")


# ============================================================
# ROUTE RACINE - REDIRECTION
# ============================================================
@app.route("/")
def index():
    """
    Redirige vers le dashboard si connecté,
    sinon vers la page de login
    """
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return redirect(url_for('auth.login'))

# INITIALISATION DE LA BASE DE DONNÉES

def init_database():
    """
    Initialise la base de données
    Crée les tables et un admin par défaut si vide
    """
    with app.app_context():
        db.create_all()
        
        # Créer un admin par défaut si aucun utilisateur
        if User.query.count() == 0:
            # Admin par défaut
            admin = User(
                username='admin',
                email='admin@presence.local',
                full_name='Administrateur RH',
                role='admin',
                is_active=True
            )
            admin.set_password('admin123')
            db.session.add(admin)
            
            # Utilisateur normal par défaut
            user = User(
                username='user',
                email='user@presence.local',
                full_name='Utilisateur Test',
                role='user',
                is_active=True
            )
            user.set_password('user123')
            db.session.add(user)
            
            db.session.commit()
            
            print("\n" + "="*60)
            print("✅ BASE DE DONNÉES INITIALISÉE")
            print("="*60)
            print("👨‍💼 ADMIN :")
            print("   Utilisateur : admin")
            print("   Mot de passe : admin123")
            print()
            print("👤 UTILISATEUR :")
            print("   Utilisateur : user")
            print("   Mot de passe : user123")
            print("="*60)
            print("⚠️  CHANGEZ CES MOTS DE PASSE EN PRODUCTION !")
            print("="*60 + "\n")
        else:
            print("✅ Base de données déjà initialisée")


# ============================================================
# LANCEMENT DE L'APPLICATION
# ============================================================
if __name__ == "__main__":
    # Initialiser la BDD
    init_database()
    
    # Afficher les informations de démarrage
    print("\n" + "="*60)
    print("🚀 DÉMARRAGE DE L'APPLICATION OCR PRÉSENCE")
    print("="*60)
    print(f"🌐 URL : http://localhost:5001")
    print(f"📁 Upload : {os.path.abspath(UPLOAD_DIR)}")
    print(f"💾 Base de données : {app.config['SQLALCHEMY_DATABASE_URI']}")
    print("="*60 + "\n")
    
    # Lancer l'application
    app.run(
        port=5001,
        debug=True
    )