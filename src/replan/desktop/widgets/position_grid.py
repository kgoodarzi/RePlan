"""Position grid widget for label placement."""

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional


class PositionGrid(ttk.Frame):
    """
    A 3x3 grid for selecting label position.
    
    Provides an intuitive visual way to choose where labels
    should be positioned relative to objects.
    
    Positions:
        top-left    top-center    top-right
        middle-left center        middle-right
        bottom-left bottom-center bottom-right
    """
    
    POSITIONS = [
        ("top-left", "↖"), ("top-center", "↑"), ("top-right", "↗"),
        ("middle-left", "←"), ("center", "•"), ("middle-right", "→"),
        ("bottom-left", "↙"), ("bottom-center", "↓"), ("bottom-right", "↘"),
    ]
    
    def __init__(self, parent, 
                 on_change: Optional[Callable[[str], None]] = None,
                 initial: str = "center",
                 **kwargs):
        """
        Initialize the position grid.
        
        Args:
            parent: Parent widget
            on_change: Callback when position changes
            initial: Initial position value
        """
        super().__init__(parent, **kwargs)
        
        self.on_change = on_change
        self.position = tk.StringVar(value=initial)
        
        self._create_grid()
    
    def _create_grid(self):
        """Create the 3x3 button grid."""
        for i, (pos, symbol) in enumerate(self.POSITIONS):
            row = i // 3
            col = i % 3
            
            btn = ttk.Radiobutton(
                self,
                text=symbol,
                value=pos,
                variable=self.position,
                width=3,
                command=lambda p=pos: self._on_select(p),
            )
            btn.grid(row=row, column=col, padx=1, pady=1)
    
    def _on_select(self, position: str):
        """Handle position selection."""
        if self.on_change:
            self.on_change(position)
    
    def get(self) -> str:
        """Get current position."""
        return self.position.get()
    
    def set(self, position: str):
        """Set current position."""
        if any(pos == position for pos, _ in self.POSITIONS):
            self.position.set(position)


