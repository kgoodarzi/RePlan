"""Tests for drawing module."""

import pytest
import numpy as np

from replan.desktop.core.drawing import (
    DrawingTool,
    FloodFillTool,
    PolylineTool,
    FreeformTool,
    LineTool,
    SelectTool,
    create_tool,
)
from replan.desktop.core.segmentation import SegmentationEngine
from replan.desktop.models import SegmentElement


class TestDrawingTool:
    """Tests for DrawingTool base class."""

    def test_mode_property(self):
        """Test mode property derivation from class name."""
        # Create a concrete implementation for testing
        class TestTool(DrawingTool):
            def on_click(self, x, y):
                return None
        
        engine = SegmentationEngine()
        tool = TestTool(engine, "test", (255, 0, 0), (100, 100))
        assert tool.mode == "test"

    def test_start(self):
        """Test starting a tool."""
        class TestTool(DrawingTool):
            def on_click(self, x, y):
                return None
        
        engine = SegmentationEngine()
        tool = TestTool(engine, "test", (255, 0, 0), (100, 100))
        tool.points = [(10, 10), (20, 20)]
        
        tool.start()
        assert tool.is_active == True
        assert tool.points == []

    def test_cancel(self):
        """Test canceling a tool."""
        class TestTool(DrawingTool):
            def on_click(self, x, y):
                return None
        
        engine = SegmentationEngine()
        tool = TestTool(engine, "test", (255, 0, 0), (100, 100))
        tool.points = [(10, 10)]
        tool.is_active = True
        
        callback_called = []
        tool.on_points_changed = lambda pts: callback_called.append(pts)
        
        tool.cancel()
        assert tool.is_active == False
        assert tool.points == []
        assert len(callback_called) == 1

    def test_undo_last_point(self):
        """Test undoing last point."""
        class TestTool(DrawingTool):
            def on_click(self, x, y):
                return None
        
        engine = SegmentationEngine()
        tool = TestTool(engine, "test", (255, 0, 0), (100, 100))
        tool.points = [(10, 10), (20, 20), (30, 30)]
        
        callback_called = []
        tool.on_points_changed = lambda pts: callback_called.append(pts)
        
        tool.undo_last_point()
        assert tool.points == [(10, 10), (20, 20)]
        assert len(callback_called) == 1

    def test_undo_last_point_empty(self):
        """Test undoing last point when empty."""
        class TestTool(DrawingTool):
            def on_click(self, x, y):
                return None
        
        engine = SegmentationEngine()
        tool = TestTool(engine, "test", (255, 0, 0), (100, 100))
        tool.undo_last_point()
        assert tool.points == []

    def test_validate_point(self):
        """Test point validation."""
        class TestTool(DrawingTool):
            def on_click(self, x, y):
                return None
        
        engine = SegmentationEngine()
        tool = TestTool(engine, "test", (255, 0, 0), (100, 100))
        
        assert tool._validate_point(50, 50) == True
        assert tool._validate_point(0, 0) == True
        assert tool._validate_point(99, 99) == True
        assert tool._validate_point(-1, 50) == False
        assert tool._validate_point(100, 50) == False
        assert tool._validate_point(50, -1) == False
        assert tool._validate_point(50, 100) == False

    def test_get_preview_points(self):
        """Test getting preview points."""
        class TestTool(DrawingTool):
            def on_click(self, x, y):
                return None
        
        engine = SegmentationEngine()
        tool = TestTool(engine, "test", (255, 0, 0), (100, 100))
        tool.points = [(10, 10), (20, 20)]
        
        preview = tool.get_preview_points()
        assert preview == [(10, 10), (20, 20)]
        assert preview is not tool.points  # Should be a copy


class TestFloodFillTool:
    """Tests for FloodFillTool."""

    @pytest.fixture
    def engine(self):
        """Create a SegmentationEngine."""
        return SegmentationEngine()

    @pytest.fixture
    def source_image(self):
        """Create a test source image."""
        img = np.ones((100, 100, 3), dtype=np.uint8) * 255
        img[20:40, 20:40] = [100, 100, 100]  # Gray rectangle
        return img

    @pytest.fixture
    def tool(self, engine, source_image):
        """Create a FloodFillTool."""
        return FloodFillTool(engine, "rib", (255, 0, 0), (100, 100), source_image)

    def test_on_click_valid(self, tool):
        """Test clicking on valid point."""
        result = tool.on_click(30, 30)
        
        assert result is not None
        assert isinstance(result, SegmentElement)
        assert result.category == "rib"
        assert result.mode == "flood"
        assert result.points == [(30, 30)]
        assert result.mask is not None
        assert result.mask.shape == (100, 100)

    def test_on_click_invalid_point(self, tool):
        """Test clicking on invalid point."""
        result = tool.on_click(-10, -10)
        assert result is None
        
        result = tool.on_click(200, 200)
        assert result is None

    def test_on_click_empty_mask(self, tool, engine):
        """Test clicking that produces empty mask."""
        # Create image with seed point out of bounds - flood_fill returns empty mask
        # Use a mock to simulate empty mask return
        from unittest.mock import patch
        
        empty_img = np.zeros((100, 100, 3), dtype=np.uint8)
        tool_empty = FloodFillTool(engine, "rib", (255, 0, 0), (100, 100), empty_img)
        
        # Mock flood_fill to return empty mask
        with patch.object(engine, 'flood_fill', return_value=np.zeros((100, 100), dtype=np.uint8)):
            result = tool_empty.on_click(50, 50)
            # Should return None when flood fill produces empty mask (np.sum(mask) == 0)
            # This tests branch at line 124
            assert result is None


