"""Core segmentation operations."""

import cv2
import numpy as np
from typing import Tuple, List, Optional

from replan.desktop.utils.profiling import timed


class SegmentationEngine:
    """
    Core segmentation operations.
    
    Handles mask creation using various methods:
    - Flood fill for region selection
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
    
    @timed("flood_fill")
    def flood_fill(self, image: np.ndarray, 
                   seed: Tuple[int, int]) -> np.ndarray:
        """
        Create a mask using flood fill from a seed point.
        
        Optimized for performance:
        - Avoids unnecessary image copy when possible
        - Optimizes grayscale conversion
        - Uses efficient mask extraction
        
        Args:
            image: Source image (BGR or grayscale)
            seed: (x, y) seed point
            
        Returns:
            Binary mask (H x W) where 255 = filled region
        """
        h, w = image.shape[:2]
        x, y = seed
        
        # Validate seed point
        if not (0 <= x < w and 0 <= y < h):
            return np.zeros((h, w), dtype=np.uint8)
        
        # Optimize grayscale conversion - check if already grayscale
        if len(image.shape) == 2:
            gray = image.copy()  # Already grayscale, but need copy for cv2.floodFill
        elif len(image.shape) == 3 and image.shape[2] == 1:
            gray = image[:, :, 0].copy()  # Single channel, extract and copy
        else:
            # Convert BGR to grayscale (most common case)
            # Use cv2.cvtColor which is optimized, then copy for floodFill
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            # Note: cv2.floodFill modifies the input, so we need a copy
            # But if image is already a working copy, we can optimize by checking
        
        # Create mask for flood fill (needs to be 2 pixels larger)
        flood_mask = np.zeros((h + 2, w + 2), dtype=np.uint8)
        
        # Perform flood fill - cv2.floodFill modifies both image and mask
        # Use FLOODFILL_MASK_ONLY flag so it only modifies the mask
        _, _, flood_mask, _ = cv2.floodFill(
            gray,  # Will be modified, but we have a copy
            flood_mask,
            (x, y),
            255,
            self.tolerance,
            self.tolerance,
            cv2.FLOODFILL_MASK_ONLY
        )
        
        # Optimize mask extraction - extract center region and convert to binary
        # Use direct indexing and multiplication (faster than np.where for binary conversion)
        result = flood_mask[1:-1, 1:-1]
        result = (result > 0).astype(np.uint8) * 255
        
        return result
    
    @timed("polygon_mask")
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
        
        pts = np.array(points, dtype=np.int32)
        
        if closed:
            cv2.fillPoly(mask, [pts], 255)
        else:
            # For open polygons, just draw the outline with thickness
            cv2.polylines(mask, [pts], False, 255, self.line_thickness * 3)
        
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
        pts = np.array(points, dtype=np.int32)
        cv2.polylines(mask, [pts], False, 255, thickness)
        
        return mask
    
    def create_freeform_mask(self, shape: Tuple[int, int],
                             points: List[Tuple[int, int]],
                             thickness: int = None) -> np.ndarray:
        """
        Create a freeform drawing mask.
        
        Similar to line mask but with thicker strokes for brush-like effect.
        
        Args:
            shape: (height, width) of the output mask
            points: List of (x, y) points from mouse drag
            thickness: Brush thickness
            
        Returns:
            Binary mask (H x W)
        """
        thickness = thickness or (self.line_thickness * 3)
        return self.create_line_mask(shape, points, thickness)
    
    def erode_mask(self, mask: np.ndarray, iterations: int = 1) -> np.ndarray:
        """Erode a mask to shrink the selection."""
        kernel = np.ones((3, 3), np.uint8)
        return cv2.erode(mask, kernel, iterations=iterations)
    
    def dilate_mask(self, mask: np.ndarray, iterations: int = 1) -> np.ndarray:
        """Dilate a mask to expand the selection."""
        kernel = np.ones((3, 3), np.uint8)
        return cv2.dilate(mask, kernel, iterations=iterations)
    
    def smooth_mask(self, mask: np.ndarray, kernel_size: int = 5) -> np.ndarray:
        """Smooth mask edges using morphological operations."""
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        return mask
    
    def get_contours(self, mask: np.ndarray) -> list:
        """
        Get contours from a mask.
        
        Returns:
            List of contours (each is an array of points)
        """
        contours, _ = cv2.findContours(
            mask.astype(np.uint8),
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )
        return contours
    
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


