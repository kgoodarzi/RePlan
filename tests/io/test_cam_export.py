"""Tests for CAM/G-code export functionality."""

import unittest
import numpy as np
import tempfile
import os

from replan.desktop.io.cam_export import GCodeExporter
from replan.desktop.models.page import PageTab
from replan.desktop.models.objects import SegmentedObject, ObjectInstance, SegmentElement
from replan.desktop.models.categories import DynamicCategory


class TestGCodeExporter(unittest.TestCase):
    """Test G-code export functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.exporter = GCodeExporter(feed_rate=1000.0, power=80.0)
        
        # Create test page
        self.page = PageTab(
            tab_id="page1",
            model_name="test",
            page_name="Page 1",
            original_image=np.zeros((100, 100, 3), dtype=np.uint8),
            dpi=150.0
        )
        
        # Create test object with mask
        mask = np.zeros((100, 100), dtype=np.uint8)
        mask[20:80, 20:80] = 255  # Square region
        
        elem = SegmentElement(
            element_id="elem1",
            category="rib",
            mode="flood",
            mask=mask
        )
        
        inst = ObjectInstance(
            instance_id="inst1",
            instance_num=1,
            page_id="page1",
            elements=[elem]
        )
        
        obj = SegmentedObject(
            object_id="obj1",
            name="Test Part",
            category="rib",
            instances=[inst]
        )
        
        self.page.objects = [obj]
        self.categories = {
            "rib": DynamicCategory(prefix="rib", full_name="Rib", name="Rib", color_rgb=(255, 0, 0))
        }
    
    def test_export_gcode(self):
        """Test exporting G-code."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.gcode', delete=False) as f:
            temp_path = f.name
        
        try:
            # Export
            scale = 25.4 / self.page.pixels_per_inch  # mm per pixel
            result = self.exporter.export_page(temp_path, self.page, self.categories, scale)
            
            self.assertTrue(result)
            self.assertTrue(os.path.exists(temp_path))
            
            # Verify file content
            with open(temp_path, 'r') as f:
                content = f.read()
            
            # Check for G-code commands
            self.assertIn("G21", content)  # Millimeters
            self.assertIn("G90", content)  # Absolute positioning
            self.assertIn("M3", content)  # Laser on
            self.assertIn("M5", content)  # Laser off
            self.assertIn("M30", content)  # End of program
            
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)


if __name__ == "__main__":
    unittest.main()
