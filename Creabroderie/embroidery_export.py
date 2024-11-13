from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Tuple
import math
import struct
import os

@dataclass
class StitchPoint:
    """Représente un point de broderie"""
    x: float            # Position X en mm
    y: float            # Position Y en mm
    stitch_type: int    # Type de point (normal, saut, etc.)
    color_index: int    # Index de la couleur dans la palette

class StitchType:
    """Types de points disponibles"""
    NORMAL = 0
    JUMP = 1
    TRIM = 2
    COLOR_CHANGE = 3
    END = 4

@dataclass
class EmbroideryDesign:
    """Contient toutes les informations d'un motif de broderie"""
    points: List[StitchPoint]
    thread_colors: List[str]  # Liste des couleurs hex
    size_mm: Tuple[float, float]  # Taille en mm (largeur, hauteur)
    hoop_size_mm: Tuple[float, float]  # Taille du tambour (largeur, hauteur)

class EmbroideryExporter(ABC):
    """Classe abstraite pour l'export de motifs"""
    
    @abstractmethod
    def export(self, design: EmbroideryDesign, filepath: str) -> bool:
        """Exporte le motif dans un fichier"""
        pass

    def _convert_to_machine_units(self, mm: float) -> int:
        """Convertit les millimètres en unités machine (0.1mm)"""
        return int(mm * 10)

class PesExporter(EmbroideryExporter):
    """Exporteur au format PES (Brother)"""
    
    def export(self, design: EmbroideryDesign, filepath: str) -> bool:
        try:
            with open(filepath, 'wb') as f:
                # En-tête PES
                f.write(b'#PES0001')
                
                # Réserver la place pour l'offset PEC (nous le mettrons à jour plus tard)
                pec_offset_pos = f.tell()
                f.write(struct.pack('<I', 0))  # Placeholder pour l'offset PEC
                
                # Section PES
                f.write(struct.pack('<III', 
                    int(design.size_mm[0] * 10),  # Largeur en 0.1mm
                    int(design.size_mm[1] * 10),  # Hauteur en 0.1mm
                    len(design.thread_colors)      # Nombre de couleurs
                ))
                
                # Ajouter les informations de couleurs
                for color in design.thread_colors:
                    # Convertir la couleur hex en RGB
                    r = int(color[1:3], 16)
                    g = int(color[3:5], 16)
                    b = int(color[5:7], 16)
                    f.write(struct.pack('BBB', r, g, b))
                
                # Noter la position du début du segment PEC
                pec_offset = f.tell()
                
                # Revenir en arrière et écrire l'offset PEC correct
                f.seek(pec_offset_pos)
                f.write(struct.pack('<I', pec_offset))
                f.seek(pec_offset)
                
                # Section PEC
                f.write(b'#PEC0001')
                
                # Table des couleurs PEC
                f.write(bytes([len(design.thread_colors)]))
                for i in range(len(design.thread_colors)):
                    f.write(bytes([i + 1]))
                
                # Points de broderie
                last_x = last_y = 0
                for point in design.points:
                    dx = int(point.x * 10) - last_x
                    dy = int(point.y * 10) - last_y
                    
                    # Limiter les déplacements à la plage valide
                    dx = max(min(dx, 127), -127)
                    dy = max(min(dy, 127), -127)
                    
                    if point.stitch_type == StitchType.NORMAL:
                        f.write(bytes([dx & 0xff, dy & 0xff]))
                    elif point.stitch_type == StitchType.JUMP:
                        f.write(bytes([0x80 | 0x40, dx & 0xff, dy & 0xff]))
                    elif point.stitch_type == StitchType.COLOR_CHANGE:
                        f.write(bytes([0xfe]))
                    
                    last_x += dx
                    last_y += dy
                
                # Marquer la fin
                f.write(bytes([0xff]))
                
                return True
                
        except Exception as e:
            print(f"Erreur lors de l'export PES : {str(e)}")
            return False