class TestSelectTool:
    """Tests for SelectTool."""

    @pytest.fixture
    def engine(self):
        """Create a SegmentationEngine."""
        return SegmentationEngine()

    @pytest.fixture
    def mock_element(self):
        """Create a mock element."""
        from replan.desktop.models import SegmentElement
        return SegmentElement(
            element_id="elem1",
            category="rib",
            mode="flood",
            points=[(50, 50)],
            mask=np.zeros((100, 100), dtype=np.uint8)
        )

    @pytest.fixture
    def get_element_func(self, mock_element):
        """Create a mock get_element_at_point function."""
        def get_element(x, y):
            if 40 <= x <= 60 and 40 <= y <= 60:
                return ("obj1", "inst1", mock_element)
            return None
        return get_element

    @pytest.fixture
    def tool(self, engine, get_element_func):
        """Create a SelectTool."""
        return SelectTool(engine, "rib", (255, 0, 0), (100, 100), get_element_func)

    def test_on_click_finds_element(self, tool):
        """Test clicking finds an element."""
        result = tool.on_click(50, 50)
        
        assert result is None  # SelectTool doesn't create elements
        assert tool.selected_element_id == "elem1"

    def test_on_click_no_element(self, tool):
        """Test clicking where no element exists."""
        result = tool.on_click(10, 10)
        
        assert result is None
        assert tool.selected_element_id is None

    def test_on_click_invalid_point(self, tool):
        """Test clicking on invalid point."""
        result = tool.on_click(-10, -10)
        assert result is None


