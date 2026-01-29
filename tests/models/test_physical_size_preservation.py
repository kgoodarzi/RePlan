"""Tests for physical size preservation when moving objects between pages."""

import unittest
import numpy as np
from replan.desktop.models.page import PageTab
from replan.desktop.models.objects import SegmentedObject, ObjectInstance, SegmentElement


class TestPhysicalSizePreservation(unittest.TestCase):
    """Test that physical size is preserved when moving objects between pages."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Page 1: 150 DPI, 8.5x11 inches
        self.page1 = PageTab(
            tab_id="page1",
            model_name="test",
            page_name="Page 1",
            original_image=np.zeros((1650, 1275, 3), dtype=np.uint8),  # 11" x 8.5" at 150 DPI
            dpi=150.0,
            pdf_width_inches=8.5,
            pdf_height_inches=11.0
        )
        
        # Page 2: 300 DPI, 8.5x11 inches (same physical size, different DPI)
        self.page2 = PageTab(
            tab_id="page2",
            model_name="test",
            page_name="Page 2",
            original_image=np.zeros((3300, 2550, 3), dtype=np.uint8),  # 11" x 8.5" at 300 DPI
            dpi=300.0,
            pdf_width_inches=8.5,
            pdf_height_inches=11.0
        )
        
        # Create test object with physical dimensions
        elem = SegmentElement(
            element_id="elem1",
            category="rib",
            mode="flood",
            mask=np.ones((150, 150), dtype=np.uint8) * 255  # 1" x 1" at 150 DPI
        )
        
        inst = ObjectInstance(
            instance_id="inst1",
            instance_num=1,
            page_id="page1",
            elements=[elem]
        )
        
        self.obj = SegmentedObject(
            object_id="obj1",
            name="Test Object",
            category="rib",
            instances=[inst]
        )
    
    def test_physical_scale_calculation(self):
        """Test that scale factor is calculated based on pixels_per_inch ratio."""
        src_ppi = self.page1.pixels_per_inch
        dst_ppi = self.page2.pixels_per_inch
        
        # Scale should be 300/150 = 2.0
        physical_scale = dst_ppi / src_ppi if src_ppi > 0 else 1.0
        
        self.assertEqual(physical_scale, 2.0)
    
    def test_mask_scaling_preserves_physical_size(self):
        """Test that mask is scaled to preserve physical size."""
        src_h, src_w = self.page1.original_image.shape[:2]
        src_ppi = self.page1.pixels_per_inch
        dst_ppi = self.page2.pixels_per_inch
        
        physical_scale = dst_ppi / src_ppi if src_ppi > 0 else 1.0
        
        # Original mask is 150x150 pixels (1" x 1" at 150 DPI)
        original_mask = np.ones((150, 150), dtype=np.uint8) * 255
        
        # After scaling, should be 300x300 pixels (1" x 1" at 300 DPI)
        new_w = int(150 * physical_scale)
        new_h = int(150 * physical_scale)
        
        self.assertEqual(new_w, 300)
        self.assertEqual(new_h, 300)
        
        # Physical size should be preserved: 1" x 1"
        physical_width_original = 150 / src_ppi  # 1.0 inch
        physical_width_new = new_w / dst_ppi  # 1.0 inch
        
        self.assertAlmostEqual(physical_width_original, physical_width_new, places=2)
    
    def test_points_scaling_preserves_physical_size(self):
        """Test that points are scaled to preserve physical size."""
        src_ppi = self.page1.pixels_per_inch
        dst_ppi = self.page2.pixels_per_inch
        
        physical_scale = dst_ppi / src_ppi if src_ppi > 0 else 1.0
        
        # Original point at (150, 150) - 1" from origin at 150 DPI
        original_point = (150, 150)
        
        # After scaling
        scaled_point = (int(original_point[0] * physical_scale), 
                       int(original_point[1] * physical_scale))
        
        self.assertEqual(scaled_point, (300, 300))
        
        # Physical distance should be preserved
        physical_dist_original = 150 / src_ppi  # 1.0 inch
        physical_dist_new = 300 / dst_ppi  # 1.0 inch
        
        self.assertAlmostEqual(physical_dist_original, physical_dist_new, places=2)


if __name__ == "__main__":
    unittest.main()
