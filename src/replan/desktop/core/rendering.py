"""Rendering engine for segmentation visualization with caching."""

import cv2
import numpy as np
from typing import Dict, List, Set, Tuple, Optional
import hashlib

from replan.desktop.models import PageTab, SegmentedObject, DynamicCategory
from replan.desktop.utils.profiling import timed


class RenderCache:
    """Cache for expensive rendering operations."""
    
    def __init__(self):
        self.base_image: Optional[np.ndarray] = None  # Original + overlay blended
        self.base_hash: str = ""  # Hash of objects state
        self.zoomed_cache: Dict[float, np.ndarray] = {}  # Zoom level -> zoomed base
        self.page_id: str = ""
    
    def invalidate(self):
        """Clear all caches."""
        self.base_image = None
        self.base_hash = ""
        self.zoomed_cache.clear()
    
    def invalidate_zoom(self):
        """Clear only zoom cache (when base changes)."""
        self.zoomed_cache.clear()


class Renderer:
    """
    Renders segmentation overlays and labels with caching.
    
    Performance optimizations:
    - Caches base blended image (original + segmentation)
    - Only redraws highlights/labels on selection change
    - Caches zoomed versions
    """
    
    def __init__(self):
        self.label_font = cv2.FONT_HERSHEY_SIMPLEX
        self.label_scale = 0.5
        self.label_thickness = 1
        self.cache = RenderCache()
    
    def invalidate_cache(self):
        """Call when objects change to force re-render."""
        self.cache.invalidate()
    
    def _compute_objects_hash(self, page: PageTab, categories: Dict[str, DynamicCategory], 
                               planform_opacity: float) -> str:
        """Compute a hash representing the current state of objects."""
        return self._compute_objects_hash_from_list(page.objects, categories, planform_opacity, page.tab_id)
    
    def _compute_objects_hash_from_list(self, objects: list, categories: Dict[str, DynamicCategory], 
                                        planform_opacity: float, page_id: str = "") -> str:
        """Compute a hash representing the current state of objects list."""
        # Simple hash based on object count and element count
        parts = [page_id, str(planform_opacity)]
        for obj in objects:
            cat = categories.get(obj.category)
            visible = cat.visible if cat else True
            parts.append(f"{obj.object_id}:{len(obj.instances)}:{visible}")
            for inst in obj.instances:
                parts.append(f"{inst.instance_id}:{len(inst.elements)}")
        return hashlib.md5("|".join(parts).encode()).hexdigest()[:16]
    
    @timed("canvas_render")
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
                    hide_background: bool = False,
                    objects: list = None,
                    text_mask: np.ndarray = None,
                    hatching_mask: np.ndarray = None,
                    line_mask: np.ndarray = None,
                    pixel_selection_mask: np.ndarray = None,
                    pixel_move_offset: Tuple[int, int] = None,
                    object_move_offset: Tuple[int, int] = None) -> np.ndarray:
        """
        Render a page with all overlays (with caching).
        
        Args:
            objects: List of objects to render (filtered to this page). If None, uses page.objects.
            hide_background: If True, show only object masks on white background
            text_mask: Optional mask of text regions to hide (255 = text area)
            hatching_mask: Optional mask of hatching regions to hide (255 = hatching area)
        """
        if page.original_image is None:
            return np.zeros((100, 100, 4), dtype=np.uint8)
        
        selected_object_ids = selected_object_ids or set()
        selected_instance_ids = selected_instance_ids or set()
        selected_element_ids = selected_element_ids or set()
        pending_elements = pending_elements or []
        objects = objects if objects is not None else page.objects
        
        h, w = page.original_image.shape[:2]
        
        # Compute mask hashes to detect when mask content changes
        text_mask_hash = ""
        hatching_mask_hash = ""
        line_mask_hash = ""
        if text_mask is not None and text_mask.shape == (h, w):
            text_mask_hash = str(np.sum(text_mask))  # Simple checksum
        if hatching_mask is not None and hatching_mask.shape == (h, w):
            hatching_mask_hash = str(np.sum(hatching_mask))
        if line_mask is not None and line_mask.shape == (h, w):
            line_mask_hash = str(np.sum(line_mask))
        
        # Check if we need to rebuild base image (include mask content in hash)
        current_hash = (self._compute_objects_hash_from_list(objects, categories, planform_opacity) + 
                       str(hide_background) + text_mask_hash + hatching_mask_hash + line_mask_hash)
        need_base_rebuild = (
            self.cache.base_image is None or 
            self.cache.base_hash != current_hash or
            self.cache.page_id != page.tab_id
        )
        
        if need_base_rebuild:
            # Rebuild base image (expensive)
            print(f"RENDER: Rebuilding base image for page {page.tab_id}")
            print(f"  text_mask: {text_mask is not None}, hash={text_mask_hash}")
            print(f"  hatching_mask: {hatching_mask is not None}, hash={hatching_mask_hash}")
            print(f"  line_mask: {line_mask is not None}, hash={line_mask_hash}")
            self.cache.base_image = self._render_base(page, categories, planform_opacity, hide_background, objects, text_mask, hatching_mask, line_mask)
            self.cache.base_hash = current_hash
            self.cache.page_id = page.tab_id
            self.cache.invalidate_zoom()
        
        # Start with a copy of the cached base
        blended = self.cache.base_image.copy()
        
        # Draw highlights (lightweight - only contours)
        self._highlight_selected(
            blended, objects,
            selected_object_ids, selected_instance_ids, selected_element_ids,
            move_offset=object_move_offset
        )
        
        # Draw pending group elements
        if pending_elements:
            self._draw_pending_elements(blended, pending_elements)
        
        # Draw labels (lightweight)
        if show_labels:
            self._draw_labels_fast(blended, objects, categories)
        
        # Apply zoom (use cache if available and no dynamic elements)
        if zoom != 1.0:
            new_w = max(1, int(w * zoom))
            new_h = max(1, int(h * zoom))
            interp = cv2.INTER_AREA if zoom < 1.0 else cv2.INTER_LINEAR
            blended = cv2.resize(blended, (new_w, new_h), interpolation=interp)
        
        return blended
    
    def _render_base(self, page: PageTab, categories: Dict[str, DynamicCategory],
                     planform_opacity: float, hide_background: bool = False,
                     objects: list = None, text_mask: np.ndarray = None,
                     hatching_mask: np.ndarray = None, line_mask: np.ndarray = None) -> np.ndarray:
        """Render the base blended image (original + segmentation overlay)."""
        h, w = page.original_image.shape[:2]
        objects = objects if objects is not None else page.objects
        
        # Start with original image and ALWAYS hide text/hatching first
        # This ensures text/hatch is invisible in ALL areas
        base_image = page.original_image.copy()
        
        # Create combined hide mask (text + hatch)
        hide_mask = np.zeros((h, w), dtype=np.uint8)
        
        if text_mask is not None and text_mask.shape == (h, w):
            base_image[text_mask > 0] = [255, 255, 255]  # White in BGR
            hide_mask = np.maximum(hide_mask, text_mask)
            
        if hatching_mask is not None and hatching_mask.shape == (h, w):
            base_image[hatching_mask > 0] = [255, 255, 255]  # White in BGR
            hide_mask = np.maximum(hide_mask, hatching_mask)
        
        if line_mask is not None and line_mask.shape == (h, w):
            base_image[line_mask > 0] = [255, 255, 255]  # White in BGR
            hide_mask = np.maximum(hide_mask, line_mask)
        
        # Create segmentation overlay
        overlay = np.zeros((h, w, 4), dtype=np.uint8)
        
        # Check if we have text to fill through (text ghosting fix)
        # Note: We only fix text ghosting, not hatch ghosting
        has_text_mask = text_mask is not None and text_mask.shape == (h, w) and np.any(text_mask > 0)
        
        for obj in objects:
            cat = categories.get(obj.category)
            if not cat or not cat.visible:
                continue
            
            # Skip rendering fill for mark_* objects (they're only for hiding/erasing)
            # They will still be highlighted if selected via _highlight_selected
            if obj.category in ["mark_text", "mark_hatch", "mark_line"]:
                continue
            
            opacity = planform_opacity if obj.category == "planform" else 0.7
            alpha_val = int(255 * opacity)
            
            # Separate line/perimeter elements from filled elements
            filled_mask = np.zeros((h, w), dtype=np.uint8)
            line_elements = []  # Store line/perimeter elements for special rendering
            
            for inst in obj.instances:
                # Only process instances for the current page
                if inst.page_id != page.tab_id:
                    continue
                    
                for elem in inst.elements:
                    if elem.mask is not None and elem.mask.shape == (h, w):
                        # Line and perimeter elements should be drawn as solid lines
                        if elem.mode in ["line", "perimeter", "polyline"]:
                            line_elements.append(elem)
                        else:
                            # Regular filled elements
                            filled_mask = np.maximum(filled_mask, elem.mask)
            
            # Text ghosting fix: grow mask into text areas only
            # This fills gaps caused by text that was present during flood fill
            if has_text_mask and np.any(filled_mask > 0):
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
                # Use in-place operations where possible to reduce memory
                grown_mask = filled_mask.copy()
                
                # Limit iterations to prevent excessive memory usage on large images
                max_iterations = min(100, int(np.sqrt(h * w) / 10))  # Adaptive limit
                for _ in range(max_iterations):
                    dilated = cv2.dilate(grown_mask, kernel, iterations=1)
                    # Only grow into TEXT mask pixels (not hatch)
                    new_pixels = (dilated > 0) & (grown_mask == 0) & (text_mask > 0)
                    if not np.any(new_pixels):
                        break
                    grown_mask[new_pixels] = 255
                
                filled_mask = grown_mask
            
            # Apply filled regions to overlay
            if np.any(filled_mask > 0):
                mask_region = filled_mask > 0
                overlay[mask_region, 0] = cat.color_bgr[0]
                overlay[mask_region, 1] = cat.color_bgr[1]
                overlay[mask_region, 2] = cat.color_bgr[2]
                overlay[mask_region, 3] = alpha_val
            
            # Draw line/perimeter elements as solid lines on top
            # Use category color at full opacity for visibility
            # IMPORTANT: Draw lines AFTER filled regions so they appear on top
            for elem in line_elements:
                if elem.mask is not None and elem.mask.shape == (h, w):
                    line_region = elem.mask > 0
                    pixel_count = np.sum(line_region)
                    print(f"DEBUG RENDER LINE: {elem.mode} element for {obj.name}, {pixel_count} pixels, cat={obj.category}, color_bgr={cat.color_bgr}")
                    if pixel_count > 0:
                        # Get line color - use category color but ensure it's dark enough to be visible
                        line_bgr = list(cat.color_bgr)
                        
                        # If color is too light (close to white), darken it for visibility
                        brightness = (line_bgr[0] + line_bgr[1] + line_bgr[2]) / 3
                        if brightness > 200:
                            # Darken the color significantly
                            line_bgr = [max(0, c - 150) for c in line_bgr]
                        
                        print(f"DEBUG RENDER LINE: Final color after brightness check: {line_bgr}")
                        
                        # Force line color and full opacity - this should overwrite filled regions
                        overlay[line_region, 0] = line_bgr[0]
                        overlay[line_region, 1] = line_bgr[1]
                        overlay[line_region, 2] = line_bgr[2]
                        overlay[line_region, 3] = 255  # Full opacity for lines
        
        if hide_background:
            # Show only objects on white background
            # Use uint8 operations to avoid float32 memory overhead
            blended = np.zeros((h, w, 4), dtype=np.uint8)
            blended[:, :, :3] = 255  # White background
            alpha_channel = overlay[:, :, 3]  # Extract alpha as 2D array
            # Blend: result = background * (1 - alpha/255) + overlay * (alpha/255)
            # For white background: result = 255 * (1 - alpha/255) + overlay * (alpha/255)
            # = 255 - alpha + overlay * alpha / 255
            # Optimized: use uint16 for intermediate calculations
            alpha_u16 = alpha_channel.astype(np.uint16)
            for c in range(3):
                overlay_c = overlay[:, :, c].astype(np.uint16)
                # result = 255 - alpha + overlay * alpha / 255
                result = 255 - alpha_u16 + (overlay_c * alpha_u16 // 255)
                blended[:, :, c] = result.clip(0, 255).astype(np.uint8)
            blended[:, :, 3] = 255  # Full opacity
        else:
            # Blend overlay onto base image (which already has text/hatch hidden)
            base_rgba = cv2.cvtColor(base_image, cv2.COLOR_BGR2BGRA)
            alpha_channel = overlay[:, :, 3]  # Extract alpha as 2D array
            # Blending formula: result = base * (1 - alpha/255) + overlay * (alpha/255)
            # Use signed integers for the difference to handle dark-on-light correctly
            alpha_i32 = alpha_channel.astype(np.int32)
            blended = base_rgba.copy()
            for c in range(3):
                base_c = base_rgba[:, :, c].astype(np.int32)
                overlay_c = overlay[:, :, c].astype(np.int32)
                # result = base + (overlay - base) * alpha / 255
                diff = overlay_c - base_c  # Can be negative (e.g., dark line on white)
                result = base_c + (diff * alpha_i32 // 255)
                blended[:, :, c] = result.clip(0, 255).astype(np.uint8)
            blended[:, :, 3] = 255  # Full opacity
        
        return blended
    
    def _draw_labels_fast(self, image: np.ndarray, objects: List[SegmentedObject],
                          categories: Dict[str, DynamicCategory]):
        """Draw labels directly on BGRA image with dark text and light shadow."""
        for obj in objects:
            cat = categories.get(obj.category)
            if cat and not cat.visible:
                continue
            
            for inst_idx, inst in enumerate(obj.instances):
                label = f"{obj.name}[{inst_idx + 1}]" if len(obj.instances) > 1 else obj.name
                
                # Use FONT_HERSHEY_SIMPLEX for clean text
                font = cv2.FONT_HERSHEY_SIMPLEX
                scale = 0.5
                thickness = 1
                
                (text_w, text_h), baseline = cv2.getTextSize(label, font, scale, thickness)
                
                # Determine label position: use first element's label position/offset if available
                label_pos = None
                if inst.elements:
                    first_elem = inst.elements[0]
                    label_pos = first_elem.get_label_position()
                
                # Fallback to centroid if no label position available
                if label_pos is None:
                    centroid = self._calculate_group_centroid(inst.elements)
                    if centroid is None:
                        continue
                    cx, cy = centroid
                    label_pos = (cx, cy)
                
                # Calculate label text position (anchor point is center of text)
                lx = int(label_pos[0] - text_w // 2)
                ly = int(label_pos[1] + text_h // 2)
                
                # Draw light shadow (white/light gray for contrast on white paper)
                shadow_color = (220, 220, 220, 255)  # Light gray shadow
                for dx, dy in [(1, 1), (2, 2), (1, 2), (2, 1)]:
                    cv2.putText(image, label, (lx + dx, ly + dy), font, scale, shadow_color, thickness, cv2.LINE_AA)
                
                # Draw main text in dark color
                cv2.putText(image, label, (lx, ly), font, scale, (30, 30, 30, 255), thickness, cv2.LINE_AA)
    
    def _highlight_selected(self,
                            image: np.ndarray,
                            objects: List[SegmentedObject],
                            selected_object_ids: Set[str],
                            selected_instance_ids: Set[str],
                            selected_element_ids: Set[str],
                            move_offset: Tuple[int, int] = None):
        """
        Draw highlight borders around selected elements.
        
        Selection priority (most specific wins):
        - If elements are selected, only highlight those specific elements
        - If instances are selected (no elements), highlight all elements in those instances
        - If objects are selected (no instances/elements), highlight all elements in those objects
        
        If move_offset is provided, shows preview of moved location.
        """
        # Determine what level of selection we have
        has_element_selection = bool(selected_element_ids)
        has_instance_selection = bool(selected_instance_ids)
        has_object_selection = bool(selected_object_ids)
        
        for obj in objects:
            for inst in obj.instances:
                for elem in inst.elements:
                    should_highlight = False
                    
                    # Most specific: element is directly selected
                    if has_element_selection:
                        should_highlight = elem.element_id in selected_element_ids
                    # Next: instance is selected (and no specific elements selected)
                    elif has_instance_selection:
                        should_highlight = inst.instance_id in selected_instance_ids
                    # Least specific: object is selected (and nothing more specific)
                    elif has_object_selection:
                        should_highlight = obj.object_id in selected_object_ids
                    
                    if should_highlight and elem.mask is not None:
                        # Check if mask has any content
                        if np.any(elem.mask > 0):
                            contours, _ = cv2.findContours(
                                elem.mask.astype(np.uint8),
                                cv2.RETR_EXTERNAL,
                                cv2.CHAIN_APPROX_SIMPLE
                            )
                            if contours:  # Only draw if contours found
                                # Draw black outline first (for contrast)
                                cv2.drawContours(image, contours, -1, (0, 0, 0, 255), 4)
                                # Yellow highlight contour on top
                                cv2.drawContours(image, contours, -1, (0, 255, 255, 255), 2)
                                
                                # If moving, draw preview at new location
                                if move_offset is not None:
                                    offset_x, offset_y = move_offset
                                    # Translate contours
                                    M = np.float32([[1, 0, offset_x], [0, 1, offset_y]])
                                    shifted_contours = []
                                    for contour in contours:
                                        shifted = contour.astype(np.float32)
                                        shifted = cv2.transform(shifted.reshape(-1, 1, 2), M).reshape(-1, 2)
                                        shifted_contours.append(shifted.astype(np.int32))
                                    # Draw cyan dashed outline at new location
                                    for contour in shifted_contours:
                                        pts = contour.reshape(-1, 2)
                                        for i in range(0, len(pts) - 1, 2):
                                            pt1 = tuple(pts[i])
                                            pt2 = tuple(pts[min(i + 1, len(pts) - 1)])
                                            cv2.line(image, pt1, pt2, (255, 255, 0, 255), 2)  # Cyan
                        else:
                            print(f"DEBUG: Element {elem.element_id} has empty mask, skipping highlight")
    
    def _draw_pending_elements(self, image: np.ndarray, elements: list):
        """Draw elements being created in group mode."""
        for elem in elements:
            if elem.mask is not None:
                contours, _ = cv2.findContours(
                    elem.mask.astype(np.uint8),
                    cv2.RETR_EXTERNAL,
                    cv2.CHAIN_APPROX_SIMPLE
                )
                # Cyan dashed outline
                for contour in contours:
                    # Draw dashed by skipping points
                    pts = contour.reshape(-1, 2)
                    for i in range(0, len(pts) - 1, 2):
                        pt1 = tuple(pts[i])
                        pt2 = tuple(pts[min(i + 1, len(pts) - 1)])
                        cv2.line(image, pt1, pt2, (255, 255, 0, 255), 2)
    
    def _draw_pixel_selection(self, image: np.ndarray, mask: np.ndarray, 
                             move_offset: Tuple[int, int] = None) -> np.ndarray:
        """Draw pixel selection with optional move preview."""
        h, w = image.shape[:2]
        if mask.shape != (h, w):
            return image
        
        # Ensure image is BGRA
        if len(image.shape) == 3 and image.shape[2] == 3:
            image = cv2.cvtColor(image, cv2.COLOR_BGR2BGRA)
        elif len(image.shape) == 2:
            image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGRA)
        
        # Draw selection outline
        contours, _ = cv2.findContours(
            mask.astype(np.uint8),
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )
        
        # Draw selection with semi-transparent yellow fill
        overlay = image.copy()
        for contour in contours:
            # Fill with yellow (semi-transparent)
            cv2.fillPoly(overlay, [contour], (0, 255, 255, 128))
            # Outline in yellow
            cv2.drawContours(overlay, [contour], -1, (0, 255, 255, 255), 2)
        
        # If moving, draw preview at new location
        if move_offset is not None:
            offset_x, offset_y = move_offset
            # Create shifted mask
            M = np.float32([[1, 0, offset_x], [0, 1, offset_y]])
            h_mask, w_mask = mask.shape
            shifted_mask = cv2.warpAffine(mask.astype(np.uint8), M, (w_mask, h_mask))
            
            # Draw preview at new location (cyan dashed outline)
            shifted_contours, _ = cv2.findContours(
                shifted_mask,
                cv2.RETR_EXTERNAL,
                cv2.CHAIN_APPROX_SIMPLE
            )
            for contour in shifted_contours:
                pts = contour.reshape(-1, 2).astype(int)
                # Draw dashed line
                for i in range(0, len(pts) - 1, 2):
                    pt1 = tuple(pts[i])
                    pt2 = tuple(pts[min(i + 1, len(pts) - 1)])
                    cv2.line(overlay, pt1, pt2, (255, 255, 0, 255), 2)  # Cyan
        
        # Blend overlay with alpha
        mask_alpha = (overlay[:, :, 3] > 0).astype(np.float32)
        for c in range(3):
            image[:, :, c] = (image[:, :, c] * (1 - mask_alpha * 0.3) + 
                             overlay[:, :, c] * mask_alpha * 0.3).astype(np.uint8)
        
        return image
    
    def _draw_labels(self,
                     image: np.ndarray,
                     objects: List[SegmentedObject],
                     categories: Dict[str, DynamicCategory]):
        """
        Draw object labels on the image with filled text and contrasting shadow.
        
        Only ONE label is drawn per object (or per instance if multiple instances),
        centered at the center of gravity of all elements in that group.
        """
        # Use simple font with anti-aliasing for clean filled text
        font = cv2.FONT_HERSHEY_SIMPLEX
        scale = 0.5
        thickness = 1  # Thin for filled appearance
        
        for obj in objects:
            cat = categories.get(obj.category)
            if cat and not cat.visible:
                continue
            
            # Get category color for label
            label_color = (255, 255, 255)  # Default white
            if cat:
                # Use category color
                r, g, b = int(cat.color[1:3], 16), int(cat.color[3:5], 16), int(cat.color[5:7], 16)
                # Make sure it's bright enough to read
                brightness = (r + g + b) / 3
                if brightness > 128:
                    label_color = (b, g, r)  # BGR
                else:
                    # Brighten dark colors for visibility
                    label_color = (min(255, b + 100), min(255, g + 100), min(255, r + 100))
            
            for inst_idx, inst in enumerate(obj.instances):
                # Format label - one per instance
                if len(obj.instances) > 1:
                    label = f"{obj.name}[{inst_idx + 1}]"
                else:
                    label = obj.name
                
                # Get text size for positioning
                (text_w, text_h), baseline = cv2.getTextSize(label, font, scale, thickness)
                
                # Determine label position: use first element's label position/offset if available
                label_pos = None
                if inst.elements:
                    first_elem = inst.elements[0]
                    label_pos = first_elem.get_label_position()
                
                # Fallback to centroid if no label position available
                if label_pos is None:
                    centroid = self._calculate_group_centroid(inst.elements)
                    if centroid is None:
                        continue
                    cx, cy = centroid
                    label_pos = (cx, cy)
                
                # Calculate label text position (anchor point is center of text)
                lx = int(label_pos[0] - text_w // 2)
                ly = int(label_pos[1] + text_h // 2)
                
                # Draw soft drop shadow (multiple offsets)
                shadow_color = (40, 40, 40)
                for dx, dy in [(1, 1), (2, 2), (1, 2), (2, 1)]:
                    cv2.putText(image, label, (lx + dx, ly + dy), font, scale,
                               shadow_color, thickness, cv2.LINE_AA)
                
                # Draw main text with category color (anti-aliased)
                cv2.putText(image, label, (lx, ly), font, scale,
                           label_color, thickness, cv2.LINE_AA)
    
    def _calculate_group_centroid(self, elements: list) -> Optional[Tuple[int, int]]:
        """
        Calculate the center of gravity for a group of elements.
        
        The centroid is the weighted average of all mask pixels across all elements.
        
        Args:
            elements: List of SegmentElement objects
            
        Returns:
            (cx, cy) centroid coordinates, or None if no valid masks
        """
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
        
        # Calculate center of gravity
        cx = int(np.mean(all_xs))
        cy = int(np.mean(all_ys))
        
        return (cx, cy)
    
    def render_thumbnail(self, 
                         page: PageTab,
                         max_size: int = 200) -> np.ndarray:
        """
        Render a thumbnail of a page.
        
        Args:
            page: Page to render
            max_size: Maximum dimension
            
        Returns:
            Thumbnail image (BGR)
        """
        if page.original_image is None:
            thumb = np.zeros((max_size, max_size, 3), dtype=np.uint8)
            cv2.putText(thumb, "No Image", (10, max_size // 2),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (128, 128, 128), 1)
            return thumb
        
        h, w = page.original_image.shape[:2]
        scale = max_size / max(h, w)
        new_w = max(1, int(w * scale))
        new_h = max(1, int(h * scale))
        
        return cv2.resize(page.original_image, (new_w, new_h), 
                         interpolation=cv2.INTER_AREA)

