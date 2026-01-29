"""Tests for SegmentElement model."""

import pytest
import numpy as np
from replan.desktop.models import SegmentElement
from replan.desktop.models.elements import LABEL_POSITIONS


class TestSegmentElementBasics:
    """Tests for basic SegmentElement functionality."""

    def test_default_initialization(self):
        """Test that defaults are set correctly."""
        elem = SegmentElement()
        assert elem.element_id != ""  # Auto-generated
        assert elem.category == ""
        assert elem.mode == "flood"
        assert elem.points == []
        assert elem.mask is None
        assert elem.color == (128, 128, 128)
        assert elem.label_position == "center"

    def test_auto_generated_id(self):
        """Test that element_id is auto-generated when empty."""
        elem1 = SegmentElement()
        elem2 = SegmentElement()
        assert elem1.element_id != elem2.element_id
        assert len(elem1.element_id) == 8

    def test_explicit_id(self):
        """Test that explicit element_id is preserved."""
        elem = SegmentElement(element_id="my-custom-id")
        assert elem.element_id == "my-custom-id"

    def test_full_initialization(self, sample_element):
        """Test initialization with all fields."""
        elem = sample_element
        assert elem.element_id == "elem-001"
        assert elem.category == "R"
        assert elem.mode == "flood"
        assert elem.points == [(50, 50)]
        assert elem.mask is not None


class TestSegmentElementBounds:
    """Tests for bounds property."""

    def test_bounds_with_mask(self, sample_element):
        """Test bounds calculation with filled mask."""
        bounds = sample_element.bounds
        assert bounds is not None
        x1, y1, x2, y2 = bounds
        # Mask is filled from [20:80, 30:70]
        assert x1 == 30
        assert y1 == 20
        assert x2 == 69  # max index
        assert y2 == 79

    def test_bounds_with_none_mask(self):
        """Test bounds returns None when mask is None."""
        elem = SegmentElement()
        assert elem.bounds is None

    def test_bounds_with_empty_mask(self, empty_mask):
        """Test bounds returns None when mask is empty."""
        elem = SegmentElement(mask=empty_mask)
        assert elem.bounds is None

    def test_bounds_single_pixel(self):
        """Test bounds with single pixel mask."""
        mask = np.zeros((100, 100), dtype=np.uint8)
        mask[50, 50] = 255
        elem = SegmentElement(mask=mask)
        bounds = elem.bounds
        assert bounds == (50, 50, 50, 50)

    def test_bounds_mask_with_holes(self):
        """Test bounds with mask containing holes."""
        mask = np.zeros((100, 100), dtype=np.uint8)
        mask[20:80, 30:70] = 255
        mask[40:60, 40:60] = 0  # Create a hole
        elem = SegmentElement(mask=mask)
        bounds = elem.bounds
        # Should still encompass the entire region including the hole
        assert bounds == (30, 20, 69, 79)

    def test_bounds_scattered_pixels(self):
        """Test bounds with scattered pixels."""
        mask = np.zeros((100, 100), dtype=np.uint8)
        mask[10, 20] = 255
        mask[90, 80] = 255
        mask[50, 50] = 255
        elem = SegmentElement(mask=mask)
        bounds = elem.bounds
        assert bounds == (20, 10, 80, 90)


class TestSegmentElementCentroid:
    """Tests for centroid property."""

    def test_centroid_with_mask(self, sample_element):
        """Test centroid calculation with filled mask."""
        centroid = sample_element.centroid
        assert centroid is not None
        cx, cy = centroid
        # Mask is filled from [20:80, 30:70], center should be around (49, 49)
        assert 45 <= cx <= 55
        assert 45 <= cy <= 55

    def test_centroid_with_none_mask(self):
        """Test centroid returns None when mask is None."""
        elem = SegmentElement()
        assert elem.centroid is None

    def test_centroid_with_empty_mask(self, empty_mask):
        """Test centroid returns None when mask is empty."""
        elem = SegmentElement(mask=empty_mask)
        assert elem.centroid is None

    def test_centroid_single_pixel(self):
        """Test centroid with single pixel mask."""
        mask = np.zeros((100, 100), dtype=np.uint8)
        mask[50, 50] = 255
        elem = SegmentElement(mask=mask)
        centroid = elem.centroid
        assert centroid == (50, 50)

    def test_centroid_mask_with_holes(self):
        """Test centroid with mask containing holes."""
        mask = np.zeros((100, 100), dtype=np.uint8)
        mask[20:80, 30:70] = 255
        mask[40:60, 40:60] = 0  # Create a hole
        elem = SegmentElement(mask=mask)
        centroid = elem.centroid
        # Should still be near center of bounding box
        assert 45 <= centroid[0] <= 55
        assert 45 <= centroid[1] <= 55

    def test_centroid_asymmetric_mask(self):
        """Test centroid with asymmetric mask."""
        mask = np.zeros((100, 100), dtype=np.uint8)
        mask[10:30, 20:40] = 255  # Small region at top-left
        elem = SegmentElement(mask=mask)
        centroid = elem.centroid
        # Should be near center of the small region
        assert 20 <= centroid[0] <= 40
        assert 10 <= centroid[1] <= 30


