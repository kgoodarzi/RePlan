"""Tests for ObjectInstance and SegmentedObject models."""

import pytest
import numpy as np
from replan.desktop.models import (
    ObjectInstance,
    SegmentedObject,
    SegmentElement,
    ObjectAttributes,
)


class TestObjectInstanceBasics:
    """Tests for basic ObjectInstance functionality."""

    def test_default_initialization(self):
        """Test that defaults are set correctly."""
        inst = ObjectInstance()
        assert inst.instance_id != ""  # Auto-generated
        assert inst.instance_num == 1
        assert inst.elements == []
        assert inst.page_id is None
        assert inst.view_type == ""
        assert isinstance(inst.attributes, ObjectAttributes)

    def test_auto_generated_id(self):
        """Test that instance_id is auto-generated when empty."""
        inst1 = ObjectInstance()
        inst2 = ObjectInstance()
        assert inst1.instance_id != inst2.instance_id
        assert len(inst1.instance_id) == 8

    def test_explicit_id(self):
        """Test that explicit instance_id is preserved."""
        inst = ObjectInstance(instance_id="my-custom-id")
        assert inst.instance_id == "my-custom-id"

    def test_full_initialization(self, sample_instance):
        """Test initialization with all fields."""
        inst = sample_instance
        assert inst.instance_id == "inst-001"
        assert inst.instance_num == 1
        assert inst.page_id == "page-001"
        assert inst.view_type == "top"
        assert len(inst.elements) == 1


class TestObjectInstanceIsGrouped:
    """Tests for is_grouped property."""

    def test_empty_elements(self):
        """Test is_grouped with no elements."""
        inst = ObjectInstance()
        assert inst.is_grouped is False

    def test_single_element(self, sample_instance):
        """Test is_grouped with one element."""
        assert sample_instance.is_grouped is False

    def test_multiple_elements(self, multi_element_instance):
        """Test is_grouped with multiple elements."""
        assert multi_element_instance.is_grouped is True


class TestObjectInstanceElementCount:
    """Tests for element_count property."""

    def test_empty_elements(self):
        """Test element_count with no elements."""
        inst = ObjectInstance()
        assert inst.element_count == 0

    def test_single_element(self, sample_instance):
        """Test element_count with one element."""
        assert sample_instance.element_count == 1

    def test_multiple_elements(self, multi_element_instance):
        """Test element_count with multiple elements."""
        assert multi_element_instance.element_count == 2


class TestObjectInstanceTotalArea:
    """Tests for total_area property."""

    def test_empty_elements(self):
        """Test total_area with no elements."""
        inst = ObjectInstance()
        assert inst.total_area == 0

    def test_with_elements(self, sample_instance):
        """Test total_area sums element areas."""
        area = sample_instance.total_area
        assert area == 60 * 40  # Sample mask is 60x40

    def test_with_none_mask_elements(self):
        """Test total_area with elements having None masks."""
        elem = SegmentElement(mask=None)
        inst = ObjectInstance(elements=[elem])
        assert inst.total_area == 0


class TestObjectInstanceSerialization:
    """Tests for to_dict and from_dict methods."""

    def test_to_dict(self, sample_instance):
        """Test serialization to dictionary."""
        data = sample_instance.to_dict()
        assert data["instance_id"] == "inst-001"
        assert data["instance_num"] == 1
        assert data["page_id"] == "page-001"
        assert data["view_type"] == "top"
        assert "elements" in data
        assert "attributes" in data

    def test_from_dict_basic(self):
        """Test deserialization from dictionary."""
        data = {
            "instance_id": "test-inst",
            "instance_num": 2,
            "page_id": "page-002",
            "view_type": "side",
        }
        inst = ObjectInstance.from_dict(data)
        assert inst.instance_id == "test-inst"
        assert inst.instance_num == 2
        assert inst.page_id == "page-002"
        assert inst.view_type == "side"

    def test_from_dict_defaults(self):
        """Test deserialization with defaults."""
        inst = ObjectInstance.from_dict({})
        assert inst.instance_num == 1
        assert inst.page_id is None
        assert inst.view_type == ""

    def test_from_dict_with_elements(self, sample_element):
        """Test deserialization with provided elements."""
        data = {"instance_id": "test"}
        inst = ObjectInstance.from_dict(data, elements=[sample_element])
        assert len(inst.elements) == 1

    def test_from_dict_with_attributes(self):
        """Test deserialization loads attributes."""
        data = {
            "instance_id": "test",
            "attributes": {"material": "balsa", "width": 5.0},
        }
        inst = ObjectInstance.from_dict(data)
        assert inst.attributes.material == "balsa"
        assert inst.attributes.width == 5.0