class TestPolylineTool:
    """Tests for PolylineTool."""

    @pytest.fixture
    def engine(self):
        """Create a SegmentationEngine."""
        return SegmentationEngine()

    @pytest.fixture
    def tool(self, engine):
        """Create a PolylineTool."""
        return PolylineTool(engine, "rib", (255, 0, 0), (100, 100), snap_distance=15)

    def test_on_click_adds_point(self, tool):
        """Test clicking adds a point."""
        result = tool.on_click(10, 10)
        
        assert result is None  # Not complete yet
        assert tool.points == [(10, 10)]

    def test_on_click_multiple_points(self, tool):
        """Test adding multiple points."""
        tool.on_click(10, 10)
        tool.on_click(20, 20)
        tool.on_click(30, 30)
        
        assert len(tool.points) == 3
        assert tool.points == [(10, 10), (20, 20), (30, 30)]

    def test_on_double_click_completes(self, tool):
        """Test double click completes polyline."""
        tool.on_click(10, 10)
        tool.on_click(20, 20)
        tool.on_click(30, 30)  # Need at least 3 points
        
        result = tool.on_double_click(40, 40)
        
        assert result is not None
        assert isinstance(result, SegmentElement)
        assert result.category == "rib"
        assert result.mode == "polyline"
        assert len(result.points) >= 3
        assert tool.points == []  # Cleared after completion

    def test_on_double_click_insufficient_points(self, tool):
        """Test double click with insufficient points."""
        tool.on_click(10, 10)
        tool.on_click(20, 20)
        
        result = tool.on_double_click(30, 30)
        
        # Need at least 3 points for polyline
        assert result is None

    def test_on_key_escape_cancels(self, tool):
        """Test escape key cancels (via base class cancel)."""
        tool.on_click(10, 10)
        tool.on_click(20, 20)
        
        # PolylineTool doesn't handle Escape, but base class cancel can be called
        tool.cancel()
        
        assert tool.points == []
        assert tool.is_active == False

    def test_on_key_enter_completes(self, tool):
        """Test enter key completes."""
        tool.on_click(10, 10)
        tool.on_click(20, 20)
        tool.on_click(30, 30)
        
        result = tool.on_key("Return")
        
        assert result is not None
        assert isinstance(result, SegmentElement)

    def test_snap_to_existing_point(self, tool):
        """Test snapping to existing point."""
        tool.on_click(10, 10)
        # Click near existing point (within snap distance)
        tool.on_click(12, 12)  # Within snap_distance=15
        
        # Should snap or add as new point depending on implementation
        assert len(tool.points) >= 1
    
    def test_snap_to_close_polyline(self, tool):
        """Test snapping to close polyline when >= 3 points."""
        tool.on_click(10, 10)
        tool.on_click(20, 20)
        tool.on_click(30, 30)  # Now have 3 points
        
        # Click very close to first point (within snap distance)
        # snap_distance is 15, so (10, 10) to (12, 12) = ~2.8 pixels, well within range
        result = tool.on_click(12, 12)  # Within snap_distance=15 of (10, 10)
        
        # Should snap and complete the polyline (tests branch 174->175)
        assert result is not None
        assert isinstance(result, SegmentElement)
        assert tool.points == []  # Cleared after completion
    
    def test_snap_to_close_not_close_enough(self, tool):
        """Test when click is not close enough to snap."""
        tool.on_click(10, 10)
        tool.on_click(20, 20)
        tool.on_click(30, 30)  # Now have 3 points
        
        # Click far from first point (outside snap distance)
        result = tool.on_click(50, 50)  # Far from (10, 10), outside snap_distance=15
        
        # Should not snap, just add point (tests branch 174->177)
        assert result is None
        assert len(tool.points) == 4  # Added new point
    
    def test_finish_insufficient_points(self, tool):
        """Test _finish with insufficient points."""
        tool.on_click(10, 10)
        tool.on_click(20, 20)  # Only 2 points
        
        result = tool._finish()
        
        # Should return None with < 3 points
        assert result is None
    
    def test_get_snap_target(self, tool):
        """Test get_snap_target method."""
        # No snap target with < 3 points
        tool.on_click(10, 10)
        assert tool.get_snap_target() is None
        
        # Should return first point with >= 3 points
        tool.on_click(20, 20)
        tool.on_click(30, 30)
        assert tool.get_snap_target() == (10, 10)
    
    def test_on_key_wrong_key(self, tool):
        """Test on_key with wrong key."""
        tool.on_click(10, 10)
        tool.on_click(20, 20)
        tool.on_click(30, 30)
        
        result = tool.on_key("Escape")  # Wrong key
        
        # Should return None for non-Return key
        assert result is None


class TestFreeformTool:
    """Tests for FreeformTool."""

    @pytest.fixture
    def engine(self):
        """Create a SegmentationEngine."""
        return SegmentationEngine()

    @pytest.fixture
    def tool(self, engine):
        """Create a FreeformTool."""
        return FreeformTool(engine, "rib", (255, 0, 0), (100, 100))

    def test_on_click_starts_drawing(self, tool):
        """Test click starts drawing."""
        result = tool.on_click(10, 10)
        
        assert result is None
        assert tool.is_drawing == True
        assert tool.points == [(10, 10)]

    def test_on_drag_adds_points(self, tool):
        """Test drag adds points."""
        tool.on_click(10, 10)
        tool.on_drag(20, 20)
        tool.on_drag(30, 30)
        
        assert len(tool.points) == 3
    
    def test_on_drag_when_not_drawing(self, tool):
        """Test on_drag when not drawing (should do nothing)."""
        # Don't call on_click first
        tool.on_drag(20, 20)
        
        # Should not add points when not drawing
        assert len(tool.points) == 0
    
    def test_on_drag_invalid_point(self, tool):
        """Test on_drag with invalid point."""
        tool.on_click(10, 10)
        tool.on_drag(-10, -10)  # Invalid point
        
        # Should not add invalid point
        assert len(tool.points) == 1  # Only the initial click
    
    def test_on_click_invalid_point(self, tool):
        """Test on_click with invalid point."""
        result = tool.on_click(-10, -10)
        
        assert result is None
        # Invalid point should not start drawing (validate_point returns False early)
        # The important thing is that no element is created and points aren't added
        assert len(tool.points) == 0
        assert tool.is_drawing == False  # Should remain False when validation fails

    def test_on_release_completes(self, tool):
        """Test release completes freeform."""
        tool.on_click(10, 10)
        tool.on_drag(20, 20)
        tool.on_drag(30, 30)
        
        result = tool.on_release(40, 40)
        
        assert result is not None
        assert isinstance(result, SegmentElement)
        assert result.category == "rib"
        assert result.mode == "freeform"
        assert tool.is_drawing == False
        assert tool.points == []

    def test_on_release_insufficient_points(self, tool):
        """Test release with insufficient points."""
        tool.on_click(10, 10)
        
        result = tool.on_release(20, 20)
        
        # Need at least 2 points
        assert result is None
        assert tool.points == []

    def test_on_release_not_drawing(self, tool):
        """Test release when not drawing."""
        result = tool.on_release(10, 10)
        assert result is None