class TestSegmentElementArea:
    """Tests for area property."""

    def test_area_with_mask(self, sample_element):
        """Test area calculation with filled mask."""
        area = sample_element.area
        # Mask is 60x40 filled region
        assert area == 60 * 40

    def test_area_with_none_mask(self):
        """Test area returns 0 when mask is None."""
        elem = SegmentElement()
        assert elem.area == 0

    def test_area_with_empty_mask(self, empty_mask):
        """Test area returns 0 when mask is empty."""
        elem = SegmentElement(mask=empty_mask)
        assert elem.area == 0

    def test_area_single_pixel(self):
        """Test area with single pixel mask."""
        mask = np.zeros((100, 100), dtype=np.uint8)
        mask[50, 50] = 255
        elem = SegmentElement(mask=mask)
        assert elem.area == 1

    def test_area_mask_with_holes(self):
        """Test area with mask containing holes."""
        mask = np.zeros((100, 100), dtype=np.uint8)
        mask[20:80, 30:70] = 255
        mask[40:60, 40:60] = 0  # Create a hole (20x20)
        elem = SegmentElement(mask=mask)
        # Should exclude the hole
        expected_area = (60 * 40) - (20 * 20)
        assert elem.area == expected_area

    def test_area_partial_values(self):
        """Test area with mask containing partial values (not just 0/255)."""
        mask = np.zeros((100, 100), dtype=np.uint8)
        mask[20:80, 30:70] = 128  # Partial values
        elem = SegmentElement(mask=mask)
        # Should count pixels > 0
        assert elem.area == 60 * 40


class TestSegmentElementLabelPosition:
    """Tests for get_label_position method."""

    def test_center_position(self, sample_element):
        """Test center label position."""
        sample_element.label_position = "center"
        pos = sample_element.get_label_position()
        assert pos is not None
        x, y = pos
        # Center should be at (49, 49) for mask at [20:80, 30:70]
        cx, cy = (30 + 69) // 2, (20 + 79) // 2
        assert x == cx
        assert y == cy

    def test_top_left_position(self, sample_element):
        """Test top-left label position."""
        sample_element.label_position = "top-left"
        pos = sample_element.get_label_position()
        assert pos is not None
        x, y = pos
        # Top-left should be at (30, 15) for mask at [20:80, 30:70]
        assert x == 30
        assert y == 15  # y1 - 5

    def test_top_center_position(self, sample_element):
        """Test top-center label position."""
        sample_element.label_position = "top-center"
        pos = sample_element.get_label_position()
        assert pos is not None
        x, y = pos
        cx = (30 + 69) // 2
        assert x == cx
        assert y == 15  # y1 - 5

    def test_top_right_position(self, sample_element):
        """Test top-right label position."""
        sample_element.label_position = "top-right"
        pos = sample_element.get_label_position()
        assert pos is not None
        x, y = pos
        assert x == 69  # x2
        assert y == 15  # y1 - 5

    def test_middle_left_position(self, sample_element):
        """Test middle-left label position."""
        sample_element.label_position = "middle-left"
        pos = sample_element.get_label_position()
        assert pos is not None
        x, y = pos
        cy = (20 + 79) // 2
        assert x == 25  # x1 - 5
        assert y == cy

    def test_middle_right_position(self, sample_element):
        """Test middle-right label position."""
        sample_element.label_position = "middle-right"
        pos = sample_element.get_label_position()
        assert pos is not None
        x, y = pos
        cy = (20 + 79) // 2
        assert x == 74  # x2 + 5
        assert y == cy

    def test_bottom_left_position(self, sample_element):
        """Test bottom-left label position."""
        sample_element.label_position = "bottom-left"
        pos = sample_element.get_label_position()
        assert pos is not None
        x, y = pos
        assert x == 30  # x1
        assert y == 94  # y2 + 15

    def test_bottom_center_position(self, sample_element):
        """Test bottom-center label position."""
        sample_element.label_position = "bottom-center"
        pos = sample_element.get_label_position()
        assert pos is not None
        x, y = pos
        cx = (30 + 69) // 2
        assert x == cx
        assert y == 94  # y2 + 15

    def test_bottom_right_position(self, sample_element):
        """Test bottom-right label position."""
        sample_element.label_position = "bottom-right"
        pos = sample_element.get_label_position()
        assert pos is not None
        x, y = pos
        assert x == 69  # x2
        assert y == 94  # y2 + 15

    def test_invalid_position_defaults_to_center(self, sample_element):
        """Test that invalid label_position defaults to center."""
        sample_element.label_position = "invalid"
        pos = sample_element.get_label_position()
        assert pos is not None
        # Should default to center
        cx, cy = (30 + 69) // 2, (20 + 79) // 2
        x, y = pos
        assert x == cx
        assert y == cy

    def test_none_mask_returns_none(self):
        """Test get_label_position returns None with no mask."""
        elem = SegmentElement()
        assert elem.get_label_position() is None


