"""Tests for DynamicCategory model and category utilities."""

import pytest
from replan.desktop.models import (
    DynamicCategory,
    DEFAULT_CATEGORIES,
    CATEGORY_COLORS,
    create_default_categories,
    get_next_color,
)


class TestDynamicCategoryBasics:
    """Tests for basic DynamicCategory functionality."""

    def test_basic_initialization(self):
        """Test basic category creation."""
        cat = DynamicCategory(
            name="R",
            prefix="R",
            full_name="Rib",
            color_rgb=(220, 60, 60),
        )
        assert cat.name == "R"
        assert cat.prefix == "R"
        assert cat.full_name == "Rib"
        assert cat.color_rgb == (220, 60, 60)

    def test_default_selection_mode(self):
        """Test default selection mode is flood."""
        cat = DynamicCategory(
            name="X",
            prefix="X",
            full_name="Test",
            color_rgb=(100, 100, 100),
        )
        assert cat.selection_mode == "flood"

    def test_default_visible(self):
        """Test default visible is True."""
        cat = DynamicCategory(
            name="X",
            prefix="X",
            full_name="Test",
            color_rgb=(100, 100, 100),
        )
        assert cat.visible is True

    def test_default_instances(self):
        """Test default instances is empty list."""
        cat = DynamicCategory(
            name="X",
            prefix="X",
            full_name="Test",
            color_rgb=(100, 100, 100),
        )
        assert cat.instances == []


class TestDynamicCategoryColorBgr:
    """Tests for color_bgr auto-generation."""

    def test_auto_generated_bgr(self):
        """Test color_bgr is auto-generated from color_rgb."""
        cat = DynamicCategory(
            name="X",
            prefix="X",
            full_name="Test",
            color_rgb=(220, 60, 80),
        )
        # BGR should be reversed RGB
        assert cat.color_bgr == (80, 60, 220)

    def test_explicit_bgr(self):
        """Test explicit color_bgr overrides auto-generation."""
        cat = DynamicCategory(
            name="X",
            prefix="X",
            full_name="Test",
            color_rgb=(220, 60, 80),
            color_bgr=(10, 20, 30),
        )
        assert cat.color_bgr == (10, 20, 30)

    def test_rgb_bgr_relationship(self, sample_category):
        """Test that RGB and BGR are properly related."""
        r, g, b = sample_category.color_rgb
        b_bgr, g_bgr, r_bgr = sample_category.color_bgr
        assert r == r_bgr
        assert g == g_bgr
        assert b == b_bgr


class TestDynamicCategoryColorHex:
    """Tests for color_hex property."""

    def test_color_hex_basic(self, sample_category):
        """Test color_hex format."""
        hex_color = sample_category.color_hex
        assert hex_color.startswith("#")
        assert len(hex_color) == 7

    def test_color_hex_values(self):
        """Test color_hex conversion."""
        cat = DynamicCategory(
            name="X",
            prefix="X",
            full_name="Test",
            color_rgb=(255, 128, 0),
        )
        assert cat.color_hex == "#ff8000"

    def test_color_hex_black(self):
        """Test color_hex for black."""
        cat = DynamicCategory(
            name="X",
            prefix="X",
            full_name="Test",
            color_rgb=(0, 0, 0),
        )
        assert cat.color_hex == "#000000"

    def test_color_hex_white(self):
        """Test color_hex for white."""
        cat = DynamicCategory(
            name="X",
            prefix="X",
            full_name="Test",
            color_rgb=(255, 255, 255),
        )
        assert cat.color_hex == "#ffffff"


class TestDynamicCategorySerialization:
    """Tests for to_dict and from_dict methods."""

    def test_to_dict(self, sample_category):
        """Test serialization to dictionary."""
        data = sample_category.to_dict()
        assert data["name"] == "R"
        assert data["prefix"] == "R"
        assert data["full_name"] == "Rib"
        assert data["color_rgb"] == [220, 60, 60]
        assert data["selection_mode"] == "flood"
        assert data["visible"] is True

    def test_to_dict_excludes_instances(self, sample_category):
        """Test that instances are excluded from serialization."""
        sample_category.instances = ["R1", "R2", "R3"]
        data = sample_category.to_dict()
        assert "instances" not in data

    def test_to_dict_excludes_color_bgr(self, sample_category):
        """Test that color_bgr is excluded from serialization."""
        data = sample_category.to_dict()
        assert "color_bgr" not in data

    def test_from_dict_basic(self):
        """Test deserialization from dictionary."""
        data = {
            "name": "F",
            "prefix": "F",
            "full_name": "Former",
            "color_rgb": [200, 80, 80],
            "selection_mode": "polyline",
            "visible": False,
        }
        cat = DynamicCategory.from_dict(data)
        assert cat.name == "F"
        assert cat.full_name == "Former"
        assert cat.color_rgb == (200, 80, 80)
        assert cat.selection_mode == "polyline"
        assert cat.visible is False

    def test_from_dict_defaults(self):
        """Test deserialization uses defaults for missing fields."""
        data = {"name": "X"}
        cat = DynamicCategory.from_dict(data)
        assert cat.name == "X"
        assert cat.prefix == ""
        assert cat.full_name == ""
        assert cat.color_rgb == (128, 128, 128)  # Default color
        assert cat.selection_mode == "flood"
        assert cat.visible is True

    def test_from_dict_empty(self):
        """Test deserialization from empty dict."""
        cat = DynamicCategory.from_dict({})
        assert cat.name == ""
        assert cat.selection_mode == "flood"
        assert cat.visible is True

    def test_roundtrip_serialization(self, sample_category):
        """Test that to_dict -> from_dict preserves data."""
        data = sample_category.to_dict()
        restored = DynamicCategory.from_dict(data)
        assert restored.name == sample_category.name
        assert restored.prefix == sample_category.prefix
        assert restored.full_name == sample_category.full_name
        assert restored.color_rgb == sample_category.color_rgb
        assert restored.selection_mode == sample_category.selection_mode
        assert restored.visible == sample_category.visible


