"""
Responsive Layout Manager for PlanMod Segmenter.

Provides VS Code-style dockable panels with activity bar and
adaptive behavior based on window size.
"""

import tkinter as tk
from tkinter import ttk
from typing import Callable, Dict, Optional, List
from dataclasses import dataclass


@dataclass
class PanelConfig:
    """Configuration for a dockable panel."""
    name: str
    icon: str  # Unicode icon
    title: str
    min_width: int = 200
    max_width: int = 400
    default_width: int = 280
    side: str = "left"  # "left" or "right"


class ActivityBar(tk.Frame):
    """
    VS Code-style activity bar with icon buttons for panel switching.
    """
    
    def __init__(self, parent, theme: dict, on_panel_toggle: Callable[[str], None]):
        super().__init__(parent, bg=theme["activity_bg"], width=48)
        self.theme = theme
        self.on_panel_toggle = on_panel_toggle
        self.buttons: Dict[str, tk.Label] = {}
        self.active_panel: Optional[str] = None
        
        self.pack_propagate(False)
        
    def add_panel_button(self, panel_id: str, icon: str, tooltip: str = ""):
        """Add a button for a panel."""
        btn = tk.Label(
            self,
            text=icon,
            font=("Segoe UI", 18),
            fg=self.theme["activity_fg"],
            bg=self.theme["activity_bg"],
            width=3,
            height=2,
            cursor="hand2"
        )
        btn.pack(pady=(0, 0))
        btn.bind("<Button-1>", lambda e: self._on_click(panel_id))
        btn.bind("<Enter>", lambda e: self._on_hover(btn, True))
        btn.bind("<Leave>", lambda e: self._on_hover(btn, False))
        
        # Store tooltip info
        btn.tooltip_text = tooltip
        btn.panel_id = panel_id
        
        self.buttons[panel_id] = btn
        
        # Create tooltip
        self._create_tooltip(btn, tooltip)
        
    def _create_tooltip(self, widget, text):
        """Create a tooltip for a widget."""
        tooltip = None
        
        def show_tooltip(event):
            nonlocal tooltip
            if tooltip:
                return
            x = widget.winfo_rootx() + widget.winfo_width() + 5
            y = widget.winfo_rooty() + widget.winfo_height() // 2
            
            tooltip = tk.Toplevel(widget)
            tooltip.wm_overrideredirect(True)
            tooltip.wm_geometry(f"+{x}+{y}")
            
            label = tk.Label(
                tooltip,
                text=text,
                bg=self.theme["tooltip_bg"],
                fg=self.theme["tooltip_fg"],
                font=("Segoe UI", 9),
                padx=8,
                pady=4,
                relief="solid",
                borderwidth=1
            )
            label.configure(highlightbackground=self.theme["tooltip_border"])
            label.pack()
            
        def hide_tooltip(event):
            nonlocal tooltip
            if tooltip:
                tooltip.destroy()
                tooltip = None
                
        widget.bind("<Enter>", lambda e: (show_tooltip(e), self._on_hover(widget, True)))
        widget.bind("<Leave>", lambda e: (hide_tooltip(e), self._on_hover(widget, False)))
        
    def _on_click(self, panel_id: str):
        """Handle panel button click."""
        self.on_panel_toggle(panel_id)
        
    def _on_hover(self, btn: tk.Label, hovering: bool):
        """Handle hover state."""
        if btn.panel_id == self.active_panel:
            return
        if hovering:
            btn.configure(fg=self.theme["fg"])
        else:
            btn.configure(fg=self.theme["activity_fg"])
            
    def set_active(self, panel_id: Optional[str]):
        """Set the active panel."""
        # Reset previous active
        if self.active_panel and self.active_panel in self.buttons:
            btn = self.buttons[self.active_panel]
            btn.configure(fg=self.theme["activity_fg"], bg=self.theme["activity_bg"])
            
        self.active_panel = panel_id
        
        # Highlight new active
        if panel_id and panel_id in self.buttons:
            btn = self.buttons[panel_id]
            btn.configure(fg=self.theme["activity_active"], bg=self.theme["activity_bg"])
            # Add indicator line
            
    def add_spacer(self):
        """Add flexible spacer."""
        spacer = tk.Frame(self, bg=self.theme["activity_bg"])
        spacer.pack(fill=tk.Y, expand=True)
        
    def add_bottom_button(self, icon: str, command: Callable, tooltip: str = ""):
        """Add a button at the bottom of the activity bar."""
        btn = tk.Label(
            self,
            text=icon,
            font=("Segoe UI", 16),
            fg=self.theme["activity_fg"],
            bg=self.theme["activity_bg"],
            width=3,
            height=2,
            cursor="hand2"
        )
        btn.pack(side=tk.BOTTOM, pady=(0, 5))
        btn.bind("<Button-1>", lambda e: command())
        btn.bind("<Enter>", lambda e: btn.configure(fg=self.theme["fg"]))
        btn.bind("<Leave>", lambda e: btn.configure(fg=self.theme["activity_fg"]))
        
        self._create_tooltip(btn, tooltip)


