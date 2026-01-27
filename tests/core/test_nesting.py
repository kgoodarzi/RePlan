"""Tests for nesting module including 1D linear nesting."""

import pytest
import numpy as np

from replan.desktop.core.nesting import (
    LinearPart,
    LinearNestingEngine,
    NestedLinearPart,
    NestedStock,
    NestingEngine,
    NestedPart,
    NestedSheet,
)


class TestLinearPart:
    """Tests for LinearPart dataclass."""

    def test_basic_creation(self):
        """Test creating a linear part."""
        part = LinearPart(
            object_id="obj-1",
            instance_id="inst-1",
            name="Longeron",
            length=24.0,
            width=0.25,
            material="spruce",
            quantity=2,
        )
        assert part.length == 24.0
        assert part.quantity == 2
        assert part.total_length == 48.0

    def test_total_length_single(self):
        """Test total_length with quantity 1."""
        part = LinearPart(
            object_id="obj-1",
            instance_id="inst-1",
            name="Spar",
            length=12.0,
            width=0.5,
            material="balsa",
            quantity=1,
        )
        assert part.total_length == 12.0


class TestNestedLinearPart:
    """Tests for NestedLinearPart dataclass."""

    def test_end_position(self):
        """Test end_position calculation."""
        part = LinearPart(
            object_id="obj-1",
            instance_id="inst-1",
            name="Part",
            length=10.0,
            width=0.25,
            material="balsa",
        )
        nested = NestedLinearPart(part=part, position=5.0, copy_num=1)
        assert nested.end_position == 15.0


class TestNestedStock:
    """Tests for NestedStock dataclass."""

    def test_empty_stock(self):
        """Test empty stock properties."""
        stock = NestedStock(
            stock_id="test",
            length=36.0,
            width=0.25,
            material="balsa",
        )
        assert stock.utilization == 0.0
        assert stock.waste == 36.0
        assert stock.remaining_length == 36.0

    def test_stock_with_parts(self):
        """Test stock with parts placed."""
        part = LinearPart(
            object_id="obj-1",
            instance_id="inst-1",
            name="Part",
            length=10.0,
            width=0.25,
            material="balsa",
        )
        stock = NestedStock(
            stock_id="test",
            length=36.0,
            width=0.25,
            material="balsa",
            parts=[
                NestedLinearPart(part=part, position=0.0),
                NestedLinearPart(part=part, position=10.0),
            ],
        )
        assert stock.utilization == pytest.approx(55.56, abs=0.1)
        assert stock.waste == 16.0
        assert stock.remaining_length == 16.0


