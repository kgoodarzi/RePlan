"""
UI module for iPad Segmenter.

Contains all UI components for the Pyto-based iPad interface:
- CanvasView: Touch-enabled drawing canvas
- ToolbarView: Tool selection and actions
- SidebarView: Category and object lists
- Dialogs: Attribute editing, settings, export options
"""

from replan.ipad.ui.canvas_view import CanvasView, TouchState
from replan.ipad.ui.toolbar import ToolbarView, ToolButton
from replan.ipad.ui.sidebar import SidebarView, CategoryRow, ObjectRow
from replan.ipad.ui.dialogs import (
    show_alert,
    show_confirm,
    AttributeDialog,
    SettingsDialog,
    ExportDialog,
    DialogResult,
)

__all__ = [
    # Canvas
    'CanvasView',
    'TouchState',
    
    # Toolbar
    'ToolbarView',
    'ToolButton',
    
    # Sidebar
    'SidebarView',
    'CategoryRow',
    'ObjectRow',
    
    # Dialogs
    'show_alert',
    'show_confirm',
    'AttributeDialog',
    'SettingsDialog',
    'ExportDialog',
    'DialogResult',
]
