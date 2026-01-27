"""Object attributes for segmented components."""

from dataclasses import dataclass, field
from typing import List

# Material options for model aircraft components
MATERIALS: List[str] = [
    "balsa",
    "basswood", 
    "plywood",
    "lite-ply",
    "spruce",
    "hardwood",
    "foam",
    "depron",
    "carbon fiber",
    "fiberglass",
    "wire",
    "aluminum",
    "plastic",
    "covering",
    "complex",
    "other",
]

# Component types
TYPES: List[str] = [
    "stick",
    "sheet",
    "block",
    "tube",
    "dowel",
    "electrical",
    "hardware",
    "covering",
    "control surface",
    "structural",
    "other",
]

# View types for instances
VIEWS: List[str] = [
    "top",
    "side", 
    "front",
    "rear",
    "isometric",
    "section",
    "detail",
    "template",
    "cutout",
]


@dataclass
class ObjectAttributes:
    """
    Attributes describing a segmented object's physical properties.
    
    These attributes help define material requirements and dimensions
    for manufacturing or modification purposes.
    """
    material: str = ""
    width: float = 0.0
    height: float = 0.0
    depth: float = 0.0
    obj_type: str = ""
    view: str = ""
    description: str = ""
    url: str = ""
    
    # Additional metadata
    quantity: int = 1
    notes: str = ""
    
    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "material": self.material,
            "width": self.width,
            "height": self.height,
            "depth": self.depth,
            "obj_type": self.obj_type,
            "view": self.view,
            "description": self.description,
            "url": self.url,
            "quantity": self.quantity,
            "notes": self.notes,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "ObjectAttributes":
        """Deserialize from dictionary."""
        return cls(
            material=data.get("material", ""),
            width=data.get("width", 0.0),
            height=data.get("height", 0.0),
            depth=data.get("depth", 0.0),
            obj_type=data.get("obj_type", ""),
            view=data.get("view", ""),
            description=data.get("description", ""),
            url=data.get("url", ""),
            quantity=data.get("quantity", 1),
            notes=data.get("notes", ""),
        )
    
    @property
    def has_dimensions(self) -> bool:
        """Check if any dimensions are set."""
        return self.width > 0 or self.height > 0 or self.depth > 0
    
    @property
    def size_string(self) -> str:
        """Format dimensions as string."""
        parts = []
        if self.width > 0:
            parts.append(f"W:{self.width}")
        if self.height > 0:
            parts.append(f"H:{self.height}")
        if self.depth > 0:
            parts.append(f"D:{self.depth}")
        return " × ".join(parts) if parts else ""


