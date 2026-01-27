"""
Touch-enabled canvas view for iPad Segmenter.

Supports:
- Touch and Apple Pencil drawing
- Pinch to zoom
- Two-finger pan
- Drawing modes: flood, polyline, freeform, line
"""

import numpy as np
from PIL import Image
from typing import List, Tuple, Optional, Callable
from dataclasses import dataclass, field

# Check for UI availability
try:
    import pyto_ui as ui
    HAS_UI = True
except ImportError:
    ui = None
    HAS_UI = False


@dataclass
class TouchState:
    """Tracks current touch state for drawing."""
    is_drawing: bool = False
    points: List[Tuple[int, int]] = field(default_factory=list)
    start_point: Optional[Tuple[int, int]] = None
    current_point: Optional[Tuple[int, int]] = None
    mode: str = "flood"


class CanvasView:
    """
    Touch-enabled canvas for drawing segmentation masks.
    
    This is the core drawing surface that displays the image
    and handles all touch/pencil interactions.
    """
    
    def __init__(self, on_segment_created: Callable = None):
        """
        Initialize the canvas view.
        
        Args:
            on_segment_created: Callback when a segment is completed
                               Signature: callback(points: List, mode: str)
        """
        self.on_segment_created = on_segment_created
        
        # Image state
        self.image: Optional[np.ndarray] = None
        self.display_image: Optional[Image.Image] = None
        
        # View state
        self.zoom_level = 1.0
        self.pan_offset = (0, 0)
        self.min_zoom = 0.1
        self.max_zoom = 10.0
        
        # Touch state
        self.touch_state = TouchState()
        
        # Drawing settings
        self.current_mode = "flood"
        self.line_color = (255, 0, 0)  # Red preview
        self.line_width = 3
        
        # UI view (created when shown)
        self.view = None
        self._setup_view()
    
    def _setup_view(self):
        """Create the UI view."""
        if not HAS_UI:
            return
        
        self.view = ui.View()
        self.view.background_color = ui.Color.rgb(0.1, 0.1, 0.1)
        
        # Image view
        self.image_view = ui.ImageView()
        self.image_view.content_mode = ui.ContentMode.SCALE_ASPECT_FIT
        self.view.add_subview(self.image_view)
        
        # Set up gesture recognizers
        self._setup_gestures()
    
    def _setup_gestures(self):
        """Set up touch gesture recognizers."""
        if not HAS_UI or not self.view:
            return
        
        # Touch callbacks would be set up here
        # Pyto uses different gesture handling than Pythonista
        pass
    
    def set_image(self, image: np.ndarray):
        """Set the image to display."""
        self.image = image
        self._update_display()
    
    def _update_display(self):
        """Update the displayed image."""
        if self.image is None:
            return
        
        # Convert numpy to PIL
        if len(self.image.shape) == 3:
            if self.image.shape[2] == 4:
                pil_img = Image.fromarray(self.image, 'RGBA')
            else:
                pil_img = Image.fromarray(self.image, 'RGB')
        else:
            pil_img = Image.fromarray(self.image, 'L')
        
        self.display_image = pil_img
        
        if HAS_UI and self.image_view:
            # Convert PIL to Pyto UI image
            # This would use the appropriate Pyto method
            pass
    
    def set_mode(self, mode: str):
        """Set the current drawing mode."""
        if mode in ["select", "flood", "polyline", "freeform", "line"]:
            self.current_mode = mode
            self.touch_state.mode = mode
    
    def screen_to_image(self, point: Tuple[float, float]) -> Tuple[int, int]:
        """Convert screen coordinates to image coordinates."""
        if self.image is None:
            return (0, 0)
        
        x = (point[0] - self.pan_offset[0]) / self.zoom_level
        y = (point[1] - self.pan_offset[1]) / self.zoom_level
        
        # Clamp to image bounds
        h, w = self.image.shape[:2]
        x = max(0, min(int(x), w - 1))
        y = max(0, min(int(y), h - 1))
        
        return (x, y)
    
    def image_to_screen(self, point: Tuple[int, int]) -> Tuple[float, float]:
        """Convert image coordinates to screen coordinates."""
        x = point[0] * self.zoom_level + self.pan_offset[0]
        y = point[1] * self.zoom_level + self.pan_offset[1]
        return (x, y)
    
    def handle_touch_began(self, location: Tuple[float, float], 
                           pressure: float = 1.0, is_pencil: bool = False):
        """Handle touch down event."""
        img_point = self.screen_to_image(location)
        
        if self.current_mode == "flood":
            # Flood fill is immediate on tap
            self.touch_state.points = [img_point]
            self._complete_segment()
        elif self.current_mode in ["polyline", "freeform", "line"]:
            self.touch_state.is_drawing = True
            self.touch_state.start_point = img_point
            self.touch_state.points = [img_point]
            self.touch_state.current_point = img_point
    
    def handle_touch_moved(self, location: Tuple[float, float],
                           pressure: float = 1.0, is_pencil: bool = False):
        """Handle touch move event."""
        if not self.touch_state.is_drawing:
            return
        
        img_point = self.screen_to_image(location)
        
        if self.current_mode == "freeform":
            # Add point for freeform drawing
            self.touch_state.points.append(img_point)
        elif self.current_mode == "line":
            # Update current point for line preview
            self.touch_state.current_point = img_point
        
        self._update_preview()
    
    def handle_touch_ended(self, location: Tuple[float, float]):
        """Handle touch up event."""
        if not self.touch_state.is_drawing:
            return
        
        img_point = self.screen_to_image(location)
        
        if self.current_mode == "polyline":
            # Add point to polygon
            self.touch_state.points.append(img_point)
            # Double-tap to close - handled separately
        elif self.current_mode in ["freeform", "line"]:
            self.touch_state.points.append(img_point)
            self._complete_segment()
        
        self.touch_state.is_drawing = False
    
    def handle_double_tap(self, location: Tuple[float, float]):
        """Handle double tap to complete polygon."""
        if self.current_mode == "polyline" and len(self.touch_state.points) >= 3:
            self._complete_segment()
    
    def _complete_segment(self):
        """Complete the current segment and notify callback."""
        if self.on_segment_created and self.touch_state.points:
            self.on_segment_created(
                self.touch_state.points.copy(),
                self.touch_state.mode
            )
        
        # Reset touch state
        self.touch_state.points = []
        self.touch_state.start_point = None
        self.touch_state.current_point = None
        self._update_preview()
    
    def _update_preview(self):
        """Update the drawing preview."""
        # Would draw current points as a preview overlay
        pass
    
    def cancel_drawing(self):
        """Cancel current drawing operation."""
        self.touch_state.is_drawing = False
        self.touch_state.points = []
        self.touch_state.start_point = None
        self.touch_state.current_point = None
        self._update_preview()
    
    def zoom_to_fit(self):
        """Zoom to fit the entire image."""
        if self.image is None or self.view is None:
            return
        
        h, w = self.image.shape[:2]
        view_w = self.view.frame[2]
        view_h = self.view.frame[3]
        
        scale_x = view_w / w
        scale_y = view_h / h
        self.zoom_level = min(scale_x, scale_y) * 0.95
        
        # Center the image
        scaled_w = w * self.zoom_level
        scaled_h = h * self.zoom_level
        self.pan_offset = (
            (view_w - scaled_w) / 2,
            (view_h - scaled_h) / 2
        )
        
        self._update_display()
    
    def zoom_in(self):
        """Zoom in."""
        self.zoom_level = min(self.zoom_level * 1.25, self.max_zoom)
        self._update_display()
    
    def zoom_out(self):
        """Zoom out."""
        self.zoom_level = max(self.zoom_level / 1.25, self.min_zoom)
        self._update_display()
    
    def handle_pinch(self, scale: float, center: Tuple[float, float]):
        """Handle pinch zoom gesture."""
        new_zoom = self.zoom_level * scale
        new_zoom = max(self.min_zoom, min(new_zoom, self.max_zoom))
        
        # Adjust pan to zoom around the pinch center
        old_img_center = self.screen_to_image(center)
        self.zoom_level = new_zoom
        new_screen_center = self.image_to_screen(old_img_center)
        
        self.pan_offset = (
            self.pan_offset[0] + (center[0] - new_screen_center[0]),
            self.pan_offset[1] + (center[1] - new_screen_center[1])
        )
        
        self._update_display()
    
    def handle_pan(self, translation: Tuple[float, float]):
        """Handle pan gesture."""
        self.pan_offset = (
            self.pan_offset[0] + translation[0],
            self.pan_offset[1] + translation[1]
        )
        self._update_display()

