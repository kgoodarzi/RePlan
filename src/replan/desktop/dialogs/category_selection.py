"""Dialog for selecting a target category to move objects to."""

import tkinter as tk
from tkinter import ttk
from typing import Optional, Dict
from replan.desktop.models import DynamicCategory


class CategorySelectionDialog:
    """Dialog for selecting a target category."""
    
    def __init__(self, parent, categories: Dict[str, DynamicCategory], current_category: str, theme: dict):
        self.parent = parent
        self.categories = categories
        self.current_category = current_category
        self.theme = theme
        self.result: Optional[str] = None  # Selected category name or None (cancel)
        
        # Create dialog window
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Change Category")
        self.dialog.configure(bg=theme["bg"])
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Center dialog
        self.dialog.update_idletasks()
        width = 400
        height = 400
        x = (self.dialog.winfo_screenwidth() // 2) - (width // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (height // 2)
        self.dialog.geometry(f"{width}x{height}+{x}+{y}")
        
        # Create UI
        self._create_ui()
        
        # Wait for dialog to close
        self.dialog.wait_window()
    
    def _create_ui(self):
        """Create the dialog UI."""
        t = self.theme
        
        # Main frame
        main_frame = tk.Frame(self.dialog, bg=t["bg"])
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Title
        title_label = tk.Label(
            main_frame,
            text="Select target category:",
            bg=t["bg"], fg=t["fg"], font=("Segoe UI", 12, "bold")
        )
        title_label.pack(anchor=tk.W, pady=(0, 10))
        
        # Current category info
        current_cat = self.categories.get(self.current_category)
        if current_cat:
            current_label = tk.Label(
                main_frame,
                text=f"Current: {current_cat.full_name} ({self.current_category})",
                bg=t["bg"], fg=t["fg"], font=("Segoe UI", 9)
            )
            current_label.pack(anchor=tk.W, pady=(0, 15))
        
        # Listbox with scrollbar
        list_frame = tk.Frame(main_frame, bg=t["bg"])
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.listbox = tk.Listbox(
            list_frame,
            yscrollcommand=scrollbar.set,
            bg=t["bg"], fg=t["fg"],
            selectbackground=t["selection_bg"],
            selectforeground=t["selection_fg"],
            font=("Segoe UI", 10),
            height=12
        )
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.listbox.yview)
        
        # Populate listbox with categories
        self.category_names = []
        for cat_name, cat in sorted(self.categories.items(), key=lambda x: x[1].full_name):
            # Skip current category
            if cat_name == self.current_category:
                continue
            
            display_name = f"{cat.full_name} ({cat_name})"
            self.listbox.insert(tk.END, display_name)
            self.category_names.append(cat_name)
        
        # Select first item by default
        if self.category_names:
            self.listbox.selection_set(0)
            self.listbox.see(0)
        
        # Bind double-click to OK
        self.listbox.bind("<Double-Button-1>", lambda e: self._ok())
        
        # Buttons
        button_frame = tk.Frame(main_frame, bg=t["bg"])
        button_frame.pack(fill=tk.X)
        
        ttk.Button(
            button_frame,
            text="Cancel",
            command=self._cancel
        ).pack(side=tk.RIGHT, padx=(5, 0))
        
        ttk.Button(
            button_frame,
            text="Change Category",
            command=self._ok
        ).pack(side=tk.RIGHT)
    
    def _ok(self):
        """OK button - return selected category name."""
        selection = self.listbox.curselection()
        if selection:
            index = selection[0]
            if 0 <= index < len(self.category_names):
                self.result = self.category_names[index]
        self.dialog.destroy()
    
    def _cancel(self):
        """Cancel button - return None."""
        self.result = None
        self.dialog.destroy()
