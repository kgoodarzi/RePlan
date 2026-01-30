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
        """Handle print button - send to printer spooler."""
        if self.preview_image is None:
            messagebox.showerror("Print Error", "No preview image available", parent=self)
            return
        
        try:
            # Convert BGR to RGB for PIL
            rgb_image = cv2.cvtColor(self.preview_image, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(rgb_image)
            
            # Use PIL's print functionality (works on Windows, macOS, Linux)
            # This opens the system print dialog
            pil_image.show()  # This will open in default image viewer
            
            # For actual printing, we need to use platform-specific code
            import platform
            if platform.system() == "Windows":
                # Windows: Use win32print if available, otherwise fall back to PIL
                try:
                    from PIL import ImageWin
                    import win32print
                    import win32ui
                    
                    # Get default printer
                    printer_name = win32print.GetDefaultPrinter()
                    hprinter = win32print.OpenPrinter(printer_name)
                    try:
                        hdc = win32ui.CreateDC()
                        hdc.CreatePrinterDC(printer_name)
                        hdc.StartDoc("RePlan Print")
                        hdc.StartPage()
                        
                        # Calculate scaling to fit page
                        printer_size = hdc.GetDeviceCaps(110), hdc.GetDeviceCaps(111)  # HORZRES, VERTRES
                        printer_dpi = hdc.GetDeviceCaps(88), hdc.GetDeviceCaps(90)  # LOGPIXELSX, LOGPIXELSY
                        
                        # Scale image to fit printable area
                        img_width = pil_image.width
                        img_height = pil_image.height
                        scale_x = printer_size[0] / img_width
                        scale_y = printer_size[1] / img_height
                        scale = min(scale_x, scale_y, 1.0)  # Don't scale up
                        
                        new_width = int(img_width * scale)
                        new_height = int(img_height * scale)
                        
                        # Center image
                        x = (printer_size[0] - new_width) // 2
                        y = (printer_size[1] - new_height) // 2
                        
                        # Print image
                        dib = ImageWin.Dib(pil_image)
                        dib.draw(hdc.GetHandleOutput(), (x, y, x + new_width, y + new_height))
                        
                        hdc.EndPage()
                        hdc.EndDoc()
                        hdc.DeleteDC()
                    finally:
                        win32print.ClosePrinter(hprinter)
                    
                    messagebox.showinfo("Print", f"Sent to printer: {printer_name}", parent=self)
                    self.result = self.settings
                    self.destroy()
                    return
                except ImportError:
                    # Fall back to PIL's print method
                    pass
            
            # Fallback: Use PIL's print method (opens system print dialog)
            # Note: This may not work on all platforms
            try:
                pil_image.print()
                messagebox.showinfo("Print", "Print job sent to printer", parent=self)
            except Exception as e:
                # If PIL print doesn't work, save to temp file and open print dialog
                import tempfile
                import os
                temp_path = os.path.join(tempfile.gettempdir(), "replan_print.png")
                pil_image.save(temp_path)
                os.startfile(temp_path, "print")  # Windows
                messagebox.showinfo("Print", "Opening print dialog...", parent=self)
            
            self.result = self.settings
            self.destroy()
            
        except Exception as e:
            messagebox.showerror("Print Error", f"Error printing: {e}", parent=self)
    
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
