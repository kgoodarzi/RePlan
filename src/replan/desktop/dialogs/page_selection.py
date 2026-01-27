"""Dialog for selecting a target page to move objects to."""

import tkinter as tk
from tkinter import ttk
from typing import Optional, Dict
from replan.desktop.models import PageTab


class PageSelectionDialog:
    """Dialog for selecting a target page."""
    
    def __init__(self, parent, pages: Dict[str, PageTab], current_page_id: str, theme: dict):
        self.parent = parent
        self.pages = pages
        self.current_page_id = current_page_id
        self.theme = theme
        self.result: Optional[str] = None  # Selected page_id or None (cancel)
        
        # Create dialog window
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Move to Page")
        self.dialog.configure(bg=theme["bg"])
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Center dialog
        self.dialog.update_idletasks()
        width = 400
        height = 300
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
            text="Select target page:",
            bg=t["bg"], fg=t["fg"], font=("Segoe UI", 12, "bold")
        )
        title_label.pack(anchor=tk.W, pady=(0, 15))
        
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
            height=10
        )
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.listbox.yview)
        
        # Populate listbox with pages
        self.page_ids = []
        for page_id, page in sorted(self.pages.items(), key=lambda x: x[1].display_name):
            display_name = page.display_name
            # Mark current page
            if page_id == self.current_page_id:
                display_name = f"{display_name} (current)"
            self.listbox.insert(tk.END, display_name)
            self.page_ids.append(page_id)
        
        # Select first item by default
        if self.page_ids:
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
            text="Move",
            command=self._ok
        ).pack(side=tk.RIGHT)
    
    def _ok(self):
        """OK button - return selected page_id."""
        selection = self.listbox.curselection()
        if selection:
            index = selection[0]
            if 0 <= index < len(self.page_ids):
                self.result = self.page_ids[index]
        self.dialog.destroy()
    
    def _cancel(self):
        """Cancel button - return None."""
        self.result = None
        self.dialog.destroy()
