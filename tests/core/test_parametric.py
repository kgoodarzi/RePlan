"""Tests for parametric part generation."""

import unittest
import numpy as np

from replan.desktop.core.parametric import ParametricPartGenerator, RibParameters, FormerParameters
from replan.desktop.models.objects import SegmentedObject


class TestParametricPartGenerator(unittest.TestCase):
    """Test parametric part generation."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.generator = ParametricPartGenerator(dpi=150.0)
    
    def test_generate_rib(self):
        """Test generating a rib from parameters."""
        params = RibParameters(
            chord=10.0,  # 10 inches
            thickness=0.125,  # 1/8 inch
            lightening_holes=[(5.0, 0.0625, 0.5)],  # One hole at center
            tabs=[(0, 0, 1.0, 0.25)]  # One tab
        )
        
        obj = self.generator.generate_rib(params)
        
        self.assertIsNotNone(obj)
        self.assertEqual(obj.category, "rib")
        self.assertEqual(len(obj.instances), 1)
        self.assertEqual(len(obj.instances[0].elements), 1)
        
        # Check attributes
        attrs = obj.instances[0].attributes
        self.assertEqual(attrs.width, 10.0)
        self.assertEqual(attrs.height, 0.125)
        self.assertEqual(attrs.obj_type, "rib")
        
        # Check mask exists
        elem = obj.instances[0].elements[0]
        self.assertIsNotNone(elem.mask)
        self.assertGreater(elem.mask.shape[0], 0)
        self.assertGreater(elem.mask.shape[1], 0)
    
    def test_generate_former(self):
        """Test generating a former from parameters."""
        params = FormerParameters(
            diameter=6.0,  # 6 inches
            thickness=0.25,  # 1/4 inch wall
            lightening_holes=[(0, 0, 1.0)],  # One hole at center
            cutouts=[(2.0, 0, 1.0, 0.5)]  # One cutout
        )
        
        obj = self.generator.generate_former(params)
        
        self.assertIsNotNone(obj)
        self.assertEqual(obj.category, "former")
        self.assertEqual(len(obj.instances), 1)
        self.assertEqual(len(obj.instances[0].elements), 1)
        
        # Check attributes
        attrs = obj.instances[0].attributes
        self.assertEqual(attrs.width, 6.0)
        self.assertEqual(attrs.height, 6.0)
        self.assertEqual(attrs.depth, 0.25)
        self.assertEqual(attrs.obj_type, "former")
        
        # Check mask exists
        elem = obj.instances[0].elements[0]
        self.assertIsNotNone(elem.mask)
        # Former should be roughly circular
        self.assertGreater(elem.mask.shape[0], 0)
        self.assertGreater(elem.mask.shape[1], 0)
    
    def test_inches_to_pixels(self):
        """Test inches to pixels conversion."""
        pixels = self.generator.inches_to_pixels(1.0)
        self.assertEqual(pixels, 150)  # 1 inch * 150 DPI
        
        pixels = self.generator.inches_to_pixels(2.5)
        self.assertEqual(pixels, 375)  # 2.5 inches * 150 DPI


if __name__ == "__main__":
    unittest.main()
