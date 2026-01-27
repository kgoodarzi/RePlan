"""Tests for ObjectAttributes model."""

import pytest
from replan.desktop.models import ObjectAttributes, MATERIALS, TYPES, VIEWS


class TestObjectAttributesBasics:
    """Tests for basic ObjectAttributes functionality."""

    def test_default_initialization(self, default_attributes):
        """Test that defaults are set correctly."""
        attrs = default_attributes
        assert attrs.material == ""
        assert attrs.width == 0.0
        assert attrs.height == 0.0
        assert attrs.depth == 0.0
        assert attrs.obj_type == ""
        assert attrs.view == ""
        assert attrs.description == ""
        assert attrs.url == ""
        assert attrs.quantity == 1
        assert attrs.notes == ""

    def test_full_initialization(self, full_attributes):
        """Test initialization with all fields."""
        attrs = full_attributes
        assert attrs.material == "balsa"
        assert attrs.width == 10.0
        assert attrs.height == 5.0
        assert attrs.depth == 0.125
        assert attrs.obj_type == "sheet"
        assert attrs.view == "top"
        assert attrs.quantity == 12


class TestObjectAttributesHasDimensions:
    """Tests for has_dimensions property."""

    def test_no_dimensions(self, default_attributes):
        """Test has_dimensions returns False when all dimensions are zero."""
        assert default_attributes.has_dimensions is False

    def test_only_width(self):
        """Test has_dimensions returns True when only width is set."""
        attrs = ObjectAttributes(width=5.0)
        assert attrs.has_dimensions is True

    def test_only_height(self):
        """Test has_dimensions returns True when only height is set."""
        attrs = ObjectAttributes(height=3.0)
        assert attrs.has_dimensions is True

    def test_only_depth(self):
        """Test has_dimensions returns True when only depth is set."""
        attrs = ObjectAttributes(depth=0.125)
        assert attrs.has_dimensions is True

    def test_all_dimensions(self, full_attributes):
        """Test has_dimensions returns True when all dimensions are set."""
        assert full_attributes.has_dimensions is True

    def test_negative_dimensions(self):
        """Test has_dimensions with negative values (treated as not set)."""
        attrs = ObjectAttributes(width=-5.0)
        assert attrs.has_dimensions is False


class TestObjectAttributesSizeString:
    """Tests for size_string property."""

    def test_empty_size_string(self, default_attributes):
        """Test size_string is empty when no dimensions."""
        assert default_attributes.size_string == ""

    def test_width_only(self):
        """Test size_string with only width."""
        attrs = ObjectAttributes(width=10.0)
        assert attrs.size_string == "W:10.0"

    def test_height_only(self):
        """Test size_string with only height."""
        attrs = ObjectAttributes(height=5.0)
        assert attrs.size_string == "H:5.0"

    def test_depth_only(self):
        """Test size_string with only depth."""
        attrs = ObjectAttributes(depth=0.125)
        assert attrs.size_string == "D:0.125"

    def test_all_dimensions(self):
        """Test size_string with all dimensions."""
        attrs = ObjectAttributes(width=10.0, height=5.0, depth=0.125)
        assert attrs.size_string == "W:10.0 × H:5.0 × D:0.125"

    def test_two_dimensions(self):
        """Test size_string with two dimensions."""
        attrs = ObjectAttributes(width=10.0, depth=0.125)
        assert attrs.size_string == "W:10.0 × D:0.125"


class TestObjectAttributesSerialization:
    """Tests for to_dict and from_dict methods."""

    def test_to_dict_default(self, default_attributes):
        """Test serialization of default attributes."""
        data = default_attributes.to_dict()
        assert data["material"] == ""
        assert data["width"] == 0.0
        assert data["quantity"] == 1

    def test_to_dict_full(self, full_attributes):
        """Test serialization of full attributes."""
        data = full_attributes.to_dict()
        assert data["material"] == "balsa"
        assert data["width"] == 10.0
        assert data["height"] == 5.0
        assert data["depth"] == 0.125
        assert data["obj_type"] == "sheet"
        assert data["view"] == "top"
        assert data["quantity"] == 12

    def test_from_dict_empty(self):
        """Test deserialization from empty dict."""
        attrs = ObjectAttributes.from_dict({})
        assert attrs.material == ""
        assert attrs.quantity == 1

    def test_from_dict_full(self):
        """Test deserialization from full dict."""
        data = {
            "material": "plywood",
            "width": 20.0,
            "height": 10.0,
            "depth": 3.0,
            "obj_type": "sheet",
            "view": "side",
            "description": "Test part",
            "url": "https://example.com",
            "quantity": 5,
            "notes": "Some notes",
        }
        attrs = ObjectAttributes.from_dict(data)
        assert attrs.material == "plywood"
        assert attrs.width == 20.0
        assert attrs.quantity == 5

    def test_roundtrip_serialization(self, full_attributes):
        """Test that to_dict -> from_dict preserves data."""
        data = full_attributes.to_dict()
        restored = ObjectAttributes.from_dict(data)
        assert restored.material == full_attributes.material
        assert restored.width == full_attributes.width
        assert restored.height == full_attributes.height
        assert restored.depth == full_attributes.depth
        assert restored.quantity == full_attributes.quantity

    def test_from_dict_partial(self):
        """Test deserialization with partial data."""
        data = {"material": "balsa", "width": 5.0}
        attrs = ObjectAttributes.from_dict(data)
        assert attrs.material == "balsa"
        assert attrs.width == 5.0
        assert attrs.height == 0.0  # Default
        assert attrs.quantity == 1  # Default


class TestMaterialsTypesViews:
    """Tests for module-level constants."""

    def test_materials_contains_common(self):
        """Test MATERIALS contains common materials."""
        assert "balsa" in MATERIALS
        assert "plywood" in MATERIALS
        assert "carbon fiber" in MATERIALS

    def test_types_contains_common(self):
        """Test TYPES contains common component types."""
        assert "stick" in TYPES
        assert "sheet" in TYPES
        assert "tube" in TYPES

    def test_views_contains_common(self):
        """Test VIEWS contains common view types."""
        assert "top" in VIEWS
        assert "side" in VIEWS
        assert "template" in VIEWS
        assert "cutout" in VIEWS