class TestSegmentedObjectBasics:
    """Tests for basic SegmentedObject functionality."""

    def test_default_initialization(self):
        """Test that defaults are set correctly."""
        obj = SegmentedObject()
        assert obj.object_id != ""  # Auto-generated
        assert obj.name == ""
        assert obj.category == ""
        assert obj.instances == []

    def test_auto_generated_id(self):
        """Test that object_id is auto-generated when empty."""
        obj1 = SegmentedObject()
        obj2 = SegmentedObject()
        assert obj1.object_id != obj2.object_id
        assert len(obj1.object_id) == 8

    def test_explicit_id(self):
        """Test that explicit object_id is preserved."""
        obj = SegmentedObject(object_id="my-custom-id")
        assert obj.object_id == "my-custom-id"

    def test_full_initialization(self, sample_object):
        """Test initialization with all fields."""
        obj = sample_object
        assert obj.object_id == "obj-001"
        assert obj.name == "R1"
        assert obj.category == "R"
        assert len(obj.instances) == 1


class TestSegmentedObjectElementCount:
    """Tests for element_count property."""

    def test_empty_instances(self):
        """Test element_count with no instances."""
        obj = SegmentedObject()
        assert obj.element_count == 0

    def test_with_instances(self, sample_object):
        """Test element_count sums across instances."""
        assert sample_object.element_count == 1

    def test_with_multiple_instances(self, multi_instance_object):
        """Test element_count with multiple instances."""
        assert multi_instance_object.element_count == 2


class TestSegmentedObjectInstanceCount:
    """Tests for instance_count property."""

    def test_empty_instances(self):
        """Test instance_count with no instances."""
        obj = SegmentedObject()
        assert obj.instance_count == 0

    def test_with_one_instance(self, sample_object):
        """Test instance_count with one instance."""
        assert sample_object.instance_count == 1

    def test_with_multiple_instances(self, multi_instance_object):
        """Test instance_count with multiple instances."""
        assert multi_instance_object.instance_count == 2


class TestSegmentedObjectIsSimple:
    """Tests for is_simple property."""

    def test_empty_object(self):
        """Test is_simple with no instances."""
        obj = SegmentedObject()
        assert obj.is_simple is False

    def test_simple_object(self, sample_object):
        """Test is_simple with one instance, one element."""
        assert sample_object.is_simple is True

    def test_multiple_instances(self, multi_instance_object):
        """Test is_simple with multiple instances."""
        assert multi_instance_object.is_simple is False

    def test_grouped_elements(self, multi_element_instance):
        """Test is_simple with grouped elements."""
        obj = SegmentedObject(instances=[multi_element_instance])
        assert obj.is_simple is False


class TestSegmentedObjectHasMultipleInstances:
    """Tests for has_multiple_instances property."""

    def test_empty_object(self):
        """Test with no instances."""
        obj = SegmentedObject()
        assert obj.has_multiple_instances is False

    def test_single_instance(self, sample_object):
        """Test with one instance."""
        assert sample_object.has_multiple_instances is False

    def test_multiple_instances(self, multi_instance_object):
        """Test with multiple instances."""
        assert multi_instance_object.has_multiple_instances is True


