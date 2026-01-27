#!/usr/bin/env python
"""
RePlan Performance Benchmark Suite

Measures the performance of key operations and generates a report.

Usage:
    python -m benchmarks.run_benchmarks
    python -m benchmarks.run_benchmarks --pdf path/to/test.pdf
"""

import argparse
import sys
import time
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from replan.desktop.utils.profiling import profiler, profile_block


def benchmark_imports():
    """Benchmark module import times."""
    print("Benchmarking imports...")
    
    with profile_block("import_numpy"):
        import numpy as np
    
    with profile_block("import_cv2"):
        import cv2
    
    with profile_block("import_pil"):
        from PIL import Image
    
    with profile_block("import_replan_models"):
        from replan.desktop.models import PageTab, SegmentedObject
    
    with profile_block("import_replan_core"):
        from replan.desktop.core import SegmentationEngine, Renderer


def benchmark_segmentation_engine():
    """Benchmark core segmentation operations."""
    print("Benchmarking segmentation engine...")
    
    import numpy as np
    from replan.desktop.core import SegmentationEngine
    
    engine = SegmentationEngine(tolerance=5, line_thickness=3)
    
    # Create test image (1000x1000 white image with some features)
    test_image = np.ones((1000, 1000, 3), dtype=np.uint8) * 255
    # Add a black rectangle
    test_image[200:400, 200:400] = [0, 0, 0]
    # Add a gray region
    test_image[500:700, 500:800] = [128, 128, 128]
    
    # Benchmark flood fill
    with profile_block("flood_fill"):
        mask = engine.flood_fill(test_image, (300, 300))
    
    # Benchmark polygon mask creation
    polygon_points = [(100, 100), (200, 100), (200, 200), (100, 200)]
    with profile_block("polygon_mask"):
        mask = engine.create_polygon_mask((1000, 1000), polygon_points)
    
    # Benchmark line mask creation
    line_points = [(0, 0), (500, 500), (1000, 0)]
    with profile_block("line_mask"):
        mask = engine.create_line_mask((1000, 1000), line_points, thickness=3)


def benchmark_workspace_io():
    """Benchmark workspace save/load operations."""
    print("Benchmarking workspace I/O...")
    
    import tempfile
    import numpy as np
    from replan.desktop.io import WorkspaceManager
    from replan.desktop.models import PageTab, SegmentedObject, ObjectInstance, SegmentElement
    from replan.desktop.models.categories import create_default_categories
    
    mgr = WorkspaceManager(tolerance=5, line_thickness=3)
    
    # Create test data
    categories = create_default_categories()
    
    # Create a simple test page
    test_image = np.ones((1000, 1000, 3), dtype=np.uint8) * 255
    page = PageTab(
        tab_id="test-page",
        model_name="Test Model",
        page_name="Page 1"
    )
    page.original_image = test_image
    page.segmentation_layer = np.zeros((1000, 1000, 4), dtype=np.uint8)
    
    # Add some test objects
    for i in range(10):
        obj = SegmentedObject(
            object_id=f"obj-{i}",
            name=f"Object {i}",
            category="rib"
        )
        instance = ObjectInstance(
            instance_id=f"inst-{i}",
            instance_num=1,
            page_id=page.tab_id
        )
        element = SegmentElement(
            element_id=f"elem-{i}",
            category="rib",
            mode="flood",
            points=[(100 + i*50, 100), (150 + i*50, 150)],
            mask=np.zeros((1000, 1000), dtype=np.uint8),
            color=(255, 0, 0)
        )
        instance.elements.append(element)
        obj.instances.append(instance)
        page.groups.append(obj)
    
    pages = {"test-page": page}
    
    # Benchmark save
    with tempfile.NamedTemporaryFile(suffix=".pmw", delete=False) as f:
        temp_path = f.name
    
    with profile_block("workspace_save"):
        mgr.save(temp_path, pages, categories)
    
    # Benchmark load
    with profile_block("workspace_load"):
        loaded_pages, loaded_categories = mgr.load(temp_path)
    
    # Cleanup
    Path(temp_path).unlink(missing_ok=True)


def benchmark_pdf_load(pdf_path: str = None):
    """Benchmark PDF loading operations."""
    if not pdf_path:
        print("Skipping PDF benchmark (no PDF path provided)")
        return
    
    print(f"Benchmarking PDF load: {pdf_path}")
    
    from replan.desktop.io import PDFReader
    
    reader = PDFReader()
    
    with profile_block("pdf_load"):
        pages = reader.load(pdf_path)
    
    print(f"  Loaded {len(pages)} pages")


def benchmark_canvas_render():
    """Benchmark canvas rendering operations."""
    print("Benchmarking canvas rendering...")
    
    import numpy as np
    from replan.desktop.core import Renderer
    from replan.desktop.models import PageTab
    
    renderer = Renderer()
    
    # Create test page with image
    test_image = np.random.randint(0, 255, (2000, 2000, 3), dtype=np.uint8)
    page = PageTab(
        tab_id="test-page",
        model_name="Test Model",
        page_name="Page 1"
    )
    page.original_image = test_image
    page.segmentation_layer = np.zeros((2000, 2000, 4), dtype=np.uint8)
    
    # Benchmark render at different zoom levels
    for zoom in [0.5, 1.0, 2.0]:
        with profile_block(f"canvas_render_zoom_{zoom}"):
            rendered = renderer.render_page(
                page=page,
                zoom=zoom,
                show_labels=True,
                selected_ids=set(),
                planform_opacity=0.5
            )


def main():
    parser = argparse.ArgumentParser(description="RePlan Performance Benchmarks")
    parser.add_argument("--pdf", type=str, help="Path to PDF file for benchmarking")
    parser.add_argument("--output", type=str, help="Path to save benchmark report (JSON)")
    args = parser.parse_args()
    
    print("=" * 60)
    print("RePlan Performance Benchmark Suite")
    print("=" * 60)
    print()
    
    # Run benchmarks
    benchmark_imports()
    print()
    
    benchmark_segmentation_engine()
    print()
    
    benchmark_workspace_io()
    print()
    
    benchmark_canvas_render()
    print()
    
    if args.pdf:
        benchmark_pdf_load(args.pdf)
        print()
    
    # Print summary
    profiler.print_summary()
    
    # Save report if requested
    if args.output:
        output_path = Path(args.output)
        profiler.save_report(output_path)
        print(f"\nReport saved to: {output_path}")


if __name__ == "__main__":
    main()
