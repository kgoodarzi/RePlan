"""Transformation dialog for scale, rotate, and mirror operations."""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional, Tuple
from replan.desktop.dialogs.base import BaseDialog


class TransformDialog(BaseDialog):
    """Dialog for specifying transformations (scale, rotate, mirror)."""
    
    def __init__(self, parent, theme: dict, transform_type: str = "scale"):
        """
        Initialize transformation dialog.
        
        Args:
            parent: Parent window
            theme: Theme dictionary
            transform_type: Type of transformation - "scale", "rotate", or "mirror"
        """
        self.transform_type = transform_type
        self.theme = theme
        self.result: Optional[dict] = None
        super().__init__(parent, title=f"{transform_type.capitalize()} Objects", width=400, height=200)
        self.configure(bg=theme["bg"])
    
    def _setup_ui(self):
        """Create the dialog UI."""
        t = self.theme
        
        # Main frame
        main_frame = tk.Frame(self, bg=t["bg"])
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        if self.transform_type == "scale":
            # Scale transformation
            tk.Label(main_frame, text="Scale Factor:", bg=t["bg"], fg=t["fg"], 
                    font=("Segoe UI", 10)).pack(anchor=tk.W, pady=(0, 5))
            
            scale_frame = tk.Frame(main_frame, bg=t["bg"])
            scale_frame.pack(fill=tk.X, pady=(0, 10))
            
            self.scale_var = tk.DoubleVar(value=1.0)
            scale_spin = ttk.Spinbox(scale_frame, from_=0.1, to=10.0, 
                                     increment=0.1, textvariable=self.scale_var, width=10)
            scale_spin.pack(side=tk.LEFT, padx=(0, 10))
            
            tk.Label(scale_frame, text="(1.0 = 100%, 2.0 = 200%, etc.)", 
                    bg=t["bg"], fg=t["fg_subtle"], font=("Segoe UI", 9)).pack(side=tk.LEFT)
            
            # Center point option
            center_frame = tk.Frame(main_frame, bg=t["bg"])
            center_frame.pack(fill=tk.X, pady=(0, 10))
            
            self.center_var = tk.BooleanVar(value=True)
            center_check = tk.Checkbutton(center_frame, text="Scale around center of selection",
                                          variable=self.center_var, bg=t["bg"], fg=t["fg"],
                                          selectcolor=t["bg"], font=("Segoe UI", 9))
            center_check.pack(anchor=tk.W)
            
        elif self.transform_type == "rotate":
            # Rotation transformation
            tk.Label(main_frame, text="Rotation Angle (degrees):", bg=t["bg"], fg=t["fg"],
                    font=("Segoe UI", 10)).pack(anchor=tk.W, pady=(0, 5))
            
            angle_frame = tk.Frame(main_frame, bg=t["bg"])
            angle_frame.pack(fill=tk.X, pady=(0, 10))
            
            self.angle_var = tk.DoubleVar(value=0.0)
            angle_spin = ttk.Spinbox(angle_frame, from_=-360, to=360,
                                     increment=1.0, textvariable=self.angle_var, width=10)
            angle_spin.pack(side=tk.LEFT, padx=(0, 10))
            
            tk.Label(angle_frame, text="(positive = clockwise, negative = counter-clockwise)",
                    bg=t["bg"], fg=t["fg_subtle"], font=("Segoe UI", 9)).pack(side=tk.LEFT)
            
            # Center point option
            center_frame = tk.Frame(main_frame, bg=t["bg"])
            center_frame.pack(fill=tk.X, pady=(0, 10))
            
            self.center_var = tk.BooleanVar(value=True)
            center_check = tk.Checkbutton(center_frame, text="Rotate around center of selection",
                                          variable=self.center_var, bg=t["bg"], fg=t["fg"],
                                          selectcolor=t["bg"], font=("Segoe UI", 9))
            center_check.pack(anchor=tk.W)
            
        elif self.transform_type == "mirror":
            # Mirror transformation
            tk.Label(main_frame, text="Mirror Axis:", bg=t["bg"], fg=t["fg"],
                    font=("Segoe UI", 10)).pack(anchor=tk.W, pady=(0, 10))
            
            self.axis_var = tk.StringVar(value="horizontal")
            
            axis_frame = tk.Frame(main_frame, bg=t["bg"])
            axis_frame.pack(fill=tk.X, pady=(0, 10))
            
            tk.Radiobutton(axis_frame, text="Horizontal (flip vertically)",
                          variable=self.axis_var, value="horizontal",
                          bg=t["bg"], fg=t["fg"], selectcolor=t["bg"],
                          font=("Segoe UI", 9), anchor=tk.W).pack(fill=tk.X, pady=(0, 5))
            
            tk.Radiobutton(axis_frame, text="Vertical (flip horizontally)",
                          variable=self.axis_var, value="vertical",
                          bg=t["bg"], fg=t["fg"], selectcolor=t["bg"],
                          font=("Segoe UI", 9), anchor=tk.W).pack(fill=tk.X)
        
        # Buttons
        button_frame = tk.Frame(main_frame, bg=t["bg"])
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(button_frame, text="Cancel", command=self._on_cancel).pack(side=tk.RIGHT, padx=(8, 0))
        ttk.Button(button_frame, text="Apply", style="Accent.TButton", command=self._on_apply).pack(side=tk.RIGHT)
    
    def _on_apply(self):
        """Handle apply button."""
        if self.transform_type == "scale":
            scale = self.scale_var.get()
            if scale <= 0:
                messagebox.showerror("Invalid Scale", "Scale factor must be greater than 0.", parent=self)
                return
            self.result = {
                "type": "scale",
                "scale": scale,
                "around_center": self.center_var.get()
            }
        elif self.transform_type == "rotate":
            angle = self.angle_var.get()
            self.result = {
                "type": "rotate",
                "angle": angle,
                "around_center": self.center_var.get()
            }
        elif self.transform_type == "mirror":
            self.result = {
                "type": "mirror",
                "axis": self.axis_var.get()
            }
        
        self.destroy()
    
    def _on_cancel(self):
        """Handle cancel button."""
        self.result = None
        self.destroy()
