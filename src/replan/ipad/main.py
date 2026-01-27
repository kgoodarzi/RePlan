"""
PlanMod Segmenter for iPad - Main Entry Point

This is the main application that can run on:
- Pyto (iOS) - Full UI with touch support
- Pythonista (iOS) - Full UI with touch support  
- Desktop (testing) - Console-based interface

Usage on iPad:
    Open this file in Pyto or Pythonista and run it.

Usage for testing on desktop:
    python -m tools.segmenter_ipad.main --console
"""

import sys
import os
from pathlib import Path
from typing import Dict, List, Optional, Set
import numpy as np

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from replan.ipad.config import load_settings, save_settings, get_theme, AppSettings
from replan.ipad.models import (
    PageTab, SegmentedObject, ObjectInstance, SegmentElement,
    DynamicCategory, create_default_categories, get_next_color
)
from replan.ipad.core import SegmentationEngine, Renderer
from replan.ipad.io import WorkspaceManager, ImageExporter, DataExporter
from replan.ipad.services import PDFService, OCRService

VERSION = "1.0.0"

# Check for UI availability
try:
    import pyto_ui as ui
    HAS_PYTO_UI = True
except ImportError:
    ui = None
    HAS_PYTO_UI = False


class SegmenterApp:
    """
    Main application class for iPad Segmenter.
    
    This class manages the application state and coordinates
    between the UI, core logic, and I/O modules.
    """
    
    MODES = {
        "select": "Select existing objects",
        "flood": "Flood fill region",
        "polyline": "Draw polygon",
        "freeform": "Freeform brush",
        "line": "Line segments",
    }
    
    def __init__(self):
        # Load settings
        self.settings = load_settings()
        self.theme = get_theme(self.settings.theme)
        
        # Core components
        self.engine = SegmentationEngine(
            self.settings.tolerance, 
            self.settings.line_thickness
        )
        self.renderer = Renderer()
        self.workspace_mgr = WorkspaceManager(
            self.settings.tolerance,
            self.settings.line_thickness
        )
        self.pdf_service = PDFService(self.settings.default_dpi)
        self.ocr_service = OCRService()
        
        # Application state
        self.pages: Dict[str, PageTab] = {}
        self.current_page_id: Optional[str] = None
        self.categories: Dict[str, DynamicCategory] = create_default_categories()
        self.all_objects: List[SegmentedObject] = []
        
        # Selection state
        self.selected_object_ids: Set[str] = set()
        self.selected_instance_ids: Set[str] = set()
        self.selected_element_ids: Set[str] = set()
        
        # Tool state
        self.current_mode = "flood"
        self.current_category = "R"  # Default to Rib
        self.current_points: List[tuple] = []
        self.is_drawing = False
        
        # Display state
        self.zoom_level = 1.0
        self.show_labels = True
        
        # Workspace state
        self.workspace_file: Optional[str] = None
        self.workspace_modified = False
        
        # UI components (set when UI is created)
        self.main_view = None
        self.canvas_view = None
        self.toolbar_view = None
        self.sidebar_view = None
    
    @property
    def current_page(self) -> Optional[PageTab]:
        """Get the current page."""
        if self.current_page_id:
            return self.pages.get(self.current_page_id)
        return None
    
    def load_image(self, path: str, model_name: str = None) -> bool:
        """Load an image file."""
        try:
            from PIL import Image
            
            pil_img = Image.open(path)
            image = np.array(pil_img)
            
            if model_name is None:
                model_name = Path(path).stem
            
            page = PageTab(
                model_name=model_name,
                page_name="Page 1",
                original_image=image,
                source_path=path,
            )
            
            self.pages[page.tab_id] = page
            self.current_page_id = page.tab_id
            self.workspace_modified = True
            
            self._update_canvas()
            self._update_sidebar()
            
            return True
            
        except Exception as e:
            print(f"Error loading image: {e}")
            return False
    
    def load_pdf(self, path: str, model_name: str = None) -> bool:
        """Load a PDF file."""
        try:
            pages_data = self.pdf_service.load_with_dimensions(path)
            
            if not pages_data:
                print("No pages loaded from PDF")
                return False
            
            if model_name is None:
                model_name = PDFService.get_default_model_name(path)
            
            for i, page_info in enumerate(pages_data):
                page = PageTab(
                    model_name=model_name,
                    page_name=f"Page {i + 1}",
                    original_image=page_info['image'],
                    source_path=path,
                    dpi=page_info['dpi'],
                    pdf_width_inches=page_info['width_inches'],
                    pdf_height_inches=page_info['height_inches'],
                )
                
                self.pages[page.tab_id] = page
                
                if i == 0:
                    self.current_page_id = page.tab_id
            
            self.workspace_modified = True
            self._update_canvas()
            self._update_sidebar()
            
            return True
            
        except Exception as e:
            print(f"Error loading PDF: {e}")
            return False
    
    def save_workspace(self, path: str = None) -> bool:
        """Save the current workspace."""
        path = path or self.workspace_file
        if not path:
            print("No workspace path specified")
            return False
        
        success = self.workspace_mgr.save(
            path,
            list(self.pages.values()),
            self.categories,
            self.all_objects,
        )
        
        if success:
            self.workspace_file = path
            self.workspace_modified = False
            self.settings.last_workspace = path
            self.settings.add_recent_file(path)
            save_settings(self.settings)
        
        return success
    
    def load_workspace(self, path: str) -> bool:
        """Load a workspace file."""
        data = self.workspace_mgr.load(path)
        
        if not data:
            return False
        
        self.pages = {p.tab_id: p for p in data.pages}
        self.categories = data.categories
        self.all_objects = data.objects
        
        if data.pages:
            self.current_page_id = data.pages[0].tab_id
        
        self.workspace_file = path
        self.workspace_modified = False
        self.settings.last_workspace = path
        self.settings.add_recent_file(path)
        save_settings(self.settings)
        
        self._update_canvas()
        self._update_sidebar()
        
        return True
    
    def create_segment(self, points: List[tuple], mode: str = None) -> Optional[SegmentElement]:
        """Create a new segment from points."""
        page = self.current_page
        if page is None or page.original_image is None:
            return None
        
        mode = mode or self.current_mode
        h, w = page.original_image.shape[:2]
        
        # Create mask based on mode
        if mode == "flood" and points:
            mask = self.engine.flood_fill(page.original_image, points[0])
        elif mode == "polyline" and len(points) >= 3:
            mask = self.engine.create_polygon_mask((h, w), points)
        elif mode in ["line", "freeform"] and len(points) >= 2:
            mask = self.engine.create_line_mask((h, w), points)
        else:
            return None
        
        # Check if mask has any content
        if not np.any(mask):
            return None
        
        # Get category color
        cat = self.categories.get(self.current_category)
        color = cat.color_rgb if cat else (128, 128, 128)
        
        element = SegmentElement(
            category=self.current_category,
            mode=mode,
            points=points,
            mask=mask,
            color=color,
        )
        
        return element
    
    def add_object(self, element: SegmentElement) -> SegmentedObject:
        """Add a new object from an element."""
        page = self.current_page
        if page is None:
            return None
        
        # Generate name
        cat = self.categories.get(element.category)
        prefix = cat.prefix if cat else element.category
        
        # Count existing objects with this prefix
        existing = [o for o in self.all_objects if o.category == element.category]
        num = len(existing) + 1
        name = f"{prefix}{num}"
        
        # Create instance and object
        instance = ObjectInstance(
            instance_num=1,
            elements=[element],
            page_id=page.tab_id,
        )
        
        obj = SegmentedObject(
            name=name,
            category=element.category,
            instances=[instance],
        )
        
        self.all_objects.append(obj)
        self.workspace_modified = True
        self.renderer.invalidate_cache()
        
        self._update_canvas()
        self._update_sidebar()
        
        return obj
    
    def delete_selected(self):
        """Delete selected objects/instances/elements."""
        if self.selected_element_ids:
            for obj in self.all_objects:
                for inst in obj.instances:
                    inst.elements = [e for e in inst.elements 
                                    if e.element_id not in self.selected_element_ids]
        elif self.selected_instance_ids:
            for obj in self.all_objects:
                obj.instances = [i for i in obj.instances 
                               if i.instance_id not in self.selected_instance_ids]
        elif self.selected_object_ids:
            self.all_objects = [o for o in self.all_objects 
                               if o.object_id not in self.selected_object_ids]
        
        # Clean up empty objects/instances
        for obj in self.all_objects[:]:
            obj.instances = [i for i in obj.instances if i.elements]
            if not obj.instances:
                self.all_objects.remove(obj)
        
        self.clear_selection()
        self.workspace_modified = True
        self.renderer.invalidate_cache()
        
        self._update_canvas()
        self._update_sidebar()
    
    def clear_selection(self):
        """Clear all selections."""
        self.selected_object_ids.clear()
        self.selected_instance_ids.clear()
        self.selected_element_ids.clear()
    
    def get_objects_for_page(self, page_id: str = None) -> List[SegmentedObject]:
        """Get objects that have instances on a specific page."""
        page_id = page_id or self.current_page_id
        result = []
        
        for obj in self.all_objects:
            for inst in obj.instances:
                if inst.page_id == page_id:
                    result.append(obj)
                    break
        
        return result
    
    def render_current_page(self) -> Optional[np.ndarray]:
        """Render the current page with all overlays."""
        page = self.current_page
        if page is None:
            return None
        
        objects = self.get_objects_for_page()
        
        return self.renderer.render_page(
            page,
            self.categories,
            zoom=self.zoom_level,
            show_labels=self.show_labels,
            selected_object_ids=self.selected_object_ids,
            selected_instance_ids=self.selected_instance_ids,
            selected_element_ids=self.selected_element_ids,
            objects=objects,
        )
    
    def export_current_page(self, path: str, include_labels: bool = True) -> bool:
        """Export the current page as an image."""
        page = self.current_page
        if page is None:
            return False
        
        exporter = ImageExporter(self.renderer)
        return exporter.export_page(path, page, self.categories, include_labels)
    
    # === UI Callbacks ===
    
    def _on_segment_created(self, points: List[tuple], mode: str):
        """Handle segment creation from canvas."""
        element = self.create_segment(points, mode)
        if element:
            self.add_object(element)
    
    def _on_tool_selected(self, tool_name: str):
        """Handle tool selection from toolbar."""
        self.current_mode = tool_name
        if self.canvas_view:
            self.canvas_view.set_mode(tool_name)
    
    def _on_action(self, action_name: str):
        """Handle action from toolbar."""
        if action_name == "undo":
            # Undo not yet implemented
            pass
        elif action_name == "delete":
            self.delete_selected()
        elif action_name == "zoom_fit":
            if self.canvas_view:
                self.canvas_view.zoom_to_fit()
    
    def _on_category_selected(self, key: str):
        """Handle category selection from sidebar."""
        self.current_category = key
    
    def _on_category_visibility(self, key: str):
        """Handle category visibility toggle."""
        if key in self.categories:
            self.categories[key].visible = not self.categories[key].visible
            self.renderer.invalidate_cache()
            self._update_canvas()
    
    def _on_object_selected(self, object_id: str):
        """Handle object selection from sidebar."""
        self.clear_selection()
        self.selected_object_ids.add(object_id)
        
        if self.sidebar_view:
            self.sidebar_view.select_objects(self.selected_object_ids)
        
        self._update_canvas()
    
    def _update_canvas(self):
        """Update the canvas display."""
        if self.canvas_view:
            rendered = self.render_current_page()
            if rendered is not None:
                self.canvas_view.set_image(rendered)
    
    def _update_sidebar(self):
        """Update the sidebar."""
        if self.sidebar_view:
            self.sidebar_view.set_categories(self.categories)
            self.sidebar_view.set_objects(self.get_objects_for_page())


