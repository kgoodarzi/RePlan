"""
Printing functionality for 1:1 scale output.

Provides functions to prepare images for printing at actual size,
using DPI information from the original PDF or user settings.
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

from replan.desktop.models import PageTab, DynamicCategory
from replan.desktop.core.rendering import Renderer


@dataclass
class PrintSettings:
    """Settings for print output."""
    target_dpi: float = 300.0  # Output DPI for print file
    margin_inches: float = 0.5  # Margin around content
    include_labels: bool = True
    include_scale_bar: bool = True
    paper_width_inches: float = 8.5  # Letter width
    paper_height_inches: float = 11.0  # Letter height
    
    @property
    def printable_width_inches(self) -> float:
        """Printable area width after margins."""
        return self.paper_width_inches - (2 * self.margin_inches)
    
    @property
    def printable_height_inches(self) -> float:
        """Printable area height after margins."""
        return self.paper_height_inches - (2 * self.margin_inches)
    
    @property
    def printable_width_px(self) -> int:
        """Printable area width in pixels."""
        return int(self.printable_width_inches * self.target_dpi)
    
    @property
    def printable_height_px(self) -> int:
        """Printable area height in pixels."""
        return int(self.printable_height_inches * self.target_dpi)


@dataclass
class TileInfo:
    """Information about a tile in a tiled print."""
    row: int
    col: int
    x_offset: float  # Offset in inches from top-left of full image
    y_offset: float
    width_inches: float  # Size of this tile's content
    height_inches: float
    image: Optional[np.ndarray] = None  # The tile image


class ScaledPrinter:
    """
    Prepares images for 1:1 scale printing.
    
    Uses the DPI information stored in PageTab to ensure parts
    print at their actual physical dimensions.
    """
    
    def __init__(self, renderer: Renderer = None):
        self.renderer = renderer or Renderer()
    
    def get_actual_scale(self, page: PageTab) -> float:
        """
        Calculate the actual scale factor from image pixels to inches.
        
        Returns:
            Pixels per inch based on PDF dimensions or DPI setting
        """
        return page.pixels_per_inch
    
    def prepare_print_image(self, page: PageTab,
                            categories: Dict[str, DynamicCategory],
                            settings: PrintSettings) -> np.ndarray:
        """
        Prepare a page image for 1:1 scale printing.
        
        Resamples the image to the target print DPI while maintaining
        the correct physical dimensions.
        
        Args:
            page: Page to print
            categories: Category definitions
            settings: Print settings
            
        Returns:
            Image ready for printing at target DPI
        """
        if page.original_image is None:
            return np.zeros((100, 100, 3), dtype=np.uint8)
        
        # Render the page with overlays
        rendered = self.renderer.render_page(
            page, categories,
            zoom=1.0,
            show_labels=settings.include_labels,
        )
        
        # Convert BGRA to BGR
        if rendered.shape[2] == 4:
            rendered = cv2.cvtColor(rendered, cv2.COLOR_BGRA2BGR)
        
        # Calculate scale factor to reach target DPI
        source_ppi = self.get_actual_scale(page)
        scale = settings.target_dpi / source_ppi
        
        # Resize image
        new_width = int(rendered.shape[1] * scale)
        new_height = int(rendered.shape[0] * scale)
        
        interp = cv2.INTER_LANCZOS4 if scale > 1 else cv2.INTER_AREA
        resized = cv2.resize(rendered, (new_width, new_height), interpolation=interp)
        
        # Add scale bar if requested
        if settings.include_scale_bar:
            resized = self._add_scale_bar(resized, settings.target_dpi)
        
        return resized
    
    def _add_scale_bar(self, image: np.ndarray, dpi: float,
                       bar_inches: float = 1.0) -> np.ndarray:
        """Add a scale bar to the image."""
        h, w = image.shape[:2]
        
        bar_px = int(bar_inches * dpi)
        bar_height = max(10, int(dpi / 30))  # Scale bar thickness
        margin = int(dpi / 10)
        
        # Position in bottom-left
        x1 = margin
        y1 = h - margin - bar_height
        x2 = x1 + bar_px
        y2 = y1 + bar_height
        
        # Draw white background
        cv2.rectangle(image, (x1 - 2, y1 - 2), (x2 + 2, y2 + 2), (255, 255, 255), -1)
        # Draw black bar
        cv2.rectangle(image, (x1, y1), (x2, y2), (0, 0, 0), -1)
        
        # Add label
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = max(0.4, dpi / 600)
        label = f'{bar_inches}"'
        
        text_size = cv2.getTextSize(label, font, font_scale, 1)[0]
        text_x = x1 + (bar_px - text_size[0]) // 2
        text_y = y1 - 5
        
        cv2.putText(image, label, (text_x, text_y), font, font_scale, (0, 0, 0), 1, cv2.LINE_AA)
        
        return image
    
    def get_physical_size(self, page: PageTab) -> Tuple[float, float]:
        """
        Get the physical size of the page in inches.
        
        Returns:
            (width_inches, height_inches)
        """
        if page.original_image is None:
            return (0.0, 0.0)
        
        h, w = page.original_image.shape[:2]
        ppi = self.get_actual_scale(page)
        
        return (w / ppi, h / ppi)
    
    def needs_tiling(self, page: PageTab, settings: PrintSettings) -> bool:
        """Check if the page needs to be tiled for printing."""
        width_in, height_in = self.get_physical_size(page)
        return (width_in > settings.printable_width_inches or
                height_in > settings.printable_height_inches)
    
    def calculate_tiles(self, page: PageTab, 
                        settings: PrintSettings) -> List[TileInfo]:
        """
        Calculate tile layout for large prints.
        
        Args:
            page: Page to tile
            settings: Print settings
            
        Returns:
            List of TileInfo for each tile
        """
        width_in, height_in = self.get_physical_size(page)
        
        if width_in <= 0 or height_in <= 0:
            return []
        
        tile_w = settings.printable_width_inches
        tile_h = settings.printable_height_inches
        
        cols = max(1, int(np.ceil(width_in / tile_w)))
        rows = max(1, int(np.ceil(height_in / tile_h)))
        
        tiles = []
        for row in range(rows):
            for col in range(cols):
                x_offset = col * tile_w
                y_offset = row * tile_h
                
                # Calculate actual tile size (may be smaller at edges)
                w = min(tile_w, width_in - x_offset)
                h = min(tile_h, height_in - y_offset)
                
                tiles.append(TileInfo(
                    row=row,
                    col=col,
                    x_offset=x_offset,
                    y_offset=y_offset,
                    width_inches=w,
                    height_inches=h,
                ))
        
        return tiles
    
    def render_tile(self, page: PageTab,
                    categories: Dict[str, DynamicCategory],
                    tile: TileInfo,
                    settings: PrintSettings) -> np.ndarray:
        """
        Render a single tile from the page.
        
        Args:
            page: Source page
            categories: Category definitions
            tile: Tile to render
            settings: Print settings
            
        Returns:
            Tile image at target DPI
        """
        if page.original_image is None:
            return np.zeros((settings.printable_height_px, settings.printable_width_px, 3), dtype=np.uint8)
        
        # Render full page
        rendered = self.renderer.render_page(
            page, categories,
            zoom=1.0,
            show_labels=settings.include_labels,
        )
        
        if rendered.shape[2] == 4:
            rendered = cv2.cvtColor(rendered, cv2.COLOR_BGRA2BGR)
        
        # Calculate source region in pixels
        source_ppi = self.get_actual_scale(page)
        
        x1 = int(tile.x_offset * source_ppi)
        y1 = int(tile.y_offset * source_ppi)
        x2 = int((tile.x_offset + tile.width_inches) * source_ppi)
        y2 = int((tile.y_offset + tile.height_inches) * source_ppi)
        
        # Clamp to image bounds
        x2 = min(x2, rendered.shape[1])
        y2 = min(y2, rendered.shape[0])
        
        # Extract region
        region = rendered[y1:y2, x1:x2]
        
        # Resize to target DPI
        scale = settings.target_dpi / source_ppi
        new_w = int(region.shape[1] * scale)
        new_h = int(region.shape[0] * scale)
        
        interp = cv2.INTER_LANCZOS4 if scale > 1 else cv2.INTER_AREA
        tile_image = cv2.resize(region, (new_w, new_h), interpolation=interp)
        
        # Add alignment marks
        tile_image = self._add_alignment_marks(tile_image, tile, settings)
        
        return tile_image
    
    def _add_alignment_marks(self, image: np.ndarray, 
                             tile: TileInfo,
                             settings: PrintSettings) -> np.ndarray:
        """Add alignment marks and tile info to a tile."""
        h, w = image.shape[:2]
        mark_size = int(settings.target_dpi / 8)  # 1/8" marks
        
        # Corner marks (L-shaped)
        color = (128, 128, 128)
        thickness = max(1, int(settings.target_dpi / 150))
        
        # Top-left
        cv2.line(image, (0, mark_size), (mark_size, mark_size), color, thickness)
        cv2.line(image, (mark_size, 0), (mark_size, mark_size), color, thickness)
        
        # Top-right  
        cv2.line(image, (w - mark_size, mark_size), (w, mark_size), color, thickness)
        cv2.line(image, (w - mark_size, 0), (w - mark_size, mark_size), color, thickness)
        
        # Bottom-left
        cv2.line(image, (0, h - mark_size), (mark_size, h - mark_size), color, thickness)
        cv2.line(image, (mark_size, h - mark_size), (mark_size, h), color, thickness)
        
        # Bottom-right
        cv2.line(image, (w - mark_size, h - mark_size), (w, h - mark_size), color, thickness)
        cv2.line(image, (w - mark_size, h - mark_size), (w - mark_size, h), color, thickness)
        
        # Tile label
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = max(0.3, settings.target_dpi / 800)
        label = f"Tile {tile.row + 1},{tile.col + 1}"
        
        text_size = cv2.getTextSize(label, font, font_scale, 1)[0]
        text_x = mark_size + 5
        text_y = mark_size + text_size[1] + 5
        
        cv2.putText(image, label, (text_x, text_y), font, font_scale, color, 1, cv2.LINE_AA)
        
        return image
    
    def export_for_print(self, path: str,
                         page: PageTab,
                         categories: Dict[str, DynamicCategory],
                         settings: PrintSettings = None) -> bool:
        """
        Export a page ready for 1:1 scale printing.
        
        Args:
            path: Output path (PNG or TIFF recommended for print)
            page: Page to export
            categories: Category definitions
            settings: Print settings (uses defaults if None)
            
        Returns:
            True if successful
        """
        settings = settings or PrintSettings()
        
        try:
            image = self.prepare_print_image(page, categories, settings)
            cv2.imwrite(path, image)
            return True
        except Exception as e:
            print(f"Error exporting for print: {e}")
            return False
    
    def export_tiles(self, output_dir: str,
                     page: PageTab,
                     categories: Dict[str, DynamicCategory],
                     settings: PrintSettings = None,
                     filename_prefix: str = "tile") -> List[str]:
        """
        Export a page as tiles for large format printing.
        
        Args:
            output_dir: Output directory
            page: Page to export
            categories: Category definitions
            settings: Print settings
            filename_prefix: Prefix for tile filenames
            
        Returns:
            List of created file paths
        """
        settings = settings or PrintSettings()
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        
        tiles = self.calculate_tiles(page, settings)
        created_files = []
        
        for tile in tiles:
            tile_image = self.render_tile(page, categories, tile, settings)
            
            filename = f"{filename_prefix}_{tile.row + 1}_{tile.col + 1}.png"
            filepath = out_path / filename
            
            cv2.imwrite(str(filepath), tile_image)
            created_files.append(str(filepath))
        
        return created_files


def get_recommended_settings(page: PageTab) -> PrintSettings:
    """
    Get recommended print settings based on page dimensions.
    
    Args:
        page: Page to analyze
        
    Returns:
        Recommended PrintSettings
    """
    settings = PrintSettings()
    
    # Get physical size
    if page.original_image is not None:
        h, w = page.original_image.shape[:2]
        ppi = page.pixels_per_inch
        width_in = w / ppi
        height_in = h / ppi
        
        # Use larger paper if needed
        if width_in > 8.5 or height_in > 11:
            # Try landscape
            if width_in <= 11 and height_in <= 8.5:
                settings.paper_width_inches = 11.0
                settings.paper_height_inches = 8.5
            # Try tabloid
            elif width_in <= 17 and height_in <= 11:
                settings.paper_width_inches = 17.0
                settings.paper_height_inches = 11.0
    
    return settings
