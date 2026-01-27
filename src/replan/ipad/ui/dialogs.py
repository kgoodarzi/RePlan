"""
Dialog views for iPad Segmenter.

Modal dialogs for:
- Attribute editing
- Settings
- Export options
- PDF import
"""

from typing import Callable, Dict, List, Optional
from dataclasses import dataclass

try:
    import pyto_ui as ui
    HAS_UI = True
except ImportError:
    ui = None
    HAS_UI = False


@dataclass
class DialogResult:
    """Result from a dialog."""
    confirmed: bool = False
    data: Dict = None


def show_alert(title: str, message: str, on_dismiss: Callable = None):
    """Show a simple alert dialog."""
    if not HAS_UI:
        print(f"Alert: {title}\n{message}")
        return
    
    alert = ui.Alert(title, message)
    alert.add_action(ui.AlertAction("OK"))
    alert.show()


def show_confirm(title: str, message: str, 
                 on_confirm: Callable = None,
                 on_cancel: Callable = None):
    """Show a confirmation dialog."""
    if not HAS_UI:
        print(f"Confirm: {title}\n{message}")
        return
    
    alert = ui.Alert(title, message)
    alert.add_action(ui.AlertAction("Cancel", ui.AlertActionStyle.CANCEL))
    alert.add_action(ui.AlertAction("OK", ui.AlertActionStyle.DEFAULT))
    
    def handle_action(action_index):
        if action_index == 1 and on_confirm:
            on_confirm()
        elif action_index == 0 and on_cancel:
            on_cancel()
    
    # Note: Pyto's alert handling may differ
    alert.show()


class AttributeDialog:
    """
    Dialog for editing object/instance attributes.
    
    Displays fields for:
    - Name
    - Material
    - Type
    - View
    - Dimensions (W, H, D)
    - Quantity
    - Description
    - URL
    """
    
    MATERIALS = [
        "balsa", "basswood", "plywood", "lite-ply", "spruce",
        "hardwood", "foam", "depron", "carbon fiber", "fiberglass",
        "wire", "aluminum", "plastic", "covering", "complex", "other"
    ]
    
    TYPES = [
        "stick", "sheet", "block", "tube", "dowel", "electrical",
        "hardware", "covering", "control surface", "structural", "other"
    ]
    
    VIEWS = [
        "top", "side", "front", "rear", "isometric",
        "section", "detail", "template", "cutout"
    ]
    
    def __init__(self, name: str = "", attributes: Dict = None,
                 on_save: Callable = None, on_cancel: Callable = None):
        """
        Initialize the attribute dialog.
        
        Args:
            name: Object name
            attributes: Current attribute values
            on_save: Callback with new values
            on_cancel: Callback when cancelled
        """
        self.name = name
        self.attributes = attributes or {}
        self.on_save = on_save
        self.on_cancel = on_cancel
        
        self.view = None
        self.fields = {}
    
    def show(self):
        """Show the dialog."""
        if not HAS_UI:
            print(f"AttributeDialog: {self.name}")
            return
        
        # Create modal view
        self.view = ui.View()
        self.view.background_color = ui.Color.rgb(0.15, 0.15, 0.16)
        
        # Title
        title = ui.Label(f"Attributes: {self.name}")
        title.text_color = ui.Color.white()
        title.font = ui.Font.bold_system_font_of_size(18)
        title.frame = (20, 20, 300, 30)
        self.view.add_subview(title)
        
        y = 60
        
        # Name field
        y = self._add_text_field("name", "Name:", self.name, y)
        
        # Material picker
        y = self._add_picker_field("material", "Material:", 
                                   self.MATERIALS, 
                                   self.attributes.get("material", ""), y)
        
        # Type picker
        y = self._add_picker_field("type", "Type:", 
                                   self.TYPES,
                                   self.attributes.get("obj_type", ""), y)
        
        # View picker
        y = self._add_picker_field("view", "View:",
                                   self.VIEWS,
                                   self.attributes.get("view", ""), y)
        
        # Dimensions
        y = self._add_dimension_fields(y)
        
        # Quantity
        y = self._add_text_field("quantity", "Quantity:", 
                                str(self.attributes.get("quantity", 1)), y)
        
        # Description
        y = self._add_text_field("description", "Description:",
                                self.attributes.get("description", ""), y, height=60)
        
        # Buttons
        self._add_buttons(y + 20)
        
        # Present modally
        self.view.present()
    
    def _add_text_field(self, key: str, label: str, value: str, 
                        y: int, height: int = 32) -> int:
        """Add a text field."""
        lbl = ui.Label(label)
        lbl.text_color = ui.Color.rgb(0.7, 0.7, 0.7)
        lbl.font = ui.Font.system_font_of_size(14)
        lbl.frame = (20, y, 100, 24)
        self.view.add_subview(lbl)
        
        field = ui.TextField()
        field.text = value
        field.background_color = ui.Color.rgb(0.2, 0.2, 0.21)
        field.text_color = ui.Color.white()
        field.frame = (120, y, 200, height)
        self.view.add_subview(field)
        
        self.fields[key] = field
        return y + height + 10
    
    def _add_picker_field(self, key: str, label: str, 
                          options: List[str], value: str, y: int) -> int:
        """Add a picker field."""
        lbl = ui.Label(label)
        lbl.text_color = ui.Color.rgb(0.7, 0.7, 0.7)
        lbl.font = ui.Font.system_font_of_size(14)
        lbl.frame = (20, y, 100, 24)
        self.view.add_subview(lbl)
        
        # Use a button that shows a picker
        btn = ui.Button()
        btn.title = value or "Select..."
        btn.background_color = ui.Color.rgb(0.2, 0.2, 0.21)
        btn.tint_color = ui.Color.white()
        btn.frame = (120, y, 200, 32)
        self.view.add_subview(btn)
        
        # Store options for picker
        btn._options = options
        btn._key = key
        
        self.fields[key] = btn
        return y + 42
    
    def _add_dimension_fields(self, y: int) -> int:
        """Add dimension fields (W, H, D)."""
        lbl = ui.Label("Size:")
        lbl.text_color = ui.Color.rgb(0.7, 0.7, 0.7)
        lbl.font = ui.Font.system_font_of_size(14)
        lbl.frame = (20, y, 100, 24)
        self.view.add_subview(lbl)
        
        x = 120
        for dim, key in [("W:", "width"), ("H:", "height"), ("D:", "depth")]:
            dim_lbl = ui.Label(dim)
            dim_lbl.text_color = ui.Color.rgb(0.6, 0.6, 0.6)
            dim_lbl.font = ui.Font.system_font_of_size(12)
            dim_lbl.frame = (x, y, 20, 24)
            self.view.add_subview(dim_lbl)
            
            field = ui.TextField()
            field.text = str(self.attributes.get(key, ""))
            field.background_color = ui.Color.rgb(0.2, 0.2, 0.21)
            field.text_color = ui.Color.white()
            field.frame = (x + 20, y, 45, 28)
            self.view.add_subview(field)
            
            self.fields[key] = field
            x += 70
        
        return y + 40
    
    def _add_buttons(self, y: int):
        """Add Save and Cancel buttons."""
        cancel_btn = ui.Button()
        cancel_btn.title = "Cancel"
        cancel_btn.background_color = ui.Color.rgb(0.3, 0.3, 0.31)
        cancel_btn.tint_color = ui.Color.white()
        cancel_btn.frame = (20, y, 100, 40)
        cancel_btn.action = self._on_cancel
        self.view.add_subview(cancel_btn)
        
        save_btn = ui.Button()
        save_btn.title = "Save"
        save_btn.background_color = ui.Color.rgb(0.04, 0.52, 1.0)
        save_btn.tint_color = ui.Color.white()
        save_btn.frame = (140, y, 100, 40)
        save_btn.action = self._on_save
        self.view.add_subview(save_btn)
    
    def _on_save(self, sender):
        """Handle save button."""
        if self.on_save:
            data = self._collect_data()
            self.on_save(data)
        
        if self.view:
            self.view.close()
    
    def _on_cancel(self, sender):
        """Handle cancel button."""
        if self.on_cancel:
            self.on_cancel()
        
        if self.view:
            self.view.close()
    
    def _collect_data(self) -> Dict:
        """Collect field values."""
        data = {}
        
        for key, field in self.fields.items():
            if hasattr(field, 'text'):
                data[key] = field.text
            elif hasattr(field, 'title'):
                data[key] = field.title
        
        return data


