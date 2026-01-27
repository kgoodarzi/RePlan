"""Category definitions for segmentation.

This module is 100% portable from desktop - no changes needed.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple


@dataclass
class DynamicCategory:
    """
    A category for segmenting objects.
    
    Categories define how objects are classified and displayed.
    Each category has a color for visualization and a default
    selection mode.
    
    Attributes:
        name: Short name/key (e.g., "R")
        prefix: Prefix for auto-naming (e.g., "R" → R1, R2, R3)
        full_name: Display name (e.g., "Rib")
        color_rgb: RGB color tuple for display
        color_bgr: BGR color tuple for OpenCV
        selection_mode: Default tool ("flood", "polyline", "line", etc.)
        visible: Whether to show objects of this category
        instances: List of instance names created
    """
    name: str
    prefix: str
    full_name: str
    color_rgb: Tuple[int, int, int]
    color_bgr: Tuple[int, int, int] = field(default=None)
    selection_mode: str = "flood"
    visible: bool = True
    instances: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        if self.color_bgr is None:
            self.color_bgr = (self.color_rgb[2], self.color_rgb[1], self.color_rgb[0])
    
    @property
    def color_hex(self) -> str:
        """Get color as hex string."""
        r, g, b = self.color_rgb
        return f"#{r:02x}{g:02x}{b:02x}"
    
    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "name": self.name,
            "prefix": self.prefix,
            "full_name": self.full_name,
            "color_rgb": list(self.color_rgb),
            "selection_mode": self.selection_mode,
            "visible": self.visible,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "DynamicCategory":
        """Deserialize from dictionary."""
        color = tuple(data.get("color_rgb", (128, 128, 128)))
        return cls(
            name=data.get("name", ""),
            prefix=data.get("prefix", ""),
            full_name=data.get("full_name", ""),
            color_rgb=color,
            selection_mode=data.get("selection_mode", "flood"),
            visible=data.get("visible", True),
        )


# Default categories available in the application
DEFAULT_CATEGORIES: Dict[str, Tuple[str, Tuple[int, int, int], str]] = {
    # Special categories
    "planform": ("Planform/View", (0, 200, 100), "polyline"),
    "textbox": ("Text/Description", (200, 200, 100), "polyline"),
    
    # Manual mask markers (for hide text/hatching feature)
    "mark_text": ("Mark as Text", (255, 200, 0), "flood"),
    "mark_hatch": ("Mark as Hatching", (200, 0, 255), "flood"),
    
    # Structural categories
    "longeron": ("Longeron", (0, 80, 200), "line"),
    "spar": ("Spar", (0, 120, 255), "line"),
    
    # Common model aircraft categories
    "R": ("Rib", (220, 60, 60), "flood"),
    "F": ("Former", (200, 80, 80), "flood"),
    "FS": ("Fuselage Side", (80, 80, 200), "flood"),
    "WT": ("Wing Tip", (60, 150, 220), "flood"),
    "T": ("Tail", (200, 80, 200), "flood"),
    "TS": ("Tail Surface", (180, 100, 180), "flood"),
    "M": ("Motor Mount", (255, 140, 0), "flood"),
    "UC": ("Undercarriage", (255, 150, 180), "flood"),
    "B": ("Misc Part", (140, 140, 140), "flood"),
    "L": ("Longeron", (0, 80, 200), "line"),
}


# Color palette for dynamically created categories
CATEGORY_COLORS: List[Tuple[int, int, int]] = [
    (220, 60, 60),    # Red
    (60, 180, 60),    # Green
    (60, 100, 220),   # Blue
    (255, 140, 0),    # Orange
    (200, 80, 200),   # Magenta
    (0, 180, 180),    # Cyan
    (140, 80, 180),   # Purple
    (255, 150, 180),  # Pink
    (180, 140, 100),  # Brown
    (140, 140, 140),  # Gray
    (200, 200, 60),   # Yellow
    (60, 200, 140),   # Teal
]


def create_default_categories() -> Dict[str, DynamicCategory]:
    """Create the default category dictionary."""
    categories = {}
    for key, (full_name, color, mode) in DEFAULT_CATEGORIES.items():
        categories[key] = DynamicCategory(
            name=key,
            prefix=key,
            full_name=full_name,
            color_rgb=color,
            selection_mode=mode,
        )
    return categories


def get_next_color(existing_count: int) -> Tuple[int, int, int]:
    """Get the next color from the palette."""
    return CATEGORY_COLORS[existing_count % len(CATEGORY_COLORS)]

