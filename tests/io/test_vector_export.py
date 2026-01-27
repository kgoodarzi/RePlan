"""Tests for DXF and SVG vector export functionality."""

import pytest
import numpy as np
import tempfile
from pathlib import Path

from replan.desktop.io.vector_export import (
    ContourExtractor,
    DXFExporter,
    SVGExporter,
    VectorPath,
    export_dxf,
    export_svg,
)
from replan.desktop.models import (
    PageTab,
    SegmentedObject,
    ObjectInstance,
    SegmentElement,
    DynamicCategory,
)


@pytest.fixture
def rectangle_mask():
    """Create a mask with a simple rectangle."""
    mask = np.zeros((100, 100), dtype=np.uint8)
    mask[20:80, 30:70] = 255
    return mask


@pytest.fixture
def circle_mask():
    """Create a mask with a filled circle."""
    mask = np.zeros((100, 100), dtype=np.uint8)
    y, x = np.ogrid[:100, :100]
    center_y, center_x = 50, 50
    radius = 30
    dist = np.sqrt((x - center_x)**2 + (y - center_y)**2)
    mask[dist <= radius] = 255
    return mask


@pytest.fixture
def donut_mask():
    """Create a mask with a donut shape (outer circle with hole)."""
    mask = np.zeros((100, 100), dtype=np.uint8)
    y, x = np.ogrid[:100, :100]
    center_y, center_x = 50, 50
    outer_r, inner_r = 40, 15
    dist = np.sqrt((x - center_x)**2 + (y - center_y)**2)
    mask[(dist <= outer_r) & (dist > inner_r)] = 255
    return mask


@pytest.fixture
def sample_page_with_objects(rectangle_mask, circle_mask):
    """Create a page with multiple objects for testing export."""
    image = np.zeros((100, 100, 3), dtype=np.uint8)
    
    page = PageTab(
        tab_id="test-page",
        model_name="TestModel",
        page_name="Page1",
        original_image=image,
    )
    
    # Create object with rectangle
    elem1 = SegmentElement(
        element_id="elem-rect",
        category="R",
        mode="flood",
        mask=rectangle_mask,
    )
    inst1 = ObjectInstance(
        instance_id="inst-1",
        instance_num=1,
        elements=[elem1],
        page_id="test-page",
    )
    obj1 = SegmentedObject(
        object_id="obj-rect",
        name="R1",
        category="R",
        instances=[inst1],
    )
    
    # Create object with circle
    elem2 = SegmentElement(
        element_id="elem-circle",
        category="F",
        mode="flood",
        mask=circle_mask,
    )
    inst2 = ObjectInstance(
        instance_id="inst-2",
        instance_num=1,
        elements=[elem2],
        page_id="test-page",
    )
    obj2 = SegmentedObject(
        object_id="obj-circle",
        name="F1",
        category="F",
        instances=[inst2],
    )
    
    page.objects = [obj1, obj2]
    return page


@pytest.fixture
def categories():
    """Create category definitions."""
    return {
        "R": DynamicCategory(
            name="R",
            prefix="R",
            full_name="Rib",
            color_rgb=(220, 60, 60),
        ),
        "F": DynamicCategory(
            name="F",
            prefix="F",
            full_name="Former",
            color_rgb=(60, 60, 220),
        ),
    }