class TestCreateDefaultCategories:
    """Tests for create_default_categories function."""

    def test_returns_dict(self):
        """Test that function returns a dictionary."""
        cats = create_default_categories()
        assert isinstance(cats, dict)

    def test_contains_expected_categories(self):
        """Test that result contains expected categories."""
        cats = create_default_categories()
        assert "R" in cats
        assert "F" in cats
        assert "planform" in cats

    def test_all_values_are_dynamic_category(self):
        """Test that all values are DynamicCategory instances."""
        cats = create_default_categories()
        for cat in cats.values():
            assert isinstance(cat, DynamicCategory)

    def test_categories_match_defaults(self):
        """Test that categories match DEFAULT_CATEGORIES."""
        cats = create_default_categories()
        for key, (full_name, color, mode) in DEFAULT_CATEGORIES.items():
            assert key in cats
            assert cats[key].full_name == full_name
            assert cats[key].color_rgb == color
            assert cats[key].selection_mode == mode


class TestGetNextColor:
    """Tests for get_next_color function."""

    def test_returns_tuple(self):
        """Test that function returns a tuple."""
        color = get_next_color(0)
        assert isinstance(color, tuple)
        assert len(color) == 3

    def test_first_color(self):
        """Test first color from palette."""
        color = get_next_color(0)
        assert color == CATEGORY_COLORS[0]

    def test_second_color(self):
        """Test second color from palette."""
        color = get_next_color(1)
        assert color == CATEGORY_COLORS[1]

    def test_wraparound(self):
        """Test color wraparound when count exceeds palette length."""
        palette_len = len(CATEGORY_COLORS)
        color_first = get_next_color(0)
        color_wrapped = get_next_color(palette_len)
        assert color_first == color_wrapped

    def test_wraparound_multiple(self):
        """Test multiple wraparounds."""
        palette_len = len(CATEGORY_COLORS)
        for i in range(palette_len * 3):
            color = get_next_color(i)
            assert color == CATEGORY_COLORS[i % palette_len]


class TestDefaultCategories:
    """Tests for DEFAULT_CATEGORIES constant."""

    def test_is_dict(self):
        """Test DEFAULT_CATEGORIES is a dictionary."""
        assert isinstance(DEFAULT_CATEGORIES, dict)

    def test_contains_rib(self):
        """Test contains Rib category."""
        assert "R" in DEFAULT_CATEGORIES
        full_name, color, mode = DEFAULT_CATEGORIES["R"]
        assert full_name == "Rib"

    def test_contains_former(self):
        """Test contains Former category."""
        assert "F" in DEFAULT_CATEGORIES
        full_name, color, mode = DEFAULT_CATEGORIES["F"]
        assert full_name == "Former"

    def test_contains_mark_categories(self):
        """Test contains mark categories for hide feature."""
        assert "mark_text" in DEFAULT_CATEGORIES
        assert "mark_hatch" in DEFAULT_CATEGORIES
        assert "mark_line" in DEFAULT_CATEGORIES

    def test_all_values_are_tuples(self):
        """Test all values are 3-element tuples."""
        for key, value in DEFAULT_CATEGORIES.items():
            assert isinstance(value, tuple)
            assert len(value) == 3


class TestCategoryColors:
    """Tests for CATEGORY_COLORS constant."""

    def test_is_list(self):
        """Test CATEGORY_COLORS is a list."""
        assert isinstance(CATEGORY_COLORS, list)

    def test_not_empty(self):
        """Test CATEGORY_COLORS is not empty."""
        assert len(CATEGORY_COLORS) > 0

    def test_all_tuples(self):
        """Test all elements are 3-element tuples."""
        for color in CATEGORY_COLORS:
            assert isinstance(color, tuple)
            assert len(color) == 3

    def test_valid_rgb_values(self):
        """Test all RGB values are in valid range."""
        for r, g, b in CATEGORY_COLORS:
            assert 0 <= r <= 255
            assert 0 <= g <= 255
            assert 0 <= b <= 255
