"""Workspace save/load operations."""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import cv2
import numpy as np

from replan.desktop.models import (
    PageTab, SegmentedObject, ObjectInstance, SegmentElement,
    ObjectAttributes, DynamicCategory,
)
from replan.desktop.core.segmentation import SegmentationEngine
from replan.desktop.utils.profiling import timed


VERSION = "5.0"


class WorkspaceData:
    """Container for loaded workspace data."""
    
    def __init__(self):
        self.pages: List[PageTab] = []
        self.categories: Dict[str, DynamicCategory] = {}
        self.objects: List[SegmentedObject] = []  # Global objects list
        self.version: str = ""
        self.timestamp: str = ""
        self.view_state: dict = {}  # Current page, panel widths, etc.


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
    
    @timed("workspace_save")
    def save(self, 
             path: str,
             pages: List[PageTab],
             categories: Dict[str, DynamicCategory],
             objects: List[SegmentedObject] = None,
             view_state: dict = None) -> bool:
        """
        Save workspace to file.
        
        Args:
            path: Path to .pmw file
            pages: List of pages to save
            categories: Category definitions
            view_state: Optional dict with current_page_id, sidebar_width, etc.
            
        Returns:
            True if successful
        """
        try:
            workspace_dir = Path(path).parent
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
                # Save image
                if page.original_image is not None:
                    img_filename = f"{page.model_name}_{page.page_name}_raster.png"
                    img_path = workspace_dir / img_filename
                    cv2.imwrite(str(img_path), page.original_image)
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
                    # Scale information
                    "dpi": getattr(page, 'dpi', 150.0),
                    "pdf_width_inches": getattr(page, 'pdf_width_inches', 0.0),
                    "pdf_height_inches": getattr(page, 'pdf_height_inches', 0.0),
                    # View state
                    "zoom_level": getattr(page, 'zoom_level', 1.0),
                    "scroll_x": getattr(page, 'scroll_x', 0.0),
                    "scroll_y": getattr(page, 'scroll_y', 0.0),
                    # View settings
                    "hide_background": getattr(page, 'hide_background', False),
                    "hide_text": getattr(page, 'hide_text', False),
                    "hide_hatching": getattr(page, 'hide_hatching', False),
                    # Text/hatching regions (masks stored as points for recreation)
                    "auto_text_regions": self._serialize_mask_regions(
                        getattr(page, 'auto_text_regions', [])
                    ),
                    "manual_text_regions": self._serialize_mask_regions(
                        getattr(page, 'manual_text_regions', [])
                    ),
                    "auto_hatch_regions": self._serialize_mask_regions(
                        getattr(page, 'auto_hatch_regions', [])
                    ),
                    "manual_hatch_regions": self._serialize_mask_regions(
                        getattr(page, 'manual_hatch_regions', [])
                    ),
                }
                
                data["pages"].append(page_data)
            
            # Optimize JSON serialization: use compact format for large workspaces
            # Use indent=2 for readability but ensure_ascii=False for performance
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            return True
            
        except Exception as e:
            print(f"Error saving workspace: {e}")
            return False
    
    @timed("workspace_load")
    def load(self, path: str) -> Optional[WorkspaceData]:
        """
        Load workspace from file.
        
        Args:
            path: Path to .pmw file
            
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
            
            # Load pages first to build image map
            pages_data = data.get("pages", data.get("tabs", []))
            page_images = {}  # tab_id -> (image, shape)
            
            for page_data in pages_data:
                # Find image file
                img_file = page_data.get("image_file", page_data.get("raster_file", ""))
                img_path = workspace_dir / img_file if img_file else None
                
                image = None
                if img_path and img_path.exists():
                    image = cv2.imread(str(img_path))
                
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
                    objects=[],  # Objects are now global
                )
                
                # Restore view state
                page.zoom_level = page_data.get("zoom_level", 1.0)
                page.scroll_x = page_data.get("scroll_x", 0.0)
                page.scroll_y = page_data.get("scroll_y", 0.0)
                
                # Restore view settings
                page.hide_background = page_data.get("hide_background", False)
                page.hide_text = page_data.get("hide_text", False)
                page.hide_hatching = page_data.get("hide_hatching", False)
                
                # Restore text/hatching regions
                page.auto_text_regions = self._deserialize_mask_regions(
                    page_data.get("auto_text_regions", []), image, "text"
                )
                page.manual_text_regions = self._deserialize_mask_regions(
                    page_data.get("manual_text_regions", []), image, "text"
                )
                page.auto_hatch_regions = self._deserialize_mask_regions(
                    page_data.get("auto_hatch_regions", []), image, "hatch"
                )
                page.manual_hatch_regions = self._deserialize_mask_regions(
                    page_data.get("manual_hatch_regions", []), image, "hatch"
                )
                result.pages.append(page)
                
                # Backward compatibility: load per-page objects and add to global list
                objects_data = page_data.get("objects", page_data.get("groups", []))
                h, w = image.shape[:2]
                for obj_data in objects_data:
                    obj = self._deserialize_object(obj_data, (h, w), image, result.categories)
                    if obj and obj.instances:
                        result.objects.append(obj)
            
            # Load global objects (new format)
            global_objects_data = data.get("objects", [])
            for obj_data in global_objects_data:
                try:
                    # Find appropriate image for mask reconstruction
                    # Use first instance's page_id to find image
                    page_id = None
                    for inst_data in obj_data.get("instances", []):
                        page_id = inst_data.get("page_id")
                        if page_id:
                            break
                    
                    image = page_images.get(page_id) if page_id else None
                    if image is None and page_images:
                        # Fallback to first available image
                        image = next(iter(page_images.values()))
                    
                    if image is not None:
                        h, w = image.shape[:2]
                        obj = self._deserialize_object(obj_data, (h, w), image, result.categories)
                        if obj and obj.instances:
                            result.objects.append(obj)
                except MemoryError as e:
                    print(f"Warning: Memory error loading object {obj_data.get('object_id', 'unknown')}: {e}")
                    print(f"  Skipping this object and continuing...")
                    continue
                except Exception as e:
                    print(f"Warning: Error loading object {obj_data.get('object_id', 'unknown')}: {e}")
                    print(f"  Skipping this object and continuing...")
                    continue
            
            # Load view state (current page, panel widths, etc.)
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
    
    def _serialize_mask_regions(self, regions: list) -> list:
        """Serialize mask regions (text/hatch) - store mask data for manual regions."""
        serialized = []
        for r in regions:
            region_data = {
                'id': r.get('id', ''),
                'mode': r.get('mode', 'auto'),
            }
            # Store bbox for auto regions
            if 'bbox' in r:
                region_data['bbox'] = list(r['bbox'])
            # Store point for manual regions
            if 'point' in r:
                region_data['point'] = list(r['point'])
            # Store text and confidence for text regions
            if 'text' in r:
                region_data['text'] = r['text']
            if 'confidence' in r:
                region_data['confidence'] = r['confidence']
            # Store area/center for hatch regions
            if 'area' in r:
                region_data['area'] = r['area']
            if 'center' in r:
                region_data['center'] = list(r['center'])
            
            # For manual regions, store mask as RLE (run-length encoding) for compactness
            if r.get('mode') != 'auto' and 'mask' in r and r['mask'] is not None:
                mask = r['mask']
                # Store bounding box of mask to reduce data
                ys, xs = np.where(mask > 0)
                if len(xs) > 0 and len(ys) > 0:
                    x1, y1 = int(xs.min()), int(ys.min())
                    x2, y2 = int(xs.max()) + 1, int(ys.max()) + 1
                    region_data['mask_bbox'] = [x1, y1, x2, y2]
                    # Extract cropped mask and encode as RLE
                    cropped = mask[y1:y2, x1:x2]
                    # Store shape explicitly for decoding
                    region_data['mask_shape'] = [int(cropped.shape[0]), int(cropped.shape[1])]
                    region_data['mask_rle'] = self._encode_rle(cropped)
            
            serialized.append(region_data)
        return serialized
    
    def _encode_rle(self, mask: np.ndarray) -> list:
        """Encode binary mask as run-length encoding."""
        flat = mask.flatten()
        # Find runs
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
    
    def _decode_rle(self, rle: list, shape: tuple) -> np.ndarray:
        """Decode run-length encoding to binary mask."""
        flat = []
        for val, count in rle:
            flat.extend([val] * count)
        return np.array(flat, dtype=np.uint8).reshape(shape)
    
    def _deserialize_mask_regions(self, data: list, image: np.ndarray, region_type: str) -> list:
        """Deserialize mask regions and recreate masks (optimized for batch processing)."""
        if image is None or not data:
            return []
        
        h, w = image.shape[:2]
        regions = []
        
        # Pre-allocate arrays for batch operations where possible
        # Process auto regions first (faster - just bbox)
        auto_regions = [r for r in data if r.get('mode') == 'auto']
        manual_regions = [r for r in data if r.get('mode') != 'auto']
        
        # Process auto regions (fast - just bbox operations)
        for r in auto_regions:
            region = dict(r)  # Copy all stored data
            mask = np.zeros((h, w), dtype=np.uint8)
            
            bbox = region.get('bbox', [0, 0, 0, 0])
            if len(bbox) == 4:
                x1, y1, x2, y2 = [int(v) for v in bbox]
                x1 = max(0, min(x1, w))
                y1 = max(0, min(y1, h))
                x2 = max(0, min(x2, w))
                y2 = max(0, min(y2, h))
                if x2 > x1 and y2 > y1:
                    mask[y1:y2, x1:x2] = 255
            
            region['mask'] = mask
            regions.append(region)
        
        # Process manual regions (slower - RLE decoding)
        for r in manual_regions:
            region = dict(r)  # Copy all stored data
            mask = np.zeros((h, w), dtype=np.uint8)
            
            # For manual regions, decode RLE mask if available
            if 'mask_rle' in region and 'mask_bbox' in region:
                bbox = region['mask_bbox']
                x1, y1, x2, y2 = [int(v) for v in bbox]
                rle = region['mask_rle']
                
                # Use stored shape if available, otherwise compute from bbox
                if 'mask_shape' in region:
                    crop_h, crop_w = region['mask_shape']
                else:
                    crop_h, crop_w = max(1, y2 - y1), max(1, x2 - x1)
                
                try:
                    cropped_mask = self._decode_rle(rle, (crop_h, crop_w))
                    
                    # Clip coordinates to image bounds
                    dest_x1 = max(0, min(x1, w))
                    dest_y1 = max(0, min(y1, h))
                    dest_x2 = max(0, min(x2, w))
                    dest_y2 = max(0, min(y2, h))
                    
                    # Calculate source region in cropped mask
                    src_x1 = dest_x1 - x1
                    src_y1 = dest_y1 - y1
                    src_x2 = src_x1 + (dest_x2 - dest_x1)
                    src_y2 = src_y1 + (dest_y2 - dest_y1)
                    
                    # Ensure we don't exceed cropped mask bounds
                    src_x2 = min(src_x2, cropped_mask.shape[1])
                    src_y2 = min(src_y2, cropped_mask.shape[0])
                    
                    # Place cropped mask into full mask
                    if dest_x2 > dest_x1 and dest_y2 > dest_y1 and src_x2 > src_x1 and src_y2 > src_y1:
                        actual_w = min(dest_x2 - dest_x1, src_x2 - src_x1)
                        actual_h = min(dest_y2 - dest_y1, src_y2 - src_y1)
                        mask[dest_y1:dest_y1+actual_h, dest_x1:dest_x1+actual_w] = \
                            cropped_mask[src_y1:src_y1+actual_h, src_x1:src_x1+actual_w]
                except Exception as e:
                    # Fallback: use point as marker
                    point = region.get('point', [0, 0])
                    if len(point) == 2:
                        px, py = int(point[0]), int(point[1])
                        r_size = 10
                        y1 = max(0, py - r_size)
                        y2 = min(h, py + r_size)
                        x1 = max(0, px - r_size)
                        x2 = min(w, px + r_size)
                        if x2 > x1 and y2 > y1:
                            mask[y1:y2, x1:x2] = 255
            else:
                # Fallback: use point as marker
                point = region.get('point', [0, 0])
                if len(point) == 2:
                    px, py = int(point[0]), int(point[1])
                    r_size = 10
                    y1 = max(0, py - r_size)
                    y2 = min(h, py + r_size)
                    x1 = max(0, px - r_size)
                    x2 = min(w, px + r_size)
                    if x2 > x1 and y2 > y1:
                        mask[y1:y2, x1:x2] = 255
            
            region['mask'] = mask
            regions.append(region)
        
        return regions
    
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
                            categories: Dict[str, DynamicCategory]) -> Optional[SegmentedObject]:
        """Deserialize a segmented object."""
        h, w = image_shape
        category = data.get("category", "")
        cat = categories.get(category)
        color = cat.color_rgb if cat else (128, 128, 128)
        
        engine = SegmentationEngine(self.tolerance, self.line_thickness)
        
        instances = []
        for inst_data in data.get("instances", []):
            elements = []
            
            inst_h, inst_w = (h, w)
            
            for elem_data in inst_data.get("elements", []):
                points = [tuple(p) for p in elem_data.get("points", [])]
                mode = elem_data.get("mode", "flood")
                
                # Reconstruct mask using instance's page image
                # Only create mask when needed - don't pre-allocate full-size array
                mask = None
                
                if mode in ["auto", "rect"] and "mask_rle" in elem_data:
                    # Decode RLE-encoded mask for 'auto' and 'rect' mode elements
                    try:
                        bbox = elem_data.get("mask_bbox", [0, 0, inst_w, inst_h])
                        shape = elem_data.get("mask_shape", [inst_h, inst_w])
                        rle = elem_data.get("mask_rle", [])
                        
                        # Decode RLE
                        flat = []
                        for val, count in rle:
                            flat.extend([val] * count)
                        cropped = np.array(flat, dtype=np.uint8).reshape(shape)
                        
                        # Place cropped mask into full-size mask
                        x1, y1, x2, y2 = bbox
                        mask = np.zeros((inst_h, inst_w), dtype=np.uint8)
                        mask[y1:y2, x1:x2] = cropped
                    except Exception as e:
                        print(f"Warning: Failed to decode mask for element {elem_data.get('element_id', 'unknown')}: {e}")
                        mask = np.zeros((inst_h, inst_w), dtype=np.uint8)
                elif mode == "flood" and points and image is not None:
                    px, py = points[0]
                    if 0 <= px < inst_w and 0 <= py < inst_h:
                        mask = engine.flood_fill(image, (px, py))
                elif mode == "polyline" and len(points) >= 3:
                    mask = engine.create_polygon_mask((inst_h, inst_w), points)
                elif mode in ["line", "freeform"] and len(points) >= 2:
                    mask = engine.create_line_mask((inst_h, inst_w), points)
                
                # If no mask was created, create empty one only if needed
                if mask is None:
                    try:
                        mask = np.zeros((inst_h, inst_w), dtype=np.uint8)
                    except MemoryError:
                        # Skip this element if we can't allocate memory
                        print(f"Warning: Skipping element {elem_data.get('element_id', 'unknown')} - memory allocation failed")
                        continue
                
                anchor_offset = elem_data.get("label_anchor_offset")
                if anchor_offset is not None:
                    anchor_offset = tuple(anchor_offset)
                
                elem = SegmentElement(
                    element_id=elem_data.get("element_id", ""),
                    category=category,
                    mode=mode,
                    points=points,
                    mask=mask,
                    color=color,
                    label_position=elem_data.get("label_position", "center"),
                    label_anchor_offset=anchor_offset,
                )
                elements.append(elem)
            
            if elements:
                # Load instance-level attributes (new format) or use default
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
        
        # Backward compatibility: migrate object-level attributes to first instance
        if "attributes" in data and instances:
            old_attrs = ObjectAttributes.from_dict(data.get("attributes", {}))
            # Only migrate if there's actual data and instance doesn't already have attrs
            if (old_attrs.material or old_attrs.obj_type) and not instances[0].attributes.material:
                instances[0].attributes = old_attrs
        
        return obj

