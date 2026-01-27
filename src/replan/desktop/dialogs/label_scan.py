"""Label scanning dialog with OCR."""

import tkinter as tk
from tkinter import ttk
from typing import Dict, List, Optional

from replan.desktop.dialogs.base import BaseDialog
from replan.desktop.models import PageTab
from replan.desktop.utils.ocr import (
    is_tesseract_available, 
    find_labels, 
    group_labels,
    KNOWN_PREFIXES,
)


class LabelScanDialog(BaseDialog):
    """Dialog for scanning pages for labels using OCR."""
    
    def __init__(self, parent, pages: List[PageTab]):
        self.pages = pages
        self.found_groups: Dict[str, List[str]] = {}
        self.check_vars: Dict[str, tk.BooleanVar] = {}
        self.name_entries: Dict[str, ttk.Entry] = {}
        
        super().__init__(parent, "Scan for Labels", 600, 500)
    
    def _setup_ui(self):
        # Progress section
        self.progress_frame = ttk.LabelFrame(self, text="Scanning Progress")
        self.progress_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.progress_label = ttk.Label(self.progress_frame, text="Preparing...")
        self.progress_label.pack(padx=10, pady=5)
        
        self.progress_bar = ttk.Progressbar(self.progress_frame, mode='determinate', length=400)
        self.progress_bar.pack(padx=10, pady=5)
        
        # Results section (hidden initially)
        self.results_frame = ttk.LabelFrame(self, text="Found Labels - Select to Add")
        
        # Scrollable area for results
        canvas_frame = ttk.Frame(self.results_frame)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.results_canvas = tk.Canvas(canvas_frame, height=250)
        scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=self.results_canvas.yview)
        self.checkbox_frame = ttk.Frame(self.results_canvas)
        
        self.checkbox_frame.bind(
            "<Configure>", 
            lambda e: self.results_canvas.configure(scrollregion=self.results_canvas.bbox("all"))
        )
        
        self.results_canvas.create_window((0, 0), window=self.checkbox_frame, anchor="nw")
        self.results_canvas.configure(yscrollcommand=scrollbar.set)
        
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.results_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Button frame (hidden initially)
        self.btn_frame = ttk.Frame(self)
        ttk.Button(self.btn_frame, text="Select All", command=self._select_all).pack(side=tk.LEFT, padx=5)
        ttk.Button(self.btn_frame, text="Select None", command=self._select_none).pack(side=tk.LEFT, padx=5)
        ttk.Button(self.btn_frame, text="Cancel", command=self._on_cancel).pack(side=tk.RIGHT, padx=5)
        ttk.Button(self.btn_frame, text="Add Selected", command=self._on_ok).pack(side=tk.RIGHT, padx=5)
        
        # Start scanning after dialog is shown
        self.after(100, self._start_scan)
    
    def _start_scan(self):
        if not is_tesseract_available():
            self.progress_label.config(text="⚠ Tesseract OCR not available")
            ttk.Label(self.progress_frame, 
                     text="Install Tesseract to enable label scanning",
                     foreground="gray").pack(pady=5)
            ttk.Button(self.progress_frame, text="Close", 
                      command=self._on_cancel).pack(pady=10)
            return
        
        total = len(self.pages)
        self.progress_bar['maximum'] = total
        all_found: Dict[str, set] = {}
        
        for i, page in enumerate(self.pages):
            self.progress_label.config(text=f"Scanning page {i+1}/{total}: {page.page_name}")
            self.progress_bar['value'] = i
            self.update()
            
            if page.original_image is None:
                continue
            
            try:
                page_labels = find_labels(page.original_image)
                for prefix, instances in page_labels.items():
                    if prefix not in all_found:
                        all_found[prefix] = set()
                    all_found[prefix].update(instances)
            except Exception as e:
                print(f"OCR error on {page.page_name}: {e}")
        
        self.progress_bar['value'] = total
        self.found_groups = {k: sorted(v) for k, v in all_found.items() if v}
        
        if self.found_groups:
            self.progress_label.config(text=f"Found {len(self.found_groups)} category groups")
            self._show_results()
        else:
            self.progress_label.config(text="No labels found")
            ttk.Button(self.progress_frame, text="Close", 
                      command=self._on_cancel).pack(pady=10)
    
    def _show_results(self):
        self.results_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.btn_frame.pack(fill=tk.X, padx=10, pady=10)
        
        row = 0
        for prefix in sorted(self.found_groups.keys()):
            instances = self.found_groups[prefix]
            
            var = tk.BooleanVar(value=True)
            self.check_vars[prefix] = var
            
            cb = ttk.Checkbutton(self.checkbox_frame, variable=var)
            cb.grid(row=row, column=0, padx=5, pady=3, sticky="w")
            
            default_name = KNOWN_PREFIXES.get(prefix, prefix)
            entry = ttk.Entry(self.checkbox_frame, width=20)
            entry.insert(0, default_name)
            entry.grid(row=row, column=1, padx=5, pady=3, sticky="w")
            self.name_entries[prefix] = entry
            
            ttk.Label(self.checkbox_frame, text=f"({prefix})", 
                     foreground="gray").grid(row=row, column=2, padx=5, pady=3, sticky="w")
            
            instances_str = ", ".join(instances[:5])
            if len(instances) > 5:
                instances_str += "..."
            ttk.Label(self.checkbox_frame, text=instances_str,
                     foreground="blue").grid(row=row, column=3, padx=5, pady=3, sticky="w")
            
            row += 1
    
    def _select_all(self):
        for var in self.check_vars.values():
            var.set(True)
    
    def _select_none(self):
        for var in self.check_vars.values():
            var.set(False)
    
    def _on_ok(self):
        self.result = {
            prefix: self.name_entries[prefix].get().strip()
            for prefix, var in self.check_vars.items()
            if var.get()
        }
        self.destroy()


