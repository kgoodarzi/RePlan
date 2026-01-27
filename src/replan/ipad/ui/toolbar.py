"""
Toolbar view for iPad Segmenter.

Provides tool selection and common actions.
"""

from typing import Callable, Dict, Optional

try:
    import pyto_ui as ui
    HAS_UI = True
except ImportError:
    ui = None
    HAS_UI = False


class ToolButton:
    """A single tool button."""
    
    def __init__(self, name: str, icon: str, action: Callable, tooltip: str = ""):
        self.name = name
        self.icon = icon
        self.action = action
        self.tooltip = tooltip
        self.is_selected = False
        self.button = None
    
    def create_button(self, theme: Dict[str, str]) -> Optional[object]:
        """Create the UI button."""
        if not HAS_UI:
            return None
        
        btn = ui.Button()
        btn.title = self.icon
        btn.font = ui.Font.system_font_of_size(24)
        
        if self.is_selected:
            btn.background_color = ui.Color.rgb(0.04, 0.52, 1.0)  # iOS blue
            btn.tint_color = ui.Color.white()
        else:
            btn.background_color = ui.Color.rgb(0.17, 0.17, 0.18)
            btn.tint_color = ui.Color.rgb(0.6, 0.6, 0.65)
        
        btn.corner_radius = 8
        btn.action = self._on_tap
        
        self.button = btn
        return btn
    
    def _on_tap(self, sender):
        """Handle button tap."""
        if self.action:
            self.action(self.name)
    
    def set_selected(self, selected: bool, theme: Dict[str, str]):
        """Update selection state."""
        self.is_selected = selected
        
        if self.button and HAS_UI:
            if selected:
                self.button.background_color = ui.Color.rgb(0.04, 0.52, 1.0)
                self.button.tint_color = ui.Color.white()
            else:
                self.button.background_color = ui.Color.rgb(0.17, 0.17, 0.18)
                self.button.tint_color = ui.Color.rgb(0.6, 0.6, 0.65)


class ToolbarView:
    """
    Toolbar for tool selection and actions.
    
    Contains:
    - Drawing tool buttons (select, flood, polyline, freeform, line)
    - Action buttons (undo, delete, zoom fit)
    - Mode indicator
    """
    
    TOOLS = [
        ("select", "👆", "Select objects"),
        ("flood", "🪣", "Flood fill"),
        ("polyline", "⬡", "Draw polygon"),
        ("freeform", "✏️", "Freeform brush"),
        ("line", "📏", "Line segments"),
    ]
    
    ACTIONS = [
        ("undo", "↩️", "Undo"),
        ("delete", "🗑️", "Delete selected"),
        ("zoom_fit", "🔍", "Zoom to fit"),
    ]
    
    def __init__(self, on_tool_selected: Callable = None,
                 on_action: Callable = None,
                 theme: Dict[str, str] = None):
        """
        Initialize the toolbar.
        
        Args:
            on_tool_selected: Callback when tool changes
            on_action: Callback for action buttons
            theme: Theme dictionary
        """
        self.on_tool_selected = on_tool_selected
        self.on_action = on_action
        self.theme = theme or {}
        
        self.current_tool = "flood"
        self.tool_buttons: Dict[str, ToolButton] = {}
        self.action_buttons: Dict[str, ToolButton] = {}
        
        self.view = None
        self._setup_view()
    
    def _setup_view(self):
        """Create the toolbar view."""
        if not HAS_UI:
            return
        
        self.view = ui.View()
        self.view.background_color = ui.Color.rgb(0.11, 0.11, 0.12)
        
        # Create horizontal stack for tools
        x_offset = 10
        button_size = 44
        spacing = 8
        
        # Tool buttons
        for name, icon, tooltip in self.TOOLS:
            btn = ToolButton(name, icon, self._on_tool_tap, tooltip)
            btn.is_selected = (name == self.current_tool)
            button = btn.create_button(self.theme)
            
            if button:
                button.frame = (x_offset, 8, button_size, button_size)
                self.view.add_subview(button)
            
            self.tool_buttons[name] = btn
            x_offset += button_size + spacing
        
        # Separator
        x_offset += spacing
        
        # Action buttons
        for name, icon, tooltip in self.ACTIONS:
            btn = ToolButton(name, icon, self._on_action_tap, tooltip)
            button = btn.create_button(self.theme)
            
            if button:
                button.frame = (x_offset, 8, button_size, button_size)
                self.view.add_subview(button)
            
            self.action_buttons[name] = btn
            x_offset += button_size + spacing
    
    def _on_tool_tap(self, tool_name: str):
        """Handle tool button tap."""
        self.select_tool(tool_name)
        
        if self.on_tool_selected:
            self.on_tool_selected(tool_name)
    
    def _on_action_tap(self, action_name: str):
        """Handle action button tap."""
        if self.on_action:
            self.on_action(action_name)
    
    def select_tool(self, tool_name: str):
        """Select a tool."""
        if tool_name not in self.tool_buttons:
            return
        
        self.current_tool = tool_name
        
        for name, btn in self.tool_buttons.items():
            btn.set_selected(name == tool_name, self.theme)
    
    def get_height(self) -> int:
        """Get toolbar height."""
        return 60

