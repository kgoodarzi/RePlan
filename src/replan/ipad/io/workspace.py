"""Workspace save/load operations for iPad.

Adapted from desktop version - uses PIL instead of cv2 for image I/O.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import numpy as np
from PIL import Image

from ..models import (
    PageTab, SegmentedObject, ObjectInstance, SegmentElement,
    ObjectAttributes, DynamicCategory,
)
from ..core.segmentation import SegmentationEngine


VERSION = "5.0-ipad"


class WorkspaceData:
    """Container for loaded workspace data."""
    
    def __init__(self):
        self.pages: List[PageTab] = []
        self.categories: Dict[str, DynamicCategory] = {}
        self.objects: List[SegmentedObject] = []
        self.version: str = ""
        self.timestamp: str = ""
        self.view_state: dict = {}


class WorkspaceManager:
    """
    Manages workspace save and load operations.
    
    Workspace files (.pmw) contain:
    - All page definitions
    - All segmented objects with their instances and elements
    - Category definitions
    - Metadata (version, timestamp)
    
    Images are saved alongside the workspace file.
    """
    
    def __init__(self, tolerance: int = 5, line_thickness: int = 3):
        self.tolerance = tolerance
        self.line_thickness = line_thickness
    
    def save(self, 
             path: str,
             pages: List[PageTab],
             categories: Dict[str, DynamicCategory],
             objects: List[SegmentedObject] = None,
             view_state: dict = None) -> bool:
        """
        Save workspace to file.
        
        Returns:
            True if successful
        """
        try:
            workspace_dir = Path(path).parent
            workspace_dir.mkdir(parents=True, exist_ok=True)
            
            objects = objects or []
            view_state = view_state or {}
            
            data = {
                "version": VERSION,
                "timestamp": datetime.now().isoformat(),
                "categories": self._serialize_categories(categories),
                "objects": [self._serialize_object(obj) for obj in objects],
                "pages": [],
                "view_state": view_state,
            }
            
            for page in pages:
                # Save image using PIL
                if page.original_image is not None:
                    img_filename = f"{page.model_name}_{page.page_name}_raster.png"
                    img_path = workspace_dir / img_filename
                    
                    # Convert from BGR to RGB if needed and save
                    pil_img = Image.fromarray(page.original_image)
                    pil_img.save(str(img_path), 'PNG')
                else:
                    img_filename = ""
                
                page_data = {
                    "tab_id": page.tab_id,
                    "model_name": page.model_name,
                    "page_name": page.page_name,
                    "source_path": page.source_path,
                    "rotation": page.rotation,
                    "active": page.active,
                    "image_file": img_filename,
                    "dpi": getattr(page, 'dpi', 150.0),
                    "pdf_width_inches": getattr(page, 'pdf_width_inches', 0.0),
                    "pdf_height_inches": getattr(page, 'pdf_height_inches', 0.0),
                }
                
                data["pages"].append(page_data)
            
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            
            return True
            
        except Exception as e:
            print(f"Error saving workspace: {e}")
            return False
    
    def load(self, path: str) -> Optional[WorkspaceData]:
        """
        Load workspace from file.
        
        Returns:
            WorkspaceData or None if failed
        """
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            workspace_dir = Path(path).parent
            result = WorkspaceData()
            result.version = data.get("version", "")
            result.timestamp = data.get("timestamp", "")
            
            # Load categories
            result.categories = self._deserialize_categories(data.get("categories", {}))
            
            # Load pages
            pages_data = data.get("pages", data.get("tabs", []))
            page_images = {}
            
            for page_data in pages_data:
                img_file = page_data.get("image_file", page_data.get("raster_file", ""))
                img_path = workspace_dir / img_file if img_file else None
                
                image = None
                if img_path and img_path.exists():
                    # Load with PIL
                    pil_img = Image.open(str(img_path))
                    image = np.array(pil_img)
                
                if image is None:
                    continue
                
                tab_id = page_data.get("tab_id", "")
                page_images[tab_id] = image
                
                page = PageTab(
                    tab_id=tab_id,
                    model_name=page_data.get("model_name", ""),
                    page_name=page_data.get("page_name", ""),
                    original_image=image,
                    source_path=page_data.get("source_path"),
                    rotation=page_data.get("rotation", 0),
                    active=page_data.get("active", True),
                    dpi=page_data.get("dpi", 150.0),
                    pdf_width_inches=page_data.get("pdf_width_inches", 0.0),
                    pdf_height_inches=page_data.get("pdf_height_inches", 0.0),
                    objects=[],
                )
                
                result.pages.append(page)
                
                # Backward compat: load per-page objects
                objects_data = page_data.get("objects", page_data.get("groups", []))
                h, w = image.shape[:2]
                for obj_data in objects_data:
                    obj = self._deserialize_object(obj_data, (h, w), image, result.categories)
                    if obj and obj.instances:
                        result.objects.append(obj)
            
            # Load global objects
            global_objects_data = data.get("objects", [])
            for obj_data in global_objects_data:
                page_id = None
                for inst_data in obj_data.get("instances", []):
                    page_id = inst_data.get("page_id")
                    if page_id:
                        break
                
                image = page_images.get(page_id) if page_id else None
                if image is None and page_images:
                    image = next(iter(page_images.values()))
                
                if image is not None:
                    h, w = image.shape[:2]
                    obj = self._deserialize_object(obj_data, (h, w), image, result.categories, page_images)
                    if obj and obj.instances:
                        result.objects.append(obj)
            
            result.view_state = data.get("view_state", {})
            
            return result
            
        except Exception as e:
            print(f"Error loading workspace: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _serialize_categories(self, categories: Dict[str, DynamicCategory]) -> dict:
        """Serialize categories to dictionary."""
        return {k: v.to_dict() for k, v in categories.items()}
    
    def _deserialize_categories(self, data: dict) -> Dict[str, DynamicCategory]:
        """Deserialize categories from dictionary."""
        return {k: DynamicCategory.from_dict(v) for k, v in data.items()}
    
    def _serialize_object(self, obj: SegmentedObject) -> dict:
        """Serialize a segmented object."""
        return {
            "object_id": obj.object_id,
            "name": obj.name,
            "category": obj.category,
            "instances": [
                {
                    "instance_id": inst.instance_id,
                    "instance_num": inst.instance_num,
                    "page_id": inst.page_id,
                    "view_type": inst.view_type,
                    "attributes": inst.attributes.to_dict(),
                    "elements": [elem.to_dict() for elem in inst.elements],
                }
                for inst in obj.instances
            ],
        }
    
    def _deserialize_object(self,
                            data: dict,
                            image_shape: Tuple[int, int],
                            image: np.ndarray,
                            categories: Dict[str, DynamicCategory],
                            page_images: Dict[str, np.ndarray] = None) -> Optional[SegmentedObject]:
        """Deserialize a segmented object."""
        h, w = image_shape
        category = data.get("category", "")
        cat = categories.get(category)
        color = cat.color_rgb if cat else (128, 128, 128)
        page_images = page_images or {}
        
        engine = SegmentationEngine(self.tolerance, self.line_thickness)
        
        instances = []
        for inst_data in data.get("instances", []):
            elements = []
            
            inst_page_id = inst_data.get("page_id")
            inst_image = page_images.get(inst_page_id, image) if inst_page_id else image
            inst_h, inst_w = inst_image.shape[:2] if inst_image is not None else (h, w)
            
            for elem_data in inst_data.get("elements", []):
                points = [tuple(p) for p in elem_data.get("points", [])]
                mode = elem_data.get("mode", "flood")
                
                # Reconstruct mask
                mask = np.zeros((inst_h, inst_w), dtype=np.uint8)
                
                if mode == "flood" and points and inst_image is not None:
                    px, py = points[0]
                    if 0 <= px < inst_w and 0 <= py < inst_h:
                        mask = engine.flood_fill(inst_image, (px, py))
                elif mode == "polyline" and len(points) >= 3:
                    mask = engine.create_polygon_mask((inst_h, inst_w), points)
                elif mode in ["line", "freeform"] and len(points) >= 2:
                    mask = engine.create_line_mask((inst_h, inst_w), points)
                
                elem = SegmentElement(
                    element_id=elem_data.get("element_id", ""),
                    category=category,
                    mode=mode,
                    points=points,
                    mask=mask,
                    color=color,
                    label_position=elem_data.get("label_position", "center"),
                )
                elements.append(elem)
            
            if elements:
                inst_attrs = ObjectAttributes.from_dict(inst_data.get("attributes", {}))
                
                inst = ObjectInstance(
                    instance_id=inst_data.get("instance_id", ""),
                    instance_num=inst_data.get("instance_num", 1),
                    elements=elements,
                    page_id=inst_data.get("page_id"),
                    view_type=inst_data.get("view_type", ""),
                    attributes=inst_attrs,
                )
                instances.append(inst)
        
        if not instances:
            return None
        
        obj = SegmentedObject(
            object_id=data.get("object_id", data.get("group_id", "")),
            name=data.get("name", ""),
            category=category,
            instances=instances,
        )
        
        return obj

