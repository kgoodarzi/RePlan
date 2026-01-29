"""Integration tests for end-to-end workflows: load PDF -> segment -> save workspace."""

import pytest
import numpy as np
import tempfile
import json
from pathlib import Path

from replan.desktop.io.pdf_reader import PDFReader
from replan.desktop.io.workspace import WorkspaceManager, WorkspaceData
from replan.desktop.core.segmentation import SegmentationEngine
from replan.desktop.models import (
    PageTab, SegmentedObject, ObjectInstance, SegmentElement,
    DynamicCategory, create_default_categories
)


class TestPDFLoadWorkflow:
    """Test PDF loading workflow."""
    
    @pytest.fixture
    def pdf_reader(self):
        """Create PDFReader instance."""
        return PDFReader(dpi=150)
    
    def test_load_pdf_basic(self, pdf_reader):
        """Test basic PDF loading."""
        # Create a simple test PDF using numpy image
        # Note: In real tests, you'd use an actual PDF file
        # For now, we'll test the structure without requiring a PDF file
        
        # Test that PDFReader can be instantiated
        assert pdf_reader is not None
        assert pdf_reader.dpi == 150
    
    def test_load_pdf_with_dimensions(self, pdf_reader):
        """Test PDF loading with dimension information."""
        # Test structure - actual PDF loading requires a real PDF file
        # This test verifies the API exists and works correctly
        reader = PDFReader(dpi=150)
        assert hasattr(reader, 'load_with_dimensions')
        assert callable(reader.load_with_dimensions)


class TestSegmentationWorkflow:
    """Test segmentation workflow."""
    
    @pytest.fixture
    def engine(self):
        """Create SegmentationEngine."""
        return SegmentationEngine(tolerance=5, line_thickness=3)
    
    @pytest.fixture
    def sample_image(self):
        """Create a sample image for segmentation."""
        img = np.zeros((200, 300, 3), dtype=np.uint8)
        # Add some colored regions for flood fill
        img[50:150, 50:150] = [100, 100, 100]  # Gray region
        img[50:150, 150:250] = [200, 200, 200]  # Light gray region
        return img
    
    def test_flood_fill_segmentation(self, engine, sample_image):
        """Test flood fill segmentation workflow."""
        # Perform flood fill
        mask = engine.flood_fill(sample_image, (100, 100))
        
        assert mask is not None
        assert mask.shape == (200, 300)
        assert mask.dtype == np.uint8
        assert np.sum(mask) > 0  # Should have some filled pixels
    
    def test_polygon_mask_creation(self, engine, sample_image):
        """Test polygon mask creation workflow."""
        points = [(50, 50), (150, 50), (150, 150), (50, 150)]
        mask = engine.create_polygon_mask(sample_image.shape[:2], points)
        
        assert mask is not None
        assert mask.shape == (200, 300)
        assert mask.dtype == np.uint8
        assert np.sum(mask) > 0
    
    def test_line_mask_creation(self, engine, sample_image):
        """Test line mask creation workflow."""
        points = [(50, 50), (150, 150)]
        mask = engine.create_line_mask(sample_image.shape[:2], points, thickness=3)
        
        assert mask is not None
        assert mask.shape == (200, 300)
        assert mask.dtype == np.uint8


