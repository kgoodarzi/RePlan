"""Base dialog class with common functionality."""

import tkinter as tk
from tkinter import ttk
from typing import Optional


class BaseDialog(tk.Toplevel):
    """
    Base class for modal dialogs.
    
    Provides:
    - Centering on parent window
    - Modal behavior
    - Standard button handling
    """
    
    def __init__(self, parent, title: str, width: int = 400, height: int = 300):
        """
        Initialize the dialog.
        
        Args:
            parent: Parent window
            title: Dialog title
            width: Dialog width
            height: Dialog height
        """
        super().__init__(parent)
        
        self.title(title)
        self.result: Optional[any] = None
        
        # Make modal
        self.transient(parent)
        
        # Center on parent
        self.update_idletasks()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        px = parent.winfo_x()
        py = parent.winfo_y()
        
        x = px + (pw - width) // 2
        y = py + (ph - height) // 2
        
        self.geometry(f"{width}x{height}+{x}+{y}")
        
        # Grab focus
        self.grab_set()
        
        # Setup UI
        self._setup_ui()
        
        # Handle close
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
    
    def _setup_ui(self):
        """Override to setup dialog UI."""
        pass
    
    def _on_ok(self):
        """Handle OK button."""
        self.destroy()
    
    def _on_cancel(self):
        """Handle Cancel/close."""
        self.result = None
        self.destroy()
    
    def show(self):
        """Show dialog and wait for result."""
        self.wait_window()
        return self.result
    
    def _create_button_frame(self, ok_text: str = "OK", 
                             cancel_text: str = "Cancel") -> ttk.Frame:
        """Create standard button frame."""
        frame = ttk.Frame(self)
        
        ttk.Button(frame, text=cancel_text, 
                   command=self._on_cancel).pack(side=tk.RIGHT, padx=5)
        ttk.Button(frame, text=ok_text,
                   command=self._on_ok).pack(side=tk.RIGHT, padx=5)
        
        return frame


