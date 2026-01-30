"""Parts library system for saving and reusing common part shapes."""

import json
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
import uuid
import numpy as np
import cv2

from replan.desktop.models import SegmentedObject, ObjectInstance, SegmentElement, ObjectAttributes


@dataclass
class LibraryPart:
    """Represents a part template in the library."""
    part_id: str
    name: str
    category: str
    description: str = ""
    tags: List[str] = None
    elements: List[dict] = None  # Serialized element data
    attributes: dict = None  # ObjectAttributes as dict
    thumbnail: Optional[np.ndarray] = None  # Small preview image
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if self.elements is None:
            self.elements = []
        if self.attributes is None:
            self.attributes = {}
    
    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        data = asdict(self)
        # Convert thumbnail to base64 if present
        if self.thumbnail is not None:
            import base64
            _, buffer = cv2.imencode('.png', self.thumbnail)
            data['thumbnail_base64'] = base64.b64encode(buffer).decode('utf-8')
        else:
            data['thumbnail_base64'] = None
        data.pop('thumbnail', None)  # Remove numpy array
        return data
    
    @classmethod
    def from_dict(cls, data: dict) -> "LibraryPart":
        """Deserialize from dictionary."""
        # Decode thumbnail if present
        thumbnail = None
        if data.get('thumbnail_base64'):
            import base64
            img_data = base64.b64decode(data['thumbnail_base64'])
            nparr = np.frombuffer(img_data, np.uint8)
            thumbnail = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        data.pop('thumbnail_base64', None)
        return cls(**data, thumbnail=thumbnail)