class TestContourExtractor:
    """Tests for ContourExtractor class."""

    def test_extract_from_rectangle_mask(self, rectangle_mask):
        """Test extracting contours from rectangle mask."""
        extractor = ContourExtractor()
        contours = extractor.extract_from_mask(rectangle_mask)
        
        assert len(contours) > 0
        contour, is_outer = contours[0]
        assert is_outer == True
        assert len(contour) >= 4  # Rectangle has at least 4 vertices

    def test_extract_from_circle_mask(self, circle_mask):
        """Test extracting contours from circle mask."""
        extractor = ContourExtractor()
        contours = extractor.extract_from_mask(circle_mask)
        
        assert len(contours) > 0
        contour, is_outer = contours[0]
        assert is_outer == True

    def test_extract_from_donut_mask(self, donut_mask):
        """Test extracting contours from donut mask (with hole)."""
        extractor = ContourExtractor()
        contours = extractor.extract_from_mask(donut_mask)
        
        # Should have outer and inner contour
        assert len(contours) >= 2
        
        outer_count = sum(1 for _, is_outer in contours if is_outer)
        inner_count = sum(1 for _, is_outer in contours if not is_outer)
        
        assert outer_count >= 1
        assert inner_count >= 1

    def test_extract_from_empty_mask(self):
        """Test extracting from empty mask."""
        extractor = ContourExtractor()
        empty_mask = np.zeros((100, 100), dtype=np.uint8)
        contours = extractor.extract_from_mask(empty_mask)
        
        assert len(contours) == 0

    def test_extract_from_none_mask(self):
        """Test extracting from None mask."""
        extractor = ContourExtractor()
        contours = extractor.extract_from_mask(None)
        
        assert len(contours) == 0

    def test_simplification(self, circle_mask):
        """Test that simplification reduces vertex count."""
        extractor_no_simplify = ContourExtractor(simplify_epsilon=0)
        extractor_simplify = ContourExtractor(simplify_epsilon=2.0)
        
        contours_no_simp = extractor_no_simplify.extract_from_mask(circle_mask)
        contours_simp = extractor_simplify.extract_from_mask(circle_mask)
        
        # Simplified should have fewer or equal vertices
        if contours_no_simp and contours_simp:
            len_no_simp = len(contours_no_simp[0][0])
            len_simp = len(contours_simp[0][0])
            assert len_simp <= len_no_simp

    def test_extract_from_page(self, sample_page_with_objects, categories):
        """Test extracting all paths from a page."""
        extractor = ContourExtractor()
        paths = extractor.extract_from_page(sample_page_with_objects, categories)
        
        assert len(paths) >= 2  # At least one path per object
        
        # Check path structure
        for path in paths:
            assert isinstance(path, VectorPath)
            assert path.object_name in ["R1", "F1"]
            assert len(path.contour) >= 3


class TestDXFExporter:
    """Tests for DXFExporter class."""

    def test_export_page(self, sample_page_with_objects, categories):
        """Test exporting page to DXF."""
        exporter = DXFExporter()
        
        with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False) as f:
            temp_path = f.name
        
        try:
            result = exporter.export_page(temp_path, sample_page_with_objects, categories)
            assert result is True
            
            # Verify file was created
            assert Path(temp_path).exists()
            
            # Verify basic DXF structure
            content = Path(temp_path).read_text()
            assert "SECTION" in content
            assert "ENTITIES" in content
            assert "LWPOLYLINE" in content
            assert "EOF" in content
            
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_export_empty_page(self, categories):
        """Test exporting page with no objects."""
        page = PageTab(
            tab_id="empty",
            model_name="Empty",
            page_name="Page1",
        )
        
        exporter = DXFExporter()
        
        with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False) as f:
            temp_path = f.name
        
        try:
            result = exporter.export_page(temp_path, page, categories)
            assert result is False  # No contours to export
            
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_export_includes_layers(self, sample_page_with_objects, categories):
        """Test that DXF includes category layers."""
        exporter = DXFExporter()
        
        with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False) as f:
            temp_path = f.name
        
        try:
            exporter.export_page(temp_path, sample_page_with_objects, categories)
            content = Path(temp_path).read_text()
            
            # Check for layer definitions
            assert "LAYER" in content
            assert "R" in content  # Rib category
            assert "F" in content  # Former category
            
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_rgb_to_aci_red(self):
        """Test RGB to ACI conversion for red."""
        exporter = DXFExporter()
        aci = exporter._rgb_to_aci((255, 0, 0))
        assert aci == 1  # Red

    def test_rgb_to_aci_blue(self):
        """Test RGB to ACI conversion for blue."""
        exporter = DXFExporter()
        aci = exporter._rgb_to_aci((0, 0, 255))
        assert aci == 5  # Blue


