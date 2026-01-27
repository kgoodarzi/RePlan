"""Export functionality for iPad.

Adapted from desktop - uses PIL instead of cv2.
"""

import json
from pathlib import Path
from typing import Dict, List
import numpy as np
from PIL import Image

from ..models import PageTab, DynamicCategory, SegmentedObject
from ..core.rendering import Renderer


class ImageExporter:
    """Exports segmented images."""
    
    def __init__(self, renderer: Renderer = None):
        self.renderer = renderer or Renderer()
    
    def export_page(self,
                    path: str,
                    page: PageTab,
                    categories: Dict[str, DynamicCategory],
                    include_labels: bool = True) -> bool:
        """
        Export a segmented page as an image.
        
        Returns:
            True if successful
        """
        try:
            # Render at full resolution
            rendered = self.renderer.render_page(
                page, categories,
                zoom=1.0,
                show_labels=include_labels,
            )
            
            # Convert to PIL and save
            pil_img = Image.fromarray(rendered)
            
            # Convert RGBA to RGB if saving as JPEG
            if path.lower().endswith(('.jpg', '.jpeg')):
                pil_img = pil_img.convert('RGB')
            
            pil_img.save(path)
            return True
            
        except Exception as e:
            print(f"Error exporting image: {e}")
            return False
    
    def export_masks(self,
                     output_dir: str,
                     page: PageTab,
                     separate_objects: bool = True) -> List[str]:
        """
        Export segmentation masks.
        
        Returns:
            List of created file paths
        """
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        created = []
        
        if page.original_image is None:
            return created
        
        h, w = page.original_image.shape[:2]
        
        if separate_objects:
            for obj in page.objects:
                mask = np.zeros((h, w), dtype=np.uint8)
                for inst in obj.instances:
                    for elem in inst.elements:
                        if elem.mask is not None:
                            mask = np.maximum(mask, elem.mask)
                
                if np.any(mask):
                    filename = f"{page.model_name}_{page.page_name}_{obj.name}_mask.png"
                    filepath = out_path / filename
                    pil_mask = Image.fromarray(mask)
                    pil_mask.save(str(filepath))
                    created.append(str(filepath))
        else:
            mask = np.zeros((h, w), dtype=np.uint8)
            for obj in page.objects:
                for inst in obj.instances:
                    for elem in inst.elements:
                        if elem.mask is not None:
                            mask = np.maximum(mask, elem.mask)
            
            filename = f"{page.model_name}_{page.page_name}_mask.png"
            filepath = out_path / filename
            pil_mask = Image.fromarray(mask)
            pil_mask.save(str(filepath))
            created.append(str(filepath))
        
        return created


class DataExporter:
    """Exports segmentation data as JSON."""
    
    def export_page(self, path: str, page: PageTab) -> bool:
        """Export page data as JSON."""
        try:
            data = {
                "model": page.model_name,
                "page": page.page_name,
                "image_size": list(page.image_size) if page.image_size else None,
                "objects": [],
            }
            
            for obj in page.objects:
                # Get attributes from first instance
                attrs = obj.instances[0].attributes if obj.instances else None
                
                obj_data = {
                    "id": obj.object_id,
                    "name": obj.name,
                    "category": obj.category,
                    "attributes": {
                        "material": attrs.material if attrs else "",
                        "type": attrs.obj_type if attrs else "",
                        "view": attrs.view if attrs else "",
                        "size": {
                            "width": attrs.width if attrs else 0,
                            "height": attrs.height if attrs else 0,
                            "depth": attrs.depth if attrs else 0,
                        },
                        "description": attrs.description if attrs else "",
                        "quantity": attrs.quantity if attrs else 1,
                    },
                    "instances": [],
                }
                
                for inst in obj.instances:
                    inst_data = {
                        "instance_num": inst.instance_num,
                        "view_type": inst.view_type,
                        "elements": [],
                    }
                    
                    for elem in inst.elements:
                        elem_data = {
                            "mode": elem.mode,
                            "points": elem.points,
                            "bounds": elem.bounds,
                            "centroid": elem.centroid,
                            "area": elem.area,
                        }
                        inst_data["elements"].append(elem_data)
                    
                    obj_data["instances"].append(inst_data)
                
                data["objects"].append(obj_data)
            
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            
            return True
            
        except Exception as e:
            print(f"Error exporting data: {e}")
            return False
    
    def export_bom(self, path: str, objects: List[SegmentedObject]) -> bool:
        """
        Export a Bill of Materials.
        
        Args:
            path: Output path
            objects: List of objects
            
        Returns:
            True if successful
        """
        try:
            bom = {
                "title": "Bill of Materials",
                "items": [],
            }
            
            seen = set()
            
            for obj in objects:
                if obj.name in seen:
                    continue
                seen.add(obj.name)
                
                attrs = obj.instances[0].attributes if obj.instances else None
                
                item = {
                    "name": obj.name,
                    "category": obj.category,
                    "material": attrs.material if attrs else "",
                    "type": attrs.obj_type if attrs else "",
                    "quantity": attrs.quantity if attrs else 1,
                    "size": attrs.size_string if attrs else "",
                    "description": attrs.description if attrs else "",
                }
                bom["items"].append(item)
            
            bom["items"].sort(key=lambda x: (x["category"], x["name"]))
            
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(bom, f, indent=2)
            
            return True
            
        except Exception as e:
            print(f"Error exporting BOM: {e}")
            return False

