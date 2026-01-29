"""
Configuration and Theme Management for RePlan.

Modern VS Code/Cursor-inspired themes with responsive layout support.
"""

import json
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import Dict, Any, List

CONFIG_FILE = Path.home() / ".replan.json"


# Layout breakpoints (window width in pixels)
class Breakpoints:
    MINIMAL = 700    # Single panel mode
    COMPACT = 1000   # Auto-hide sidebars
    STANDARD = 1400  # Collapsible object panel
    FULL = 1800      # All panels visible


@dataclass
class PanelState:
    """State of a dockable panel."""
    visible: bool = True
    width: int = 280
    collapsed: bool = False
    pinned: bool = True


@dataclass
class AppSettings:
    """
    Persistent application settings.
    
    Saved between sessions to preserve user preferences.
    """
    # Appearance
    theme: str = "dark"
    ui_scale: float = 1.0  # For high DPI support
    
    # Tool defaults
    tolerance: int = 5
    line_thickness: int = 3
    planform_opacity: float = 0.5
    snap_distance: int = 15
    
    # Window state
    window_width: int = 1400
    window_height: int = 900
    window_x: int = 100
    window_y: int = 100
    window_maximized: bool = False
    
    # Panel states
    sidebar_width: int = 260
    sidebar_visible: bool = True
    sidebar_collapsed: bool = False
    
    tree_width: int = 260  # Same as sidebar by default
    tree_visible: bool = True
    tree_collapsed: bool = False
    
    # Recent files
    last_workspace: str = ""
    recent_files: list = field(default_factory=list)
    max_recent_files: int = 10
    
    # Display preferences
    show_labels: bool = True
    show_grid: bool = False
    default_zoom: float = 1.0
    tree_density: str = "comfortable"  # "comfortable", "compact"
    
    # Ruler settings
    show_ruler: bool = True
    ruler_unit: str = "inch"
    default_dpi: int = 150
    
    # Responsive behavior
    auto_collapse_panels: bool = True
    compact_toolbar: bool = False
    
    # Auto-detection
    auto_detect_text: bool = False  # Automatically detect text regions when pages are loaded
    auto_detect_hatch: bool = False  # Automatically detect hatching regions when pages are loaded
    
    def add_recent_file(self, path: str):
        """Add a file to recent files list."""
        if path in self.recent_files:
            self.recent_files.remove(path)
        self.recent_files.insert(0, path)
        self.recent_files = self.recent_files[:self.max_recent_files]


