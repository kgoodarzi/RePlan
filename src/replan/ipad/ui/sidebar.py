"""
Sidebar view for iPad Segmenter.

Contains category list and object hierarchy.
"""

from typing import Callable, Dict, List, Optional, Set

try:
    import pyto_ui as ui
    HAS_UI = True
except ImportError:
    ui = None
    HAS_UI = False


class CategoryRow:
    """A single category row in the sidebar."""
    
    def __init__(self, key: str, name: str, color: tuple, visible: bool = True):
        self.key = key
        self.name = name
        self.color = color
        self.visible = visible
        self.view = None
    
    def create_view(self, on_select: Callable, on_visibility: Callable) -> Optional[object]:
        """Create the row view."""
        if not HAS_UI:
            return None
        
        row = ui.View()
        row.background_color = ui.Color.rgb(0.17, 0.17, 0.18)
        
        # Color indicator
        color_view = ui.View()
        color_view.background_color = ui.Color.rgb(
            self.color[0] / 255,
            self.color[1] / 255,
            self.color[2] / 255
        )
        color_view.corner_radius = 4
        color_view.frame = (10, 10, 20, 20)
        row.add_subview(color_view)
        
        # Name label
        label = ui.Label(self.name)
        label.text_color = ui.Color.white()
        label.font = ui.Font.system_font_of_size(14)
        label.frame = (40, 8, 150, 24)
        row.add_subview(label)
        
        # Visibility toggle
        toggle = ui.Button()
        toggle.title = "👁" if self.visible else "👁‍🗨"
        toggle.font = ui.Font.system_font_of_size(18)
        toggle.frame = (200, 8, 30, 24)
        toggle.action = lambda s: on_visibility(self.key)
        row.add_subview(toggle)
        
        self.view = row
        return row


class ObjectRow:
    """A single object row in the object list."""
    
    def __init__(self, object_id: str, name: str, category: str, 
                 color: tuple, instance_count: int = 1):
        self.object_id = object_id
        self.name = name
        self.category = category
        self.color = color
        self.instance_count = instance_count
        self.is_selected = False
        self.is_expanded = False
        self.view = None
    
    def create_view(self, on_select: Callable, on_expand: Callable) -> Optional[object]:
        """Create the row view."""
        if not HAS_UI:
            return None
        
        row = ui.View()
        
        if self.is_selected:
            row.background_color = ui.Color.rgb(0.04, 0.52, 1.0)
        else:
            row.background_color = ui.Color.rgb(0.17, 0.17, 0.18)
        
        # Expand arrow (if has multiple instances)
        if self.instance_count > 1:
            arrow = ui.Label("›" if not self.is_expanded else "⌄")
            arrow.text_color = ui.Color.rgb(0.6, 0.6, 0.65)
            arrow.font = ui.Font.system_font_of_size(12)
            arrow.frame = (5, 10, 15, 20)
            row.add_subview(arrow)
        
        # Color indicator
        color_view = ui.View()
        color_view.background_color = ui.Color.rgb(
            self.color[0] / 255,
            self.color[1] / 255,
            self.color[2] / 255
        )
        color_view.corner_radius = 3
        color_view.frame = (22, 12, 14, 14)
        row.add_subview(color_view)
        
        # Name label
        label = ui.Label(self.name)
        label.text_color = ui.Color.white()
        label.font = ui.Font.system_font_of_size(13)
        label.frame = (42, 8, 130, 22)
        row.add_subview(label)
        
        # Instance count badge
        if self.instance_count > 1:
            badge = ui.Label(f"×{self.instance_count}")
            badge.text_color = ui.Color.rgb(0.6, 0.6, 0.65)
            badge.font = ui.Font.system_font_of_size(11)
            badge.frame = (175, 10, 30, 18)
            row.add_subview(badge)
        
        self.view = row
        return row