class TestWorkspaceSaveLoadWorkflow:
    """Test workspace save/load workflow."""
    
    @pytest.fixture
    def workspace_manager(self):
        """Create WorkspaceManager."""
        return WorkspaceManager()
    
    @pytest.fixture
    def sample_pages(self):
        """Create sample pages for testing."""
        img1 = np.zeros((200, 300, 3), dtype=np.uint8)
        img1[50:150, 50:150] = [100, 100, 100]
        
        img2 = np.zeros((200, 300, 3), dtype=np.uint8)
        img2[50:150, 50:150] = [200, 200, 200]
        
        page1 = PageTab(
            tab_id="page-1",
            model_name="TestModel",
            page_name="Page 1",
            original_image=img1,
            source_path="/test/path.pdf",
            dpi=150.0,
            pdf_width_inches=11.0,
            pdf_height_inches=8.5,
        )
        
        page2 = PageTab(
            tab_id="page-2",
            model_name="TestModel",
            page_name="Page 2",
            original_image=img2,
            source_path="/test/path.pdf",
            dpi=150.0,
            pdf_width_inches=11.0,
            pdf_height_inches=8.5,
        )
        
        return [page1, page2]
    
    @pytest.fixture
    def sample_categories(self):
        """Create sample categories."""
        return create_default_categories()
    
    @pytest.fixture
    def sample_objects(self, sample_pages):
        """Create sample objects with segmentation."""
        engine = SegmentationEngine()
        
        # Create element on first page
        mask1 = np.zeros((200, 300), dtype=np.uint8)
        mask1[50:150, 50:150] = 255
        
        elem1 = SegmentElement(
            element_id="elem-1",
            category="R",
            mode="flood",
            points=[(100, 100)],
            mask=mask1,
            color=(220, 60, 60),
        )
        
        inst1 = ObjectInstance(
            instance_id="inst-1",
            instance_num=1,
            elements=[elem1],
            page_id="page-1",
        )
        
        obj1 = SegmentedObject(
            object_id="obj-1",
            name="R1",
            category="R",
            instances=[inst1],
        )
        
        return [obj1]
    
    def test_save_workspace(self, workspace_manager, sample_pages, sample_categories, sample_objects):
        """Test saving workspace."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace_path = Path(tmpdir) / "test_workspace.pmw"
            
            result = workspace_manager.save(
                str(workspace_path),
                sample_pages,
                sample_categories,
                objects=sample_objects,
            )
            
            assert result is True
            assert workspace_path.exists()
            
            # Verify JSON structure
            with open(workspace_path, 'r') as f:
                data = json.load(f)
            
            assert "version" in data
            assert "pages" in data
            assert "categories" in data
            assert "objects" in data
            assert len(data["pages"]) == 2
            assert len(data["objects"]) == 1
    
    def test_load_workspace(self, workspace_manager, sample_pages, sample_categories, sample_objects):
        """Test loading workspace."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace_path = Path(tmpdir) / "test_workspace.pmw"
            
            # Save first
            workspace_manager.save(
                str(workspace_path),
                sample_pages,
                sample_categories,
                objects=sample_objects,
            )
            
            # Load back
            loaded = workspace_manager.load(str(workspace_path))
            
            assert loaded is not None
            assert isinstance(loaded, WorkspaceData)
            assert len(loaded.pages) == 2
            assert len(loaded.categories) > 0
            assert len(loaded.objects) == 1
            
            # Verify page data
            assert loaded.pages[0].tab_id == "page-1"
            assert loaded.pages[0].model_name == "TestModel"
            assert loaded.pages[0].original_image is not None
            
            # Verify object data
            assert loaded.objects[0].object_id == "obj-1"
            assert loaded.objects[0].name == "R1"
            assert len(loaded.objects[0].instances) == 1
            assert len(loaded.objects[0].instances[0].elements) == 1