class DockablePanel(tk.Frame):
    """
    A panel that can be collapsed, resized, and docked.
    """
    
    def __init__(self, parent, config: PanelConfig, theme: dict,
                 on_collapse: Callable[["DockablePanel"], None] = None):
        super().__init__(parent, bg=theme["bg"])
        self.config = config
        self.theme = theme
        self.on_collapse = on_collapse
        self.collapsed = False
        self.width = config.default_width
        
        self._setup_ui()
        
    def _setup_ui(self):
        """Setup panel UI with header and content area."""
        # Header
        self.header = tk.Frame(self, bg=self.theme["panel_header_bg"], height=35)
        self.header.pack(fill=tk.X)
        self.header.pack_propagate(False)
        
        # Title
        self.title_label = tk.Label(
            self.header,
            text=self.config.title.upper(),
            font=("Segoe UI", 9, "bold"),
            fg=self.theme["panel_header_fg"],
            bg=self.theme["panel_header_bg"],
            padx=12
        )
        self.title_label.pack(side=tk.LEFT, pady=8)
        
        # Collapse button
        collapse_icon = "«" if self.config.side == "left" else "»"
        self.collapse_btn = tk.Label(
            self.header,
            text=collapse_icon,
            font=("Segoe UI", 12),
            fg=self.theme["fg_muted"],
            bg=self.theme["panel_header_bg"],
            padx=8,
            cursor="hand2"
        )
        self.collapse_btn.pack(side=tk.RIGHT, pady=5)
        self.collapse_btn.bind("<Button-1>", lambda e: self.toggle_collapse())
        self.collapse_btn.bind("<Enter>", lambda e: self.collapse_btn.configure(fg=self.theme["fg"]))
        self.collapse_btn.bind("<Leave>", lambda e: self.collapse_btn.configure(fg=self.theme["fg_muted"]))
        
        # Content area
        self.content = tk.Frame(self, bg=self.theme["bg"])
        self.content.pack(fill=tk.BOTH, expand=True)
        
        # Border
        border_side = tk.RIGHT if self.config.side == "left" else tk.LEFT
        self.border = tk.Frame(self, bg=self.theme["border"], width=1)
        self.border.pack(side=border_side, fill=tk.Y)
        
    def toggle_collapse(self):
        """Toggle collapsed state."""
        self.collapsed = not self.collapsed
        
        if self.collapsed:
            self.content.pack_forget()
            collapse_icon = "»" if self.config.side == "left" else "«"
        else:
            self.content.pack(fill=tk.BOTH, expand=True)
            collapse_icon = "«" if self.config.side == "left" else "»"
            
        self.collapse_btn.configure(text=collapse_icon)
        
        if self.on_collapse:
            self.on_collapse(self)
            
    def set_width(self, width: int):
        """Set panel width."""
        self.width = max(self.config.min_width, min(width, self.config.max_width))
        self.configure(width=self.width)


