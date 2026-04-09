# ocr_to_excel_separated.py
import cv2
import os
import re
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from datetime import datetime
import easyocr

class PresenceOCRProcessor:
    def __init__(self):
        self.input_dir = "paper_preprocessed"
        self.output_excel = f"presence_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        self.confidence_min = 0.3
        self.max_text_length = 100
        
        # Initialiser EasyOCR avec Français
        self.reader = easyocr.Reader(['fr'], gpu=False)
        
        # Patterns pour détecter les matricules (à adapter selon vos données)
        self.matricule_patterns = [
            r'^\d{5}$',           # 5 chiffres exactement (ex: 25468)
            r'^\d{4,6}$',         # 4 à 6 chiffres
            r'^\d{3,8}$',         # 3 à 8 chiffres
        ]
        
        self.results = []
        
    def is_matricule(self, text):
        """Détermine si le texte est un matricule (numéro)"""
        # Nettoyer le texte
        clean_text = ''.join(c for c in text if c.isalnum())
        
        # Vérifier si c'est uniquement des chiffres
        if clean_text.isdigit():
            # Vérifier la longueur typique d'un matricule
            if 3 <= len(clean_text) <= 10:
                return True, clean_text
        
        # Vérifier les patterns spécifiques
        for pattern in self.matricule_patterns:
            if re.match(pattern, clean_text):
                return True, clean_text
                
        return False, clean_text
    
    def is_name(self, text):
        """Détermine si le texte est un nom (principalement des lettres)"""
        # Nettoyer (garder lettres, espaces, tirets, apostrophes)
        clean_text = ''.join(c for c in text if c.isalpha() or c in " -'")
        
        # Doit avoir au moins 2 caractères
        if len(clean_text) < 2:
            return False, clean_text
            
        # Doit contenir principalement des lettres
        letter_count = sum(1 for c in clean_text if c.isalpha())
        if letter_count / len(clean_text) < 0.7:  # Au moins 70% de lettres
            return False, clean_text
            
        # Format typique d'un nom (première lettre majuscule)
        # Mais on ne force pas pour éviter les faux négatifs
        
        return True, clean_text.strip()
    
    def process_single_image(self, img_path, filename):
        """Traite une image et extrait noms et matricules"""
        img = cv2.imread(img_path)
        if img is None:
            print(f"⚠ Impossible de lire {filename}")
            return [], []
        
        # OCR avec configuration optimisée
        try:
            ocr_results = self.reader.readtext(
                img,
                detail=1,
                paragraph=False,
                width_ths=0.5,    # Regroupement horizontal
                height_ths=0.5,   # Regroupement vertical
                min_size=5,       # Taille minimale du texte
                text_threshold=0.4  # Seuil de confiance du texte
            )
        except Exception as e:
            print(f"❌ Erreur OCR sur {filename}: {e}")
            return [], []
        
        names = []
        matricules = []
        other_texts = []
        
        for bbox, text, conf in ocr_results:
            if conf < self.confidence_min:
                continue
                
            # Ignorer les textes trop longs (probablement du bruit)
            if len(text) > self.max_text_length:
                continue
            
            # Vérifier si c'est un matricule
            is_mat, clean_mat = self.is_matricule(text)
            if is_mat:
                matricules.append((clean_mat, conf))
                continue
            
            # Vérifier si c'est un nom
            is_nom, clean_nom = self.is_name(text)
            if is_nom:
                names.append((clean_nom, conf))
                continue
            
            # Sinon, autre texte
            other_texts.append((text, conf))
        
        # Log pour débogage
        print(f"\n📄 {filename}")
        if names:
            print(f"   👤 Noms détectés: {[n[0] for n in names]}")
        if matricules:
            print(f"   🔢 Matricules: {[m[0] for m in matricules]}")
        if other_texts:
            print(f"   📝 Autres: {[o[0] for o in other_texts]}")
        
        return names, matricules
    
    def match_names_with_matricules(self, names, matricules):
        """Associe les noms aux matricules (logique simple)"""
        pairs = []
        
        # Cas 1: Même nombre de noms et matricules → association directe
        if len(names) == len(matricules) > 0:
            for i in range(len(names)):
                pairs.append({
                    'Nom': names[i][0],
                    'Matricule': matricules[i][0]
                })
        
        # Cas 2: Plus de noms que de matricules
        elif len(names) > len(matricules) and matricules:
            for i in range(len(matricules)):
                pairs.append({
                    'Nom': names[i][0] if i < len(names) else "INCONNU",
                    'Matricule': matricules[i][0]
                })
        
        # Cas 3: Plus de matricules que de noms
        elif len(matricules) > len(names) and names:
            for i in range(len(names)):
                pairs.append({
                    'Nom': names[i][0],
                    'Matricule': matricules[i][0] if i < len(matricules) else "INCONNU"
                })
        
        # Cas 4: Aucune correspondance claire
        else:
            # On met tout dans des colonnes séparées
            for name, conf in names:
                pairs.append({
                    'Nom': name,
                    'Matricule': ''
                })
            for mat, conf in matricules:
                pairs.append({
                    'Nom': '',
                    'Matricule': mat
                })
        
        return pairs
    
    def process_all_images(self):
        """Traite toutes les images du dossier"""
        print("🔍 Début du traitement OCR...")
        print("=" * 60)
        
        # Lister les fichiers images
        image_files = [f for f in sorted(os.listdir(self.input_dir)) 
                      if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
        
        if not image_files:
            print("❌ Aucune image trouvée dans", self.input_dir)
            return
        
        print(f"📁 {len(image_files)} images à traiter")
        
        # Traiter chaque image
        for filename in image_files:
            img_path = os.path.join(self.input_dir, filename)
            
            # Extraire noms et matricules
            names, matricules = self.process_single_image(img_path, filename)
            
            # Associer noms et matricules
            pairs = self.match_names_with_matricules(names, matricules)
            
            # Ajouter au résultat global
            for pair in pairs:
                self.results.append({
                    'Image': filename,
                    **pair  # Décompose le dictionnaire pair
                })
        
        print(f"\n✅ Traitement terminé : {len(self.results)} entrées extraites")
        
    def create_excel(self):
        """Crée un fichier Excel avec mise en forme"""
        if not self.results:
            print("❌ Aucune donnée à exporter")
            return
        
        # Convertir en DataFrame
        df = pd.DataFrame(self.results)
        
        # Réorganiser les colonnes
        column_order = ['Image', 'Nom', 'Matricule']
        df = df[column_order]
        
        # Trier par image puis par matricule
        df = df.sort_values(['Image', 'Matricule'])
        
        # Créer le fichier Excel
        with pd.ExcelWriter(self.output_excel, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Présences', index=False)
            
            # Accéder au workbook pour styliser
            workbook = writer.book
            worksheet = writer.sheets['Présences']
            
            # ===== STYLES =====
            # Styles d'en-tête
            header_font = Font(bold=True, color="FFFFFF", size=11)
            header_fill = PatternFill(
                start_color="2E75B6",  # Bleu
                end_color="2E75B6",
                fill_type="solid"
            )
            
            # Styles des cellules
            border = Border(
                left=Side(style='thin', color="000000"),
                right=Side(style='thin', color="000000"),
                top=Side(style='thin', color="000000"),
                bottom=Side(style='thin', color="000000")
            )
            
            center_align = Alignment(horizontal='center', vertical='center')
            left_align = Alignment(horizontal='left', vertical='center')
            
            # ===== MISE EN FORME =====
            # 1. Largeur des colonnes
            col_widths = {
                'A': 25,  # Image
                'B': 30,  # Nom
                'C': 15,  # Matricule
            }
            
            for col, width in col_widths.items():
                worksheet.column_dimensions[col].width = width
            
            # 2. Styliser les en-têtes
            for col in range(1, 4):
                cell = worksheet.cell(row=1, column=col)
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = center_align
                cell.border = border
            
            # 3. Styliser les données
            for row in range(2, len(df) + 2):
                # Alternance de couleurs
                if row % 2 == 0:
                    fill = PatternFill(
                        start_color="F2F2F2",
                        end_color="F2F2F2",
                        fill_type="solid"
                    )
                else:
                    fill = PatternFill(
                        start_color="FFFFFF",
                        end_color="FFFFFF",
                        fill_type="solid"
                    )
                
                for col in range(1, 4):
                    cell = worksheet.cell(row=row, column=col)
                    cell.border = border
                    cell.fill = fill
                    
                    # Alignement spécifique
                    if col == 1:  # Image
                        cell.alignment = left_align
                    elif col == 2:  # Nom
                        cell.alignment = left_align
                        cell.font = Font(name='Arial', size=11)
                    elif col == 3:  # Matricule
                        cell.alignment = center_align
                        cell.font = Font(name='Consolas', bold=True, size=11)
                        
            
            # 4. Ajouter un titre
            worksheet.insert_rows(1)
            worksheet.merge_cells('A1:C1')
            title_cell = worksheet['A1']
            title_cell.value = "📋 LISTE DE PRÉSENCE - SYSTÈME OCR"
            title_cell.font = Font(bold=True, size=14, color="1F4E79")
            title_cell.alignment = Alignment(horizontal='center', vertical='center')
            title_cell.fill = PatternFill(
                start_color="DDEBF7",
                end_color="DDEBF7",
                fill_type="solid"
            )
            
            # 5. Ajouter des statistiques
            stats_row = len(df) + 4
            
            worksheet.cell(row=stats_row, column=1, value="📊 STATISTIQUES").font = Font(bold=True, size=12)
            worksheet.cell(row=stats_row + 1, column=1, value="Total personnes:")
            worksheet.cell(row=stats_row + 1, column=2, value=len(df))
            
            worksheet.cell(row=stats_row + 2, column=1, value="Noms extraits:")
            worksheet.cell(row=stats_row + 2, column=2, value=df['Nom'].astype(bool).sum())
            
            worksheet.cell(row=stats_row + 3, column=1, value="Matricules extraits:")
            worksheet.cell(row=stats_row + 3, column=2, value=df['Matricule'].astype(bool).sum())
            
            # 6. Ajouter des filtres
            worksheet.auto_filter.ref = f"A2:C{len(df) + 1}"

        
        print(f"✅ Fichier Excel créé : {self.output_excel}")
        
    def generate_summary_report(self):
        """Génère un rapport de synthèse"""
        if not self.results:
            return
            
        df = pd.DataFrame(self.results)
        
        print("\n" + "=" * 60)
        print("📊 RAPPORT DE SYNTHÈSE")
        print("=" * 60)
        
        # Statistiques globales
        total_entries = len(df)
        with_names = df['Nom'].astype(bool).sum()
        with_matricules = df['Matricule'].astype(bool).sum()
        complete_entries = df[(df['Nom'].astype(bool)) & (df['Matricule'].astype(bool))].shape[0]
        
        print(f"\n📈 Statistiques globales:")
        print(f"   • Total des entrées: {total_entries}")
        print(f"   • Avec nom: {with_names} ({with_names/total_entries*100:.1f}%)")
        print(f"   • Avec matricule: {with_matricules} ({with_matricules/total_entries*100:.1f}%)")
        print(f"   • Complets (nom+matricule): {complete_entries} ({complete_entries/total_entries*100:.1f}%)")
        
        # Aperçu des données
        print(f"\n🔍 Aperçu des données:")
        print(df.head(10).to_string(index=False))
        
        # Suggestions
        print(f"\n💡 Suggestions:")
        if complete_entries < total_entries * 0.8:  # Moins de 80% complets
            print("   ⚠ Certaines entrées sont incomplètes")
            print("   → Vérifiez les images problématiques")
            print("   → Ajustez peut-être le prétraitement")
        
        print(f"\n📁 Fichier généré: {self.output_excel}")
        
    def run(self):
        """Exécute le pipeline complet"""
        print("🚀 Lancement du traitement OCR...")
        print("=" * 60)
        
        # 1. Traiter les images
        self.process_all_images()
        
        if not self.results:
            print("❌ Aucun résultat obtenu")
            return
        
        # 2. Exporter vers Excel
        self.create_excel()
        
        # 3. Générer un rapport
        self.generate_summary_report()

    def process_uploaded_images(image_paths, output_dir="exports"):
        """Fonction adaptée pour l'application Flask"""
        processor = PresenceOCRProcessor()
    
        # Simulez le traitement
        results = []
        for i, img_path in enumerate(image_paths):
            results.append({
                'Image': f"paper_{i+1}_clean.png",
                'Nom': f"Nom_{i+1}",
                'Matricule': f"{10000 + i}"
            })
    
        # Créez Excel
        df = pd.DataFrame(results)
        output_path = os.path.join(output_dir, f"presence_{datetime.now().strftime('%Y_%m_%d')}.xlsx")
    
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Présences', index=False)
    
        return output_path
    
def run_pipeline_for_flask():
    """
    Pipeline complet appelé par Flask
    Retourne le chemin du fichier Excel généré
    """
    processor = PresenceOCRProcessor()
    processor.process_all_images()
    if not processor.results:
        return None
    processor.create_excel()
    return processor.output_excel

if __name__ == "__main__":
    # Vérifier que le dossier d'entrée existe
    if not os.path.exists("paper_preprocessed"):
        print("❌ Dossier 'paper_preprocessed' introuvable")
        print("⚠ Exécutez d'abord:")
        print("   1. python crop_paper.py")
        print("   2. python process_for_ocr_enhanced.py")
    else:
        processor = PresenceOCRProcessor()
        processor.run()