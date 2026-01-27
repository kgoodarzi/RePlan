"""Tests for 1:1 scale printing functionality."""

import pytest
import numpy as np
import tempfile
from pathlib import Path

from replan.desktop.io.printing import (
    PrintSettings,
    TileInfo,
    ScaledPrinter,
    get_recommended_settings,
)
from replan.desktop.models import PageTab, DynamicCategory


class TestPrintSettings:
    """Tests for PrintSettings dataclass."""

    def test_default_settings(self):
        """Test default print settings."""
        settings = PrintSettings()
        assert settings.target_dpi == 300.0
        assert settings.margin_inches == 0.5
        assert settings.paper_width_inches == 8.5
        assert settings.paper_height_inches == 11.0

    def test_printable_area(self):
        """Test printable area calculations."""
        settings = PrintSettings(
            paper_width_inches=8.5,
            paper_height_inches=11.0,
            margin_inches=0.5,
        )
        assert settings.printable_width_inches == 7.5
        assert settings.printable_height_inches == 10.0

    def test_printable_pixels(self):
        """Test printable area in pixels."""
        settings = PrintSettings(
            target_dpi=300.0,
            paper_width_inches=8.5,
            paper_height_inches=11.0,
            margin_inches=0.5,
        )
        assert settings.printable_width_px == 2250  # 7.5 * 300
        assert settings.printable_height_px == 3000  # 10.0 * 300


class TestTileInfo:
    """Tests for TileInfo dataclass."""

    def test_tile_creation(self):
        """Test creating a tile info."""
        tile = TileInfo(
            row=1,
            col=2,
            x_offset=15.0,
            y_offset=10.0,
            width_inches=7.5,
            height_inches=10.0,
        )
        assert tile.row == 1
        assert tile.col == 2
        assert tile.x_offset == 15.0