def get_screen_size():
    """Get screen size in a way that works across Pyto versions."""
    # Try different methods to get screen size
    
    # Method 1: Try UIKit via rubicon-objc (Pyto)
    try:
        from rubicon.objc import ObjCClass
        UIScreen = ObjCClass('UIScreen')
        main_screen = UIScreen.mainScreen
        bounds = main_screen.bounds
        return (bounds.size.width, bounds.size.height)
    except:
        pass
    
    # Method 2: Try objc_util (Pythonista style)
    try:
        from objc_util import ObjCClass
        UIScreen = ObjCClass('UIScreen')
        main_screen = UIScreen.mainScreen()
        bounds = main_screen.bounds()
        return (bounds.size.width, bounds.size.height)
    except:
        pass
    
    # Method 3: Default iPad sizes
    # iPad Pro 12.9": 1024x1366
    # iPad Pro 11": 834x1194
    # iPad Air/regular: 820x1180
    return (1024, 768)  # Safe default


def create_pyto_ui(app: SegmenterApp):
    """Create the full Pyto UI."""
    # Try relative imports first, then full path
    try:
        from ui.canvas_view import CanvasView
        from ui.toolbar import ToolbarView
        from ui.sidebar import SidebarView
        from ui.dialogs import show_alert
    except ImportError:
        from replan.ipad.ui.canvas_view import CanvasView
        from replan.ipad.ui.toolbar import ToolbarView
        from replan.ipad.ui.sidebar import SidebarView
        from replan.ipad.ui.dialogs import show_alert
    
    # Main view
    main_view = ui.View()
    main_view.background_color = ui.Color.rgb(0.11, 0.11, 0.12)
    
    # Get screen size
    width, height = get_screen_size()
    print(f"Screen size: {width}x{height}")
    
    # Toolbar at top
    toolbar = ToolbarView(
        on_tool_selected=app._on_tool_selected,
        on_action=app._on_action,
        theme=app.theme
    )
    if toolbar.view:
        toolbar.view.frame = (0, 50, width, 60)
        main_view.add_subview(toolbar.view)
    app.toolbar_view = toolbar
    
    # Sidebar on right
    sidebar_width = 240
    sidebar = SidebarView(
        on_category_selected=app._on_category_selected,
        on_category_visibility=app._on_category_visibility,
        on_object_selected=app._on_object_selected,
        theme=app.theme
    )
    if sidebar.view:
        sidebar.view.frame = (width - sidebar_width, 110, sidebar_width, height - 160)
        main_view.add_subview(sidebar.view)
    sidebar.set_categories(app.categories)
    app.sidebar_view = sidebar
    
    # Canvas in center
    canvas = CanvasView(on_segment_created=app._on_segment_created)
    if canvas.view:
        canvas.view.frame = (0, 110, width - sidebar_width, height - 160)
        main_view.add_subview(canvas.view)
    app.canvas_view = canvas
    
    # Status bar at bottom
    status_bar = ui.View()
    status_bar.background_color = ui.Color.rgb(0.04, 0.52, 1.0)
    status_bar.frame = (0, height - 50, width, 50)
    main_view.add_subview(status_bar)
    
    status_label = ui.Label("Ready")
    status_label.text_color = ui.Color.white()
    status_label.font = ui.Font.system_font_of_size(14)
    status_label.frame = (20, 15, 300, 20)
    status_bar.add_subview(status_label)
    
    # Menu button (top left)
    menu_btn = ui.Button()
    menu_btn.title = "☰"
    menu_btn.font = ui.Font.system_font_of_size(24)
    menu_btn.tint_color = ui.Color.white()
    menu_btn.frame = (10, 10, 40, 40)
    menu_btn.action = lambda s: show_menu(app)
    main_view.add_subview(menu_btn)
    
    # Title
    title = ui.Label(f"PlanMod Segmenter v{VERSION}")
    title.text_color = ui.Color.white()
    title.font = ui.Font.bold_system_font_of_size(17)
    title.frame = (60, 15, 250, 30)
    main_view.add_subview(title)
    
    app.main_view = main_view
    return main_view