class TestSegmentElementContainsPoint:
    """Tests for contains_point method."""

    def test_point_inside_mask(self, sample_element):
        """Test point inside the filled region."""
        # Mask is filled from [20:80, 30:70]
        assert sample_element.contains_point(50, 50) == True
        assert sample_element.contains_point(35, 25) == True

    def test_point_outside_mask(self, sample_element):
        """Test point outside the filled region."""
        assert sample_element.contains_point(10, 10) == False
        assert sample_element.contains_point(90, 90) == False

    def test_point_out_of_bounds(self, sample_element):
        """Test point outside image bounds."""
        assert sample_element.contains_point(-1, 50) is False
        assert sample_element.contains_point(50, -1) is False
        assert sample_element.contains_point(100, 50) is False
        assert sample_element.contains_point(50, 100) is False

    def test_none_mask_returns_false(self):
        """Test contains_point returns False with no mask."""
        elem = SegmentElement()
        assert elem.contains_point(50, 50) is False

    def test_point_on_boundary(self, sample_element):
        """Test point on mask boundary."""
        # Mask is filled from [20:80, 30:70]
        assert sample_element.contains_point(30, 20) == True  # Top-left corner
        assert sample_element.contains_point(69, 79) == True  # Bottom-right corner
        assert sample_element.contains_point(29, 20) == False  # Just outside
        assert sample_element.contains_point(70, 79) == False  # Just outside

    def test_point_in_hole(self):
        """Test point in a hole within the mask."""
        mask = np.zeros((100, 100), dtype=np.uint8)
        mask[20:80, 30:70] = 255
        mask[40:60, 40:60] = 0  # Create a hole
        elem = SegmentElement(mask=mask)
        assert elem.contains_point(50, 50) == False  # In the hole
        assert elem.contains_point(35, 25) == True  # Outside the hole

    def test_point_with_partial_value(self):
        """Test point with partial mask value."""
        mask = np.zeros((100, 100), dtype=np.uint8)
        mask[50, 50] = 128  # Partial value
        elem = SegmentElement(mask=mask)
        assert elem.contains_point(50, 50) == True  # Should be > 0


