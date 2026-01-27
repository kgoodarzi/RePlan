"""Tests for PageTab model."""

import pytest
import numpy as np
from replan.desktop.models import PageTab, SegmentedObject, ObjectInstance, SegmentElement


class TestPageTabBasics:
    """Tests for basic PageTab functionality."""

    def test_default_initialization(self):
        """Test that defaults are set correctly."""
        page = PageTab()
        assert page.tab_id != ""  # Auto-generated
        assert page.model_name == ""
        assert page.page_name == ""
        assert page.original_image is None
        assert page.segmentation_layer is None
        assert page.objects == []
        assert page.source_path is None
        assert page.rotation == 0
        assert page.active is True
        assert page.dpi == 150.0
        assert page.pdf_width_inches == 0.0
        assert page.pdf_height_inches == 0.0

    def test_auto_generated_id(self):
        """Test that tab_id is auto-generated when empty."""
        page1 = PageTab()
        page2 = PageTab()
        assert page1.tab_id != page2.tab_id
        assert len(page1.tab_id) == 8

    def test_explicit_id(self):
        """Test that explicit tab_id is preserved."""
        page = PageTab(tab_id="my-custom-id")
        assert page.tab_id == "my-custom-id"

    def test_full_initialization(self, sample_page):
        """Test initialization with all fields."""
        page = sample_page
        assert page.tab_id == "page-001"
        assert page.model_name == "TestModel"
        assert page.page_name == "Page1"
        assert page.original_image is not None
        assert page.dpi == 150.0
        assert page.pdf_width_inches == 11.0
        assert page.pdf_height_inches == 8.5


class TestPageTabFilenames:
    """Tests for filename properties."""

    def test_raster_filename(self, sample_page):
        """Test raster_filename generation."""
        assert sample_page.raster_filename == "TestModel_Page1_raster.png"

    def test_segmented_filename(self, sample_page):
        """Test segmented_filename generation."""
        assert sample_page.segmented_filename == "TestModel_Page1_segmented.png"

    def test_empty_names(self):
        """Test filenames with empty names."""
        page = PageTab()
        assert page.raster_filename == "__raster.png"
        assert page.segmented_filename == "__segmented.png"


class TestPageTabDisplayName:
    """Tests for display_name property."""

    def test_active_page(self, sample_page):
        """Test display name for active page."""
        sample_page.active = True
        assert sample_page.display_name == "TestModel - Page1"

    def test_inactive_page(self, sample_page):
        """Test display name for inactive page."""
        sample_page.active = False
        assert sample_page.display_name == "⏸ TestModel - Page1"


class TestPageTabImageSize:
    """Tests for image_size property."""

    def test_with_image(self, sample_page):
        """Test image_size with image."""
        size = sample_page.image_size
        assert size is not None
        assert size == (300, 200)  # width, height

    def test_without_image(self, empty_page):
        """Test image_size without image."""
        assert empty_page.image_size is None


class TestPageTabPixelsPerInch:
    """Tests for pixels_per_inch property."""

    def test_with_pdf_dimensions(self, sample_page):
        """Test pixels_per_inch with PDF dimensions."""
        # Image is 300x200, pdf_width is 11 inches
        ppi = sample_page.pixels_per_inch
        expected = 300 / 11.0
        assert abs(ppi - expected) < 0.01

    def test_without_pdf_dimensions(self, sample_image):
        """Test pixels_per_inch falls back to dpi."""
        page = PageTab(
            original_image=sample_image,
            dpi=200.0,
            pdf_width_inches=0.0,
        )
        assert page.pixels_per_inch == 200.0

    def test_without_image(self, empty_page):
        """Test pixels_per_inch without image."""
        assert empty_page.pixels_per_inch == 150.0  # Default DPI


class TestPageTabPixelsPerCm:
    """Tests for pixels_per_cm property."""

    def test_conversion(self, sample_page):
        """Test pixels_per_cm calculation."""
        ppi = sample_page.pixels_per_inch
        ppc = sample_page.pixels_per_cm
        assert abs(ppc - ppi / 2.54) < 0.001


class TestPageTabObjectCount:
    """Tests for object_count property."""

    def test_with_objects(self, sample_page):
        """Test object_count with objects."""
        assert sample_page.object_count == 1

    def test_empty(self, empty_page):
        """Test object_count with no objects."""
        assert empty_page.object_count == 0


class TestPageTabElementCount:
    """Tests for element_count property."""

    def test_with_objects(self, sample_page):
        """Test element_count sums across objects."""
        assert sample_page.element_count == 1

    def test_empty(self, empty_page):
        """Test element_count with no objects."""
        assert empty_page.element_count == 0


class TestPageTabGetObjectById:
    """Tests for get_object_by_id method."""

    def test_found(self, sample_page):
        """Test finding existing object."""
        obj = sample_page.get_object_by_id("obj-001")
        assert obj is not None
        assert obj.name == "R1"

    def test_not_found(self, sample_page):
        """Test returns None for non-existent object."""
        obj = sample_page.get_object_by_id("non-existent")
        assert obj is None

    def test_empty_objects(self, empty_page):
        """Test returns None with no objects."""
        assert empty_page.get_object_by_id("any") is None


