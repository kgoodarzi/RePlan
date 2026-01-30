"""Tests for parts library system."""

import unittest
import numpy as np
import tempfile
import os
from pathlib import Path

from replan.desktop.io.parts_library import PartsLibrary, LibraryPart
from replan.desktop.models.objects import SegmentedObject, ObjectInstance, SegmentElement, ObjectAttributes


class TestPartsLibrary(unittest.TestCase):
    """Test parts library functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create temporary library file
        self.temp_dir = tempfile.mkdtemp()
        self.library_path = os.path.join(self.temp_dir, "test_library.plib")
        self.library = PartsLibrary(self.library_path)
    
    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.library_path):
            os.remove(self.library_path)
        os.rmdir(self.temp_dir)
    
    def test_add_part(self):
        """Test adding a part to the library."""
        # Create test object
        elem = SegmentElement(
            element_id="elem1",
            category="rib",
            mode="flood",
            mask=np.ones((100, 100), dtype=np.uint8) * 255
        )
        
        inst = ObjectInstance(
            instance_id="inst1",
            instance_num=1,
            page_id="page1",
            elements=[elem],
            attributes=ObjectAttributes(width=10.0, height=1.0)
        )
        
        obj = SegmentedObject(
            object_id="obj1",
            name="Test Rib",
            category="rib",
            instances=[inst]
        )
        
        # Add to library
        part_id = self.library.add_part(obj, name="Test Rib", description="A test rib")
        
        # Verify part was added
        self.assertIsNotNone(part_id)
        self.assertIn(part_id, self.library.parts)
        
        part = self.library.get_part(part_id)
        self.assertIsNotNone(part)
        self.assertEqual(part.name, "Test Rib")
        self.assertEqual(part.category, "rib")
    
    def test_list_parts(self):
        """Test listing parts."""
        # Add multiple parts
        elem1 = SegmentElement(element_id="e1", category="rib", mode="flood",
                               mask=np.ones((50, 50), dtype=np.uint8) * 255)
        obj1 = SegmentedObject(object_id="o1", name="Rib 1", category="rib",
                              instances=[ObjectInstance(elements=[elem1])])
        self.library.add_part(obj1)
        
        elem2 = SegmentElement(element_id="e2", category="former", mode="flood",
                               mask=np.ones((50, 50), dtype=np.uint8) * 255)
        obj2 = SegmentedObject(object_id="o2", name="Former 1", category="former",
                              instances=[ObjectInstance(elements=[elem2])])
        self.library.add_part(obj2)
        
        # List all parts
        all_parts = self.library.list_parts()
        self.assertEqual(len(all_parts), 2)
        
        # Filter by category
        ribs = self.library.list_parts(category="rib")
        self.assertEqual(len(ribs), 1)
        self.assertEqual(ribs[0].category, "rib")
    
    def test_instantiate_part(self):
        """Test instantiating a part from the library."""
        # Add a part
        elem = SegmentElement(element_id="e1", category="rib", mode="flood",
                             mask=np.ones((100, 100), dtype=np.uint8) * 255,
                             points=[(0, 0), (100, 0), (100, 100), (0, 100)])
        obj = SegmentedObject(object_id="o1", name="Test Part", category="rib",
                             instances=[ObjectInstance(elements=[elem])])
        part_id = self.library.add_part(obj)
        
        # Instantiate
        new_obj = self.library.instantiate_part(part_id, (200, 200), scale=1.0, x=50, y=50)
        
        self.assertIsNotNone(new_obj)
        self.assertEqual(new_obj.name, "Test Part")
        self.assertEqual(len(new_obj.instances), 1)
        self.assertEqual(len(new_obj.instances[0].elements), 1)
    
    def test_delete_part(self):
        """Test deleting a part from the library."""
        elem = SegmentElement(element_id="e1", category="rib", mode="flood",
                             mask=np.ones((50, 50), dtype=np.uint8) * 255)
        obj = SegmentedObject(object_id="o1", name="Test", category="rib",
                             instances=[ObjectInstance(elements=[elem])])
        part_id = self.library.add_part(obj)
        
        # Delete
        result = self.library.delete_part(part_id)
        self.assertTrue(result)
        self.assertNotIn(part_id, self.library.parts)
        
        # Try to delete non-existent part
        result = self.library.delete_part("nonexistent")
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
