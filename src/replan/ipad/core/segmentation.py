"""Core segmentation operations for iPad.

Adapted from desktop version with PIL fallbacks for iOS compatibility.
Uses cv2 when available (Pyto opencv-python-headless), falls back to PIL.
"""

import numpy as np
from typing import Tuple, List, Optional
from PIL import Image, ImageDraw

# Try to import cv2 (available in Pyto)
try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False


class SegmentationEngine:
    """
    Core segmentation operations for iPad.
    
    Handles mask creation using various methods:
    - Flood fill for region selection (cv2 or PIL fallback)
    - Polygon fill for polyline/freeform shapes
    - Line drawing for structural elements
    """
    
    def __init__(self, tolerance: int = 5, line_thickness: int = 3):
        """
        Initialize the segmentation engine.
        
        Args:
            tolerance: Color tolerance for flood fill (0-255)
            line_thickness: Default line thickness for line tools
        """
        self.tolerance = tolerance
        self.line_thickness = line_thickness
    
    def flood_fill(self, image: np.ndarray, 
                   seed: Tuple[int, int]) -> np.ndarray:
        """
        Create a mask using flood fill from a seed point.
        
        Args:
            image: Source image (RGB or BGR, numpy array)
            seed: (x, y) seed point
            
        Returns:
            Binary mask (H x W) where 255 = filled region
        """
        h, w = image.shape[:2]
        x, y = seed
        
        # Validate seed point
        if not (0 <= x < w and 0 <= y < h):
            return np.zeros((h, w), dtype=np.uint8)
        
        if HAS_CV2:
            return self._flood_fill_cv2(image, seed)
        else:
            return self._flood_fill_pil(image, seed)
    
    def _flood_fill_cv2(self, image: np.ndarray, seed: Tuple[int, int]) -> np.ndarray:
        """Flood fill using OpenCV."""
        h, w = image.shape[:2]
        x, y = seed
        
        # Convert to grayscale for flood fill
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
        
        # Create mask for flood fill (needs to be 2 pixels larger)
        flood_mask = np.zeros((h + 2, w + 2), dtype=np.uint8)
        
        # Perform flood fill
        _, _, flood_mask, _ = cv2.floodFill(
            gray.copy(),
            flood_mask,
            (x, y),
            255,
            self.tolerance,
            self.tolerance,
            cv2.FLOODFILL_MASK_ONLY
        )
        
        # Extract the result (remove the 1-pixel border)
        result = (flood_mask[1:-1, 1:-1] > 0).astype(np.uint8) * 255
        
        return result
    
    def _flood_fill_pil(self, image: np.ndarray, seed: Tuple[int, int]) -> np.ndarray:
        """
        Flood fill using PIL (fallback for when cv2 is not available).
        
        This is a simple implementation - less accurate than cv2 but works.
        """
        h, w = image.shape[:2]
        x, y = seed
        
        # Convert to PIL Image
        if len(image.shape) == 3:
            pil_img = Image.fromarray(image).convert('RGB')
        else:
            pil_img = Image.fromarray(image).convert('L')
        
        # Get target color at seed point
        target_color = pil_img.getpixel((x, y))
        
        # Create mask
        mask = np.zeros((h, w), dtype=np.uint8)
        
        # Simple flood fill using BFS
        from collections import deque
        
        visited = set()
        queue = deque([(x, y)])
        
        while queue:
            cx, cy = queue.popleft()
            
            if (cx, cy) in visited:
                continue
            if not (0 <= cx < w and 0 <= cy < h):
                continue
            
            pixel = pil_img.getpixel((cx, cy))
            
            # Check color difference
            if isinstance(pixel, tuple):
                diff = sum(abs(a - b) for a, b in zip(pixel, target_color)) / len(pixel)
            else:
                diff = abs(pixel - target_color)
            
            if diff > self.tolerance:
                continue
            
            visited.add((cx, cy))
            mask[cy, cx] = 255
            
            # Add neighbors
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nx, ny = cx + dx, cy + dy
                if (nx, ny) not in visited:
                    queue.append((nx, ny))
        
        return mask
    
    def create_polygon_mask(self, shape: Tuple[int, int],
                            points: List[Tuple[int, int]],
                            closed: bool = True) -> np.ndarray:
        """
        Create a filled polygon mask.
        
        Args:
            shape: (height, width) of the output mask
            points: List of (x, y) vertices
            closed: Whether to close the polygon
            
        Returns:
            Binary mask (H x W)
        """
        h, w = shape
        mask = np.zeros((h, w), dtype=np.uint8)
        
        if len(points) < 3:
            return mask
        
        if HAS_CV2:
            pts = np.array(points, dtype=np.int32)
            if closed:
                cv2.fillPoly(mask, [pts], 255)
            else:
                cv2.polylines(mask, [pts], False, 255, self.line_thickness * 3)
        else:
            # PIL fallback
            pil_mask = Image.new('L', (w, h), 0)
            draw = ImageDraw.Draw(pil_mask)
            
            if closed:
                draw.polygon(points, fill=255)
            else:
                draw.line(points, fill=255, width=self.line_thickness * 3)
            
            mask = np.array(pil_mask)
        
        return mask
    
    def create_line_mask(self, shape: Tuple[int, int],
                         points: List[Tuple[int, int]],
                         thickness: int = None) -> np.ndarray:
        """
        Create a polyline mask.
        
        Args:
            shape: (height, width) of the output mask
            points: List of (x, y) vertices
            thickness: Line thickness (uses default if None)
            
        Returns:
            Binary mask (H x W)
        """
        h, w = shape
        mask = np.zeros((h, w), dtype=np.uint8)
        
        if len(points) < 2:
            return mask
        
        thickness = thickness or self.line_thickness
        
        if HAS_CV2:
            pts = np.array(points, dtype=np.int32)
            cv2.polylines(mask, [pts], False, 255, thickness)
        else:
            # PIL fallback
            pil_mask = Image.new('L', (w, h), 0)
            draw = ImageDraw.Draw(pil_mask)
            draw.line(points, fill=255, width=thickness)
            mask = np.array(pil_mask)
        
        return mask
    
    def create_freeform_mask(self, shape: Tuple[int, int],
                             points: List[Tuple[int, int]],
                             thickness: int = None) -> np.ndarray:
        """
        Create a freeform drawing mask.
        
        Similar to line mask but with thicker strokes for brush-like effect.
        """
        thickness = thickness or (self.line_thickness * 3)
        return self.create_line_mask(shape, points, thickness)
    
    def erode_mask(self, mask: np.ndarray, iterations: int = 1) -> np.ndarray:
        """Erode a mask to shrink the selection."""
        if HAS_CV2:
            kernel = np.ones((3, 3), np.uint8)
            return cv2.erode(mask, kernel, iterations=iterations)
        else:
            # PIL fallback using min filter
            from PIL import ImageFilter
            pil_mask = Image.fromarray(mask)
            for _ in range(iterations):
                pil_mask = pil_mask.filter(ImageFilter.MinFilter(3))
            return np.array(pil_mask)
    
    def dilate_mask(self, mask: np.ndarray, iterations: int = 1) -> np.ndarray:
        """Dilate a mask to expand the selection."""
        if HAS_CV2:
            kernel = np.ones((3, 3), np.uint8)
            return cv2.dilate(mask, kernel, iterations=iterations)
        else:
            # PIL fallback using max filter
            from PIL import ImageFilter
            pil_mask = Image.fromarray(mask)
            for _ in range(iterations):
                pil_mask = pil_mask.filter(ImageFilter.MaxFilter(3))
            return np.array(pil_mask)
    
    def smooth_mask(self, mask: np.ndarray, kernel_size: int = 5) -> np.ndarray:
        """Smooth mask edges using morphological operations."""
        if HAS_CV2:
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
            return mask
        else:
            # Simple blur fallback
            pil_mask = Image.fromarray(mask)
            from PIL import ImageFilter
            pil_mask = pil_mask.filter(ImageFilter.MedianFilter(kernel_size))
            # Re-threshold
            arr = np.array(pil_mask)
            return (arr > 127).astype(np.uint8) * 255
    
    def get_contours(self, mask: np.ndarray) -> list:
        """
        Get contours from a mask.
        
        Returns:
            List of contours (each is an array of points)
        """
        if HAS_CV2:
            contours, _ = cv2.findContours(
                mask.astype(np.uint8),
                cv2.RETR_EXTERNAL,
                cv2.CHAIN_APPROX_SIMPLE
            )
            return contours
        else:
            # Simple boundary tracing fallback
            # This is a simplified version - returns bounding box corners
            ys, xs = np.where(mask > 0)
            if len(xs) == 0:
                return []
            
            x_min, x_max = xs.min(), xs.max()
            y_min, y_max = ys.min(), ys.max()
            
            # Return as contour format
            contour = np.array([
                [[x_min, y_min]],
                [[x_max, y_min]],
                [[x_max, y_max]],
                [[x_min, y_max]]
            ], dtype=np.int32)
            
            return [contour]
    
    def masks_overlap(self, mask1: np.ndarray, mask2: np.ndarray) -> bool:
        """Check if two masks overlap."""
        if mask1.shape != mask2.shape:
            return False
        return np.any((mask1 > 0) & (mask2 > 0))
    
    def combine_masks(self, masks: List[np.ndarray], 
                      operation: str = "union") -> np.ndarray:
        """
        Combine multiple masks.
        
        Args:
            masks: List of masks
            operation: "union" (OR), "intersection" (AND), or "xor"
            
        Returns:
            Combined mask
        """
        if not masks:
            return np.zeros((1, 1), dtype=np.uint8)
        
        result = masks[0].copy()
        
        for mask in masks[1:]:
            if mask.shape != result.shape:
                continue
            
            if operation == "union":
                result = np.maximum(result, mask)
            elif operation == "intersection":
                result = np.minimum(result, mask)
            elif operation == "xor":
                result = np.bitwise_xor(result, mask)
        
        return result

