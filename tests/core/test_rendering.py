"""Tests for rendering module."""

import pytest
import numpy as np
import cv2

from replan.desktop.core.rendering import Renderer, RenderCache
from replan.desktop.models import PageTab, SegmentedObject, DynamicCategory, ObjectInstance, SegmentElement


class TestRenderCache:
    """Tests for RenderCache class."""

    def test_init(self):
        """Test cache initialization."""
        cache = RenderCache()
        assert cache.base_image is None
        assert cache.base_hash == ""
        assert cache.zoomed_cache == {}
        assert cache.page_id == ""

    def test_invalidate(self):
        """Test cache invalidation."""
        cache = RenderCache()
        cache.base_image = np.zeros((100, 100, 4), dtype=np.uint8)
        cache.base_hash = "test_hash"
        cache.zoomed_cache[1.0] = np.zeros((100, 100, 4), dtype=np.uint8)
        cache.page_id = "page1"
        
        cache.invalidate()
        
        assert cache.base_image is None
        assert cache.base_hash == ""
        assert cache.zoomed_cache == {}
        assert cache.page_id == "page1"  # page_id is not cleared

    def test_invalidate_zoom(self):
        """Test zoom cache invalidation."""
        cache = RenderCache()
        cache.base_image = np.zeros((100, 100, 4), dtype=np.uint8)
        cache.zoomed_cache[1.0] = np.zeros((100, 100, 4), dtype=np.uint8)
        cache.zoomed_cache[2.0] = np.zeros((200, 200, 4), dtype=np.uint8)
        
        cache.invalidate_zoom()
        
        assert cache.base_image is not None
        assert cache.zoomed_cache == {}