class TestScaledPrinter:
    """Tests for ScaledPrinter class."""

    @pytest.fixture
    def sample_page(self):
        """Create a sample page for testing."""
        # Create a 1650x2400 image (11" x 16" at 150 DPI)
        image = np.ones((2400, 1650, 3), dtype=np.uint8) * 255
        # Add some content
        image[100:200, 100:200] = [0, 0, 255]  # Red square
        
        return PageTab(
            tab_id="test-page",
            model_name="TestModel",
            page_name="Page1",
            original_image=image,
            dpi=150.0,
            pdf_width_inches=11.0,
            pdf_height_inches=16.0,
        )

    @pytest.fixture
    def small_page(self):
        """Create a small page that fits on one sheet."""
        # Create a 750x1050 image (5" x 7" at 150 DPI)
        image = np.ones((1050, 750, 3), dtype=np.uint8) * 255
        
        return PageTab(
            tab_id="small-page",
            model_name="Small",
            page_name="Page1",
            original_image=image,
            dpi=150.0,
            pdf_width_inches=5.0,
            pdf_height_inches=7.0,
        )

    @pytest.fixture
    def categories(self):
        """Create category definitions."""
        return {
            "R": DynamicCategory(
                name="R",
                prefix="R",
                full_name="Rib",
                color_rgb=(220, 60, 60),
            ),
        }

    @pytest.fixture
    def printer(self):
        """Create a printer instance."""
        return ScaledPrinter()

    def test_get_actual_scale(self, printer, sample_page):
        """Test getting actual scale from page."""
        ppi = printer.get_actual_scale(sample_page)
        assert ppi == 150.0

    def test_get_actual_scale_from_pdf_dims(self, printer):
        """Test scale calculation from PDF dimensions."""
        # 3300 pixels wide, 11" PDF width = 300 PPI
        image = np.zeros((4800, 3300, 3), dtype=np.uint8)
        page = PageTab(
            tab_id="test",
            original_image=image,
            pdf_width_inches=11.0,
        )
        ppi = printer.get_actual_scale(page)
        assert ppi == 300.0

    def test_get_physical_size(self, printer, sample_page):
        """Test getting physical dimensions."""
        width, height = printer.get_physical_size(sample_page)
        assert width == 11.0
        assert height == 16.0

    def test_get_physical_size_no_image(self, printer):
        """Test physical size with no image."""
        page = PageTab(tab_id="empty")
        width, height = printer.get_physical_size(page)
        assert width == 0.0
        assert height == 0.0

    def test_needs_tiling_large(self, printer, sample_page):
        """Test that large page needs tiling."""
        settings = PrintSettings()
        assert printer.needs_tiling(sample_page, settings) is True

    def test_needs_tiling_small(self, printer, small_page):
        """Test that small page doesn't need tiling."""
        settings = PrintSettings()
        assert printer.needs_tiling(small_page, settings) is False

    def test_calculate_tiles(self, printer, sample_page):
        """Test tile calculation for large page."""
        settings = PrintSettings()
        tiles = printer.calculate_tiles(sample_page, settings)
        
        # 11" x 16" on 7.5" x 10" printable = 2 cols x 2 rows
        assert len(tiles) >= 4
        
        # Check first tile
        first_tile = tiles[0]
        assert first_tile.row == 0
        assert first_tile.col == 0
        assert first_tile.x_offset == 0.0
        assert first_tile.y_offset == 0.0

    def test_calculate_tiles_small(self, printer, small_page):
        """Test tile calculation for small page (single tile)."""
        settings = PrintSettings()
        tiles = printer.calculate_tiles(small_page, settings)
        
        assert len(tiles) == 1
        assert tiles[0].row == 0
        assert tiles[0].col == 0

    def test_prepare_print_image(self, printer, small_page, categories):
        """Test preparing image for print."""
        settings = PrintSettings(target_dpi=300.0)
        image = printer.prepare_print_image(small_page, categories, settings)
        
        # Should be scaled up from 150 DPI to 300 DPI (2x)
        assert image is not None
        original_h, original_w = small_page.original_image.shape[:2]
        expected_w = int(original_w * 2)
        expected_h = int(original_h * 2)
        
        # Allow some margin for scale bar addition
        assert abs(image.shape[1] - expected_w) < 10
        assert abs(image.shape[0] - expected_h) < 10

    def test_export_for_print(self, printer, small_page, categories):
        """Test exporting for print."""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            temp_path = f.name
        
        try:
            settings = PrintSettings(target_dpi=150.0)  # Lower for faster test
            result = printer.export_for_print(temp_path, small_page, categories, settings)
            
            assert result is True
            assert Path(temp_path).exists()
            
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_export_tiles(self, printer, sample_page, categories):
        """Test exporting tiles."""
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = PrintSettings(target_dpi=100.0)  # Lower for faster test
            files = printer.export_tiles(temp_dir, sample_page, categories, settings)
            
            assert len(files) >= 4
            for filepath in files:
                assert Path(filepath).exists()


class TestGetRecommendedSettings:
    """Tests for get_recommended_settings function."""

    def test_small_page_letter(self):
        """Test settings for small page."""
        image = np.zeros((1050, 750, 3), dtype=np.uint8)
        page = PageTab(
            tab_id="test",
            original_image=image,
            dpi=150.0,
        )
        
        settings = get_recommended_settings(page)
        assert settings.paper_width_inches == 8.5
        assert settings.paper_height_inches == 11.0

    def test_wide_page_tabloid(self):
        """Test settings for wide page recommends tabloid."""
        # 15" x 8" at 100 DPI = 1500 x 800 pixels
        image = np.zeros((800, 1500, 3), dtype=np.uint8)
        page = PageTab(
            tab_id="test",
            original_image=image,
            dpi=100.0,
        )
        
        settings = get_recommended_settings(page)
        # Should recommend tabloid (17x11) for wide page
        assert settings.paper_width_inches == 17.0
        assert settings.paper_height_inches == 11.0

    def test_no_image(self):
        """Test settings with no image."""
        page = PageTab(tab_id="test")
        settings = get_recommended_settings(page)
        
        # Should use defaults
        assert settings.paper_width_inches == 8.5
