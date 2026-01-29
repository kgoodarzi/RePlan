"""Segmentation element model - the atomic unit of selection."""

from dataclasses import dataclass, field
from typing import List, Tuple, Optional
import uuid
import numpy as np


# Label position options
LABEL_POSITIONS = [
    "top-left", "top-center", "top-right",
    "middle-left", "center", "middle-right",
    "bottom-left", "bottom-center", "bottom-right",
]


@dataclass
class SegmentElement:
    """
    A single segmentation element representing a selected region.
    
    This is the atomic unit of selection. Multiple elements can be
    grouped together to form an ObjectInstance.
    
    Attributes:
        element_id: Unique identifier
        category: Category name (e.g., "R" for rib)
        mode: Selection mode used ("flood", "polyline", "freeform", "line")
        points: Key points defining the selection
        mask: Binary mask array (H x W) where 255 = selected
        color: Display color (RGB tuple)
        label_position: Where to display the label (fixed position like "center", "top-left", etc.)
        label_anchor_offset: Custom offset (dx, dy) from centroid for freeform positioning. 
                             If set, overrides label_position. None means use label_position.
    """
    element_id: str = ""
    category: str = ""
    mode: str = "flood"
    points: List[Tuple[int, int]] = field(default_factory=list)
    mask: Optional[np.ndarray] = None
    color: Tuple[int, int, int] = (128, 128, 128)
    label_position: str = "center"
    label_anchor_offset: Optional[Tuple[int, int]] = None  # (dx, dy) offset from centroid
    
    def __post_init__(self):
        if not self.element_id:
            self.element_id = str(uuid.uuid4())[:8]
    
    @property
    def bounds(self) -> Optional[Tuple[int, int, int, int]]:
        """Get bounding box (x1, y1, x2, y2) of the mask."""
        if self.mask is None:
            return None
        ys, xs = np.where(self.mask > 0)
        if len(xs) == 0:
            return None
        return (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))
    
    @property
    def centroid(self) -> Optional[Tuple[int, int]]:
        """Get center point of the mask."""
        if self.mask is None:
            return None
        ys, xs = np.where(self.mask > 0)
        if len(xs) == 0:
            return None
        return (int(np.mean(xs)), int(np.mean(ys)))
    
    @property
    def area(self) -> int:
        """Get pixel area of the mask."""
        if self.mask is None:
            return 0
        return int(np.sum(self.mask > 0))
    
    def get_label_position(self) -> Optional[Tuple[int, int]]:
        """
        Calculate label position based on label_position setting or label_anchor_offset.
        
        If label_anchor_offset is set, returns centroid + offset.
        Otherwise, uses label_position to calculate position relative to bounds.
        """
        centroid = self.centroid
        if centroid is None:
            return None
        
        cx, cy = centroid
        
        # If custom anchor offset is set, use it
        if self.label_anchor_offset is not None:
            dx, dy = self.label_anchor_offset
            return (cx + dx, cy + dy)
        
        # Otherwise use fixed label_position
        bounds = self.bounds
        if bounds is None:
            return (cx, cy)
        
        x1, y1, x2, y2 = bounds
        
        positions = {
            "top-left": (x1, y1 - 5),
            "top-center": (cx, y1 - 5),
            "top-right": (x2, y1 - 5),
            "middle-left": (x1 - 5, cy),
            "center": (cx, cy),
            "middle-right": (x2 + 5, cy),
            "bottom-left": (x1, y2 + 15),
            "bottom-center": (cx, y2 + 15),
            "bottom-right": (x2, y2 + 15),
        }
        return positions.get(self.label_position, (cx, cy))
    
    def contains_point(self, x: int, y: int) -> bool:
        """Check if a point is within the mask."""
        if self.mask is None:
            return False
        h, w = self.mask.shape
        if not (0 <= x < w and 0 <= y < h):
            return False
        return self.mask[y, x] > 0
    
    def to_dict(self) -> dict:
        """Serialize to dictionary. Mask included for 'auto' mode using RLE encoding."""
        result = {
            "element_id": self.element_id,
            "category": self.category,
            "mode": self.mode,
            "points": self.points,
            "label_position": self.label_position,
            "label_anchor_offset": self.label_anchor_offset,
        }
        
        # For 'auto' and 'rect' modes, we must save the mask
        # since there are no points to reconstruct it from
        if self.mode in ["auto", "rect"] and self.mask is not None:
            # Find bounding box to minimize storage
            ys, xs = np.where(self.mask > 0)
            if len(xs) > 0 and len(ys) > 0:
                x1, x2 = int(np.min(xs)), int(np.max(xs)) + 1
                y1, y2 = int(np.min(ys)), int(np.max(ys)) + 1
                cropped = self.mask[y1:y2, x1:x2]
                
                # Encode as RLE (run-length encoding)
                flat = cropped.flatten()
                runs = []
                i = 0
                while i < len(flat):
                    val = int(flat[i])
                    count = 1
                    while i + count < len(flat) and flat[i + count] == val:
                        count += 1
                    runs.append([val, count])
                    i += count
                
                result["mask_bbox"] = [x1, y1, x2, y2]
                result["mask_shape"] = [int(cropped.shape[0]), int(cropped.shape[1])]
                result["mask_rle"] = runs
        
        return result
    
    @classmethod
    def from_dict(cls, data: dict, mask: Optional[np.ndarray] = None,
                  color: Tuple[int, int, int] = (128, 128, 128)) -> "SegmentElement":
        """Deserialize from dictionary."""
        anchor_offset = data.get("label_anchor_offset")
        if anchor_offset is not None:
            anchor_offset = tuple(anchor_offset)
        
        return cls(
            element_id=data.get("element_id", ""),
            category=data.get("category", ""),
            mode=data.get("mode", "flood"),
            points=[tuple(p) for p in data.get("points", [])],
            mask=mask,
            color=color,
            label_position=data.get("label_position", "center"),
            label_anchor_offset=anchor_offset,
        )