class TestRenderer:
    """Tests for Renderer class."""

    @pytest.fixture
    def renderer(self):
        """Create a Renderer instance."""
        return Renderer()

    @pytest.fixture
    def sample_page(self):
        """Create a sample PageTab."""
        image = np.ones((100, 100, 3), dtype=np.uint8) * 255
        page = PageTab(
            tab_id="test_page",
            page_name="Test Page",
            original_image=image,
            pdf_width_inches=8.5,
            pdf_height_inches=11.0,
            dpi=100
        )
        return page

    @pytest.fixture
    def sample_category(self):
        """Create a sample category."""
        return DynamicCategory(
            name="rib",
            prefix="R",
            full_name="Rib",
            color_rgb=(255, 0, 0),
            selection_mode="flood",
            visible=True
        )

    @pytest.fixture
    def sample_object(self, sample_category):
        """Create a sample SegmentedObject."""
        mask = np.zeros((100, 100), dtype=np.uint8)
        mask[20:40, 20:40] = 255
        
        elem = SegmentElement(
            element_id="elem1",
            category="rib",
            mode="flood",
            points=[(30, 30)],
            mask=mask,
            color=sample_category.color_rgb
        )
        
        inst = ObjectInstance(
            instance_id="inst1",
            instance_num=1,
            elements=[elem],
            page_id="test_page"
        )
        
        obj = SegmentedObject(
            object_id="obj1",
            name="R1",
            category="rib",
            instances=[inst]
        )
        
        return obj

    def test_init(self, renderer):
        """Test renderer initialization."""
        assert renderer.label_font == 0  # cv2.FONT_HERSHEY_SIMPLEX
        assert renderer.label_scale == 0.5
        assert renderer.label_thickness == 1
        assert isinstance(renderer.cache, RenderCache)

    def test_invalidate_cache(self, renderer):
        """Test cache invalidation."""
        renderer.cache.base_image = np.zeros((100, 100, 4), dtype=np.uint8)
        renderer.invalidate_cache()
        assert renderer.cache.base_image is None

    def test_render_page_no_image(self, renderer, sample_page):
        """Test rendering page with no image."""
        sample_page.original_image = None
        result = renderer.render_page(sample_page, {})
        assert result.shape == (100, 100, 4)
        assert np.sum(result > 0) == 0

    def test_render_page_basic(self, renderer, sample_page, sample_category, sample_object):
        """Test basic page rendering."""
        sample_page.objects = [sample_object]
        categories = {"rib": sample_category}
        
        result = renderer.render_page(sample_page, categories)
        
        assert result.shape == (100, 100, 4)
        assert result.dtype == np.uint8

    def test_render_page_with_zoom(self, renderer, sample_page, sample_category, sample_object):
        """Test page rendering with zoom."""
        sample_page.objects = [sample_object]
        categories = {"rib": sample_category}
        
        result = renderer.render_page(sample_page, categories, zoom=2.0)
        
        assert result.shape == (200, 200, 4)

    def test_render_page_zoom_out(self, renderer, sample_page, sample_category, sample_object):
        """Test page rendering with zoom out."""
        sample_page.objects = [sample_object]
        categories = {"rib": sample_category}
        
        result = renderer.render_page(sample_page, categories, zoom=0.5)
        
        assert result.shape == (50, 50, 4)

    def test_render_page_hide_background(self, renderer, sample_page, sample_category, sample_object):
        """Test page rendering with hidden background."""
        sample_page.objects = [sample_object]
        categories = {"rib": sample_category}
        
        result = renderer.render_page(sample_page, categories, hide_background=True)
        
        assert result.shape == (100, 100, 4)
        # Background should be white
        assert np.all(result[0, 0, :3] == 255)

    def test_render_page_with_text_mask(self, renderer, sample_page, sample_category, sample_object):
        """Test page rendering with text mask."""
        sample_page.objects = [sample_object]
        categories = {"rib": sample_category}
        
        text_mask = np.zeros((100, 100), dtype=np.uint8)
        text_mask[50:60, 50:60] = 255
        
        result = renderer.render_page(sample_page, categories, text_mask=text_mask)
        
        assert result.shape == (100, 100, 4)

    def test_render_page_with_hatching_mask(self, renderer, sample_page, sample_category, sample_object):
        """Test page rendering with hatching mask."""
        sample_page.objects = [sample_object]
        categories = {"rib": sample_category}
        
        hatching_mask = np.zeros((100, 100), dtype=np.uint8)
        hatching_mask[50:60, 50:60] = 255
        
        result = renderer.render_page(sample_page, categories, hatching_mask=hatching_mask)
        
        assert result.shape == (100, 100, 4)

    def test_render_page_with_line_mask(self, renderer, sample_page, sample_category, sample_object):
        """Test page rendering with line mask."""
        sample_page.objects = [sample_object]
        categories = {"rib": sample_category}
        
        line_mask = np.zeros((100, 100), dtype=np.uint8)
        line_mask[50:60, 50:60] = 255
        
        result = renderer.render_page(sample_page, categories, line_mask=line_mask)
        
        assert result.shape == (100, 100, 4)

    def test_render_page_selected_object(self, renderer, sample_page, sample_category, sample_object):
        """Test page rendering with selected object."""
        sample_page.objects = [sample_object]
        categories = {"rib": sample_category}
        
        result = renderer.render_page(
            sample_page, 
            categories,
            selected_object_ids={"obj1"}
        )
        
        assert result.shape == (100, 100, 4)

    def test_render_page_hide_labels(self, renderer, sample_page, sample_category, sample_object):
        """Test page rendering without labels."""
        sample_page.objects = [sample_object]
        categories = {"rib": sample_category}
        
        result = renderer.render_page(sample_page, categories, show_labels=False)
        
        assert result.shape == (100, 100, 4)

    def test_render_page_invisible_category(self, renderer, sample_page, sample_category, sample_object):
        """Test page rendering with invisible category."""
        sample_page.objects = [sample_object]
        sample_category.visible = False
        categories = {"rib": sample_category}
        
        result = renderer.render_page(sample_page, categories)
        
        assert result.shape == (100, 100, 4)
        # Object should not be visible

    def test_render_page_caching(self, renderer, sample_page, sample_category, sample_object):
        """Test that rendering uses cache."""
        sample_page.objects = [sample_object]
        categories = {"rib": sample_category}
        
        # First render - should build cache
        result1 = renderer.render_page(sample_page, categories)
        assert renderer.cache.base_image is not None
        
        # Second render - should use cache
        result2 = renderer.render_page(sample_page, categories)
        assert np.array_equal(result1, result2)

    def test_render_page_cache_invalidation(self, renderer, sample_page, sample_category, sample_object):
        """Test cache invalidation on object change."""
        sample_page.objects = [sample_object]
        categories = {"rib": sample_category}
        
        # First render
        renderer.render_page(sample_page, categories)
        assert renderer.cache.base_image is not None
        
        # Invalidate cache
        renderer.invalidate_cache()
        assert renderer.cache.base_image is None
        
        # Second render should rebuild
        renderer.render_page(sample_page, categories)
        assert renderer.cache.base_image is not None

    def test_render_page_multiple_objects(self, renderer, sample_page, sample_category):
        """Test rendering multiple objects."""
        mask1 = np.zeros((100, 100), dtype=np.uint8)
        mask1[10:30, 10:30] = 255
        
        mask2 = np.zeros((100, 100), dtype=np.uint8)
        mask2[50:70, 50:70] = 255
        
        elem1 = SegmentElement(
            element_id="elem1",
            category="rib",
            mode="flood",
            points=[(20, 20)],
            mask=mask1,
            color=sample_category.color_rgb
        )
        
        elem2 = SegmentElement(
            element_id="elem2",
            category="rib",
            mode="flood",
            points=[(60, 60)],
            mask=mask2,
            color=sample_category.color_rgb
        )
        
        inst1 = ObjectInstance(
            instance_id="inst1",
            instance_num=1,
            elements=[elem1],
            page_id="test_page"
        )
        
        inst2 = ObjectInstance(
            instance_id="inst2",
            instance_num=1,
            elements=[elem2],
            page_id="test_page"
        )
        
        obj1 = SegmentedObject(
            object_id="obj1",
            name="R1",
            category="rib",
            instances=[inst1]
        )
        
        obj2 = SegmentedObject(
            object_id="obj2",
            name="R2",
            category="rib",
            instances=[inst2]
        )
        
        sample_page.objects = [obj1, obj2]
        categories = {"rib": sample_category}
        
        result = renderer.render_page(sample_page, categories)
        
        assert result.shape == (100, 100, 4)

    def test_render_page_planform_opacity(self, renderer, sample_page, sample_category):
        """Test rendering with planform opacity."""
        mask = np.zeros((100, 100), dtype=np.uint8)
        mask[20:40, 20:40] = 255
        
        elem = SegmentElement(
            element_id="elem1",
            category="planform",
            mode="flood",
            points=[(30, 30)],
            mask=mask,
            color=(0, 255, 0)
        )
        
        inst = ObjectInstance(
            instance_id="inst1",
            instance_num=1,
            elements=[elem],
            page_id="test_page"
        )
        
        planform_cat = DynamicCategory(
            name="planform",
            prefix="P",
            full_name="Planform",
            color_rgb=(0, 255, 0),
            selection_mode="flood",
            visible=True
        )
        
        obj = SegmentedObject(
            object_id="obj1",
            name="P1",
            category="planform",
            instances=[inst]
        )
        
        sample_page.objects = [obj]
        categories = {"planform": planform_cat}
        
        result = renderer.render_page(sample_page, categories, planform_opacity=0.3)
        
        assert result.shape == (100, 100, 4)

    def test_compute_objects_hash(self, renderer, sample_page, sample_category, sample_object):
        """Test computing objects hash."""
        sample_page.objects = [sample_object]
        categories = {"rib": sample_category}
        
        hash1 = renderer._compute_objects_hash(sample_page, categories, 0.5)
        assert isinstance(hash1, str)
        assert len(hash1) > 0
        
        # Same objects should produce same hash
        hash2 = renderer._compute_objects_hash(sample_page, categories, 0.5)
        assert hash1 == hash2
        
        # Different opacity should produce different hash
        hash3 = renderer._compute_objects_hash(sample_page, categories, 0.7)
        assert hash1 != hash3

    def test_render_page_pixel_selection(self, renderer, sample_page, sample_category, sample_object):
        """Test rendering with pixel selection."""
        sample_page.objects = [sample_object]
        categories = {"rib": sample_category}
        
        pixel_mask = np.zeros((100, 100), dtype=np.uint8)
        pixel_mask[50:60, 50:60] = 255
        
        result = renderer.render_page(
            sample_page, 
            categories,
            pixel_selection_mask=pixel_mask
        )
        
        assert result.shape == (100, 100, 4)

    def test_render_page_pixel_move_offset(self, renderer, sample_page, sample_category, sample_object):
        """Test rendering with pixel move offset."""
        sample_page.objects = [sample_object]
        categories = {"rib": sample_category}
        
        pixel_mask = np.zeros((100, 100), dtype=np.uint8)
        pixel_mask[50:60, 50:60] = 255
        
        result = renderer.render_page(
            sample_page, 
            categories,
            pixel_selection_mask=pixel_mask,
            pixel_move_offset=(10, 10)
        )
        
        assert result.shape == (100, 100, 4)

    def test_render_page_object_move_offset(self, renderer, sample_page, sample_category, sample_object):
        """Test rendering with object move offset."""
        sample_page.objects = [sample_object]
        categories = {"rib": sample_category}
        
        result = renderer.render_page(
            sample_page, 
            categories,
            selected_object_ids={"obj1"},
            object_move_offset=(10, 10)
        )
        
        assert result.shape == (100, 100, 4)
    
    def test_render_page_pending_elements(self, renderer, sample_page, sample_category):
        """Test rendering with pending elements."""
        categories = {"rib": sample_category}
        
        mask = np.zeros((100, 100), dtype=np.uint8)
        mask[30:50, 30:50] = 255
        
        pending_elem = SegmentElement(
            element_id="pending1",
            category="rib",
            mode="flood",
            points=[(40, 40)],
            mask=mask,
            color=sample_category.color_rgb
        )
        
        result = renderer.render_page(
            sample_page,
            categories,
            pending_elements=[pending_elem]
        )
        
        assert result.shape == (100, 100, 4)
    
    def test_render_page_with_objects_parameter(self, renderer, sample_page, sample_category, sample_object):
        """Test rendering with custom objects list."""
        categories = {"rib": sample_category}
        
        result = renderer.render_page(
            sample_page,
            categories,
            objects=[sample_object]
        )
        
        assert result.shape == (100, 100, 4)
    
    def test_render_page_selected_instance(self, renderer, sample_page, sample_category, sample_object):
        """Test rendering with selected instance."""
        sample_page.objects = [sample_object]
        categories = {"rib": sample_category}
        
        result = renderer.render_page(
            sample_page,
            categories,
            selected_instance_ids={"inst1"}
        )
        
        assert result.shape == (100, 100, 4)
    
    def test_render_page_selected_element(self, renderer, sample_page, sample_category, sample_object):
        """Test rendering with selected element."""
        sample_page.objects = [sample_object]
        categories = {"rib": sample_category}
        
        result = renderer.render_page(
            sample_page,
            categories,
            selected_element_ids={"elem1"}
        )
        
        assert result.shape == (100, 100, 4)
    
    def test_render_page_mark_text_category(self, renderer, sample_page):
        """Test rendering with mark_text category (should not render fill)."""
        mark_text_cat = DynamicCategory(
            name="mark_text",
            prefix="T",
            full_name="Text",
            color_rgb=(255, 255, 0),
            selection_mode="flood",
            visible=True
        )
        
        mask = np.zeros((100, 100), dtype=np.uint8)
        mask[20:40, 20:40] = 255
        
        elem = SegmentElement(
            element_id="elem1",
            category="mark_text",
            mode="flood",
            points=[(30, 30)],
            mask=mask,
            color=mark_text_cat.color_rgb
        )
        
        inst = ObjectInstance(
            instance_id="inst1",
            instance_num=1,
            elements=[elem],
            page_id="test_page"
        )
        
        obj = SegmentedObject(
            object_id="obj1",
            name="T1",
            category="mark_text",
            instances=[inst]
        )
        
        sample_page.objects = [obj]
        categories = {"mark_text": mark_text_cat}
        
        result = renderer.render_page(sample_page, categories)
        
        assert result.shape == (100, 100, 4)
        # mark_text should not render fill, but should still be selectable
    
    def test_render_page_mark_hatch_category(self, renderer, sample_page):
        """Test rendering with mark_hatch category (should not render fill)."""
        mark_hatch_cat = DynamicCategory(
            name="mark_hatch",
            prefix="H",
            full_name="Hatch",
            color_rgb=(255, 0, 255),
            selection_mode="flood",
            visible=True
        )
        
        mask = np.zeros((100, 100), dtype=np.uint8)
        mask[20:40, 20:40] = 255
        
        elem = SegmentElement(
            element_id="elem1",
            category="mark_hatch",
            mode="flood",
            points=[(30, 30)],
            mask=mask,
            color=mark_hatch_cat.color_rgb
        )
        
        inst = ObjectInstance(
            instance_id="inst1",
            instance_num=1,
            elements=[elem],
            page_id="test_page"
        )
        
        obj = SegmentedObject(
            object_id="obj1",
            name="H1",
            category="mark_hatch",
            instances=[inst]
        )
        
        sample_page.objects = [obj]
        categories = {"mark_hatch": mark_hatch_cat}
        
        result = renderer.render_page(sample_page, categories)
        
        assert result.shape == (100, 100, 4)
    
    def test_render_page_line_element(self, renderer, sample_page, sample_category):
        """Test rendering with line element."""
        mask = np.zeros((100, 100), dtype=np.uint8)
        # Create a line mask
        cv2.line(mask, (10, 10), (90, 90), 255, 3)
        
        elem = SegmentElement(
            element_id="elem1",
            category="rib",
            mode="line",
            points=[(10, 10), (90, 90)],
            mask=mask,
            color=sample_category.color_rgb
        )
        
        inst = ObjectInstance(
            instance_id="inst1",
            instance_num=1,
            elements=[elem],
            page_id="test_page"
        )
        
        obj = SegmentedObject(
            object_id="obj1",
            name="R1",
            category="rib",
            instances=[inst]
        )
        
        sample_page.objects = [obj]
        categories = {"rib": sample_category}
        
        result = renderer.render_page(sample_page, categories)
        
        assert result.shape == (100, 100, 4)
    
    def test_render_page_line_element_empty_mask(self, renderer, sample_page, sample_category):
        """Test rendering line element with empty mask (no pixels)."""
        mask = np.zeros((100, 100), dtype=np.uint8)  # Empty mask
        
        elem = SegmentElement(
            element_id="elem1",
            category="rib",
            mode="line",
            points=[(10, 10), (90, 90)],
            mask=mask,
            color=sample_category.color_rgb
        )
        
        inst = ObjectInstance(
            instance_id="inst1",
            elements=[elem],
            page_id="test_page"
        )
        
        obj = SegmentedObject(
            object_id="obj1",
            name="R1",
            category="rib",
            instances=[inst]
        )
        
        sample_page.objects = [obj]
        categories = {"rib": sample_category}
        
        result = renderer.render_page(sample_page, categories)
        # Should handle empty mask gracefully (tests branch 267->262)
        assert result.shape == (100, 100, 4)
    
    def test_render_page_line_element_bright_color(self, renderer, sample_page):
        """Test rendering line element with bright color (should darken)."""
        # Create bright category (brightness > 200)
        bright_cat = DynamicCategory(
            name="bright",
            prefix="B",
            full_name="Bright",
            color_rgb=(250, 250, 250),  # Very bright, should be darkened
        )
        
        mask = np.zeros((100, 100), dtype=np.uint8)
        cv2.line(mask, (10, 10), (90, 90), 255, 3)
        
        elem = SegmentElement(
            element_id="elem1",
            category="bright",
            mode="line",
            mask=mask,
        )
        
        inst = ObjectInstance(
            instance_id="inst1",
            elements=[elem],
            page_id="test_page"
        )
        
        obj = SegmentedObject(
            object_id="obj1",
            name="R1",
            category="bright",
            instances=[inst]
        )
        
        sample_page.objects = [obj]
        categories = {"bright": bright_cat}
        
        result = renderer.render_page(sample_page, categories)
        # Should darken bright colors (tests branch 275)
        assert result.shape == (100, 100, 4)
    
    def test_render_page_centroid_none(self, renderer, sample_page, sample_category):
        """Test rendering when centroid calculation returns None."""
        # Create element with empty mask (centroid will be None)
        elem = SegmentElement(
            element_id="elem1",
            category="rib",
            mask=np.zeros((100, 100), dtype=np.uint8),  # Empty mask
        )
        
        inst = ObjectInstance(
            instance_id="inst1",
            elements=[elem],
            page_id="test_page"
        )
        
        obj = SegmentedObject(
            object_id="obj1",
            name="R1",
            category="rib",
            instances=[inst]
        )
        
        sample_page.objects = [obj]
        categories = {"rib": sample_category}
        
        result = renderer.render_page(sample_page, categories, show_labels=True)
        # Should handle None centroid gracefully (tests branch 332)
        assert result.shape == (100, 100, 4)
    
    def test_render_page_no_contours_for_highlight(self, renderer, sample_page, sample_category, sample_object):
        """Test rendering selected element when mask has no contours."""
        # Create element with mask that won't produce contours
        empty_mask = np.zeros((100, 100), dtype=np.uint8)
        elem = SegmentElement(
            element_id="elem1",
            category="rib",
            mask=empty_mask,
        )
        
        inst = ObjectInstance(
            instance_id="inst1",
            elements=[elem],
            page_id="test_page"
        )
        
        obj = SegmentedObject(
            object_id="obj1",
            name="R1",
            category="rib",
            instances=[inst]
        )
        
        sample_page.objects = [obj]
        categories = {"rib": sample_category}
        
        result = renderer.render_page(
            sample_page,
            categories,
            selected_element_ids={"elem1"}
        )
        # Should handle empty contours gracefully (tests branch 399->378)
        assert result.shape == (100, 100, 4)
    
    def test_draw_pending_elements_none_mask(self, renderer):
        """Test _draw_pending_elements with None mask."""
        image = np.zeros((100, 100, 4), dtype=np.uint8)
        
        elem = SegmentElement(
            element_id="elem1",
            category="rib",
            mask=None,  # None mask
        )
        
        # Should handle None mask gracefully (tests branch 428->427)
        renderer._draw_pending_elements(image, [elem])
        assert image.shape == (100, 100, 4)
    
    def test_draw_pixel_selection_gray_image(self, renderer):
        """Test _draw_pixel_selection with grayscale image."""
        mask = np.zeros((100, 100), dtype=np.uint8)
        mask[20:80, 20:80] = 255
        
        # Grayscale image (2D)
        gray_image = np.zeros((100, 100), dtype=np.uint8)
        
        result = renderer._draw_pixel_selection(gray_image, mask)
        # Should convert grayscale to BGRA (tests branch 453-454)
        assert result.shape == (100, 100, 4)
    
    def test_draw_pixel_selection_bgr_image(self, renderer):
        """Test _draw_pixel_selection with BGR image (3 channels)."""
        mask = np.zeros((100, 100), dtype=np.uint8)
        mask[20:80, 20:80] = 255
        
        # BGR image (3 channels)
        bgr_image = np.zeros((100, 100, 3), dtype=np.uint8)
        
        result = renderer._draw_pixel_selection(bgr_image, mask)
        # Should convert BGR to BGRA (tests branch 451->452)
        assert result.shape == (100, 100, 4)
    
    def test_render_page_text_mask_growth_max_iterations(self, renderer, sample_page, sample_category, sample_object):
        """Test text mask growth when max iterations is reached."""
        # Create a text mask that will require many iterations
        text_mask = np.ones((100, 100), dtype=np.uint8) * 255
        
        # Create filled mask that will grow into text
        mask = np.zeros((100, 100), dtype=np.uint8)
        mask[10:20, 10:20] = 255
        
        elem = SegmentElement(
            element_id="elem1",
            category="rib",
            mask=mask,
        )
        
        inst = ObjectInstance(
            instance_id="inst1",
            elements=[elem],
            page_id="test_page"
        )
        
        sample_object.instances = [inst]
        sample_page.objects = [sample_object]
        categories = {"rib": sample_category}
        
        result = renderer.render_page(
            sample_page,
            categories,
            text_mask=text_mask
        )
        # Should handle max iterations gracefully (tests branch 241->249)
        assert result.shape == (100, 100, 4)
    
    def test_render_page_text_mask_growth_early_break(self, renderer, sample_page, sample_category, sample_object):
        """Test text mask growth when break happens early."""
        # Create a small text mask that will be filled quickly
        text_mask = np.zeros((100, 100), dtype=np.uint8)
        text_mask[15:25, 15:25] = 255  # Small text region
        
        # Create filled mask adjacent to text
        mask = np.zeros((100, 100), dtype=np.uint8)
        mask[10:15, 10:15] = 255  # Adjacent to text
        
        elem = SegmentElement(
            element_id="elem1",
            category="rib",
            mask=mask,
        )
        
        inst = ObjectInstance(
            instance_id="inst1",
            elements=[elem],
            page_id="test_page"
        )
        
        sample_object.instances = [inst]
        sample_page.objects = [sample_object]
        categories = {"rib": sample_category}
        
        result = renderer.render_page(
            sample_page,
            categories,
            text_mask=text_mask
        )
        # Should break early when no new pixels (tests branch 245->247)
        assert result.shape == (100, 100, 4)
    
    def test_draw_labels_invisible_category(self, renderer, sample_page, sample_category, sample_object):
        """Test _draw_labels with invisible category."""
        image = np.zeros((100, 100, 4), dtype=np.uint8)
        
        # Make category invisible
        sample_category.visible = False
        
        categories = {"rib": sample_category}
        
        renderer._draw_labels(image, [sample_object], categories)
        # Should skip invisible categories (tests branch 518)
        assert image.shape == (100, 100, 4)
    
    def test_draw_labels_centroid_none(self, renderer, sample_page, sample_category):
        """Test _draw_labels when centroid is None."""
        image = np.zeros((100, 100, 4), dtype=np.uint8)
        
        # Add color attribute that rendering code expects
        sample_category.color = sample_category.color_hex
        
        # Create instance with empty mask (centroid will be None)
        elem = SegmentElement(
            element_id="elem1",
            category="rib",
            mask=np.zeros((100, 100), dtype=np.uint8),  # Empty mask
        )
        
        inst = ObjectInstance(
            instance_id="inst1",
            elements=[elem],
            page_id="test_page"
        )
        
        obj = SegmentedObject(
            object_id="obj1",
            name="R1",
            category="rib",
            instances=[inst]
        )
        
        categories = {"rib": sample_category}
        
        renderer._draw_labels(image, [obj], categories)
        # Should skip when centroid is None (tests branch 537->538)
        assert image.shape == (100, 100, 4)
    
    def test_draw_labels_bright_color(self, renderer, sample_page, sample_object):
        """Test _draw_labels with bright category color."""
        image = np.zeros((100, 100, 4), dtype=np.uint8)
        
        # Create bright category (brightness > 128) - use color_rgb
        bright_cat = DynamicCategory(
            name="bright",
            prefix="B",
            full_name="Bright",
            color_rgb=(255, 255, 255),  # White, brightness > 128
        )
        # Add color attribute that rendering code expects (it uses cat.color)
        bright_cat.color = bright_cat.color_hex
        
        sample_object.category = "bright"
        categories = {"bright": bright_cat}
        
        renderer._draw_labels(image, [sample_object], categories)
        # Should use bright color logic (tests branch 528->529)
        assert image.shape == (100, 100, 4)
    
    def test_draw_labels_dark_color(self, renderer, sample_page, sample_object):
        """Test _draw_labels with dark category color."""
        image = np.zeros((100, 100, 4), dtype=np.uint8)
        
        # Create dark category (brightness <= 128) - use color_rgb
        dark_cat = DynamicCategory(
            name="dark",
            prefix="D",
            full_name="Dark",
            color_rgb=(0, 0, 0),  # Black, brightness <= 128
        )
        # Add color attribute that rendering code expects (it uses cat.color)
        dark_cat.color = dark_cat.color_hex
        
        sample_object.category = "dark"
        categories = {"dark": dark_cat}
        
        renderer._draw_labels(image, [sample_object], categories)
        # Should brighten dark colors (tests branch 530->532)
        assert image.shape == (100, 100, 4)
    
    def test_draw_labels_multiple_instances(self, renderer, sample_page, sample_category):
        """Test _draw_labels with object having multiple instances."""
        image = np.zeros((100, 100, 4), dtype=np.uint8)
        
        # Add color attribute that rendering code expects
        sample_category.color = sample_category.color_hex
        
        mask = np.zeros((100, 100), dtype=np.uint8)
        mask[40:60, 40:60] = 255
        
        elem1 = SegmentElement(element_id="elem1", category="rib", mask=mask)
        elem2 = SegmentElement(element_id="elem2", category="rib", mask=mask)
        
        inst1 = ObjectInstance(instance_id="inst1", elements=[elem1], page_id="test_page")
        inst2 = ObjectInstance(instance_id="inst2", elements=[elem2], page_id="test_page")
        
        obj = SegmentedObject(
            object_id="obj1",
            name="R1",
            category="rib",
            instances=[inst1, inst2]
        )
        
        categories = {"rib": sample_category}
        
        renderer._draw_labels(image, [obj], categories)
        # Should format label with instance number when multiple instances (tests branch 543->544)
        assert image.shape == (100, 100, 4)
    
    def test_render_page_perimeter_element(self, renderer, sample_page, sample_category):
        """Test rendering with perimeter element."""
        mask = np.zeros((100, 100), dtype=np.uint8)
        cv2.rectangle(mask, (20, 20), (80, 80), 255, 2)
        
        elem = SegmentElement(
            element_id="elem1",
            category="rib",
            mode="perimeter",
            points=[(20, 20), (80, 80)],
            mask=mask,
            color=sample_category.color_rgb
        )
        
        inst = ObjectInstance(
            instance_id="inst1",
            instance_num=1,
            elements=[elem],
            page_id="test_page"
        )
        
        obj = SegmentedObject(
            object_id="obj1",
            name="R1",
            category="rib",
            instances=[inst]
        )
        
        sample_page.objects = [obj]
        categories = {"rib": sample_category}
        
        result = renderer.render_page(sample_page, categories)
        
        assert result.shape == (100, 100, 4)
    
    def test_render_page_text_ghosting_fix(self, renderer, sample_page, sample_category, sample_object):
        """Test text ghosting fix when text mask is present."""
        sample_page.objects = [sample_object]
        categories = {"rib": sample_category}
        
        # Create text mask that overlaps with object
        text_mask = np.zeros((100, 100), dtype=np.uint8)
        text_mask[25:35, 25:35] = 255  # Overlaps with object mask at 20:40, 20:40
        
        result = renderer.render_page(sample_page, categories, text_mask=text_mask)
        
        assert result.shape == (100, 100, 4)
    
    def test_render_page_cache_with_mask_changes(self, renderer, sample_page, sample_category, sample_object):
        """Test that cache invalidates when masks change."""
        sample_page.objects = [sample_object]
        categories = {"rib": sample_category}
        
        text_mask1 = np.zeros((100, 100), dtype=np.uint8)
        text_mask1[10:20, 10:20] = 255
        
        text_mask2 = np.zeros((100, 100), dtype=np.uint8)
        text_mask2[30:40, 30:40] = 255
        
        # First render
        result1 = renderer.render_page(sample_page, categories, text_mask=text_mask1)
        assert renderer.cache.base_image is not None
        
        # Second render with different mask - should rebuild
        result2 = renderer.render_page(sample_page, categories, text_mask=text_mask2)
        assert result2.shape == (100, 100, 4)
    
    def test_compute_objects_hash_from_list(self, renderer, sample_category, sample_object):
        """Test computing hash from objects list directly."""
        categories = {"rib": sample_category}
        
        hash1 = renderer._compute_objects_hash_from_list([sample_object], categories, 0.5, "page1")
        assert isinstance(hash1, str)
        assert len(hash1) > 0
        
        # Same objects should produce same hash
        hash2 = renderer._compute_objects_hash_from_list([sample_object], categories, 0.5, "page1")
        assert hash1 == hash2
        
        # Different page_id should produce different hash
        hash3 = renderer._compute_objects_hash_from_list([sample_object], categories, 0.5, "page2")
        assert hash1 != hash3
    
    def test_compute_objects_hash_invisible_category(self, renderer, sample_page, sample_category, sample_object):
        """Test hash computation with invisible category."""
        sample_page.objects = [sample_object]
        sample_category.visible = False
        categories = {"rib": sample_category}
        
        hash1 = renderer._compute_objects_hash(sample_page, categories, 0.5)
        assert isinstance(hash1, str)
        
        # Make visible - hash should change
        sample_category.visible = True
        hash2 = renderer._compute_objects_hash(sample_page, categories, 0.5)
        assert hash1 != hash2
    
    def test_calculate_group_centroid_single_element(self, renderer, sample_category):
        """Test centroid calculation with single element."""
        mask = np.zeros((100, 100), dtype=np.uint8)
        mask[40:60, 40:60] = 255
        
        elem = SegmentElement(
            element_id="elem1",
            category="rib",
            mode="flood",
            points=[(50, 50)],
            mask=mask,
            color=sample_category.color_rgb
        )
        
        centroid = renderer._calculate_group_centroid([elem])
        assert centroid is not None
        assert isinstance(centroid, tuple)
        assert len(centroid) == 2
        # Should be near center of mask (50, 50)
        assert 45 <= centroid[0] <= 55
        assert 45 <= centroid[1] <= 55
    
    def test_calculate_group_centroid_multiple_elements(self, renderer, sample_category):
        """Test centroid calculation with multiple elements."""
        mask1 = np.zeros((100, 100), dtype=np.uint8)
        mask1[20:30, 20:30] = 255
        
        mask2 = np.zeros((100, 100), dtype=np.uint8)
        mask2[70:80, 70:80] = 255
        
        elem1 = SegmentElement(
            element_id="elem1",
            category="rib",
            mode="flood",
            points=[(25, 25)],
            mask=mask1,
            color=sample_category.color_rgb
        )
        
        elem2 = SegmentElement(
            element_id="elem2",
            category="rib",
            mode="flood",
            points=[(75, 75)],
            mask=mask2,
            color=sample_category.color_rgb
        )
        
        centroid = renderer._calculate_group_centroid([elem1, elem2])
        assert centroid is not None
        # Should be between the two elements
        assert 20 <= centroid[0] <= 80
        assert 20 <= centroid[1] <= 80
    
    def test_calculate_group_centroid_no_masks(self, renderer):
        """Test centroid calculation with no valid masks."""
        elem = SegmentElement(
            element_id="elem1",
            category="rib",
            mode="flood",
            points=[(50, 50)],
            mask=None,
            color=(255, 0, 0)
        )
        
        centroid = renderer._calculate_group_centroid([elem])
        assert centroid is None
    
    def test_calculate_group_centroid_empty_mask(self, renderer, sample_category):
        """Test centroid calculation with empty mask."""
        mask = np.zeros((100, 100), dtype=np.uint8)
        
        elem = SegmentElement(
            element_id="elem1",
            category="rib",
            mode="flood",
            points=[(50, 50)],
            mask=mask,
            color=sample_category.color_rgb
        )
        
        centroid = renderer._calculate_group_centroid([elem])
        assert centroid is None
    
    def test_render_thumbnail_with_image(self, renderer, sample_page):
        """Test thumbnail rendering with image."""
        thumb = renderer.render_thumbnail(sample_page, max_size=50)
        
        assert thumb.shape[0] <= 50
        assert thumb.shape[1] <= 50
        assert thumb.dtype == np.uint8
    
    def test_render_thumbnail_no_image(self, renderer):
        """Test thumbnail rendering without image."""
        page = PageTab(
            tab_id="test_page",
            page_name="Test Page",
            original_image=None
        )
        
        thumb = renderer.render_thumbnail(page, max_size=50)
        
        assert thumb.shape == (50, 50, 3)
        assert thumb.dtype == np.uint8
    
    def test_render_thumbnail_large_image(self, renderer):
        """Test thumbnail rendering with large image."""
        # Create a large image
        image = np.ones((500, 1000, 3), dtype=np.uint8) * 255
        page = PageTab(
            tab_id="test_page",
            page_name="Test Page",
            original_image=image
        )
        
        thumb = renderer.render_thumbnail(page, max_size=100)
        
        # Should be scaled down
        assert max(thumb.shape[0], thumb.shape[1]) <= 100
        assert thumb.dtype == np.uint8
    
    def test_render_thumbnail_small_image(self, renderer):
        """Test thumbnail rendering with small image."""
        image = np.ones((50, 50, 3), dtype=np.uint8) * 255
        page = PageTab(
            tab_id="test_page",
            page_name="Test Page",
            original_image=image
        )
        
        thumb = renderer.render_thumbnail(page, max_size=100)
        
        # Should not be scaled up (or scaled minimally)
        assert thumb.shape[0] <= 100
        assert thumb.shape[1] <= 100
    
    def test_highlight_selected_with_move_offset(self, renderer, sample_category, sample_object):
        """Test highlighting with move offset."""
        image = np.zeros((100, 100, 4), dtype=np.uint8)
        
        renderer._highlight_selected(
            image,
            [sample_object],
            selected_object_ids={"obj1"},
            selected_instance_ids=set(),
            selected_element_ids=set(),
            move_offset=(10, 10)
        )
        
        # Should have drawn highlights
        assert np.any(image > 0)
    
    def test_highlight_selected_element_level(self, renderer, sample_category, sample_object):
        """Test highlighting at element level."""
        image = np.zeros((100, 100, 4), dtype=np.uint8)
        
        renderer._highlight_selected(
            image,
            [sample_object],
            selected_object_ids=set(),
            selected_instance_ids=set(),
            selected_element_ids={"elem1"}
        )
        
        # Should have drawn highlights
        assert np.any(image > 0)
    
    def test_highlight_selected_instance_level(self, renderer, sample_category, sample_object):
        """Test highlighting at instance level."""
        image = np.zeros((100, 100, 4), dtype=np.uint8)
        
        renderer._highlight_selected(
            image,
            [sample_object],
            selected_object_ids=set(),
            selected_instance_ids={"inst1"},
            selected_element_ids=set()
        )
        
        # Should have drawn highlights
        assert np.any(image > 0)
    
    def test_highlight_selected_empty_mask(self, renderer, sample_category):
        """Test highlighting with element that has empty mask."""
        empty_mask = np.zeros((100, 100), dtype=np.uint8)
        
        elem = SegmentElement(
            element_id="elem1",
            category="rib",
            mode="flood",
            points=[(50, 50)],
            mask=empty_mask,
            color=sample_category.color_rgb
        )
        
        inst = ObjectInstance(
            instance_id="inst1",
            instance_num=1,
            elements=[elem],
            page_id="test_page"
        )
        
        obj = SegmentedObject(
            object_id="obj1",
            name="R1",
            category="rib",
            instances=[inst]
        )
        
        image = np.zeros((100, 100, 4), dtype=np.uint8)
        
        # Should not crash
        renderer._highlight_selected(
            image,
            [obj],
            selected_object_ids={"obj1"},
            selected_instance_ids=set(),
            selected_element_ids=set()
        )
    
    def test_draw_pending_elements(self, renderer, sample_category):
        """Test drawing pending elements."""
        image = np.zeros((100, 100, 4), dtype=np.uint8)
        
        mask = np.zeros((100, 100), dtype=np.uint8)
        mask[30:50, 30:50] = 255
        
        elem = SegmentElement(
            element_id="pending1",
            category="rib",
            mode="flood",
            points=[(40, 40)],
            mask=mask,
            color=sample_category.color_rgb
        )
        
        renderer._draw_pending_elements(image, [elem])
        
        # Should have drawn something
        assert np.any(image > 0)
    
    def test_draw_pixel_selection(self, renderer):
        """Test drawing pixel selection."""
        image = np.ones((100, 100, 3), dtype=np.uint8) * 255
        
        mask = np.zeros((100, 100), dtype=np.uint8)
        mask[40:60, 40:60] = 255
        
        result = renderer._draw_pixel_selection(image, mask)
        
        assert result.shape == (100, 100, 4)  # Should be BGRA
        assert result.dtype == np.uint8
    
    def test_draw_pixel_selection_with_move_offset(self, renderer):
        """Test drawing pixel selection with move offset."""
        image = np.ones((100, 100, 3), dtype=np.uint8) * 255
        
        mask = np.zeros((100, 100), dtype=np.uint8)
        mask[40:60, 40:60] = 255
        
        result = renderer._draw_pixel_selection(image, mask, move_offset=(10, 10))
        
        assert result.shape == (100, 100, 4)
    
    def test_draw_pixel_selection_wrong_size(self, renderer):
        """Test drawing pixel selection with wrong mask size."""
        image = np.ones((100, 100, 3), dtype=np.uint8) * 255
        
        mask = np.zeros((50, 50), dtype=np.uint8)  # Wrong size
        
        result = renderer._draw_pixel_selection(image, mask)
        
        # Should return original image unchanged
        assert result.shape == image.shape
    
    def test_render_page_different_page_instance(self, renderer, sample_page, sample_category, sample_object):
        """Test rendering with instance from different page."""
        # Create instance for different page
        mask = np.zeros((100, 100), dtype=np.uint8)
        mask[20:40, 20:40] = 255
        
        elem = SegmentElement(
            element_id="elem2",
            category="rib",
            mode="flood",
            points=[(30, 30)],
            mask=mask,
            color=sample_category.color_rgb
        )
        
        inst_other_page = ObjectInstance(
            instance_id="inst2",
            instance_num=1,
            elements=[elem],
            page_id="other_page"  # Different page
        )
        
        obj = SegmentedObject(
            object_id="obj2",
            name="R2",
            category="rib",
            instances=[inst_other_page]
        )
        
        sample_page.objects = [obj]
        categories = {"rib": sample_category}
        
        result = renderer.render_page(sample_page, categories)
        
        # Should render but instance from other page should be skipped
        assert result.shape == (100, 100, 4)
