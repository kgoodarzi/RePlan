"""Pytest fixtures for RePlan tests."""

import pytest
import numpy as np

from replan.desktop.models import (
    ObjectAttributes,
    SegmentElement,
    ObjectInstance,
    SegmentedObject,
    DynamicCategory,
    PageTab,
)


# ============================================================================
# ObjectAttributes Fixtures
# ============================================================================

@pytest.fixture
def default_attributes():
    """Create default ObjectAttributes."""
    return ObjectAttributes()


@pytest.fixture
def full_attributes():
    """Create ObjectAttributes with all fields populated."""
    return ObjectAttributes(
        material="balsa",
        width=10.0,
        height=5.0,
        depth=0.125,
        obj_type="sheet",
        view="top",
        description="Main wing rib",
        url="https://example.com/plans/rib.pdf",
        quantity=12,
        notes="Cut from 3/32 balsa",
    )


# ============================================================================
# Category Fixtures
# ============================================================================

@pytest.fixture
def sample_category():
    """Create a sample DynamicCategory."""
    return DynamicCategory(
        name="R",
        prefix="R",
        full_name="Rib",
        color_rgb=(220, 60, 60),
        selection_mode="flood",
    )


@pytest.fixture
def categories_dict(sample_category):
    """Create a dictionary of categories."""
    return {
        "R": sample_category,
        "F": DynamicCategory(
            name="F",
            prefix="F",
            full_name="Former",
            color_rgb=(200, 80, 80),
            selection_mode="flood",
        ),
    }


# ============================================================================
# Element Fixtures
# ============================================================================

@pytest.fixture
def sample_mask():
    """Create a simple 100x100 mask with a filled rectangle."""
    mask = np.zeros((100, 100), dtype=np.uint8)
    mask[20:80, 30:70] = 255  # 60x40 filled region
    return mask


@pytest.fixture
def empty_mask():
    """Create an empty 100x100 mask."""
    return np.zeros((100, 100), dtype=np.uint8)


@pytest.fixture
def sample_element(sample_mask):
    """Create a sample SegmentElement with a mask."""
    return SegmentElement(
        element_id="elem-001",
        category="R",
        mode="flood",
        points=[(50, 50)],
        mask=sample_mask,
        color=(220, 60, 60),
    )


@pytest.fixture
def polygon_element(sample_mask):
    """Create a polygon-mode SegmentElement."""
    return SegmentElement(
        element_id="elem-002",
        category="F",
        mode="polyline",
        points=[(30, 20), (70, 20), (70, 80), (30, 80)],
        mask=sample_mask,
        color=(200, 80, 80),
    )


# ============================================================================
# Instance Fixtures
# ============================================================================

@pytest.fixture
def sample_instance(sample_element, full_attributes):
    """Create a sample ObjectInstance with one element."""
    return ObjectInstance(
        instance_id="inst-001",
        instance_num=1,
        elements=[sample_element],
        page_id="page-001",
        view_type="top",
        attributes=full_attributes,
    )


@pytest.fixture
def multi_element_instance(sample_element, polygon_element):
    """Create an instance with multiple elements."""
    return ObjectInstance(
        instance_id="inst-002",
        instance_num=1,
        elements=[sample_element, polygon_element],
        page_id="page-001",
        view_type="top",
    )


# ============================================================================
# Object Fixtures
# ============================================================================

@pytest.fixture
def sample_object(sample_instance):
    """Create a sample SegmentedObject with one instance."""
    return SegmentedObject(
        object_id="obj-001",
        name="R1",
        category="R",
        instances=[sample_instance],
    )


@pytest.fixture
def multi_instance_object(sample_instance):
    """Create an object with multiple instances."""
    inst2 = ObjectInstance(
        instance_id="inst-003",
        instance_num=2,
        elements=[SegmentElement(
            element_id="elem-003",
            category="R",
            mode="flood",
            points=[(25, 25)],
            mask=np.zeros((100, 100), dtype=np.uint8),
        )],
        page_id="page-002",
    )
    return SegmentedObject(
        object_id="obj-002",
        name="R2",
        category="R",
        instances=[sample_instance, inst2],
    )


# ============================================================================
# Page Fixtures
# ============================================================================

@pytest.fixture
def sample_image():
    """Create a sample 200x300 BGR image."""
    return np.zeros((200, 300, 3), dtype=np.uint8)


@pytest.fixture
def sample_page(sample_image, sample_object):
    """Create a sample PageTab with an object."""
    page = PageTab(
        tab_id="page-001",
        model_name="TestModel",
        page_name="Page1",
        original_image=sample_image,
        source_path="/path/to/test.pdf",
        dpi=150.0,
        pdf_width_inches=11.0,
        pdf_height_inches=8.5,
    )
    page.objects = [sample_object]
    return page


@pytest.fixture
def empty_page():
    """Create an empty page without image."""
    return PageTab(
        tab_id="page-empty",
        model_name="Empty",
        page_name="Empty",
    )