class TestSegmentElementSerialization:
    """Tests for to_dict and from_dict methods."""

    def test_to_dict_basic(self, sample_element):
        """Test basic serialization."""
        data = sample_element.to_dict()
        assert data["element_id"] == "elem-001"
        assert data["category"] == "R"
        assert data["mode"] == "flood"
        assert data["points"] == [(50, 50)]
        assert data["label_position"] == "center"

    def test_to_dict_excludes_mask_for_flood(self, sample_element):
        """Test that flood mode doesn't include mask in serialization."""
        data = sample_element.to_dict()
        assert "mask_rle" not in data
        assert "mask_bbox" not in data

    def test_to_dict_includes_mask_for_auto_mode(self, sample_mask):
        """Test that auto mode includes mask in serialization."""
        elem = SegmentElement(
            element_id="auto-elem",
            mode="auto",
            mask=sample_mask,
        )
        data = elem.to_dict()
        assert "mask_rle" in data
        assert "mask_bbox" in data
        assert "mask_shape" in data

    def test_to_dict_includes_mask_for_rect_mode(self, sample_mask):
        """Test that rect mode includes mask in serialization."""
        elem = SegmentElement(
            element_id="rect-elem",
            mode="rect",
            mask=sample_mask,
        )
        data = elem.to_dict()
        assert "mask_rle" in data
        assert "mask_bbox" in data

    def test_rle_encoding_structure(self, sample_mask):
        """Test RLE encoding produces correct structure."""
        elem = SegmentElement(
            element_id="rle-test",
            mode="auto",
            mask=sample_mask,
        )
        data = elem.to_dict()
        
        # Check structure
        assert "mask_rle" in data
        assert "mask_bbox" in data
        assert "mask_shape" in data
        
        # Check bbox format
        bbox = data["mask_bbox"]
        assert len(bbox) == 4
        assert all(isinstance(x, int) for x in bbox)
        
        # Check shape format
        shape = data["mask_shape"]
        assert len(shape) == 2
        assert all(isinstance(x, int) for x in shape)
        
        # Check RLE format
        rle = data["mask_rle"]
        assert isinstance(rle, list)
        assert len(rle) > 0
        for run in rle:
            assert isinstance(run, list)
            assert len(run) == 2
            assert isinstance(run[0], int)  # value
            assert isinstance(run[1], int)  # count

    def test_rle_encoding_correctness(self, sample_mask):
        """Test RLE encoding produces correct values."""
        elem = SegmentElement(
            element_id="rle-test",
            mode="auto",
            mask=sample_mask,
        )
        data = elem.to_dict()
        
        # Decode RLE to verify correctness
        bbox = data["mask_bbox"]
        shape = data["mask_shape"]
        rle = data["mask_rle"]
        
        # Reconstruct flat array
        flat = []
        for val, count in rle:
            flat.extend([val] * count)
        
        # Reshape and place in full mask
        cropped = np.array(flat, dtype=np.uint8).reshape(shape)
        x1, y1, x2, y2 = bbox
        reconstructed = np.zeros((100, 100), dtype=np.uint8)
        reconstructed[y1:y2, x1:x2] = cropped
        
        # Compare with original (only in the bbox region)
        original_cropped = sample_mask[y1:y2, x1:x2]
        np.testing.assert_array_equal(reconstructed[y1:y2, x1:x2], original_cropped)

    def test_rle_encoding_empty_mask(self):
        """Test RLE encoding with empty mask."""
        empty_mask = np.zeros((100, 100), dtype=np.uint8)
        elem = SegmentElement(
            element_id="empty-rle",
            mode="auto",
            mask=empty_mask,
        )
        data = elem.to_dict()
        # Empty mask should not include RLE data
        assert "mask_rle" not in data
        assert "mask_bbox" not in data

    def test_rle_encoding_single_pixel(self):
        """Test RLE encoding with single pixel mask."""
        mask = np.zeros((100, 100), dtype=np.uint8)
        mask[50, 50] = 255
        elem = SegmentElement(
            element_id="single-pixel",
            mode="auto",
            mask=mask,
        )
        data = elem.to_dict()
        assert "mask_rle" in data
        assert "mask_bbox" == [50, 50, 51, 51] or data["mask_bbox"] == [50, 50, 51, 51]

    def test_from_dict_basic(self):
        """Test basic deserialization."""
        data = {
            "element_id": "test-id",
            "category": "F",
            "mode": "polyline",
            "points": [(10, 20), (30, 40)],
            "label_position": "top-center",
        }
        elem = SegmentElement.from_dict(data)
        assert elem.element_id == "test-id"
        assert elem.category == "F"
        assert elem.mode == "polyline"
        assert elem.points == [(10, 20), (30, 40)]
        assert elem.label_position == "top-center"

    def test_from_dict_defaults(self):
        """Test deserialization with defaults."""
        elem = SegmentElement.from_dict({})
        # element_id is auto-generated in __post_init__ when empty
        assert elem.element_id != ""
        assert len(elem.element_id) == 8
        assert elem.mode == "flood"
        assert elem.label_position == "center"

    def test_from_dict_with_mask_and_color(self, sample_mask):
        """Test deserialization with provided mask and color."""
        data = {"element_id": "test"}
        elem = SegmentElement.from_dict(data, mask=sample_mask, color=(255, 0, 0))
        assert elem.mask is not None
        assert elem.color == (255, 0, 0)

    def test_roundtrip_serialization(self, sample_element):
        """Test that to_dict -> from_dict preserves basic data."""
        data = sample_element.to_dict()
        restored = SegmentElement.from_dict(data)
        assert restored.element_id == sample_element.element_id
        assert restored.category == sample_element.category
        assert restored.mode == sample_element.mode
        assert restored.points == sample_element.points


class TestLabelPositions:
    """Tests for LABEL_POSITIONS constant."""

    def test_contains_expected_positions(self):
        """Test that expected positions are defined."""
        assert "center" in LABEL_POSITIONS
        assert "top-left" in LABEL_POSITIONS
        assert "bottom-right" in LABEL_POSITIONS

    def test_nine_positions(self):
        """Test that all nine positions are defined."""
        assert len(LABEL_POSITIONS) == 9
