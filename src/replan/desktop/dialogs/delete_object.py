"""Dialog for choosing what to do with pixels when deleting objects."""

import tkinter as tk
from tkinter import ttk
from typing import Optional


class DeleteObjectDialog:
    """Dialog for choosing pixel handling when deleting objects."""
    
    def __init__(self, parent, object_count: int, theme: dict):
        self.parent = parent
        self.object_count = object_count
        self.theme = theme
        self.result: Optional[str] = None  # "delete_pixels" or "revert_pixels" or None (cancel)
        
        # Create dialog window
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Delete Object")
        self.dialog.configure(bg=theme["bg"])
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Center dialog
        self.dialog.update_idletasks()
        width = 450
        height = 250  # Increased height to accommodate buttons with gap below
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
        title_text = f"Delete {self.object_count} object(s)?"
        if self.object_count == 1:
            title_text = "Delete object?"
        
        title_label = tk.Label(
            main_frame,
            text=title_text,
            bg=t["bg"], fg=t["fg"], font=("Segoe UI", 12, "bold")
        )
        title_label.pack(anchor=tk.W, pady=(0, 15))
        
        # Instructions
        info_label = tk.Label(
            main_frame,
            text="What would you like to do with the pixels?",
            bg=t["bg"], fg=t["fg"], font=("Segoe UI", 10)
        )
        info_label.pack(anchor=tk.W, pady=(0, 10))
        
        # Radio buttons frame
        radio_frame = tk.Frame(main_frame, bg=t["bg"])
        radio_frame.pack(fill=tk.X, pady=(0, 20))
        
        self.choice_var = tk.StringVar(value="revert_pixels")
        
        # Option 1: Revert pixels (keep pixels, remove object)
        revert_radio = tk.Radiobutton(
            radio_frame,
            text="Revert pixels (keep pixels, remove object association)",
            variable=self.choice_var,
            value="revert_pixels",
            bg=t["bg"], fg=t["fg"], selectcolor=t["bg"],
            font=("Segoe UI", 9),
            anchor=tk.W
        )
        revert_radio.pack(fill=tk.X, pady=(0, 8))
        
        # Option 2: Delete pixels (remove pixels from image)
        delete_radio = tk.Radiobutton(
            radio_frame,
            text="Delete pixels (remove pixels from image, set to white)",
            variable=self.choice_var,
            value="delete_pixels",
            bg=t["bg"], fg=t["fg"], selectcolor=t["bg"],
            font=("Segoe UI", 9),
            anchor=tk.W
        )
        delete_radio.pack(fill=tk.X)
        
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
            text="Delete",
            command=self._ok
        ).pack(side=tk.RIGHT)
    
    def _ok(self):
        """OK button - return selected choice."""
        self.result = self.choice_var.get()
        self.dialog.destroy()
    
    def _cancel(self):
        """Cancel button - return None."""
        self.result = None
        self.dialog.destroy()