class DstExporter(EmbroideryExporter):
    """Exporteur au format DST (Tajima)"""
    
    def export(self, design: EmbroideryDesign, filepath: str) -> bool:
        try:
            with open(filepath, 'wb') as f:
                # En-tête DST standard
                header = bytearray(512)
                header[0:13] = b'LA:Desktop   '
                header[14:42] = f"ST:{len(design.points):6d}".encode()
                header[42:48] = b"+   0"
                header[48:54] = b"+   0"
                header[54:60] = b"+   0"
                header[60:66] = b"+   0"
                f.write(header)
                
                last_x = last_y = 0
                for point in design.points:
                    # Conversion en coordonnées relatives en 0.1mm
                    dx = int(point.x * 10) - last_x
                    dy = int(point.y * 10) - last_y
                    
                    # Calcul des bytes DST
                    x_dst = min(max(dx, -121), 121)
                    y_dst = min(max(dy, -121), 121)
                    
                    byte1 = byte2 = byte3 = 0
                    
                    if x_dst > 40:
                        byte1 |= 0x04
                    elif x_dst < -40:
                        byte1 |= 0x08
                    if y_dst > 40:
                        byte1 |= 0x20
                    elif y_dst < -40:
                        byte1 |= 0x10
                        
                    if point.stitch_type == StitchType.JUMP:
                        byte1 |= 0x83
                    elif point.stitch_type == StitchType.COLOR_CHANGE:
                        byte1 |= 0xc3
                        
                    byte2 |= abs(x_dst) % 41
                    byte3 |= abs(y_dst) % 41
                    
                    f.write(bytes([byte1, byte2, byte3]))
                    
                    last_x += dx
                    last_y += dy
                
                # Fin du fichier
                f.write(bytes([0x03, 0x00, 0x00]))
                return True
                
        except Exception as e:
            print(f"Erreur lors de l'export DST : {str(e)}")
            return False

class JefExporter(EmbroideryExporter):
    """Exporteur au format JEF (Janome)"""
    
    def export(self, design: EmbroideryDesign, filepath: str) -> bool:
        try:
            with open(filepath, 'wb') as f:
                num_colors = len(design.thread_colors)
                num_points = len(design.points)
                
                # En-tête JEF
                f.write(struct.pack('<I', num_colors))    # Nombre de couleurs
                f.write(struct.pack('<I', num_points))    # Nombre de points
                
                # Offset des données de points (après l'en-tête)
                data_offset = 128 + (num_colors * 4)
                f.write(struct.pack('<I', data_offset))
                
                # Dimensions
                size_x = self._convert_to_machine_units(design.size_mm[0])
                size_y = self._convert_to_machine_units(design.size_mm[1])
                f.write(struct.pack('<iiii', size_x, size_y, size_x, size_y))
                
                # Remplir l'en-tête jusqu'à 128 bytes
                f.write(b'\x00' * (116 - f.tell()))
                
                # Liste des couleurs
                for i in range(num_colors):
                    f.write(struct.pack('<I', i + 1))
                
                # Points de broderie
                last_x = last_y = 0
                for point in design.points:
                    dx = int(point.x * 10) - last_x
                    dy = int(point.y * 10) - last_y
                    
                    # Limiter les déplacements
                    dx = max(min(dx, 127), -127)
                    dy = max(min(dy, 127), -127)
                    
                    if point.stitch_type == StitchType.NORMAL:
                        f.write(struct.pack('<bb', dx, dy))
                    elif point.stitch_type == StitchType.JUMP:
                        f.write(bytes([0x80, dx, dy]))
                    elif point.stitch_type == StitchType.COLOR_CHANGE:
                        f.write(bytes([0x7c]))
                    
                    last_x += dx
                    last_y += dy
                
                # Fin du fichier
                f.write(bytes([0x7f]))
                
                return True
                
        except Exception as e:
            print(f"Erreur lors de l'export JEF : {str(e)}")
            return False