"""Nesting results dialog for displaying and exporting nested sheets."""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Dict, List, Optional
from PIL import Image, ImageTk
import cv2
import numpy as np
import os


class NestingResultsDialog(tk.Toplevel):
    """
    Dialog to display nesting results.
    
    Shows:
    - Tabs for each material group
    - Visual preview of each nested sheet
    - Export options (PNG, PDF, DXF)
    - Statistics (utilization, part count, etc.)
    """
    
    def __init__(self, parent, results: Dict[str, List], theme: Dict = None):
        """
        Initialize the results dialog.
        
        Args:
            parent: Parent window
            results: Dict mapping material key to list of NestedSheet objects
            theme: Theme dictionary for styling
        """
        super().__init__(parent)
        
        self.results = results
        self.theme = theme or {}
        self.current_images = {}  # Cache for rendered images
        
        self.title("Nesting Results")
        self.transient(parent)
        
        # Size and position
        width, height = 1000, 700
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
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        
        # Render first sheet
        self._render_all_sheets()
    
    def _setup_ui(self):
        """Setup the dialog UI."""
        bg = self.theme.get("bg", "#2b2b2b")
        fg = self.theme.get("fg", "#ffffff")
        self.configure(bg=bg)
        
        # Main container
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Top toolbar
        toolbar = ttk.Frame(main_frame)
        toolbar.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(toolbar, text="Nesting Results", font=("", 12, "bold")).pack(side=tk.LEFT)
        
        # Export buttons
        export_frame = ttk.Frame(toolbar)
        export_frame.pack(side=tk.RIGHT)
        
        ttk.Button(export_frame, text="Export All as PNG", 
                   command=self._export_all_png).pack(side=tk.LEFT, padx=2)
        ttk.Button(export_frame, text="Export Current Sheet", 
                   command=self._export_current).pack(side=tk.LEFT, padx=2)
        ttk.Button(export_frame, text="Create Pages", 
                   command=self._create_pages).pack(side=tk.LEFT, padx=2)
        
        # Content area with notebook for material groups
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # Create tabs for each material group
        self.sheet_frames = {}
        self.sheet_canvases = {}
        self.sheet_lists = {}
        
        for material_key, sheets in self.results.items():
            self._create_material_tab(material_key, sheets)
        
        # Bottom stats
        stats_frame = ttk.Frame(main_frame)
        stats_frame.pack(fill=tk.X, pady=(10, 0))
        
        total_sheets = sum(len(sheets) for sheets in self.results.values())
        total_parts = sum(
            sum(len(sheet.parts) for sheet in sheets)
            for sheets in self.results.values()
        )
        
        self.stats_var = tk.StringVar(
            value=f"Total: {total_sheets} sheets, {total_parts} parts across {len(self.results)} material groups"
        )
        ttk.Label(stats_frame, textvariable=self.stats_var).pack(side=tk.LEFT)
        
        # Close button
        ttk.Button(stats_frame, text="Close", command=self._on_close).pack(side=tk.RIGHT)
    
    def _create_material_tab(self, material_key: str, sheets: List):
        """Create a tab for a material group."""
        # Parse material key
        parts = material_key.rsplit("_", 1)
        material = parts[0] if parts else material_key
        thickness = parts[1] if len(parts) > 1 else ""
        
        tab_name = f"{material}"
        if thickness and thickness != "0.0":
            tab_name += f" ({thickness}\")"
        
        # Create tab frame
        tab_frame = ttk.Frame(self.notebook)
        self.notebook.add(tab_frame, text=tab_name)
        
        # Left side: Sheet list
        left_frame = ttk.Frame(tab_frame, width=200)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 5))
        left_frame.pack_propagate(False)
        
        ttk.Label(left_frame, text="Sheets:", font=("", 10, "bold")).pack(anchor=tk.W)
        
        sheet_list = tk.Listbox(left_frame, height=15)
        sheet_scroll = ttk.Scrollbar(left_frame, orient=tk.VERTICAL, command=sheet_list.yview)
        sheet_list.configure(yscrollcommand=sheet_scroll.set)
        
        sheet_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sheet_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Populate sheet list
        for i, sheet in enumerate(sheets):
            utilization = sheet.utilization
            sheet_list.insert(tk.END, f"Sheet {i+1} ({utilization:.1f}% used)")
        
        sheet_list.bind("<<ListboxSelect>>", 
                        lambda e, mk=material_key: self._on_sheet_select(e, mk))
        
        self.sheet_lists[material_key] = sheet_list
        
        # Right side: Preview
        right_frame = ttk.Frame(tab_frame)
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Canvas with scrollbars
        canvas_frame = ttk.Frame(right_frame)
        canvas_frame.pack(fill=tk.BOTH, expand=True)
        
        h_scroll = ttk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL)
        v_scroll = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL)
        
        canvas = tk.Canvas(canvas_frame, bg="white",
                          xscrollcommand=h_scroll.set, yscrollcommand=v_scroll.set)
        
        h_scroll.config(command=canvas.xview)
        v_scroll.config(command=canvas.yview)
        
        h_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(fill=tk.BOTH, expand=True)
        
        self.sheet_canvases[material_key] = canvas
        self.sheet_frames[material_key] = right_frame
        
        # Sheet info
        info_frame = ttk.Frame(right_frame)
        info_frame.pack(fill=tk.X, pady=5)
        
        info_var = tk.StringVar(value="Select a sheet to preview")
        ttk.Label(info_frame, textvariable=info_var).pack(side=tk.LEFT)
        
        # Store info var
        if not hasattr(self, 'info_vars'):
            self.info_vars = {}
        self.info_vars[material_key] = info_var
        
        # Select first sheet
        if sheets:
            sheet_list.selection_set(0)
            self._show_sheet(material_key, 0)
    
    def _on_sheet_select(self, event, material_key: str):
        """Handle sheet selection."""
        listbox = self.sheet_lists.get(material_key)
        if not listbox:
            return
        
        selection = listbox.curselection()
        if not selection:
            return
        
        sheet_idx = selection[0]
        self._show_sheet(material_key, sheet_idx)
    
    def _show_sheet(self, material_key: str, sheet_idx: int):
        """Display a sheet on the canvas."""
        sheets = self.results.get(material_key, [])
        if sheet_idx >= len(sheets):
            return
        
        sheet = sheets[sheet_idx]
        canvas = self.sheet_canvases.get(material_key)
        if not canvas:
            return
        
        # Get cached or render new image
        cache_key = f"{material_key}_{sheet_idx}"
        if cache_key not in self.current_images:
            # Render the sheet
            rendered = sheet.render(include_masks=True)
            
            # Convert BGRA to RGB for PIL
            rgb = cv2.cvtColor(rendered, cv2.COLOR_BGRA2RGB)
            pil_img = Image.fromarray(rgb)
            
            # Scale if too large
            max_size = 800
            if pil_img.width > max_size or pil_img.height > max_size:
                ratio = min(max_size / pil_img.width, max_size / pil_img.height)
                new_size = (int(pil_img.width * ratio), int(pil_img.height * ratio))
                pil_img = pil_img.resize(new_size, Image.Resampling.LANCZOS)
            
            tk_img = ImageTk.PhotoImage(pil_img)
            self.current_images[cache_key] = tk_img
        else:
            tk_img = self.current_images[cache_key]
        
        # Display on canvas
        canvas.delete("all")
        canvas.create_image(0, 0, anchor=tk.NW, image=tk_img)
        canvas.configure(scrollregion=(0, 0, tk_img.width(), tk_img.height()))
        
        # Update info
        info_var = self.info_vars.get(material_key)
        if info_var:
            info_var.set(
                f"Sheet {sheet_idx + 1}: {sheet.width}x{sheet.height}px, "
                f"{len(sheet.parts)} parts, {sheet.utilization:.1f}% utilization"
            )
    
    def _render_all_sheets(self):
        """Pre-render all sheets."""
        for material_key, sheets in self.results.items():
            for i, sheet in enumerate(sheets):
                cache_key = f"{material_key}_{i}"
                if cache_key not in self.current_images:
                    rendered = sheet.render(include_masks=True)
                    rgb = cv2.cvtColor(rendered, cv2.COLOR_BGRA2RGB)
                    pil_img = Image.fromarray(rgb)
                    
                    max_size = 800
                    if pil_img.width > max_size or pil_img.height > max_size:
                        ratio = min(max_size / pil_img.width, max_size / pil_img.height)
                        new_size = (int(pil_img.width * ratio), int(pil_img.height * ratio))
                        pil_img = pil_img.resize(new_size, Image.Resampling.LANCZOS)
                    
                    tk_img = ImageTk.PhotoImage(pil_img)
                    self.current_images[cache_key] = tk_img
    
    def _export_all_png(self):
        """Export all sheets as PNG files."""
        folder = filedialog.askdirectory(title="Select Export Folder")
        if not folder:
            return
        
        count = 0
        for material_key, sheets in self.results.items():
            # Clean material key for filename
            safe_key = material_key.replace("/", "-").replace("\\", "-")
            
            for i, sheet in enumerate(sheets):
                rendered = sheet.render(include_masks=True)
                rgb = cv2.cvtColor(rendered, cv2.COLOR_BGRA2RGB)
                
                filename = f"{safe_key}_sheet_{i+1}.png"
                filepath = os.path.join(folder, filename)
                
                cv2.imwrite(filepath, cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
                count += 1
        
        messagebox.showinfo("Export Complete", f"Exported {count} sheets to {folder}")
    
    def _export_current(self):
        """Export the currently selected sheet."""
        # Find current tab
        current_tab = self.notebook.index(self.notebook.select())
        material_keys = list(self.results.keys())
        
        if current_tab >= len(material_keys):
            return
        
        material_key = material_keys[current_tab]
        listbox = self.sheet_lists.get(material_key)
        
        if not listbox:
            return
        
        selection = listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a sheet first.")
            return
        
        sheet_idx = selection[0]
        sheets = self.results.get(material_key, [])
        
        if sheet_idx >= len(sheets):
            return
        
        sheet = sheets[sheet_idx]
        
        # Ask for save location
        safe_key = material_key.replace("/", "-").replace("\\", "-")
        default_name = f"{safe_key}_sheet_{sheet_idx+1}.png"
        
        filepath = filedialog.asksaveasfilename(
            title="Save Sheet",
            defaultextension=".png",
            filetypes=[("PNG files", "*.png"), ("All files", "*.*")],
            initialfile=default_name
        )
        
        if not filepath:
            return
        
        # Render and save
        rendered = sheet.render(include_masks=True)
        rgb = cv2.cvtColor(rendered, cv2.COLOR_BGRA2RGB)
        cv2.imwrite(filepath, cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
        
        messagebox.showinfo("Export Complete", f"Saved to {filepath}")
    
    def _create_pages(self):
        """Create new pages from nested sheets (for importing back into app)."""
        # This will be connected to the main app
        self.result = "create_pages"
        self._on_close()
    
    def _on_close(self):
        """Handle dialog close."""
        self.destroy()
