"""Collapsible frame widget with modern styling."""

import tkinter as tk
from tkinter import ttk
from typing import Optional, Dict


class CollapsibleFrame(tk.Frame):
    """
    A modern collapsible frame with VS Code-style appearance.
    
    Provides a clean way to organize sidebar sections that users
    can show or hide based on their workflow.
    
    Usage:
        section = CollapsibleFrame(parent, "Settings", theme=theme_dict)
        section.pack(fill=tk.X)
        tk.Label(section.content, text="Option 1").pack()
    """
    
    def __init__(self, parent, title: str = "", collapsed: bool = False, 
                 theme: Optional[Dict[str, str]] = None, **kwargs):
        """
        Initialize a collapsible frame.
        
        Args:
            parent: Parent widget
            title: Section title
            collapsed: Whether to start collapsed
            theme: Theme dictionary with color definitions
        """
        # Default theme if not provided
        if theme is None:
            theme = {
                "bg": "#252526",
                "fg": "#cccccc",
                "fg_muted": "#9d9d9d",
                "border": "#3c3c3c",
                "accent": "#0078d4",
            }
        
        self.theme = theme
        bg_color = theme.get("bg", "#252526")
        
        super().__init__(parent, bg=bg_color, **kwargs)
        
        self.collapsed = collapsed
        self.title = title
        
        # Header frame
        self.header = tk.Frame(self, bg=bg_color)
        self.header.pack(fill=tk.X, pady=(4, 0))
        
        # Toggle arrow
        arrow = "›" if collapsed else "⌄"
        self.arrow_label = tk.Label(
            self.header,
            text=arrow,
            font=("Segoe UI", 10),
            fg=theme.get("fg_muted", "#9d9d9d"),
            bg=bg_color,
            width=2,
            cursor="hand2"
        )
        self.arrow_label.pack(side=tk.LEFT)
        self.arrow_label.bind("<Button-1>", lambda e: self.toggle())
        
        # Title label (clickable)
        self.title_label = tk.Label(
            self.header,
            text=title.upper(),
            font=("Segoe UI", 9, "bold"),
            fg=theme.get("fg_muted", "#9d9d9d"),
            bg=bg_color,
            cursor="hand2"
        )
        self.title_label.pack(side=tk.LEFT, fill=tk.X, expand=True, anchor=tk.W)
        self.title_label.bind("<Button-1>", lambda e: self.toggle())
        
        # Hover effects
        self.header.bind("<Enter>", self._on_header_enter)
        self.header.bind("<Leave>", self._on_header_leave)
        self.arrow_label.bind("<Enter>", self._on_header_enter)
        self.arrow_label.bind("<Leave>", self._on_header_leave)
        self.title_label.bind("<Enter>", self._on_header_enter)
        self.title_label.bind("<Leave>", self._on_header_leave)
        
        # Content frame
        self.content = tk.Frame(self, bg=bg_color)
        if not collapsed:
            self.content.pack(fill=tk.BOTH, expand=True, padx=(8, 0), pady=(4, 8))
    
    def _on_header_enter(self, event):
        """Handle mouse entering header."""
        fg_color = self.theme.get("fg", "#cccccc")
        self.arrow_label.configure(fg=fg_color)
        self.title_label.configure(fg=fg_color)
    
    def _on_header_leave(self, event):
        """Handle mouse leaving header."""
        fg_color = self.theme.get("fg_muted", "#9d9d9d")
        self.arrow_label.configure(fg=fg_color)
        self.title_label.configure(fg=fg_color)
    
    def toggle(self):
        """Toggle collapsed state."""
        self.collapsed = not self.collapsed
        
        if self.collapsed:
            self.content.pack_forget()
            self.arrow_label.config(text="›")
        else:
            self.content.pack(fill=tk.BOTH, expand=True, padx=(8, 0), pady=(4, 8))
            self.arrow_label.config(text="⌄")
    
    def expand(self):
        """Expand the section."""
        if self.collapsed:
            self.toggle()
    
    def collapse(self):
        """Collapse the section."""
        if not self.collapsed:
            self.toggle()
    
    def set_title(self, title: str):
        """Update the section title."""
        self.title = title
        self.title_label.config(text=title.upper())
