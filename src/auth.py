from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from datetime import datetime
from src.models import db, User

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Page de connexion"""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember = request.form.get('remember', False)
        
        if not username or not password:
            flash('Veuillez remplir tous les champs', 'error')
            return render_template('auth/login.html')
        
        user = User.query.filter_by(username=username).first()
        
        if user is None or not user.check_password(password):
            flash('Nom d\'utilisateur ou mot de passe incorrect', 'error')
            return render_template('auth/login.html')
        
        if not user.is_active:
            flash('Votre compte est désactivé', 'error')
            return render_template('auth/login.html')
        
        # Connexion réussie
        user.last_login = datetime.utcnow()
        db.session.commit()
        
        login_user(user, remember=remember)
        flash(f'Bienvenue {user.full_name or user.username} !', 'success')
        
        # Redirection
        next_page = request.args.get('next')
        if next_page and next_page.startswith('/'):
            return redirect(next_page)
        return redirect(url_for('main.dashboard'))
    
    return render_template('auth/login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Page d'inscription (admin seulement en production)"""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')
        full_name = request.form.get('full_name', '').strip()
        role = request.form.get('role', 'user')
        
        # Validations
        if not username or not email or not password:
            flash('Tous les champs sont obligatoires', 'error')
            return render_template('auth/register.html')
        
        if password != confirm:
            flash('Les mots de passe ne correspondent pas', 'error')
            return render_template('auth/register.html')
        
        if len(password) < 6:
            flash('Le mot de passe doit faire au moins 6 caractères', 'error')
            return render_template('auth/register.html')
        
        if User.query.filter_by(username=username).first():
            flash('Ce nom d\'utilisateur existe déjà', 'error')
            return render_template('auth/register.html')
        
        if User.query.filter_by(email=email).first():
            flash('Cet email est déjà utilisé', 'error')
            return render_template('auth/register.html')
        
        # Création de l'utilisateur
        user = User(
            username=username,
            email=email,
            full_name=full_name,
            role=role
        )
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        flash('Compte créé avec succès ! Vous pouvez vous connecter.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/register.html')


@auth_bp.route('/logout')
@login_required
def logout():
    """Déconnexion"""
    logout_user()
    flash('Vous êtes déconnecté', 'info')
    return redirect(url_for('auth.login'))