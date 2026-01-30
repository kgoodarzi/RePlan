"""Print preview dialog with page setup and tile configuration."""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional
import cv2
import numpy as np
from PIL import Image, ImageTk

from replan.desktop.dialogs.base import BaseDialog
from replan.desktop.models import PageTab, DynamicCategory
from replan.desktop.io.printing import ScaledPrinter, PrintSettings, get_recommended_settings


class PrintPreviewDialog(BaseDialog):
    """Dialog for print preview and configuration."""
    
    def __init__(self, parent, theme: dict, page: PageTab, categories: dict):
        """
        Initialize print preview dialog.
        
        Args:
            parent: Parent window
            theme: Theme dictionary
            page: Page to preview
            categories: Category definitions
        """
        self.page = page
        self.categories = categories
        self.theme = theme
        self.printer = ScaledPrinter()
        self.settings = get_recommended_settings(page)
        self.result: Optional[PrintSettings] = None
        self.preview_image = None
        self.preview_photo = None
        
        super().__init__(parent, title="Print Preview", width=900, height=700)
        self.configure(bg=theme["bg"])
    
    def _setup_ui(self):
        """Create the dialog UI."""
        t = self.theme
        
        # Main container
        main_frame = tk.Frame(self, bg=t["bg"])
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Left side: Settings
        settings_frame = tk.Frame(main_frame, bg=t["bg"], width=300)
        settings_frame.pack(side=tk.LEFT, fill=tk.BOTH, padx=(0, 10))
        settings_frame.pack_propagate(False)
        
        # Right side: Preview
        preview_frame = tk.Frame(main_frame, bg=t["bg"])
        preview_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        self._create_settings_panel(settings_frame)
        self._create_preview_panel(preview_frame)
        
        # Buttons
        button_frame = tk.Frame(main_frame, bg=t["bg"])
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(button_frame, text="Cancel", command=self._on_cancel).pack(side=tk.RIGHT, padx=(8, 0))
        ttk.Button(button_frame, text="Print", style="Accent.TButton", command=self._on_print).pack(side=tk.RIGHT)
        ttk.Button(button_frame, text="Export PNG", command=self._on_export).pack(side=tk.RIGHT, padx=(0, 8))
    
    def _create_settings_panel(self, parent):
        """Create settings panel."""
        t = self.theme
        
        # Paper size
        paper_frame = tk.LabelFrame(parent, text="Paper Size", bg=t["bg"], fg=t["fg"])
        paper_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.paper_var = tk.StringVar(value="letter")
        papers = [
            ("Letter (8.5\" x 11\")", "letter", 8.5, 11.0),
            ("Legal (8.5\" x 14\")", "legal", 8.5, 14.0),
            ("Tabloid (11\" x 17\")", "tabloid", 11.0, 17.0),
            ("A4 (8.27\" x 11.69\")", "a4", 8.27, 11.69),
        ]
        
        for text, value, w, h in papers:
            rb = tk.Radiobutton(paper_frame, text=text, variable=self.paper_var, value=value,
                              bg=t["bg"], fg=t["fg"], selectcolor=t["bg"],
                              command=lambda w=w, h=h: self._on_paper_change(w, h))
            rb.pack(anchor=tk.W, padx=10, pady=2)
        
        # Print settings
        settings_frame = tk.LabelFrame(parent, text="Print Settings", bg=t["bg"], fg=t["fg"])
        settings_frame.pack(fill=tk.X, pady=(0, 10))
        
        # DPI
        dpi_frame = tk.Frame(settings_frame, bg=t["bg"])
        dpi_frame.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(dpi_frame, text="DPI:", bg=t["bg"], fg=t["fg"]).pack(side=tk.LEFT)
        self.dpi_var = tk.DoubleVar(value=self.settings.target_dpi)
        ttk.Spinbox(dpi_frame, from_=150, to=600, increment=50, textvariable=self.dpi_var,
                   width=10, command=self._update_preview).pack(side=tk.RIGHT)
        
        # Margins
        margin_frame = tk.Frame(settings_frame, bg=t["bg"])
        margin_frame.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(margin_frame, text="Margins (inches):", bg=t["bg"], fg=t["fg"]).pack(side=tk.LEFT)
        self.margin_var = tk.DoubleVar(value=self.settings.margin_inches)
        ttk.Spinbox(margin_frame, from_=0.0, to=2.0, increment=0.1, textvariable=self.margin_var,
                   width=10, command=self._update_preview).pack(side=tk.RIGHT)
        
        # Options
        options_frame = tk.Frame(settings_frame, bg=t["bg"])
        options_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.labels_var = tk.BooleanVar(value=self.settings.include_labels)
        tk.Checkbutton(options_frame, text="Include Labels", variable=self.labels_var,
                      bg=t["bg"], fg=t["fg"], selectcolor=t["bg"],
                      command=self._update_preview).pack(anchor=tk.W)
        
        self.scale_bar_var = tk.BooleanVar(value=self.settings.include_scale_bar)
        tk.Checkbutton(options_frame, text="Include Scale Bar", variable=self.scale_bar_var,
                      bg=t["bg"], fg=t["fg"], selectcolor=t["bg"],
                      command=self._update_preview).pack(anchor=tk.W)
        
        # Tile printing
        tile_frame = tk.LabelFrame(parent, text="Tile Printing", bg=t["bg"], fg=t["fg"])
        tile_frame.pack(fill=tk.X)
        
        self.tile_var = tk.BooleanVar(value=self.printer.needs_tiling(self.page, self.settings))
        tk.Checkbutton(tile_frame, text="Enable Tile Printing", variable=self.tile_var,
                      bg=t["bg"], fg=t["fg"], selectcolor=t["bg"],
                      command=self._update_preview).pack(anchor=tk.W, padx=10, pady=5)
        
        if self.tile_var.get():
            tiles = self.printer.calculate_tiles(self.page, self.settings)
            tk.Label(tile_frame, text=f"Will create {len(tiles)} tile(s)",
                    bg=t["bg"], fg=t["fg_subtle"], font=("Segoe UI", 9)).pack(anchor=tk.W, padx=10, pady=(0, 5))
    
    def _create_preview_panel(self, parent):
        """Create preview panel."""
        t = self.theme
        
        # Preview label
        label = tk.Label(parent, text="Preview", bg=t["bg"], fg=t["fg"], font=("Segoe UI", 12, "bold"))
        label.pack(anchor=tk.W, pady=(0, 10))
        
        # Canvas with scrollbars
        canvas_frame = tk.Frame(parent, bg=t["bg"])
        canvas_frame.pack(fill=tk.BOTH, expand=True)
        
        h_scroll = ttk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL)
        h_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        
        v_scroll = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.preview_canvas = tk.Canvas(canvas_frame, bg=t["bg"], highlightthickness=0,
                                        xscrollcommand=h_scroll.set, yscrollcommand=v_scroll.set)
        self.preview_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        h_scroll.config(command=self.preview_canvas.xview)
        v_scroll.config(command=self.preview_canvas.yview)
        
        # Update preview
        self._update_preview()
    
    def _on_paper_change(self, width: float, height: float):
        """Handle paper size change."""
        self.settings.paper_width_inches = width
        self.settings.paper_height_inches = height
        self._update_preview()
    
    def _update_preview(self):
        """Update preview image."""
        # Update settings
        self.settings.target_dpi = self.dpi_var.get()
        self.settings.margin_inches = self.margin_var.get()
        self.settings.include_labels = self.labels_var.get()
        self.settings.include_scale_bar = self.scale_bar_var.get()
        
        # Generate preview
        try:
            preview_image = self.printer.prepare_print_image(self.page, self.categories, self.settings)
            
            # Resize for preview (max 800px width)
            h, w = preview_image.shape[:2]
            scale = min(800.0 / w, 600.0 / h, 1.0)
            preview_w = int(w * scale)
            preview_h = int(h * scale)
            
            if scale < 1.0:
                preview_image = cv2.resize(preview_image, (preview_w, preview_h), interpolation=cv2.INTER_AREA)
            
            # Convert to PIL Image
            preview_rgb = cv2.cvtColor(preview_image, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(preview_rgb)
            self.preview_photo = ImageTk.PhotoImage(pil_image)
            
            # Update canvas
            self.preview_canvas.delete("all")
            self.preview_canvas.create_image(0, 0, anchor=tk.NW, image=self.preview_photo)
            self.preview_canvas.config(scrollregion=self.preview_canvas.bbox("all"))
            
            self.preview_image = preview_image
        except Exception as e:
            messagebox.showerror("Preview Error", f"Error generating preview: {e}", parent=self)
    
    def _on_print(self):
        """Handle print button."""
        self.result = self.settings
        self.destroy()
    
    def _on_export(self):
        """Handle export button."""
        from tkinter import filedialog
        path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG files", "*.png"), ("All files", "*.*")],
            parent=self
        )
        if path:
            try:
                cv2.imwrite(path, self.preview_image)
                messagebox.showinfo("Export", f"Image exported to {path}", parent=self)
            except Exception as e:
                messagebox.showerror("Export Error", f"Error exporting image: {e}", parent=self)
    
    def _on_cancel(self):
        """Handle cancel button."""
        self.result = None
        self.destroy()
