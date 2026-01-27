"""Nesting configuration dialog for sheet layout optimization."""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class SheetSize:
    """Represents a sheet size configuration."""
    name: str
    width: float  # in inches or mm
    height: float
    unit: str = "in"  # "in" or "mm"
    
    def to_pixels(self, dpi: float = 150.0) -> Tuple[int, int]:
        """Convert to pixels at given DPI."""
        if self.unit == "mm":
            # Convert mm to inches first
            w_in = self.width / 25.4
            h_in = self.height / 25.4
        else:
            w_in = self.width
            h_in = self.height
        return (int(w_in * dpi), int(h_in * dpi))
    
    def __str__(self):
        return f"{self.name}: {self.width} x {self.height} {self.unit}"


@dataclass
class MaterialGroup:
    """Group of objects by material type."""
    material: str
    is_sheet: bool
    thickness: float
    objects: List[any] = field(default_factory=list)
    
    @property
    def object_count(self) -> int:
        return len(self.objects)


# Common sheet sizes
COMMON_SHEET_SIZES = [
    SheetSize("1/16 x 3 x 36 Balsa", 3.0, 36.0, "in"),
    SheetSize("1/8 x 3 x 36 Balsa", 3.0, 36.0, "in"),
    SheetSize("1/8 x 4 x 36 Balsa", 4.0, 36.0, "in"),
    SheetSize("3/16 x 3 x 36 Balsa", 3.0, 36.0, "in"),
    SheetSize("1/4 x 3 x 36 Balsa", 3.0, 36.0, "in"),
    SheetSize("3/32 x 4 x 12 Plywood", 4.0, 12.0, "in"),
    SheetSize("1/8 x 6 x 12 Plywood", 6.0, 12.0, "in"),
    SheetSize("1/8 x 12 x 12 Plywood", 12.0, 12.0, "in"),
    SheetSize("1/4 x 12 x 12 Plywood", 12.0, 12.0, "in"),
    SheetSize("A4 Paper", 210.0, 297.0, "mm"),
    SheetSize("Letter Paper", 8.5, 11.0, "in"),
]

# Common materials for model aircraft
MATERIAL_TYPES = [
    "Balsa",
    "Lite-Ply",
    "Plywood",
    "Basswood",
    "Spruce",
    "Hardwood",
    "Carbon Fiber",
    "Foam",
    "Other",
]

# Common thicknesses in inches
THICKNESS_OPTIONS = [
    "1/32",
    "1/16",
    "3/32",
    "1/8",
    "5/32",
    "3/16",
    "1/4",
    "5/16",
    "3/8",
    "1/2",
]


