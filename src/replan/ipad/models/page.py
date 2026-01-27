"""Page/Tab model for multi-page document support.

This module is 100% portable from desktop - no changes needed.
"""

from dataclasses import dataclass, field
from typing import List, Optional
import uuid
import numpy as np

from .objects import SegmentedObject


@dataclass
class PageTab:
    """
    Represents a single page/tab in the segmenter.
    
    Each page contains an image and a list of segmented objects.
    Pages can be from a multi-page PDF or individual image files.
    
    Attributes:
        tab_id: Unique identifier
        model_name: Name of the model/project
        page_name: Name of this page
        original_image: The source image (BGR format)
        segmentation_layer: Overlay layer for visualization
        objects: List of segmented objects on this page
        source_path: Original file path
        rotation: Applied rotation in degrees
        active: Whether page is included in exports
        dpi: Resolution in dots per inch (for scale calculation)
        pdf_width_inches: Original PDF page width in inches
        pdf_height_inches: Original PDF page height in inches
    """
    tab_id: str = ""
    model_name: str = ""
    page_name: str = ""
    original_image: Optional[np.ndarray] = None
    segmentation_layer: Optional[np.ndarray] = None
    objects: List[SegmentedObject] = field(default_factory=list)
    source_path: Optional[str] = None
    rotation: int = 0
    active: bool = True
    dpi: float = 150.0  # Default rasterization DPI
    pdf_width_inches: float = 0.0  # Original PDF width in inches
    pdf_height_inches: float = 0.0  # Original PDF height in inches
    
    def __post_init__(self):
        if not self.tab_id:
            self.tab_id = str(uuid.uuid4())[:8]
    
    @property
    def raster_filename(self) -> str:
        """Generate raster image filename."""
        return f"{self.model_name}_{self.page_name}_raster.png"
    
    @property
    def segmented_filename(self) -> str:
        """Generate segmented image filename."""
        return f"{self.model_name}_{self.page_name}_segmented.png"
    
    @property
    def display_name(self) -> str:
        """Generate display name for tab."""
        prefix = "" if self.active else "⏸ "
        return f"{prefix}{self.model_name} - {self.page_name}"
    
    @property
    def image_size(self) -> Optional[tuple]:
        """Get image dimensions (width, height)."""
        if self.original_image is None:
            return None
        h, w = self.original_image.shape[:2]
        return (w, h)
    
    @property
    def pixels_per_inch(self) -> float:
        """Calculate actual pixels per inch from image and PDF dimensions."""
        if self.original_image is None:
            return self.dpi
        h, w = self.original_image.shape[:2]
        # Use width for calculation (or average of width/height)
        if self.pdf_width_inches > 0:
            return w / self.pdf_width_inches
        return self.dpi
    
    @property
    def pixels_per_cm(self) -> float:
        """Calculate pixels per centimeter."""
        return self.pixels_per_inch / 2.54
    
    @property
    def object_count(self) -> int:
        """Number of objects on this page."""
        return len(self.objects)
    
    @property
    def element_count(self) -> int:
        """Total number of elements across all objects."""
        return sum(obj.element_count for obj in self.objects)
    
    def get_object_by_id(self, object_id: str) -> Optional[SegmentedObject]:
        """Find object by ID."""
        for obj in self.objects:
            if obj.object_id == object_id:
                return obj
        return None
    
    def get_element_at_point(self, x: int, y: int) -> Optional[tuple]:
        """
        Find element at a point.
        
        Returns:
            Tuple of (object, instance, element) or None
        """
        for obj in self.objects:
            for inst in obj.instances:
                for elem in inst.elements:
                    if elem.contains_point(x, y):
                        return (obj, inst, elem)
        return None
    
    def add_object(self, obj: SegmentedObject):
        """Add an object to this page."""
        self.objects.append(obj)
    
    def remove_object(self, object_id: str) -> bool:
        """Remove object by ID. Returns True if found and removed."""
        for i, obj in enumerate(self.objects):
            if obj.object_id == object_id:
                self.objects.pop(i)
                return True
        return False
    
    def clear_segmentation_layer(self):
        """Reset the segmentation overlay."""
        if self.original_image is not None:
            h, w = self.original_image.shape[:2]
            self.segmentation_layer = np.zeros((h, w, 4), dtype=np.uint8)
    
    def to_dict(self) -> dict:
        """Serialize to dictionary (image not included)."""
        return {
            "tab_id": self.tab_id,
            "model_name": self.model_name,
            "page_name": self.page_name,
            "source_path": self.source_path,
            "rotation": self.rotation,
            "active": self.active,
            "dpi": self.dpi,
            "pdf_width_inches": self.pdf_width_inches,
            "pdf_height_inches": self.pdf_height_inches,
            "objects": [obj.to_dict() for obj in self.objects],
        }
    
    @classmethod
    def from_dict(cls, data: dict, image: np.ndarray = None,
                  objects: List[SegmentedObject] = None) -> "PageTab":
        """Deserialize from dictionary."""
        return cls(
            tab_id=data.get("tab_id", ""),
            model_name=data.get("model_name", ""),
            page_name=data.get("page_name", ""),
            original_image=image,
            source_path=data.get("source_path"),
            rotation=data.get("rotation", 0),
            active=data.get("active", True),
            dpi=data.get("dpi", 150.0),
            pdf_width_inches=data.get("pdf_width_inches", 0.0),
            pdf_height_inches=data.get("pdf_height_inches", 0.0),
            objects=objects or [],
        )


# Backward compatibility - PageTab was previously used with 'groups' attribute
PageTab.groups = property(lambda self: self.objects)

