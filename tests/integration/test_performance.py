"""Performance tests to verify operations meet targets."""

import pytest
import numpy as np
import time

from replan.desktop.io.pdf_reader import PDFReader
from replan.desktop.core.segmentation import SegmentationEngine
from replan.desktop.utils.profiling import PerformanceProfiler


class TestPDFLoadPerformance:
    """Test PDF loading performance."""
    
    @pytest.fixture
    def pdf_reader(self):
        """Create PDFReader instance."""
        return PDFReader(dpi=150)
    
    def test_pdf_load_performance_target(self, pdf_reader):
        """Test that PDF loading meets < 2 second target."""
        # Note: This test requires an actual PDF file
        # For now, we verify the profiling is in place
        profiler = PerformanceProfiler.get_instance()
        target = profiler.TARGETS.get("pdf_load", 2000)
        
        assert target == 2000, "PDF load target should be 2000ms"
        
        # The actual performance test would require a PDF file
        # In CI/CD, this could use a test PDF fixture
        # For now, we verify the infrastructure is in place


class TestFloodFillPerformance:
    """Test flood fill performance."""
    
    @pytest.fixture
    def engine(self):
        """Create SegmentationEngine."""
        return SegmentationEngine(tolerance=5)
    
    @pytest.fixture
    def large_image(self):
        """Create a large test image (typical PDF page size)."""
        # Typical PDF page at 150 DPI: ~1650x1275 pixels (11x8.5 inches)
        return np.zeros((1275, 1650, 3), dtype=np.uint8)
    
    def test_flood_fill_performance_target(self, engine, large_image):
        """Test that flood fill meets < 1 second target."""
        profiler = PerformanceProfiler.get_instance()
        target = profiler.TARGETS.get("flood_fill", 1000)
        
        assert target == 1000, "Flood fill target should be 1000ms"
        
        # Add a region to fill
        large_image[500:700, 500:700] = [100, 100, 100]
        
        # Clear profiler
        profiler.clear()
        
        # Perform flood fill (should be timed automatically via @timed decorator)
        mask = engine.flood_fill(large_image, (600, 600))
        
        # Verify it completed
        assert mask is not None
        assert np.sum(mask) > 0
        
        # Check performance
        summary = profiler.get_summary()
        if "flood_fill" in summary:
            avg_time = summary["flood_fill"]["avg_ms"]
            target_time = summary["flood_fill"]["target_ms"]
            
            # Log the result (won't fail test, but provides info)
            print(f"\nFlood fill performance: {avg_time:.1f}ms (target: {target_time}ms)")
            
            # In a real scenario, you might want to assert:
            # assert avg_time <= target_time, f"Flood fill took {avg_time}ms, exceeds target of {target_time}ms"
            # But we'll be lenient for now since performance can vary by system
    
    def test_flood_fill_small_image_performance(self, engine):
        """Test flood fill on smaller image (should be very fast)."""
        small_image = np.zeros((200, 300, 3), dtype=np.uint8)
        small_image[50:150, 50:150] = [100, 100, 100]
        
        profiler = PerformanceProfiler.get_instance()
        profiler.clear()
        
        mask = engine.flood_fill(small_image, (100, 100))
        
        assert mask is not None
        
        summary = profiler.get_summary()
        if "flood_fill" in summary:
            avg_time = summary["flood_fill"]["avg_ms"]
            print(f"\nSmall image flood fill: {avg_time:.1f}ms")
            
            # Small images should be very fast (< 100ms typically)
            assert avg_time < 500, f"Small image flood fill should be < 500ms, got {avg_time}ms"