class TestPageTabGetElementAtPoint:
    """Tests for get_element_at_point method."""

    def test_found(self, sample_page, sample_mask):
        """Test finding element at point inside mask."""
        # The sample mask is filled from [20:80, 30:70]
        # Need to ensure the instance has the correct page_id
        sample_page.objects[0].instances[0].page_id = sample_page.tab_id
        result = sample_page.get_element_at_point(50, 50)
        assert result is not None
        obj, inst, elem = result
        assert obj.name == "R1"

    def test_not_found(self, sample_page):
        """Test returns None for point outside all masks."""
        result = sample_page.get_element_at_point(0, 0)
        assert result is None

    def test_empty_objects(self, empty_page):
        """Test returns None with no objects."""
        result = empty_page.get_element_at_point(50, 50)
        assert result is None


class TestPageTabAddObject:
    """Tests for add_object method."""

    def test_add_object(self, empty_page):
        """Test adding an object."""
        obj = SegmentedObject(name="R1", category="R")
        empty_page.add_object(obj)
        assert len(empty_page.objects) == 1
        assert empty_page.objects[0].name == "R1"

    def test_add_multiple_objects(self, empty_page):
        """Test adding multiple objects."""
        empty_page.add_object(SegmentedObject(name="R1", category="R"))
        empty_page.add_object(SegmentedObject(name="F1", category="F"))
        assert len(empty_page.objects) == 2


class TestPageTabRemoveObject:
    """Tests for remove_object method."""

    def test_remove_existing(self, sample_page):
        """Test removing existing object."""
        result = sample_page.remove_object("obj-001")
        assert result is True
        assert len(sample_page.objects) == 0

    def test_remove_non_existent(self, sample_page):
        """Test removing non-existent object."""
        result = sample_page.remove_object("non-existent")
        assert result is False
        assert len(sample_page.objects) == 1

    def test_remove_from_empty(self, empty_page):
        """Test removing from empty list."""
        result = empty_page.remove_object("any")
        assert result is False


class TestPageTabClearSegmentationLayer:
    """Tests for clear_segmentation_layer method."""

    def test_with_image(self, sample_page):
        """Test clearing segmentation layer."""
        sample_page.clear_segmentation_layer()
        assert sample_page.segmentation_layer is not None
        assert sample_page.segmentation_layer.shape == (200, 300, 4)
        assert np.all(sample_page.segmentation_layer == 0)

    def test_without_image(self, empty_page):
        """Test clearing with no image does nothing."""
        empty_page.clear_segmentation_layer()
        assert empty_page.segmentation_layer is None


class TestPageTabSerialization:
    """Tests for to_dict and from_dict methods."""

    def test_to_dict(self, sample_page):
        """Test serialization to dictionary."""
        data = sample_page.to_dict()
        assert data["tab_id"] == "page-001"
        assert data["model_name"] == "TestModel"
        assert data["page_name"] == "Page1"
        assert data["rotation"] == 0
        assert data["active"] is True
        assert data["dpi"] == 150.0
        assert data["pdf_width_inches"] == 11.0
        assert "objects" in data

    def test_to_dict_excludes_images(self, sample_page):
        """Test that images are not included in serialization."""
        data = sample_page.to_dict()
        assert "original_image" not in data
        assert "segmentation_layer" not in data

    def test_from_dict_basic(self):
        """Test deserialization from dictionary."""
        data = {
            "tab_id": "test-id",
            "model_name": "MyModel",
            "page_name": "Page2",
            "rotation": 90,
            "active": False,
            "dpi": 200.0,
            "pdf_width_inches": 8.5,
            "pdf_height_inches": 11.0,
        }
        page = PageTab.from_dict(data)
        assert page.tab_id == "test-id"
        assert page.model_name == "MyModel"
        assert page.rotation == 90
        assert page.active is False
        assert page.dpi == 200.0

    def test_from_dict_defaults(self):
        """Test deserialization with defaults."""
        page = PageTab.from_dict({})
        assert page.rotation == 0
        assert page.active is True
        assert page.dpi == 150.0

    def test_from_dict_with_image(self, sample_image):
        """Test deserialization with provided image."""
        data = {"tab_id": "test"}
        page = PageTab.from_dict(data, image=sample_image)
        assert page.original_image is not None
        assert page.image_size == (300, 200)

    def test_from_dict_with_objects(self, sample_object):
        """Test deserialization with provided objects."""
        data = {"tab_id": "test"}
        page = PageTab.from_dict(data, objects=[sample_object])
        assert len(page.objects) == 1

    def test_roundtrip_serialization(self, sample_page):
        """Test that to_dict -> from_dict preserves basic data."""
        data = sample_page.to_dict()
        restored = PageTab.from_dict(data)
        assert restored.tab_id == sample_page.tab_id
        assert restored.model_name == sample_page.model_name
        assert restored.page_name == sample_page.page_name
        assert restored.dpi == sample_page.dpi


class TestPageTabBackwardCompatibility:
    """Tests for backward compatibility."""

    def test_groups_property(self, sample_page):
        """Test that groups property returns objects."""
        # groups is an alias for objects
        assert sample_page.groups == sample_page.objects
