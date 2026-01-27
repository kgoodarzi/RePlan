"""Attribute editing dialog."""

import tkinter as tk
from tkinter import ttk

from replan.desktop.dialogs.base import BaseDialog
from replan.desktop.models import ObjectAttributes, ObjectInstance, MATERIALS, TYPES, VIEWS


class AttributeDialog(BaseDialog):
    """Dialog for editing instance attributes and object name."""
    
    def __init__(self, parent, instance: ObjectInstance, obj_name: str = ""):
        self.instance = instance
        self.obj_name = obj_name
        self.new_name = None  # Will hold new name if changed
        title = f"Attributes: {obj_name} (Instance {instance.instance_num})" if obj_name else f"Instance {instance.instance_num}"
        super().__init__(parent, title, 420, 520)
    
    def _setup_ui(self):
        main = ttk.Frame(self)
        main.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        attrs = self.instance.attributes
        
        # Object Name (at top)
        ttk.Label(main, text="Name:", font=('TkDefaultFont', 9, 'bold')).grid(row=0, column=0, sticky="w", pady=5)
        self.name_var = tk.StringVar(value=self.obj_name)
        ttk.Entry(main, textvariable=self.name_var, width=28).grid(row=0, column=1, pady=5, sticky="w")
        
        ttk.Separator(main, orient='horizontal').grid(row=1, column=0, columnspan=2, sticky="ew", pady=10)
        
        # Material
        ttk.Label(main, text="Material:").grid(row=2, column=0, sticky="w", pady=5)
        self.material_var = tk.StringVar(value=attrs.material)
        ttk.Combobox(main, textvariable=self.material_var, 
                     values=MATERIALS, width=25).grid(row=2, column=1, pady=5)
        
        # Type
        ttk.Label(main, text="Type:").grid(row=3, column=0, sticky="w", pady=5)
        self.type_var = tk.StringVar(value=attrs.obj_type)
        ttk.Combobox(main, textvariable=self.type_var,
                     values=TYPES, width=25).grid(row=3, column=1, pady=5)
        
        # View
        ttk.Label(main, text="View:").grid(row=4, column=0, sticky="w", pady=5)
        self.view_var = tk.StringVar(value=attrs.view)
        ttk.Combobox(main, textvariable=self.view_var,
                     values=VIEWS, width=25).grid(row=4, column=1, pady=5)
        
        # Size frame
        size_frame = ttk.LabelFrame(main, text="Size")
        size_frame.grid(row=5, column=0, columnspan=2, sticky="ew", pady=10)
        
        self.width_var = tk.StringVar(value=str(attrs.width) if attrs.width else "")
        self.height_var = tk.StringVar(value=str(attrs.height) if attrs.height else "")
        self.depth_var = tk.StringVar(value=str(attrs.depth) if attrs.depth else "")
        
        ttk.Label(size_frame, text="W:").grid(row=0, column=0, padx=5, pady=5)
        ttk.Entry(size_frame, textvariable=self.width_var, width=8).grid(row=0, column=1)
        ttk.Label(size_frame, text="H:").grid(row=0, column=2, padx=5)
        ttk.Entry(size_frame, textvariable=self.height_var, width=8).grid(row=0, column=3)
        ttk.Label(size_frame, text="D:").grid(row=0, column=4, padx=5)
        ttk.Entry(size_frame, textvariable=self.depth_var, width=8).grid(row=0, column=5)
        
        # Quantity
        ttk.Label(main, text="Quantity:").grid(row=6, column=0, sticky="w", pady=5)
        self.quantity_var = tk.StringVar(value=str(attrs.quantity))
        ttk.Entry(main, textvariable=self.quantity_var, width=8).grid(row=6, column=1, sticky="w", pady=5)
        
        # Description
        ttk.Label(main, text="Description:").grid(row=7, column=0, sticky="nw", pady=5)
        self.desc_text = tk.Text(main, width=30, height=3)
        self.desc_text.grid(row=7, column=1, pady=5)
        self.desc_text.insert("1.0", attrs.description)
        
        # URL
        ttk.Label(main, text="URL/Spec:").grid(row=8, column=0, sticky="w", pady=5)
        self.url_var = tk.StringVar(value=attrs.url)
        ttk.Entry(main, textvariable=self.url_var, width=28).grid(row=8, column=1, pady=5)
        
        # Buttons
        btn_frame = self._create_button_frame("Save", "Cancel")
        btn_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)
    
    def _on_ok(self):
        try:
            w = float(self.width_var.get()) if self.width_var.get() else 0.0
            h = float(self.height_var.get()) if self.height_var.get() else 0.0
            d = float(self.depth_var.get()) if self.depth_var.get() else 0.0
            qty = int(self.quantity_var.get()) if self.quantity_var.get() else 1
        except ValueError:
            w = h = d = 0.0
            qty = 1
        
        # Store new name if changed
        new_name = self.name_var.get().strip()
        if new_name and new_name != self.obj_name:
            self.new_name = new_name
        
        self.result = ObjectAttributes(
            material=self.material_var.get(),
            width=w, height=h, depth=d,
            obj_type=self.type_var.get(),
            view=self.view_var.get(),
            description=self.desc_text.get("1.0", tk.END).strip(),
            url=self.url_var.get(),
            quantity=qty,
        )
        self.destroy()

