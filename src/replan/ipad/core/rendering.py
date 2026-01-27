"""Rendering engine for iPad segmentation visualization.

Adapted from desktop version - uses PIL with cv2 optional.
"""

import numpy as np
from typing import Dict, List, Set, Tuple, Optional
from PIL import Image, ImageDraw, ImageFont
import hashlib

from ..models import PageTab, SegmentedObject, DynamicCategory

# Try to import cv2
try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False


class RenderCache:
    """Cache for expensive rendering operations."""
    
    def __init__(self):
        self.base_image: Optional[np.ndarray] = None
        self.base_hash: str = ""
        self.page_id: str = ""
    
    def invalidate(self):
        """Clear all caches."""
        self.base_image = None
        self.base_hash = ""


class Renderer:
    """
    Renders segmentation overlays and labels.
    
    Optimized for iPad with PIL-based rendering.
    """
    
    def __init__(self):
        self.cache = RenderCache()
        self._font = None
    
    def _get_font(self, size: int = 14):
        """Get a font for text rendering."""
        if self._font is None:
            try:
                # Try to load a system font
                self._font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", size)
            except:
                # Fallback to default
                self._font = ImageFont.load_default()
        return self._font
    
    def invalidate_cache(self):
        """Call when objects change to force re-render."""
        self.cache.invalidate()
    
    def _compute_objects_hash(self, objects: list, categories: Dict[str, DynamicCategory],
                               planform_opacity: float, page_id: str = "") -> str:
        """Compute a hash representing the current state of objects."""
        parts = [page_id, str(planform_opacity)]
        for obj in objects:
            cat = categories.get(obj.category)
            visible = cat.visible if cat else True
            parts.append(f"{obj.object_id}:{len(obj.instances)}:{visible}")
            for inst in obj.instances:
                parts.append(f"{inst.instance_id}:{len(inst.elements)}")
        return hashlib.md5("|".join(parts).encode()).hexdigest()[:16]
    
    def render_page(self,
                    page: PageTab,
                    categories: Dict[str, DynamicCategory],
                    zoom: float = 1.0,
                    show_labels: bool = True,
                    selected_object_ids: Set[str] = None,
                    selected_instance_ids: Set[str] = None,
                    selected_element_ids: Set[str] = None,
                    planform_opacity: float = 0.5,
                    pending_elements: list = None,
                    objects: list = None) -> np.ndarray:
        """
        Render a page with all overlays.
        
        Returns:
            RGBA numpy array
        """
        if page.original_image is None:
            return np.zeros((100, 100, 4), dtype=np.uint8)
        
        selected_object_ids = selected_object_ids or set()
        selected_instance_ids = selected_instance_ids or set()
        selected_element_ids = selected_element_ids or set()
        pending_elements = pending_elements or []
        objects = objects if objects is not None else page.objects
        
        h, w = page.original_image.shape[:2]
        
        # Check cache
        current_hash = self._compute_objects_hash(objects, categories, planform_opacity, page.tab_id)
        need_rebuild = (
            self.cache.base_image is None or 
            self.cache.base_hash != current_hash or
            self.cache.page_id != page.tab_id
        )
        
        if need_rebuild:
            self.cache.base_image = self._render_base(page, categories, planform_opacity, objects)
            self.cache.base_hash = current_hash
            self.cache.page_id = page.tab_id
        
        # Start with cached base
        blended = self.cache.base_image.copy()
        
        # Draw highlights
        self._highlight_selected(blended, objects, selected_object_ids, 
                                 selected_instance_ids, selected_element_ids)
        
        # Draw pending elements
        if pending_elements:
            self._draw_pending_elements(blended, pending_elements)
        
        # Draw labels
        if show_labels:
            self._draw_labels(blended, objects, categories)
        
        # Apply zoom
        if zoom != 1.0:
            new_w = max(1, int(w * zoom))
            new_h = max(1, int(h * zoom))
            
            pil_img = Image.fromarray(blended)
            resample = Image.Resampling.LANCZOS if zoom < 1.0 else Image.Resampling.BILINEAR
            pil_img = pil_img.resize((new_w, new_h), resample)
            blended = np.array(pil_img)
        
        return blended
    
    def _render_base(self, page: PageTab, categories: Dict[str, DynamicCategory],
                     planform_opacity: float, objects: list = None) -> np.ndarray:
        """Render the base blended image."""
        h, w = page.original_image.shape[:2]
        objects = objects if objects is not None else page.objects
        
        # Convert base to RGBA
        if page.original_image.shape[2] == 3:
            base_rgba = np.zeros((h, w, 4), dtype=np.uint8)
            base_rgba[:, :, :3] = page.original_image
            base_rgba[:, :, 3] = 255
        else:
            base_rgba = page.original_image.copy()
        
        # Create overlay
        overlay = np.zeros((h, w, 4), dtype=np.uint8)
        
        for obj in objects:
            cat = categories.get(obj.category)
            if not cat or not cat.visible:
                continue
            
            opacity = planform_opacity if obj.category == "planform" else 0.7
            alpha_val = int(255 * opacity)
            
            # Collect masks
            obj_mask = np.zeros((h, w), dtype=np.uint8)
            for inst in obj.instances:
                for elem in inst.elements:
                    if elem.mask is not None and elem.mask.shape == (h, w):
                        obj_mask = np.maximum(obj_mask, elem.mask)
            
            # Apply color to overlay
            mask_region = obj_mask > 0
            overlay[mask_region, 0] = cat.color_rgb[0]
            overlay[mask_region, 1] = cat.color_rgb[1]
            overlay[mask_region, 2] = cat.color_rgb[2]
            overlay[mask_region, 3] = alpha_val
        
        # Blend
        alpha = overlay[:, :, 3:4] / 255.0
        blended = (base_rgba[:, :, :3] * (1 - alpha) + overlay[:, :, :3] * alpha).astype(np.uint8)
        result = np.zeros((h, w, 4), dtype=np.uint8)
        result[:, :, :3] = blended
        result[:, :, 3] = 255
        
        return result
    
    def _highlight_selected(self, image: np.ndarray, objects: List[SegmentedObject],
                            selected_object_ids: Set[str], selected_instance_ids: Set[str],
                            selected_element_ids: Set[str]):
        """Draw highlight borders around selected elements."""
        has_element_selection = bool(selected_element_ids)
        has_instance_selection = bool(selected_instance_ids)
        has_object_selection = bool(selected_object_ids)
        
        # Convert to PIL for drawing
        pil_img = Image.fromarray(image)
        draw = ImageDraw.Draw(pil_img)
        
        for obj in objects:
            for inst in obj.instances:
                for elem in inst.elements:
                    should_highlight = False
                    
                    if has_element_selection:
                        should_highlight = elem.element_id in selected_element_ids
                    elif has_instance_selection:
                        should_highlight = inst.instance_id in selected_instance_ids
                    elif has_object_selection:
                        should_highlight = obj.object_id in selected_object_ids
                    
                    if should_highlight and elem.mask is not None:
                        # Get bounding box and draw highlight
                        bounds = elem.bounds
                        if bounds:
                            x1, y1, x2, y2 = bounds
                            # Draw selection rectangle
                            draw.rectangle([x1-2, y1-2, x2+2, y2+2], outline=(0, 0, 0, 255), width=3)
                            draw.rectangle([x1-1, y1-1, x2+1, y2+1], outline=(255, 255, 0, 255), width=2)
        
        # Copy back to numpy array
        image[:] = np.array(pil_img)
    
    def _draw_pending_elements(self, image: np.ndarray, elements: list):
        """Draw elements being created."""
        pil_img = Image.fromarray(image)
        draw = ImageDraw.Draw(pil_img)
        
        for elem in elements:
            bounds = elem.bounds
            if bounds:
                x1, y1, x2, y2 = bounds
                # Cyan dashed outline
                draw.rectangle([x1, y1, x2, y2], outline=(0, 255, 255, 255), width=2)
        
        image[:] = np.array(pil_img)
    
    def _draw_labels(self, image: np.ndarray, objects: List[SegmentedObject],
                     categories: Dict[str, DynamicCategory]):
        """Draw object labels."""
        pil_img = Image.fromarray(image)
        draw = ImageDraw.Draw(pil_img)
        font = self._get_font(14)
        
        for obj in objects:
            cat = categories.get(obj.category)
            if cat and not cat.visible:
                continue
            
            for inst_idx, inst in enumerate(obj.instances):
                centroid = self._calculate_centroid(inst.elements)
                if centroid is None:
                    continue
                
                cx, cy = centroid
                label = f"{obj.name}[{inst_idx + 1}]" if len(obj.instances) > 1 else obj.name
                
                # Get text size
                bbox = draw.textbbox((0, 0), label, font=font)
                text_w = bbox[2] - bbox[0]
                text_h = bbox[3] - bbox[1]
                
                lx = int(cx - text_w // 2)
                ly = int(cy - text_h // 2)
                
                # Draw shadow
                draw.text((lx + 1, ly + 1), label, fill=(220, 220, 220, 255), font=font)
                draw.text((lx + 2, ly + 2), label, fill=(200, 200, 200, 255), font=font)
                
                # Draw main text
                draw.text((lx, ly), label, fill=(30, 30, 30, 255), font=font)
        
        image[:] = np.array(pil_img)
    
    def _calculate_centroid(self, elements: list) -> Optional[Tuple[int, int]]:
        """Calculate center of gravity for elements."""
        all_xs = []
        all_ys = []
        
        for elem in elements:
            if elem.mask is not None:
                ys, xs = np.where(elem.mask > 0)
                if len(xs) > 0:
                    all_xs.extend(xs)
                    all_ys.extend(ys)
        
        if not all_xs:
            return None
        
        return (int(np.mean(all_xs)), int(np.mean(all_ys)))
    
    def render_thumbnail(self, page: PageTab, max_size: int = 200) -> np.ndarray:
        """Render a thumbnail of a page."""
        if page.original_image is None:
            thumb = np.zeros((max_size, max_size, 3), dtype=np.uint8)
            return thumb
        
        h, w = page.original_image.shape[:2]
        scale = max_size / max(h, w)
        new_w = max(1, int(w * scale))
        new_h = max(1, int(h * scale))
        
        pil_img = Image.fromarray(page.original_image)
        pil_img = pil_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        
        return np.array(pil_img)