class PartsLibrary:
    """Manages a library of reusable part templates."""
    
    def __init__(self, library_path: Optional[str] = None):
        """
        Initialize the parts library.
        
        Args:
            library_path: Path to library file (.plib). If None, uses default location.
        """
        if library_path is None:
            # Default location: user's home directory / .replan / library.plib
            home = Path.home()
            library_path = home / ".replan" / "library.plib"
        
        self.library_path = Path(library_path)
        self.parts: Dict[str, LibraryPart] = {}
        self._ensure_directory()
        self.load()
    
    def _ensure_directory(self):
        """Ensure library directory exists."""
        self.library_path.parent.mkdir(parents=True, exist_ok=True)
    
    def load(self) -> bool:
        """Load library from file."""
        if not self.library_path.exists():
            return True  # No file yet, start with empty library
        
        try:
            with open(self.library_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.parts = {}
            for part_data in data.get('parts', []):
                part = LibraryPart.from_dict(part_data)
                self.parts[part.part_id] = part
            
            return True
        except Exception as e:
            print(f"Error loading parts library: {e}")
            return False
    
    def save(self) -> bool:
        """Save library to file."""
        try:
            data = {
                'version': '1.0',
                'parts': [part.to_dict() for part in self.parts.values()]
            }
            
            with open(self.library_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            return True
        except Exception as e:
            print(f"Error saving parts library: {e}")
            return False
    
    def add_part(self, obj: SegmentedObject, name: str = None, 
                 description: str = "", tags: List[str] = None) -> str:
        """
        Add a part to the library.
        
        Args:
            obj: SegmentedObject to save as template
            name: Part name (uses obj.name if None)
            description: Optional description
            tags: Optional tags for categorization
            
        Returns:
            Part ID
        """
        part_id = str(uuid.uuid4())[:8]
        name = name or obj.name or f"Part {part_id}"
        
        # Serialize elements
        elements = []
        for inst in obj.instances:
            for elem in inst.elements:
                elem_data = {
                    'mode': elem.mode,
                    'points': elem.points,
                    'category': elem.category,
                    'color': elem.color,
                    'label_position': elem.label_position,
                }
                # Store mask as RLE if present
                if elem.mask is not None:
                    elem_data['mask_rle'] = self._encode_mask_rle(elem.mask)
                    elem_data['mask_shape'] = list(elem.mask.shape)
                elements.append(elem_data)
        
        # Get attributes from first instance
        attrs = {}
        if obj.instances and obj.instances[0].attributes:
            attrs = obj.instances[0].attributes.to_dict()
        
        # Generate thumbnail from first element's mask
        thumbnail = None
        if obj.instances:
            for inst in obj.instances:
                for elem in inst.elements:
                    if elem.mask is not None:
                        # Create small thumbnail
                        h, w = elem.mask.shape[:2]
                        scale = min(64.0 / max(h, w), 1.0)
                        new_h, new_w = int(h * scale), int(w * scale)
                        if new_h > 0 and new_w > 0:
                            thumbnail = cv2.resize(elem.mask, (new_w, new_h), interpolation=cv2.INTER_AREA)
                            # Convert to BGR for thumbnail
                            thumbnail = cv2.cvtColor(thumbnail, cv2.COLOR_GRAY2BGR)
                        break
                if thumbnail is not None:
                    break
        
        part = LibraryPart(
            part_id=part_id,
            name=name,
            category=obj.category,
            description=description,
            tags=tags or [],
            elements=elements,
            attributes=attrs,
            thumbnail=thumbnail
        )
        
        self.parts[part_id] = part
        self.save()
        return part_id
    
    def get_part(self, part_id: str) -> Optional[LibraryPart]:
        """Get a part by ID."""
        return self.parts.get(part_id)
    
    def list_parts(self, category: str = None, tag: str = None) -> List[LibraryPart]:
        """List parts, optionally filtered by category or tag."""
        parts = list(self.parts.values())
        
        if category:
            parts = [p for p in parts if p.category == category]
        
        if tag:
            parts = [p for p in parts if tag in p.tags]
        
        return parts
    
    def delete_part(self, part_id: str) -> bool:
        """Delete a part from the library."""
        if part_id in self.parts:
            del self.parts[part_id]
            self.save()
            return True
        return False
    
    def instantiate_part(self, part_id: str, page_image_shape: tuple,
                        scale: float = 1.0, x: int = 0, y: int = 0) -> Optional[SegmentedObject]:
        """
        Create a SegmentedObject from a library part.
        
        Args:
            part_id: Part ID to instantiate
            page_image_shape: (height, width) of target page image
            scale: Scale factor (1.0 = original size)
            x, y: Position offset
            
        Returns:
            SegmentedObject or None if part not found
        """
        part = self.get_part(part_id)
        if not part:
            return None
        
        h, w = page_image_shape
        
        # Reconstruct elements
        elements = []
        for elem_data in part.elements:
            mask = None
            if 'mask_rle' in elem_data and 'mask_shape' in elem_data:
                mask = self._decode_mask_rle(elem_data['mask_rle'], tuple(elem_data['mask_shape']))
                # Scale mask if needed
                if scale != 1.0 and mask is not None:
                    new_h, new_w = int(mask.shape[0] * scale), int(mask.shape[1] * scale)
                    if new_h > 0 and new_w > 0:
                        mask = cv2.resize(mask, (new_w, new_h), interpolation=cv2.INTER_NEAREST)
            
            # Scale and offset points
            points = [(int((px * scale) + x), int((py * scale) + y)) 
                     for px, py in elem_data.get('points', [])]
            
            elem = SegmentElement(
                element_id=str(uuid.uuid4())[:8],
                category=elem_data.get('category', part.category),
                mode=elem_data.get('mode', 'flood'),
                points=points,
                mask=mask,
                color=elem_data.get('color', (128, 128, 128)),
                label_position=elem_data.get('label_position', 'center')
            )
            elements.append(elem)
        
        # Create instance
        inst = ObjectInstance(
            instance_id=str(uuid.uuid4())[:8],
            instance_num=1,
            page_id="",  # Will be set when added to page
            elements=elements,
            attributes=ObjectAttributes.from_dict(part.attributes) if part.attributes else ObjectAttributes()
        )
        
        # Create object
        obj = SegmentedObject(
            object_id=str(uuid.uuid4())[:8],
            name=part.name,
            category=part.category,
            instances=[inst]
        )
        
        return obj
    
    def _encode_mask_rle(self, mask: np.ndarray) -> list:
        """Encode mask as run-length encoding."""
        flat = mask.flatten()
        runs = []
        i = 0
        while i < len(flat):
            val = flat[i]
            count = 1
            while i + count < len(flat) and flat[i + count] == val:
                count += 1
            runs.append([int(val), count])
            i += count
        return runs
    
    def _decode_mask_rle(self, rle: list, shape: tuple) -> np.ndarray:
        """Decode run-length encoding to mask."""
        flat = []
        for val, count in rle:
            flat.extend([val] * count)
        return np.array(flat, dtype=np.uint8).reshape(shape)