class TestSVGExporter:
    """Tests for SVGExporter class."""

    def test_export_page(self, sample_page_with_objects, categories):
        """Test exporting page to SVG."""
        exporter = SVGExporter()
        
        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as f:
            temp_path = f.name
        
        try:
            result = exporter.export_page(temp_path, sample_page_with_objects, categories)
            assert result is True
            
            # Verify file was created
            assert Path(temp_path).exists()
            
            # Verify basic SVG structure
            content = Path(temp_path).read_text()
            assert '<?xml version="1.0"' in content
            assert '<svg' in content
            assert '</svg>' in content
            assert '<path' in content
            
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_export_empty_page(self, categories):
        """Test exporting page with no objects."""
        page = PageTab(
            tab_id="empty",
            model_name="Empty",
            page_name="Page1",
        )
        
        exporter = SVGExporter()
        
        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as f:
            temp_path = f.name
        
        try:
            result = exporter.export_page(temp_path, page, categories)
            assert result is False  # No contours to export
            
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_export_includes_groups(self, sample_page_with_objects, categories):
        """Test that SVG includes category groups."""
        exporter = SVGExporter()
        
        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as f:
            temp_path = f.name
        
        try:
            exporter.export_page(temp_path, sample_page_with_objects, categories)
            content = Path(temp_path).read_text()
            
            # Check for group elements
            assert '<g id="R"' in content  # Rib category group
            assert '<g id="F"' in content  # Former category group
            
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_export_with_colors(self, sample_page_with_objects, categories):
        """Test that SVG includes correct colors."""
        exporter = SVGExporter()
        
        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as f:
            temp_path = f.name
        
        try:
            exporter.export_page(temp_path, sample_page_with_objects, categories)
            content = Path(temp_path).read_text()
            
            # Check for color values (R category is (220, 60, 60))
            assert "#dc3c3c" in content  # RGB 220, 60, 60 as hex
            # Check for F category color (60, 60, 220)
            assert "#3c3cdc" in content
            
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_contour_to_path_data(self):
        """Test SVG path data generation."""
        exporter = SVGExporter()
        contour = np.array([[10, 20], [30, 20], [30, 40], [10, 40]])
        
        path_data = exporter._contour_to_path_data(contour)
        
        assert path_data.startswith("M ")
        assert "L " in path_data
        assert path_data.endswith("Z")


class TestConvenienceFunctions:
    """Tests for export_dxf and export_svg convenience functions."""

    def test_export_dxf_function(self, sample_page_with_objects, categories):
        """Test export_dxf convenience function."""
        with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False) as f:
            temp_path = f.name
        
        try:
            result = export_dxf(temp_path, sample_page_with_objects, categories)
            assert result is True
            assert Path(temp_path).exists()
            
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_export_svg_function(self, sample_page_with_objects, categories):
        """Test export_svg convenience function."""
        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as f:
            temp_path = f.name
        
        try:
            result = export_svg(temp_path, sample_page_with_objects, categories)
            assert result is True
            assert Path(temp_path).exists()
            
        finally:
            Path(temp_path).unlink(missing_ok=True)


class TestVectorPath:
    """Tests for VectorPath dataclass."""

    def test_vector_path_creation(self):
        """Test creating a VectorPath."""
        contour = np.array([[0, 0], [10, 0], [10, 10], [0, 10]])
        
        path = VectorPath(
            object_id="obj-1",
            object_name="R1",
            category="R",
            instance_num=1,
            element_id="elem-1",
            contour=contour,
            area=100.0,
            is_outer=True,
            color_rgb=(255, 0, 0),
        )
        
        assert path.object_name == "R1"
        assert path.is_outer is True
        assert len(path.contour) == 4
