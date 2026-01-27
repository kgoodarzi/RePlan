"""Image processing utility functions."""

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageTk
from typing import Tuple, Optional


def resize_image(image: np.ndarray, 
                 max_width: int = None,
                 max_height: int = None,
                 scale: float = None) -> np.ndarray:
    """
    Resize an image maintaining aspect ratio.
    
    Args:
        image: Input image (BGR or RGB)
        max_width: Maximum width constraint
        max_height: Maximum height constraint
        scale: Scale factor (overrides max_width/max_height)
        
    Returns:
        Resized image
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
    
    interpolation = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR
    return cv2.resize(image, (new_w, new_h), interpolation=interpolation)


def create_color_icon(color: Tuple[int, int, int], 
                      size: int = 12,
                      border: bool = True) -> ImageTk.PhotoImage:
    """
    Create a small colored square icon for use in UI.
    
    Args:
        color: RGB color tuple
        size: Icon size in pixels
        border: Whether to draw a border
        
    Returns:
        Tkinter-compatible PhotoImage
    """
    img = Image.new('RGB', (size, size), color)
    
    if border:
        draw = ImageDraw.Draw(img)
        # Draw border
        draw.rectangle([0, 0, size-1, size-1], outline=(0, 0, 0))
        # Draw inner highlight
        if sum(color) < 380:  # Dark color
            draw.rectangle([1, 1, size-2, size-2], outline=(80, 80, 80))
    
    return ImageTk.PhotoImage(img)


def blend_images(base: np.ndarray, 
                 overlay: np.ndarray,
                 alpha: float = 0.5) -> np.ndarray:
    """
    Blend two images with alpha compositing.
    
    Args:
        base: Base image (BGR or BGRA)
        overlay: Overlay image (BGRA with alpha channel)
        alpha: Global opacity for overlay
        
    Returns:
        Blended image (BGRA)
    """
    # Ensure base is BGRA
    if base.shape[2] == 3:
        base = cv2.cvtColor(base, cv2.COLOR_BGR2BGRA)
    
    # Ensure overlay is BGRA
    if overlay.shape[2] == 3:
        overlay = cv2.cvtColor(overlay, cv2.COLOR_BGR2BGRA)
    
    # Get overlay alpha channel
    overlay_alpha = overlay[:, :, 3:4] / 255.0 * alpha
    
    # Blend
    result = base.copy().astype(float)
    result[:, :, :3] = (base[:, :, :3] * (1 - overlay_alpha) + 
                        overlay[:, :, :3] * overlay_alpha)
    
    return result.astype(np.uint8)


def create_checkerboard(width: int, height: int, 
                        cell_size: int = 10,
                        color1: Tuple[int, int, int] = (200, 200, 200),
                        color2: Tuple[int, int, int] = (150, 150, 150)) -> np.ndarray:
    """
    Create a checkerboard pattern (useful for showing transparency).
    
    Args:
        width: Image width
        height: Image height
        cell_size: Size of each checker cell
        color1: First color
        color2: Second color
        
    Returns:
        BGR image with checkerboard pattern
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
                     clip_limit: float = 2.0,
                     tile_size: int = 8) -> np.ndarray:
    """
    Enhance image contrast using CLAHE.
    
    Args:
        image: Input image (BGR)
        clip_limit: Contrast limit
        tile_size: Size of grid for histogram equalization
        
    Returns:
        Contrast-enhanced image
    """
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    
    clahe = cv2.createCLAHE(clipLimit=clip_limit, 
                            tileGridSize=(tile_size, tile_size))
    l = clahe.apply(l)
    
    lab = cv2.merge([l, a, b])
    return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)


def draw_dashed_line(image: np.ndarray,
                     pt1: Tuple[int, int],
                     pt2: Tuple[int, int],
                     color: Tuple[int, int, int],
                     thickness: int = 1,
                     dash_length: int = 10,
                     gap_length: int = 5):
    """
    Draw a dashed line on an image.
    
    Args:
        image: Image to draw on (modified in place)
        pt1: Start point
        pt2: End point
        color: Line color (BGR)
        thickness: Line thickness
        dash_length: Length of each dash
        gap_length: Length of gap between dashes
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
        cv2.line(image, start, end, color, thickness)
        
        current += dash_length + gap_length


def draw_dashed_polygon(image: np.ndarray,
                        points: list,
                        color: Tuple[int, int, int],
                        thickness: int = 1,
                        dash_length: int = 10,
                        gap_length: int = 5,
                        closed: bool = True):
    """
    Draw a dashed polygon outline.
    
    Args:
        image: Image to draw on
        points: List of (x, y) vertices
        color: Line color
        thickness: Line thickness
        dash_length: Length of dashes
        gap_length: Length of gaps
        closed: Whether to close the polygon
    """
    if len(points) < 2:
        return
    
    for i in range(len(points) - 1):
        draw_dashed_line(image, points[i], points[i+1], color, 
                        thickness, dash_length, gap_length)
    
    if closed and len(points) > 2:
        draw_dashed_line(image, points[-1], points[0], color,
                        thickness, dash_length, gap_length)