def show_menu(app: SegmenterApp):
    """Show the main menu."""
    if not HAS_PYTO_UI:
        return
    
    alert = ui.Alert("Menu", "")
    alert.add_action(ui.AlertAction("Open Image"))
    alert.add_action(ui.AlertAction("Open PDF"))
    alert.add_action(ui.AlertAction("Open Workspace"))
    alert.add_action(ui.AlertAction("Save Workspace"))
    alert.add_action(ui.AlertAction("Export..."))
    alert.add_action(ui.AlertAction("Settings"))
    alert.add_action(ui.AlertAction("Cancel", ui.AlertActionStyle.CANCEL))
    alert.show()


def run_console_mode():
    """Run in console mode for testing."""
    print(f"PlanMod Segmenter for iPad v{VERSION}")
    print("=" * 40)
    print("Console mode - for testing on desktop")
    print()
    
    app = SegmenterApp()
    
    while True:
        print("\nCommands:")
        print("  load <path>  - Load image or PDF")
        print("  save <path>  - Save workspace")
        print("  open <path>  - Open workspace")
        print("  info         - Show current state")
        print("  objects      - List objects")
        print("  categories   - List categories")
        print("  quit         - Exit")
        
        try:
            cmd = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        
        if not cmd:
            continue
        
        parts = cmd.split(maxsplit=1)
        action = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""
        
        if action == "quit":
            break
        elif action == "load":
            if arg.lower().endswith('.pdf'):
                if app.load_pdf(arg):
                    print(f"Loaded PDF: {len(app.pages)} pages")
                else:
                    print("Failed to load PDF")
            else:
                if app.load_image(arg):
                    print("Image loaded")
                else:
                    print("Failed to load image")
        elif action == "save":
            if app.save_workspace(arg):
                print("Workspace saved")
            else:
                print("Failed to save workspace")
        elif action == "open":
            if app.load_workspace(arg):
                print(f"Workspace loaded: {len(app.pages)} pages, {len(app.all_objects)} objects")
            else:
                print("Failed to load workspace")
        elif action == "info":
            print(f"Pages: {len(app.pages)}")
            print(f"Objects: {len(app.all_objects)}")
            print(f"Categories: {len(app.categories)}")
            if app.current_page:
                print(f"Current page: {app.current_page.display_name}")
        elif action == "objects":
            for obj in app.all_objects:
                print(f"  {obj.name} ({obj.category}) - {obj.instance_count} instances")
        elif action == "categories":
            for key, cat in app.categories.items():
                vis = "visible" if cat.visible else "hidden"
                print(f"  {key}: {cat.full_name} ({vis})")
        else:
            print(f"Unknown command: {action}")
    
    print("Goodbye!")


def run_pyto_ui():
    """Run with Pyto UI."""
    try:
        app = SegmenterApp()
        main_view = create_pyto_ui(app)
        main_view.present()
        
    except Exception as e:
        print(f"Error starting Pyto UI: {e}")
        import traceback
        traceback.print_exc()
        run_console_mode()


def main():
    """Main entry point."""
    # Check command line args
    if "--console" in sys.argv:
        run_console_mode()
        return
    
    # Check for UI availability
    if HAS_PYTO_UI:
        run_pyto_ui()
    else:
        print("Pyto UI not available, running in console mode")
        run_console_mode()


if __name__ == "__main__":
    main()
