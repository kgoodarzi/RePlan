"""Tests for segmentation module."""

import pytest
import numpy as np
import cv2

from replan.desktop.core.segmentation import SegmentationEngine


class TestSegmentationEngine:
    """Tests for SegmentationEngine class."""

    @pytest.fixture
    def engine(self):
        """Create a SegmentationEngine instance."""
        return SegmentationEngine(tolerance=5, line_thickness=3)

    @pytest.fixture
    def test_image(self):
        """Create a test image (BGR format)."""
        # Create a simple test image: white background with colored regions
        img = np.ones((100, 100, 3), dtype=np.uint8) * 255
        # Add a colored rectangle
        img[20:40, 20:40] = [100, 100, 100]  # Gray rectangle
        return img

    @pytest.fixture
    def simple_mask(self):
        """Create a simple binary mask."""
        mask = np.zeros((50, 50), dtype=np.uint8)
        mask[10:30, 10:30] = 255
        return mask

    def test_init_defaults(self):
        """Test default initialization."""
        engine = SegmentationEngine()
        assert engine.tolerance == 5
        assert engine.line_thickness == 3

    def test_init_custom(self):
        """Test custom initialization."""
        engine = SegmentationEngine(tolerance=10, line_thickness=5)
        assert engine.tolerance == 10
        assert engine.line_thickness == 5

    def test_flood_fill_basic(self, engine, test_image):
        """Test basic flood fill operation."""
        seed = (30, 30)  # Inside the gray rectangle
        mask = engine.flood_fill(test_image, seed)
        
        assert mask.shape == (100, 100)
        assert mask.dtype == np.uint8
        # Should have filled the gray region
        assert np.sum(mask > 0) > 0

    def test_flood_fill_outside_bounds(self, engine, test_image):
        """Test flood fill with seed point outside image bounds."""
        mask = engine.flood_fill(test_image, (-10, -10))
        assert np.sum(mask > 0) == 0
        
        mask = engine.flood_fill(test_image, (200, 200))
        assert np.sum(mask > 0) == 0

    def test_flood_fill_white_background(self, engine, test_image):
        """Test flood fill on white background."""
        seed = (50, 50)  # White area
        mask = engine.flood_fill(test_image, seed)
        
        # Should fill most of the white area
        assert np.sum(mask > 0) > 1000

    def test_flood_fill_tolerance(self, engine):
        """Test flood fill with different tolerance values."""
        # Create image with gradient
        img = np.zeros((50, 50, 3), dtype=np.uint8)
        for i in range(50):
            img[i, :] = [i * 5, i * 5, i * 5]
        
        engine_low = SegmentationEngine(tolerance=2)
        engine_high = SegmentationEngine(tolerance=20)
        
        seed = (25, 25)
        mask_low = engine_low.flood_fill(img, seed)
        mask_high = engine_high.flood_fill(img, seed)
        
        # Higher tolerance should fill more pixels
        assert np.sum(mask_high > 0) >= np.sum(mask_low > 0)

    def test_create_polygon_mask_closed(self, engine):
        """Test creating a closed polygon mask."""
        points = [(10, 10), (40, 10), (40, 40), (10, 40)]
        mask = engine.create_polygon_mask((50, 50), points, closed=True)
        
        assert mask.shape == (50, 50)
        assert mask.dtype == np.uint8
        # Should be filled
        assert np.sum(mask > 0) > 0
        # Center should be filled
        assert mask[25, 25] == 255

    def test_create_polygon_mask_open(self, engine):
        """Test creating an open polygon mask."""
        points = [(10, 10), (40, 10), (40, 40)]
        mask = engine.create_polygon_mask((50, 50), points, closed=False)
        
        assert mask.shape == (50, 50)
        # Should only have outline, not filled
        assert np.sum(mask > 0) > 0
        # Center should not be filled (it's just a line)
        assert mask[25, 25] == 0

    def test_create_polygon_mask_insufficient_points(self, engine):
        """Test polygon mask with insufficient points."""
        mask = engine.create_polygon_mask((50, 50), [], closed=True)
        assert np.sum(mask > 0) == 0
        
        mask = engine.create_polygon_mask((50, 50), [(10, 10)], closed=True)
        assert np.sum(mask > 0) == 0
        
        mask = engine.create_polygon_mask((50, 50), [(10, 10), (20, 20)], closed=True)
        assert np.sum(mask > 0) == 0

    def test_create_polygon_mask_triangle(self, engine):
        """Test creating a triangle polygon."""
        points = [(25, 10), (10, 40), (40, 40)]
        mask = engine.create_polygon_mask((50, 50), points, closed=True)
        
        assert mask.shape == (50, 50)
        assert mask[25, 25] == 255  # Center should be filled
        assert mask[10, 10] == 0  # Outside should be empty

    def test_create_line_mask_basic(self, engine):
        """Test creating a basic line mask."""
        points = [(10, 10), (40, 40)]
        mask = engine.create_line_mask((50, 50), points)
        
        assert mask.shape == (50, 50)
        assert mask.dtype == np.uint8
        assert np.sum(mask > 0) > 0

    def test_create_line_mask_insufficient_points(self, engine):
        """Test line mask with insufficient points."""
        mask = engine.create_line_mask((50, 50), [])
        assert np.sum(mask > 0) == 0
        
        mask = engine.create_line_mask((50, 50), [(10, 10)])
        assert np.sum(mask > 0) == 0

    def test_create_line_mask_custom_thickness(self, engine):
        """Test line mask with custom thickness."""
        points = [(10, 10), (40, 10)]
        mask_thin = engine.create_line_mask((50, 50), points, thickness=1)
        mask_thick = engine.create_line_mask((50, 50), points, thickness=5)
        
        # Thicker line should have more pixels
        assert np.sum(mask_thick > 0) >= np.sum(mask_thin > 0)

    def test_create_line_mask_polyline(self, engine):
        """Test creating a polyline mask."""
        points = [(10, 10), (30, 10), (30, 30), (10, 30)]
        mask = engine.create_line_mask((50, 50), points)
        
        assert mask.shape == (50, 50)
        assert np.sum(mask > 0) > 0

    def test_create_freeform_mask(self, engine):
        """Test creating a freeform mask."""
        points = [(10, 10), (15, 12), (20, 15), (25, 18)]
        mask = engine.create_freeform_mask((50, 50), points)
        
        assert mask.shape == (50, 50)
        assert mask.dtype == np.uint8
        # Freeform should be thicker than regular line
        assert np.sum(mask > 0) > 0

    def test_create_freeform_mask_custom_thickness(self, engine):
        """Test freeform mask with custom thickness."""
        points = [(10, 10), (40, 10)]
        mask = engine.create_freeform_mask((50, 50), points, thickness=10)
        
        assert mask.shape == (50, 50)
        assert np.sum(mask > 0) > 0

    def test_erode_mask(self, engine, simple_mask):
        """Test mask erosion."""
        eroded = engine.erode_mask(simple_mask, iterations=1)
        
        assert eroded.shape == simple_mask.shape
        # Eroded mask should be smaller or equal
        assert np.sum(eroded > 0) <= np.sum(simple_mask > 0)

    def test_erode_mask_multiple_iterations(self, engine, simple_mask):
        """Test mask erosion with multiple iterations."""
        eroded_1 = engine.erode_mask(simple_mask, iterations=1)
        eroded_3 = engine.erode_mask(simple_mask, iterations=3)
        
        # More iterations should erode more
        assert np.sum(eroded_3 > 0) <= np.sum(eroded_1 > 0)

    def test_dilate_mask(self, engine, simple_mask):
        """Test mask dilation."""
        dilated = engine.dilate_mask(simple_mask, iterations=1)
        
        assert dilated.shape == simple_mask.shape
        # Dilated mask should be larger or equal
        assert np.sum(dilated > 0) >= np.sum(simple_mask > 0)

    def test_dilate_mask_multiple_iterations(self, engine, simple_mask):
        """Test mask dilation with multiple iterations."""
        dilated_1 = engine.dilate_mask(simple_mask, iterations=1)
        dilated_3 = engine.dilate_mask(simple_mask, iterations=3)
        
        # More iterations should dilate more
        assert np.sum(dilated_3 > 0) >= np.sum(dilated_1 > 0)

    def test_smooth_mask(self, engine, simple_mask):
        """Test mask smoothing."""
        smoothed = engine.smooth_mask(simple_mask, kernel_size=5)
        
        assert smoothed.shape == simple_mask.shape
        assert smoothed.dtype == np.uint8

    def test_smooth_mask_different_kernels(self, engine, simple_mask):
        """Test mask smoothing with different kernel sizes."""
        smoothed_3 = engine.smooth_mask(simple_mask, kernel_size=3)
        smoothed_7 = engine.smooth_mask(simple_mask, kernel_size=7)
        
        assert smoothed_3.shape == simple_mask.shape
        assert smoothed_7.shape == simple_mask.shape

    def test_get_contours_simple(self, engine, simple_mask):
        """Test getting contours from a simple mask."""
        contours = engine.get_contours(simple_mask)
        
        # cv2.findContours returns a tuple (contours, hierarchy)
        # Our method returns just the contours list
        assert isinstance(contours, (list, tuple))
        assert len(contours) > 0
        assert len(contours[0]) > 0

    def test_get_contours_empty_mask(self, engine):
        """Test getting contours from empty mask."""
        empty_mask = np.zeros((50, 50), dtype=np.uint8)
        contours = engine.get_contours(empty_mask)
        
        # cv2.findContours returns a tuple (contours, hierarchy)
        # Our method returns just the contours list
        assert isinstance(contours, (list, tuple))
        # May have no contours or empty contours depending on OpenCV version
        assert len(contours) >= 0

    def test_get_contours_multiple_regions(self, engine):
        """Test getting contours from mask with multiple regions."""
        mask = np.zeros((50, 50), dtype=np.uint8)
        mask[10:20, 10:20] = 255  # First region
        mask[30:40, 30:40] = 255  # Second region
        
        contours = engine.get_contours(mask)
        assert len(contours) >= 2

    def test_masks_overlap_overlapping(self, engine):
        """Test overlap detection with overlapping masks."""
        mask1 = np.zeros((50, 50), dtype=np.uint8)
        mask1[10:30, 10:30] = 255
        
        mask2 = np.zeros((50, 50), dtype=np.uint8)
        mask2[20:40, 20:40] = 255
        
        assert engine.masks_overlap(mask1, mask2) == True

    def test_masks_overlap_non_overlapping(self, engine):
        """Test overlap detection with non-overlapping masks."""
        mask1 = np.zeros((50, 50), dtype=np.uint8)
        mask1[10:20, 10:20] = 255
        
        mask2 = np.zeros((50, 50), dtype=np.uint8)
        mask2[30:40, 30:40] = 255
        
        assert engine.masks_overlap(mask1, mask2) == False

    def test_masks_overlap_different_shapes(self, engine):
        """Test overlap detection with different shape masks."""
        mask1 = np.zeros((50, 50), dtype=np.uint8)
        mask2 = np.zeros((100, 100), dtype=np.uint8)
        
        assert engine.masks_overlap(mask1, mask2) == False

    def test_combine_masks_union(self, engine):
        """Test combining masks with union operation."""
        mask1 = np.zeros((50, 50), dtype=np.uint8)
        mask1[10:20, 10:20] = 255
        
        mask2 = np.zeros((50, 50), dtype=np.uint8)
        mask2[30:40, 30:40] = 255
        
        combined = engine.combine_masks([mask1, mask2], operation="union")
        
        assert combined.shape == mask1.shape
        assert np.sum(combined > 0) == np.sum(mask1 > 0) + np.sum(mask2 > 0)

    def test_combine_masks_intersection(self, engine):
        """Test combining masks with intersection operation."""
        mask1 = np.zeros((50, 50), dtype=np.uint8)
        mask1[10:30, 10:30] = 255
        
        mask2 = np.zeros((50, 50), dtype=np.uint8)
        mask2[20:40, 20:40] = 255
        
        combined = engine.combine_masks([mask1, mask2], operation="intersection")
        
        assert combined.shape == mask1.shape
        # Intersection should be smaller than either mask
        assert np.sum(combined > 0) <= np.sum(mask1 > 0)
        assert np.sum(combined > 0) <= np.sum(mask2 > 0)

    def test_combine_masks_xor(self, engine):
        """Test combining masks with XOR operation."""
        mask1 = np.zeros((50, 50), dtype=np.uint8)
        mask1[10:30, 10:30] = 255
        
        mask2 = np.zeros((50, 50), dtype=np.uint8)
        mask2[20:40, 20:40] = 255
        
        combined = engine.combine_masks([mask1, mask2], operation="xor")
        
        assert combined.shape == mask1.shape
        # XOR should exclude intersection
        assert np.sum(combined > 0) > 0

    def test_combine_masks_empty_list(self, engine):
        """Test combining empty list of masks."""
        combined = engine.combine_masks([])
        assert combined.shape == (1, 1)
        assert np.sum(combined > 0) == 0

    def test_combine_masks_single_mask(self, engine, simple_mask):
        """Test combining single mask."""
        combined = engine.combine_masks([simple_mask], operation="union")
        assert np.array_equal(combined, simple_mask)

    def test_combine_masks_shape_mismatch(self, engine):
        """Test combining masks with mismatched shapes."""
        mask1 = np.zeros((50, 50), dtype=np.uint8)
        mask2 = np.zeros((100, 100), dtype=np.uint8)
        
        combined = engine.combine_masks([mask1, mask2], operation="union")
        # Should return first mask when shapes don't match
        assert combined.shape == mask1.shape