class ResizableLayout(tk.Frame):
    """
    Main layout manager with resizable panels and activity bar.
    """
    
    def __init__(self, parent, theme: dict, settings):
        super().__init__(parent, bg=theme["bg_base"])
        self.theme = theme
        self.settings = settings
        self.panels: Dict[str, DockablePanel] = {}
        self.panel_configs: Dict[str, PanelConfig] = {}
        self.current_layout_mode = "full"
        
        self._setup_structure()
        self._bind_resize()
        
    def _setup_structure(self):
        """Setup the main layout structure."""
        # Activity bar (far left)
        self.activity_bar = ActivityBar(
            self, self.theme, self._on_panel_toggle
        )
        self.activity_bar.pack(side=tk.LEFT, fill=tk.Y)
        
        # Main paned window for resizable areas
        self.paned = tk.PanedWindow(
            self,
            orient=tk.HORIZONTAL,
            bg=self.theme["border"],
            sashwidth=4,
            sashrelief=tk.FLAT,
            borderwidth=0
        )
        self.paned.pack(fill=tk.BOTH, expand=True)
        
        # Left panel area
        self.left_panel_frame = tk.Frame(self.paned, bg=self.theme["bg"])
        
        # Center area (will contain notebook)
        self.center_frame = tk.Frame(self.paned, bg=self.theme["bg_base"])
        
        # Right panel area
        self.right_panel_frame = tk.Frame(self.paned, bg=self.theme["bg"])
        
    def add_panel(self, panel_id: str, config: PanelConfig) -> DockablePanel:
        """Add a dockable panel."""
        self.panel_configs[panel_id] = config
        
        parent = self.left_panel_frame if config.side == "left" else self.right_panel_frame
        
        panel = DockablePanel(
            parent, config, self.theme,
            on_collapse=lambda p: self._on_panel_collapse(panel_id, p)
        )
        
        self.panels[panel_id] = panel
        
        # Add to activity bar
        self.activity_bar.add_panel_button(panel_id, config.icon, config.title)
        
        return panel
    
    def finalize_layout(self):
        """Finalize layout after all panels are added."""
        # Add frames to paned window with minimum sizes to prevent collapse
        if self.panels:
            # Check for left panels
            left_panels = [p for pid, p in self.panels.items() 
                          if self.panel_configs[pid].side == "left"]
            if left_panels:
                self.paned.add(self.left_panel_frame, width=self.settings.sidebar_width, minsize=200)
                for panel in left_panels:
                    panel.pack(fill=tk.BOTH, expand=True)
        
        # Always add center
        self.paned.add(self.center_frame, stretch="always", minsize=400)
        
        # Check for right panels
        right_panels = [p for pid, p in self.panels.items() 
                       if self.panel_configs[pid].side == "right"]
        if right_panels:
            self.paned.add(self.right_panel_frame, width=self.settings.tree_width, minsize=200)
            for panel in right_panels:
                panel.pack(fill=tk.BOTH, expand=True)
            
            # Bind to paned window sash movement to track panel width changes
            def on_sash_moved(event=None):
                if right_panels:
                    # Get current width of right panel frame
                    try:
                        right_width = self.right_panel_frame.winfo_width()
                        if right_width > 0:
                            self.settings.tree_width = right_width
                            # Save settings immediately
                            from replan.desktop.config import save_settings
                            save_settings(self.settings)
                    except:
                        pass
            
            # Bind to paned window configure event to track resize
            self.paned.bind('<ButtonRelease-1>', on_sash_moved)
            self.paned.bind('<B1-Motion>', lambda e: self.after_idle(on_sash_moved))
                
        # Set initial active panel
        if self.panels:
            first_panel = list(self.panels.keys())[0]
            self.activity_bar.set_active(first_panel)
            
    def _on_panel_toggle(self, panel_id: str):
        """Handle panel toggle from activity bar."""
        if panel_id not in self.panels:
            return
            
        panel = self.panels[panel_id]
        config = self.panel_configs[panel_id]
        
        # Toggle visibility
        if panel.winfo_viewable():
            panel.pack_forget()
            self.activity_bar.set_active(None)
        else:
            panel.pack(fill=tk.BOTH, expand=True)
            self.activity_bar.set_active(panel_id)
            
    def _on_panel_collapse(self, panel_id: str, panel: DockablePanel):
        """Handle panel collapse."""
        # Update settings
        if self.panel_configs[panel_id].side == "left":
            self.settings.sidebar_collapsed = panel.collapsed
        else:
            self.settings.tree_collapsed = panel.collapsed
            
    def _bind_resize(self):
        """Bind window resize events."""
        self.bind("<Configure>", self._on_resize)
        
    def _on_resize(self, event):
        """Handle resize events for responsive behavior."""
        width = self.winfo_width()
        
        # Import here to avoid circular
        from replan.desktop.config import get_layout_mode
        new_mode = get_layout_mode(width)
        
        if new_mode != self.current_layout_mode:
            self.current_layout_mode = new_mode
            self._apply_layout_mode(new_mode)
            
    def _apply_layout_mode(self, mode: str):
        """Apply layout based on mode."""
        if not self.settings.auto_collapse_panels:
            return
            
        if mode == "minimal":
            # Hide all panels, show only on demand
            for panel in self.panels.values():
                panel.pack_forget()
        elif mode == "compact":
            # Collapse panels but keep visible
            for panel in self.panels.values():
                if not panel.collapsed:
                    panel.toggle_collapse()
        elif mode == "standard":
            # Left panel expanded, right collapsed
            for pid, panel in self.panels.items():
                config = self.panel_configs[pid]
                if config.side == "right" and not panel.collapsed:
                    panel.toggle_collapse()
                elif config.side == "left" and panel.collapsed:
                    panel.toggle_collapse()
        else:  # full
            # All panels expanded
            for panel in self.panels.values():
                if panel.collapsed:
                    panel.toggle_collapse()
                    
    def get_center_frame(self) -> tk.Frame:
        """Get the center frame for main content."""
        return self.center_frame
    
    def show_panel(self, panel_id: str):
        """Show a specific panel."""
        if panel_id in self.panels:
            panel = self.panels[panel_id]
            if not panel.winfo_viewable():
                panel.pack(fill=tk.BOTH, expand=True)
            self.activity_bar.set_active(panel_id)
            
    def hide_panel(self, panel_id: str):
        """Hide a specific panel."""
        if panel_id in self.panels:
            self.panels[panel_id].pack_forget()
            self.activity_bar.set_active(None)