# VS Code / Cursor inspired themes
THEMES: Dict[str, Dict[str, str]] = {
    "dark": {
        # Background hierarchy (darkest to lightest)
        "bg_base": "#1e1e1e",           # Editor background
        "bg": "#252526",                 # Sidebar background
        "bg_secondary": "#2d2d30",       # Panel backgrounds
        "bg_tertiary": "#3c3c3c",        # Hover states
        "bg_elevated": "#37373d",        # Dropdowns, menus
        "bg_input": "#3c3c3c",           # Input fields
        
        # Foreground hierarchy
        "fg": "#cccccc",                 # Primary text
        "fg_muted": "#9d9d9d",           # Secondary text
        "fg_subtle": "#6e6e6e",          # Disabled/hint text
        "fg_accent": "#ffffff",          # Emphasized text
        
        # Accent colors (Cursor blue)
        "accent": "#0078d4",             # Primary accent
        "accent_hover": "#1c8ae6",       # Hover state
        "accent_active": "#0066b8",      # Active/pressed
        "accent_muted": "#264f78",       # Subtle accent bg
        
        # Semantic colors
        "success": "#4ec9b0",
        "warning": "#dcdcaa",
        "error": "#f14c4c",
        "info": "#75beff",
        
        # Borders
        "border": "#3c3c3c",             # Subtle borders
        "border_focus": "#0078d4",       # Focus rings
        "border_active": "#007acc",      # Active borders
        
        # Canvas
        "canvas_bg": "#1e1e1e",
        
        # Interactive elements
        "button_bg": "#0e639c",
        "button_fg": "#ffffff",
        "button_hover": "#1177bb",
        "button_secondary_bg": "#3c3c3c",
        "button_secondary_fg": "#cccccc",
        "button_secondary_hover": "#4c4c4c",
        
        # Input fields
        "input_bg": "#3c3c3c",
        "input_fg": "#cccccc",
        "input_border": "#3c3c3c",
        "input_focus": "#007acc",
        "input_placeholder": "#6e6e6e",
        
        # Selection
        "selection_bg": "#264f78",
        "selection_fg": "#ffffff",
        
        # Tree view / Lists
        "list_bg": "#252526",
        "list_fg": "#cccccc",
        "list_hover": "#2a2d2e",
        "list_active": "#37373d",
        "list_selected": "#094771",
        "list_selected_unfocused": "#37373d",
        
        # Scrollbars
        "scrollbar_bg": "transparent",
        "scrollbar_thumb": "#424242",
        "scrollbar_thumb_hover": "#4f4f4f",
        
        # Tab bar
        "tab_bg": "#2d2d30",
        "tab_fg": "#969696",
        "tab_active_bg": "#1e1e1e",
        "tab_active_fg": "#ffffff",
        "tab_border": "#252526",
        
        # Activity bar
        "activity_bg": "#333333",
        "activity_fg": "#858585",
        "activity_active": "#ffffff",
        "activity_indicator": "#0078d4",
        
        # Status bar
        "status_bg": "#007acc",
        "status_fg": "#ffffff",
        
        # Panel headers
        "panel_header_bg": "#252526",
        "panel_header_fg": "#bbbbbb",
        
        # Menus
        "menu_bg": "#2d2d30",
        "menu_fg": "#cccccc",
        "menu_hover": "#094771",
        "menu_separator": "#454545",
        
        # Tooltips
        "tooltip_bg": "#252526",
        "tooltip_fg": "#cccccc",
        "tooltip_border": "#454545",
        
        # Shadows
        "shadow": "rgba(0, 0, 0, 0.36)",
    },
    
    "light": {
        # Background hierarchy
        "bg_base": "#ffffff",
        "bg": "#f3f3f3",
        "bg_secondary": "#eaeaea",
        "bg_tertiary": "#e5e5e5",
        "bg_elevated": "#ffffff",
        "bg_input": "#ffffff",
        
        # Foreground hierarchy
        "fg": "#333333",
        "fg_muted": "#616161",
        "fg_subtle": "#9e9e9e",
        "fg_accent": "#000000",
        
        # Accent colors
        "accent": "#0078d4",
        "accent_hover": "#106ebe",
        "accent_active": "#005a9e",
        "accent_muted": "#c2e0ff",
        
        # Semantic colors
        "success": "#16825d",
        "warning": "#9d5d00",
        "error": "#e51400",
        "info": "#1a85ff",
        
        # Borders
        "border": "#d4d4d4",
        "border_focus": "#0078d4",
        "border_active": "#005a9e",
        
        # Canvas
        "canvas_bg": "#ffffff",
        
        # Interactive elements
        "button_bg": "#0078d4",
        "button_fg": "#ffffff",
        "button_hover": "#106ebe",
        "button_secondary_bg": "#e5e5e5",
        "button_secondary_fg": "#333333",
        "button_secondary_hover": "#d4d4d4",
        
        # Input fields
        "input_bg": "#ffffff",
        "input_fg": "#333333",
        "input_border": "#cecece",
        "input_focus": "#0078d4",
        "input_placeholder": "#9e9e9e",
        
        # Selection
        "selection_bg": "#add6ff",
        "selection_fg": "#000000",
        
        # Tree view / Lists
        "list_bg": "#f3f3f3",
        "list_fg": "#333333",
        "list_hover": "#e8e8e8",
        "list_active": "#e4e4e4",
        "list_selected": "#0078d4",
        "list_selected_unfocused": "#e4e4e4",
        
        # Scrollbars
        "scrollbar_bg": "transparent",
        "scrollbar_thumb": "#c1c1c1",
        "scrollbar_thumb_hover": "#a8a8a8",
        
        # Tab bar
        "tab_bg": "#ececec",
        "tab_fg": "#616161",
        "tab_active_bg": "#ffffff",
        "tab_active_fg": "#333333",
        "tab_border": "#f3f3f3",
        
        # Activity bar
        "activity_bg": "#2c2c2c",
        "activity_fg": "#858585",
        "activity_active": "#ffffff",
        "activity_indicator": "#0078d4",
        
        # Status bar
        "status_bg": "#007acc",
        "status_fg": "#ffffff",
        
        # Panel headers
        "panel_header_bg": "#f3f3f3",
        "panel_header_fg": "#616161",
        
        # Menus
        "menu_bg": "#ffffff",
        "menu_fg": "#333333",
        "menu_hover": "#0078d4",
        "menu_separator": "#d4d4d4",
        
        # Tooltips
        "tooltip_bg": "#f3f3f3",
        "tooltip_fg": "#333333",
        "tooltip_border": "#d4d4d4",
        
        # Shadows
        "shadow": "rgba(0, 0, 0, 0.16)",
    },
    
    "high_contrast": {
        # High contrast dark for accessibility
        "bg_base": "#000000",
        "bg": "#000000",
        "bg_secondary": "#000000",
        "bg_tertiary": "#1a1a1a",
        "bg_elevated": "#000000",
        "bg_input": "#000000",
        
        "fg": "#ffffff",
        "fg_muted": "#ffffff",
        "fg_subtle": "#cccccc",
        "fg_accent": "#ffffff",
        
        "accent": "#1aebff",
        "accent_hover": "#6fffff",
        "accent_active": "#1aebff",
        "accent_muted": "#003b49",
        
        "success": "#89d185",
        "warning": "#f5f543",
        "error": "#f88070",
        "info": "#6fc3df",
        
        "border": "#6fc3df",
        "border_focus": "#f38518",
        "border_active": "#f38518",
        
        "canvas_bg": "#000000",
        
        "button_bg": "#000000",
        "button_fg": "#ffffff",
        "button_hover": "#1a1a1a",
        "button_secondary_bg": "#000000",
        "button_secondary_fg": "#ffffff",
        "button_secondary_hover": "#1a1a1a",
        
        "input_bg": "#000000",
        "input_fg": "#ffffff",
        "input_border": "#6fc3df",
        "input_focus": "#f38518",
        "input_placeholder": "#cccccc",
        
        "selection_bg": "#f38518",
        "selection_fg": "#000000",
        
        "list_bg": "#000000",
        "list_fg": "#ffffff",
        "list_hover": "#1a1a1a",
        "list_active": "#1a1a1a",
        "list_selected": "#f38518",
        "list_selected_unfocused": "#1a1a1a",
        
        "scrollbar_bg": "#000000",
        "scrollbar_thumb": "#6fc3df",
        "scrollbar_thumb_hover": "#1aebff",
        
        "tab_bg": "#000000",
        "tab_fg": "#ffffff",
        "tab_active_bg": "#000000",
        "tab_active_fg": "#ffffff",
        "tab_border": "#6fc3df",
        
        "activity_bg": "#000000",
        "activity_fg": "#ffffff",
        "activity_active": "#ffffff",
        "activity_indicator": "#f38518",
        
        "status_bg": "#000000",
        "status_fg": "#ffffff",
        
        "panel_header_bg": "#000000",
        "panel_header_fg": "#ffffff",
        
        "menu_bg": "#000000",
        "menu_fg": "#ffffff",
        "menu_hover": "#f38518",
        "menu_separator": "#6fc3df",
        
        "tooltip_bg": "#000000",
        "tooltip_fg": "#ffffff",
        "tooltip_border": "#6fc3df",
        
        "shadow": "none",
    },
}


def load_settings() -> AppSettings:
    """Load settings from config file."""
    try:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                known_fields = {f.name for f in AppSettings.__dataclass_fields__.values()}
                filtered = {k: v for k, v in data.items() if k in known_fields}
                return AppSettings(**filtered)
    except Exception as e:
        print(f"Warning: Could not load settings: {e}")
    return AppSettings()


def save_settings(settings: AppSettings):
    """Save settings to config file."""
    try:
        data = asdict(settings)
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Warning: Could not save settings: {e}")


def get_theme(name: str) -> Dict[str, str]:
    """Get theme colors by name."""
    return THEMES.get(name, THEMES["dark"])


def get_theme_names() -> list:
    """Get list of available theme names."""
    return list(THEMES.keys())


def get_layout_mode(width: int) -> str:
    """Determine layout mode based on window width."""
    if width < Breakpoints.MINIMAL:
        return "minimal"
    elif width < Breakpoints.COMPACT:
        return "compact"
    elif width < Breakpoints.STANDARD:
        return "standard"
    else:
        return "full"