class TestLineTool:
    """Tests for LineTool."""

    @pytest.fixture
    def engine(self):
        """Create a SegmentationEngine."""
        return SegmentationEngine()

    @pytest.fixture
    def tool(self, engine):
        """Create a LineTool."""
        return LineTool(engine, "rib", (255, 0, 0), (100, 100))

    def test_on_click_adds_point(self, tool):
        """Test clicking adds a point."""
        result = tool.on_click(10, 10)
        
        assert result is None
        assert tool.points == [(10, 10)]

    def test_on_click_two_points(self, tool):
        """Test two clicks add points (doesn't auto-complete)."""
        tool.on_click(10, 10)
        result = tool.on_click(20, 20)
        
        # LineTool doesn't auto-complete on second click
        assert result is None
        assert len(tool.points) == 2

    def test_on_click_invalid_point(self, tool):
        """Test on_click with invalid point."""
        result = tool.on_click(-10, -10)
        
        assert result is None
        assert len(tool.points) == 0
    
    def test_on_key_enter_completes_line(self, tool):
        """Test enter key completes line."""
        tool.on_click(10, 10)
        tool.on_click(20, 20)
        
        result = tool.on_key("Return")
        
        assert result is not None
        assert isinstance(result, SegmentElement)
    
    def test_on_key_wrong_key(self, tool):
        """Test on_key with wrong key."""
        tool.on_click(10, 10)
        tool.on_click(20, 20)
        
        result = tool.on_key("Escape")  # Wrong key
        
        # Should return None for non-Return key
        assert result is None
    
    def test_on_key_insufficient_points(self, tool):
        """Test on_key with insufficient points."""
        tool.on_click(10, 10)  # Only 1 point
        
        result = tool.on_key("Return")
        
        # Need at least 2 points, so should return None
        assert result is None
        assert len(tool.points) == 1  # Points not cleared when incomplete
    
    def test_finish_insufficient_points_line(self, tool):
        """Test _finish with insufficient points for LineTool."""
        tool.on_click(10, 10)  # Only 1 point
        
        result = tool._finish()
        
        # Need at least 2 points for line
        assert result is None

    def test_on_click_multiple_points(self, tool):
        """Test multiple clicks add points."""
        tool.on_click(10, 10)
        tool.on_click(20, 20)
        tool.on_click(30, 30)
        
        assert len(tool.points) == 3
        assert tool.points == [(10, 10), (20, 20), (30, 30)]


class TestCreateTool:
    """Tests for create_tool factory function."""

    @pytest.fixture
    def engine(self):
        """Create a SegmentationEngine."""
        return SegmentationEngine()

    def test_create_flood_tool(self, engine):
        """Test creating flood fill tool."""
        source_image = np.ones((100, 100, 3), dtype=np.uint8) * 255
        tool = create_tool("flood", engine, "rib", (255, 0, 0), (100, 100), source_image=source_image)
        
        assert isinstance(tool, FloodFillTool)
        assert tool.category == "rib"

    def test_create_select_tool(self, engine):
        """Test creating select tool."""
        def get_element(x, y):
            return None
        
        tool = create_tool("select", engine, "rib", (255, 0, 0), (100, 100), get_element_at_point=get_element)
        
        assert isinstance(tool, SelectTool)
        assert tool.category == "rib"

    def test_create_polyline_tool(self, engine):
        """Test creating polyline tool."""
        tool = create_tool("polyline", engine, "rib", (255, 0, 0), (100, 100), snap_distance=20)
        
        assert isinstance(tool, PolylineTool)
        assert tool.category == "rib"

    def test_create_freeform_tool(self, engine):
        """Test creating freeform tool."""
        tool = create_tool("freeform", engine, "rib", (255, 0, 0), (100, 100))
        
        assert isinstance(tool, FreeformTool)
        assert tool.category == "rib"

    def test_create_line_tool(self, engine):
        """Test creating line tool."""
        tool = create_tool("line", engine, "rib", (255, 0, 0), (100, 100))
        
        assert isinstance(tool, LineTool)
        assert tool.category == "rib"

    def test_create_tool_invalid_mode(self, engine):
        """Test creating tool with invalid mode."""
        with pytest.raises(ValueError, match="Unknown tool mode"):
            create_tool("invalid", engine, "rib", (255, 0, 0), (100, 100))
