"""Drawing tools for segmentation."""

from abc import ABC, abstractmethod
from typing import List, Tuple, Optional, Callable
import numpy as np

from replan.desktop.models import SegmentElement
from replan.desktop.core.segmentation import SegmentationEngine
from replan.desktop.utils.geometry import distance, snap_to_point


class DrawingTool(ABC):
    """
    Abstract base class for drawing tools.
    
    Drawing tools handle mouse interactions and create SegmentElements
    when the user completes a selection.
    """
    
    def __init__(self, 
                 engine: SegmentationEngine,
                 category: str,
                 color: Tuple[int, int, int],
                 image_shape: Tuple[int, int]):
        """
        Initialize a drawing tool.
        
        Args:
            engine: Segmentation engine for mask creation
            category: Category for created elements
            color: RGB color for visualization
            image_shape: (height, width) of the target image
        """
        self.engine = engine
        self.category = category
        self.color = color
        self.image_shape = image_shape
        
        self.points: List[Tuple[int, int]] = []
        self.is_active = False
        
        # Callback for when points change (for preview)
        self.on_points_changed: Optional[Callable] = None
    
    @property
    def mode(self) -> str:
        """Get the tool mode name."""
        return self.__class__.__name__.replace("Tool", "").lower()
    
    def start(self):
        """Start using this tool."""
        self.is_active = True
        self.points.clear()
    
    def cancel(self):
        """Cancel the current operation."""
        self.points.clear()
        self.is_active = False
        self._notify_points_changed()
    
    def undo_last_point(self):
        """Remove the last point added."""
        if self.points:
            self.points.pop()
            self._notify_points_changed()
    
    def _notify_points_changed(self):
        """Notify callback that points have changed."""
        if self.on_points_changed:
            self.on_points_changed(self.points.copy())
    
    def _validate_point(self, x: int, y: int) -> bool:
        """Check if a point is within image bounds."""
        h, w = self.image_shape
        return 0 <= x < w and 0 <= y < h
    
    @abstractmethod
    def on_click(self, x: int, y: int) -> Optional[SegmentElement]:
        """
        Handle mouse click.
        
        Returns:
            Completed element if operation is done, None otherwise
        """
        pass
    
    def on_double_click(self, x: int, y: int) -> Optional[SegmentElement]:
        """Handle double click. Default does nothing."""
        return None
    
    def on_drag(self, x: int, y: int):
        """Handle mouse drag. Default does nothing."""
        pass
    
    def on_release(self, x: int, y: int) -> Optional[SegmentElement]:
        """Handle mouse release. Default does nothing."""
        return None
    
    def on_key(self, key: str) -> Optional[SegmentElement]:
        """Handle key press. Default does nothing."""
        return None
    
    def get_preview_points(self) -> List[Tuple[int, int]]:
        """Get points for preview rendering."""
        return self.points.copy()


class FloodFillTool(DrawingTool):
    """Flood fill tool for selecting contiguous regions."""
    
    def __init__(self, engine: SegmentationEngine, category: str,
                 color: Tuple[int, int, int], image_shape: Tuple[int, int],
                 source_image: np.ndarray):
        super().__init__(engine, category, color, image_shape)
        self.source_image = source_image
    
    def on_click(self, x: int, y: int) -> Optional[SegmentElement]:
        if not self._validate_point(x, y):
            return None
        
        mask = self.engine.flood_fill(self.source_image, (x, y))
        
        if np.sum(mask) == 0:
            return None
        
        return SegmentElement(
            category=self.category,
            mode="flood",
            points=[(x, y)],
            mask=mask,
            color=self.color,
        )


class SelectTool(DrawingTool):
    """Selection tool for clicking on existing elements."""
    
    def __init__(self, engine: SegmentationEngine, category: str,
                 color: Tuple[int, int, int], image_shape: Tuple[int, int],
                 get_element_at_point: Callable):
        super().__init__(engine, category, color, image_shape)
        self.get_element_at_point = get_element_at_point
        self.selected_element_id: Optional[str] = None
    
    def on_click(self, x: int, y: int) -> Optional[SegmentElement]:
        if not self._validate_point(x, y):
            return None
        
        # This tool doesn't create elements, it selects them
        result = self.get_element_at_point(x, y)
        if result:
            self.selected_element_id = result[2].element_id  # (obj, inst, elem)
        else:
            self.selected_element_id = None
        
        return None  # Selection is handled externally