class NestingConfigDialog(tk.Toplevel):
    """
    Dialog to configure nesting parameters.
    
    Allows user to:
    - Select which page/objects to nest
    - Group objects by material and thickness
    - Define sheet sizes for each material group
    - Configure nesting parameters (spacing, rotation, etc.)
    """
    
    def __init__(self, parent, objects: List, pages: Dict, categories: Dict,
                 current_page_id: str, theme: Dict = None):
        super().__init__(parent)
        
        self.objects = objects
        self.pages = pages
        self.categories = categories
        self.current_page_id = current_page_id
        self.theme = theme or {}
        
        self.result: Optional[Dict] = None
        self.material_groups: List[MaterialGroup] = []
        self.sheet_configs: Dict[str, List[SheetSize]] = {}  # material -> sheet sizes
        
        self.title("Nesting Configuration")
        self.transient(parent)
        
        # Size and position
        width, height = 800, 600
        self.update_idletasks()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        px = parent.winfo_x()
        py = parent.winfo_y()
        x = px + (pw - width) // 2
        y = py + (ph - height) // 2
        self.geometry(f"{width}x{height}+{x}+{y}")
        
        self.grab_set()
        self._setup_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        
        # Analyze objects
        self._analyze_objects()
    
    def _setup_ui(self):
        """Setup the dialog UI."""
        # Apply theme if available
        bg = self.theme.get("bg", "#2b2b2b")
        fg = self.theme.get("fg", "#ffffff")
        self.configure(bg=bg)
        
        # Main container
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Top section: Source selection
        source_frame = ttk.LabelFrame(main_frame, text="Source", padding=5)
        source_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(source_frame, text="Nest objects from:").pack(side=tk.LEFT, padx=5)
        
        self.source_var = tk.StringVar(value="current_page")
        ttk.Radiobutton(source_frame, text="Current Page", variable=self.source_var,
                        value="current_page", command=self._analyze_objects).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(source_frame, text="All Pages", variable=self.source_var,
                        value="all_pages", command=self._analyze_objects).pack(side=tk.LEFT, padx=5)
        
        # Middle section: Two panes
        paned = ttk.PanedWindow(main_frame, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Left pane: Material groups
        left_frame = ttk.LabelFrame(paned, text="Material Groups", padding=5)
        paned.add(left_frame, weight=1)
        
        # Treeview for material groups
        self.groups_tree = ttk.Treeview(left_frame, columns=("count", "thickness"),
                                         show="tree headings", height=10)
        self.groups_tree.heading("#0", text="Material")
        self.groups_tree.heading("count", text="Objects")
        self.groups_tree.heading("thickness", text="Thickness")
        self.groups_tree.column("#0", width=150)
        self.groups_tree.column("count", width=60, anchor=tk.CENTER)
        self.groups_tree.column("thickness", width=80, anchor=tk.CENTER)
        
        groups_scroll = ttk.Scrollbar(left_frame, orient=tk.VERTICAL, command=self.groups_tree.yview)
        self.groups_tree.configure(yscrollcommand=groups_scroll.set)
        
        self.groups_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        groups_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.groups_tree.bind("<<TreeviewSelect>>", self._on_group_select)
        
        # Right pane: Sheet configuration
        right_frame = ttk.LabelFrame(paned, text="Sheet Sizes", padding=5)
        paned.add(right_frame, weight=1)
        
        # Sheet size list
        self.sheets_listbox = tk.Listbox(right_frame, height=8)
        sheets_scroll = ttk.Scrollbar(right_frame, orient=tk.VERTICAL, command=self.sheets_listbox.yview)
        self.sheets_listbox.configure(yscrollcommand=sheets_scroll.set)
        
        self.sheets_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sheets_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Sheet controls
        sheet_controls = ttk.Frame(right_frame)
        sheet_controls.pack(fill=tk.X, pady=5)
        
        ttk.Button(sheet_controls, text="Add Sheet Size", command=self._add_sheet_size).pack(side=tk.LEFT, padx=2)
        ttk.Button(sheet_controls, text="Remove", command=self._remove_sheet_size).pack(side=tk.LEFT, padx=2)
        
        # Preset dropdown
        ttk.Label(sheet_controls, text="Preset:").pack(side=tk.LEFT, padx=(10, 2))
        self.preset_var = tk.StringVar()
        preset_combo = ttk.Combobox(sheet_controls, textvariable=self.preset_var,
                                     values=[s.name for s in COMMON_SHEET_SIZES],
                                     width=20, state="readonly")
        preset_combo.pack(side=tk.LEFT, padx=2)
        preset_combo.bind("<<ComboboxSelected>>", self._on_preset_select)
        
        # Nesting options
        options_frame = ttk.LabelFrame(main_frame, text="Nesting Options", padding=5)
        options_frame.pack(fill=tk.X, pady=10)
        
        # Row 1: Spacing and rotation
        row1 = ttk.Frame(options_frame)
        row1.pack(fill=tk.X, pady=2)
        
        ttk.Label(row1, text="Part Spacing:").pack(side=tk.LEFT, padx=5)
        self.spacing_var = tk.StringVar(value="0.1")
        ttk.Entry(row1, textvariable=self.spacing_var, width=8).pack(side=tk.LEFT, padx=2)
        ttk.Label(row1, text="in").pack(side=tk.LEFT)
        
        ttk.Label(row1, text="   ").pack(side=tk.LEFT)
        
        self.rotate_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(row1, text="Allow 90° Rotation", variable=self.rotate_var).pack(side=tk.LEFT, padx=10)
        
        self.include_quantity_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(row1, text="Respect Quantity", variable=self.include_quantity_var).pack(side=tk.LEFT, padx=10)
        
        # Row 2: DPI
        row2 = ttk.Frame(options_frame)
        row2.pack(fill=tk.X, pady=2)
        
        ttk.Label(row2, text="Output DPI:").pack(side=tk.LEFT, padx=5)
        self.dpi_var = tk.StringVar(value="150")
        ttk.Entry(row2, textvariable=self.dpi_var, width=8).pack(side=tk.LEFT, padx=2)
        
        # Button row
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(button_frame, text="Cancel", command=self._on_cancel).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Start Nesting", command=self._on_ok).pack(side=tk.RIGHT, padx=5)
        
        # Status
        self.status_var = tk.StringVar(value="Analyzing objects...")
        ttk.Label(main_frame, textvariable=self.status_var).pack(fill=tk.X)
    
    def _analyze_objects(self):
        """Analyze objects and group by material."""
        self.material_groups.clear()
        
        # Get relevant objects based on source selection
        source = self.source_var.get()
        
        relevant_objects = []
        for obj in self.objects:
            # Skip special categories
            if obj.category in ["mark_text", "mark_hatch", "mark_line", "planform", "eraser"]:
                continue
            
            for inst in obj.instances:
                if source == "current_page" and inst.page_id != self.current_page_id:
                    continue
                
                # Check if instance has any elements with masks
                has_content = any(e.mask is not None for e in inst.elements)
                if has_content:
                    relevant_objects.append((obj, inst))
        
        # Group by material and thickness
        groups_dict: Dict[Tuple[str, str], List] = {}
        
        for obj, inst in relevant_objects:
            material = inst.attributes.material or "Unknown"
            thickness = str(inst.attributes.depth) if inst.attributes.depth else "Unknown"
            
            key = (material, thickness)
            if key not in groups_dict:
                groups_dict[key] = []
            groups_dict[key].append((obj, inst))
        
        # Create MaterialGroup objects
        for (material, thickness), obj_list in groups_dict.items():
            try:
                thickness_val = float(thickness) if thickness != "Unknown" else 0.0
            except ValueError:
                thickness_val = 0.0
            
            group = MaterialGroup(
                material=material,
                is_sheet=True,  # Assume all are sheet goods for now
                thickness=thickness_val,
                objects=obj_list
            )
            self.material_groups.append(group)
        
        # Update tree
        self._update_groups_tree()
        
        # Update status
        total_objects = sum(g.object_count for g in self.material_groups)
        self.status_var.set(f"Found {total_objects} objects in {len(self.material_groups)} material groups")
    
    def _update_groups_tree(self):
        """Update the material groups treeview."""
        self.groups_tree.delete(*self.groups_tree.get_children())
        
        for group in self.material_groups:
            thickness_str = f'{group.thickness}"' if group.thickness > 0 else "N/A"
            item_id = self.groups_tree.insert("", tk.END, text=group.material,
                                               values=(group.object_count, thickness_str))
            
            # Initialize sheet config if not exists
            group_key = f"{group.material}_{group.thickness}"
            if group_key not in self.sheet_configs:
                self.sheet_configs[group_key] = []
    
    def _on_group_select(self, event):
        """Handle group selection."""
        selection = self.groups_tree.selection()
        if not selection:
            return
        
        # Get selected group
        item = selection[0]
        material = self.groups_tree.item(item, "text")
        thickness = self.groups_tree.item(item, "values")[1]
        
        # Find matching group
        for group in self.material_groups:
            thickness_str = f'{group.thickness}"' if group.thickness > 0 else "N/A"
            if group.material == material and thickness_str == thickness:
                group_key = f"{group.material}_{group.thickness}"
                self._update_sheets_list(group_key)
                break
    
    def _update_sheets_list(self, group_key: str):
        """Update the sheets listbox for selected group."""
        self.sheets_listbox.delete(0, tk.END)
        
        sheets = self.sheet_configs.get(group_key, [])
        for sheet in sheets:
            self.sheets_listbox.insert(tk.END, str(sheet))
        
        # Store current group key
        self._current_group_key = group_key
    
    def _add_sheet_size(self):
        """Add a new sheet size to current group."""
        if not hasattr(self, '_current_group_key'):
            messagebox.showwarning("No Selection", "Please select a material group first.")
            return
        
        # Show add sheet dialog
        dialog = AddSheetSizeDialog(self, self.theme)
        self.wait_window(dialog)
        
        if dialog.result:
            sheet = dialog.result
            if self._current_group_key not in self.sheet_configs:
                self.sheet_configs[self._current_group_key] = []
            self.sheet_configs[self._current_group_key].append(sheet)
            self._update_sheets_list(self._current_group_key)
    
    def _remove_sheet_size(self):
        """Remove selected sheet size."""
        if not hasattr(self, '_current_group_key'):
            return
        
        selection = self.sheets_listbox.curselection()
        if not selection:
            return
        
        idx = selection[0]
        if self._current_group_key in self.sheet_configs:
            del self.sheet_configs[self._current_group_key][idx]
            self._update_sheets_list(self._current_group_key)
    
    def _on_preset_select(self, event):
        """Handle preset selection."""
        if not hasattr(self, '_current_group_key'):
            messagebox.showwarning("No Selection", "Please select a material group first.")
            return
        
        preset_name = self.preset_var.get()
        for sheet in COMMON_SHEET_SIZES:
            if sheet.name == preset_name:
                if self._current_group_key not in self.sheet_configs:
                    self.sheet_configs[self._current_group_key] = []
                self.sheet_configs[self._current_group_key].append(sheet)
                self._update_sheets_list(self._current_group_key)
                break
    
    def _on_ok(self):
        """Handle OK button - validate and return configuration."""
        # Validate that all groups have at least one sheet size
        groups_without_sheets = []
        for group in self.material_groups:
            group_key = f"{group.material}_{group.thickness}"
            if not self.sheet_configs.get(group_key):
                groups_without_sheets.append(group.material)
        
        if groups_without_sheets:
            messagebox.showwarning(
                "Missing Sheet Sizes",
                f"Please add sheet sizes for: {', '.join(groups_without_sheets)}"
            )
            return
        
        # Parse spacing
        try:
            spacing = float(self.spacing_var.get())
        except ValueError:
            spacing = 0.1
        
        # Parse DPI
        try:
            dpi = float(self.dpi_var.get())
        except ValueError:
            dpi = 150.0
        
        self.result = {
            "material_groups": self.material_groups,
            "sheet_configs": self.sheet_configs,
            "spacing": spacing,
            "allow_rotation": self.rotate_var.get(),
            "respect_quantity": self.include_quantity_var.get(),
            "dpi": dpi,
            "source": self.source_var.get(),
        }
        self.destroy()
    
    def _on_cancel(self):
        """Handle cancel button."""
        self.result = None
        self.destroy()


class AddSheetSizeDialog(tk.Toplevel):
    """Dialog to add a custom sheet size."""
    
    def __init__(self, parent, theme: Dict = None):
        super().__init__(parent)
        
        self.theme = theme or {}
        self.result: Optional[SheetSize] = None
        
        self.title("Add Sheet Size")
        self.transient(parent)
        
        width, height = 350, 200
        self.update_idletasks()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        px = parent.winfo_x()
        py = parent.winfo_y()
        x = px + (pw - width) // 2
        y = py + (ph - height) // 2
        self.geometry(f"{width}x{height}+{x}+{y}")
        
        self.grab_set()
        self._setup_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
    
    def _setup_ui(self):
        """Setup dialog UI."""
        main_frame = ttk.Frame(self, padding=15)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Name
        row1 = ttk.Frame(main_frame)
        row1.pack(fill=tk.X, pady=5)
        ttk.Label(row1, text="Name:", width=10).pack(side=tk.LEFT)
        self.name_var = tk.StringVar(value="Custom Sheet")
        ttk.Entry(row1, textvariable=self.name_var, width=25).pack(side=tk.LEFT, padx=5)
        
        # Width
        row2 = ttk.Frame(main_frame)
        row2.pack(fill=tk.X, pady=5)
        ttk.Label(row2, text="Width:", width=10).pack(side=tk.LEFT)
        self.width_var = tk.StringVar(value="3")
        ttk.Entry(row2, textvariable=self.width_var, width=10).pack(side=tk.LEFT, padx=5)
        
        # Height
        row3 = ttk.Frame(main_frame)
        row3.pack(fill=tk.X, pady=5)
        ttk.Label(row3, text="Height:", width=10).pack(side=tk.LEFT)
        self.height_var = tk.StringVar(value="36")
        ttk.Entry(row3, textvariable=self.height_var, width=10).pack(side=tk.LEFT, padx=5)
        
        # Unit
        row4 = ttk.Frame(main_frame)
        row4.pack(fill=tk.X, pady=5)
        ttk.Label(row4, text="Unit:", width=10).pack(side=tk.LEFT)
        self.unit_var = tk.StringVar(value="in")
        ttk.Radiobutton(row4, text="Inches", variable=self.unit_var, value="in").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(row4, text="Millimeters", variable=self.unit_var, value="mm").pack(side=tk.LEFT, padx=5)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=15)
        ttk.Button(button_frame, text="Cancel", command=self._on_cancel).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Add", command=self._on_ok).pack(side=tk.RIGHT, padx=5)
    
    def _on_ok(self):
        """Validate and return sheet size."""
        try:
            width = float(self.width_var.get())
            height = float(self.height_var.get())
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter valid numbers for width and height.")
            return
        
        if width <= 0 or height <= 0:
            messagebox.showerror("Invalid Input", "Width and height must be positive.")
            return
        
        self.result = SheetSize(
            name=self.name_var.get(),
            width=width,
            height=height,
            unit=self.unit_var.get()
        )
        self.destroy()
    
    def _on_cancel(self):
        """Handle cancel."""
        self.result = None
        self.destroy()
