"""Image processing utility functions for iPad.

Adapted from desktop version - uses PIL instead of cv2 where possible.
cv2 functions kept for compatibility but with PIL fallbacks.
"""

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from typing import Tuple, Optional

# Try to import cv2 (available in Pyto as opencv-python-headless)
try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False


def resize_image(image: np.ndarray, 
                 max_width: int = None,
                 max_height: int = None,
                 scale: float = None) -> np.ndarray:
    """
    Resize an image maintaining aspect ratio.
    Uses PIL for iOS compatibility.
    """
    h, w = image.shape[:2]
    
    if scale is not None:
        new_w = int(w * scale)
        new_h = int(h * scale)
    else:
        scale_x = max_width / w if max_width else 1.0
        scale_y = max_height / h if max_height else 1.0
        scale = min(scale_x, scale_y)
        new_w = int(w * scale)
        new_h = int(h * scale)
    
    if new_w <= 0 or new_h <= 0:
        return image
    
    # Use PIL for resizing (more compatible)
    if len(image.shape) == 3:
        mode = 'RGB' if image.shape[2] == 3 else 'RGBA'
        pil_img = Image.fromarray(image if mode == 'RGB' else image)
    else:
        mode = 'L'
        pil_img = Image.fromarray(image)
    
    resample = Image.Resampling.LANCZOS if scale < 1.0 else Image.Resampling.BILINEAR
    pil_img = pil_img.resize((new_w, new_h), resample)
    
    return np.array(pil_img)


def create_color_image(color: Tuple[int, int, int], 
                       size: int = 12,
                       border: bool = True) -> Image.Image:
    """
    Create a small colored square image for use in UI.
    Returns PIL Image (iOS compatible).
    """
    img = Image.new('RGB', (size, size), color)
    
    if border:
        draw = ImageDraw.Draw(img)
        # Draw border
        draw.rectangle([0, 0, size-1, size-1], outline=(0, 0, 0))
        # Draw inner highlight for dark colors
        if sum(color) < 380:
            draw.rectangle([1, 1, size-2, size-2], outline=(80, 80, 80))
    
    return img


def blend_images(base: np.ndarray, 
                 overlay: np.ndarray,
                 alpha: float = 0.5) -> np.ndarray:
    """
    Blend two images with alpha compositing.
    Uses PIL for iOS compatibility.
    """
    # Convert to PIL
    if base.shape[2] == 3:
        base_pil = Image.fromarray(base).convert('RGBA')
    else:
        base_pil = Image.fromarray(base)
    
    if overlay.shape[2] == 3:
        overlay_pil = Image.fromarray(overlay).convert('RGBA')
    else:
        overlay_pil = Image.fromarray(overlay)
    
    # Adjust overlay alpha
    if alpha < 1.0:
        overlay_data = np.array(overlay_pil)
        overlay_data[:, :, 3] = (overlay_data[:, :, 3] * alpha).astype(np.uint8)
        overlay_pil = Image.fromarray(overlay_data)
    
    # Composite
    result = Image.alpha_composite(base_pil, overlay_pil)
    return np.array(result)


def create_checkerboard(width: int, height: int, 
                        cell_size: int = 10,
                        color1: Tuple[int, int, int] = (200, 200, 200),
                        color2: Tuple[int, int, int] = (150, 150, 150)) -> np.ndarray:
    """
    Create a checkerboard pattern (useful for showing transparency).
    """
    img = np.zeros((height, width, 3), dtype=np.uint8)
    
    for y in range(0, height, cell_size):
        for x in range(0, width, cell_size):
            cell_y = y // cell_size
            cell_x = x // cell_size
            color = color1 if (cell_x + cell_y) % 2 == 0 else color2
            
            y_end = min(y + cell_size, height)
            x_end = min(x + cell_size, width)
            img[y:y_end, x:x_end] = color
    
    return img


def enhance_contrast(image: np.ndarray, 
                     factor: float = 1.5) -> np.ndarray:
    """
    Enhance image contrast using PIL (iOS compatible).
    Simplified from cv2 CLAHE - uses PIL ImageEnhance instead.
    """
    from PIL import ImageEnhance
    
    if len(image.shape) == 3:
        pil_img = Image.fromarray(image)
    else:
        pil_img = Image.fromarray(image).convert('RGB')
    
    enhancer = ImageEnhance.Contrast(pil_img)
    enhanced = enhancer.enhance(factor)
    
    return np.array(enhanced)


def draw_dashed_line_pil(draw: ImageDraw.Draw,
                         pt1: Tuple[int, int],
                         pt2: Tuple[int, int],
                         color: Tuple[int, int, int],
                         width: int = 1,
                         dash_length: int = 10,
                         gap_length: int = 5):
    """
    Draw a dashed line using PIL ImageDraw.
    """
    import math
    
    dx = pt2[0] - pt1[0]
    dy = pt2[1] - pt1[1]
    length = math.sqrt(dx*dx + dy*dy)
    
    if length == 0:
        return
    
    dx /= length
    dy /= length
    
    current = 0
    while current < length:
        # Draw dash
        start = (int(pt1[0] + dx * current), int(pt1[1] + dy * current))
        end_dist = min(current + dash_length, length)
        end = (int(pt1[0] + dx * end_dist), int(pt1[1] + dy * end_dist))
        draw.line([start, end], fill=color, width=width)
        
        current += dash_length + gap_length


def draw_dashed_polygon_pil(draw: ImageDraw.Draw,
                            points: list,
                            color: Tuple[int, int, int],
                            width: int = 1,
                            dash_length: int = 10,
                            gap_length: int = 5,
                            closed: bool = True):
    """
    Draw a dashed polygon outline using PIL.
    """
    if len(points) < 2:
        return
    
    for i in range(len(points) - 1):
        draw_dashed_line_pil(draw, points[i], points[i+1], color, 
                             width, dash_length, gap_length)
    
    if closed and len(points) > 2:
        draw_dashed_line_pil(draw, points[-1], points[0], color,
                             width, dash_length, gap_length)


# OpenCV-based functions (if available)
if HAS_CV2:
    def draw_dashed_line(image: np.ndarray,
                         pt1: Tuple[int, int],
                         pt2: Tuple[int, int],
                         color: Tuple[int, int, int],
                         thickness: int = 1,
                         dash_length: int = 10,
                         gap_length: int = 5):
        """Draw a dashed line on a numpy array using cv2."""
        import math
        
        dx = pt2[0] - pt1[0]
        dy = pt2[1] - pt1[1]
        length = math.sqrt(dx*dx + dy*dy)
        
        if length == 0:
            return
        
        dx /= length
        dy /= length
        
        current = 0
        while current < length:
            start = (int(pt1[0] + dx * current), int(pt1[1] + dy * current))
            end_dist = min(current + dash_length, length)
            end = (int(pt1[0] + dx * end_dist), int(pt1[1] + dy * end_dist))
            cv2.line(image, start, end, color, thickness)
            
            current += dash_length + gap_length

