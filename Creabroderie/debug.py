import tkinter as tk
from tkinter import ttk, colorchooser, font, simpledialog, filedialog, messagebox
from PIL import Image, ImageDraw, ImageTk, ImageFont
import os
from thread_management import ThreadPanel
from typing import List, Tuple
import math
from embroidery_export import EmbroideryDesign, StitchPoint, StitchType, PesExporter, DstExporter, JefExporter

class EmbroideryDesigner:
    def __init__(self, root):
        self.root = root
        self.root.title("Créateur de Motifs de Broderie")
        self.root.geometry("1000x700")
        
        # Configuration de la fenêtre
        self.root.lift()
        self.root.attributes('-topmost', True)
        self.root.after_idle(root.attributes, '-topmost', False)

        # Variables principales
        self.current_tool = "point"
        self.current_fill_color = "#000000"
        self.current_outline_color = "#000000"
        self.start_x = None
        self.start_y = None
        self.current_shape = None
        self.history = []
        self.current_step = -1
        self.grid_size = 20
        self.show_grid = False
        self.snap_to_grid = False
        self.grid_lines = []
        self.current_outline_width = 1  # Épaisseur par défaut du contour
        self.outline_width = tk.StringVar(value="1")  # Pour le widget Combobox

        # Variables pour undo/redo
        self.history = []  # Liste des états
        self.current_step = -1  # Position actuelle dans l'historique
        self.max_history = 50  # Nombre maximum d'actions dans l'historique

        # Variables de sélection
        self.selected_item = None
        self.selection_rect = None
        self.dragging = False
        self.last_click_x = None
        self.last_click_y = None

        # Rectangle de sélection (handles pour redimensionnement)
        self.selection_handles = []
        self.handle_size = 6
        self.resizing = False
        self.current_handle = None

        # Constantes pour les poignées de redimensionnement
        self.HANDLE_NW = 0  # Nord-Ouest
        self.HANDLE_N  = 1  # Nord
        self.HANDLE_NE = 2  # Nord-Est
        self.HANDLE_E  = 3  # Est
        self.HANDLE_SE = 4  # Sud-Est
        self.HANDLE_S  = 5  # Sud
        self.HANDLE_SW = 6  # Sud-Ouest
        self.HANDLE_W  = 7  # Ouest

        # Variables pour copier/coller
        self.clipboard = None  # Stockera les propriétés de l'élément copié
        
        # Variables pour le texte
        self.text_preview = ""
        self.current_font_family = tk.StringVar(value="Arial")
        self.current_font_size = tk.StringVar(value="12")
        self.font_bold = tk.BooleanVar(value=False)
        self.font_italic = tk.BooleanVar(value=False)
        self.font_underline = tk.BooleanVar(value=False)

        # Frame principal
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Configuration de l'interface
        self.setup_menu()
        self.setup_toolbar()

        # Création d'un PanedWindow horizontal pour le panneau de fils
        self.main_paned = ttk.PanedWindow(self.main_frame, orient=tk.HORIZONTAL)
        self.main_paned.pack(fill=tk.BOTH, expand=True)
     
        # Panneau de fils à gauche
        self.thread_panel = ThreadPanel(self.main_paned, self.on_thread_select)
        self.main_paned.add(self.thread_panel, weight=1)

        # Frame de contenu à droite
        self.content_frame = ttk.Frame(self.main_paned)
        self.main_paned.add(self.content_frame, weight=3)
        
        self.setup_canvas()
        self.setup_text_panel()

        # Raccourcis clavier (macOS)
        self.root.bind('<Command-z>', lambda e: self.undo())
        self.root.bind('<Command-y>', lambda e: self.redo())
        self.root.bind('<Command-c>', lambda e: self.copy())
        self.root.bind('<Command-v>', lambda e: self.paste())
        self.root.bind('<Delete>', self.delete_selected)  # Touche Delete
        self.root.bind('<BackSpace>', self.delete_selected)  # Touche Retour arrière également

        # Raccourcis pour l'ordre des éléments
        self.root.bind('<Command-bracketright>', lambda e: self.bring_forward())  # ⌘]
        self.root.bind('<Command-bracketleft>', lambda e: self.send_backward())   # ⌘[
        self.root.bind('<Command-Shift-F>', lambda e: self.bring_to_front())      # ⌘⇧F
        self.root.bind('<Command-Shift-B>', lambda e: self.send_to_back())        # ⌘⇧B

    def on_thread_select(self, hex_color: str):
        """Callback appelé quand une couleur de fil est sélectionnée"""
        # L'indentation du docstring et du code était incorrecte
        self.current_fill_color = hex_color
        self.current_outline_color = hex_color
        self.update_font_preview()  # Si on est en mode texte

    def setup_menu(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # Menu Fichier
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Fichier", menu=file_menu)
        file_menu.add_command(label="Nouveau", command=self.new_design)
        file_menu.add_command(label="Exporter...", command=self.export_design)
        file_menu.add_separator()
        file_menu.add_command(label="Quitter", command=self.root.quit)
        
       # Menu Edition
        edit_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Edition", menu=edit_menu)
        edit_menu.add_command(label="Annuler (⌘Z)", command=self.undo)
        edit_menu.add_command(label="Rétablir (⌘Y)", command=self.redo)
        edit_menu.add_separator()
        edit_menu.add_command(label="Copier (⌘C)", command=self.copy)
        edit_menu.add_command(label="Coller (⌘V)", command=self.paste)
        edit_menu.add_separator()
        edit_menu.add_command(label="Supprimer", command=self.delete_selected)

        # Menu Disposition (à ajouter après le menu Edition)
        arrange_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Disposition", menu=arrange_menu)
        arrange_menu.add_command(label="Premier plan (⌘⇧F)", 
                               command=self.bring_to_front)
        arrange_menu.add_command(label="Arrière-plan (⌘⇧B)", 
                               command=self.send_to_back)
        arrange_menu.add_separator()
        arrange_menu.add_command(label="Avancer (⌘])", 
                               command=self.bring_forward)
        arrange_menu.add_command(label="Reculer (⌘[)", 
                               command=self.send_backward)
        
        # Menu Affichage
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Affichage", menu=view_menu)
        view_menu.add_checkbutton(label="Grille", command=self.toggle_grid)
        view_menu.add_checkbutton(label="Magnétisme", command=self.toggle_snap)
        view_menu.add_separator()
        view_menu.add_command(label="Panneau des fils", command=self.toggle_thread_panel)
        
        # Menu Outils
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Outils", menu=tools_menu)
        tools_menu.add_command(label="Point", command=lambda: self.set_tool("point"))
        tools_menu.add_command(label="Rectangle", command=lambda: self.set_tool("rectangle"))
        tools_menu.add_command(label="Ovale", command=lambda: self.set_tool("oval"))
        tools_menu.add_command(label="Texte", command=lambda: self.set_tool("text"))

    def export_design(self):
        """Interface d'export du motif"""
        export_window = tk.Toplevel(self.root)
        export_window.title("Exporter le motif")
        export_window.geometry("400x300")
        export_window.transient(self.root)
        export_window.grab_set()
        
        # Frame pour les paramètres
        params_frame = ttk.LabelFrame(export_window, text="Paramètres d'export")
        params_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Format d'export
        format_frame = ttk.Frame(params_frame)
        format_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(format_frame, text="Format :").pack(side=tk.LEFT)
        format_var = tk.StringVar(value="pes")
        formats = {
            "Brother (*.pes)": "pes",
            "Tajima (*.dst)": "dst",
            "Janome (*.jef)": "jef"
        }
        format_combo = ttk.Combobox(format_frame, values=list(formats.keys()),
                                   textvariable=format_var, state="readonly")
        format_combo.pack(side=tk.LEFT, padx=5)
        
        # Taille du tambour
        hoop_frame = ttk.Frame(params_frame)
        hoop_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(hoop_frame, text="Tambour :").pack(side=tk.LEFT)
        hoop_var = tk.StringVar(value="100x100")
        hoops = ["100x100", "130x180", "200x200", "300x200"]
        hoop_combo = ttk.Combobox(hoop_frame, values=hoops,
                                 textvariable=hoop_var, state="readonly")
        hoop_combo.pack(side=tk.LEFT, padx=5)
        
        # Densité des points
        density_frame = ttk.Frame(params_frame)
        density_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(density_frame, text="Densité des points :").pack(side=tk.LEFT)
        density_var = tk.StringVar(value="2.0")
        densities = ["1.0", "1.5", "2.0", "2.5", "3.0"]
        density_combo = ttk.Combobox(density_frame, values=densities,
                                    textvariable=density_var, state="readonly")
        density_combo.pack(side=tk.LEFT, padx=5)

        # Informations
        info_frame = ttk.LabelFrame(export_window, text="Informations")
        info_frame.pack(fill=tk.X, padx=10, pady=5)
        self.export_info_label = ttk.Label(info_frame, text="Calculé des points...")
        self.export_info_label.pack(padx=5, pady=5)
        # Boutons (à ajouter après self.export_info_label.pack())
        btn_frame = ttk.Frame(export_window)
        btn_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)
        
        def do_export():
            """Effectue l'export du motif"""
            selected_format = formats[format_combo.get()]
            file_extensions = {
                "pes": ".pes",
                "dst": ".dst",
                "jef": ".jef"
            }
            
            # Dialogue de sauvegarde
            filetypes = [
                ("Fichier Brother", "*.pes"),
                ("Fichier Tajima", "*.dst"),
                ("Fichier Janome", "*.jef"),
            ]
            
            filename = filedialog.asksaveasfilename(
                parent=export_window,
                defaultextension=file_extensions[selected_format],
                filetypes=filetypes
            )
            
            if filename:
                try:
                    # Récupérer les paramètres
                    density = float(density_var.get())
                    hoop_size = tuple(map(int, hoop_var.get().split('x')))
                    
                    # Convertir le dessin
                    self.export_info_label.config(text="Conversion en cours...")
                    export_window.update()
                    
                    design = self.convert_to_embroidery(density, hoop_size)
                    
                    # Exporter selon le format
                    success = self.export_to_format(design, filename, selected_format)
                    
                    if success:
                        messagebox.showinfo(
                            "Export réussi",
                            "Le motif a été exporté avec succès.",
                            parent=export_window
                        )
                        export_window.destroy()
                    else:
                        messagebox.showerror(
                            "Erreur",
                            "Une erreur est survenue lors de l'export.",
                            parent=export_window
                        )
                except Exception as e:
                    messagebox.showerror(
                        "Erreur",
                        f"Erreur lors de l'export : {str(e)}",
                        parent=export_window
                    )
        
        ttk.Button(btn_frame, text="Exporter", command=do_export).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="Annuler", 
                  command=export_window.destroy).pack(side=tk.RIGHT)    



    def toggle_thread_panel(self):
        """Affiche ou masque le panneau des fils"""
        pane_pos = self.main_paned.sash_coord(0)
        if pane_pos[0] == 0:  # Si le panneau est masqué
            self.main_paned.sash_place(0, 200, 0)  # Afficher
        else:  # Si le panneau est visible
            self.main_paned.sash_place(0, 0, 0)    # Masquer      

    def setup_toolbar(self):
        toolbar = ttk.Frame(self.main_frame)
        toolbar.pack(side=tk.TOP, fill=tk.X, pady=5)

        # Outils de dessin
        tools_frame = ttk.LabelFrame(toolbar, text="Outils")
        tools_frame.pack(side=tk.LEFT, padx=5)

        ttk.Button(tools_frame, text="Sélection", command=lambda: self.set_tool("select")).pack(side=tk.LEFT, padx=2)
        ttk.Button(tools_frame, text="Point", command=lambda: self.set_tool("point")).pack(side=tk.LEFT, padx=2)
        ttk.Button(tools_frame, text="Rectangle", command=lambda: self.set_tool("rectangle")).pack(side=tk.LEFT, padx=2)
        ttk.Button(tools_frame, text="Ovale", command=lambda: self.set_tool("oval")).pack(side=tk.LEFT, padx=2)
        ttk.Button(tools_frame, text="Texte", command=lambda: self.set_tool("text")).pack(side=tk.LEFT, padx=2)

        # Couleurs et styles
        style_frame = ttk.LabelFrame(toolbar, text="Couleurs et styles")
        style_frame.pack(side=tk.LEFT, padx=5)

        # Couleur de remplissage
        fill_frame = ttk.Frame(style_frame)
        fill_frame.pack(side=tk.LEFT, padx=5)
        ttk.Button(fill_frame, text="Couleur de remplissage", 
                  command=self.choose_fill_color).pack(side=tk.TOP, pady=2)
        
        # Couleur de contour
        outline_frame = ttk.Frame(style_frame)
        outline_frame.pack(side=tk.LEFT, padx=5)
        ttk.Button(outline_frame, text="Couleur du contour", 
                  command=self.choose_outline_color).pack(side=tk.TOP, pady=2)
        
        # Épaisseur du contour
        width_frame = ttk.Frame(style_frame)
        width_frame.pack(side=tk.LEFT, padx=5)
        ttk.Label(width_frame, text="Épaisseur :").pack(side=tk.LEFT)
        width_values = [1, 2, 3, 4, 5, 6, 8, 10, 12, 15, 20]
        width_combo = ttk.Combobox(width_frame, textvariable=self.outline_width, 
                                 values=width_values, width=3)
        width_combo.pack(side=tk.LEFT, padx=2)
        width_combo.bind('<<ComboboxSelected>>', self.update_outline_width)    

    def choose_outline_color(self):
        color = colorchooser.askcolor(title="Choisir la couleur du contour")[1]
        if color:
            self.current_outline_color = color

    def update_outline_width(self, event=None):
        try:
            self.current_outline_width = int(self.outline_width.get())
        except ValueError:
            self.current_outline_width = 1
            self.outline_width.set("1")

    def save_state(self):
        """Sauvegarde l'état actuel du canvas dans l'historique"""
        # Supprimer les états après la position actuelle si on a fait des undo
        if self.current_step < len(self.history) - 1:
            self.history = self.history[:self.current_step + 1]
        
        # Sauvegarder l'état actuel
        state = []
        for item in self.canvas.find_all():
            if item not in self.grid_lines:  # Ne pas sauvegarder les lignes de la grille
                item_type = self.canvas.type(item)
                coords = self.canvas.coords(item)
                config = {}
                
                # Sauvegarder les propriétés en fonction du type
                if item_type == 'text':
                    config['fill'] = self.canvas.itemcget(item, 'fill')
                    config['text'] = self.canvas.itemcget(item, 'text')
                    config['font'] = self.canvas.itemcget(item, 'font')
                    config['anchor'] = self.canvas.itemcget(item, 'anchor')
                elif item_type == 'line':  # Pour le soulignement du texte
                    config['fill'] = self.canvas.itemcget(item, 'fill')
                    config['width'] = self.canvas.itemcget(item, 'width')
                else:  # Pour les formes (rectangle, oval)
                    config['fill'] = self.canvas.itemcget(item, 'fill')
                    config['outline'] = self.canvas.itemcget(item, 'outline')
                    config['width'] = self.canvas.itemcget(item, 'width')
                
                state.append((item_type, coords, config))
        
        self.history.append(state)
        self.current_step += 1
        
        # Limiter la taille de l'historique
        if len(self.history) > self.max_history:
            self.history.pop(0)
            self.current_step -= 1

    def restore_state(self, state):
        """Restaure un état sauvegardé du canvas"""
        # Effacer tous les éléments sauf la grille
        for item in self.canvas.find_all():
            if item not in self.grid_lines:
                self.canvas.delete(item)
        
        # Recréer les éléments
        for item_type, coords, config in state:
            if item_type == 'text':
                self.canvas.create_text(
                    coords[0], coords[1],
                    text=config.get('text', ''),
                    fill=config.get('fill', 'black'),
                    font=config.get('font', ('Arial', 12)),
                    anchor=config.get('anchor', 'nw')
                )
            else:
                create_method = getattr(self.canvas, f'create_{item_type}')
                create_method(*coords, **config)

    def undo(self):
        """Annule la dernière action"""
        if self.current_step > 0:
            self.current_step -= 1
            self.restore_state(self.history[self.current_step])

    def redo(self):
        """Rétablit la dernière action annulée"""
        if self.current_step < len(self.history) - 1:
            self.current_step += 1
            self.restore_state(self.history[self.current_step])

    def copy(self, event=None):
        """Copier l'élément sélectionné"""
        if not self.selected_item:
            return
            
        # Récupérer le type et les propriétés de l'élément
        item_type = self.canvas.type(self.selected_item)
        coords = self.canvas.coords(self.selected_item)
        config = {}
        
        if item_type == 'text':
            config['text'] = self.canvas.itemcget(self.selected_item, 'text')
            config['fill'] = self.canvas.itemcget(self.selected_item, 'fill')
            config['font'] = self.canvas.itemcget(self.selected_item, 'font')
            config['anchor'] = self.canvas.itemcget(self.selected_item, 'anchor')
        else:  # Pour les formes (rectangle, oval)
            config['fill'] = self.canvas.itemcget(self.selected_item, 'fill')
            config['outline'] = self.canvas.itemcget(self.selected_item, 'outline')
            config['width'] = self.canvas.itemcget(self.selected_item, 'width')
        
        # Sauvegarder dans le presse-papier
        self.clipboard = {
            'type': item_type,
            'coords': coords,
            'config': config
        }

    def paste(self, event=None):
        """Coller l'élément copié"""
        if not self.clipboard:
            return
            
        # Calculer le décalage pour la nouvelle position
        offset = 20  # Décalage en pixels
        new_coords = []
        for i, coord in enumerate(self.clipboard['coords']):
            new_coords.append(coord + offset)
        
        # Créer le nouvel élément
        if self.clipboard['type'] == 'text':
            new_item = self.canvas.create_text(
                new_coords[0], new_coords[1],
                **self.clipboard['config']
            )
        else:
            create_method = getattr(self.canvas, f'create_{self.clipboard["type"]}')
            new_item = create_method(*new_coords, **self.clipboard['config'])
        
        # Sélectionner le nouvel élément
        self.clear_selection()
        self.selected_item = new_item
        self.show_selection_handles()
        
        # Sauvegarder l'état
        self.save_state()        

    def select_item(self, event):
        """Gérer la sélection d'un élément"""
        x, y = event.x, event.y
        
        # Vérifier d'abord si on clique sur une poignée de l'élément actuellement sélectionné
        handle = self.get_handle_at_pos(x, y)
        if handle is not None and self.selected_item:
            self.current_handle = handle
            self.resizing = True
            return
            
        # Chercher un élément sous le curseur
        items = self.canvas.find_overlapping(x-1, y-1, x+1, y+1)
        # Filtrer les éléments de l'interface (grille, poignées, rectangle de sélection)
        items = [item for item in items 
                if item not in self.grid_lines 
                and item != self.selection_rect 
                and item not in self.selection_handles]
        
        # Effacer toujours la sélection actuelle
        self.clear_selection()
        
        # Si on a trouvé un élément, le sélectionner
        if items:
            self.selected_item = items[-1]
            self.show_selection_handles()
            self.last_click_x = x
            self.last_click_y = y
            self.dragging = True
            
    def get_handle_at_pos(self, x, y):
        """Retourne l'index de la poignée sous le curseur"""
        for i, handle in enumerate(self.selection_handles):
            bbox = self.canvas.bbox(handle)
            if bbox:
                if (bbox[0] <= x <= bbox[2] and 
                    bbox[1] <= y <= bbox[3]):
                    return i
        return None

    def resize_item(self, event):
        """Redimensionner l'élément sélectionné"""
        if not self.resizing or not self.selected_item:
            return
            
        x, y = event.x, event.y
        bbox = list(self.canvas.bbox(self.selected_item))
        
        # Mettre à jour les coordonnées en fonction de la poignée
        if self.current_handle in [self.HANDLE_NW, self.HANDLE_N, self.HANDLE_NE]:
            bbox[1] = y  # Modifier y1
        if self.current_handle in [self.HANDLE_SW, self.HANDLE_S, self.HANDLE_SE]:
            bbox[3] = y  # Modifier y2
        if self.current_handle in [self.HANDLE_NW, self.HANDLE_W, self.HANDLE_SW]:
            bbox[0] = x  # Modifier x1
        if self.current_handle in [self.HANDLE_NE, self.HANDLE_E, self.HANDLE_SE]:
            bbox[2] = x  # Modifier x2
            
        # Maintenir les proportions si Shift est enfoncé
        if event.state & 0x1:  # Shift est enfoncé
            original_ratio = (bbox[2] - bbox[0]) / (bbox[3] - bbox[1])
            width = bbox[2] - bbox[0]
            height = bbox[3] - bbox[1]
            
            if self.current_handle in [self.HANDLE_N, self.HANDLE_S]:
                # Ajuster la largeur
                new_width = height * original_ratio
                dx = (new_width - width) / 2
                bbox[0] -= dx
                bbox[2] += dx
            elif self.current_handle in [self.HANDLE_E, self.HANDLE_W]:
                # Ajuster la hauteur
                new_height = width / original_ratio
                dy = (new_height - height) / 2
                bbox[1] -= dy
                bbox[3] += dy
                
        # Empêcher les dimensions trop petites
        min_size = 10
        if bbox[2] - bbox[0] < min_size:
            if self.current_handle in [self.HANDLE_NW, self.HANDLE_W, self.HANDLE_SW]:
                bbox[0] = bbox[2] - min_size
            else:
                bbox[2] = bbox[0] + min_size
                
        if bbox[3] - bbox[1] < min_size:
            if self.current_handle in [self.HANDLE_NW, self.HANDLE_N, self.HANDLE_NE]:
                bbox[1] = bbox[3] - min_size
            else:
                bbox[3] = bbox[1] + min_size
                
        # Mettre à jour uniquement l'élément et les poignées
        self.canvas.coords(self.selected_item, *bbox)
        self.update_selection_position()  # Nouvelle méthode

    def bring_to_front(self, event=None):
        """Mettre l'élément sélectionné au premier plan"""
        if self.selected_item:
            # Trouver l'élément le plus haut (sans compter la sélection)
            all_items = self.canvas.find_all()
            top_item = max(i for i in all_items 
                         if i not in self.selection_handles 
                         and i != self.selection_rect)
            
            if self.selected_item != top_item:
                self.canvas.tag_raise(self.selected_item, top_item)
                self.show_selection_handles()  # Mettre à jour la sélection
                self.save_state()

    def send_to_back(self, event=None):
        """Mettre l'élément sélectionné à l'arrière-plan"""
        if self.selected_item:
            # Trouver l'élément le plus bas (sans compter la grille)
            bottom_item = min(i for i in self.canvas.find_all() 
                            if i not in self.grid_lines)
            
            if self.selected_item != bottom_item:
                self.canvas.tag_lower(self.selected_item, bottom_item)
                self.show_selection_handles()  # Mettre à jour la sélection
                self.save_state()

    def bring_forward(self, event=None):
        """Avancer l'élément sélectionné d'un niveau"""
        if self.selected_item:
            next_item = self.canvas.find_above(self.selected_item)
            if next_item and next_item not in self.selection_handles and next_item != self.selection_rect:
                self.canvas.tag_raise(self.selected_item, next_item)
                self.show_selection_handles()  # Mettre à jour la sélection
                self.save_state()

    def send_backward(self, event=None):
        """Reculer l'élément sélectionné d'un niveau"""
        if self.selected_item:
            prev_item = self.canvas.find_below(self.selected_item)
            if prev_item and prev_item not in self.grid_lines:
                self.canvas.tag_lower(self.selected_item, prev_item)
                self.show_selection_handles()  # Mettre à jour la sélection
                self.save_state()    

    def update_selection_position(self):
        """Mettre à jour la position du rectangle de sélection et des poignées"""
        if not self.selected_item:
            return
            
        bbox = self.canvas.bbox(self.selected_item)
        if not bbox:
            return
            
        # Mettre à jour le rectangle de sélection
        if self.selection_rect:
            self.canvas.coords(self.selection_rect,
                bbox[0]-1, bbox[1]-1, bbox[2]+1, bbox[3]+1)
        
        # Mettre à jour les poignées
        handles_coords = [
            (bbox[0], bbox[1]),  # NW
            ((bbox[0] + bbox[2])/2, bbox[1]),  # N
            (bbox[2], bbox[1]),  # NE
            (bbox[2], (bbox[1] + bbox[3])/2),  # E
            (bbox[2], bbox[3]),  # SE
            ((bbox[0] + bbox[2])/2, bbox[3]),  # S
            (bbox[0], bbox[3]),  # SW
            (bbox[0], (bbox[1] + bbox[3])/2),  # W
        ]
        
        for handle, (x, y) in zip(self.selection_handles, handles_coords):
            self.canvas.coords(handle,
                x-self.handle_size/2, y-self.handle_size/2,
                x+self.handle_size/2, y+self.handle_size/2)

    def show_selection_handles(self):
        """Afficher les poignées de sélection/redimensionnement"""
        if not self.selected_item:
            return
            
        # Obtenir les coordonnées de l'élément
        try:
            coords = self.canvas.coords(self.selected_item)
            if not coords:
                return
                
            # Calculer la boîte englobante
            if len(coords) == 2:  # Point ou texte
                x, y = coords
                bbox = (x-5, y-5, x+5, y+5)
            elif len(coords) == 4:  # Rectangle ou ovale
                bbox = coords
            else:
                return
                
            # Créer le rectangle de sélection
            self.selection_rect = self.canvas.create_rectangle(
                bbox[0]-1, bbox[1]-1, bbox[2]+1, bbox[3]+1,
                outline='#0078D7', dash=(2, 2),
                fill=""  # Transparent
            )
            
            # Créer les poignées de redimensionnement
            handles_coords = [
                (bbox[0], bbox[1]),  # NW
                ((bbox[0] + bbox[2])/2, bbox[1]),  # N
                (bbox[2], bbox[1]),  # NE
                (bbox[2], (bbox[1] + bbox[3])/2),  # E
                (bbox[2], bbox[3]),  # SE
                ((bbox[0] + bbox[2])/2, bbox[3]),  # S
                (bbox[0], bbox[3]),  # SW
                (bbox[0], (bbox[1] + bbox[3])/2),  # W
            ]
            
            self.selection_handles.clear()
            for x, y in handles_coords:
                handle = self.canvas.create_rectangle(
                    x-self.handle_size/2, y-self.handle_size/2,
                    x+self.handle_size/2, y+self.handle_size/2,
                    fill='white', outline='#0078D7'
                )
                self.selection_handles.append(handle)
                
        except Exception as e:
            print(f"Erreur lors de l'affichage des poignées : {str(e)}")
            self.clear_selection()

    def clear_selection(self):
        """Effacer les éléments de sélection"""
        if self.selection_rect:
            self.canvas.delete(self.selection_rect)
            self.selection_rect = None
        
        for handle in self.selection_handles:
            self.canvas.delete(handle)
        self.selection_handles.clear()
        
        self.selected_item = None
        self.dragging = False
        self.resizing = False
        self.current_handle = None         

    def delete_selected(self, event=None):
        """Supprimer l'élément sélectionné"""
        if self.selected_item:
            # Supprimer l'élément
            self.canvas.delete(self.selected_item)
            # Nettoyer la sélection
            self.clear_selection()
            # Sauvegarder l'état pour le undo/redo
            self.save_state()       

    def canvas_click(self, event):
        if self.current_tool == "select":
            self.select_item(event)
            return
            
        x, y = event.x, event.y
        
        if self.current_tool == "text":
            try:
                selected_indices = self.font_listbox.curselection()
                if not selected_indices:
                    return
                font_family = self.font_listbox.get(selected_indices[0])
                font_size = int(self.current_font_size.get())
                
                font_weight = "bold" if self.font_bold.get() else "normal"
                font_slant = "italic" if self.font_italic.get() else "roman"
                
                text_font = (font_family, font_size, font_weight, font_slant)
                
                text = self.preview_entry.get()
                if not text:
                    text = "Texte"
                
                text_item = self.canvas.create_text(
                    x, y,
                    text=text,
                    font=text_font,
                    fill=self.current_fill_color,
                    anchor="nw"
                )
                
                if self.font_underline.get():
                    bbox = self.canvas.bbox(text_item)
                    if bbox:
                        self.canvas.create_line(
                            bbox[0], bbox[3] + 2,
                            bbox[2], bbox[3] + 2,
                            fill=self.current_fill_color
                        )
                self.save_state()
            except Exception as e:
                print(f"Erreur lors de l'insertion du texte : {str(e)}")
        elif self.current_tool == "point":
            self.canvas.create_oval(
                x-2, y-2, x+2, y+2,
                fill=self.current_fill_color,
                outline=self.current_outline_color,
                width=self.current_outline_width
            )
            self.save_state()
        else:
            self.start_x = x
            self.start_y = y

    def canvas_drag(self, event):
        if self.resizing:
            self.resize_item(event)
            return
            
        # Le reste du code existant pour le déplacement...
        x, y = event.x, event.y
        
        if self.current_tool == "select" and self.dragging and self.selected_item:
            # Calculer le déplacement
            dx = x - self.last_click_x
            dy = y - self.last_click_y
            
            # Déplacer l'élément
            self.canvas.move(self.selected_item, dx, dy)
            
            # Déplacer le rectangle de sélection et les poignées
            if self.selection_rect:
                self.canvas.move(self.selection_rect, dx, dy)
            for handle in self.selection_handles:
                self.canvas.move(handle, dx, dy)
            
            # Mettre à jour la dernière position
            self.last_click_x = x
            self.last_click_y = y
            return
            
        if self.start_x is None or self.current_tool == "point" or self.current_tool == "text":
            return
            
        if hasattr(self, 'temp_shape'):
            self.canvas.delete(self.temp_shape)
        
        if self.current_tool == "rectangle":
            self.temp_shape = self.canvas.create_rectangle(
                self.start_x, self.start_y, x, y,
                fill=self.current_fill_color,
                outline=self.current_outline_color,
                width=self.current_outline_width
            )
        elif self.current_tool == "oval":
            self.temp_shape = self.canvas.create_oval(
                self.start_x, self.start_y, x, y,
                fill=self.current_fill_color,
                outline=self.current_outline_color,
                width=self.current_outline_width
            )

    def canvas_release(self, event):
        if self.resizing:
            self.resizing = False
            self.current_handle = None
            self.save_state()
            return
            
        # Le reste du code existant...
        if self.current_tool == "select" and self.dragging:
            self.dragging = False
            if self.selected_item:
                self.save_state()
            return

        if self.current_tool not in ["point", "text"] and hasattr(self, 'temp_shape'):
            x, y = event.x, event.y
            if self.current_tool == "rectangle":
                self.canvas.create_rectangle(
                    self.start_x, self.start_y, x, y,
                    fill=self.current_fill_color,
                    outline=self.current_outline_color,
                    width=self.current_outline_width
                )
            elif self.current_tool == "oval":
                self.canvas.create_oval(
                    self.start_x, self.start_y, x, y,
                    fill=self.current_fill_color,
                    outline=self.current_outline_color,
                    width=self.current_outline_width
                )
            
            self.canvas.delete(self.temp_shape)
            delattr(self, 'temp_shape')
            self.save_state()
        
        self.start_x = None
        self.start_y = None    

    def convert_to_embroidery(self, density: float, hoop_size: tuple) -> EmbroideryDesign:
        """Convertit le dessin en points de broderie"""
        points = []
        thread_colors = []
    
        # Parcourir les éléments dans l'ordre de dessin
        for item in self.canvas.find_all():
            if item in self.grid_lines:
                continue
            
            # Récupérer les propriétés de l'élément
            item_type = self.canvas.type(item)
            coords = self.canvas.coords(item)
            fill = self.canvas.itemcget(item, 'fill')
        
            # Si l'élément a une couleur de remplissage
            if fill and fill != '':
                # Ajouter la couleur à la palette si nécessaire
                if fill not in thread_colors:
                    thread_colors.append(fill)
                color_index = thread_colors.index(fill)
            
                try:
                    # Convertir selon le type d'élément
                    if item_type == 'oval':
                        points.extend(self._circle_to_stitches(coords, color_index, density))
                    elif item_type == 'rectangle':
                        points.extend(self._rectangle_to_stitches(coords, color_index, density))
                    elif item_type == 'text':
                        points.extend(self._text_to_stitches(coords, color_index, density))
                except Exception as e:
                    print(f"Erreur lors de la conversion de {item_type}: {str(e)}")
                    continue
    
        # S'assurer qu'il y a au moins un point
        if not points:
            points.append(StitchPoint(0, 0, StitchType.NORMAL, 0))
    
        # Calculer la taille du motif
        bbox = self.canvas.bbox('all')
        if bbox:
            width = (bbox[2] - bbox[0]) / 10  # Convertir en mm
            height = (bbox[3] - bbox[1]) / 10
        else:
            width = height = 100
    
        # Créer le design
        return EmbroideryDesign(
            points=points,
            thread_colors=thread_colors,
            size_mm=(width, height),
            hoop_size_mm=hoop_size
        )

    def _circle_to_stitches(self, coords: list, color_index: int, density: float) -> List[StitchPoint]:
        """Convertit un cercle en points de broderie"""
        x1, y1, x2, y2 = coords
        center_x = (x1 + x2) / 2
        center_y = (y1 + y2) / 2
        radius_x = (x2 - x1) / 2
        radius_y = (y2 - y1) / 2
        
        points = []
        num_points = int(max(radius_x, radius_y) * density)
        
        for i in range(num_points):
            angle = 2 * math.pi * i / num_points
            x = center_x + radius_x * math.cos(angle)
            y = center_y + radius_y * math.sin(angle)
            points.append(StitchPoint(x/10, y/10, StitchType.NORMAL, color_index))
        
        # Ajouter un point de fin
        points.append(StitchPoint(
            points[0].x, points[0].y, 
            StitchType.END, color_index
        ))
        
        return points

    def _rectangle_to_stitches(self, coords: list, color_index: int, density: float) -> List[StitchPoint]:
        """Convertit un rectangle en points de broderie"""
        x1, y1, x2, y2 = coords
        points = []
        
        # Calculer l'espacement entre les lignes
        spacing = 1.0 / density  # en pixels
        
        # Créer des lignes horizontales
        y = y1
        direction = 1
        while y <= y2:
            if direction > 0:
                # Gauche à droite
                points.append(StitchPoint(x1/10, y/10, StitchType.NORMAL, color_index))
                points.append(StitchPoint(x2/10, y/10, StitchType.NORMAL, color_index))
            else:
                # Droite à gauche
                points.append(StitchPoint(x2/10, y/10, StitchType.NORMAL, color_index))
                points.append(StitchPoint(x1/10, y/10, StitchType.NORMAL, color_index))
            
            y += spacing
            direction *= -1
        
        return points

    def _text_to_stitches(self, coords: list, color_index: int, density: float) -> List[StitchPoint]:
        """Convertit du texte en points de broderie"""
        x, y = coords
        points = []
        # Pour l'instant, on crée juste un point au début du texte
        # Cette méthode devrait être améliorée pour vraiment convertir le texte en points
        points.append(StitchPoint(x/10, y/10, StitchType.NORMAL, color_index))
        return points

    def export_to_format(self, design: EmbroideryDesign, filename: str, format_type: str) -> bool:
        """Exporte le design dans le format spécifié"""
        try:
            if format_type == "pes":
                exporter = PesExporter()
            elif format_type == "dst":
                exporter = DstExporter()
            else:  # jef
                exporter = JefExporter()
            
            return exporter.export(design, filename)
        except Exception as e:
            print(f"Erreur lors de l'export : {str(e)}")
            return False                   
    
    def setup_canvas(self):
        canvas_frame = ttk.LabelFrame(self.content_frame, text="Zone de dessin")
        canvas_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.canvas = tk.Canvas(canvas_frame, bg='white')
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        self.canvas.bind('<Button-1>', self.canvas_click)
        self.canvas.bind('<B1-Motion>', self.canvas_drag)
        self.canvas.bind('<ButtonRelease-1>', self.canvas_release)

         # Sauvegarder l'état initial (canvas vide)
        self.save_state()

    def setup_text_panel(self):
        text_panel = ttk.LabelFrame(self.content_frame, text="Paramètres du texte")
        text_panel.pack(side=tk.RIGHT, fill=tk.Y, padx=5, pady=5)

        # Liste des polices avec aperçu
        ttk.Label(text_panel, text="Police :").pack(pady=5)
        self.font_listbox = tk.Listbox(text_panel, width=30, height=10)
        self.font_listbox.pack(pady=5, padx=5)
        
        # Remplir la liste des polices
        available_fonts = sorted(font.families())
        for f in available_fonts:
            self.font_listbox.insert(tk.END, f)
        self.font_listbox.select_set(0)
        
        self.font_listbox.bind('<<ListboxSelect>>', self.update_font_preview)

        # Taille de police
        size_frame = ttk.Frame(text_panel)
        size_frame.pack(fill=tk.X, pady=5, padx=5)
        ttk.Label(size_frame, text="Taille :").pack(side=tk.LEFT)
        font_sizes = [8, 9, 10, 11, 12, 14, 16, 18, 20, 22, 24, 28, 32, 36, 48, 72]
        size_combo = ttk.Combobox(size_frame, values=font_sizes, textvariable=self.current_font_size, width=5)
        size_combo.pack(side=tk.LEFT, padx=5)
        size_combo.bind('<<ComboboxSelected>>', self.update_font_preview)

        # Styles de police
        style_frame = ttk.Frame(text_panel)
        style_frame.pack(fill=tk.X, pady=5, padx=5)
        
        ttk.Checkbutton(style_frame, text="Gras", variable=self.font_bold, 
                       command=self.update_font_preview).pack(side=tk.LEFT)
        ttk.Checkbutton(style_frame, text="Italique", variable=self.font_italic,
                       command=self.update_font_preview).pack(side=tk.LEFT)
        ttk.Checkbutton(style_frame, text="Souligné", variable=self.font_underline,
                       command=self.update_font_preview).pack(side=tk.LEFT)

        # Zone de prévisualisation
        preview_frame = ttk.LabelFrame(text_panel, text="Aperçu")
        preview_frame.pack(fill=tk.BOTH, expand=True, pady=5, padx=5)
        
        self.preview_entry = ttk.Entry(preview_frame)
        self.preview_entry.insert(0, "Tapez votre texte ici")
        self.preview_entry.pack(fill=tk.X, pady=5, padx=5)
        self.preview_entry.bind('<KeyRelease>', self.update_font_preview)
        
        self.preview_canvas = tk.Canvas(preview_frame, width=200, height=100, bg='white')
        self.preview_canvas.pack(fill=tk.BOTH, expand=True, pady=5)

    def update_font_preview(self, event=None):
        self.preview_canvas.delete("all")
        
        try:
            selected_indices = self.font_listbox.curselection()
            if not selected_indices:
                return
            font_family = self.font_listbox.get(selected_indices[0])
            font_size = int(self.current_font_size.get())
            
            font_weight = "bold" if self.font_bold.get() else "normal"
            font_slant = "italic" if self.font_italic.get() else "roman"
            
            preview_font = (font_family, font_size, font_weight, font_slant)
            
            preview_text = self.preview_entry.get()
            if not preview_text:
                preview_text = "Exemple de texte"
            
            self.preview_canvas.create_text(
                100, 50,
                text=preview_text,
                font=preview_font,
                fill=self.current_fill_color,
                anchor="center"
            )
            
            if self.font_underline.get():
                bbox = self.preview_canvas.bbox("all")
                if bbox:
                    self.preview_canvas.create_line(
                        bbox[0], bbox[3] + 2,
                        bbox[2], bbox[3] + 2,
                        fill=self.current_fill_color
                    )
        except Exception as e:
            print(f"Erreur lors de la prévisualisation : {str(e)}")

    def choose_fill_color(self):
        color = colorchooser.askcolor(title="Choisir la couleur du texte")[1]
        if color:
            self.current_fill_color = color
            self.update_font_preview()

    def new_design(self):
        if messagebox.askyesno("Nouveau", "Voulez-vous créer un nouveau design ?\nLes modifications non sauvegardées seront perdues."):
            self.canvas.delete("all")
            self.history.clear()
            self.current_step = -1
            self.draw_grid() if self.show_grid else None

    def toggle_grid(self):
        self.show_grid = not self.show_grid
        if self.show_grid:
            self.draw_grid()
        else:
            for line in self.grid_lines:
                self.canvas.delete(line)
            self.grid_lines.clear()

    def toggle_snap(self):
        self.snap_to_grid = not self.snap_to_grid

    def set_tool(self, tool):
        self.current_tool = tool

    def draw_grid(self):
        for line in self.grid_lines:
            self.canvas.delete(line)
        self.grid_lines.clear()
        
        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()
        
        for x in range(0, width, self.grid_size):
            line = self.canvas.create_line(x, 0, x, height, fill="#CCCCCC", dash=(1,))
            self.grid_lines.append(line)
        
        for y in range(0, height, self.grid_size):
            line = self.canvas.create_line(0, y, width, y, fill="#CCCCCC", dash=(1,))
            self.grid_lines.append(line)

if __name__ == "__main__":
    try:
        root = tk.Tk()
        app = EmbroideryDesigner(root)
        root.mainloop()
    except Exception as e:
        print(f"Erreur lors du démarrage : {str(e)}")
        import traceback
        traceback.print_exc()
        input("Appuyez sur Entrée pour fermer...")

    