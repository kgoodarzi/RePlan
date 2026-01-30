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
                 on_collapse: Callable[["DockablePanel"], None] = None,
                 on_drag_start: Callable[["DockablePanel"], None] = None):
        super().__init__(parent, bg=theme["bg"])
        self.config = config
        self.theme = theme
        self.on_collapse = on_collapse
        self.on_drag_start = on_drag_start
        self.collapsed = False
        self.width = config.default_width
        
        # Drag state
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.is_dragging = False
        
        self._setup_ui()
        
    def _setup_ui(self):
        """Setup panel UI with header and content area."""
        # Header
        self.header = tk.Frame(self, bg=self.theme["panel_header_bg"], height=35)
        self.header.pack(fill=tk.X)
        self.header.pack_propagate(False)
        
        # Drag handle (grip icon) - make header draggable
        drag_handle = tk.Label(
            self.header,
            text="⋮⋮",
            font=("Segoe UI", 10),
            fg=self.theme["fg_muted"],
            bg=self.theme["panel_header_bg"],
            padx=4,
            cursor="hand2"
        )
        drag_handle.pack(side=tk.LEFT, pady=8)
        drag_handle.bind("<Button-1>", self._on_drag_start)
        drag_handle.bind("<B1-Motion>", self._on_drag_motion)
        drag_handle.bind("<ButtonRelease-1>", self._on_drag_end)
        
        # Title (also draggable)
        self.title_label = tk.Label(
            self.header,
            text=self.config.title.upper(),
            font=("Segoe UI", 9, "bold"),
            fg=self.theme["panel_header_fg"],
            bg=self.theme["panel_header_bg"],
            padx=12,
            cursor="hand2"
        )
        self.title_label.pack(side=tk.LEFT, pady=8, fill=tk.X, expand=True)
        self.title_label.bind("<Button-1>", self._on_drag_start)
        self.title_label.bind("<B1-Motion>", self._on_drag_motion)
        self.title_label.bind("<ButtonRelease-1>", self._on_drag_end)
        
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
    
    def _on_drag_start(self, event):
        """Handle drag start on panel header."""
        if self.on_drag_start:
            self.drag_start_x = event.x_root
            self.drag_start_y = event.y_root
            self.is_dragging = True
            self.on_drag_start(self)
            # Bind to root window for global drag tracking
            root = self.winfo_toplevel()
            root.bind("<B1-Motion>", self._on_global_drag_motion)
            root.bind("<ButtonRelease-1>", self._on_global_drag_end)
    
    def _on_drag_motion(self, event):
        """Handle drag motion (local)."""
        pass  # Handled by global binding
    
    def _on_drag_end(self, event):
        """Handle drag end (local)."""
        pass  # Handled by global binding
    
    def _on_global_drag_motion(self, event):
        """Handle global drag motion."""
        if self.is_dragging and self.on_drag_start:
            layout = self._get_layout_manager()
            if layout:
                layout._on_panel_drag_motion(self, event.x_root, event.y_root)
    
    def _on_global_drag_end(self, event):
        """Handle global drag end."""
        if self.is_dragging:
            self.is_dragging = False
            layout = self._get_layout_manager()
            if layout:
                layout._on_panel_drag_end(self, event.x_root, event.y_root)
            # Unbind from root
            root = self.winfo_toplevel()
            root.unbind("<B1-Motion>")
            root.unbind("<ButtonRelease-1>")
    
    def _get_layout_manager(self):
        """Get the ResizableLayout parent."""
        parent = self.master
        while parent:
            if isinstance(parent, ResizableLayout):
                return parent
            parent = parent.master
        return None


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
        
        # Store panel content setup callbacks for repositioning
        self.panel_content_setup_callbacks: Dict[str, Callable[[DockablePanel], None]] = {}
        
    def add_panel(self, panel_id: str, config: PanelConfig, 
                  content_setup_callback: Optional[Callable[[DockablePanel], None]] = None) -> DockablePanel:
        """Add a dockable panel.
        
        Args:
            panel_id: Unique identifier for the panel
            config: Panel configuration
            content_setup_callback: Optional callback to setup panel content (called when panel is repositioned)
        """
        self.panel_configs[panel_id] = config
        
        # Store content setup callback if provided
        if content_setup_callback:
            self.panel_content_setup_callbacks[panel_id] = content_setup_callback
        
        # Restore dock state from settings if available
        if hasattr(self.settings, 'panel_dock_states') and panel_id in self.settings.panel_dock_states:
            saved_side = self.settings.panel_dock_states[panel_id]
            if saved_side in ["left", "right"]:
                config.side = saved_side
        
        parent = self.left_panel_frame if config.side == "left" else self.right_panel_frame
        
        panel = DockablePanel(
            parent, config, self.theme,
            on_collapse=lambda p: self._on_panel_collapse(panel_id, p),
            on_drag_start=lambda p: self._on_panel_drag_start(panel_id, p)
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
                """Save sidebar and center widths when sash is moved."""
                try:
                    paned_width = self.paned.winfo_width()
                    if paned_width <= 0:
                        return
                    
                    panes = self.paned.panes()
                    if len(panes) < 2:
                        return
                    
                    # Save sidebar width (sash 0)
                    try:
                        sash0_pos = self.paned.sashpos(0)
                        if sash0_pos > 50:
                            self.settings.sidebar_width = sash0_pos
                    except (tk.TclError, AttributeError, IndexError):
                        try:
                            sidebar_width = self.left_panel_frame.winfo_width()
                            if sidebar_width > 50:
                                self.settings.sidebar_width = sidebar_width
                        except:
                            pass
                    
                    # Save center width (sash 1 - sash 0) and object viewer width
                    if len(panes) >= 3:
                        try:
                            sash0_pos = self.paned.sashpos(0)
                            sash1_pos = self.paned.sashpos(1)
                            center_width = sash1_pos - sash0_pos
                            object_viewer_width = paned_width - sash1_pos
                            
                            if center_width > 100 and object_viewer_width > 50:
                                self.settings.tree_width = object_viewer_width
                                # Save settings immediately
                                from replan.desktop.config import save_settings
                                save_settings(self.settings)
                        except (tk.TclError, AttributeError, IndexError):
                            # Fallback to winfo_width
                            try:
                                object_viewer_width = self.right_panel_frame.winfo_width()
                                if object_viewer_width > 50:
                                    self.settings.tree_width = object_viewer_width
                                    from replan.desktop.config import save_settings
                                    save_settings(self.settings)
                            except:
                                pass
                except Exception as e:
                    pass
            
            # Bind to paned window sash movement to track resize
            self.paned.bind('<ButtonRelease-1>', on_sash_moved)
            self.paned.bind('<B1-Motion>', lambda e: self.after_idle(on_sash_moved))
            # Also bind to configure event in case window is resized
            self.paned.bind('<Configure>', lambda e: self.after_idle(on_sash_moved))
                
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
    
    def _on_panel_drag_start(self, panel_id: str, panel: DockablePanel):
        """Handle panel drag start."""
        # Store drag state
        self.dragging_panel_id = panel_id
        self.dragging_panel = panel
        
        # Create drag preview overlay
        self._create_drag_preview(panel)
    
    def _on_panel_drag_motion(self, panel: DockablePanel, x_root: int, y_root: int):
        """Handle panel drag motion - update preview and show drop zones."""
        if hasattr(self, 'drag_preview'):
            # Update preview position
            width = self.drag_preview.winfo_width()
            height = self.drag_preview.winfo_height()
            self.drag_preview.geometry(f"{width}x{height}+{x_root - width//2}+{y_root - height//2}")
            
            # Show drop zones
            self._show_drop_zones(x_root, y_root)
    
    def _create_drag_preview(self, panel: DockablePanel):
        """Create semi-transparent drag preview."""
        try:
            # Get panel geometry
            x = panel.winfo_rootx()
            y = panel.winfo_rooty()
            width = max(200, panel.winfo_width())  # Ensure minimum width
            height = max(100, panel.winfo_height())  # Ensure minimum height
            
            # Create overlay window
            self.drag_preview = tk.Toplevel(self)
            self.drag_preview.wm_overrideredirect(True)
            self.drag_preview.wm_attributes("-alpha", 0.5)
            self.drag_preview.configure(bg=self.theme["accent"])
            self.drag_preview.geometry(f"{width}x{height}+{x}+{y}")
            
            # Create label with panel title
            label = tk.Label(
                self.drag_preview,
                text=panel.config.title.upper(),
                font=("Segoe UI", 9, "bold"),
                fg="white",
                bg=self.theme["accent"],
                padx=12,
                pady=8
            )
            label.pack(fill=tk.BOTH, expand=True)
        except Exception as e:
            # If preview creation fails, continue without it
            print(f"Warning: Failed to create drag preview: {e}")
    
    
    def _show_drop_zones(self, x_root: int, y_root: int):
        """Show visual drop zones for left/right docking."""
        try:
            # Get main window geometry
            root_x = self.winfo_rootx()
            root_y = self.winfo_rooty()
            root_width = self.winfo_width()
            root_height = self.winfo_height()
            
            if root_width <= 0 or root_height <= 0:
                return  # Window not ready yet
            
            # Determine which side to highlight
            center_x = root_x + root_width // 2
            target_side = "left" if x_root < center_x else "right"
            
            # Remove old drop zone indicators
            if hasattr(self, 'drop_zone_left') and self.drop_zone_left.winfo_exists():
                try:
                    self.drop_zone_left.destroy()
                except:
                    pass
            if hasattr(self, 'drop_zone_right') and self.drop_zone_right.winfo_exists():
                try:
                    self.drop_zone_right.destroy()
                except:
                    pass
            
            # Create drop zone indicators
            drop_zone = tk.Toplevel(self)
            drop_zone.wm_overrideredirect(True)
            drop_zone.wm_attributes("-alpha", 0.3)
            drop_zone.configure(bg=self.theme["accent"])
            
            if target_side == "left":
                drop_zone.geometry(f"200x{root_height}+{root_x}+{root_y}")
                self.drop_zone_left = drop_zone
            else:
                drop_zone.geometry(f"200x{root_height}+{root_x + root_width - 200}+{root_y}")
                self.drop_zone_right = drop_zone
        except Exception as e:
            # Ignore errors in drop zone display
            pass
    
    def _on_panel_drag_end(self, panel: DockablePanel, x_root: int, y_root: int):
        """Handle panel drag end - determine drop location and reposition."""
        # Clean up drag preview
        if hasattr(self, 'drag_preview'):
            try:
                if self.drag_preview.winfo_exists():
                    self.drag_preview.destroy()
            except:
                pass
            delattr(self, 'drag_preview')
        
        # Clean up drop zones
        if hasattr(self, 'drop_zone_left'):
            try:
                if self.drop_zone_left.winfo_exists():
                    self.drop_zone_left.destroy()
            except:
                pass
            delattr(self, 'drop_zone_left')
        if hasattr(self, 'drop_zone_right'):
            try:
                if self.drop_zone_right.winfo_exists():
                    self.drop_zone_right.destroy()
            except:
                pass
            delattr(self, 'drop_zone_right')
        
        # Determine target side
        try:
            root_x = self.winfo_rootx()
            root_width = self.winfo_width()
            if root_width <= 0:
                return  # Window not ready
            
            center_x = root_x + root_width // 2
            target_side = "left" if x_root < center_x else "right"
            
            # Get panel ID
            panel_id = None
            for pid, p in self.panels.items():
                if p == panel:
                    panel_id = pid
                    break
            
            if not panel_id:
                return
            
            # If already on target side, do nothing
            if self.panel_configs[panel_id].side == target_side:
                return
            
            # Reposition panel
            self._reposition_panel(panel_id, target_side)
        except Exception as e:
            # Ignore errors during drag end
            print(f"Warning: Error during panel drag end: {e}")
    
    def _reposition_panel(self, panel_id: str, new_side: str):
        """Reposition a panel to a different side."""
        if panel_id not in self.panels:
            return
        
        panel = self.panels[panel_id]
        config = self.panel_configs[panel_id]
        
        # If already on target side, do nothing
        if config.side == new_side:
            return
        
        # Store panel state before destroying
        was_collapsed = panel.collapsed
        content_setup_callback = self.panel_content_setup_callbacks.get(panel_id)
        
        # Get new parent
        new_parent = self.left_panel_frame if new_side == "left" else self.right_panel_frame
        
        # Destroy old panel (tkinter widgets can't be reparented)
        panel.destroy()
        
        # Update config side
        config.side = new_side
        
        # Create new panel in new location
        new_panel = DockablePanel(
            new_parent, config, self.theme,
            on_collapse=lambda p: self._on_panel_collapse(panel_id, p),
            on_drag_start=lambda p: self._on_panel_drag_start(panel_id, p)
        )
        
        # Restore collapsed state
        if was_collapsed:
            new_panel.toggle_collapse()
        
        # Update stored panel reference
        self.panels[panel_id] = new_panel
        
        # Re-setup panel content if callback exists
        if content_setup_callback:
            content_setup_callback(new_panel)
        
        # Pack panel in new location
        new_panel.pack(fill=tk.BOTH, expand=True)
        
        # Rebuild paned window structure
        self._rebuild_paned_structure()
        
        # Save dock state
        self._save_panel_dock_state(panel_id, new_side)
    
    def _rebuild_paned_structure(self):
        """Rebuild paned window structure after panel repositioning."""
        # Get current pane list
        panes = list(self.paned.panes())
        
        # Check which frames should be present
        left_panels = [pid for pid, p in self.panels.items() 
                      if self.panel_configs[pid].side == "left"]
        right_panels = [pid for pid, p in self.panels.items() 
                       if self.panel_configs[pid].side == "right"]
        
        # Determine which frames should be in paned window
        has_left = len(left_panels) > 0
        has_right = len(right_panels) > 0
        
        # Check current state - need to check by widget identity, not just membership
        has_left_frame = False
        has_right_frame = False
        has_center_frame = False
        for pane_id in panes:
            try:
                pane_widget = self.paned.nametowidget(pane_id)
                if pane_widget == self.left_panel_frame:
                    has_left_frame = True
                elif pane_widget == self.right_panel_frame:
                    has_right_frame = True
                elif pane_widget == self.center_frame:
                    has_center_frame = True
            except:
                pass
        
        # Only rebuild if structure needs to change
        if (has_left != has_left_frame) or (has_right != has_right_frame) or not has_center_frame:
            # Remove all panes
            for pane in panes:
                try:
                    self.paned.remove(pane)
                except:
                    pass
            
            # Re-add panes in correct order
            if has_left:
                width = self.settings.sidebar_width
                self.paned.add(self.left_panel_frame, width=width, minsize=200)
            
            # Always add center
            self.paned.add(self.center_frame, stretch="always", minsize=400)
            
            # Add right panels frame if there are right panels
            if has_right:
                width = self.settings.tree_width
                self.paned.add(self.right_panel_frame, width=width, minsize=200)
            
            # Force update
            self.paned.update_idletasks()
    
    def _save_panel_dock_state(self, panel_id: str, side: str):
        """Save panel dock state to settings."""
        # Store in settings (we'll add panel_dock_states dict if needed)
        if not hasattr(self.settings, 'panel_dock_states'):
            self.settings.panel_dock_states = {}
        self.settings.panel_dock_states[panel_id] = side
        
        # Save settings
        from replan.desktop.config import save_settings
        save_settings(self.settings)


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

