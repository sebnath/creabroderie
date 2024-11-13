# thread_management.py

from dataclasses import dataclass
from typing import Dict, List
import json
import os
import tkinter as tk
from tkinter import ttk
import sqlite3

@dataclass
class ThreadColor:
    """Classe représentant un fil de broderie"""
    brand: str
    reference: str
    name: str
    hex_color: str
    is_favorite: bool = False

class ThreadDatabase:
    """Gestionnaire de la base de données des fils"""
    def __init__(self):
        self.db_path = "threads.db"
        self.init_database()

    def init_database(self):
        """Initialise la base de données SQLite"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS threads (
                    brand TEXT,
                    reference TEXT,
                    name TEXT,
                    hex_color TEXT,
                    is_favorite INTEGER DEFAULT 0,
                    PRIMARY KEY (brand, reference)
                )
            ''')
            
            # Vérifier si la table est vide pour insérer les données initiales
            cursor.execute("SELECT COUNT(*) FROM threads")
            if cursor.fetchone()[0] == 0:
                self.load_initial_data()

    def load_initial_data(self):
        """Charge les données initiales des fils DMC"""
        dmc_threads = [
            ("DMC", "310", "Black", "#000000"),
            ("DMC", "Blanc", "White", "#FFFFFF"),
            ("DMC", "B5200", "Snow White", "#FFFFFF"),
            ("DMC", "606", "Bright Orange-Red", "#FF3800"),
            ("DMC", "699", "Christmas Green", "#115935"),
            # Ajoutez d'autres couleurs DMC ici
        ]
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.executemany(
                "INSERT INTO threads (brand, reference, name, hex_color) VALUES (?, ?, ?, ?)",
                dmc_threads
            )

    def get_all_threads(self, brand: str = None) -> List[ThreadColor]:
        """Récupère tous les fils, filtré par marque si spécifiée"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            if brand:
                cursor.execute(
                    "SELECT brand, reference, name, hex_color, is_favorite FROM threads WHERE brand = ?",
                    (brand,)
                )
            else:
                cursor.execute(
                    "SELECT brand, reference, name, hex_color, is_favorite FROM threads"
                )
            return [ThreadColor(*row) for row in cursor.fetchall()]

    def get_favorites(self) -> List[ThreadColor]:
        """Récupère les fils favoris"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT brand, reference, name, hex_color, is_favorite FROM threads WHERE is_favorite = 1"
            )
            return [ThreadColor(*row) for row in cursor.fetchall()]

    def toggle_favorite(self, brand: str, reference: str) -> bool:
        """Change l'état favori d'un fil et retourne le nouvel état"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE threads SET is_favorite = NOT is_favorite WHERE brand = ? AND reference = ?",
                (brand, reference)
            )
            cursor.execute(
                "SELECT is_favorite FROM threads WHERE brand = ? AND reference = ?",
                (brand, reference)
            )
            return bool(cursor.fetchone()[0])

class ThreadPanel(ttk.Frame):
    """Panneau de sélection des fils de broderie"""
    def __init__(self, parent, callback):
        super().__init__(parent)
        self.callback = callback
        self.db = ThreadDatabase()
        self.setup_ui()

    def setup_ui(self):
        # Panneau principal avec onglets
        notebook = ttk.Notebook(self)
        notebook.pack(fill=tk.BOTH, expand=True)

        # Onglet Favoris
        favorites_frame = ttk.Frame(notebook)
        notebook.add(favorites_frame, text="Favoris")
        self.create_thread_list(favorites_frame, self.db.get_favorites())

        # Onglet DMC
        dmc_frame = ttk.Frame(notebook)
        notebook.add(dmc_frame, text="DMC")
        self.create_thread_list(dmc_frame, self.db.get_all_threads("DMC"))

        # Prévoir d'autres onglets pour d'autres marques
        # Anchor, Madeira, etc.

    def create_thread_list(self, parent, threads: List[ThreadColor]):
        """Crée la liste des fils avec aperçu des couleurs"""
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.BOTH, expand=True)

        # Scrollbar
        scrollbar = ttk.Scrollbar(frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Liste avec colonnes
        columns = ("Référence", "Nom", "Couleur", "Favori")
        tree = ttk.Treeview(frame, columns=columns, show="headings", 
                           yscrollcommand=scrollbar.set)
        
        # Configuration des colonnes
        tree.heading("Référence", text="Réf.")
        tree.heading("Nom", text="Nom")
        tree.heading("Couleur", text="Couleur")
        tree.heading("Favori", text="★")
        
        tree.column("Référence", width=80)
        tree.column("Nom", width=150)
        tree.column("Couleur", width=80)
        tree.column("Favori", width=30)

        # Remplissage des données
        for thread in threads:
            tree.insert("", tk.END, values=(
                thread.reference,
                thread.name,
                "",  # La couleur sera affichée via un tag
                "★" if thread.is_favorite else ""
            ), tags=(f"color_{thread.hex_color}",))
            
            # Création du tag de couleur
            tree.tag_configure(f"color_{thread.hex_color}", 
                             background=thread.hex_color,
                             foreground=self.get_contrast_color(thread.hex_color))

        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=tree.yview)

        # Événements
        tree.bind("<Double-1>", lambda e: self.on_color_select(e, tree))
        tree.bind("<Button-1>", lambda e: self.on_click(e, tree))

    def get_contrast_color(self, hex_color: str) -> str:
        """Retourne la couleur de texte (noir ou blanc) selon la couleur de fond"""
        # Conversion hex to RGB
        r = int(hex_color[1:3], 16)
        g = int(hex_color[3:5], 16)
        b = int(hex_color[5:7], 16)
        
        # Calcul de la luminance
        luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
        
        return "#000000" if luminance > 0.5 else "#FFFFFF"

    def on_color_select(self, event, tree):
        """Gestion de la sélection d'une couleur"""
        item = tree.selection()[0]
        values = tree.item(item)["values"]
        tag = tree.item(item)["tags"][0]
        hex_color = tag.split("_")[1]
        
        # Appel du callback avec la couleur sélectionnée
        self.callback(hex_color)

    def on_click(self, event, tree):
        """Gestion du clic sur la colonne favori"""
        region = tree.identify("region", event.x, event.y)
        if region == "cell":
            column = tree.identify_column(event.x)
            if column == "#4":  # Colonne Favori
                item = tree.identify_row(event.y)
                values = tree.item(item)["values"]
                # Toggle favori dans la base de données
                is_favorite = self.db.toggle_favorite("DMC", values[0])
                # Mise à jour de l'affichage
                tree.set(item, "Favori", "★" if is_favorite else "")