class SettingsDialog:
    """Dialog for app settings."""
    
    def __init__(self, settings: Dict = None,
                 on_save: Callable = None):
        self.settings = settings or {}
        self.on_save = on_save
        self.view = None
    
    def show(self):
        """Show the settings dialog."""
        if not HAS_UI:
            print("Settings dialog")
            return
        
        self.view = ui.View()
        self.view.background_color = ui.Color.rgb(0.15, 0.15, 0.16)
        
        title = ui.Label("Settings")
        title.text_color = ui.Color.white()
        title.font = ui.Font.bold_system_font_of_size(18)
        title.frame = (20, 20, 200, 30)
        self.view.add_subview(title)
        
        y = 70
        
        # Theme selector
        theme_lbl = ui.Label("Theme:")
        theme_lbl.text_color = ui.Color.rgb(0.7, 0.7, 0.7)
        theme_lbl.frame = (20, y, 100, 24)
        self.view.add_subview(theme_lbl)
        
        # Tolerance slider
        y += 50
        tol_lbl = ui.Label("Flood Fill Tolerance:")
        tol_lbl.text_color = ui.Color.rgb(0.7, 0.7, 0.7)
        tol_lbl.frame = (20, y, 150, 24)
        self.view.add_subview(tol_lbl)
        
        # Line thickness slider
        y += 50
        line_lbl = ui.Label("Line Thickness:")
        line_lbl.text_color = ui.Color.rgb(0.7, 0.7, 0.7)
        line_lbl.frame = (20, y, 150, 24)
        self.view.add_subview(line_lbl)
        
        # Show labels toggle
        y += 50
        labels_lbl = ui.Label("Show Labels:")
        labels_lbl.text_color = ui.Color.rgb(0.7, 0.7, 0.7)
        labels_lbl.frame = (20, y, 150, 24)
        self.view.add_subview(labels_lbl)
        
        # Close button
        y += 80
        close_btn = ui.Button()
        close_btn.title = "Done"
        close_btn.background_color = ui.Color.rgb(0.04, 0.52, 1.0)
        close_btn.tint_color = ui.Color.white()
        close_btn.frame = (20, y, 100, 40)
        close_btn.action = lambda s: self.view.close()
        self.view.add_subview(close_btn)
        
        self.view.present()


class ExportDialog:
    """Dialog for export options."""
    
    def __init__(self, on_export: Callable = None):
        self.on_export = on_export
        self.view = None
    
    def show(self):
        """Show export options."""
        if not HAS_UI:
            print("Export dialog")
            return
        
        # Use action sheet for export options
        alert = ui.Alert("Export", "Choose export format:")
        alert.add_action(ui.AlertAction("Segmented Image (PNG)"))
        alert.add_action(ui.AlertAction("Masks Only"))
        alert.add_action(ui.AlertAction("Data (JSON)"))
        alert.add_action(ui.AlertAction("Bill of Materials"))
        alert.add_action(ui.AlertAction("Cancel", ui.AlertActionStyle.CANCEL))
        alert.show()

