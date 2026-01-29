"""Settings/Preferences dialog."""

import tkinter as tk
from tkinter import ttk
from typing import Dict, Optional, Callable

from replan.desktop.dialogs.base import BaseDialog
from replan.desktop.config import AppSettings, get_theme_names


class SettingsDialog(BaseDialog):
    """
    Modern settings dialog with tabbed interface.
    Similar to VS Code's settings UI.
    """
    
    def __init__(self, parent, settings: AppSettings, theme: dict,
                 on_save: Callable[[AppSettings], None] = None):
        self.settings = settings
        self.theme = theme
        self.on_save = on_save
        self.modified = False
        
        # Create copies of settings values
        self._init_values()
        
        super().__init__(parent, "Preferences", 600, 580)
        self.resizable(False, False)  # Fixed size dialog
    
    def _init_values(self):
        """Initialize setting values."""
        self.values = {
            # Appearance
            "theme": self.settings.theme,
            "ui_scale": self.settings.ui_scale,
            
            # Tools
            "tolerance": self.settings.tolerance,
            "line_thickness": self.settings.line_thickness,
            "snap_distance": self.settings.snap_distance,
            "planform_opacity": self.settings.planform_opacity,
            
            # Display
            "show_labels": self.settings.show_labels,
            "show_ruler": self.settings.show_ruler,
            "ruler_unit": self.settings.ruler_unit,
            "default_dpi": self.settings.default_dpi,
            "tree_density": self.settings.tree_density,
            
            # Behavior
            "auto_collapse_panels": self.settings.auto_collapse_panels,
            "auto_detect_text": self.settings.auto_detect_text,
            "auto_detect_hatch": self.settings.auto_detect_hatch,
            
            # OCR
            "ocr_backend": getattr(self.settings, 'ocr_backend', 'tesseract'),
            "aws_profile": getattr(self.settings, 'aws_profile', ''),
            "aws_region": getattr(self.settings, 'aws_region', 'us-east-1'),
        }
    
    def _setup_ui(self):
        """Setup the dialog UI."""
        t = self.theme
        self.configure(bg=t["bg"])
        
        # Notebook for tabs
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=16, pady=(16, 8))
        
        # Create tabs
        self._create_appearance_tab()
        self._create_tools_tab()
        self._create_display_tab()
        self._create_behavior_tab()
        self._create_ocr_tab()
        
        # Button frame
        btn_frame = tk.Frame(self, bg=t["bg"])
        btn_frame.pack(fill=tk.X, padx=16, pady=16)
        
        ttk.Button(btn_frame, text="Cancel", command=self._on_cancel).pack(side=tk.RIGHT, padx=(8, 0))
        ttk.Button(btn_frame, text="Save", style="Accent.TButton", command=self._on_save).pack(side=tk.RIGHT)
        ttk.Button(btn_frame, text="Reset to Defaults", command=self._reset_defaults).pack(side=tk.LEFT)
    
    def _create_appearance_tab(self):
        """Create appearance settings tab."""
        t = self.theme
        frame = tk.Frame(self.notebook, bg=t["bg"])
        self.notebook.add(frame, text="Appearance")
        
        # Theme
        self._add_section_header(frame, "Theme")
        
        theme_frame = tk.Frame(frame, bg=t["bg"])
        theme_frame.pack(fill=tk.X, padx=16, pady=8)
        
        tk.Label(theme_frame, text="Color Theme:", bg=t["bg"], fg=t["fg"]).pack(side=tk.LEFT)
        self.theme_var = tk.StringVar(value=self.values["theme"])
        theme_combo = ttk.Combobox(theme_frame, textvariable=self.theme_var,
                                   values=get_theme_names(), state="readonly", width=20)
        theme_combo.pack(side=tk.RIGHT)
        theme_combo.bind("<<ComboboxSelected>>", lambda e: self._mark_modified())
        
        # UI Scale
        scale_frame = tk.Frame(frame, bg=t["bg"])
        scale_frame.pack(fill=tk.X, padx=16, pady=8)
        
        tk.Label(scale_frame, text="UI Scale:", bg=t["bg"], fg=t["fg"]).pack(side=tk.LEFT)
        self.scale_var = tk.DoubleVar(value=self.values["ui_scale"])
        ttk.Scale(scale_frame, from_=0.8, to=1.5, variable=self.scale_var,
                 orient=tk.HORIZONTAL, length=150, command=lambda e: self._mark_modified()).pack(side=tk.RIGHT)
        
        tk.Label(frame, text="Note: Theme changes require restart to fully apply.",
                bg=t["bg"], fg=t["fg_subtle"], font=("Segoe UI", 9)).pack(anchor=tk.W, padx=16, pady=(16, 0))
    
    def _create_tools_tab(self):
        """Create tools settings tab."""
        t = self.theme
        frame = tk.Frame(self.notebook, bg=t["bg"])
        self.notebook.add(frame, text="Tools")
        
        self._add_section_header(frame, "Flood Fill")
        
        # Tolerance
        tol_frame = tk.Frame(frame, bg=t["bg"])
        tol_frame.pack(fill=tk.X, padx=16, pady=8)
        
        tk.Label(tol_frame, text="Color Tolerance:", bg=t["bg"], fg=t["fg"]).pack(side=tk.LEFT)
        self.tolerance_var = tk.IntVar(value=self.values["tolerance"])
        tol_spin = ttk.Spinbox(tol_frame, from_=0, to=50, textvariable=self.tolerance_var, width=8,
                              command=self._mark_modified)
        tol_spin.pack(side=tk.RIGHT)
        
        tk.Label(frame, text="Higher values select more similar colors (0-50)",
                bg=t["bg"], fg=t["fg_subtle"], font=("Segoe UI", 9)).pack(anchor=tk.W, padx=16)
        
        self._add_section_header(frame, "Drawing")
        
        # Line thickness
        thick_frame = tk.Frame(frame, bg=t["bg"])
        thick_frame.pack(fill=tk.X, padx=16, pady=8)
        
        tk.Label(thick_frame, text="Line Thickness:", bg=t["bg"], fg=t["fg"]).pack(side=tk.LEFT)
        self.thickness_var = tk.IntVar(value=self.values["line_thickness"])
        ttk.Spinbox(thick_frame, from_=1, to=20, textvariable=self.thickness_var, width=8,
                   command=self._mark_modified).pack(side=tk.RIGHT)
        
        # Snap distance
        snap_frame = tk.Frame(frame, bg=t["bg"])
        snap_frame.pack(fill=tk.X, padx=16, pady=8)
        
        tk.Label(snap_frame, text="Snap Distance:", bg=t["bg"], fg=t["fg"]).pack(side=tk.LEFT)
        self.snap_var = tk.IntVar(value=self.values["snap_distance"])
        ttk.Spinbox(snap_frame, from_=5, to=50, textvariable=self.snap_var, width=8,
                   command=self._mark_modified).pack(side=tk.RIGHT)
        
        self._add_section_header(frame, "Overlay")
        
        # Opacity
        opacity_frame = tk.Frame(frame, bg=t["bg"])
        opacity_frame.pack(fill=tk.X, padx=16, pady=8)
        
        tk.Label(opacity_frame, text="Planform Opacity:", bg=t["bg"], fg=t["fg"]).pack(side=tk.LEFT)
        self.opacity_var = tk.DoubleVar(value=self.values["planform_opacity"])
        ttk.Scale(opacity_frame, from_=0.0, to=1.0, variable=self.opacity_var,
                 orient=tk.HORIZONTAL, length=150, command=lambda e: self._mark_modified()).pack(side=tk.RIGHT)
    
    def _create_display_tab(self):
        """Create display settings tab."""
        t = self.theme
        frame = tk.Frame(self.notebook, bg=t["bg"])
        self.notebook.add(frame, text="Display")
        
        self._add_section_header(frame, "Labels")
        
        # Show labels
        self.labels_var = tk.BooleanVar(value=self.values["show_labels"])
        ttk.Checkbutton(frame, text="Show object labels on canvas",
                       variable=self.labels_var, command=self._mark_modified).pack(anchor=tk.W, padx=16, pady=8)
        
        self._add_section_header(frame, "Ruler")
        
        # Show ruler
        self.ruler_var = tk.BooleanVar(value=self.values["show_ruler"])
        ttk.Checkbutton(frame, text="Show ruler",
                       variable=self.ruler_var, command=self._mark_modified).pack(anchor=tk.W, padx=16, pady=8)
        
        # Ruler unit
        unit_frame = tk.Frame(frame, bg=t["bg"])
        unit_frame.pack(fill=tk.X, padx=16, pady=8)
        
        tk.Label(unit_frame, text="Ruler Unit:", bg=t["bg"], fg=t["fg"]).pack(side=tk.LEFT)
        self.unit_var = tk.StringVar(value=self.values["ruler_unit"])
        ttk.Combobox(unit_frame, textvariable=self.unit_var,
                    values=["inch", "cm"], state="readonly", width=10).pack(side=tk.RIGHT)
        
        self._add_section_header(frame, "PDF")
        
        # Default DPI
        dpi_frame = tk.Frame(frame, bg=t["bg"])
        dpi_frame.pack(fill=tk.X, padx=16, pady=8)
        
        tk.Label(dpi_frame, text="Default Rasterization DPI:", bg=t["bg"], fg=t["fg"]).pack(side=tk.LEFT)
        self.dpi_var = tk.IntVar(value=self.values["default_dpi"])
        ttk.Combobox(dpi_frame, textvariable=self.dpi_var,
                    values=[72, 100, 150, 200, 300], width=8).pack(side=tk.RIGHT)
        
        tk.Label(frame, text="Higher DPI = better quality but larger files",
                bg=t["bg"], fg=t["fg_subtle"], font=("Segoe UI", 9)).pack(anchor=tk.W, padx=16)
        
        self._add_section_header(frame, "Object List")
        
        # Tree density
        density_frame = tk.Frame(frame, bg=t["bg"])
        density_frame.pack(fill=tk.X, padx=16, pady=8)
        
        tk.Label(density_frame, text="List Density:", bg=t["bg"], fg=t["fg"]).pack(side=tk.LEFT)
        self.density_var = tk.StringVar(value=self.values["tree_density"])
        ttk.Combobox(density_frame, textvariable=self.density_var,
                    values=["comfortable", "compact"], state="readonly", width=12).pack(side=tk.RIGHT)
    
    def _create_behavior_tab(self):
        """Create behavior settings tab."""
        t = self.theme
        frame = tk.Frame(self.notebook, bg=t["bg"])
        self.notebook.add(frame, text="Behavior")
        
        self._add_section_header(frame, "Panels")
        
        # Auto collapse
        self.auto_collapse_var = tk.BooleanVar(value=self.values["auto_collapse_panels"])
        ttk.Checkbutton(frame, text="Auto-collapse panels on small screens",
                       variable=self.auto_collapse_var, command=self._mark_modified).pack(anchor=tk.W, padx=16, pady=8)
        
        tk.Label(frame, text="When enabled, panels will automatically collapse\nwhen the window is resized to a smaller size.",
                bg=t["bg"], fg=t["fg_subtle"], font=("Segoe UI", 9), justify=tk.LEFT).pack(anchor=tk.W, padx=16)
        
        self._add_section_header(frame, "Auto-Detection")
        
        # Auto detect text
        self.auto_detect_text_var = tk.BooleanVar(value=self.values["auto_detect_text"])
        ttk.Checkbutton(frame, text="Automatically detect text regions when pages are loaded",
                       variable=self.auto_detect_text_var, command=self._mark_modified).pack(anchor=tk.W, padx=16, pady=8)
        
        # Auto detect hatch
        self.auto_detect_hatch_var = tk.BooleanVar(value=self.values["auto_detect_hatch"])
        ttk.Checkbutton(frame, text="Automatically detect hatching regions when pages are loaded",
                       variable=self.auto_detect_hatch_var, command=self._mark_modified).pack(anchor=tk.W, padx=16, pady=8)
    
    def _create_ocr_tab(self):
        """Create OCR settings tab."""
        t = self.theme
        frame = tk.Frame(self.notebook, bg=t["bg"])
        self.notebook.add(frame, text="OCR")
        
        self._add_section_header(frame, "Backend Selection")
        
        # OCR Backend
        backend_frame = tk.Frame(frame, bg=t["bg"])
        backend_frame.pack(fill=tk.X, padx=16, pady=8)
        
        tk.Label(backend_frame, text="OCR Backend:", bg=t["bg"], fg=t["fg"]).pack(side=tk.LEFT)
        self.ocr_backend_var = tk.StringVar(value=self.values["ocr_backend"])
        backend_combo = ttk.Combobox(backend_frame, textvariable=self.ocr_backend_var,
                                     values=["tesseract", "aws", "google", "azure", "openai"],
                                     state="readonly", width=20)
        backend_combo.pack(side=tk.RIGHT)
        backend_combo.bind("<<ComboboxSelected>>", lambda e: self._mark_modified())
        
        tk.Label(frame, text="Select the OCR engine to use for text detection.",
                bg=t["bg"], fg=t["fg_subtle"], font=("Segoe UI", 9)).pack(anchor=tk.W, padx=16)
        
        self._add_section_header(frame, "AWS Configuration")
        
        # AWS Profile
        profile_frame = tk.Frame(frame, bg=t["bg"])
        profile_frame.pack(fill=tk.X, padx=16, pady=8)
        
        tk.Label(profile_frame, text="AWS Profile:", bg=t["bg"], fg=t["fg"]).pack(side=tk.LEFT)
        self.aws_profile_var = tk.StringVar(value=self.values["aws_profile"])
        profile_entry = ttk.Entry(profile_frame, textvariable=self.aws_profile_var, width=25)
        profile_entry.pack(side=tk.RIGHT)
        profile_entry.bind("<KeyRelease>", lambda e: self._mark_modified())
        
        tk.Label(frame, text="AWS profile name from ~/.aws/credentials (leave empty for default)",
                bg=t["bg"], fg=t["fg_subtle"], font=("Segoe UI", 9)).pack(anchor=tk.W, padx=16)
        
        # AWS Region
        region_frame = tk.Frame(frame, bg=t["bg"])
        region_frame.pack(fill=tk.X, padx=16, pady=8)
        
        tk.Label(region_frame, text="AWS Region:", bg=t["bg"], fg=t["fg"]).pack(side=tk.LEFT)
        self.aws_region_var = tk.StringVar(value=self.values["aws_region"])
        region_entry = ttk.Entry(region_frame, textvariable=self.aws_region_var, width=25)
        region_entry.pack(side=tk.RIGHT)
        region_entry.bind("<KeyRelease>", lambda e: self._mark_modified())
        
        tk.Label(frame, text="AWS region for Textract (e.g., us-east-1, eu-west-1)",
                bg=t["bg"], fg=t["fg_subtle"], font=("Segoe UI", 9)).pack(anchor=tk.W, padx=16)
    
    def _add_section_header(self, parent, text: str):
        """Add a section header."""
        t = self.theme
        header = tk.Label(parent, text=text.upper(), font=("Segoe UI", 9, "bold"),
                         bg=t["bg"], fg=t["fg_muted"])
        header.pack(anchor=tk.W, padx=16, pady=(16, 4))
        
        # Separator line
        sep = tk.Frame(parent, bg=t["border"], height=1)
        sep.pack(fill=tk.X, padx=16)
    
    def _mark_modified(self, *args):
        """Mark settings as modified."""
        self.modified = True
    
    def _reset_defaults(self):
        """Reset all settings to defaults."""
        defaults = AppSettings()
        
        self.theme_var.set(defaults.theme)
        self.scale_var.set(defaults.ui_scale)
        self.tolerance_var.set(defaults.tolerance)
        self.thickness_var.set(defaults.line_thickness)
        self.snap_var.set(defaults.snap_distance)
        self.opacity_var.set(defaults.planform_opacity)
        self.labels_var.set(defaults.show_labels)
        self.ruler_var.set(defaults.show_ruler)
        self.unit_var.set(defaults.ruler_unit)
        self.dpi_var.set(defaults.default_dpi)
        self.density_var.set(defaults.tree_density)
        self.auto_collapse_var.set(defaults.auto_collapse_panels)
        self.auto_detect_text_var.set(defaults.auto_detect_text)
        self.auto_detect_hatch_var.set(defaults.auto_detect_hatch)
        
        # OCR defaults
        if hasattr(defaults, 'ocr_backend'):
            self.ocr_backend_var.set(defaults.ocr_backend)
        if hasattr(defaults, 'aws_profile'):
            self.aws_profile_var.set(defaults.aws_profile)
        if hasattr(defaults, 'aws_region'):
            self.aws_region_var.set(defaults.aws_region)
        
        self.modified = True
    
    def _on_save(self):
        """Save settings and close."""
        # Update settings object
        self.settings.theme = self.theme_var.get()
        self.settings.ui_scale = self.scale_var.get()
        self.settings.tolerance = self.tolerance_var.get()
        self.settings.line_thickness = self.thickness_var.get()
        self.settings.snap_distance = self.snap_var.get()
        self.settings.planform_opacity = self.opacity_var.get()
        self.settings.show_labels = self.labels_var.get()
        self.settings.show_ruler = self.ruler_var.get()
        self.settings.ruler_unit = self.unit_var.get()
        self.settings.default_dpi = self.dpi_var.get()
        self.settings.tree_density = self.density_var.get()
        self.settings.auto_collapse_panels = self.auto_collapse_var.get()
        self.settings.auto_detect_text = self.auto_detect_text_var.get()
        self.settings.auto_detect_hatch = self.auto_detect_hatch_var.get()
        
        # OCR settings
        if hasattr(self.settings, 'ocr_backend'):
            self.settings.ocr_backend = self.ocr_backend_var.get()
        if hasattr(self.settings, 'aws_profile'):
            self.settings.aws_profile = self.aws_profile_var.get()
        if hasattr(self.settings, 'aws_region'):
            self.settings.aws_region = self.aws_region_var.get()
        
        self.result = self.settings
        
        if self.on_save:
            self.on_save(self.settings)
        
        self.destroy()

