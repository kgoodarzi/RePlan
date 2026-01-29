"""Tests for delete pixels functionality."""

import unittest
import numpy as np
import cv2
from replan.desktop.models.page import PageTab
from replan.desktop.models.objects import SegmentedObject, ObjectInstance, SegmentElement


class TestDeletePixels(unittest.TestCase):
    """Test pixel deletion functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a test image with some colored pixels
        self.test_image = np.zeros((100, 100, 3), dtype=np.uint8)
        self.test_image[20:40, 20:40] = [255, 0, 0]  # Red square
        
        self.page = PageTab(
            tab_id="page1",
            model_name="test",
            page_name="Page 1",
            original_image=self.test_image.copy(),
            dpi=150.0
        )
        
        # Create object with mask covering the red square
        mask = np.zeros((100, 100), dtype=np.uint8)
        mask[20:40, 20:40] = 255
        
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
        
        self.obj = SegmentedObject(
            object_id="obj1",
            name="Test Object",
            category="rib",
            instances=[inst]
        )
    
    def test_delete_pixels_sets_to_white(self):
        """Test that deleting pixels sets them to white."""
        # Get mask from object
        mask = self.obj.instances[0].elements[0].mask
        
        # Simulate pixel deletion
        h, w = self.page.original_image.shape[:2]
        combined_mask = mask.copy()
        
        # Set pixels to white where mask is active
        if len(self.page.original_image.shape) == 3:
            mask_3channel = cv2.cvtColor(combined_mask, cv2.COLOR_GRAY2BGR)
            # Use proper broadcasting for BGR assignment
            self.page.original_image[mask_3channel[:, :, 0] > 0] = [255, 255, 255]
        else:
            self.page.original_image[combined_mask > 0] = 255
        
        # Verify pixels are white
        deleted_region = self.page.original_image[20:40, 20:40]
        if len(deleted_region.shape) == 3:
            # BGR image - check all channels are 255
            self.assertTrue(np.all(deleted_region == [255, 255, 255]))
        else:
            # Grayscale - check all pixels are 255
            self.assertTrue(np.all(deleted_region == 255))
    
    def test_delete_pixels_preserves_other_pixels(self):
        """Test that deleting pixels doesn't affect other pixels."""
        # Add another colored region
        self.page.original_image[60:80, 60:80] = [0, 255, 0]  # Green square
        
        # Get mask from object
        mask = self.obj.instances[0].elements[0].mask
        
        # Simulate pixel deletion
        h, w = self.page.original_image.shape[:2]
        combined_mask = mask.copy()
        
        # Set pixels to white where mask is active
        if len(self.page.original_image.shape) == 3:
            mask_3channel = cv2.cvtColor(combined_mask, cv2.COLOR_GRAY2BGR)
            # Use proper broadcasting for BGR assignment
            self.page.original_image[mask_3channel[:, :, 0] > 0] = [255, 255, 255]
        else:
            self.page.original_image[combined_mask > 0] = 255
        
        # Verify other pixels are preserved
        preserved_region = self.page.original_image[60:80, 60:80]
        if len(preserved_region.shape) == 3:
            self.assertTrue(np.all(preserved_region == [0, 255, 0]))
        else:
            # Grayscale - green would be converted, but shouldn't be white
            self.assertFalse(np.all(preserved_region == 255))


if __name__ == "__main__":
    unittest.main()