class SidebarView:
    """
    Sidebar containing categories and objects.
    
    Two sections:
    1. Categories - with visibility toggles
    2. Objects - hierarchical list with selection
    """
    
    def __init__(self, 
                 on_category_selected: Callable = None,
                 on_category_visibility: Callable = None,
                 on_object_selected: Callable = None,
                 theme: Dict[str, str] = None):
        """
        Initialize the sidebar.
        
        Args:
            on_category_selected: Callback when category tapped
            on_category_visibility: Callback for visibility toggle
            on_object_selected: Callback when object selected
            theme: Theme dictionary
        """
        self.on_category_selected = on_category_selected
        self.on_category_visibility = on_category_visibility
        self.on_object_selected = on_object_selected
        self.theme = theme or {}
        
        self.current_category = "R"
        self.selected_object_ids: Set[str] = set()
        
        self.category_rows: Dict[str, CategoryRow] = {}
        self.object_rows: Dict[str, ObjectRow] = {}
        
        self.view = None
        self._setup_view()
    
    def _setup_view(self):
        """Create the sidebar view."""
        if not HAS_UI:
            return
        
        self.view = ui.View()
        self.view.background_color = ui.Color.rgb(0.11, 0.11, 0.12)
        
        # Categories header
        cat_header = ui.Label("CATEGORIES")
        cat_header.text_color = ui.Color.rgb(0.6, 0.6, 0.65)
        cat_header.font = ui.Font.bold_system_font_of_size(11)
        cat_header.frame = (10, 10, 200, 20)
        self.view.add_subview(cat_header)
        
        # Category list container
        self.category_container = ui.View()
        self.category_container.frame = (0, 35, 240, 200)
        self.view.add_subview(self.category_container)
        
        # Objects header
        obj_header = ui.Label("OBJECTS")
        obj_header.text_color = ui.Color.rgb(0.6, 0.6, 0.65)
        obj_header.font = ui.Font.bold_system_font_of_size(11)
        obj_header.frame = (10, 245, 200, 20)
        self.view.add_subview(obj_header)
        
        # Object list container (scrollable)
        self.object_container = ui.ScrollView()
        self.object_container.frame = (0, 270, 240, 400)
        self.view.add_subview(self.object_container)
    
    def set_categories(self, categories: Dict):
        """Update the category list."""
        if not HAS_UI:
            return
        
        # Clear existing
        for row in self.category_rows.values():
            if row.view:
                row.view.remove_from_superview()
        self.category_rows.clear()
        
        # Add categories
        y_offset = 0
        row_height = 40
        
        for key, cat in categories.items():
            row = CategoryRow(
                key=key,
                name=cat.full_name,
                color=cat.color_rgb,
                visible=cat.visible
            )
            
            view = row.create_view(
                on_select=self._on_category_tap,
                on_visibility=self._on_visibility_tap
            )
            
            if view:
                view.frame = (0, y_offset, 240, row_height)
                self.category_container.add_subview(view)
            
            self.category_rows[key] = row
            y_offset += row_height + 2
    
    def set_objects(self, objects: List):
        """Update the object list."""
        if not HAS_UI:
            return
        
        # Clear existing
        for row in self.object_rows.values():
            if row.view:
                row.view.remove_from_superview()
        self.object_rows.clear()
        
        # Add objects
        y_offset = 0
        row_height = 38
        
        for obj in objects:
            row = ObjectRow(
                object_id=obj.object_id,
                name=obj.name,
                category=obj.category,
                color=obj.instances[0].elements[0].color if obj.instances and obj.instances[0].elements else (128, 128, 128),
                instance_count=len(obj.instances)
            )
            row.is_selected = obj.object_id in self.selected_object_ids
            
            view = row.create_view(
                on_select=self._on_object_tap,
                on_expand=self._on_object_expand
            )
            
            if view:
                view.frame = (0, y_offset, 240, row_height)
                self.object_container.add_subview(view)
            
            self.object_rows[obj.object_id] = row
            y_offset += row_height + 1
        
        # Update scroll content size
        self.object_container.content_size = (240, y_offset + 50)
    
    def _on_category_tap(self, key: str):
        """Handle category selection."""
        self.current_category = key
        if self.on_category_selected:
            self.on_category_selected(key)
    
    def _on_visibility_tap(self, key: str):
        """Handle visibility toggle."""
        if key in self.category_rows:
            row = self.category_rows[key]
            row.visible = not row.visible
        
        if self.on_category_visibility:
            self.on_category_visibility(key)
    
    def _on_object_tap(self, object_id: str):
        """Handle object selection."""
        if self.on_object_selected:
            self.on_object_selected(object_id)
    
    def _on_object_expand(self, object_id: str):
        """Handle object expansion."""
        if object_id in self.object_rows:
            row = self.object_rows[object_id]
            row.is_expanded = not row.is_expanded
            # Rebuild object list to show/hide instances
    
    def select_objects(self, object_ids: Set[str]):
        """Update object selection."""
        self.selected_object_ids = object_ids
        
        for obj_id, row in self.object_rows.items():
            row.is_selected = obj_id in object_ids
            if row.view and HAS_UI:
                if row.is_selected:
                    row.view.background_color = ui.Color.rgb(0.04, 0.52, 1.0)
                else:
                    row.view.background_color = ui.Color.rgb(0.17, 0.17, 0.18)
    
    def get_width(self) -> int:
        """Get sidebar width."""
        return 240