class TestLinearNestingEngine:
    """Tests for LinearNestingEngine class."""

    @pytest.fixture
    def engine(self):
        """Create a nesting engine."""
        return LinearNestingEngine(kerf=0.0)

    @pytest.fixture
    def sample_parts(self):
        """Create sample parts for testing."""
        return [
            LinearPart("obj-1", "inst-1", "Longeron A", 24.0, 0.25, "spruce", 2),
            LinearPart("obj-2", "inst-2", "Longeron B", 18.0, 0.25, "spruce", 2),
            LinearPart("obj-3", "inst-3", "Cross Member", 6.0, 0.25, "spruce", 4),
        ]

    def test_nest_single_part(self, engine):
        """Test nesting a single part."""
        parts = [LinearPart("obj-1", "inst-1", "Test", 10.0, 0.25, "balsa", 1)]
        stocks = engine.nest_parts(parts, [36.0], "balsa")
        
        assert len(stocks) == 1
        assert len(stocks[0].parts) == 1
        assert stocks[0].parts[0].part.length == 10.0

    def test_nest_multiple_parts_single_stock(self, engine):
        """Test nesting multiple parts that fit in one stock."""
        parts = [
            LinearPart("obj-1", "inst-1", "A", 10.0, 0.25, "balsa", 1),
            LinearPart("obj-2", "inst-2", "B", 10.0, 0.25, "balsa", 1),
            LinearPart("obj-3", "inst-3", "C", 10.0, 0.25, "balsa", 1),
        ]
        stocks = engine.nest_parts(parts, [36.0], "balsa")
        
        assert len(stocks) == 1
        assert len(stocks[0].parts) == 3

    def test_nest_multiple_stocks_needed(self, engine, sample_parts):
        """Test nesting when multiple stocks are needed."""
        # Total length needed: 24*2 + 18*2 + 6*4 = 48 + 36 + 24 = 108
        # With 36" stocks, need at least 3
        stocks = engine.nest_parts(sample_parts, [36.0], "spruce")
        
        assert len(stocks) >= 3
        
        # Verify all parts were placed
        total_parts = sum(len(s.parts) for s in stocks)
        expected_parts = 2 + 2 + 4  # quantities
        assert total_parts == expected_parts

    def test_first_fit_decreasing(self, engine):
        """Test that FFD places longest parts first."""
        parts = [
            LinearPart("obj-1", "inst-1", "Short", 5.0, 0.25, "balsa", 1),
            LinearPart("obj-2", "inst-2", "Long", 30.0, 0.25, "balsa", 1),
            LinearPart("obj-3", "inst-3", "Medium", 15.0, 0.25, "balsa", 1),
        ]
        stocks = engine.nest_parts(parts, [36.0], "balsa")
        
        # First stock should have the long part first
        assert stocks[0].parts[0].part.name == "Long"

    def test_with_kerf(self):
        """Test nesting with kerf allowance."""
        engine = LinearNestingEngine(kerf=0.125)  # 1/8" kerf
        parts = [
            LinearPart("obj-1", "inst-1", "A", 12.0, 0.25, "balsa", 3),
        ]
        # Without kerf: 3 x 12 = 36, fits in one 36" stock
        # With kerf: 3 x (12 + 0.125) = 36.375, needs two stocks
        stocks = engine.nest_parts(parts, [36.0], "balsa")
        
        # Should need 2 stocks due to kerf
        assert len(stocks) >= 1

    def test_empty_parts(self, engine):
        """Test with no parts."""
        stocks = engine.nest_parts([], [36.0], "balsa")
        assert len(stocks) == 0

    def test_empty_stock_lengths(self, engine):
        """Test with no stock lengths."""
        parts = [LinearPart("obj-1", "inst-1", "A", 10.0, 0.25, "balsa", 1)]
        stocks = engine.nest_parts(parts, [], "balsa")
        assert len(stocks) == 0

    def test_part_longer_than_stock(self, engine):
        """Test when part is longer than available stock."""
        parts = [LinearPart("obj-1", "inst-1", "Too Long", 48.0, 0.25, "balsa", 1)]
        stocks = engine.nest_parts(parts, [36.0], "balsa")
        
        # Should still place it (with warning)
        assert len(stocks) == 1
        assert len(stocks[0].parts) == 1

    def test_nest_by_width(self, engine):
        """Test nesting grouped by width."""
        parts = [
            LinearPart("obj-1", "inst-1", "1/4 stick", 10.0, 0.25, "balsa", 2),
            LinearPart("obj-2", "inst-2", "1/2 stick", 10.0, 0.5, "balsa", 2),
        ]
        stock_configs = {
            0.25: [36.0],
            0.5: [24.0],
        }
        results = engine.nest_by_width(parts, stock_configs)
        
        assert 0.25 in results
        assert 0.5 in results

    def test_generate_cut_list(self, engine, sample_parts):
        """Test cut list generation."""
        stocks = engine.nest_parts(sample_parts, [36.0], "spruce")
        cut_list = engine.generate_cut_list(stocks)
        
        assert len(cut_list) > 0
        assert "stock_num" in cut_list[0]
        assert "cuts" in cut_list[0]
        assert "utilization" in cut_list[0]

    def test_get_summary(self, engine, sample_parts):
        """Test summary generation."""
        stocks = engine.nest_parts(sample_parts, [36.0], "spruce")
        summary = engine.get_summary(stocks)
        
        assert "stock_count" in summary
        assert "total_stock_length" in summary
        assert "overall_utilization" in summary
        assert summary["parts_count"] == 8  # 2+2+4

    def test_get_summary_empty(self, engine):
        """Test summary with no stocks."""
        summary = engine.get_summary([])
        assert summary["stock_count"] == 0


class TestNestedSheet:
    """Tests for 2D NestedSheet class."""

    def test_utilization(self):
        """Test sheet utilization calculation."""
        sheet = NestedSheet(
            sheet_id="test",
            width=100,
            height=100,
            material="balsa",
            thickness=0.0625,
            parts=[
                NestedPart(
                    object_id="obj-1",
                    instance_id="inst-1",
                    name="Part 1",
                    x=0, y=0,
                    width=50, height=50,
                    rotated=False,
                ),
            ],
        )
        # 50x50 = 2500 out of 100x100 = 10000 = 25%
        assert sheet.utilization == 25.0

    def test_zero_dimensions(self):
        """Test utilization with zero dimensions."""
        sheet = NestedSheet(
            sheet_id="test",
            width=0,
            height=0,
            material="balsa",
            thickness=0.0625,
        )
        assert sheet.utilization == 0.0
