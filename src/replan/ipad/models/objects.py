"""Segmented object and instance models.

This module is 100% portable from desktop - no changes needed.
"""

from dataclasses import dataclass, field
from typing import List, Optional
import uuid

from .elements import SegmentElement
from .attributes import ObjectAttributes


@dataclass
class ObjectInstance:
    """
    An instance of an object - the object appearing in a specific view/location.
    
    An object like "R1" (Rib 1) might appear multiple times:
    - Instance 1: Side view showing the rib's profile
    - Instance 2: Template view showing the full shape
    
    Each instance can contain multiple grouped elements that together
    form that particular view of the object.
    
    Attributes:
        instance_id: Unique identifier
        instance_num: Display number (1, 2, 3...)
        elements: List of grouped elements forming this instance
        page_id: Which page this instance is on
        view_type: Type of view ("side", "top", "template", etc.)
        attributes: Physical attributes (material, size, etc.) - per instance
    """
    instance_id: str = ""
    instance_num: int = 1
    elements: List[SegmentElement] = field(default_factory=list)
    page_id: Optional[str] = None
    view_type: str = ""
    attributes: ObjectAttributes = field(default_factory=ObjectAttributes)
    
    def __post_init__(self):
        if not self.instance_id:
            self.instance_id = str(uuid.uuid4())[:8]
    
    @property
    def is_grouped(self) -> bool:
        """True if this instance has multiple grouped elements."""
        return len(self.elements) > 1
    
    @property
    def element_count(self) -> int:
        """Number of elements in this instance."""
        return len(self.elements)
    
    @property
    def total_area(self) -> int:
        """Total pixel area of all elements."""
        return sum(e.area for e in self.elements)
    
    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "instance_id": self.instance_id,
            "instance_num": self.instance_num,
            "page_id": self.page_id,
            "view_type": self.view_type,
            "elements": [e.to_dict() for e in self.elements],
            "attributes": self.attributes.to_dict(),
        }
    
    @classmethod
    def from_dict(cls, data: dict, elements: List[SegmentElement] = None) -> "ObjectInstance":
        """Deserialize from dictionary."""
        return cls(
            instance_id=data.get("instance_id", ""),
            instance_num=data.get("instance_num", 1),
            elements=elements or [],
            page_id=data.get("page_id"),
            view_type=data.get("view_type", ""),
            attributes=ObjectAttributes.from_dict(data.get("attributes", {})),
        )


@dataclass
class SegmentedObject:
    """
    A named object that can have multiple instances across pages/views.
    
    Hierarchy:
        Object (R1) - A named entity like "Rib 1"
        └── Instance 1 (side view) - Appearance in one view
              └── Element(s) - Grouped selections forming this view
              └── Attributes (material, size, view, etc.)
        └── Instance 2 (template) - Appearance in another view
              └── Element(s)
              └── Attributes (may differ from instance 1)
    
    Attributes:
        object_id: Unique identifier
        name: Display name (e.g., "R1", "F2")
        category: Category key (e.g., "R" for rib)
        instances: List of instances across views/pages
    """
    object_id: str = ""
    name: str = ""
    category: str = ""
    instances: List[ObjectInstance] = field(default_factory=list)
    
    def __post_init__(self):
        if not self.object_id:
            self.object_id = str(uuid.uuid4())[:8]
    
    @property
    def element_count(self) -> int:
        """Total number of elements across all instances."""
        return sum(inst.element_count for inst in self.instances)
    
    @property
    def instance_count(self) -> int:
        """Number of instances."""
        return len(self.instances)
    
    @property
    def is_simple(self) -> bool:
        """True if just one instance with one element (no grouping)."""
        return (len(self.instances) == 1 and 
                len(self.instances[0].elements) == 1)
    
    @property
    def has_multiple_instances(self) -> bool:
        """True if object appears in multiple views/pages."""
        return len(self.instances) > 1
    
    @property
    def has_grouped_elements(self) -> bool:
        """True if any instance has multiple grouped elements."""
        return any(inst.is_grouped for inst in self.instances)
    
    def get_instance_for_page(self, page_id: str) -> Optional[ObjectInstance]:
        """Get instance on a specific page."""
        for inst in self.instances:
            if inst.page_id == page_id:
                return inst
        return None
    
    def add_instance(self, view_type: str = "", page_id: str = None) -> ObjectInstance:
        """Create and add a new instance."""
        inst = ObjectInstance(
            instance_num=len(self.instances) + 1,
            page_id=page_id,
            view_type=view_type,
        )
        self.instances.append(inst)
        return inst
    
    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "object_id": self.object_id,
            "name": self.name,
            "category": self.category,
            "instances": [inst.to_dict() for inst in self.instances],
        }
    
    @classmethod
    def from_dict(cls, data: dict, instances: List[ObjectInstance] = None) -> "SegmentedObject":
        """Deserialize from dictionary."""
        obj = cls(
            object_id=data.get("object_id", data.get("group_id", "")),  # backward compat
            name=data.get("name", ""),
            category=data.get("category", ""),
            instances=instances or [],
        )
        # Backward compatibility: migrate object-level attributes to first instance
        if "attributes" in data and obj.instances:
            old_attrs = ObjectAttributes.from_dict(data.get("attributes", {}))
            if old_attrs.material or old_attrs.obj_type:  # Only if there's actual data
                obj.instances[0].attributes = old_attrs
        return obj


# Backward compatibility alias
ObjectGroup = SegmentedObject