class StatusBar(tk.Frame):
    """VS Code-style status bar."""
    
    def __init__(self, parent, theme: dict):
        super().__init__(parent, bg=theme["status_bg"], height=22)
        self.theme = theme
        self.pack_propagate(False)
        
        self.items: Dict[str, tk.Label] = {}
        
    def add_item(self, item_id: str, text: str = "", side: str = "left", 
                 icon: str = "", click_command: Callable = None):
        """Add a status bar item."""
        full_text = f"{icon} {text}" if icon else text
        
        item = tk.Label(
            self,
            text=full_text,
            font=("Segoe UI", 9),
            fg=self.theme["status_fg"],
            bg=self.theme["status_bg"],
            padx=10
        )
        item.pack(side=tk.LEFT if side == "left" else tk.RIGHT)
        
        if click_command:
            item.configure(cursor="hand2")
            item.bind("<Button-1>", lambda e: click_command())
            
        self.items[item_id] = item
        
    def set_item_text(self, item_id: str, text: str, icon: str = ""):
        """Update a status bar item's text."""
        if item_id in self.items:
            full_text = f"{icon} {text}" if icon else text
            self.items[item_id].configure(text=full_text)
            
    def add_separator(self):
        """Add a visual separator."""
        sep = tk.Frame(self, bg=self.theme["status_fg"], width=1)
        sep.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=4)

