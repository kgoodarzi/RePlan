"""PDF loader dialog."""

import tkinter as tk
from tkinter import ttk, simpledialog
from pathlib import Path
from typing import List, Tuple, Optional
import re
import cv2
import numpy as np
from PIL import Image, ImageTk

from replan.desktop.dialogs.base import BaseDialog
from replan.desktop.io.pdf_reader import PDFReader


class PDFLoaderDialog(BaseDialog):
    """Dialog for loading PDF and naming pages."""
    
    def __init__(self, parent, pdf_path: str, pages: List[dict], dpi: int = 150):
        """
        Initialize PDF loader dialog.
        
        Args:
            parent: Parent window
            pdf_path: Path to PDF file
            pages: List of dicts with 'image', 'width_inches', 'height_inches', 'dpi'
            dpi: Rasterization DPI
        """
        self.pdf_path = pdf_path
        self.dpi = dpi
        
        # Handle both old format (list of images) and new format (list of dicts)
        if pages and isinstance(pages[0], dict):
            self.original_pages = [p['image'] for p in pages]
            self.page_dimensions = [(p.get('width_inches', 0), p.get('height_inches', 0)) for p in pages]
        else:
            self.original_pages = pages
            self.page_dimensions = [(0, 0)] * len(pages)
        
        self.pages = [p.copy() for p in self.original_pages]
        self.rotations = [0] * len(self.original_pages)
        self.page_names = [f"Page_{i+1}" for i in range(len(self.original_pages))]
        self.model_name = PDFReader.get_default_model_name(pdf_path)
        self.preview_image = None
        
        super().__init__(parent, "PDF Page Setup", 1000, 750)
    
    def _setup_ui(self):
        # Top: Model name
        top = ttk.Frame(self)
        top.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(top, text="Model Name:", font=("", 11, "bold")).pack(side=tk.LEFT)
        self.model_var = tk.StringVar(value=self.model_name)
        ttk.Entry(top, textvariable=self.model_var, width=30, font=("", 11)).pack(side=tk.LEFT, padx=10)
        ttk.Label(top, text=f"({len(self.pages)} pages)", foreground="gray").pack(side=tk.LEFT)
        
        # Main area
        main = ttk.Frame(self)
        main.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Left: Page list
        left = ttk.LabelFrame(main, text="Pages")
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        
        self.page_listbox = tk.Listbox(left, width=25, height=15, font=("", 10))
        self.page_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.page_listbox.bind("<<ListboxSelect>>", self._on_page_select)
        
        for i in range(len(self.pages)):
            self.page_listbox.insert(tk.END, f"Page {i+1}: {self.page_names[i]}")
        
        # Controls
        ctrl = ttk.Frame(left)
        ctrl.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(ctrl, text="Rename", command=self._rename_page).pack(fill=tk.X, pady=2)
        
        rot = ttk.LabelFrame(left, text="Rotate")
        rot.pack(fill=tk.X, padx=5, pady=5)
        rot_btns = ttk.Frame(rot)
        rot_btns.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(rot_btns, text="↺ 90°", width=6, command=lambda: self._rotate(-90)).pack(side=tk.LEFT, padx=2)
        ttk.Button(rot_btns, text="↻ 90°", width=6, command=lambda: self._rotate(90)).pack(side=tk.LEFT, padx=2)
        ttk.Button(rot_btns, text="180°", width=5, command=lambda: self._rotate(180)).pack(side=tk.LEFT, padx=2)
        
        # Right: Preview
        right = ttk.LabelFrame(main, text="Preview")
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        self.preview_canvas = tk.Canvas(right, bg="#333333")
        self.preview_canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.page_info = ttk.Label(right, text="")
        self.page_info.pack(pady=5)
        
        # Bottom buttons
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Button(btn_frame, text="Cancel", command=self._on_cancel).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="Load All Pages", command=self._on_ok).pack(side=tk.RIGHT, padx=5)
        
        # Select first page
        if self.pages:
            self.page_listbox.selection_set(0)
            self.after(100, lambda: self._update_preview(0))
    
    def _rotate(self, degrees: int):
        sel = self.page_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        self.rotations[idx] = (self.rotations[idx] + degrees) % 360
        rot_count = self.rotations[idx] // 90
        self.pages[idx] = np.rot90(self.original_pages[idx], k=-rot_count)
        self._update_preview(idx)
    
    def _update_preview(self, idx: int):
        if not (0 <= idx < len(self.pages)):
            return
        page = self.pages[idx]
        if page is None or page.size == 0:
            return
        
        h, w = page.shape[:2]
        self.update_idletasks()
        cw = max(self.preview_canvas.winfo_width(), 400)
        ch = max(self.preview_canvas.winfo_height(), 300)
        
        scale = min(cw / w, ch / h) * 0.9
        new_w, new_h = max(1, int(w * scale)), max(1, int(h * scale))
        
        try:
            resized = cv2.resize(page, (new_w, new_h), interpolation=cv2.INTER_AREA)
            pil_img = Image.fromarray(cv2.cvtColor(resized, cv2.COLOR_BGR2RGB))
            self.preview_image = ImageTk.PhotoImage(pil_img)
            
            self.preview_canvas.delete("all")
            self.preview_canvas.create_image(cw//2, ch//2, image=self.preview_image)
        except Exception as e:
            print(f"Preview error: {e}")
        
        rot_str = f" (rotated {self.rotations[idx]}°)" if self.rotations[idx] else ""
        
        # Show dimensions in inches/cm if available
        dim_w, dim_h = self.page_dimensions[idx]
        if self.rotations[idx] in [90, 270]:
            dim_w, dim_h = dim_h, dim_w  # Swap for rotation
        
        if dim_w > 0 and dim_h > 0:
            dim_str = f" • {dim_w:.1f}\" × {dim_h:.1f}\" ({dim_w*2.54:.1f}cm × {dim_h*2.54:.1f}cm)"
        else:
            dim_str = ""
        
        self.page_info.config(text=f"Size: {w}×{h} px{rot_str}{dim_str}")
    
    def _on_page_select(self, event):
        sel = self.page_listbox.curselection()
        if sel:
            self._update_preview(sel[0])
    
    def _rename_page(self):
        sel = self.page_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        
        new_name = simpledialog.askstring(
            "Rename Page", 
            f"Enter name for Page {idx+1}:",
            initialvalue=self.page_names[idx],
            parent=self
        )
        
        if new_name:
            new_name = re.sub(r'[^\w\s-]', '', new_name).replace(' ', '_')
            self.page_names[idx] = new_name
            self.page_listbox.delete(idx)
            self.page_listbox.insert(idx, f"Page {idx+1}: {new_name}")
            self.page_listbox.selection_set(idx)
    
    def _on_ok(self):
        model = self.model_var.get().strip().replace(' ', '_')
        if not model:
            return
        
        self.result = []
        for i in range(len(self.pages)):
            # Adjust dimensions for rotation
            dim_w, dim_h = self.page_dimensions[i]
            if self.rotations[i] in [90, 270]:
                dim_w, dim_h = dim_h, dim_w
            
            self.result.append({
                'model_name': model,
                'page_name': self.page_names[i],
                'image': self.pages[i],
                'rotation': self.rotations[i],
                'width_inches': dim_w,
                'height_inches': dim_h,
                'dpi': self.dpi,
            })
        self.destroy()

