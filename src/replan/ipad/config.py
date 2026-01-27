"""Configuration and Theme Management for iPad Segmenter.

Adapted from desktop version - uses iOS-compatible storage.
"""

import json
from dataclasses import dataclass, asdict, field
from typing import Dict, Any, List
import os

# iOS-compatible config path (in app's Documents folder)
def get_config_path():
    """Get config file path - works on iOS and desktop for testing."""
    # Try iOS Documents directory first
    docs_dir = os.path.expanduser("~/Documents")
    if os.path.exists(docs_dir):
        return os.path.join(docs_dir, ".planmod_segmenter_ipad.json")
    # Fallback to home directory
    return os.path.expanduser("~/.planmod_segmenter_ipad.json")

CONFIG_FILE = get_config_path()


@dataclass
class AppSettings:
    """
    Persistent application settings for iPad.
    
    Simplified from desktop version for touch-based interface.
    """
    # Appearance
    theme: str = "dark"
    
    # Tool defaults
    tolerance: int = 5
    line_thickness: int = 3
    planform_opacity: float = 0.5
    snap_distance: int = 15
    
    # Display preferences
    show_labels: bool = True
    show_grid: bool = False
    default_zoom: float = 1.0
    
    # Ruler settings
    show_ruler: bool = True
    ruler_unit: str = "inch"
    default_dpi: int = 150
    
    # Recent files
    last_workspace: str = ""
    recent_files: list = field(default_factory=list)
    max_recent_files: int = 10
    
    # iPad-specific settings
    pencil_sensitivity: float = 1.0
    haptic_feedback: bool = True
    double_tap_action: str = "undo"  # "undo", "zoom_fit", "none"
    
    def add_recent_file(self, path: str):
        """Add a file to recent files list."""
        if path in self.recent_files:
            self.recent_files.remove(path)
        self.recent_files.insert(0, path)
        self.recent_files = self.recent_files[:self.max_recent_files]


# iOS-optimized themes (supports dark mode)
THEMES: Dict[str, Dict[str, str]] = {
    "dark": {
        # Background hierarchy
        "bg_base": "#1c1c1e",           # iOS dark background
        "bg": "#2c2c2e",                 # Secondary background
        "bg_secondary": "#3a3a3c",       # Tertiary background
        "bg_tertiary": "#48484a",        # Quaternary background
        "bg_elevated": "#3a3a3c",
        
        # Foreground hierarchy
        "fg": "#ffffff",                 # Primary text
        "fg_muted": "#98989d",           # Secondary text
        "fg_subtle": "#636366",          # Tertiary text
        
        # Accent colors (iOS blue)
        "accent": "#0a84ff",
        "accent_hover": "#409cff",
        "accent_active": "#0077ed",
        
        # Semantic colors
        "success": "#30d158",
        "warning": "#ffd60a",
        "error": "#ff453a",
        "info": "#64d2ff",
        
        # Borders
        "border": "#38383a",
        "border_focus": "#0a84ff",
        
        # Canvas
        "canvas_bg": "#1c1c1e",
        
        # Selection
        "selection_bg": "#0a84ff",
        "selection_fg": "#ffffff",
        
        # List items
        "list_bg": "#2c2c2e",
        "list_hover": "#3a3a3c",
        "list_selected": "#0a84ff",
    },
    
    "light": {
        # Background hierarchy  
        "bg_base": "#ffffff",
        "bg": "#f2f2f7",
        "bg_secondary": "#e5e5ea",
        "bg_tertiary": "#d1d1d6",
        "bg_elevated": "#ffffff",
        
        # Foreground hierarchy
        "fg": "#000000",
        "fg_muted": "#3c3c43",
        "fg_subtle": "#8e8e93",
        
        # Accent colors
        "accent": "#007aff",
        "accent_hover": "#0056b3",
        "accent_active": "#004494",
        
        # Semantic colors
        "success": "#34c759",
        "warning": "#ff9500",
        "error": "#ff3b30",
        "info": "#5ac8fa",
        
        # Borders
        "border": "#c6c6c8",
        "border_focus": "#007aff",
        
        # Canvas
        "canvas_bg": "#ffffff",
        
        # Selection
        "selection_bg": "#007aff",
        "selection_fg": "#ffffff",
        
        # List items
        "list_bg": "#ffffff",
        "list_hover": "#f2f2f7",
        "list_selected": "#007aff",
    },
}


def load_settings() -> AppSettings:
    """Load settings from config file."""
    try:
        if os.path.exists(CONFIG_FILE):
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

