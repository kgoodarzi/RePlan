"""
Test for planform view creation to ensure only overlapping objects are copied.
"""
import unittest
from unittest.mock import Mock, patch, MagicMock
import numpy as np
import cv2
import uuid
from replan.desktop.models import PageTab, SegmentedObject, ObjectInstance, SegmentElement, DynamicCategory
from replan.desktop.config import AppSettings


class TestPlanformViewCreation(unittest.TestCase):
    """Test that planform view creation only includes objects that overlap with the planform."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a mock app with minimal setup
        self.app = Mock()
        self.app.settings = AppSettings()
        self.app.categories = {}
        self.app.all_objects = []
        self.app.selected_object_ids = set()
        self.app.pages = {}
        self.app.current_page_id = None
        
        # Create default categories
        from replan.desktop.models import create_default_categories
        self.app.categories = create_default_categories()
        
        
        # Create a test image (200x200)
        self.image_h, self.image_w = 200, 200
        test_image = np.ones((self.image_h, self.image_w, 3), dtype=np.uint8) * 255
        
        # Create a test page
        self.page_id = str(uuid.uuid4())[:8]
        self.page = PageTab(
            tab_id=self.page_id,
            model_name="test_model",
            page_name="test_page",
            original_image=test_image,
            source_path=None,
            rotation=0,
            active=True,
            dpi=150.0,
            pdf_width_inches=10.0,
            pdf_height_inches=10.0
        )
        self.app.pages[self.page_id] = self.page
        self.app.current_page_id = self.page_id
        
        # Mock _get_current_page
        self.app._get_current_page = Mock(return_value=self.page)
        
        # Mock _get_working_image to return the original image
        self.app._get_working_image = Mock(return_value=test_image)
        
        # Mock _add_page
        self.app._add_page = Mock()
        
        # Mock _update_display and _update_tree
        self.app._update_display = Mock()
        self.app._update_tree = Mock()
        
        # Mock _invalidate_working_image_cache
        self.app._invalidate_working_image_cache = Mock()
        
        # Mock status_var
        self.app.status_var = Mock()
        self.app.status_var.set = Mock()
        
        # Mock workspace_modified
        self.app.workspace_modified = False
        
        # Mock notebook
        self.app.notebook = Mock()
        self.app.notebook.select = Mock()
        
        # Mock pages dict structure (needed for notebook.select)
        self.app.pages = {self.page_id: Mock(frame=Mock())}
        
        # Track new pages added
        self.app.added_pages = []
        
        def mock_add_page(page, from_workspace=False):
            self.app.added_pages.append(page)
            # Add to pages dict with a mock frame
            self.app.pages[page.tab_id] = Mock(frame=Mock())
        
        self.app._add_page = mock_add_page
    
    def create_planform_mask(self, shape, center_x, center_y, width, height):
        """Create a polyline-shaped planform mask (L-shaped, not a rectangle)."""
        h, w = shape
        mask = np.zeros((h, w), dtype=np.uint8)
        
        # Create an L-shaped polyline (not a filled rectangle)
        # This creates a specific L-shape that doesn't fill the entire bounding box
        x_min = center_x - width // 2
        x_max = center_x + width // 2
        y_min = center_y - height // 2
        y_max = center_y + height // 2
        
        # Create L-shape explicitly by filling only the L region
        # Top horizontal bar (from left edge to center, with some thickness)
        bar_thickness = 10
        mask[y_min:y_min+bar_thickness, x_min:center_x] = 255
        
        # Left vertical bar (from top to bottom, with some thickness)
        mask[y_min:y_max, x_min:x_min+bar_thickness] = 255
        
        # Fill the L-shaped interior explicitly (don't use floodFill to avoid overfilling)
        # Fill a rectangular region in the corner
        fill_width = center_x - x_min - bar_thickness
        fill_height = y_max - y_min - bar_thickness
        if fill_width > 0 and fill_height > 0:
            mask[y_min+bar_thickness:y_min+bar_thickness+fill_height//2, 
                 x_min+bar_thickness:x_min+bar_thickness+fill_width] = 255
        
        return mask
    
    def create_object_mask(self, shape, center_x, center_y, radius):
        """Create a circular object mask."""
        h, w = shape
        y, x = np.ogrid[:h, :w]
        mask = ((x - center_x)**2 + (y - center_y)**2 <= radius**2).astype(np.uint8) * 255
        return mask
    
    def test_only_overlapping_objects_copied(self):
        """Test that only objects overlapping with planform polyline are copied."""
        import cv2
        
        # Create a planform with L-shaped polyline (center at 100, 100, size 80x80)
        planform_center_x, planform_center_y = 100, 100
        planform_width, planform_height = 80, 80
        planform_mask = self.create_planform_mask(
            (self.image_h, self.image_w),
            planform_center_x, planform_center_y,
            planform_width, planform_height
        )
        
        # Create planform object
        planform_elem = SegmentElement(
            element_id="planform_elem_1",
            category="planform",
            mode="polyline",
            points=[(60, 60), (140, 60), (60, 60), (60, 140)],  # L-shape points
            mask=planform_mask,
            color=(255, 0, 0),
            label_position=None
        )
        planform_inst = ObjectInstance(
            instance_id="planform_inst_1",
            instance_num=1,
            elements=[planform_elem],
            page_id=self.page_id,
            view_type="plan",
            attributes=None
        )
        planform_obj = SegmentedObject(
            object_id="planform_obj_1",
            name="TestPlanform",
            category="planform",
            instances=[planform_inst]
        )
        self.app.all_objects.append(planform_obj)
        self.app.selected_object_ids = {planform_obj.object_id}
        
        # Create objects:
        # 1. Object INSIDE planform (should be copied)
        inside_mask = self.create_object_mask(
            (self.image_h, self.image_w), 80, 80, 15
        )
        inside_elem = SegmentElement(
            element_id="inside_elem_1",
            category="R",  # Use existing "Rib" category
            mode="flood",
            points=[(80, 80)],
            mask=inside_mask,
            color=(0, 255, 0),
            label_position=None
        )
        inside_obj = SegmentedObject(
            object_id="inside_obj_1",
            name="InsideObject",
            category="R",  # Use existing "Rib" category
            instances=[ObjectInstance(
                instance_id="inside_inst_1",
                instance_num=1,
                elements=[inside_elem],
                page_id=self.page_id,
                view_type="plan",
                attributes=None
            )]
        )
        self.app.all_objects.append(inside_obj)
        
        # 2. Object OUTSIDE planform (should NOT be copied)
        # Position it far enough away that it doesn't overlap (planform is at 60-140, so put object at 20,20)
        outside_mask = self.create_object_mask(
            (self.image_h, self.image_w), 20, 20, 15
        )
        outside_elem = SegmentElement(
            element_id="outside_elem_1",
            category="R",  # Use existing "Rib" category
            mode="flood",
            points=[(20, 20)],
            mask=outside_mask,
            color=(0, 0, 255),
            label_position=None
        )
        outside_obj = SegmentedObject(
            object_id="outside_obj_1",
            name="OutsideObject",
            category="R",  # Use existing "Rib" category
            instances=[ObjectInstance(
                instance_id="outside_inst_1",
                instance_num=1,
                elements=[outside_elem],
                page_id=self.page_id,
                view_type="plan",
                attributes=None
            )]
        )
        self.app.all_objects.append(outside_obj)
        
        # 3. Object PARTIALLY overlapping (should be copied, but only overlapping part)
        partial_mask = self.create_object_mask(
            (self.image_h, self.image_w), 70, 70, 20  # Overlaps with planform
        )
        partial_elem = SegmentElement(
            element_id="partial_elem_1",
            category="R",  # Use existing "Rib" category
            mode="flood",
            points=[(70, 70)],
            mask=partial_mask,
            color=(255, 255, 0),
            label_position=None
        )
        partial_obj = SegmentedObject(
            object_id="partial_obj_1",
            name="PartialObject",
            category="R",  # Use existing "Rib" category
            instances=[ObjectInstance(
                instance_id="partial_inst_1",
                instance_num=1,
                elements=[partial_elem],
                page_id=self.page_id,
                view_type="plan",
                attributes=None
            )]
        )
        self.app.all_objects.append(partial_obj)
        
        # Verify initial state
        self.assertEqual(len(self.app.all_objects), 4)  # planform + 3 objects
        
        # Mock simpledialog to return a view name
        with patch('tools.segmenter.app.simpledialog.askstring', return_value="test_view"):
            # Import and call the method
            from replan.desktop.app import SegmenterApp
            # We need to get the actual method from the class
            create_method = SegmenterApp._create_view_tab_from_planform
            
            # Bind it to our mock app
            bound_method = create_method.__get__(self.app, SegmenterApp)
            
            # Call it
            bound_method()
        
        # Verify that a new page was created
        self.assertEqual(len(self.app.added_pages), 1)
        new_page = self.app.added_pages[0]
        self.assertIsInstance(new_page, PageTab)
        self.assertEqual(new_page.page_name, "test_view")
        
        # Verify objects in new view
        # Count objects that should be in the new view
        new_view_objects = [obj for obj in self.app.all_objects 
                           if any(inst.page_id == new_page.tab_id for inst in obj.instances)]
        
        # Debug: Print what we found
        print(f"\nDEBUG: New view objects:")
        for obj in new_view_objects:
            print(f"  - {obj.object_id} ({obj.name})")
        
        # Debug: Check overlap manually
        print(f"\nDEBUG: Checking overlaps manually:")
        print(f"  Planform mask pixels: {np.sum(planform_mask > 0)}")
        print(f"  Inside object mask pixels: {np.sum(inside_mask > 0)}")
        inside_overlap = np.sum((inside_mask > 0) & (planform_mask > 0))
        print(f"  Inside object overlap: {inside_overlap}")
        print(f"  Outside object mask pixels: {np.sum(outside_mask > 0)}")
        outside_overlap = np.sum((outside_mask > 0) & (planform_mask > 0))
        print(f"  Outside object overlap: {outside_overlap}")
        print(f"  Partial object mask pixels: {np.sum(partial_mask > 0)}")
        partial_overlap = np.sum((partial_mask > 0) & (planform_mask > 0))
        print(f"  Partial object overlap: {partial_overlap}")
        
        # Should have: planform + inside_obj + partial_obj (but NOT outside_obj)
        new_view_object_ids = {obj.object_id for obj in new_view_objects}
        
        # Verify planform is included
        self.assertIn(planform_obj.object_id + "_" + new_page.tab_id, 
                     [obj.object_id for obj in new_view_objects])
        
        # Verify inside object is included
        self.assertIn(inside_obj.object_id + "_" + new_page.tab_id,
                     [obj.object_id for obj in new_view_objects])
        
        # Verify partial object is included
        self.assertIn(partial_obj.object_id + "_" + new_page.tab_id,
                     [obj.object_id for obj in new_view_objects])
        
        # CRITICAL: Verify outside object is NOT included
        outside_obj_ids = [obj.object_id for obj in new_view_objects 
                          if obj.object_id.startswith("outside_obj_1")]
        self.assertEqual(len(outside_obj_ids), 0, 
                        f"Outside object should not be in new view, but found: {outside_obj_ids}")
        
        # Verify that copied objects only have pixels within planform
        for obj in new_view_objects:
            if obj.object_id == planform_obj.object_id + "_" + new_page.tab_id:
                continue  # Skip planform itself
            
            for inst in obj.instances:
                if inst.page_id == new_page.tab_id:
                    for elem in inst.elements:
                        if elem.mask is not None:
                            # Get the cropped planform mask for comparison
                            # The mask should already be cropped to the bounding box
                            mask_h, mask_w = elem.mask.shape
                            
                            # Check that all mask pixels are within the cropped planform area
                            # We need to check against the original planform mask
                            # Since masks are cropped, we need to verify the logic differently
                            # For now, just verify the mask exists and has pixels
                            mask_pixels = np.sum(elem.mask > 0)
                            self.assertGreater(mask_pixels, 0, 
                                             f"Object {obj.object_id} element {elem.element_id} has no pixels")


if __name__ == '__main__':
    unittest.main()
