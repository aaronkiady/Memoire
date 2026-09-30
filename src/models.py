"""
Modèles de base de données pour l'authentification
"""
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()


class User(UserMixin, db.Model):
    """Modèle utilisateur avec rôles"""
    
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default='user')  # 'admin' ou 'user'
    full_name = db.Column(db.String(120))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    
    # Historique des imports
    uploads = db.relationship('UploadHistory', backref='user', lazy=True)
    
    def set_password(self, password):
        """Hash le mot de passe"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Vérifie le mot de passe"""
        return check_password_hash(self.password_hash, password)
    
    def is_admin(self):
        """Vérifie si l'utilisateur est admin"""
        return self.role == 'admin'
    
    def __repr__(self):
        return f'<User {self.username} ({self.role})>'


class UploadHistory(db.Model):
    """Historique des imports de fichiers"""
    
    __tablename__ = 'upload_history'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    filename = db.Column(db.String(255))
    excel_path = db.Column(db.String(255))
    nb_images = db.Column(db.Integer, default=0)
    nb_personnes = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Upload {self.filename} by {self.user_id}>'