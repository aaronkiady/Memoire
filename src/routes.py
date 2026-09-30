"""
Routes principales (dashboard, upload, etc.)
"""
from flask import Blueprint, render_template, request, send_file, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from datetime import datetime
import os

from src.models import db, UploadHistory
from src.crop_paper import run_crop
from src.process_for_ocr_soft import run_preprocess_soft
from src.ocr_to_excel_separated import run_pipeline_for_flask

main_bp = Blueprint('main', __name__)


def admin_required(f):
    """Décorateur : accès admin uniquement"""
    from functools import wraps
    from flask import abort
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


@main_bp.route('/')
@login_required
def dashboard():
    """Page d'accueil après connexion"""
    # Récupérer les statistiques
    total_uploads = UploadHistory.query.count()
    my_uploads = UploadHistory.query.filter_by(user_id=current_user.id).count()
    
    # Derniers imports
    recent_uploads = UploadHistory.query.order_by(
        UploadHistory.created_at.desc()
    ).limit(5).all()
    
    return render_template(
        'dashboard.html',
        total_uploads=total_uploads,
        my_uploads=my_uploads,
        recent_uploads=recent_uploads
    )


@main_bp.route('/upload', methods=['GET', 'POST'])
@login_required
@admin_required
def upload():
    """Upload et traitement des photos (admin uniquement)"""
    if request.method == 'POST':
        files = request.files.getlist('images')
        
        if not files or files[0].filename == '':
            flash('Aucune image sélectionnée', 'error')
            return redirect(url_for('main.upload'))
        
        # Nettoyage
        for d in ['paper_crops', 'paper_preprocessed']:
            if os.path.exists(d):
                for f in os.listdir(d):
                    os.remove(os.path.join(d, f))
        
        # Sauvegarde + YOLO
        for file in files:
            filename = secure_filename(file.filename)
            image_path = os.path.join('uploads', filename)
            file.save(image_path)
            run_crop(image_path)
        
        # Prétraitement
        run_preprocess_soft()
        
        # OCR → Excel
        excel_path = run_pipeline_for_flask()
        
        if not excel_path:
            flash('Aucun résultat OCR', 'error')
            return redirect(url_for('main.upload'))
        
        # Enregistrement dans l'historique
        history = UploadHistory(
            user_id=current_user.id,
            filename=f"{len(files)} fichier(s)",
            excel_path=excel_path,
            nb_images=len(files),
            nb_personnes=0  # À calculer si besoin
        )
        db.session.add(history)
        db.session.commit()
        
        # Envoi du fichier
        return send_file(excel_path, as_attachment=True)
    
    return render_template('upload.html')


@main_bp.route('/history')
@login_required
def history():
    """Historique des imports"""
    if current_user.is_admin():
        # Admin voit tout
        uploads = UploadHistory.query.order_by(
            UploadHistory.created_at.desc()
        ).all()
    else:
        # User voit seulement les siens
        uploads = UploadHistory.query.filter_by(
            user_id=current_user.id
        ).order_by(UploadHistory.created_at.desc()).all()
    
    return render_template('history.html', uploads=uploads)


@main_bp.route('/download/<int:history_id>')
@login_required
def download(history_id):
    """Télécharger un fichier depuis l'historique"""
    history = UploadHistory.query.get_or_404(history_id)
    
    # Vérifier les permissions
    if not current_user.is_admin() and history.user_id != current_user.id:
        flash('Accès refusé', 'error')
        return redirect(url_for('main.history'))
    
    if not os.path.exists(history.excel_path):
        flash('Fichier introuvable', 'error')
        return redirect(url_for('main.history'))
    
    return send_file(history.excel_path, as_attachment=True)


@main_bp.route('/admin/users')
@login_required
@admin_required
def admin_users():
    """Gestion des utilisateurs (admin)"""
    from src.models import User
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin/users.html', users=users)


@main_bp.route('/admin/users/<int:user_id>/toggle', methods=['POST'])
@login_required
@admin_required
def toggle_user(user_id):
    """Activer/désactiver un utilisateur"""
    from src.models import User
    user = User.query.get_or_404(user_id)
    
    if user.id == current_user.id:
        flash('Vous ne pouvez pas vous désactiver vous-même', 'error')
        return redirect(url_for('main.admin_users'))
    
    user.is_active = not user.is_active
    db.session.commit()
    
    flash(f'Utilisateur {"activé" if user.is_active else "désactivé"}', 'success')
    return redirect(url_for('main.admin_users'))