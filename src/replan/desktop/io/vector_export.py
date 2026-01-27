"""
Vector export functionality for DXF and SVG formats.

Extracts contours from segmentation masks and exports them as vector paths
for CAD software, laser cutting, and scalable graphics applications.
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

from replan.desktop.models import PageTab, SegmentedObject, DynamicCategory
from replan.desktop.core.segmentation import SegmentationEngine


@dataclass
class VectorPath:
    """Represents a vector path extracted from a mask."""
    object_id: str
    object_name: str
    category: str
    instance_num: int
    element_id: str
    contour: np.ndarray  # Nx2 array of (x, y) points
    area: float
    is_outer: bool  # True for outer contour, False for holes
    color_rgb: Tuple[int, int, int]


class ContourExtractor:
    """Extracts vector contours from segmentation masks."""
    
    def __init__(self, simplify_epsilon: float = 1.0):
        """
        Initialize the contour extractor.
        
        Args:
            simplify_epsilon: Epsilon for Douglas-Peucker simplification.
                             Higher values = more simplification. 0 = no simplification.
        """
        self.simplify_epsilon = simplify_epsilon
        self.engine = SegmentationEngine()
    
    def extract_from_mask(self, mask: np.ndarray, 
                          simplify: bool = True) -> List[Tuple[np.ndarray, bool]]:
        """
        Extract contours from a binary mask.
        
        Args:
            mask: Binary mask (H x W) where 255 = filled region
            simplify: Whether to apply Douglas-Peucker simplification
            
        Returns:
            List of (contour, is_outer) tuples where contour is Nx2 array
        """
        if mask is None or not np.any(mask > 0):
            return []
        
        # Find contours with hierarchy
        contours, hierarchy = cv2.findContours(
            mask.astype(np.uint8),
            cv2.RETR_CCOMP,  # Two-level hierarchy for outer/inner
            cv2.CHAIN_APPROX_SIMPLE
        )
        
        if not contours or hierarchy is None:
            return []
        
        results = []
        hierarchy = hierarchy[0]  # Get the actual hierarchy array
        
        for i, contour in enumerate(contours):
            # Simplify if requested
            if simplify and self.simplify_epsilon > 0:
                contour = cv2.approxPolyDP(contour, self.simplify_epsilon, True)
            
            # Reshape to Nx2
            points = contour.reshape(-1, 2)
            
            if len(points) < 3:
                continue
            
            # Determine if this is an outer contour or a hole
            # In RETR_CCOMP: hierarchy[i][3] == -1 means outer contour
            is_outer = hierarchy[i][3] == -1
            
            results.append((points, is_outer))
        
        return results
    
    def extract_from_page(self, page: PageTab,
                          categories: Dict[str, DynamicCategory]) -> List[VectorPath]:
        """
        Extract all vector paths from a page.
        
        Args:
            page: Page to extract from
            categories: Category definitions for colors
            
        Returns:
            List of VectorPath objects
        """
        paths = []
        
        for obj in page.objects:
            cat = categories.get(obj.category)
            color = cat.color_rgb if cat else (128, 128, 128)
            
            for inst in obj.instances:
                # Only process instances for this page
                if inst.page_id != page.tab_id:
                    continue
                
                for elem in inst.elements:
                    if elem.mask is None:
                        continue
                    
                    contours = self.extract_from_mask(elem.mask)
                    
                    for contour, is_outer in contours:
                        area = cv2.contourArea(contour) if is_outer else 0
                        
                        path = VectorPath(
                            object_id=obj.object_id,
                            object_name=obj.name,
                            category=obj.category,
                            instance_num=inst.instance_num,
                            element_id=elem.element_id,
                            contour=contour,
                            area=area,
                            is_outer=is_outer,
                            color_rgb=color,
                        )
                        paths.append(path)
        
        return paths


class DXFExporter:
    """Exports vector paths to DXF format."""
    
    def __init__(self, extractor: ContourExtractor = None):
        self.extractor = extractor or ContourExtractor()
    
    def export_page(self, path: str, page: PageTab,
                    categories: Dict[str, DynamicCategory],
                    include_holes: bool = True,
                    flip_y: bool = True) -> bool:
        """
        Export a page to DXF format.
        
        Args:
            path: Output path
            page: Page to export
            categories: Category definitions
            include_holes: Whether to include hole contours
            flip_y: Whether to flip Y coordinates (DXF uses bottom-left origin)
            
        Returns:
            True if successful
        """
        try:
            paths = self.extractor.extract_from_page(page, categories)
            
            if not paths:
                print("No contours to export")
                return False
            
            # Get image height for Y-flip
            height = 0
            if page.original_image is not None:
                height = page.original_image.shape[0]
            
            # Build DXF content
            dxf_content = self._build_dxf(paths, height, include_holes, flip_y)
            
            with open(path, 'w') as f:
                f.write(dxf_content)
            
            return True
            
        except Exception as e:
            print(f"Error exporting DXF: {e}")
            return False
    
    def _build_dxf(self, paths: List[VectorPath], height: int,
                   include_holes: bool, flip_y: bool) -> str:
        """Build DXF file content."""
        lines = []
        
        # DXF Header
        lines.extend([
            "0", "SECTION",
            "2", "HEADER",
            "9", "$ACADVER",
            "1", "AC1014",  # AutoCAD R14 format
            "9", "$INSUNITS",
            "70", "0",  # Unitless (pixels)
            "0", "ENDSEC",
        ])
        
        # Tables section (layers)
        lines.extend([
            "0", "SECTION",
            "2", "TABLES",
            "0", "TABLE",
            "2", "LAYER",
        ])
        
        # Create layers for each category
        layer_colors = {}
        category_set = set(p.category for p in paths)
        for i, category in enumerate(sorted(category_set)):
            color = 7  # Default white
            # Find a path with this category to get the color
            for p in paths:
                if p.category == category:
                    # Map RGB to AutoCAD color index (simplified)
                    color = self._rgb_to_aci(p.color_rgb)
                    break
            layer_colors[category] = color
            
            lines.extend([
                "0", "LAYER",
                "2", category,
                "70", "0",
                "62", str(color),
                "6", "CONTINUOUS",
            ])
        
        lines.extend([
            "0", "ENDTAB",
            "0", "ENDSEC",
        ])
        
        # Entities section
        lines.extend([
            "0", "SECTION",
            "2", "ENTITIES",
        ])
        
        for path in paths:
            if not include_holes and not path.is_outer:
                continue
            
            contour = path.contour
            if len(contour) < 2:
                continue
            
            # Create LWPOLYLINE entity
            lines.extend([
                "0", "LWPOLYLINE",
                "8", path.category,  # Layer
                "90", str(len(contour)),  # Number of vertices
                "70", "1",  # Closed polyline
            ])
            
            for point in contour:
                x, y = float(point[0]), float(point[1])
                if flip_y and height > 0:
                    y = height - y
                lines.extend([
                    "10", f"{x:.3f}",
                    "20", f"{y:.3f}",
                ])
        
        lines.extend([
            "0", "ENDSEC",
            "0", "EOF",
        ])
        
        return "\n".join(lines)
    
    def _rgb_to_aci(self, rgb: Tuple[int, int, int]) -> int:
        """
        Convert RGB color to AutoCAD Color Index (simplified mapping).
        
        Returns the closest standard ACI color.
        """
        r, g, b = rgb
        
        # Standard ACI colors (simplified)
        aci_colors = {
            1: (255, 0, 0),      # Red
            2: (255, 255, 0),    # Yellow
            3: (0, 255, 0),      # Green
            4: (0, 255, 255),    # Cyan
            5: (0, 0, 255),      # Blue
            6: (255, 0, 255),    # Magenta
            7: (255, 255, 255),  # White
            8: (128, 128, 128),  # Gray
            9: (192, 192, 192),  # Light gray
        }
        
        # Find closest color
        min_dist = float('inf')
        best_aci = 7  # Default white
        
        for aci, (ar, ag, ab) in aci_colors.items():
            dist = (r - ar) ** 2 + (g - ag) ** 2 + (b - ab) ** 2
            if dist < min_dist:
                min_dist = dist
                best_aci = aci
        
        return best_aci


class SVGExporter:
    """Exports vector paths to SVG format."""
    
    def __init__(self, extractor: ContourExtractor = None):
        self.extractor = extractor or ContourExtractor()
    
    def export_page(self, path: str, page: PageTab,
                    categories: Dict[str, DynamicCategory],
                    include_holes: bool = True,
                    stroke_width: float = 1.0,
                    fill_opacity: float = 0.3) -> bool:
        """
        Export a page to SVG format.
        
        Args:
            path: Output path
            page: Page to export
            categories: Category definitions
            include_holes: Whether to include hole contours
            stroke_width: Width of outline strokes
            fill_opacity: Opacity of fill (0-1)
            
        Returns:
            True if successful
        """
        try:
            paths = self.extractor.extract_from_page(page, categories)
            
            if not paths:
                print("No contours to export")
                return False
            
            # Get image dimensions
            width, height = 100, 100
            if page.image_size:
                width, height = page.image_size
            
            # Build SVG content
            svg_content = self._build_svg(paths, width, height, 
                                          include_holes, stroke_width, fill_opacity)
            
            with open(path, 'w') as f:
                f.write(svg_content)
            
            return True
            
        except Exception as e:
            print(f"Error exporting SVG: {e}")
            return False
    
    def _build_svg(self, paths: List[VectorPath], width: int, height: int,
                   include_holes: bool, stroke_width: float, 
                   fill_opacity: float) -> str:
        """Build SVG file content."""
        lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
            '  <title>RePlan Vector Export</title>',
            '  <desc>Exported from RePlan segmentation</desc>',
        ]
        
        # Group paths by category
        by_category: Dict[str, List[VectorPath]] = {}
        for path in paths:
            if path.category not in by_category:
                by_category[path.category] = []
            by_category[path.category].append(path)
        
        # Create groups for each category
        for category, cat_paths in sorted(by_category.items()):
            if not cat_paths:
                continue
            
            # Get color from first path
            color = cat_paths[0].color_rgb
            hex_color = f"#{color[0]:02x}{color[1]:02x}{color[2]:02x}"
            
            lines.append(f'  <g id="{category}" class="category-{category}">')
            
            for path in cat_paths:
                if not include_holes and not path.is_outer:
                    continue
                
                contour = path.contour
                if len(contour) < 2:
                    continue
                
                # Build path data
                d = self._contour_to_path_data(contour)
                
                # Determine fill
                fill = hex_color if path.is_outer else "none"
                fill_attr = f'fill="{fill}"'
                if path.is_outer and fill_opacity < 1.0:
                    fill_attr = f'fill="{fill}" fill-opacity="{fill_opacity}"'
                
                # Element ID
                elem_id = f"{path.object_name}-{path.instance_num}-{path.element_id[:8]}"
                
                lines.append(
                    f'    <path id="{elem_id}" d="{d}" '
                    f'{fill_attr} stroke="{hex_color}" stroke-width="{stroke_width}" />'
                )
            
            lines.append('  </g>')
        
        lines.append('</svg>')
        
        return '\n'.join(lines)
    
    def _contour_to_path_data(self, contour: np.ndarray) -> str:
        """Convert contour points to SVG path data."""
        if len(contour) < 2:
            return ""
        
        # Start with move to first point
        parts = [f"M {contour[0][0]:.1f} {contour[0][1]:.1f}"]
        
        # Line to subsequent points
        for point in contour[1:]:
            parts.append(f"L {point[0]:.1f} {point[1]:.1f}")
        
        # Close path
        parts.append("Z")
        
        return " ".join(parts)


def export_dxf(path: str, page: PageTab, 
               categories: Dict[str, DynamicCategory], **kwargs) -> bool:
    """
    Convenience function to export a page to DXF.
    
    Args:
        path: Output file path
        page: Page to export
        categories: Category definitions
        **kwargs: Additional arguments for DXFExporter.export_page()
        
    Returns:
        True if successful
    """
    exporter = DXFExporter()
    return exporter.export_page(path, page, categories, **kwargs)


def export_svg(path: str, page: PageTab,
               categories: Dict[str, DynamicCategory], **kwargs) -> bool:
    """
    Convenience function to export a page to SVG.
    
    Args:
        path: Output file path
        page: Page to export
        categories: Category definitions
        **kwargs: Additional arguments for SVGExporter.export_page()
        
    Returns:
        True if successful
    """
    exporter = SVGExporter()
    return exporter.export_page(path, page, categories, **kwargs)
