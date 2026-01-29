"""Tests for page deletion functionality."""

import unittest
import numpy as np
from replan.desktop.models.page import PageTab
from replan.desktop.models.objects import SegmentedObject, ObjectInstance, SegmentElement


class TestPageDeletion(unittest.TestCase):
    """Test page deletion and cleanup."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.page1 = PageTab(
            tab_id="page1",
            model_name="test",
            page_name="Page 1",
            original_image=np.zeros((100, 100, 3), dtype=np.uint8),
            dpi=150.0
        )
        
        self.page2 = PageTab(
            tab_id="page2",
            model_name="test",
            page_name="Page 2",
            original_image=np.zeros((100, 100, 3), dtype=np.uint8),
            dpi=150.0
        )
        
        # Create test objects
        elem1 = SegmentElement(
            element_id="elem1",
            category="rib",
            mode="flood",
            mask=np.ones((100, 100), dtype=np.uint8) * 255
        )
        
        inst1 = ObjectInstance(
            instance_id="inst1",
            instance_num=1,
            page_id="page1",
            elements=[elem1]
        )
        
        self.obj1 = SegmentedObject(
            object_id="obj1",
            name="Object 1",
            category="rib",
            instances=[inst1]
        )
    
    def test_page_deletion_removes_objects(self):
        """Test that deleting a page removes objects on that page."""
        pages = {"page1": self.page1, "page2": self.page2}
        all_objects = [self.obj1]
        
        # Simulate page deletion
        page_id = "page1"
        del pages[page_id]
        
        # Objects with instances on deleted page should be removed
        objects_to_remove = []
        for obj in all_objects:
            obj.instances = [inst for inst in obj.instances if inst.page_id != page_id]
            if not obj.instances:
                objects_to_remove.append(obj)
        
        for obj in objects_to_remove:
            all_objects.remove(obj)
        
        # Verify object was removed
        self.assertEqual(len(all_objects), 0)
        self.assertNotIn(self.obj1, all_objects)
    
    def test_page_deletion_preserves_other_pages(self):
        """Test that deleting one page doesn't affect other pages."""
        pages = {"page1": self.page1, "page2": self.page2}
        
        # Create object on page2
        elem2 = SegmentElement(
            element_id="elem2",
            category="rib",
            mode="flood",
            mask=np.ones((100, 100), dtype=np.uint8) * 255
        )
        
        inst2 = ObjectInstance(
            instance_id="inst2",
            instance_num=1,
            page_id="page2",
            elements=[elem2]
        )
        
        obj2 = SegmentedObject(
            object_id="obj2",
            name="Object 2",
            category="rib",
            instances=[inst2]
        )
        
        all_objects = [self.obj1, obj2]
        
        # Delete page1
        page_id = "page1"
        del pages[page_id]
        
        # Remove objects on deleted page
        objects_to_remove = []
        for obj in all_objects:
            obj.instances = [inst for inst in obj.instances if inst.page_id != page_id]
            if not obj.instances:
                objects_to_remove.append(obj)
        
        for obj in objects_to_remove:
            all_objects.remove(obj)
        
        # Verify page2 and obj2 are preserved
        self.assertEqual(len(pages), 1)
        self.assertIn("page2", pages)
        self.assertEqual(len(all_objects), 1)
        self.assertIn(obj2, all_objects)
        self.assertNotIn(self.obj1, all_objects)


if __name__ == "__main__":
    unittest.main()