class TestSegmentedObjectHasGroupedElements:
    """Tests for has_grouped_elements property."""

    def test_empty_object(self):
        """Test with no instances."""
        obj = SegmentedObject()
        assert obj.has_grouped_elements is False

    def test_ungrouped_elements(self, sample_object):
        """Test with ungrouped elements."""
        assert sample_object.has_grouped_elements is False

    def test_grouped_elements(self, multi_element_instance):
        """Test with grouped elements."""
        obj = SegmentedObject(instances=[multi_element_instance])
        assert obj.has_grouped_elements is True


class TestSegmentedObjectGetInstanceForPage:
    """Tests for get_instance_for_page method."""

    def test_found(self, sample_object):
        """Test finding instance on existing page."""
        inst = sample_object.get_instance_for_page("page-001")
        assert inst is not None
        assert inst.page_id == "page-001"

    def test_not_found(self, sample_object):
        """Test returns None for non-existent page."""
        inst = sample_object.get_instance_for_page("non-existent")
        assert inst is None

    def test_empty_instances(self):
        """Test returns None with no instances."""
        obj = SegmentedObject()
        assert obj.get_instance_for_page("page-001") is None


class TestSegmentedObjectAddInstance:
    """Tests for add_instance method."""

    def test_add_first_instance(self):
        """Test adding first instance."""
        obj = SegmentedObject(name="R1", category="R")
        inst = obj.add_instance(view_type="top", page_id="page-001")
        assert len(obj.instances) == 1
        assert inst.instance_num == 1
        assert inst.view_type == "top"
        assert inst.page_id == "page-001"

    def test_add_multiple_instances(self):
        """Test adding multiple instances."""
        obj = SegmentedObject(name="R1", category="R")
        inst1 = obj.add_instance(view_type="top", page_id="page-001")
        inst2 = obj.add_instance(view_type="side", page_id="page-002")
        assert len(obj.instances) == 2
        assert inst1.instance_num == 1
        assert inst2.instance_num == 2

    def test_instance_num_increments(self, sample_object):
        """Test that instance_num increments correctly."""
        # sample_object already has one instance
        inst = sample_object.add_instance()
        assert inst.instance_num == 2


class TestSegmentedObjectSerialization:
    """Tests for to_dict and from_dict methods."""

    def test_to_dict(self, sample_object):
        """Test serialization to dictionary."""
        data = sample_object.to_dict()
        assert data["object_id"] == "obj-001"
        assert data["name"] == "R1"
        assert data["category"] == "R"
        assert "instances" in data
        assert len(data["instances"]) == 1

    def test_from_dict_basic(self):
        """Test deserialization from dictionary."""
        data = {
            "object_id": "test-obj",
            "name": "F1",
            "category": "F",
        }
        obj = SegmentedObject.from_dict(data)
        assert obj.object_id == "test-obj"
        assert obj.name == "F1"
        assert obj.category == "F"

    def test_from_dict_backward_compat_group_id(self):
        """Test backward compatibility with group_id."""
        data = {
            "group_id": "old-id",
            "name": "R1",
            "category": "R",
        }
        obj = SegmentedObject.from_dict(data)
        assert obj.object_id == "old-id"

    def test_from_dict_with_instances(self, sample_instance):
        """Test deserialization with provided instances."""
        data = {"object_id": "test", "name": "R1"}
        obj = SegmentedObject.from_dict(data, instances=[sample_instance])
        assert len(obj.instances) == 1

    def test_from_dict_migrates_old_attributes(self, sample_instance):
        """Test backward compatibility: object-level attributes migrated to first instance."""
        data = {
            "object_id": "test",
            "name": "R1",
            "attributes": {"material": "balsa", "obj_type": "sheet"},
        }
        obj = SegmentedObject.from_dict(data, instances=[sample_instance])
        # Old attributes should be migrated to first instance
        assert obj.instances[0].attributes.material == "balsa"

    def test_from_dict_no_migration_if_no_instances(self):
        """Test that attribute migration is skipped if no instances."""
        data = {
            "object_id": "test",
            "name": "R1",
            "attributes": {"material": "balsa"},
        }
        obj = SegmentedObject.from_dict(data)
        # No instances, so no migration
        assert len(obj.instances) == 0