class PolylineTool(DrawingTool):
    """Polyline tool for creating polygon selections."""
    
    def __init__(self, engine: SegmentationEngine, category: str,
                 color: Tuple[int, int, int], image_shape: Tuple[int, int],
                 snap_distance: int = 15):
        super().__init__(engine, category, color, image_shape)
        self.snap_distance = snap_distance
    
    def on_click(self, x: int, y: int) -> Optional[SegmentElement]:
        if not self._validate_point(x, y):
            return None
        
        # Check for snap to close
        if len(self.points) >= 3:
            if snap_to_point((x, y), self.points[0], self.snap_distance):
                return self._finish()
        
        self.points.append((x, y))
        self._notify_points_changed()
        return None
    
    def on_double_click(self, x: int, y: int) -> Optional[SegmentElement]:
        if len(self.points) >= 3:
            return self._finish()
        return None
    
    def on_key(self, key: str) -> Optional[SegmentElement]:
        if key == "Return" and len(self.points) >= 3:
            return self._finish()
        return None
    
    def _finish(self) -> Optional[SegmentElement]:
        if len(self.points) < 3:
            return None
        
        mask = self.engine.create_polygon_mask(self.image_shape, self.points)
        points = self.points.copy()
        self.points.clear()
        self._notify_points_changed()
        
        return SegmentElement(
            category=self.category,
            mode="polyline",
            points=points,
            mask=mask,
            color=self.color,
        )
    
    def get_snap_target(self) -> Optional[Tuple[int, int]]:
        """Get the snap target point if snapping is possible."""
        if len(self.points) >= 3:
            return self.points[0]
        return None


class FreeformTool(DrawingTool):
    """Freeform drawing tool for brush-like selections."""
    
    def __init__(self, engine: SegmentationEngine, category: str,
                 color: Tuple[int, int, int], image_shape: Tuple[int, int]):
        super().__init__(engine, category, color, image_shape)
        self.is_drawing = False
    
    def on_click(self, x: int, y: int) -> Optional[SegmentElement]:
        if not self._validate_point(x, y):
            return None
        
        self.is_drawing = True
        self.points = [(x, y)]
        self._notify_points_changed()
        return None
    
    def on_drag(self, x: int, y: int):
        if self.is_drawing and self._validate_point(x, y):
            self.points.append((x, y))
            self._notify_points_changed()
    
    def on_release(self, x: int, y: int) -> Optional[SegmentElement]:
        if not self.is_drawing:
            return None
        
        self.is_drawing = False
        
        if len(self.points) < 2:
            self.points.clear()
            return None
        
        mask = self.engine.create_freeform_mask(self.image_shape, self.points)
        points = self.points.copy()
        self.points.clear()
        self._notify_points_changed()
        
        return SegmentElement(
            category=self.category,
            mode="freeform",
            points=points,
            mask=mask,
            color=self.color,
        )


class LineTool(DrawingTool):
    """Line tool for structural elements like longerons and spars."""
    
    def on_click(self, x: int, y: int) -> Optional[SegmentElement]:
        if not self._validate_point(x, y):
            return None
        
        self.points.append((x, y))
        self._notify_points_changed()
        return None
    
    def on_key(self, key: str) -> Optional[SegmentElement]:
        if key == "Return" and len(self.points) >= 2:
            return self._finish()
        return None
    
    def _finish(self) -> Optional[SegmentElement]:
        if len(self.points) < 2:
            return None
        
        mask = self.engine.create_line_mask(self.image_shape, self.points)
        points = self.points.copy()
        self.points.clear()
        self._notify_points_changed()
        
        return SegmentElement(
            category=self.category,
            mode="line",
            points=points,
            mask=mask,
            color=self.color,
        )


def create_tool(mode: str,
                engine: SegmentationEngine,
                category: str,
                color: Tuple[int, int, int],
                image_shape: Tuple[int, int],
                source_image: np.ndarray = None,
                snap_distance: int = 15,
                get_element_at_point: Callable = None) -> DrawingTool:
    """
    Factory function to create the appropriate tool.
    
    Args:
        mode: Tool mode name
        engine: Segmentation engine
        category: Category for created elements
        color: RGB color
        image_shape: (height, width) of target image
        source_image: Source image for flood fill
        snap_distance: Snap distance for polyline
        get_element_at_point: Function for select tool
        
    Returns:
        Appropriate DrawingTool instance
    """
    if mode == "flood":
        return FloodFillTool(engine, category, color, image_shape, source_image)
    elif mode == "select":
        return SelectTool(engine, category, color, image_shape, get_element_at_point)
    elif mode == "polyline":
        return PolylineTool(engine, category, color, image_shape, snap_distance)
    elif mode == "freeform":
        return FreeformTool(engine, category, color, image_shape)
    elif mode == "line":
        return LineTool(engine, category, color, image_shape)
    else:
        raise ValueError(f"Unknown tool mode: {mode}")