class TestEndToEndWorkflow:
    """Test complete end-to-end workflow: load PDF -> segment -> save workspace."""
    
    @pytest.fixture
    def sample_image(self):
        """Create a sample image simulating a PDF page."""
        img = np.zeros((400, 600, 3), dtype=np.uint8)
        # Add multiple regions for segmentation
        img[50:150, 50:150] = [100, 100, 100]  # Region 1
        img[200:300, 200:300] = [150, 150, 150]  # Region 2
        img[50:150, 400:500] = [200, 200, 200]  # Region 3
        return img
    
    def test_complete_workflow(self, sample_image):
        """Test complete workflow: create page -> segment -> save -> load."""
        # Step 1: Create page from "loaded PDF"
        page = PageTab(
            tab_id="workflow-page-1",
            model_name="WorkflowTest",
            page_name="Test Page",
            original_image=sample_image,
            source_path="/test/workflow.pdf",
            dpi=150.0,
            pdf_width_inches=11.0,
            pdf_height_inches=8.5,
        )
        
        # Step 2: Perform segmentation
        engine = SegmentationEngine()
        categories = create_default_categories()
        
        # Flood fill region 1
        mask1 = engine.flood_fill(sample_image, (100, 100))
        elem1 = SegmentElement(
            element_id="workflow-elem-1",
            category="R",
            mode="flood",
            points=[(100, 100)],
            mask=mask1,
            color=(220, 60, 60),
        )
        
        # Flood fill region 2
        mask2 = engine.flood_fill(sample_image, (250, 250))
        elem2 = SegmentElement(
            element_id="workflow-elem-2",
            category="F",
            mode="flood",
            points=[(250, 250)],
            mask=mask2,
            color=(200, 80, 80),
        )
        
        # Create instances and objects
        inst1 = ObjectInstance(
            instance_id="workflow-inst-1",
            instance_num=1,
            elements=[elem1],
            page_id="workflow-page-1",
        )
        
        inst2 = ObjectInstance(
            instance_id="workflow-inst-2",
            instance_num=1,
            elements=[elem2],
            page_id="workflow-page-1",
        )
        
        obj1 = SegmentedObject(
            object_id="workflow-obj-1",
            name="R1",
            category="R",
            instances=[inst1],
        )
        
        obj2 = SegmentedObject(
            object_id="workflow-obj-2",
            name="F1",
            category="F",
            instances=[inst2],
        )
        
        page.objects = [obj1, obj2]
        
        # Step 3: Save workspace
        workspace_manager = WorkspaceManager()
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace_path = Path(tmpdir) / "workflow_test.pmw"
            
            save_result = workspace_manager.save(
                str(workspace_path),
                [page],
                categories,
                objects=[obj1, obj2],
            )
            
            assert save_result is True
            assert workspace_path.exists()
            
            # Step 4: Load workspace
            loaded = workspace_manager.load(str(workspace_path))
            
            assert loaded is not None
            assert len(loaded.pages) == 1
            assert len(loaded.objects) == 2
            
            # Verify segmentation data is preserved
            loaded_page = loaded.pages[0]
            assert loaded_page.tab_id == "workflow-page-1"
            assert loaded_page.original_image is not None
            assert loaded_page.original_image.shape == sample_image.shape
            
            # Verify objects are preserved
            assert loaded.objects[0].object_id == "workflow-obj-1"
            assert loaded.objects[1].object_id == "workflow-obj-2"
            assert len(loaded.objects[0].instances[0].elements) == 1
            assert len(loaded.objects[1].instances[0].elements) == 1
            
            # Verify masks are preserved
            loaded_elem1 = loaded.objects[0].instances[0].elements[0]
            assert loaded_elem1.mask is not None
            assert loaded_elem1.mask.shape == mask1.shape
            assert np.array_equal(loaded_elem1.mask, mask1)
    
    def test_workflow_with_multiple_pages(self):
        """Test workflow with multiple pages."""
        # Create multiple pages
        img1 = np.zeros((200, 300, 3), dtype=np.uint8)
        img1[50:150, 50:150] = [100, 100, 100]
        
        img2 = np.zeros((200, 300, 3), dtype=np.uint8)
        img2[50:150, 50:150] = [200, 200, 200]
        
        page1 = PageTab(
            tab_id="multi-page-1",
            model_name="MultiPageTest",
            page_name="Page 1",
            original_image=img1,
            dpi=150.0,
        )
        
        page2 = PageTab(
            tab_id="multi-page-2",
            model_name="MultiPageTest",
            page_name="Page 2",
            original_image=img2,
            dpi=150.0,
        )
        
        # Create objects on different pages
        engine = SegmentationEngine()
        mask1 = engine.flood_fill(img1, (100, 100))
        elem1 = SegmentElement(
            element_id="multi-elem-1",
            category="R",
            mode="flood",
            points=[(100, 100)],
            mask=mask1,
        )
        
        mask2 = engine.flood_fill(img2, (100, 100))
        elem2 = SegmentElement(
            element_id="multi-elem-2",
            category="R",
            mode="flood",
            points=[(100, 100)],
            mask=mask2,
        )
        
        inst1 = ObjectInstance(
            instance_id="multi-inst-1",
            elements=[elem1],
            page_id="multi-page-1",
        )
        
        inst2 = ObjectInstance(
            instance_id="multi-inst-2",
            elements=[elem2],
            page_id="multi-page-2",
        )
        
        obj1 = SegmentedObject(
            object_id="multi-obj-1",
            name="R1",
            category="R",
            instances=[inst1, inst2],  # Same object on multiple pages
        )
        
        categories = create_default_categories()
        workspace_manager = WorkspaceManager()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace_path = Path(tmpdir) / "multi_page_test.pmw"
            
            workspace_manager.save(
                str(workspace_path),
                [page1, page2],
                categories,
                objects=[obj1],
            )
            
            loaded = workspace_manager.load(str(workspace_path))
            
            assert loaded is not None
            assert len(loaded.pages) == 2
            assert len(loaded.objects) == 1
            assert len(loaded.objects[0].instances) == 2  # Two instances on different pages
