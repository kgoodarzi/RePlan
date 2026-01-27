"""
RePlan Application - Main Coordinator

This is the main entry point that coordinates all modules.
Modern VS Code/Cursor-inspired UI with responsive layout.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from pathlib import Path
from typing import Dict, Set, List, Optional
import uuid
import cv2
import numpy as np
from PIL import Image, ImageTk, ImageDraw
import sys
import os

# Add findline tools to path
_desktop_dir = Path(__file__).parent  # replan/desktop
_replan_dir = _desktop_dir.parent  # replan
findline_path = _replan_dir / "findline"
if findline_path.exists() and str(findline_path) not in sys.path:
    sys.path.insert(0, str(findline_path))

# Import findline functions
try:
    from trace_with_points import (
        convert_to_monochrome,
        skeletonize_image,
        find_nearest_skeleton_point,
        trace_between_points,
        measure_line_thickness,
        select_line_pixels,
        detect_collisions
    )
    FINDLINE_AVAILABLE = True
except ImportError as e:
    print(f"Warning: findline tools not available: {e}")
    FINDLINE_AVAILABLE = False

from replan.desktop.config import (
    load_settings, save_settings, get_theme, get_theme_names, 
    AppSettings, Breakpoints, get_layout_mode
)
from replan.desktop.models import (
    PageTab, SegmentedObject, ObjectInstance, SegmentElement,
    DynamicCategory, create_default_categories, get_next_color
)
from replan.desktop.models.attributes import ObjectAttributes
from replan.desktop.core import SegmentationEngine, Renderer
from replan.desktop.io import WorkspaceManager, PDFReader
from replan.desktop.dialogs import (
    PDFLoaderDialog, LabelScanDialog, AttributeDialog, SettingsDialog, 
    DeleteObjectDialog, PageSelectionDialog, NestingConfigDialog, NestingResultsDialog
)
from replan.desktop.core.nesting import NestingEngine, check_rectpack_available
from replan.desktop.widgets import (
    CollapsibleFrame, PositionGrid,
    ResizableLayout, StatusBar, PanelConfig, DockablePanel
)

VERSION = "6.0"


class RePlanApp:
    """
    Main application coordinator.
    
    This class ties together all the modular components and handles
    high-level application logic.
    """
    
    MODES = {
        "select": "Select existing objects",
        "flood": "Flood fill region",
        "polyline": "Draw polygon",
        "freeform": "Freeform brush",
        "line": "Line segments",
        "rect": "Rectangular selection",
    }
    
    def __init__(self, startup_workspace: str = None, startup_pdf: str = None):
        # Store startup files
        self._startup_workspace = startup_workspace
        self._startup_pdf = startup_pdf
        
        # Load settings
        self.settings = load_settings()
        self.theme = get_theme(self.settings.theme)
        
        # Core components
        self.engine = SegmentationEngine(self.settings.tolerance, self.settings.line_thickness)
        self.renderer = Renderer()
        self.workspace_mgr = WorkspaceManager(self.settings.tolerance, self.settings.line_thickness)
        self.pdf_reader = PDFReader()
        
        # Application state
        self.pages: Dict[str, PageTab] = {}
        self.current_page_id: Optional[str] = None
        self.categories: Dict[str, DynamicCategory] = {}
        self.all_objects: List[SegmentedObject] = []  # Global object list across all pages
        # Store which objects are within each planform (planform_id -> list of object_ids)
        self.planform_objects: Dict[str, List[str]] = {}
        
        # Selection state
        self.selected_object_ids: Set[str] = set()
        self.selected_instance_ids: Set[str] = set()
        self.selected_element_ids: Set[str] = set()
        
        # Pixel/raster selection state
        self.selected_pixel_mask: Optional[np.ndarray] = None  # Binary mask of selected pixels
        self.selected_pixel_bbox: Optional[Tuple[int, int, int, int]] = None  # (x_min, y_min, x_max, y_max)
        self.is_moving_pixels = False  # Whether we're in move mode for pixels
        self.pixel_move_start: Optional[Tuple[int, int]] = None  # Starting position for move
        self.pixel_move_offset: Optional[Tuple[int, int]] = None  # Current offset during move
        
        # Object/element move state
        self.is_moving_objects = False  # Whether we're in move mode for objects/elements
        self.object_move_start: Optional[Tuple[int, int]] = None  # Starting position for move
        self.object_move_offset: Optional[Tuple[int, int]] = None  # Current offset during move
        
        # Tool state
        self.current_mode = "flood"
        self.current_points: List[tuple] = []
        self.is_drawing = False
        self.group_mode_active = False
        self.group_mode_elements: List[SegmentElement] = []
        
        # Rectangle selection state
        self.rect_start: Optional[tuple] = None  # (x, y) where rectangle started
        self.rect_current: Optional[tuple] = None  # (x, y) current mouse position
        self.rect_id = None  # Canvas item ID for rectangle preview
        
        # Display state
        self.zoom_level = 1.0
        self.show_labels = True
        self.label_position = "center"
        
        # Workspace state
        self.workspace_file: Optional[str] = None
        self.workspace_modified = False
        
        # Cache for working image (to avoid recomputing on every call)
        # Format: (page_id, visibility_state, image, applied_masks)
        # applied_masks: dict with keys 'text', 'hatch', 'line' containing the mask hashes/checksums
        self._working_image_cache: Optional[tuple] = None
        
        # Performance: Debouncing for display updates
        self._update_display_pending = False
        self._update_display_timer_id = None
        
        # Dialog state tracking
        
        # Create UI
        self.root = tk.Tk()
        self.root.title(f"PlanMod Segmenter v{VERSION}")
        # Restore window geometry including position
        geometry = f"{self.settings.window_width}x{self.settings.window_height}"
        if self.settings.window_x >= 0 and self.settings.window_y >= 0:
            geometry += f"+{self.settings.window_x}+{self.settings.window_y}"
        self.root.geometry(geometry)
        
        self._apply_theme()
        self._init_categories()
        self._setup_ui()
        self._bind_events()
        
        # Schedule startup file loading after UI is ready
        if self._startup_workspace or self._startup_pdf:
            self.root.after(100, self._load_startup_file)
    
    def _apply_theme(self):
        """Apply VS Code/Cursor-inspired theme to ttk styles."""
        style = ttk.Style()
        style.theme_use('clam')
        t = self.theme
        
        # Base styles
        style.configure(".", background=t["bg"], foreground=t["fg"], font=("Segoe UI", 9))
        style.configure("TFrame", background=t["bg"])
        style.configure("TLabel", background=t["bg"], foreground=t["fg"])
        
        # Primary button (accent color)
        style.configure("TButton", 
                       background=t["button_secondary_bg"], 
                       foreground=t["button_secondary_fg"],
                       padding=(12, 6),
                       borderwidth=0)
        style.map("TButton", 
                 background=[("active", t["button_secondary_hover"]), ("pressed", t["accent"])],
                 foreground=[("active", t["fg"]), ("pressed", t["button_fg"])])
        
        # Accent button
        style.configure("Accent.TButton",
                       background=t["accent"],
                       foreground=t["button_fg"],
                       padding=(12, 6))
        style.map("Accent.TButton",
                 background=[("active", t["accent_hover"]), ("pressed", t["accent_active"])])
        
        # Input fields
        style.configure("TEntry", 
                       fieldbackground=t["input_bg"], 
                       foreground=t["input_fg"],
                       bordercolor=t["input_border"],
                       lightcolor=t["input_border"],
                       darkcolor=t["input_border"],
                       padding=6)
        style.map("TEntry",
                 bordercolor=[("focus", t["input_focus"])],
                 lightcolor=[("focus", t["input_focus"])])
        
        style.configure("TCombobox", 
                       fieldbackground=t["input_bg"], 
                       foreground=t["input_fg"],
                       arrowcolor=t["fg_muted"],
                       padding=4)
        style.map("TCombobox",
                 fieldbackground=[("readonly", t["input_bg"])],
                 selectbackground=[("readonly", t["selection_bg"])])
        
        # Notebook (tabs)
        style.configure("TNotebook", background=t["tab_bg"], borderwidth=0)
        style.configure("TNotebook.Tab", 
                       background=t["tab_bg"], 
                       foreground=t["tab_fg"], 
                       padding=[16, 8],
                       borderwidth=0)
        style.map("TNotebook.Tab", 
                 background=[("selected", t["tab_active_bg"])], 
                 foreground=[("selected", t["tab_active_fg"])])
        
        # Treeview (lists)
        style.configure("Treeview", 
                       background=t["list_bg"], 
                       foreground=t["list_fg"], 
                       fieldbackground=t["list_bg"],
                       borderwidth=0,
                       rowheight=28)
        style.map("Treeview", 
                 background=[("selected", t["list_selected"])],
                 foreground=[("selected", t["selection_fg"])])
        style.configure("Treeview.Heading",
                       background=t["bg_secondary"],
                       foreground=t["fg_muted"],
                       borderwidth=0)
        
        # Checkbutton & Radiobutton
        style.configure("TCheckbutton", background=t["bg"], foreground=t["fg"])
        style.map("TCheckbutton", background=[("active", t["bg"])])
        style.configure("TRadiobutton", background=t["bg"], foreground=t["fg"])
        style.map("TRadiobutton", background=[("active", t["bg"])])
        
        # LabelFrame
        style.configure("TLabelframe", background=t["bg"], bordercolor=t["border"])
        style.configure("TLabelframe.Label", background=t["bg"], foreground=t["fg_muted"])
        
        # Scale (slider)
        style.configure("TScale", background=t["bg"], troughcolor=t["bg_tertiary"])
        
        # Scrollbar
        style.configure("TScrollbar",
                       background=t["scrollbar_thumb"],
                       troughcolor=t["bg"],
                       borderwidth=0,
                       arrowsize=0)
        style.map("TScrollbar",
                 background=[("active", t["scrollbar_thumb_hover"])])
        
        # Separator
        style.configure("TSeparator", background=t["border"])
        
        # Panel header style
        style.configure("PanelHeader.TLabel", 
                       background=t["panel_header_bg"], 
                       foreground=t["panel_header_fg"],
                       font=("Segoe UI", 9, "bold"),
                       padding=(12, 8))
        
        # Section header style
        style.configure("Section.TLabel", 
                       background=t["bg"], 
                       foreground=t["fg_muted"], 
                       font=("Segoe UI", 9, "bold"))
        
        self.root.configure(bg=t["bg_base"])
    
    def _init_categories(self):
        """Initialize default categories."""
        self.categories = create_default_categories()
    
    def _setup_ui(self):
        """Setup the modern VS Code/Cursor-inspired UI."""
        t = self.theme
        
        # Menu bar
        self._setup_menubar()
        
        # Main responsive layout
        self.layout = ResizableLayout(self.root, t, self.settings)
        self.layout.pack(fill=tk.BOTH, expand=True)
        
        # Add panels to layout
        self._setup_tools_panel()
        self._setup_object_panel()
        
        # Finalize panel layout
        self.layout.finalize_layout()
        
        # Setup center content (notebook)
        self._setup_center(self.layout.get_center_frame())
        
        # Add activity bar bottom buttons
        self.layout.activity_bar.add_spacer()
        self.layout.activity_bar.add_bottom_button("⚙", self._show_settings_dialog, "Settings")
        
        # Status bar
        self.status_bar = StatusBar(self.root, t)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        self.status_bar.add_item("status", "Ready - Open a PDF to begin")
        self.status_bar.add_separator()
        self.status_bar.add_item("zoom", "100%", side="right", click_command=self._zoom_fit)
        self.status_bar.add_item("mode", "Flood", side="right")
        
        # For backward compatibility
        self.status_var = type('obj', (object,), {'set': lambda s, x: self.status_bar.set_item_text("status", x)})()
    
    def _setup_menubar(self):
        """Setup the menu bar."""
        t = self.theme
        
        menubar = tk.Menu(self.root, bg=t["menu_bg"], fg=t["menu_fg"], 
                         activebackground=t["menu_hover"], activeforeground=t["selection_fg"],
                         borderwidth=0)
        self.root.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0, bg=t["menu_bg"], fg=t["menu_fg"],
                           activebackground=t["menu_hover"], activeforeground=t["selection_fg"])
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Open PDF...", command=self._open_pdf, accelerator="Ctrl+N")
        file_menu.add_command(label="Open Workspace...", command=self._load_workspace, accelerator="Ctrl+O")
        file_menu.add_separator()
        file_menu.add_command(label="Save Workspace", command=self._save_workspace, accelerator="Ctrl+S")
        file_menu.add_command(label="Save Workspace As...", command=self._save_workspace_as)
        file_menu.add_separator()
        file_menu.add_command(label="Export Image...", command=self._export_image)
        file_menu.add_command(label="Export Data...", command=self._export_data)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._on_close)
        
        # Edit menu (with settings)
        edit_menu = tk.Menu(menubar, tearoff=0, bg=t["menu_bg"], fg=t["menu_fg"],
                           activebackground=t["menu_hover"], activeforeground=t["selection_fg"])
        menubar.add_cascade(label="Edit", menu=edit_menu)
        edit_menu.add_command(label="Undo", command=self._undo, accelerator="Ctrl+Z")
        edit_menu.add_separator()
        edit_menu.add_command(label="Delete Selected", command=self._delete_selected, accelerator="Del")
        edit_menu.add_separator()
        edit_menu.add_command(label="Preferences...", command=self._show_settings_dialog)
        
        # View menu
        view_menu = tk.Menu(menubar, tearoff=0, bg=t["menu_bg"], fg=t["menu_fg"],
                           activebackground=t["menu_hover"], activeforeground=t["selection_fg"])
        menubar.add_cascade(label="View", menu=view_menu)
        
        self.view_menu = view_menu
        
        # Panel toggles
        view_menu.add_command(label="Toggle Tools Panel", command=lambda: self.layout._on_panel_toggle("tools"),
                             accelerator="Ctrl+B")
        view_menu.add_command(label="Toggle Objects Panel", command=lambda: self.layout._on_panel_toggle("objects"),
                             accelerator="Ctrl+J")
        view_menu.add_separator()
        
        # View options (per-page toggles)
        view_menu.add_command(label="Hide Background", command=self._toggle_hide_background)
        view_menu.add_command(label="Run OCR", command=self._run_ocr_for_page)
        view_menu.add_command(label="Hide Hatching", command=self._toggle_hide_hatching)
        view_menu.add_separator()
        view_menu.add_command(label="Create View Tab from Planform", command=self._create_view_tab_from_planform)
        view_menu.add_separator()
        view_menu.add_separator()
        
        # Ruler options
        ruler_label = "Hide Ruler" if self.settings.show_ruler else "Show Ruler"
        view_menu.add_command(label=ruler_label, command=self._toggle_ruler)
        
        self.ruler_unit_var = tk.StringVar(value=self.settings.ruler_unit)
        ruler_menu = tk.Menu(view_menu, tearoff=0, bg=t["menu_bg"], fg=t["menu_fg"])
        view_menu.add_cascade(label="Ruler Unit", menu=ruler_menu)
        ruler_menu.add_radiobutton(label="Inches (1/16\" ticks)", variable=self.ruler_unit_var,
                                   value="inch", command=lambda: self._set_ruler_unit("inch"))
        ruler_menu.add_radiobutton(label="Centimeters (mm ticks)", variable=self.ruler_unit_var,
                                   value="cm", command=lambda: self._set_ruler_unit("cm"))
        view_menu.add_separator()
        
        # Theme submenu
        theme_menu = tk.Menu(view_menu, tearoff=0, bg=t["menu_bg"], fg=t["menu_fg"])
        view_menu.add_cascade(label="Theme", menu=theme_menu)
        for theme_name in get_theme_names():
            theme_menu.add_radiobutton(label=theme_name.replace("_", " ").title(), 
                                       command=lambda n=theme_name: self._change_theme(n))
        
        # Zoom submenu
        view_menu.add_separator()
        view_menu.add_command(label="Zoom In", command=self._zoom_in, accelerator="Ctrl++")
        view_menu.add_command(label="Zoom Out", command=self._zoom_out, accelerator="Ctrl+-")
        view_menu.add_command(label="Fit to Window", command=self._zoom_fit, accelerator="Ctrl+0")
        
        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0, bg=t["menu_bg"], fg=t["menu_fg"],
                            activebackground=t["menu_hover"], activeforeground=t["selection_fg"])
        menubar.add_cascade(label="Tools", menu=tools_menu)
        tools_menu.add_command(label="Nest Parts on Sheets...", command=self._show_nesting_dialog)
        tools_menu.add_separator()
        tools_menu.add_command(label="Scan for Labels...", command=self._scan_for_labels)
    
    def _setup_tools_panel(self):
        """Setup the tools panel (left sidebar)."""
        t = self.theme
        
        config = PanelConfig(
            name="tools",
            icon="🔧",
            title="Tools",
            min_width=200,
            max_width=350,
            default_width=self.settings.sidebar_width,
            side="left"
        )
        
        tools_panel = self.layout.add_panel("tools", config)
        content = tools_panel.content
        
        # Scrollable content
        canvas = tk.Canvas(content, bg=t["bg"], highlightthickness=0)
        scroll = ttk.Scrollbar(content, orient="vertical", command=canvas.yview)
        frame = tk.Frame(canvas, bg=t["bg"])
        frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=frame, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Bind mousewheel only when mouse is over this canvas
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        def _bind_mousewheel(event):
            canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        def _unbind_mousewheel(event):
            canvas.unbind_all("<MouseWheel>")
        
        canvas.bind("<Enter>", _bind_mousewheel)
        canvas.bind("<Leave>", _unbind_mousewheel)
        frame.bind("<Enter>", _bind_mousewheel)
        frame.bind("<Leave>", _unbind_mousewheel)
        
        # Mode section
        mode_section = CollapsibleFrame(frame, "Selection Mode", theme=t)
        mode_section.pack(fill=tk.X, padx=8, pady=4)
        
        self.mode_var = tk.StringVar(value="flood")
        for mode, desc in self.MODES.items():
            rb = ttk.Radiobutton(mode_section.content, text=mode.capitalize(), 
                                variable=self.mode_var, value=mode,
                                command=lambda m=mode: self._set_mode(m))
            rb.pack(anchor=tk.W, padx=8, pady=2)
        
        # Categories section
        cat_section = CollapsibleFrame(frame, "Categories", theme=t)
        cat_section.pack(fill=tk.X, padx=8, pady=4)
        
        ttk.Button(cat_section.content, text="🔍 Scan Labels", 
                   command=self._scan_labels).pack(fill=tk.X, padx=8, pady=4)
        
        self.cat_frame = tk.Frame(cat_section.content, bg=t["bg"])
        self.cat_frame.pack(fill=tk.X, padx=8, pady=4)
        self.category_var = tk.StringVar()
        self._refresh_categories()
        
        # Label position
        label_section = CollapsibleFrame(frame, "Label Position", theme=t)
        label_section.pack(fill=tk.X, padx=8, pady=4)
        
        self.position_grid = PositionGrid(label_section.content, self._set_label_position, "center")
        self.position_grid.pack(padx=8, pady=4)
        
        self.show_labels_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(label_section.content, text="Show labels", 
                        variable=self.show_labels_var, 
                        command=self._toggle_labels).pack(padx=8, anchor=tk.W)
        
        # Group mode section
        group_section = CollapsibleFrame(frame, "Group Selection", theme=t)
        group_section.pack(fill=tk.X, padx=8, pady=4)
        
        self.group_mode_var = tk.BooleanVar()
        ttk.Checkbutton(group_section.content, text="Group Mode", 
                        variable=self.group_mode_var,
                        command=self._toggle_group_mode).pack(anchor=tk.W, padx=8, pady=2)
        ttk.Button(group_section.content, text="End Group & Create",
                   command=self._finish_group).pack(fill=tk.X, padx=8, pady=4)
        self.group_count = tk.Label(group_section.content, text="Elements: 0", 
                                   fg=t["accent"], bg=t["bg"], font=("Segoe UI", 9))
        self.group_count.pack(anchor=tk.W, padx=8, pady=2)
        
        # Pixel selection mode section
        pixel_section = CollapsibleFrame(frame, "Pixel Selection", theme=t)
        pixel_section.pack(fill=tk.X, padx=8, pady=4)
        
        self.pixel_selection_mode_var = tk.BooleanVar()
        ttk.Checkbutton(pixel_section.content, text="Pixel Selection Mode", 
                        variable=self.pixel_selection_mode_var,
                        command=self._toggle_pixel_selection_mode).pack(anchor=tk.W, padx=8, pady=2)
        # Use regular tk.Label for ttk.Label doesn't support fg/bg directly
        tk.Label(pixel_section.content, 
                 text="When enabled, selection tools\ncreate pixel selections instead\nof objects. Right-click for actions.",
                 fg=t["fg"], bg=t["bg"], font=("Segoe UI", 8),
                 justify=tk.LEFT).pack(anchor=tk.W, padx=8, pady=2)
        ttk.Button(pixel_section.content, text="Clear Selection",
                   command=self._clear_pixel_selection).pack(fill=tk.X, padx=8, pady=4)
        
        # Current view section
        view_section = CollapsibleFrame(frame, "Current View", theme=t)
        view_section.pack(fill=tk.X, padx=8, pady=4)
        
        view_frame = tk.Frame(view_section.content, bg=t["bg"])
        view_frame.pack(fill=tk.X, padx=8, pady=4)
        
        tk.Label(view_frame, text="Assign to view:", bg=t["bg"], fg=t["fg_muted"],
                font=("Segoe UI", 9)).pack(side=tk.LEFT)
        
        self.current_view_var = tk.StringVar(value="")
        self.view_combo = ttk.Combobox(view_frame, textvariable=self.current_view_var,
                                       values=["", "Plan", "Front", "Side", "Top", "Iso", "Detail"],
                                       width=10)
        self.view_combo.pack(side=tk.RIGHT)
        self.view_combo.bind("<<ComboboxSelected>>", self._on_view_changed)
        
        tk.Label(view_section.content, text="New objects will be assigned this view",
                bg=t["bg"], fg=t["fg_subtle"], font=("Segoe UI", 8)).pack(anchor=tk.W, padx=8)
        
        # Quick actions
        action_section = CollapsibleFrame(frame, "Quick Actions", theme=t)
        action_section.pack(fill=tk.X, padx=8, pady=4)
        
        ttk.Button(action_section.content, text="Undo", 
                   command=self._undo).pack(fill=tk.X, padx=8, pady=2)
        ttk.Button(action_section.content, text="Cancel",
                   command=self._cancel).pack(fill=tk.X, padx=8, pady=2)
        
        # Zoom controls
        zoom_frame = tk.Frame(action_section.content, bg=t["bg"])
        zoom_frame.pack(fill=tk.X, padx=8, pady=4)
        
        ttk.Button(zoom_frame, text="−", width=3, command=self._zoom_out).pack(side=tk.LEFT)
        self.zoom_label = tk.Label(zoom_frame, text="100%", width=6, bg=t["bg"], fg=t["fg"])
        self.zoom_label.pack(side=tk.LEFT, padx=8)
        ttk.Button(zoom_frame, text="+", width=3, command=self._zoom_in).pack(side=tk.LEFT)
        ttk.Button(zoom_frame, text="Fit", width=4, command=self._zoom_fit).pack(side=tk.LEFT, padx=8)
        
        # Store reference for theme changes
        self.tools_panel_frame = frame
    
    def _setup_center(self, parent):
        """Setup center notebook for pages."""
        t = self.theme
        
        self.notebook = ttk.Notebook(parent)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)
        
        # Welcome tab with modern styling
        welcome = tk.Frame(self.notebook, bg=t["bg_base"])
        self.notebook.add(welcome, text="Welcome")
        
        # Center content
        center_frame = tk.Frame(welcome, bg=t["bg_base"])
        center_frame.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        
        # Logo/Title
        tk.Label(center_frame, text="🗺️", font=("Segoe UI", 48), 
                bg=t["bg_base"], fg=t["accent"]).pack(pady=(0, 10))
        tk.Label(center_frame, text=f"PlanMod Segmenter", font=("Segoe UI", 24, "bold"),
                bg=t["bg_base"], fg=t["fg"]).pack()
        tk.Label(center_frame, text=f"Version {VERSION}", font=("Segoe UI", 11),
                bg=t["bg_base"], fg=t["fg_muted"]).pack(pady=(0, 30))
        
        # Quick start buttons
        btn_frame = tk.Frame(center_frame, bg=t["bg_base"])
        btn_frame.pack()
        
        ttk.Button(btn_frame, text="📄 Open PDF", style="Accent.TButton",
                  command=self._open_pdf).pack(side=tk.LEFT, padx=8)
        ttk.Button(btn_frame, text="📁 Open Workspace",
                  command=self._load_workspace).pack(side=tk.LEFT, padx=8)
        
        # Shortcuts hint
        tk.Label(center_frame, text="Ctrl+N: New PDF  •  Ctrl+O: Open Workspace  •  Ctrl+S: Save",
                font=("Segoe UI", 9), bg=t["bg_base"], fg=t["fg_subtle"]).pack(pady=(30, 0))
    
    def _setup_object_panel(self):
        """Setup right panel with object tree."""
        t = self.theme
        
        config = PanelConfig(
            name="objects",
            icon="📋",
            title="Objects",
            min_width=200,
            max_width=400,
            default_width=self.settings.tree_width,
            side="right"
        )
        
        objects_panel = self.layout.add_panel("objects", config)
        content = objects_panel.content
        
        # Statistics frame (mark_text, mark_hatch, mark_line counts)
        stats_frame = tk.Frame(content, bg=t["bg"])
        stats_frame.pack(fill=tk.X, padx=8, pady=(8, 0))
        
        self.mark_text_count_label = tk.Label(stats_frame, text="Mark Text: 0", bg=t["bg"], fg=t["fg_muted"],
                                             font=("Segoe UI", 9))
        self.mark_text_count_label.pack(side=tk.LEFT, padx=(0, 8))
        
        self.mark_hatch_count_label = tk.Label(stats_frame, text="Mark Hatch: 0", bg=t["bg"], fg=t["fg_muted"],
                                               font=("Segoe UI", 9))
        self.mark_hatch_count_label.pack(side=tk.LEFT, padx=(0, 8))
        
        self.mark_line_count_label = tk.Label(stats_frame, text="Mark Line: 0", bg=t["bg"], fg=t["fg_muted"],
                                             font=("Segoe UI", 9))
        self.mark_line_count_label.pack(side=tk.LEFT)
        
        # Grouping options
        group_frame = tk.Frame(content, bg=t["bg"])
        group_frame.pack(fill=tk.X, padx=8, pady=8)
        
        tk.Label(group_frame, text="Group by:", bg=t["bg"], fg=t["fg_muted"],
                font=("Segoe UI", 9)).pack(side=tk.LEFT)
        self.tree_grouping_var = tk.StringVar(value="category")
        group_combo = ttk.Combobox(group_frame, textvariable=self.tree_grouping_var,
                                   values=["category", "view"], state="readonly", width=10)
        group_combo.pack(side=tk.LEFT, padx=8)
        group_combo.bind("<<ComboboxSelected>>", lambda e: self._update_tree())
        
        # Tree
        tree_frame = tk.Frame(content, bg=t["bg"])
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        
        tree_scroll = ttk.Scrollbar(tree_frame)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.object_tree = ttk.Treeview(tree_frame, yscrollcommand=tree_scroll.set, selectmode="extended")
        self.object_tree.pack(fill=tk.BOTH, expand=True)
        tree_scroll.config(command=self.object_tree.yview)
        
        self.object_tree.heading("#0", text="Objects")
        self.object_tree.column("#0", width=250)
        self.object_tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.object_tree.bind("<Button-1>", self._on_tree_click)
        self.object_tree.bind("<Double-1>", self._on_tree_double_click)
        self.object_tree.bind("<Button-3>", self._on_tree_right_click)
        
        # Mousewheel scrolling for tree only when mouse is over it
        def _tree_mousewheel(event):
            self.object_tree.yview_scroll(int(-1*(event.delta/120)), "units")
        
        def _bind_tree_scroll(event):
            self.object_tree.bind_all("<MouseWheel>", _tree_mousewheel)
        
        def _unbind_tree_scroll(event):
            self.object_tree.unbind_all("<MouseWheel>")
        
        self.object_tree.bind("<Enter>", _bind_tree_scroll)
        self.object_tree.bind("<Leave>", _unbind_tree_scroll)
        
        self.tree_icons = {}
        
        # Checkbox to toggle auto-load image on selection
        options_frame = tk.Frame(content, bg=t["bg"])
        options_frame.pack(fill=tk.X, padx=8, pady=(0, 4))
        
        self.auto_show_image_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Show image on select",
                       variable=self.auto_show_image_var).pack(anchor=tk.W)
        
        # Collapse/expand buttons
        expand_frame = tk.Frame(content, bg=t["bg"])
        expand_frame.pack(fill=tk.X, padx=8, pady=4)
        
        ttk.Button(expand_frame, text="Expand All", width=10,
                  command=self._expand_all_tree).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(expand_frame, text="Collapse All", width=10,
                  command=self._collapse_all_tree).pack(side=tk.LEFT)
        
        # Hint text
        hint_label = tk.Label(content, text="Right-click for actions",
                             bg=t["bg"], fg=t["fg_subtle"], font=("Segoe UI", 8))
        hint_label.pack(pady=(4, 8))
    
    def _bind_events(self):
        """Bind keyboard shortcuts."""
        self.root.bind("<Control-n>", lambda e: self._open_pdf())
        self.root.bind("<Control-o>", lambda e: self._load_workspace())
        self.root.bind("<Control-s>", lambda e: self._save_workspace())
        self.root.bind("<Control-z>", lambda e: self._undo())
        self.root.bind("<Escape>", lambda e: self._cancel())
        self.root.bind("<Return>", lambda e: self._on_enter())
        
        # Panel toggles
        self.root.bind("<Control-b>", lambda e: self.layout._on_panel_toggle("tools"))
        self.root.bind("<Control-j>", lambda e: self.layout._on_panel_toggle("objects"))
        
        # Zoom shortcuts
        self.root.bind("<Control-plus>", lambda e: self._zoom_in())
        self.root.bind("<Control-equal>", lambda e: self._zoom_in())  # For keyboards without numpad
        self.root.bind("<Control-minus>", lambda e: self._zoom_out())
        self.root.bind("<Control-0>", lambda e: self._zoom_fit())
        
        # Window resize tracking
        self.root.bind("<Configure>", self._on_window_resize)
        
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
    
    def _on_window_resize(self, event):
        """Handle window resize for responsive layout."""
        if event.widget == self.root:
            # Save window size to settings
            self.settings.window_width = self.root.winfo_width()
            self.settings.window_height = self.root.winfo_height()
    
    # ... (continuing with essential methods)
    
    def _get_current_page(self) -> Optional[PageTab]:
        return self.pages.get(self.current_page_id)
    
    def _get_mask_hash(self, mask: Optional[np.ndarray]) -> Optional[int]:
        """Get a hash/checksum of a mask for change detection."""
        if mask is None:
            return None
        # Use a simple hash of mask shape and sum of pixel values
        # This is fast and sufficient for detecting changes
        return hash((mask.shape, int(np.sum(mask))))
    
    def _get_working_image(self, page: PageTab, use_cache: bool = True) -> np.ndarray:
        """Get image with text/hatch/line hidden based on category visibility."""
        # Check category visibility (not page hide flags)
        mark_text_cat = self.categories.get("mark_text")
        mark_hatch_cat = self.categories.get("mark_hatch")
        mark_line_cat = self.categories.get("mark_line")
        
        should_hide_text = mark_text_cat is not None and not mark_text_cat.visible
        should_hide_hatching = mark_hatch_cat is not None and not mark_hatch_cat.visible
        should_hide_lines = mark_line_cat is not None and not mark_line_cat.visible
        
        # Create visibility state key for caching
        visibility_state = (
            should_hide_text,
            should_hide_hatching,
            should_hide_lines,
            page.tab_id
        )
        
        # Get current mask hashes
        h, w = page.original_image.shape[:2]
        text_mask = getattr(page, 'combined_text_mask', None) if should_hide_text else None
        hatch_mask = getattr(page, 'combined_hatch_mask', None) if should_hide_hatching else None
        line_mask = getattr(page, 'combined_line_mask', None) if should_hide_lines else None
        
        current_mask_hashes = {
            'text': self._get_mask_hash(text_mask),
            'hatch': self._get_mask_hash(hatch_mask),
            'line': self._get_mask_hash(line_mask)
        }
        
        # Check cache and update incrementally if possible
        if use_cache and self._working_image_cache is not None:
            cached_page_id, cached_visibility, cached_image, cached_mask_hashes = self._working_image_cache
            if cached_page_id == page.tab_id and cached_visibility == visibility_state:
                # Check if masks have changed
                masks_changed = False
                updated_image = cached_image.copy()
                
                # Incrementally update for each mask type
                for mask_type in ['text', 'hatch', 'line']:
                    old_hash = cached_mask_hashes.get(mask_type)
                    new_hash = current_mask_hashes.get(mask_type)
                    
                    if old_hash != new_hash:
                        masks_changed = True
                        # Update this mask type in the cached image
                        if mask_type == 'text' and should_hide_text and text_mask is not None and text_mask.shape == (h, w):
                            updated_image[text_mask > 0] = [255, 255, 255]
                        elif mask_type == 'hatch' and should_hide_hatching and hatch_mask is not None and hatch_mask.shape == (h, w):
                            updated_image[hatch_mask > 0] = [255, 255, 255]
                        elif mask_type == 'line' and should_hide_lines and line_mask is not None and line_mask.shape == (h, w):
                            updated_image[line_mask > 0] = [255, 255, 255]
                
                if not masks_changed:
                    # No changes, return cached image
                    return cached_image.copy()
                else:
                    # Masks changed, update cache with new image and hashes
                    self._working_image_cache = (page.tab_id, visibility_state, updated_image, current_mask_hashes)
                    return updated_image
        
        # Need to recompute from scratch
        image = page.original_image.copy()  # Need copy since we'll modify pixels
        
        # Apply text mask if category is hidden
        if should_hide_text and text_mask is not None and text_mask.shape == (h, w):
            image[text_mask > 0] = [255, 255, 255]
        
        # Apply hatching mask if category is hidden
        if should_hide_hatching and hatch_mask is not None and hatch_mask.shape == (h, w):
            image[hatch_mask > 0] = [255, 255, 255]
        
        # Apply line mask if category is hidden
        if should_hide_lines and line_mask is not None and line_mask.shape == (h, w):
            image[line_mask > 0] = [255, 255, 255]
        
        # Update cache
        if use_cache:
            self._working_image_cache = (page.tab_id, visibility_state, image.copy(), current_mask_hashes)
        
        return image
    
    def _invalidate_working_image_cache(self):
        """Invalidate the working image cache (call when masks or visibility change)."""
        self._working_image_cache = None
    
    def _update_working_image_cache_for_mask(self, page: PageTab, mask_type: str, new_mask: Optional[np.ndarray]):
        """
        Incrementally update the working image cache when a mask is added/updated.
        For removal, use _update_working_image_cache_for_mask_with_old instead.
        """
        # This is a convenience wrapper that gets the old mask from the page
        # (but it may already be updated, so use with_old version for deletions)
        old_mask = None
        if mask_type == 'text':
            old_mask = getattr(page, 'combined_text_mask', None)
        elif mask_type == 'hatch':
            old_mask = getattr(page, 'combined_hatch_mask', None)
        elif mask_type == 'line':
            old_mask = getattr(page, 'combined_line_mask', None)
        
        self._update_working_image_cache_for_mask_with_old(page, mask_type, new_mask, old_mask)
    
    def _update_working_image_cache_for_mask_with_old(self, page: PageTab, mask_type: str, 
                                                      new_mask: Optional[np.ndarray], 
                                                      old_mask: Optional[np.ndarray]):
        """
        Incrementally update the working image cache when a mask is added/updated/removed.
        
        Handles both addition (hide pixels) and removal (unhide pixels) of masks.
        
        Args:
            page: The page being updated
            mask_type: 'text', 'hatch', or 'line'
            new_mask: The new combined mask (after update)
            old_mask: The old combined mask (before update) - needed for restoration
        """
        if self._working_image_cache is None:
            return  # No cache to update
        
        cached_page_id, cached_visibility, cached_image, cached_mask_hashes = self._working_image_cache
        
        # Check if this update applies to the cached page and visibility
        mark_text_cat = self.categories.get("mark_text")
        mark_hatch_cat = self.categories.get("mark_hatch")
        mark_line_cat = self.categories.get("mark_line")
        
        should_hide_text = mark_text_cat is not None and not mark_text_cat.visible
        should_hide_hatching = mark_hatch_cat is not None and not mark_hatch_cat.visible
        should_hide_lines = mark_line_cat is not None and not mark_line_cat.visible
        
        visibility_state = (
            should_hide_text,
            should_hide_hatching,
            should_hide_lines,
            page.tab_id
        )
        
        if cached_page_id == page.tab_id and cached_visibility == visibility_state:
            h, w = cached_image.shape[:2]
            
            # Handle mask removal: restore pixels from original image
            if old_mask is not None and old_mask.shape == (h, w):
                # Find pixels that were in old mask but not in new mask (pixels to restore)
                if new_mask is not None and new_mask.shape == (h, w):
                    pixels_to_restore = (old_mask > 0) & (new_mask == 0)
                else:
                    # New mask is None or wrong size - restore all old mask pixels
                    pixels_to_restore = (old_mask > 0)
                
                if np.any(pixels_to_restore):
                    # Check if pixels should still be hidden by OTHER mask types
                    # Build combined mask of OTHER types (excluding this mask_type)
                    other_masks_combined = np.zeros((h, w), dtype=np.uint8)
                    if mask_type != 'text' and should_hide_text:
                        other_text_mask = getattr(page, 'combined_text_mask', None)
                        if other_text_mask is not None and other_text_mask.shape == (h, w):
                            other_masks_combined = np.maximum(other_masks_combined, other_text_mask)
                    if mask_type != 'hatch' and should_hide_hatching:
                        other_hatch_mask = getattr(page, 'combined_hatch_mask', None)
                        if other_hatch_mask is not None and other_hatch_mask.shape == (h, w):
                            other_masks_combined = np.maximum(other_masks_combined, other_hatch_mask)
                    if mask_type != 'line' and should_hide_lines:
                        other_line_mask = getattr(page, 'combined_line_mask', None)
                        if other_line_mask is not None and other_line_mask.shape == (h, w):
                            other_masks_combined = np.maximum(other_masks_combined, other_line_mask)
                    
                    # Only restore pixels that are NOT in other masks
                    pixels_to_restore = pixels_to_restore & (other_masks_combined == 0)
                    
                    if np.any(pixels_to_restore):
                        # Restore pixels from original image (only those not hidden by other masks)
                        cached_image[pixels_to_restore] = page.original_image[pixels_to_restore]
            
            # Handle mask addition/update: hide pixels in new mask
            if new_mask is not None and new_mask.shape == (h, w):
                # Check if this mask type should be applied
                should_apply = False
                if mask_type == 'text' and should_hide_text:
                    should_apply = True
                elif mask_type == 'hatch' and should_hide_hatching:
                    should_apply = True
                elif mask_type == 'line' and should_hide_lines:
                    should_apply = True
                
                if should_apply:
                    # Hide pixels in the new mask
                    cached_image[new_mask > 0] = [255, 255, 255]
            
            # Update the mask hash
            new_hash = self._get_mask_hash(new_mask)
            cached_mask_hashes[mask_type] = new_hash
            # Update cache
            self._working_image_cache = (cached_page_id, cached_visibility, cached_image, cached_mask_hashes)
    
    def _refresh_categories(self):
        """Refresh category list in sidebar."""
        for w in self.cat_frame.winfo_children():
            w.destroy()
        
        # Store visibility vars
        if not hasattr(self, 'cat_visibility_vars'):
            self.cat_visibility_vars = {}
        
        # Get set of categories in use
        used_categories = self._get_used_categories()
        
        # Protected categories that can never be deleted
        protected_categories = {"planform", "textbox", "mark_text", "mark_hatch", "mark_line"}
        
        for name in sorted(self.categories.keys()):
            cat = self.categories[name]
            f = ttk.Frame(self.cat_frame)
            f.pack(fill=tk.X, pady=1)
            
            # Visibility checkbox
            if name not in self.cat_visibility_vars:
                self.cat_visibility_vars[name] = tk.BooleanVar(value=cat.visible)
            else:
                self.cat_visibility_vars[name].set(cat.visible)
            
            ttk.Checkbutton(f, variable=self.cat_visibility_vars[name],
                           command=lambda n=name: self._toggle_category_visibility(n)).pack(side=tk.LEFT)
            
            # Color swatch
            color_hex = cat.color_hex
            tk.Label(f, width=2, bg=color_hex).pack(side=tk.LEFT, padx=2)
            
            # Radio button for selection
            ttk.Radiobutton(f, text=cat.name, variable=self.category_var, value=name,
                           command=lambda n=name: self._select_category(n)).pack(side=tk.LEFT)
            
            # Delete button - only show if category not in use and not protected
            if name not in used_categories and name not in protected_categories:
                del_btn = ttk.Button(f, text="🗑", width=2,
                                    command=lambda n=name: self._delete_category(n))
                del_btn.pack(side=tk.RIGHT, padx=2)
        
        # Add new category section
        add_frame = ttk.Frame(self.cat_frame)
        add_frame.pack(fill=tk.X, pady=(5, 2))
        
        self.new_cat_entry = ttk.Entry(add_frame, width=10)
        self.new_cat_entry.pack(side=tk.LEFT, padx=2)
        self.new_cat_entry.bind("<Return>", lambda e: self._add_custom_category())
        
        ttk.Button(add_frame, text="+", width=2, command=self._add_custom_category).pack(side=tk.LEFT)
    
    def _get_used_categories(self) -> set:
        """Get set of category names that are currently in use by objects."""
        used = set()
        for obj in self.all_objects:
            used.add(obj.category)
        return used
    
    def _delete_category(self, name: str):
        """Delete an unused category."""
        if name in self._get_used_categories():
            messagebox.showwarning("Cannot Delete", 
                                  f"Category '{name}' is in use by objects and cannot be deleted.",
                                  parent=self.root)
            return
        
        if messagebox.askyesno("Confirm Delete", 
                              f"Delete category '{name}'?", parent=self.root):
            del self.categories[name]
            if name in self.cat_visibility_vars:
                del self.cat_visibility_vars[name]
            self.workspace_modified = True
            self._refresh_categories()
            self.status_var.set(f"Deleted category: {name}")
    
    def _toggle_category_visibility(self, name: str):
        """Toggle visibility of a category."""
        if name in self.categories and name in self.cat_visibility_vars:
            self.categories[name].visible = self.cat_visibility_vars[name].get()
            print(f"DEBUG: Category '{name}' visibility set to {self.categories[name].visible}")
            # Invalidate working image cache since visibility state changed
            # (can't incrementally update when visibility changes)
            self._invalidate_working_image_cache()
            self.renderer.invalidate_cache()
            self._update_display(immediate=True)
    
    def _add_custom_category(self):
        """Add a user-defined category."""
        name = self.new_cat_entry.get().strip()
        if not name:
            return
        
        if name in self.categories:
            messagebox.showinfo("Info", f"Category '{name}' already exists", parent=self.root)
            return
        
        color = get_next_color(len(self.categories))
        self.categories[name] = DynamicCategory(
            name=name, prefix=name[0].upper(), full_name=name,
            color_rgb=color, selection_mode="flood"
        )
        self.workspace_modified = True
        self._refresh_categories()
        self.category_var.set(name)  # Select the new category
        self.status_var.set(f"Added category: {name}")
    
    def _set_mode(self, mode: str):
        self.current_mode = mode
        self._cancel()
        # Update status bar
        self.status_bar.set_item_text("mode", mode.capitalize())
    
    def _cancel(self):
        """Cancel current operation."""
        # Cancel move operations
        if self.is_moving_objects:
            self.is_moving_objects = False
            self.object_move_start = None
            self.object_move_offset = None
            page = self._get_current_page()
            if page and hasattr(page, 'canvas'):
                page.canvas.config(cursor="crosshair")
            self._update_display()
            self.status_var.set("Move cancelled")
            return
        
        if self.is_moving_pixels:
            self.is_moving_pixels = False
            self.pixel_move_start = None
            self.pixel_move_offset = None
            page = self._get_current_page()
            if page and hasattr(page, 'canvas'):
                page.canvas.config(cursor="crosshair")
            self._update_display()
            self.status_var.set("Move cancelled")
            return
        
        # Cancel drawing operations
        self.current_points.clear()
        self.is_drawing = False
        self.rect_start = None
        self.rect_current = None
        page = self._get_current_page()
        if page and hasattr(page, 'canvas'):
            page.canvas.delete("temp")
            page.canvas.delete("rect")
        self._redraw_points()
    
    def _select_category(self, name: str):
        """Select a category. Does NOT automatically change selection mode."""
        # Categories no longer auto-change mode - user controls mode separately
        # This allows using any mode (flood, polyline, freeform) with any category
        pass
    
    def _set_label_position(self, pos: str):
        self.label_position = pos
    
    def _toggle_labels(self):
        self.show_labels = self.show_labels_var.get()
        self.settings.show_labels = self.show_labels
        save_settings(self.settings)
        self._update_display()
    
    def _toggle_group_mode(self):
        self.group_mode_active = self.group_mode_var.get()
        if self.group_mode_active:
            self.group_mode_elements.clear()
            self.status_var.set("GROUP MODE: Create elements to group together")
        self._update_group_count()
    
    def _toggle_pixel_selection_mode(self):
        """Toggle pixel selection mode on/off."""
        pixel_mode = self.pixel_selection_mode_var.get()
        if pixel_mode:
            self.status_var.set("PIXEL SELECTION MODE: Selection tools will create pixel selections")
        else:
            self.status_var.set("")
    
    def _update_group_count(self):
        self.group_count.config(text=f"Elements: {len(self.group_mode_elements)}")
    
    def _finish_group(self):
        if len(self.group_mode_elements) < 1:
            messagebox.showinfo("Info", "Create at least 1 element first")
            return
        
        page = self._get_current_page()
        if not page:
            return
        
        cat_name = self.category_var.get() or "R"
        cat = self.categories.get(cat_name)
        prefix = cat.prefix if cat else cat_name[0].upper()
        count = sum(1 for o in self.all_objects if o.category == cat_name) + 1
        
        # Get current view if set
        current_view = getattr(self, 'current_view_var', None)
        view_type = current_view.get() if current_view else ""
        
        name = simpledialog.askstring("Object Name", f"Name ({len(self.group_mode_elements)} elements):",
                                      initialvalue=f"{prefix}{count}", parent=self.root)
        if not name:
            return
        
        obj = SegmentedObject(name=name, category=cat_name)
        inst = ObjectInstance(instance_num=1, page_id=page.tab_id, view_type=view_type)
        inst.elements = list(self.group_mode_elements)
        obj.instances.append(inst)
        self.all_objects.append(obj)
        
        # Clear elements but keep group mode active - user can turn it off manually
        self.group_mode_elements.clear()
        # Don't turn off group mode automatically
        # self.group_mode_var.set(False)
        # self.group_mode_active = False
        self._update_group_count()
        self.workspace_modified = True
        self.renderer.invalidate_cache()
        self._add_tree_item(obj)  # Incremental add
        self._update_display()
        self.status_var.set(f"Created: {name} - Group mode still active")
    
    def _adjust(self, setting: str, delta: int):
        if setting == "tolerance":
            self.settings.tolerance = max(1, min(100, self.settings.tolerance + delta))
            self.engine.tolerance = self.settings.tolerance
            self.tol_label.config(text=str(self.settings.tolerance))
        elif setting == "snap":
            self.settings.snap_distance = max(5, min(50, self.settings.snap_distance + delta))
            self.snap_label.config(text=str(self.settings.snap_distance))
    
    def _on_opacity(self, val):
        self.settings.planform_opacity = float(val)
        self._update_display()
    
    def _zoom_in(self):
        self.zoom_level = min(5.0, self.zoom_level * 1.25)
        self._update_display()
    
    def _zoom_out(self):
        self.zoom_level = max(0.1, self.zoom_level / 1.25)
        self._update_display()
    
    def _zoom_fit(self):
        page = self._get_current_page()
        if not page or page.original_image is None or not hasattr(page, 'canvas'):
            return
        h, w = page.original_image.shape[:2]
        cw = max(page.canvas.winfo_width(), 100)
        ch = max(page.canvas.winfo_height(), 100)
        self.zoom_level = min(cw / w, ch / h) * 0.9
        self._update_display()
        self._draw_rulers(page)
    
    def _scroll_with_rulers(self, page: PageTab, direction: str, *args):
        """Scroll canvas and update rulers."""
        if direction == 'h':
            page.canvas.xview(*args)
        else:
            page.canvas.yview(*args)
        self._draw_rulers(page)
    
    def _draw_rulers(self, page: PageTab = None):
        """Draw rulers for a page."""
        if page is None:
            page = self._get_current_page()
        if not page or not hasattr(page, 'h_ruler') or not hasattr(page, 'v_ruler'):
            return
        
        # Check if rulers should be shown
        if not self.settings.show_ruler:
            page.h_ruler.delete("all")
            page.v_ruler.delete("all")
            return
        
        # Get colors from theme
        bg_color = self.theme.get("bg_secondary", "#313244")
        fg_color = self.theme.get("fg", "#cdd6f4")
        tick_color = self.theme.get("fg_muted", "#a6adc8")
        
        # Get scale info
        ppi = page.pixels_per_inch  # Pixels per inch at 100% zoom
        ppi_zoomed = ppi * self.zoom_level  # Pixels per inch at current zoom
        
        unit = self.settings.ruler_unit
        
        # Draw horizontal ruler
        self._draw_h_ruler(page, ppi_zoomed, unit, bg_color, fg_color, tick_color)
        
        # Draw vertical ruler
        self._draw_v_ruler(page, ppi_zoomed, unit, bg_color, fg_color, tick_color)
    
    def _draw_h_ruler(self, page: PageTab, ppi: float, unit: str, bg: str, fg: str, tick_color: str):
        """Draw horizontal ruler."""
        ruler = page.h_ruler
        ruler.delete("all")
        
        # Get visible region
        ruler_w = ruler.winfo_width()
        ruler_h = page.ruler_size
        
        if ruler_w <= 1:
            return
        
        # Get scroll position
        x_offset = 0
        if hasattr(page, 'canvas'):
            try:
                x_view = page.canvas.xview()
                if page.original_image is not None:
                    img_w = page.original_image.shape[1] * self.zoom_level
                    x_offset = x_view[0] * img_w
            except:
                pass
        
        # Calculate unit intervals
        if unit == "inch":
            pixels_per_unit = ppi
            major_interval = 1.0  # 1 inch
            subdivisions = [(0.5, 0.6), (0.25, 0.4), (0.125, 0.25), (0.0625, 0.15)]  # (fraction, height_ratio)
        else:  # cm
            pixels_per_unit = ppi / 2.54
            major_interval = 1.0  # 1 cm
            subdivisions = [(0.5, 0.5), (0.1, 0.3)]  # 5mm and 1mm marks
        
        # Draw background
        ruler.create_rectangle(0, 0, ruler_w, ruler_h, fill=bg, outline="")
        
        # Draw ticks
        start_unit = int(x_offset / pixels_per_unit)
        end_unit = int((x_offset + ruler_w) / pixels_per_unit) + 2
        
        for i in range(start_unit, end_unit):
            x = i * pixels_per_unit - x_offset
            
            if 0 <= x <= ruler_w:
                # Major tick
                ruler.create_line(x, ruler_h, x, ruler_h * 0.2, fill=fg, width=1)
                # Label
                label = f"{i}" if unit == "inch" else f"{i}"
                ruler.create_text(x + 3, ruler_h * 0.4, text=label, anchor="w", 
                                 fill=fg, font=("TkDefaultFont", 7))
            
            # Subdivision ticks
            for frac, height_ratio in subdivisions:
                sub_x = x + frac * pixels_per_unit
                if 0 <= sub_x <= ruler_w:
                    tick_h = ruler_h * height_ratio
                    ruler.create_line(sub_x, ruler_h, sub_x, ruler_h - tick_h, fill=tick_color, width=1)
    
    def _draw_v_ruler(self, page: PageTab, ppi: float, unit: str, bg: str, fg: str, tick_color: str):
        """Draw vertical ruler."""
        ruler = page.v_ruler
        ruler.delete("all")
        
        ruler_w = page.ruler_size
        ruler_h = ruler.winfo_height()
        
        if ruler_h <= 1:
            return
        
        # Get scroll position
        y_offset = 0
        if hasattr(page, 'canvas'):
            try:
                y_view = page.canvas.yview()
                if page.original_image is not None:
                    img_h = page.original_image.shape[0] * self.zoom_level
                    y_offset = y_view[0] * img_h
            except:
                pass
        
        # Calculate unit intervals
        if unit == "inch":
            pixels_per_unit = ppi
            subdivisions = [(0.5, 0.6), (0.25, 0.4), (0.125, 0.25), (0.0625, 0.15)]
        else:  # cm
            pixels_per_unit = ppi / 2.54
            subdivisions = [(0.5, 0.5), (0.1, 0.3)]
        
        # Draw background
        ruler.create_rectangle(0, 0, ruler_w, ruler_h, fill=bg, outline="")
        
        # Draw ticks
        start_unit = int(y_offset / pixels_per_unit)
        end_unit = int((y_offset + ruler_h) / pixels_per_unit) + 2
        
        for i in range(start_unit, end_unit):
            y = i * pixels_per_unit - y_offset
            
            if 0 <= y <= ruler_h:
                # Major tick
                ruler.create_line(ruler_w, y, ruler_w * 0.2, y, fill=fg, width=1)
                # Label (rotated text approximation)
                label = f"{i}"
                ruler.create_text(ruler_w * 0.4, y + 3, text=label, anchor="n",
                                 fill=fg, font=("TkDefaultFont", 7))
            
            # Subdivision ticks
            for frac, height_ratio in subdivisions:
                sub_y = y + frac * pixels_per_unit
                if 0 <= sub_y <= ruler_h:
                    tick_w = ruler_w * height_ratio
                    ruler.create_line(ruler_w, sub_y, ruler_w - tick_w, sub_y, fill=tick_color, width=1)
    
    def _toggle_ruler(self):
        """Toggle ruler visibility."""
        self.settings.show_ruler = not self.settings.show_ruler
        save_settings(self.settings)
        self._update_view_menu_labels()
        page = self._get_current_page()
        if page:
            self._draw_rulers(page)
    
    def _set_ruler_unit(self, unit: str):
        """Set ruler measurement unit."""
        self.settings.ruler_unit = unit
        save_settings(self.settings)
        page = self._get_current_page()
        if page:
            self._draw_rulers(page)
    
    def _undo(self):
        page = self._get_current_page()
        if not page or not self.all_objects:
            return
        
        # Find last object with instance on current page
        last = None
        for obj in reversed(self.all_objects):
            for inst in obj.instances:
                if inst.page_id == page.tab_id:
                    last = obj
                    break
            if last:
                break
        
        if not last:
            return
            
        if last.instances and last.instances[-1].elements:
            last.instances[-1].elements.pop()
            if not last.instances[-1].elements:
                last.instances.pop()
            if not last.instances:
                self.all_objects.remove(last)
                self._remove_tree_item(last.object_id)
            else:
                self._update_tree_item(last)
        self.workspace_modified = True
        self.renderer.invalidate_cache()
        self._update_display()
    
    
    def _on_enter(self):
        if self.current_mode == "line" and len(self.current_points) >= 2:
            self._finish_line()
        elif self.current_mode == "polyline" and len(self.current_points) >= 3:
            self._finish_polyline()
    
    def _change_theme(self, name: str):
        self.settings.theme = name
        save_settings(self.settings)
        messagebox.showinfo("Theme", f"Theme will be '{name}' on restart")
    
    def _toggle_hide_background(self):
        """Toggle hide background for current page."""
        page = self._get_current_page()
        if not page:
            return
        
        if not hasattr(page, 'hide_background'):
            page.hide_background = False
        page.hide_background = not page.hide_background
        
        self._update_view_menu_labels()
        self.renderer.invalidate_cache()
        self._update_display()
    
    def _run_ocr_for_page(self):
        """Run OCR on current page and add new text regions to marked text list."""
        page = self._get_current_page()
        if not page:
            return
        
        self.status_var.set("Running OCR...")
        self.root.update()
        
        # Detect text regions
        new_regions = self._detect_text_regions(page)
        
        if not new_regions:
            self.status_var.set("No text regions detected")
            return
        
        # Get existing region IDs to avoid duplicates
        existing_ids = set()
        if hasattr(page, 'auto_text_regions'):
            existing_ids.update(r.get('id', '') for r in page.auto_text_regions)
        if hasattr(page, 'manual_text_regions'):
            existing_ids.update(r.get('id', '') for r in page.manual_text_regions)
        
        # Filter out duplicates and add new regions
        if not hasattr(page, 'auto_text_regions'):
            page.auto_text_regions = []
        
        added_regions = []
        added_count = 0
        for region in new_regions:
            region_id = region.get('id', '')
            if region_id not in existing_ids:
                page.auto_text_regions.append(region)
                existing_ids.add(region_id)
                added_count += 1
                added_regions.append(region)  # Track which regions were actually added
        
        # Update combined mask
        self._update_combined_text_mask(page, force_recompute=True)
        
        # Add regions to mark_text category as objects (use the tracked list, not slice)
        objects_added = self._add_text_regions_to_category(page, added_regions)
        
        self.renderer.invalidate_cache()
        self._update_display()
        self.status_var.set(f"OCR complete: {added_count} new text regions added, {objects_added} objects created (total: {len(page.auto_text_regions)})")
    
    def _add_text_regions_to_category(self, page: PageTab, regions: list):
        """Add text regions as objects in the mark_text category. Returns number of objects created."""
        print(f"DEBUG: _add_text_regions_to_category called with {len(regions)} regions for page {page.tab_id}")
        if not regions:
            print("DEBUG: No regions to add")
            return 0
        
        mark_text_cat = self.categories.get("mark_text")
        if not mark_text_cat:
            # Create mark_text category if it doesn't exist (visible by default)
            mark_text_cat = DynamicCategory(
                name="mark_text", prefix="mark_text", full_name="Mark as Text",
                color_rgb=(255, 200, 0), selection_mode="flood", visible=True
            )
            self.categories["mark_text"] = mark_text_cat
            self._refresh_categories()
            print("DEBUG: Created mark_text category")
        
        objects_created = 0
        masks_missing = 0
        for region in regions:
            region_id = region.get('id', '')
            mask = region.get('mask')
            text = region.get('text', f"text_{region_id}")
            
            if mask is None:
                masks_missing += 1
                print(f"DEBUG: Region {region_id} has no mask, skipping")
                continue
            
            # Check if object already exists for this region
            existing_obj = None
            for obj in self.all_objects:
                if obj.category == "mark_text" and obj.name == text:
                    # Check if this instance is already on this page
                    for inst in obj.instances:
                        if inst.page_id == page.tab_id:
                            # Check if this element already exists
                            for elem in inst.elements:
                                if elem.element_id == region_id:
                                    existing_obj = obj
                                    break
                            if existing_obj:
                                break
                    if existing_obj:
                        break
            
            if existing_obj:
                # Add to existing object
                for obj in self.all_objects:
                    if obj.object_id == existing_obj.object_id:
                        # Find or create instance for this page
                        inst = None
                        for i in obj.instances:
                            if i.page_id == page.tab_id:
                                inst = i
                                break
                        
                        if not inst:
                            inst = ObjectInstance(
                                instance_id=f"{obj.object_id}_inst_{len(obj.instances) + 1}",
                                instance_num=len(obj.instances) + 1,
                                elements=[],
                                page_id=page.tab_id,
                                view_type=""
                            )
                            obj.instances.append(inst)
                        
                        # Add element if not already present
                        elem_exists = any(e.element_id == region_id for e in inst.elements)
                        if not elem_exists:
                            elem = SegmentElement(
                                element_id=region_id,
                                category="mark_text",
                                mode="auto",
                                points=[],
                                mask=mask,
                                color=mark_text_cat.color_rgb,
                                label_position="center"
                            )
                            inst.elements.append(elem)
            else:
                # Create new object
                elem = SegmentElement(
                    element_id=region_id,
                    category="mark_text",
                    mode="auto",
                    points=[],
                    mask=mask,
                    color=mark_text_cat.color_rgb,
                    label_position="center"
                )
                
                inst = ObjectInstance(
                    instance_id=f"mark_text_{region_id}_inst_1",
                    instance_num=1,
                    elements=[elem],
                    page_id=page.tab_id,
                    view_type="",
                    attributes=ObjectAttributes()
                )
                
                obj = SegmentedObject(
                    object_id=f"mark_text_{region_id}",
                    name=text,
                    category="mark_text",
                    instances=[inst]
                )
                
                self.all_objects.append(obj)
                objects_created += 1
                print(f"DEBUG: Created mark_text object '{text}' (id={obj.object_id}) with region_id '{region_id}' on page {page.tab_id}")
        
        # Update tree view and workspace state
        if objects_created > 0:
            self.workspace_modified = True
            # Get the last created object ID for selection
            last_obj_id = None
            if objects_created > 0:
                mark_text_objs = [o for o in self.all_objects if o.category == 'mark_text']
                if mark_text_objs:
                    last_obj_id = mark_text_objs[-1].object_id
            self._update_tree(preserve_state=True, select_object_id=last_obj_id)
            total_mark_text = sum(1 for o in self.all_objects if o.category == 'mark_text')
            print(f"DEBUG: Added {objects_created} mark_text objects. Total mark_text objects: {total_mark_text}")
            print(f"DEBUG: Tree should now show {total_mark_text} mark_text objects")
            # Invalidate cache since text mask changed
            self._invalidate_working_image_cache()
        else:
            print(f"DEBUG: No objects created from {len(regions)} regions (masks_missing={masks_missing})")
        return objects_created
    
    def _add_existing_text_regions_to_category(self, page: PageTab):
        """Add existing text regions from workspace to mark_text category.
        Also repairs masks for objects loaded from old workspace format."""
        # Collect all text regions (auto + manual)
        all_text_regions = []
        if hasattr(page, 'auto_text_regions'):
            all_text_regions.extend(page.auto_text_regions)
        if hasattr(page, 'manual_text_regions'):
            all_text_regions.extend(page.manual_text_regions)
        
        if not all_text_regions:
            return
        
        # Ensure mark_text category exists
        mark_text_cat = self.categories.get("mark_text")
        if not mark_text_cat:
            mark_text_cat = DynamicCategory(
                name="mark_text", prefix="mark_text", full_name="Mark as Text",
                color_rgb=(255, 200, 0), selection_mode="flood", visible=True
            )
            self.categories["mark_text"] = mark_text_cat
            self._refresh_categories()
        
        # Build a map of region_id -> mask from auto/manual regions
        region_masks = {}
        for region in all_text_regions:
            region_id = region.get('id', '')
            mask = region.get('mask')
            if region_id and mask is not None:
                region_masks[region_id] = mask
        
        # Repair masks for existing mark_text objects that have empty masks
        # This handles workspaces saved with old format (no RLE-encoded masks)
        existing_element_ids = set()
        repaired_count = 0
        for obj in self.all_objects:
            if obj.category == "mark_text":
                for inst in obj.instances:
                    if inst.page_id == page.tab_id:
                        for elem in inst.elements:
                            existing_element_ids.add(elem.element_id)
                            # Check if mask is empty or None and we have a region mask to repair it
                            if elem.mask is None or (elem.mask is not None and np.sum(elem.mask > 0) == 0):
                                if elem.element_id in region_masks:
                                    elem.mask = region_masks[elem.element_id]
                                    repaired_count += 1
        
        if repaired_count > 0:
            print(f"Repaired {repaired_count} empty mark_text masks from text regions")
        
        # Add regions that aren't already in category
        regions_to_add = []
        for region in all_text_regions:
            region_id = region.get('id', '')
            if region_id and region_id not in existing_element_ids:
                mask = region.get('mask')
                if mask is not None:
                    regions_to_add.append(region)
                    existing_element_ids.add(region_id)
        
        if regions_to_add:
            self._add_text_regions_to_category(page, regions_to_add)
    
    def _add_existing_line_regions_to_category(self, page: PageTab):
        """Add existing line regions from workspace to mark_line category.
        Also repairs masks for objects loaded from old workspace format."""
        # Collect all line regions (manual only, no auto detection for lines)
        all_line_regions = []
        if hasattr(page, 'manual_line_regions'):
            all_line_regions.extend(page.manual_line_regions)
        
        # Even if no line regions, we should still try to repair masks from element points/mode
        if not all_line_regions:
            print(f"DEBUG _add_existing_line_regions: No line regions found for page {page.tab_id}, will try to reconstruct masks from element points/mode")
        
        print(f"DEBUG _add_existing_line_regions: Found {len(all_line_regions)} line regions for page {page.tab_id}")
        
        # Ensure mark_line category exists
        mark_line_cat = self.categories.get("mark_line")
        if not mark_line_cat:
            mark_line_cat = DynamicCategory(
                name="mark_line", prefix="mark_line", full_name="Mark as Leader Line",
                color_rgb=(0, 255, 255), selection_mode="flood", visible=True
            )
            self.categories["mark_line"] = mark_line_cat
            self._refresh_categories()
        
        # Build a map of region_id -> mask from manual regions
        region_masks = {}
        for region in all_line_regions:
            region_id = region.get('id', '')
            mask = region.get('mask')
            if region_id and mask is not None:
                region_masks[region_id] = mask
        
        # Repair masks for existing mark_line objects that have empty masks
        existing_element_ids = set()
        repaired_count = 0
        print(f"DEBUG _add_existing_line_regions: Checking {len(self.all_objects)} objects for mark_line category")
        
        # First, find all mark_line objects on this page and check their masks
        mark_line_objects = []
        for obj in self.all_objects:
            if obj.category == "mark_line":
                for inst in obj.instances:
                    if inst.page_id == page.tab_id:
                        for elem in inst.elements:
                            existing_element_ids.add(elem.element_id)
                            mask_status = "None" if elem.mask is None else f"{np.sum(elem.mask > 0)} pixels"
                            print(f"DEBUG: mark_line object {obj.object_id}, element {elem.element_id}: mask={mask_status}")
                            if elem.mask is None or (elem.mask is not None and np.sum(elem.mask > 0) == 0):
                                mark_line_objects.append((obj, inst, elem))
        
        print(f"DEBUG: Found {len(mark_line_objects)} mark_line objects with empty/None masks, {len(region_masks)} region masks available")
        
        # First, try to reconstruct masks from element points/mode if no regions available
        if mark_line_objects and not region_masks:
            print(f"DEBUG: No region masks available, attempting to reconstruct masks from element points/mode")
            h, w = page.original_image.shape[:2]
            for obj, inst, elem in mark_line_objects:
                if elem.points and len(elem.points) >= 2 and elem.mode in ["line", "polyline", "freeform"]:
                    # Reconstruct mask from points
                    try:
                        if elem.mode == "line" and len(elem.points) >= 2:
                            mask = self.engine.create_line_mask((h, w), elem.points)
                        elif elem.mode in ["polyline", "freeform"] and len(elem.points) >= 2:
                            mask = self.engine.create_polygon_mask((h, w), elem.points, closed=False)
                        else:
                            mask = None
                        
                        if mask is not None and np.any(mask > 0):
                            elem.mask = mask
                            repaired_count += 1
                            print(f"DEBUG: Reconstructed mask for element {elem.element_id} from {len(elem.points)} points (mode={elem.mode}, {np.sum(mask > 0)} pixels)")
                        else:
                            print(f"DEBUG: Could not reconstruct mask for element {elem.element_id} (mode={elem.mode}, {len(elem.points)} points)")
                    except Exception as e:
                        print(f"DEBUG: Error reconstructing mask for element {elem.element_id}: {e}")
        
        # Match region masks to elements
        if mark_line_objects and region_masks:
            h, w = page.original_image.shape[:2]
            
            # Find which region masks are already used by elements with valid masks
            used_region_ids = set()
            for obj in self.all_objects:
                if obj.category == "mark_line":
                    for inst in obj.instances:
                        if inst.page_id == page.tab_id:
                            for elem in inst.elements:
                                if elem.mask is not None and np.any(elem.mask > 0):
                                    # Check which region this mask matches (80% overlap)
                                    for rid, rmask in region_masks.items():
                                        if rid not in used_region_ids and rmask.shape == (h, w):
                                            overlap = np.sum((elem.mask > 0) & (rmask > 0))
                                            total = np.sum(rmask > 0)
                                            if total > 0 and overlap / total > 0.8:
                                                print(f"DEBUG: Region {rid} already used by element {elem.element_id} ({overlap}/{total} overlap)")
                                                used_region_ids.add(rid)
                                                break
            
            print(f"DEBUG: {len(used_region_ids)} region masks already in use, {len(region_masks) - len(used_region_ids)} available for repair")
            
            # Match elements to regions - try to match by checking if any region mask
            # overlaps with the object's expected location or use first available
            # Since we can't reliably match by ID, we'll assign regions in order
            available_regions = [(rid, rmask) for rid, rmask in region_masks.items() 
                               if rid not in used_region_ids and rmask.shape == (h, w)]
            
            print(f"DEBUG: {len(available_regions)} region masks available for {len(mark_line_objects)} objects needing repair")
            
            for idx, (obj, inst, elem) in enumerate(mark_line_objects):
                if idx < len(available_regions):
                    region_id, region_mask = available_regions[idx]
                    elem.mask = region_mask.copy()
                    repaired_count += 1
                    used_region_ids.add(region_id)
                    print(f"DEBUG: Repaired element {elem.element_id} (obj {obj.object_id}) with region {region_id} ({np.sum(region_mask > 0)} pixels)")
                else:
                    print(f"DEBUG: WARNING: Could not repair element {elem.element_id} (obj {obj.object_id}) - no available region masks ({idx+1}/{len(mark_line_objects)})")
        
        if repaired_count > 0:
            print(f"DEBUG: Repaired {repaired_count} empty mark_line masks (from regions or reconstructed from points)")
        
        # Check for unrecoverable objects (mode="rect" with no mask data)
        unrecoverable_objects = []
        for obj, inst, elem in mark_line_objects:
            if elem.mask is None or np.sum(elem.mask > 0) == 0:
                unrecoverable_objects.append((obj, inst, elem))
        
        if unrecoverable_objects:
            print(f"DEBUG: WARNING: {len(unrecoverable_objects)} mark_line objects could not be repaired:")
            for obj, inst, elem in unrecoverable_objects:
                has_points = elem.points and len(elem.points) >= 2
                print(f"DEBUG:   - Element {elem.element_id} (obj {obj.object_id}, name='{obj.name}'): mode={elem.mode}, points={len(elem.points)}, UNRECOVERABLE")
                # For mode="rect" with no mask, the object is from old workspace format and can't be recovered
                if elem.mode == "rect" and not has_points:
                    print(f"DEBUG:     -> This object was created with rectangle selection but saved without mask data.")
                    print(f"DEBUG:     -> Please delete '{obj.name}' and recreate it using rectangle selection.")
        
        # Add regions that aren't already in category
        regions_to_add = []
        for region in all_line_regions:
            region_id = region.get('id', '')
            # Check if we already have an object for this region
            # We'll match by checking if any element has a similar ID or if we need to create new
            mask = region.get('mask')
            if mask is not None and np.any(mask > 0):
                # Check if this region is already represented in objects
                region_already_added = False
                for obj in self.all_objects:
                    if obj.category == "mark_line":
                        for inst in obj.instances:
                            if inst.page_id == page.tab_id:
                                for elem in inst.elements:
                                    if elem.mask is not None and np.any(elem.mask > 0):
                                        # Check if masks overlap significantly
                                        overlap = np.sum((elem.mask > 0) & (mask > 0))
                                        total = np.sum(mask > 0)
                                        if total > 0 and overlap / total > 0.8:  # 80% overlap
                                            region_already_added = True
                                            break
                                if region_already_added:
                                    break
                        if region_already_added:
                            break
                
                if not region_already_added:
                    regions_to_add.append(region)
        
        # Create objects for regions that need to be added
        for region in regions_to_add:
            region_id = region.get('id', '')
            mask = region.get('mask')
            points = region.get('points', [])
            mode = region.get('mode', 'flood')
            
            if mask is not None and np.any(mask > 0):
                # Generate element ID
                element_id = f"mark_line_{uuid.uuid4().hex[:8]}"
                
                # Create element with the mask
                elem = SegmentElement(
                    element_id=element_id,
                    category="mark_line",
                    mode=mode,
                    points=points.copy() if points else [],
                    mask=mask.copy(),
                    color=mark_line_cat.color_rgb,
                    label_position="center"
                )
                
                # Create instance
                inst = ObjectInstance(
                    instance_id=f"{element_id}_inst_1",
                    instance_num=1,
                    elements=[elem],
                    page_id=page.tab_id,
                    view_type="",
                    attributes=ObjectAttributes()
                )
                
                # Create object
                obj = SegmentedObject(
                    object_id=f"mark_line_{uuid.uuid4().hex[:8]}",
                    name=f"Leader Line {region_id}",
                    category="mark_line",
                    instances=[inst]
                )
                
                self.all_objects.append(obj)
        
        if regions_to_add:
            self.workspace_modified = True
            self._update_tree()
            print(f"Added {len(regions_to_add)} mark_line objects from existing regions")
    
    def _toggle_hide_hatching(self):
        """Toggle hide hatching for current page."""
        page = self._get_current_page()
        if not page:
            return
        
        if not hasattr(page, 'hide_hatching'):
            page.hide_hatching = False
        
        # If turning on, detect hatching regions first
        if not page.hide_hatching:
            if not hasattr(page, 'auto_hatch_regions') or not page.auto_hatch_regions:
                self.status_var.set("Detecting hatching regions...")
                self.root.update()
                page.auto_hatch_regions = self._detect_hatching_regions(page)
                self._update_combined_hatch_mask(page)
                count = len(page.auto_hatch_regions)
                self.status_var.set(f"Found {count} hatching regions - use 'Manage Manual Regions' to review")
        
        page.hide_hatching = not page.hide_hatching
        
        self._update_view_menu_labels()
        self.renderer.invalidate_cache()
        self._update_display()
    
    def _update_view_menu_labels(self):
        """Update View menu labels based on current page state."""
        page = self._get_current_page()
        
        # Menu indices with new structure:
        # 0: Toggle Tools Panel
        # 1: Toggle Objects Panel
        # 2: separator
        # 3: Hide/Show Background
        # 4: Run OCR (no longer toggles, always runs OCR)
        # 5: Hide/Show Hatching
        # 6: separator
        # 7: Manage Mask Regions...
        # 8: separator
        # 9: Hide/Show Ruler
        
        # Background toggle (index 3)
        if page and getattr(page, 'hide_background', False):
            self.view_menu.entryconfig(3, label="Show Background")
        else:
            self.view_menu.entryconfig(3, label="Hide Background")
        
        # Hatching toggle (index 5)
        if page and getattr(page, 'hide_hatching', False):
            self.view_menu.entryconfig(5, label="Show Hatching")
        else:
            self.view_menu.entryconfig(5, label="Hide Hatching")
        
        # Ruler toggle (index 10, not 9 - index 9 is a separator)
        if self.settings.show_ruler:
            self.view_menu.entryconfig(10, label="Hide Ruler")
        else:
            self.view_menu.entryconfig(10, label="Show Ruler")
    
    def _show_settings_dialog(self):
        """Show the settings/preferences dialog."""
        old_theme = self.settings.theme
        
        def on_save(settings):
            # Apply settings
            self.settings = settings
            save_settings(settings)
            
            # Update engine settings
            self.engine.tolerance = settings.tolerance
            self.engine.line_thickness = settings.line_thickness
            
            # Update UI - sync show_labels with sidebar checkbox
            self.show_labels = settings.show_labels
            self.show_labels_var.set(settings.show_labels)
            
            if hasattr(self, 'opacity_var'):
                self.opacity_var.set(settings.planform_opacity)
            
            # Redraw
            self.renderer.invalidate_cache()
            self._update_display()
            self._draw_rulers()
            
            # Show restart message if theme changed
            if settings.theme != old_theme:
                messagebox.showinfo("Restart Required", 
                    "Theme changes will fully apply after restarting the application.")
        
        dialog = SettingsDialog(self.root, self.settings, self.theme, on_save)
        dialog.show()
    
    def _show_nesting_dialog(self):
        """Show the nesting configuration dialog."""
        if not check_rectpack_available():
            messagebox.showerror(
                "Missing Library",
                "The rectpack library is required for nesting.\n\n"
                "Install it with: pip install rectpack"
            )
            return
        
        if not self.all_objects:
            messagebox.showwarning("No Objects", "No objects to nest. Create some objects first.")
            return
        
        page = self._get_current_page()
        if not page:
            messagebox.showwarning("No Page", "No page selected.")
            return
        
        # Show configuration dialog
        dialog = NestingConfigDialog(
            self.root, 
            self.all_objects, 
            self.pages, 
            self.categories,
            page.tab_id,
            self.theme
        )
        self.root.wait_window(dialog)
        
        if not dialog.result:
            return
        
        # Run nesting
        self.status_var.set("Nesting parts...")
        self.root.update()
        
        try:
            config = dialog.result
            
            # Create nesting engine
            spacing_pixels = int(config["spacing"] * config["dpi"])
            engine = NestingEngine(
                spacing=spacing_pixels,
                allow_rotation=config["allow_rotation"]
            )
            
            # Run nesting
            results = engine.nest_by_material(
                config["material_groups"],
                config["sheet_configs"],
                self.pages,
                dpi=config["dpi"],
                respect_quantity=config["respect_quantity"]
            )
            
            if not results:
                messagebox.showinfo("No Results", "No parts could be nested. Check that objects have valid masks.")
                self.status_var.set("Nesting completed - no results")
                return
            
            # Show results dialog
            results_dialog = NestingResultsDialog(self.root, results, self.theme)
            self.root.wait_window(results_dialog)
            
            # Check if user wants to create pages from results
            if hasattr(results_dialog, 'result') and results_dialog.result == "create_pages":
                self._create_pages_from_nesting(results)
            
            self.status_var.set("Nesting completed")
            
        except Exception as e:
            messagebox.showerror("Nesting Error", f"An error occurred during nesting:\n{str(e)}")
            self.status_var.set("Nesting failed")
            import traceback
            traceback.print_exc()
    
    def _create_pages_from_nesting(self, results: Dict):
        """Create new pages from nesting results."""
        count = 0
        for material_key, sheets in results.items():
            for sheet in sheets:
                # Render the sheet
                rendered = sheet.render(include_masks=True)
                
                # Convert BGRA to BGR for page
                bgr = cv2.cvtColor(rendered, cv2.COLOR_BGRA2BGR)
                
                # Create new page
                page = PageTab(
                    tab_id=str(uuid.uuid4())[:8],
                    model_name=self.model_name or "Nested",
                    page_name=sheet.sheet_name,
                    original_image=bgr,
                    active=True
                )
                
                self.pages[page.tab_id] = page
                self._add_page(page)
                count += 1
        
        if count > 0:
            messagebox.showinfo("Pages Created", f"Created {count} new pages from nesting results.")
            self.workspace_modified = True
    
    def _scan_for_labels(self):
        """Scan pages for component labels using OCR."""
        page = self._get_current_page()
        if not page:
            messagebox.showwarning("No Page", "No page selected.")
            return
        
        dialog = LabelScanDialog(self.root, [page.original_image], self.theme)
        self.root.wait_window(dialog)
        
        if dialog.result:
            # Create categories/objects from found labels
            self.status_var.set(f"Found labels: {dialog.result}")
    
    def _detect_text_regions(self, page: PageTab) -> list:
        """Detect text regions in image using OCR and return list of regions."""
        import pytesseract
        
        image = page.original_image
        h, w = image.shape[:2]
        regions = []
        
        try:
            # Configure tesseract path if needed
            pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
            
            # Get bounding boxes for detected text - use word level only
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # Use PSM 3 (fully automatic page segmentation - default) to find all text elements
            custom_config = r'--oem 3 --psm 3'

            data = pytesseract.image_to_data(gray, output_type=pytesseract.Output.DICT, config=custom_config)

            region_id = 1
            n_boxes = len(data['level'])
            for i in range(n_boxes):
                # Only consider actual text (level 5 = word)
                if data['level'][i] != 5:
                    continue
                    
                # Only consider words with high confidence
                conf = int(data['conf'][i]) if data['conf'][i] != '-1' else 0
                if conf < 30:  # Higher confidence threshold
                    continue
                
                # Only consider boxes with reasonable dimensions (not the whole image)
                x, y, bw, bh = data['left'][i], data['top'][i], data['width'][i], data['height'][i]
                
                # Skip if box is too large (> 10% of image) - likely false positive
                if bw * bh > (w * h * 0.1):
                    continue
                
                # Skip very small boxes (noise)
                if bw < 5 or bh < 5:
                    continue
                
                # Add small padding around text
                padding = 2
                x1 = max(0, x - padding)
                y1 = max(0, y - padding)
                x2 = min(w, x + bw + padding)
                y2 = min(h, y + bh + padding)
                
                # Create mask for this region
                mask = np.zeros((h, w), dtype=np.uint8)
                mask[y1:y2, x1:x2] = 255
                
                # Get detected text
                text = data['text'][i] if data['text'][i].strip() else f"text_{region_id}"
                
                regions.append({
                    'id': f"auto_{region_id}",
                    'text': text,
                    'bbox': (x1, y1, x2, y2),
                    'confidence': conf,
                    'mode': 'auto',
                    'mask': mask
                })
                region_id += 1
           
        except Exception as e:
            print(f"Text detection error: {e}")
        
        return regions
    
    def _detect_hatching_regions(self, page: PageTab) -> list:
        """Detect hatching/cross-hatch pattern regions in image and return list of regions."""
        image = page.original_image
        h, w = image.shape[:2]
        regions = []
        
        try:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # Use edge detection to find line patterns
            edges = cv2.Canny(gray, 50, 150)
            
            # Use Hough transform to detect lines
            lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=30, 
                                    minLineLength=20, maxLineGap=5)
            
            if lines is not None:
                # Find regions with high line density (hatching)
                line_density = np.zeros((h, w), dtype=np.float32)
                
                for line in lines:
                    x1, y1, x2, y2 = line[0]
                    # Calculate line length and angle
                    length = np.sqrt((x2-x1)**2 + (y2-y1)**2)
                    angle = np.arctan2(y2-y1, x2-x1)
                    
                    # Hatching typically has diagonal lines at ~45° or ~135°
                    angle_deg = np.abs(np.degrees(angle))
                    is_diagonal = (35 < angle_deg < 55) or (125 < angle_deg < 145)
                    
                    if is_diagonal and length < 100:  # Short diagonal lines = hatching
                        cv2.line(line_density, (x1, y1), (x2, y2), 1.0, 3)
                
                # Apply morphological operations to group nearby lines
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
                line_density = cv2.dilate(line_density, kernel)
                
                # Threshold to get hatching regions
                _, hatching = cv2.threshold(line_density, 0.3, 255, cv2.THRESH_BINARY)
                mask = hatching.astype(np.uint8)
                
                # Clean up with morphological closing
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (10, 10))
                mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
                
                # Find connected components to create individual regions
                num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(mask)
                
                for i in range(1, num_labels):  # Skip background (0)
                    x, y, bw, bh, area = stats[i]
                    
                    # Skip very small regions
                    if area < 100:
                        continue
                    
                    # Create mask for this region
                    region_mask = np.zeros((h, w), dtype=np.uint8)
                    region_mask[labels == i] = 255
                    
                    cx, cy = centroids[i]
                    
                    regions.append({
                        'id': f"auto_{i}",
                        'bbox': (x, y, x + bw, y + bh),
                        'area': area,
                        'center': (int(cx), int(cy)),
                        'mode': 'auto',
                        'mask': region_mask
                    })
            
        except Exception as e:
            print(f"Hatching detection error: {e}")
        
        return regions
    
    # Manual text/hatching region management
    def _add_manual_text_region(self, page: PageTab, mask: np.ndarray, point: tuple, mode: str = "flood"):
        """Add a manually marked text region."""
        if not hasattr(page, 'manual_text_regions'):
            page.manual_text_regions = []
        
        # Store the region with its seed point and mode for reference
        region_id = len(page.manual_text_regions) + 1
        page.manual_text_regions.append({
            'id': region_id,
            'point': point,
            'mode': mode,
            'mask': mask.copy()
        })
        
        # Incrementally update combined text mask (much faster than full recompute)
        old_mask = getattr(page, 'combined_text_mask', None)
        if hasattr(page, 'combined_text_mask') and page.combined_text_mask is not None:
            # Just add this mask to the existing combined mask
            page.combined_text_mask = np.maximum(page.combined_text_mask, mask)
        else:
            # First mask - just use it directly
            page.combined_text_mask = mask.copy()
        
        # Update working image cache incrementally
        self._update_working_image_cache_for_mask_with_old(page, 'text', page.combined_text_mask, old_mask)
        
        self.workspace_modified = True
        self.renderer.invalidate_cache()
        # Use debounced update for better performance
        self._update_display()
        self.status_var.set(f"Added manual text region #{region_id} ({mode})")
    
    def _add_manual_hatch_region(self, page: PageTab, mask: np.ndarray, point: tuple, mode: str = "flood"):
        """Add a manually marked hatching region."""
        if not hasattr(page, 'manual_hatch_regions'):
            page.manual_hatch_regions = []
        
        region_id = len(page.manual_hatch_regions) + 1
        page.manual_hatch_regions.append({
            'id': region_id,
            'point': point,
            'mode': mode,
            'mask': mask.copy()
        })
        
        # Incrementally update combined hatching mask (much faster than full recompute)
        old_mask = getattr(page, 'combined_hatch_mask', None)
        if hasattr(page, 'combined_hatch_mask') and page.combined_hatch_mask is not None:
            # Just add this mask to the existing combined mask
            page.combined_hatch_mask = np.maximum(page.combined_hatch_mask, mask)
        else:
            # First mask - just use it directly
            page.combined_hatch_mask = mask.copy()
        
        # Update working image cache incrementally
        self._update_working_image_cache_for_mask_with_old(page, 'hatch', page.combined_hatch_mask, old_mask)
        
        self.workspace_modified = True
        self.renderer.invalidate_cache()
        # Use debounced update for better performance
        self._update_display()
        self.status_var.set(f"Added manual hatching region #{region_id} ({mode})")
    
    def _detect_leader_line(self, page: PageTab, mask: np.ndarray, points: list) -> Optional[dict]:
        """
        Detect if a selected line is a leader line by checking:
        1. Proximity to text regions
        2. Arrow detection at endpoints
        3. Line characteristics (thin, straight-ish)
        
        Returns dict with leader info or None if not a leader.
        """
        h, w = page.original_image.shape[:2]
        
        # Get mask pixels (for arrow detection only)
        mask_pixels = np.where(mask > 0)
        if len(mask_pixels[0]) == 0:
            return None
        
        # Use points list first (much faster than scanning all pixels)
        endpoints = []
        if len(points) >= 2:
            # Use first and last points as endpoints (most common case)
            endpoints = [points[0], points[-1]]
        else:
            # Fallback: find endpoints by scanning mask (expensive, but rare)
            for y, x in zip(mask_pixels[0], mask_pixels[1]):
                # Count neighbors
                neighbors = 0
                for dy in [-1, 0, 1]:
                    for dx in [-1, 0, 1]:
                        if dy == 0 and dx == 0:
                            continue
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] > 0:
                            neighbors += 1
                if neighbors <= 1:  # Endpoint
                    endpoints.append((x, y))
                    if len(endpoints) >= 2:
                        break
        
        if len(endpoints) < 2:
            return None
        
        # Check proximity to text regions
        text_endpoint = None
        arrow_endpoint = None
        min_text_dist = float('inf')
        
        # Get all text regions
        all_text_regions = []
        if hasattr(page, 'auto_text_regions'):
            all_text_regions.extend(page.auto_text_regions)
        if hasattr(page, 'manual_text_regions'):
            all_text_regions.extend(page.manual_text_regions)
        
        # Early exit if no text regions
        if not all_text_regions:
            return None
        
        for endpoint in endpoints:
            ex, ey = endpoint
            # Find nearest text region
            for region in all_text_regions:
                region_mask = region.get('mask')
                if region_mask is None:
                    continue
                
                # Find closest point in text region
                text_pixels = np.where(region_mask > 0)
                if len(text_pixels[0]) > 0:
                    # Calculate distance to text region center
                    text_y = np.mean(text_pixels[0])
                    text_x = np.mean(text_pixels[1])
                    dist = np.sqrt((ex - text_x)**2 + (ey - text_y)**2)
                    
                    if dist < min_text_dist and dist < 100:  # Within 100 pixels
                        min_text_dist = dist
                        text_endpoint = endpoint
                        # Other endpoint is likely the arrow end
                        arrow_endpoint = endpoints[1] if endpoint == endpoints[0] else endpoints[0]
        
        if text_endpoint is None:
            return None  # Not near any text, probably not a leader
        
        # Simple arrow detection: check for small triangular patterns at arrow endpoint
        # This is a simplified check - could be enhanced with better arrow detection
        has_arrow = False
        if arrow_endpoint:
            ax, ay = arrow_endpoint
            # Check for small filled triangle pattern (arrowhead)
            # Look for small triangular region near endpoint
            arrow_region_size = 10
            x1 = max(0, ax - arrow_region_size)
            x2 = min(w, ax + arrow_region_size)
            y1 = max(0, ay - arrow_region_size)
            y2 = min(h, ay + arrow_region_size)
            
            # Check if there's a small filled region (arrowhead)
            region_mask = mask[y1:y2, x1:x2]
            if np.sum(region_mask > 0) > 20:  # Has some pixels in arrow region
                has_arrow = True
        
        return {
            'is_leader': True,
            'text_endpoint': text_endpoint,
            'arrow_endpoint': arrow_endpoint,
            'has_arrow': has_arrow,
            'text_distance': min_text_dist
        }
    
    def _trace_line_with_findline(self, page: PageTab, user_points: List[tuple]) -> Optional[np.ndarray]:
        """
        Use findline functionality to trace a line from user points.
        Returns a mask of the traced line, or None if tracing fails.
        """
        if not FINDLINE_AVAILABLE:
            # Fallback to simple line mask if findline not available
            h, w = page.original_image.shape[:2]
            return self.engine.create_line_mask((h, w), user_points)
        
        try:
            # Get working image (respects category visibility)
            working_img = self._get_working_image(page)
            if working_img is None:
                return None
            
            h, w = working_img.shape[:2]
            
            # Step 1: Convert to monochrome
            binary = convert_to_monochrome(working_img)
            
            # Step 2: Skeletonize
            skeleton = skeletonize_image(binary)
            
            # Step 3: Find nearest skeleton points for user points
            skeleton_points = []
            for x, y in user_points:
                nearest = find_nearest_skeleton_point(skeleton, x, y, search_radius=50)
                if nearest:
                    skeleton_points.append(nearest)
                else:
                    skeleton_points.append((x, y))  # Use original point as fallback
            
            # Step 4: Trace line between points
            all_traced_points = []
            for i in range(len(skeleton_points) - 1):
                start_x, start_y = skeleton_points[i]
                end_x, end_y = skeleton_points[i + 1]
                segment_path = trace_between_points(skeleton, start_x, start_y, end_x, end_y)
                if segment_path:
                    all_traced_points.extend(segment_path)
            
            if not all_traced_points or len(all_traced_points) < 5:
                # Fallback to simple line mask if tracing fails
                return self.engine.create_line_mask((h, w), user_points)
            
            # Step 5: Measure line thickness
            thickness = measure_line_thickness(working_img, all_traced_points)
            
            # Step 6: Select line pixels with collision detection
            collision_threshold = 200  # Background threshold
            line_mask = select_line_pixels(
                working_img, 
                all_traced_points, 
                thickness, 
                skeleton, 
                user_points,
                collision_threshold
            )
            
            # Step 7: Expand mask to include all non-white pixels at edges
            # This finds actual line edges without affecting thickness calculations
            line_mask = self._expand_mask_to_edges(working_img, line_mask, collision_threshold)
            
            return line_mask
            
        except Exception as e:
            print(f"Error in findline tracing: {e}")
            import traceback
            traceback.print_exc()
            # Fallback to simple line mask on error
            h, w = page.original_image.shape[:2]
            return self.engine.create_line_mask((h, w), user_points)
    
    def _expand_mask_to_edges(self, image: np.ndarray, mask: np.ndarray, threshold: int = 200) -> np.ndarray:
        """
        Expand mask to include all non-white (dark) pixels around the edges.
        This ensures full line coverage without affecting thickness calculations.
        
        Args:
            image: Original grayscale or BGR image
            mask: Binary mask to expand
            threshold: Pixel value threshold (pixels below this are considered dark/line)
        
        Returns:
            Expanded mask
        """
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
        
        h, w = mask.shape
        expanded_mask = mask.copy()
        
        # Find edge pixels of the current mask
        # Use morphological gradient to find edges
        kernel = np.ones((3, 3), np.uint8)
        mask_edges = cv2.morphologyEx(mask, cv2.MORPH_GRADIENT, kernel)
        
        # For each edge pixel, check neighbors in the original image
        # If neighbor is dark (below threshold), add it to the mask
        edge_pixels = np.where(mask_edges > 0)
        
        for y, x in zip(edge_pixels[0], edge_pixels[1]):
            # Check 8-connected neighbors
            for dy in [-1, 0, 1]:
                for dx in [-1, 0, 1]:
                    if dx == 0 and dy == 0:
                        continue
                    
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w:
                        # If neighbor is not already in mask and is dark (part of line)
                        if expanded_mask[ny, nx] == 0 and gray[ny, nx] < threshold:
                            expanded_mask[ny, nx] = 255
        
        # Iterate a few times to catch multi-pixel edges
        # But limit iterations to avoid expanding too far
        for iteration in range(2):  # 2 iterations should be enough
            new_edges = cv2.morphologyEx(expanded_mask, cv2.MORPH_GRADIENT, kernel)
            edge_pixels = np.where(new_edges > 0)
            
            added_any = False
            for y, x in zip(edge_pixels[0], edge_pixels[1]):
                for dy in [-1, 0, 1]:
                    for dx in [-1, 0, 1]:
                        if dx == 0 and dy == 0:
                            continue
                        
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < h and 0 <= nx < w:
                            if expanded_mask[ny, nx] == 0 and gray[ny, nx] < threshold:
                                expanded_mask[ny, nx] = 255
                                added_any = True
            
            if not added_any:
                break  # No more pixels to add
        
        return expanded_mask
    
    def _add_manual_line_region(self, page: PageTab, mask: np.ndarray, points: list, mode: str = "flood"):
        """Add a manually marked leader line region."""
        if not hasattr(page, 'manual_line_regions'):
            page.manual_line_regions = []
        
        # Store the region first (defer expensive leader detection)
        region_id = len(page.manual_line_regions) + 1
        region_data = {
            'id': region_id,
            'points': points.copy() if points else [],
            'mode': mode,
            'mask': mask.copy(),
            'is_leader': False,  # Will be updated asynchronously
        }
        
        page.manual_line_regions.append(region_data)
        
        # Also create a SegmentedObject with SegmentElement (like mark_text does)
        # This allows the object to be selected and highlighted
        cat = self.categories.get("mark_line")
        if not cat:
            return
        
        # Generate element ID
        element_id = f"mark_line_{uuid.uuid4().hex[:8]}"
        
        # Create element with the mask
        elem = SegmentElement(
            element_id=element_id,
            category="mark_line",
            mode=mode,
            points=points.copy() if points else [],
            mask=mask.copy(),  # Ensure we have a copy of the mask
            color=cat.color_rgb,
            label_position=self.label_position
        )
        
        # Create instance
        inst = ObjectInstance(
            instance_id=f"{element_id}_inst_1",
            instance_num=1,
            elements=[elem],
            page_id=page.tab_id,
            view_type="",
            attributes=ObjectAttributes()
        )
        
        # Count existing mark_line objects to determine next number
        mark_line_objects = [o for o in self.all_objects if o.category == "mark_line"]
        next_number = len(mark_line_objects) + 1
        
        # Create object with temporary name (will be updated after leader detection)
        obj = SegmentedObject(
            object_id=f"mark_line_{uuid.uuid4().hex[:8]}",
            name=f"ml-{next_number}",  # Default to ml- (will change to ll- if leader detected)
            category="mark_line",
            instances=[inst]
        )
        
        # Add to all_objects
        self.all_objects.append(obj)
        self.workspace_modified = True
        
        # Update tree preserving expansion state and selecting the new object
        # (Don't trigger display update here - defer until after mask update)
        self._update_tree(preserve_state=True, select_object_id=obj.object_id)
        
        # Update combined line mask incrementally (much faster than force_recompute)
        # Just add this new mask to the existing combined mask
        old_mask = getattr(page, 'combined_line_mask', None)
        if hasattr(page, 'combined_line_mask') and page.combined_line_mask is not None:
            # Incrementally add this mask
            page.combined_line_mask = np.maximum(page.combined_line_mask, mask)
        else:
            # First mask - just use it directly
            page.combined_line_mask = mask.copy()
        
        # Update working image cache incrementally (handles addition)
        self._update_working_image_cache_for_mask_with_old(page, 'line', page.combined_line_mask, old_mask)
        
        # Defer display update - don't render immediately (like rect mode)
        # Display will be updated when user finishes the operation
        
        # Count existing mark_line objects to determine next number
        mark_line_objects = [o for o in self.all_objects if o.category == "mark_line"]
        next_number = len(mark_line_objects)  # Will be updated after leader detection
        
        # Defer leader detection to after UI update (non-blocking)
        def detect_leader_async():
            leader_info = self._detect_leader_line(page, mask, points)
            is_leader = leader_info is not None
            
            # Update region data
            if leader_info:
                region_data.update(leader_info)
                region_data['is_leader'] = True
            
            # Count existing objects again (in case multiple were added quickly)
            mark_line_objects = [o for o in self.all_objects if o.category == "mark_line"]
            next_number = len(mark_line_objects)
            
            # Update object name based on leader detection
            if is_leader:
                obj.name = f"ll-{next_number}"
                self.status_var.set(f"Added leader line ll-{next_number} (text at {leader_info['text_endpoint']}, arrow: {leader_info['has_arrow']})")
            else:
                obj.name = f"ml-{next_number}"
                self.status_var.set(f"Added line region ml-{next_number} (not detected as leader)")
            
            # Update tree to reflect new name (preserve state, select this object)
            self._update_tree(preserve_state=True, select_object_id=obj.object_id)
        
        # Schedule leader detection after UI update
        self.root.after(100, detect_leader_async)
        
        # Use debounced update for better performance (matches text/hatch)
        self._update_display()
        self.status_var.set(f"Added line region #{region_id} ({mode})")
    
    def _update_combined_text_mask(self, page: PageTab, force_recompute: bool = False):
        """
        Combine auto-detected and manual text masks with caching.
        
        Args:
            page: Page to update
            force_recompute: If True, recompute even if cached
        """
        # Check if we have a cached version and regions haven't changed
        cache_key = f"text_mask_{page.tab_id}"
        if not force_recompute and hasattr(page, '_text_mask_cache_key'):
            # Check if regions have changed
            auto_count = len(getattr(page, 'auto_text_regions', []))
            manual_count = len(getattr(page, 'manual_text_regions', []))
            current_key = f"{auto_count}_{manual_count}"
            if page._text_mask_cache_key == current_key and hasattr(page, 'combined_text_mask'):
                # Cache is valid, skip recomputation
                return
        
        h, w = page.original_image.shape[:2]
        combined = np.zeros((h, w), dtype=np.uint8)
        
        auto_count = 0
        manual_count = 0
        auto_pixels = 0
        manual_pixels = 0
        
        # Collect all masks first, then combine in one operation (faster than loop with np.maximum)
        all_masks = []
        
        # Add auto-detected regions
        if hasattr(page, 'auto_text_regions'):
            for region in page.auto_text_regions:
                mask = region.get('mask')
                if mask is not None:
                    if mask.shape == (h, w):
                        all_masks.append(mask)
                        auto_count += 1
                        auto_pixels += np.sum(mask > 0)
                    else:
                        print(f"Text mask shape mismatch: {mask.shape} vs expected {(h, w)}")
        
        # Add manual regions
        if hasattr(page, 'manual_text_regions'):
            for region in page.manual_text_regions:
                mask = region.get('mask')
                if mask is not None:
                    if mask.shape == (h, w):
                        all_masks.append(mask)
                        manual_count += 1
                        manual_pixels += np.sum(mask > 0)
                    else:
                        print(f"Manual text mask shape mismatch: {mask.shape} vs expected {(h, w)}")
        
        # Combine all masks (use batch processing for large numbers to avoid memory issues)
        if all_masks:
            # For large numbers of masks, process in batches to avoid memory allocation errors
            # With 644 masks of size (555, 4500), stacking all at once would require ~15GB
            batch_size = 100  # Process 100 masks at a time
            for i in range(0, len(all_masks), batch_size):
                batch = all_masks[i:i+batch_size]
                # Use iterative np.maximum instead of np.stack to save memory
                # This avoids creating a large intermediate array
                for mask in batch:
                    combined = np.maximum(combined, mask)
            combined = combined.astype(np.uint8)
        
        total_pixels = np.sum(combined > 0)
        # Store cache key and combined mask
        page._text_mask_cache_key = f"{auto_count}_{manual_count}"
        page.combined_text_mask = combined
        
        print(f"_update_combined_text_mask: auto={auto_count} ({auto_pixels}px), "
              f"manual={manual_count} ({manual_pixels}px), combined={total_pixels}px")
        # Update working image cache incrementally (handles both addition and removal)
        page = self._get_current_page()
        if page and page.tab_id == self.current_page_id:
            # Get old mask BEFORE updating page (needed for restoration)
            old_mask = getattr(page, 'combined_text_mask', None)
            # Update the page's combined mask
            page.combined_text_mask = combined
            # Update cache (will handle restoration of removed pixels)
            self._update_working_image_cache_for_mask_with_old(page, 'text', combined, old_mask)
    
    def _update_combined_hatch_mask(self, page: PageTab, force_recompute: bool = False):
        """
        Combine auto-detected and manual hatching masks with caching.
        
        Args:
            page: Page to update
            force_recompute: If True, recompute even if cached
        """
        # Check if we have a cached version and regions haven't changed
        if not force_recompute and hasattr(page, '_hatch_mask_cache_key'):
            # Check if regions have changed
            auto_count = len(getattr(page, 'auto_hatch_regions', []))
            manual_count = len(getattr(page, 'manual_hatch_regions', []))
            current_key = f"{auto_count}_{manual_count}"
            if page._hatch_mask_cache_key == current_key and hasattr(page, 'combined_hatch_mask'):
                # Cache is valid, skip recomputation
                return
        
        h, w = page.original_image.shape[:2]
        combined = np.zeros((h, w), dtype=np.uint8)
        
        auto_count = 0
        manual_count = 0
        auto_pixels = 0
        manual_pixels = 0
        
        # Collect all masks first, then combine in one operation (faster than loop with np.maximum)
        all_masks = []
        
        # Add auto-detected regions
        if hasattr(page, 'auto_hatch_regions'):
            for region in page.auto_hatch_regions:
                mask = region.get('mask')
                if mask is not None:
                    if mask.shape == (h, w):
                        all_masks.append(mask)
                        auto_count += 1
                        auto_pixels += np.sum(mask > 0)
                    else:
                        print(f"Hatch mask shape mismatch: {mask.shape} vs expected {(h, w)}")
        
        # Add manual regions
        if hasattr(page, 'manual_hatch_regions'):
            for region in page.manual_hatch_regions:
                mask = region.get('mask')
                if mask is not None:
                    if mask.shape == (h, w):
                        all_masks.append(mask)
                        manual_count += 1
                        manual_pixels += np.sum(mask > 0)
                    else:
                        print(f"Manual hatch mask shape mismatch: {mask.shape} vs expected {(h, w)}")
        
        # Combine all masks (use batch processing for large numbers to avoid memory issues)
        if all_masks:
            # For large numbers of masks, process in batches to avoid memory allocation errors
            batch_size = 100  # Process 100 masks at a time
            for i in range(0, len(all_masks), batch_size):
                batch = all_masks[i:i+batch_size]
                # Use iterative np.maximum instead of np.stack to save memory
                # This avoids creating a large intermediate array
                for mask in batch:
                    combined = np.maximum(combined, mask)
            combined = combined.astype(np.uint8)
        
        total_pixels = np.sum(combined > 0)
        # Store cache key and combined mask
        page._hatch_mask_cache_key = f"{auto_count}_{manual_count}"
        page.combined_hatch_mask = combined
        
        print(f"_update_combined_hatch_mask: auto={auto_count} ({auto_pixels}px), "
              f"manual={manual_count} ({manual_pixels}px), combined={total_pixels}px")
        # Update working image cache incrementally (handles both addition and removal)
        page = self._get_current_page()
        if page and page.tab_id == self.current_page_id:
            # Get old mask BEFORE updating page (needed for restoration)
            old_mask = getattr(page, 'combined_hatch_mask', None)
            # Update the page's combined mask
            page.combined_hatch_mask = combined
            # Update cache (will handle restoration of removed pixels)
            self._update_working_image_cache_for_mask_with_old(page, 'hatch', combined, old_mask)
    
    def _update_combined_line_mask(self, page: PageTab, force_recompute: bool = False):
        """
        Combine all mark_line object masks into combined_line_mask.
        
        This includes masks from:
        - manual_line_regions (for backward compatibility)
        - All mark_line objects in all_objects (for objects created via rectangle/polyline)
        
        Args:
            page: Page to update
            force_recompute: If True, recompute even if cached
        """
        h, w = page.original_image.shape[:2]
        combined = np.zeros((h, w), dtype=np.uint8)
        
        region_count = 0
        object_count = 0
        region_pixels = 0
        object_pixels = 0
        
        # Collect all masks first, then combine in one operation (faster than loop with np.maximum)
        all_masks = []
        
        # Add masks from manual_line_regions (for backward compatibility)
        if hasattr(page, 'manual_line_regions'):
            for region in page.manual_line_regions:
                mask = region.get('mask')
                if mask is not None:
                    if mask.shape == (h, w):
                        all_masks.append(mask)
                        region_count += 1
                        region_pixels += np.sum(mask > 0)
                    else:
                        print(f"Line region mask shape mismatch: {mask.shape} vs expected {(h, w)}")
        
        # Add masks from all mark_line objects on this page
        for obj in self.all_objects:
            if obj.category == "mark_line":
                for inst in obj.instances:
                    if inst.page_id == page.tab_id:
                        for elem in inst.elements:
                            if elem.mask is not None:
                                if elem.mask.shape == (h, w):
                                    all_masks.append(elem.mask)
                                    object_count += 1
                                    object_pixels += np.sum(elem.mask > 0)
                                else:
                                    print(f"Mark_line object mask shape mismatch: {elem.mask.shape} vs expected {(h, w)}")
        
        # Combine all masks (use batch processing for large numbers to avoid memory issues)
        if all_masks:
            # For large numbers of masks, process in batches to avoid memory allocation errors
            batch_size = 50
            for i in range(0, len(all_masks), batch_size):
                batch = all_masks[i:i + batch_size]
                batch_combined = np.maximum.reduce(batch)
                combined = np.maximum(combined, batch_combined)
        else:
            # No masks - set to None to indicate no lines to hide
            combined = None
        
        page.combined_line_mask = combined
        
        total_pixels = region_pixels + object_pixels
        print(f"_update_combined_line_mask: regions={region_count} ({region_pixels}px), "
              f"objects={object_count} ({object_pixels}px), combined={total_pixels}px")
        # Update working image cache incrementally (handles both addition and removal)
        page = self._get_current_page()
        if page and page.tab_id == self.current_page_id:
            # Get old mask BEFORE updating page (needed for restoration)
            old_mask = getattr(page, 'combined_line_mask', None)
            # Update the page's combined mask
            page.combined_line_mask = combined
            # Update cache (will handle restoration of removed pixels)
            self._update_working_image_cache_for_mask_with_old(page, 'line', combined, old_mask)
    
    def _remove_manual_text_region(self, page: PageTab, region_id: str, update_display: bool = True):
        """Remove a manual text region by ID."""
        if hasattr(page, 'manual_text_regions'):
            page.manual_text_regions = [r for r in page.manual_text_regions if r['id'] != region_id]
            self.workspace_modified = True
            if update_display:
                self._update_combined_text_mask(page)
                self.renderer.invalidate_cache()
                self._update_display()
    
    def _remove_auto_text_region(self, page: PageTab, region_id: str, update_display: bool = True):
        """Remove an auto-detected text region by ID."""
        if hasattr(page, 'auto_text_regions'):
            page.auto_text_regions = [r for r in page.auto_text_regions if r['id'] != region_id]
            self.workspace_modified = True
            if update_display:
                self._update_combined_text_mask(page)
                self.renderer.invalidate_cache()
                self._update_display()
    
    def _remove_manual_hatch_region(self, page: PageTab, region_id: str, update_display: bool = True):
        """Remove a manual hatching region by ID."""
        if hasattr(page, 'manual_hatch_regions'):
            page.manual_hatch_regions = [r for r in page.manual_hatch_regions if r['id'] != region_id]
            self.workspace_modified = True
            if update_display:
                self._update_combined_hatch_mask(page)
                self.renderer.invalidate_cache()
                self._update_display()
    
    def _remove_auto_hatch_region(self, page: PageTab, region_id: str, update_display: bool = True):
        """Remove an auto-detected hatching region by ID."""
        if hasattr(page, 'auto_hatch_regions'):
            page.auto_hatch_regions = [r for r in page.auto_hatch_regions if r['id'] != region_id]
            self.workspace_modified = True
            if update_display:
                self._update_combined_hatch_mask(page)
                self.renderer.invalidate_cache()
                self._update_display()
    
    
    # Page management
    def _add_page(self, page: PageTab, from_workspace: bool = False):
        """Add a page to the notebook.
        
        Args:
            page: The page to add
            from_workspace: If True, don't auto-fit zoom (preserve loaded zoom level)
        """
        self.pages[page.tab_id] = page
        # Invalidate cache when new page is added (different page/image)
        self._invalidate_working_image_cache()
        
        # Create main frame with rulers
        frame = ttk.Frame(self.notebook)
        
        # Ruler dimensions
        ruler_size = 25
        
        # Create grid layout: [corner][h_ruler] / [v_ruler][canvas+scrolls]
        # Top row: corner + horizontal ruler
        top_frame = ttk.Frame(frame)
        top_frame.pack(side=tk.TOP, fill=tk.X)
        
        # Corner (empty space where rulers meet)
        corner = tk.Canvas(top_frame, width=ruler_size, height=ruler_size, 
                          bg=self.theme.get("bg_secondary", "#313244"),
                          highlightthickness=0)
        corner.pack(side=tk.LEFT)
        
        # Horizontal ruler
        h_ruler = tk.Canvas(top_frame, height=ruler_size, 
                           bg=self.theme.get("bg_secondary", "#313244"),
                           highlightthickness=0)
        h_ruler.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Bottom row: vertical ruler + canvas area
        bottom_frame = ttk.Frame(frame)
        bottom_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        # Vertical ruler
        v_ruler = tk.Canvas(bottom_frame, width=ruler_size,
                           bg=self.theme.get("bg_secondary", "#313244"),
                           highlightthickness=0)
        v_ruler.pack(side=tk.LEFT, fill=tk.Y)
        
        # Canvas area with scrollbars
        canvas_frame = ttk.Frame(bottom_frame)
        canvas_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        h_scroll = ttk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL)
        h_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        v_scroll = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        canvas = tk.Canvas(canvas_frame, bg=self.theme["canvas_bg"], cursor="crosshair",
                          xscrollcommand=h_scroll.set, yscrollcommand=v_scroll.set)
        canvas.pack(fill=tk.BOTH, expand=True)
        h_scroll.config(command=lambda *args: self._scroll_with_rulers(page, 'h', *args))
        v_scroll.config(command=lambda *args: self._scroll_with_rulers(page, 'v', *args))
        
        canvas.bind("<Button-1>", self._on_click)
        canvas.bind("<Double-Button-1>", self._on_double_click)
        canvas.bind("<Button-3>", self._on_right_click)
        canvas.bind("<B1-Motion>", self._on_drag)
        canvas.bind("<ButtonRelease-1>", self._on_release)
        canvas.bind("<Motion>", self._on_motion)
        
        # Mouse wheel scrolling for canvas
        def _canvas_mousewheel(event):
            # Vertical scroll with mouse wheel
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
            self._draw_rulers(page)
        
        def _canvas_mousewheel_horizontal(event):
            # Horizontal scroll with Shift+wheel or horizontal wheel
            canvas.xview_scroll(int(-1*(event.delta/120)), "units")
            self._draw_rulers(page)
        
        def _bind_canvas_scroll(event):
            canvas.bind_all("<MouseWheel>", _canvas_mousewheel)
            canvas.bind_all("<Shift-MouseWheel>", _canvas_mousewheel_horizontal)
            # For mice with horizontal scroll (tilt wheel)
            canvas.bind_all("<Shift-Button-4>", lambda e: canvas.xview_scroll(-1, "units"))
            canvas.bind_all("<Shift-Button-5>", lambda e: canvas.xview_scroll(1, "units"))
        
        def _unbind_canvas_scroll(event):
            canvas.unbind_all("<MouseWheel>")
            canvas.unbind_all("<Shift-MouseWheel>")
            canvas.unbind_all("<Shift-Button-4>")
            canvas.unbind_all("<Shift-Button-5>")
        
        canvas.bind("<Enter>", _bind_canvas_scroll)
        canvas.bind("<Leave>", _unbind_canvas_scroll)
        
        # Store references
        page.canvas = canvas
        page.frame = frame
        page.h_ruler = h_ruler
        page.v_ruler = v_ruler
        page.ruler_size = ruler_size
        
        self.notebook.add(frame, text=page.display_name)
        
        # Only select and render if this is a new page (not loading from workspace)
        # When loading from workspace, only the active page will be selected/rendered
        if not from_workspace:
            self.notebook.select(frame)
            self.current_page_id = page.tab_id
            self.workspace_modified = True
            # New page - fit to screen
            self.root.after(300, lambda: (self._zoom_fit(), self._update_display(), self._draw_rulers(page)))
        else:
            # Loading from workspace - don't render yet, will be rendered when selected
            # Only set current_page_id if this is the first page or if it's marked as active
            if page.active or self.current_page_id is None:
                self.notebook.select(frame)
                self.current_page_id = page.tab_id
            # Don't call _update_display here - it will be called after all pages are loaded
    
    def _on_tab_changed(self, event):
        try:
            selected = self.notebook.select()
            for tid, page in self.pages.items():
                if hasattr(page, 'frame') and str(page.frame) == selected:
                    self.current_page_id = tid
                    # Invalidate cache when switching pages (different page/image)
                    self._invalidate_working_image_cache()
                    self._update_view_menu_labels()  # Update menu for new page
                    self._update_display()
                    self._update_tree()
                    break
        except:
            pass
    
    # Canvas events
    def _canvas_to_image(self, x: int, y: int) -> tuple:
        page = self._get_current_page()
        if not page or not hasattr(page, 'canvas'):
            return (0, 0)
        ix = int(page.canvas.canvasx(x) / self.zoom_level)
        iy = int(page.canvas.canvasy(y) / self.zoom_level)
        return (ix, iy)
    
    def _on_click(self, event):
        page = self._get_current_page()
        if not page or page.original_image is None:
            return
        
        x, y = self._canvas_to_image(event.x, event.y)
        h, w = page.original_image.shape[:2]
        if not (0 <= x < w and 0 <= y < h):
            return
        
        # Handle object movement start
        if self.is_moving_objects:
            self.object_move_start = (x, y)
            self.object_move_offset = (0, 0)
            return
        
        # Handle pixel movement start
        if self.is_moving_pixels:
            self.pixel_move_start = (x, y)
            self.pixel_move_offset = (0, 0)
            return
        
        if self.current_mode == "select":
            self._select_at(x, y)
        elif self.current_mode == "flood":
            self._flood_fill(x, y)
        elif self.current_mode == "rect":
            # Start rectangle selection
            self.rect_start = (x, y)
            self.rect_current = (x, y)
            self.is_drawing = True
            self._redraw_rectangle()
        elif self.current_mode in ["polyline", "line"]:
            # Check snap
            if self.current_mode == "polyline" and len(self.current_points) >= 3:
                d = ((x - self.current_points[0][0])**2 + (y - self.current_points[0][1])**2)**0.5
                if d < self.settings.snap_distance:
                    self._finish_polyline()
                    return
            self.current_points.append((x, y))
            self._redraw_points()
        elif self.current_mode == "freeform":
            self.is_drawing = True
            self.current_points = [(x, y)]
    
    def _on_double_click(self, event):
        if self.current_mode == "polyline" and len(self.current_points) >= 3:
            self._finish_polyline()
    
    def _on_right_click(self, event):
        """Handle right-click on canvas - show context menu or remove point."""
        # If drawing a polyline, remove last point
        if self.current_points:
            self.current_points.pop()
            self._redraw_points()
            return
        
        # Cancel move operations on right-click
        if self.is_moving_pixels:
            self.is_moving_pixels = False
            self.pixel_move_start = None
            self.pixel_move_offset = None
            page = self._get_current_page()
            if page and hasattr(page, 'canvas'):
                page.canvas.config(cursor="crosshair")
            self._update_display()
            return
        
        if self.is_moving_objects:
            self.is_moving_objects = False
            self.object_move_start = None
            self.object_move_offset = None
            page = self._get_current_page()
            if page and hasattr(page, 'canvas'):
                page.canvas.config(cursor="crosshair")
            self._update_display()
            return
        
        # If we have pixel selection or object selection, show context menu
        page = self._get_current_page()
        if not page:
            return
        
        x, y = self._canvas_to_image(event.x, event.y)
        h, w = page.original_image.shape[:2]
        if not (0 <= x < w and 0 <= y < h):
            return
        
        # Check if we have pixel selection or object selection
        has_pixel_selection = self.selected_pixel_mask is not None
        has_object_selection = len(self.selected_object_ids) > 0 or len(self.selected_element_ids) > 0
        
        if has_pixel_selection or has_object_selection:
            self._show_canvas_context_menu(event, x, y, has_pixel_selection)
    
    def _show_canvas_context_menu(self, event, x: int, y: int, has_pixel_selection: bool):
        """Show context menu for canvas selections."""
        menu = tk.Menu(self.root, tearoff=0, bg=self.theme["menu_bg"], 
                      fg=self.theme["menu_fg"],
                      activebackground=self.theme["menu_hover"],
                      activeforeground=self.theme["selection_fg"])
        
        page = self._get_current_page()
        if not page:
            return
        
        if has_pixel_selection:
            # Pixel selection menu
            menu.add_command(label="Move Selection", command=lambda: self._start_move_pixels())
            menu.add_separator()
            menu.add_command(label="Add to Hidden Text", command=lambda: self._add_pixels_to_hidden_category("mark_text"))
            menu.add_command(label="Add to Hidden Hatching", command=lambda: self._add_pixels_to_hidden_category("mark_hatch"))
            menu.add_command(label="Add to Hidden Lines", command=lambda: self._add_pixels_to_hidden_category("mark_line"))
            menu.add_separator()
            menu.add_command(label="Duplicate Selection", command=self._duplicate_pixel_selection)
            menu.add_separator()
            menu.add_command(label="Clear Selection", command=self._clear_pixel_selection)
        elif len(self.selected_object_ids) > 0 or len(self.selected_element_ids) > 0:
            # Object/element selection menu - extend existing functionality
            menu.add_command(label="Duplicate", command=self._duplicate_selected)
            menu.add_separator()
            # Check if we can add selected elements to hidden categories
            if len(self.selected_element_ids) > 0:
                menu.add_command(label="Add to Hidden Text", command=lambda: self._add_elements_to_hidden_category("mark_text"))
                menu.add_command(label="Add to Hidden Hatching", command=lambda: self._add_elements_to_hidden_category("mark_hatch"))
                menu.add_command(label="Add to Hidden Lines", command=lambda: self._add_elements_to_hidden_category("mark_line"))
                menu.add_separator()
        
        # Show menu
        menu.tk_popup(event.x_root, event.y_root)
    
    def _on_drag(self, event):
        page = self._get_current_page()
        if not page:
            return
        
        x, y = self._canvas_to_image(event.x, event.y)
        
        # Handle pixel movement
        if self.is_moving_pixels and self.selected_pixel_mask is not None and self.selected_pixel_bbox:
            if self.pixel_move_start is None:
                self.pixel_move_start = (x, y)
                self.pixel_move_offset = (0, 0)
            else:
                start_x, start_y = self.pixel_move_start
                offset_x = x - start_x
                offset_y = y - start_y
                self.pixel_move_offset = (offset_x, offset_y)
                self._update_display()  # Show preview of move
            return
        
        # Handle object/element movement
        if self.is_moving_objects:
            if self.object_move_start is None:
                self.object_move_start = (x, y)
                self.object_move_offset = (0, 0)
            else:
                start_x, start_y = self.object_move_start
                offset_x = x - start_x
                offset_y = y - start_y
                self.object_move_offset = (offset_x, offset_y)
                self._update_display()  # Show preview of move
            return
        
        if self.current_mode == "rect" and self.is_drawing and self.rect_start:
            self.rect_current = (x, y)
            self._redraw_rectangle()
        elif self.current_mode == "freeform" and self.is_drawing:
            self.current_points.append((x, y))
            self._redraw_points()
    
    def _on_release(self, event):
        # Handle pixel movement completion
        if self.is_moving_pixels and self.pixel_move_offset is not None:
            offset_x, offset_y = self.pixel_move_offset
            self._finish_move_pixels(offset_x, offset_y)
            self.is_moving_pixels = False
            self.pixel_move_start = None
            self.pixel_move_offset = None
            page = self._get_current_page()
            if page and hasattr(page, 'canvas'):
                page.canvas.config(cursor="crosshair")
            return
        
        # Handle object/element movement completion
        if self.is_moving_objects and self.object_move_offset is not None:
            offset_x, offset_y = self.object_move_offset
            self._finish_move_objects(offset_x, offset_y)
            self.is_moving_objects = False
            self.object_move_start = None
            self.object_move_offset = None
            page = self._get_current_page()
            if page and hasattr(page, 'canvas'):
                page.canvas.config(cursor="crosshair")
            return
        
        if self.current_mode == "rect" and self.is_drawing and self.rect_start and self.rect_current:
            x, y = self._canvas_to_image(event.x, event.y)
            self.rect_current = (x, y)
            self._finish_rectangle()
        elif self.current_mode == "freeform" and self.is_drawing:
            self.is_drawing = False
            if len(self.current_points) >= 2:
                self._finish_freeform()
    
    def _on_motion(self, event):
        x, y = self._canvas_to_image(event.x, event.y)
        self.status_var.set(f"({x}, {y}) | Mode: {self.current_mode}")
    
    # Segmentation operations
    def _select_at(self, x: int, y: int):
        """Select object/instance/element at given image coordinates."""
        page = self._get_current_page()
        if not page:
            return
        
        # Search through all_objects for elements on this page
        result = None
        for obj in self.all_objects:
            for inst in obj.instances:
                # Only check instances on current page
                if inst.page_id != page.tab_id:
                    continue
                for elem in inst.elements:
                    if elem.contains_point(x, y):
                        result = (obj, inst, elem)
                        break
                if result:
                    break
            if result:
                break
        
        if result:
            obj, inst, elem = result
            self.selected_object_ids = {obj.object_id}
            self.selected_instance_ids = {inst.instance_id}
            self.selected_element_ids = {elem.element_id}
            
            # Select in tree view
            tree_id = f"o_{obj.object_id}"
            if self.object_tree.exists(tree_id):
                self.object_tree.selection_set(tree_id)
                self.object_tree.see(tree_id)
        else:
            self.selected_object_ids.clear()
            self.selected_instance_ids.clear()
            self.selected_element_ids.clear()
            self.object_tree.selection_remove(*self.object_tree.selection())
        
        self._update_display()
    
    def _flood_fill(self, x: int, y: int):
        page = self._get_current_page()
        cat_name = self.category_var.get()
        if not page or not cat_name:
            return
        
        cat = self.categories.get(cat_name)
        if not cat:
            return
        
        # Debug: Check page state before getting working image
        print(f"_flood_fill at ({x}, {y}): page.hide_text={getattr(page, 'hide_text', 'NOT SET')}, "
              f"page.hide_hatching={getattr(page, 'hide_hatching', 'NOT SET')}")
        text_mask = getattr(page, 'combined_text_mask', None)
        hatch_mask = getattr(page, 'combined_hatch_mask', None)
        print(f"  text_mask exists: {text_mask is not None}, "
              f"hatch_mask exists: {hatch_mask is not None}")
        if text_mask is not None:
            print(f"  text_mask pixels: {np.sum(text_mask > 0)}")
        
        # Get image with text/hatch hidden if those options are enabled
        working_image = self._get_working_image(page)
        
        # Always exclude line regions from flood fill to prevent selecting through leaders
        # This prevents flood fill from incorrectly including objects intersected by leader lines
        if hasattr(page, 'combined_line_mask') and page.combined_line_mask is not None:
            # Temporarily mask out line regions from the working image
            line_mask = page.combined_line_mask
            h_img, w_img = working_image.shape[:2]
            # Ensure mask shape matches image shape
            if isinstance(line_mask, np.ndarray) and line_mask.shape == (h_img, w_img):
                # Set line regions to white (same as background) so flood fill won't cross them
                working_image = working_image.copy()
                working_image[line_mask > 0] = [255, 255, 255]
        
        mask = self.engine.flood_fill(working_image, (x, y))
        if np.sum(mask) == 0:
            return
        
        # Handle special marker categories - add to mask list, not objects
        if cat_name == "mark_text":
            self._add_manual_text_region(page, mask, (x, y), "flood")
            return
        elif cat_name == "mark_hatch":
            self._add_manual_hatch_region(page, mask, (x, y), "flood")
            return
        elif cat_name == "mark_line":
            # For mark_line, we need to get points from the selection
            # Since flood fill doesn't give us points, we'll use the seed point
            points = [(x, y)]  # Start with seed point
            self._add_manual_line_region(page, mask, points, "flood")
            return
        
        elem = SegmentElement(
            category=cat_name, mode="flood", points=[(x, y)],
            mask=mask, color=cat.color_rgb, label_position=self.label_position
        )
        self._add_element(elem)
    
    def _finish_polyline(self):
        if len(self.current_points) < 3:
            return
        page = self._get_current_page()
        if not page:
            return
        
        h, w = page.original_image.shape[:2]
        mask = self.engine.create_polygon_mask((h, w), self.current_points)
        
        # Check if pixel selection mode is enabled
        if self.pixel_selection_mode_var.get():
            self._set_pixel_selection(mask)
            self.current_points.clear()
            self._redraw_points()
            self.status_var.set("Pixel selection created from polyline")
            return
        
        cat_name = self.category_var.get() or "planform"
        cat = self.categories.get(cat_name)
        
        # Handle special marker categories
        if cat_name == "mark_text":
            self._add_manual_text_region(page, mask, self.current_points[0], "polyline")
            self.current_points.clear()
            self._redraw_points()
            return
        elif cat_name == "mark_hatch":
            self._add_manual_hatch_region(page, mask, self.current_points[0], "polyline")
            self.current_points.clear()
            self._redraw_points()
            return
        elif cat_name == "mark_line":
            # For polyline selection, detect the actual object within the polyline area
            # and replace the mask with the detected object shape
            detected_mask = self._detect_object_in_polyline(page, mask)
            if detected_mask is not None:
                mask = detected_mask
            self._add_manual_line_region(page, mask, list(self.current_points), "polyline")
            self.current_points.clear()
            self._redraw_points()
            return
        
        elem = SegmentElement(
            category=cat_name, mode="polyline", points=list(self.current_points),
            mask=mask, color=cat.color_rgb if cat else (128, 128, 128),
            label_position=self.label_position
        )
        self._add_element(elem)
        # Note: Planform object detection and storage happens in _add_element
        self.current_points.clear()
        self._redraw_points()
    
    def _finish_freeform(self):
        if len(self.current_points) < 2:
            return
        page = self._get_current_page()
        if not page:
            return
        
        h, w = page.original_image.shape[:2]
        mask = self.engine.create_freeform_mask((h, w), self.current_points)
        
        # Check if pixel selection mode is enabled
        if self.pixel_selection_mode_var.get():
            self._set_pixel_selection(mask)
            self.current_points.clear()
            self._redraw_points()
            self.status_var.set("Pixel selection created from freeform")
            return
        
        cat_name = self.category_var.get() or "planform"
        cat = self.categories.get(cat_name)
        
        # Handle special marker categories
        if cat_name == "mark_text":
            self._add_manual_text_region(page, mask, self.current_points[0], "freeform")
            self.current_points.clear()
            self._redraw_points()
            return
        elif cat_name == "mark_hatch":
            self._add_manual_hatch_region(page, mask, self.current_points[0], "freeform")
            self.current_points.clear()
            self._redraw_points()
            return
        
        elem = SegmentElement(
            category=cat_name, mode="freeform", points=list(self.current_points),
            mask=mask, color=cat.color_rgb if cat else (128, 128, 128),
            label_position=self.label_position
        )
        self._add_element(elem)
        self.current_points.clear()
        self._redraw_points()
    
    def _finish_line(self):
        if len(self.current_points) < 2:
            return
        page = self._get_current_page()
        if not page:
            return
        
        cat_name = self.category_var.get() or "longeron"
        cat = self.categories.get(cat_name)
        h, w = page.original_image.shape[:2]
        
        # For mark_line category, use findline functionality (skeletonization, tracing, etc.)
        if cat_name == "mark_line":
            mask = self._trace_line_with_findline(page, list(self.current_points))
            if mask is None:
                # Fallback to simple line mask
                mask = self.engine.create_line_mask((h, w), self.current_points)
            self._add_manual_line_region(page, mask, list(self.current_points), "line")
            self.current_points.clear()
            self._redraw_points()
            # Update display once at the end (like rect mode) - deferred to avoid rendering during creation
            self.renderer.invalidate_cache()
            self._update_display()
            return
        
        # For other categories, use simple line mask
        mask = self.engine.create_line_mask((h, w), self.current_points)
        
        # Debug: Check mask creation
        pixel_count = np.sum(mask > 0)
        print(f"DEBUG LINE: Created line mask with {pixel_count} pixels from {len(self.current_points)} points")
        
        # Handle special marker categories
        if cat_name == "mark_text":
            self._add_manual_text_region(page, mask, self.current_points[0], "line")
            self.current_points.clear()
            self._redraw_points()
            return
        elif cat_name == "mark_hatch":
            self._add_manual_hatch_region(page, mask, self.current_points[0], "line")
            self.current_points.clear()
            self._redraw_points()
            return
        
        elem = SegmentElement(
            category=cat_name, mode="line", points=list(self.current_points),
            mask=mask, color=cat.color_rgb if cat else (128, 128, 128),
            label_position=self.label_position
        )
        self._add_element(elem)
        self.current_points.clear()
        self._redraw_points()
    
    def _add_element(self, elem: SegmentElement):
        page = self._get_current_page()
        if not page:
            return
        
        # Group mode: collect elements without creating object yet
        if self.group_mode_active and elem.category != "eraser":
            self.group_mode_elements.append(elem)
            self._update_group_count()
            self._update_display()
            self.status_var.set(f"Added to group ({len(self.group_mode_elements)})")
            return
        
        # Check if anything is selected - add to that object's last instance
        # BUT only if the selected category matches the object's category
        selected_obj_id = self._get_selected_object_for_adding()
        if selected_obj_id and elem.category != "eraser":
            obj = self._get_object_by_id(selected_obj_id)
            if obj and obj.instances:
                # Only add to existing object if category matches
                if obj.category == elem.category:
                    # Add element to the last instance of the selected object
                    last_inst = obj.instances[-1]
                    last_inst.elements.append(elem)
                    
                    # CRITICAL: If this is a planform, find and store all visible objects within its boundaries
                    # Do this asynchronously to avoid blocking the UI
                    if elem.category == "planform" and elem.mode == "polyline" and elem.mask is not None:
                        # Defer the expensive object finding to avoid blocking
                        def find_and_store_objects():
                            try:
                                objects_within = self._find_objects_within_planform(page, elem.mask, obj.object_id)
                                self.planform_objects[obj.object_id] = objects_within
                                print(f"DEBUG: Planform {obj.object_id} ({obj.name}) updated with {len(objects_within)} objects within boundaries")
                                for obj_id in objects_within:
                                    o = self._get_object_by_id(obj_id)
                                    if o:
                                        print(f"  - {o.name} ({obj_id})")
                            except Exception as e:
                                print(f"ERROR finding objects for planform {obj.object_id}: {e}")
                                import traceback
                                traceback.print_exc()
                        
                        # Run in background to avoid blocking
                        self.root.after(100, find_and_store_objects)
                    
                    self.workspace_modified = True
                    self.renderer.invalidate_cache()  # Objects changed
                    
                    # Ensure sequential instance numbering
                    self._renumber_instances(obj)
                    
                    # Preserve selection after tree update
                    old_selection = self.object_tree.selection()
                    self._update_tree_item(obj)  # Only update this object
                    # Re-select
                    for item in old_selection:
                        if self.object_tree.exists(item):
                            try:
                                self.object_tree.selection_add(item)
                            except:
                                pass
                    
                    self._update_display()
                    self.status_var.set(f"Added to {obj.name} instance {last_inst.instance_num}")
                    return
                # Category mismatch - fall through to create new object
        
        # No selection or eraser: create a new object
        cat = self.categories.get(elem.category)
        prefix = cat.prefix if cat else elem.category[0].upper()
        count = sum(1 for o in self.all_objects if o.category == elem.category) + 1
        
        # Assign current view if set
        current_view = getattr(self, 'current_view_var', None)
        view_type = current_view.get() if current_view else ""
        
        new_obj = SegmentedObject(name=f"{prefix}{count}", category=elem.category)
        inst = ObjectInstance(instance_num=1, page_id=page.tab_id, view_type=view_type)
        inst.elements.append(elem)
        new_obj.instances.append(inst)
        self.all_objects.append(new_obj)
        
        # CRITICAL: If this is a planform, find and store all visible objects within its boundaries
        # Do this asynchronously to avoid blocking planform creation
        if elem.category == "planform" and elem.mode == "polyline" and elem.mask is not None:
            # Defer the expensive object finding to avoid blocking the UI
            def find_and_store_objects():
                try:
                    objects_within = self._find_objects_within_planform(page, elem.mask, new_obj.object_id)
                    self.planform_objects[new_obj.object_id] = objects_within
                    print(f"DEBUG: Planform {new_obj.object_id} ({new_obj.name}) created with {len(objects_within)} objects within boundaries")
                    for obj_id in objects_within:
                        obj = self._get_object_by_id(obj_id)
                        if obj:
                            print(f"  - {obj.name} ({obj_id})")
                except Exception as e:
                    print(f"ERROR finding objects for planform {new_obj.object_id}: {e}")
                    import traceback
                    traceback.print_exc()
            
            # Run in background to avoid blocking - use a short delay to let UI update first
            self.root.after(50, find_and_store_objects)
        
        self.workspace_modified = True
        self.renderer.invalidate_cache()  # Objects changed
        self._add_tree_item(new_obj)  # Only add new item
        self._update_display()
        self.status_var.set(f"Created: {new_obj.name}")
    
    # Display
    def _get_objects_for_page(self, page_id: str) -> List[SegmentedObject]:
        """Get objects that have instances on a specific page."""
        result = []
        for obj in self.all_objects:
            # Check if any instance is on this page
            has_instance_on_page = any(inst.page_id == page_id for inst in obj.instances)
            if has_instance_on_page:
                result.append(obj)
        return result
    
    def _find_objects_within_planform(self, page: PageTab, planform_mask: np.ndarray, planform_obj_id: str) -> List[str]:
        """
        Find all visible objects that fall within the exact boundaries of a planform polyline.
        
        Args:
            page: The current page
            planform_mask: The planform's polyline mask (not a rectangle)
            planform_obj_id: The planform object ID to exclude from results
            
        Returns:
            List of object IDs that are within the planform boundaries
        """
        try:
            h, w = page.original_image.shape[:2]
            if planform_mask.shape != (h, w):
                print(f"WARNING: Planform mask shape {planform_mask.shape} doesn't match page shape {(h, w)}")
                return []
            
            mark_categories = {"mark_text", "mark_hatch", "mark_line"}
            objects_within = []
            
            # Get visible objects on this page - cache this to avoid repeated calls
            page_objects = self._get_objects_for_page(page.tab_id)
            
            # Early exit if no objects
            if not page_objects:
                return []
            
            # Pre-check: get bounding box of planform to quickly filter objects
            ys, xs = np.where(planform_mask > 0)
            if len(xs) == 0:
                return []
            
            planform_x_min, planform_x_max = int(np.min(xs)), int(np.max(xs)) + 1
            planform_y_min, planform_y_max = int(np.min(ys)), int(np.max(ys)) + 1
            
            for obj in page_objects:
                # Skip the planform itself and mark_* categories
                if obj.object_id == planform_obj_id or obj.category in mark_categories:
                    continue
                
                # Skip other planform objects
                if obj.category == "planform":
                    continue
                
                # Skip objects from invisible categories
                cat = self.categories.get(obj.category)
                if not cat or not cat.visible:
                    continue
                
                # Quick bounding box check first - if object's bbox doesn't overlap with planform bbox, skip
                obj_has_overlap = False
                for inst in obj.instances:
                    if inst.page_id == page.tab_id:
                        for elem in inst.elements:
                            if elem.mask is not None and elem.mask.shape == (h, w):
                                # OPTIMIZATION: Faster bounding box calculation
                                mask_bool = elem.mask > 0
                                if not np.any(mask_bool):
                                    continue
                                
                                # Get bounding box efficiently using any() instead of np.where on full mask
                                rows = np.any(mask_bool, axis=1)
                                cols = np.any(mask_bool, axis=0)
                                if not np.any(rows) or not np.any(cols):
                                    continue
                                
                                elem_y_min, elem_y_max = np.where(rows)[0][[0, -1]]
                                elem_x_min, elem_x_max = np.where(cols)[0][[0, -1]]
                                elem_y_max += 1
                                elem_x_max += 1
                                
                                # Check if bounding boxes overlap
                                if (elem_x_max < planform_x_min or elem_x_min > planform_x_max or
                                    elem_y_max < planform_y_min or elem_y_min > planform_y_max):
                                    continue  # Bounding boxes don't overlap, skip expensive pixel check
                                
                                # Only check overlap in the ROI (region of interest) where bboxes overlap
                                roi_x_min = max(0, min(elem_x_min, planform_x_min))
                                roi_x_max = min(w, max(elem_x_max, planform_x_max))
                                roi_y_min = max(0, min(elem_y_min, planform_y_min))
                                roi_y_max = min(h, max(elem_y_max, planform_y_max))
                                
                                # Check overlap only in the ROI - much faster than full image
                                elem_roi = elem.mask[roi_y_min:roi_y_max, roi_x_min:roi_x_max]
                                planform_roi = planform_mask[roi_y_min:roi_y_max, roi_x_min:roi_x_max]
                                pixels_overlap = np.sum((elem_roi > 0) & (planform_roi > 0))
                                
                                # Object overlaps if ANY pixels are within the planform polyline
                                if pixels_overlap > 0:
                                    obj_has_overlap = True
                                    break
                        if obj_has_overlap:
                            break
                
                if obj_has_overlap:
                    objects_within.append(obj.object_id)
            
            return objects_within
        except Exception as e:
            print(f"ERROR in _find_objects_within_planform: {e}")
            import traceback
            traceback.print_exc()
            return []  # Return empty list on error to avoid breaking planform creation
    
    def _update_display(self, immediate: bool = False):
        """
        Update the display with debouncing for performance.
        
        Args:
            immediate: If True, update immediately without debouncing
        """
        # Cancel any pending update
        if self._update_display_timer_id is not None:
            self.root.after_cancel(self._update_display_timer_id)
            self._update_display_timer_id = None
        
        if immediate:
            self._do_update_display()
        else:
            # Debounce: wait 50ms before updating (cancels previous if called again)
            self._update_display_pending = True
            self._update_display_timer_id = self.root.after(50, self._do_update_display)
    
    def _do_update_display(self):
        """Internal method that actually performs the display update."""
        self._update_display_pending = False
        self._update_display_timer_id = None
        
        page = self._get_current_page()
        if not page or page.original_image is None or not hasattr(page, 'canvas'):
            return
        
        # Get objects for this page
        page_objects = self._get_objects_for_page(page.tab_id)
        
        # Get page-specific view settings
        hide_background = getattr(page, 'hide_background', False)
        
        # Get category visibility settings
        mark_text_cat = self.categories.get("mark_text")
        mark_hatch_cat = self.categories.get("mark_hatch")
        mark_line_cat = self.categories.get("mark_line")
        
        should_hide_text = mark_text_cat is not None and not mark_text_cat.visible
        should_hide_hatching = mark_hatch_cat is not None and not mark_hatch_cat.visible
        should_hide_lines = mark_line_cat is not None and not mark_line_cat.visible
        
        # Build set of selected object IDs for mark_* categories that need highlighting
        selected_mark_obj_ids = set()
        for obj_id in self.selected_object_ids:
            obj = self._get_object_by_id(obj_id)
            if obj and obj.category in ["mark_text", "mark_hatch", "mark_line"]:
                selected_mark_obj_ids.add(obj_id)
        
        # Also check if any selected instance/element belongs to a mark_* object
        for obj in page_objects:
            if obj.category in ["mark_text", "mark_hatch", "mark_line"]:
                for inst in obj.instances:
                    if inst.instance_id in self.selected_instance_ids:
                        selected_mark_obj_ids.add(obj.object_id)
                    for elem in inst.elements:
                        if elem.element_id in self.selected_element_ids:
                            selected_mark_obj_ids.add(obj.object_id)
        
        # Filter out mark_text/hatch/line objects for rendering (don't draw fill)
        # BUT keep them if they're selected (so they can be highlighted)
        render_objects = []
        for obj in page_objects:
            if obj.category == "mark_text":
                # Only include if selected (for highlighting), regardless of category visibility
                if obj.object_id in selected_mark_obj_ids:
                    render_objects.append(obj)
                    # Debug: check if masks exist
                    has_mask = any(
                        elem.mask is not None and np.any(elem.mask > 0)
                        for inst in obj.instances
                        for elem in inst.elements
                    )
                    if not has_mask:
                        print(f"WARNING: mark_text object {obj.object_id} selected but has no valid mask")
            elif obj.category == "mark_hatch":
                # Only include if selected (for highlighting), regardless of category visibility
                if obj.object_id in selected_mark_obj_ids:
                    render_objects.append(obj)
            elif obj.category == "mark_line":
                # Only include if selected (for highlighting), regardless of category visibility
                if obj.object_id in selected_mark_obj_ids:
                    render_objects.append(obj)
                    # Debug: check if masks exist
                    mask_info = []
                    for inst in obj.instances:
                        for elem in inst.elements:
                            if elem.mask is None:
                                mask_info.append(f"{elem.element_id}: None")
                            elif np.sum(elem.mask > 0) == 0:
                                mask_info.append(f"{elem.element_id}: empty")
                            else:
                                mask_info.append(f"{elem.element_id}: {np.sum(elem.mask > 0)} pixels")
                    
                    has_mask = any(
                        elem.mask is not None and np.any(elem.mask > 0)
                        for inst in obj.instances
                        for elem in inst.elements
                    )
                    if not has_mask:
                        print(f"DEBUG WARNING: mark_line object {obj.object_id} selected but has no valid mask. Masks: {', '.join(mask_info)}")
                    else:
                        print(f"DEBUG: mark_line object {obj.object_id} selected with valid masks: {', '.join(mask_info)}")
            else:
                # Include all other objects normally
                render_objects.append(obj)
        
        # Debug output
        if selected_mark_obj_ids:
            print(f"DEBUG: Selected mark objects: {selected_mark_obj_ids}")
            print(f"DEBUG: Render objects count: {len(render_objects)}, mark objects in render: {sum(1 for o in render_objects if o.category in ['mark_text', 'mark_hatch', 'mark_line'])}")
        
        # Get text mask if hiding text (only when category is unchecked)
        text_mask = None
        if should_hide_text:
            if hasattr(page, 'combined_text_mask') and page.combined_text_mask is not None:
                text_mask = page.combined_text_mask
            elif hasattr(page, 'text_mask') and page.text_mask is not None:
                text_mask = page.text_mask
        
        # Get hatching mask if hiding hatching
        hatching_mask = None
        if should_hide_hatching:
            if hasattr(page, 'combined_hatch_mask') and page.combined_hatch_mask is not None:
                hatching_mask = page.combined_hatch_mask
            elif hasattr(page, 'hatching_mask') and page.hatching_mask is not None:
                hatching_mask = page.hatching_mask
        
        # Get line mask if hiding lines (only when category is unchecked)
        line_mask = None
        if should_hide_lines:
            if hasattr(page, 'combined_line_mask') and page.combined_line_mask is not None:
                line_mask = page.combined_line_mask
        
        # Get pixel selection info for rendering
        pixel_selection_mask = self.selected_pixel_mask
        pixel_move_offset = self.pixel_move_offset if self.is_moving_pixels else None
        
        # Get object move info for rendering
        object_move_offset = self.object_move_offset if self.is_moving_objects else None
        
        rendered = self.renderer.render_page(
            page, self.categories, self.zoom_level, self.show_labels,
            self.selected_object_ids, self.selected_instance_ids, self.selected_element_ids,
            self.settings.planform_opacity, self.group_mode_elements,
            hide_background=hide_background,
            objects=render_objects,
            text_mask=text_mask,
            hatching_mask=hatching_mask,
            line_mask=line_mask,
            pixel_selection_mask=pixel_selection_mask,
            pixel_move_offset=pixel_move_offset,
            object_move_offset=object_move_offset
        )
        
        pil_img = Image.fromarray(cv2.cvtColor(rendered, cv2.COLOR_BGRA2RGBA))
        page.tk_image = ImageTk.PhotoImage(pil_img)
        
        page.canvas.delete("all")
        page.canvas.create_image(0, 0, anchor=tk.NW, image=page.tk_image)
        page.canvas.configure(scrollregion=(0, 0, rendered.shape[1], rendered.shape[0]))
        
        self._redraw_points()
        
        # Update zoom display
        zoom_text = f"{int(self.zoom_level * 100)}%"
        self.zoom_label.config(text=zoom_text)
        self.status_bar.set_item_text("zoom", zoom_text)
        
        # Update rulers
        self._draw_rulers(page)
    
    def _redraw_points(self):
        page = self._get_current_page()
        if not page or not hasattr(page, 'canvas'):
            return
        
        page.canvas.delete("temp")
        
        if not self.current_points:
            return
        
        scaled = [(int(x * self.zoom_level), int(y * self.zoom_level)) for x, y in self.current_points]
        
        # Snap indicator for polyline
        if self.current_mode == "polyline" and len(scaled) >= 3:
            r = int(self.settings.snap_distance * self.zoom_level)
            page.canvas.create_oval(scaled[0][0]-r, scaled[0][1]-r, scaled[0][0]+r, scaled[0][1]+r,
                                   outline="lime", width=2, dash=(4, 2), tags="temp")
        
        for i, (x, y) in enumerate(scaled):
            color = "lime" if i == 0 else "yellow"
            page.canvas.create_oval(x-4, y-4, x+4, y+4, fill=color, outline="black", tags="temp")
        
        if len(scaled) > 1:
            for i in range(len(scaled) - 1):
                # Use dark color for visibility on white paper
                page.canvas.create_line(scaled[i][0], scaled[i][1], scaled[i+1][0], scaled[i+1][1],
                                        fill="#333333", width=2, tags="temp")
    
    def _redraw_rectangle(self):
        """Draw rectangle preview on canvas."""
        page = self._get_current_page()
        if not page or not hasattr(page, 'canvas') or not self.rect_start or not self.rect_current:
            return
        
        page.canvas.delete("rect")
        
        x1, y1 = self.rect_start
        x2, y2 = self.rect_current
        
        # Scale to canvas coordinates
        sx1 = int(x1 * self.zoom_level)
        sy1 = int(y1 * self.zoom_level)
        sx2 = int(x2 * self.zoom_level)
        sy2 = int(y2 * self.zoom_level)
        
        # Draw rectangle outline
        self.rect_id = page.canvas.create_rectangle(
            sx1, sy1, sx2, sy2,
            outline="cyan", width=2, dash=(4, 2), tags="rect"
        )
    
    def _finish_rectangle(self):
        """Finish rectangle selection and detect objects or create pixel selection."""
        page = self._get_current_page()
        if not page or not self.rect_start or not self.rect_current:
            return
        
        # Clear rectangle preview
        if page and hasattr(page, 'canvas'):
            page.canvas.delete("rect")
        
        x1, y1 = self.rect_start
        x2, y2 = self.rect_current
        
        # Normalize rectangle coordinates
        x_min, x_max = min(x1, x2), max(x1, x2)
        y_min, y_max = min(y1, y2), max(y1, y2)
        
        # Reset state
        self.rect_start = None
        self.rect_current = None
        self.is_drawing = False
        
        # Check if pixel selection mode is enabled
        if self.pixel_selection_mode_var.get():
            # Create pixel selection from rectangle
            h, w = page.original_image.shape[:2]
            mask = np.zeros((h, w), dtype=np.uint8)
            # Ensure coordinates are within image bounds
            x_min = max(0, min(w, x_min))
            x_max = max(0, min(w, x_max))
            y_min = max(0, min(h, y_min))
            y_max = max(0, min(h, y_max))
            mask[y_min:y_max, x_min:x_max] = 255
            self._set_pixel_selection(mask)
            self.status_var.set(f"Pixel selection created: {x_max-x_min}x{y_max-y_min} pixels")
            return
        
        # Get category
        cat_name = self.category_var.get()
        if not cat_name:
            return
        
        # Detect connected components in rectangle
        print(f"DEBUG: Rectangle selection: ({x_min}, {y_min}) to ({x_max}, {y_max}), category: {cat_name}")
        detected_objects = self._detect_objects_in_rectangle(page, x_min, y_min, x_max, y_max)
        print(f"DEBUG: Detected {len(detected_objects)} objects in rectangle")
        
        if not detected_objects:
            self.status_var.set("No objects detected in rectangle")
            return
        
        if len(detected_objects) == 1:
            # Single object - create it directly
            mask = detected_objects[0]
            self._create_object_from_mask(page, cat_name, mask)
        else:
            # Multiple objects - show selection dialog
            self._show_rectangle_selection_dialog(page, cat_name, detected_objects, x_min, y_min, x_max, y_max)
    
    def _is_line_like_shape(self, mask: np.ndarray) -> bool:
        """
        Check if a mask represents a line-like shape (elongated, not circular).
        This is a simpler check than full leader line detection.
        """
        mask_pixels = np.where(mask > 0)
        if len(mask_pixels[0]) == 0:
            return False
        
        # Calculate aspect ratio of bounding box
        ys, xs = mask_pixels
        if len(xs) == 0:
            return False
        
        x_min, x_max = int(np.min(xs)), int(np.max(xs))
        y_min, y_max = int(np.min(ys)), int(np.max(ys))
        width = x_max - x_min + 1
        height = y_max - y_min + 1
        
        # Line should be elongated (aspect ratio > 1.5:1)
        aspect_ratio = max(width, height) / max(min(width, height), 1)
        return aspect_ratio >= 1.5
    
    def _is_leader_line(self, page: PageTab, mask: np.ndarray) -> bool:
        """
        Check if a mask represents a leader line (line with arrow pointing to text).
        
        Criteria:
        1. Has endpoints (line-like structure)
        2. Proximity to text regions
        3. Arrow detection at one endpoint
        4. Line-like shape (elongated, not circular)
        """
        h, w = page.original_image.shape[:2]
        mask_pixels = np.where(mask > 0)
        
        if len(mask_pixels[0]) == 0:
            return False
        
        # Find endpoints by counting neighbors
        endpoints = []
        for y, x in zip(mask_pixels[0], mask_pixels[1]):
            neighbors = 0
            for dy in [-1, 0, 1]:
                for dx in [-1, 0, 1]:
                    if dy == 0 and dx == 0:
                        continue
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] > 0:
                        neighbors += 1
            if neighbors <= 1:  # Endpoint
                endpoints.append((x, y))
        
        # Leader lines should have 1-2 endpoints
        if len(endpoints) < 1 or len(endpoints) > 2:
            return False
        
        # Check if it's line-like (elongated, not circular)
        # Calculate aspect ratio of bounding box
        ys, xs = mask_pixels
        if len(xs) == 0:
            return False
        
        x_min, x_max = int(np.min(xs)), int(np.max(xs))
        y_min, y_max = int(np.min(ys)), int(np.max(ys))
        width = x_max - x_min + 1
        height = y_max - y_min + 1
        
        # Line should be elongated (aspect ratio > 2:1 or < 1:2)
        aspect_ratio = max(width, height) / max(min(width, height), 1)
        if aspect_ratio < 2.0:
            return False  # Too circular/square, not a line
        
        # Check proximity to text regions
        all_text_regions = []
        if hasattr(page, 'auto_text_regions'):
            all_text_regions.extend(page.auto_text_regions)
        if hasattr(page, 'manual_text_regions'):
            all_text_regions.extend(page.manual_text_regions)
        
        # If no text regions, still allow if it's line-like and has arrow
        # (some leader lines might not have detected text nearby)
        has_text_regions = bool(all_text_regions)
        
        # Check if any endpoint is near text (if text regions exist)
        near_text = False
        if has_text_regions:
            for endpoint in endpoints:
                ex, ey = endpoint
                for region in all_text_regions:
                    region_mask = region.get('mask')
                    if region_mask is None:
                        continue
                    
                    text_pixels = np.where(region_mask > 0)
                    if len(text_pixels[0]) > 0:
                        text_y = np.mean(text_pixels[0])
                        text_x = np.mean(text_pixels[1])
                        dist = np.sqrt((ex - text_x)**2 + (ey - text_y)**2)
                        
                        if dist < 100:  # Within 100 pixels
                            near_text = True
                            break
                if near_text:
                    break
        
        # Check for arrow at endpoint (small filled region at one end)
        # Look for endpoint with more pixels nearby (arrowhead)
        has_arrow = False
        for endpoint in endpoints:
            ax, ay = endpoint
            arrow_region_size = 15
            x1 = max(0, ax - arrow_region_size)
            x2 = min(w, ax + arrow_region_size)
            y1 = max(0, ay - arrow_region_size)
            y2 = min(h, ay + arrow_region_size)
            
            region_mask = mask[y1:y2, x1:x2]
            pixel_count = np.sum(region_mask > 0)
            
            # Arrow should have more pixels than just the line (filled triangle)
            if pixel_count > 30:  # Threshold for arrowhead
                has_arrow = True
                break
        
        # Leader line should have arrow OR be near text (if text regions exist)
        # OR if no text regions, just check for arrow (might be standalone leader)
        if has_arrow:
            return True  # Has arrow, definitely a leader
        
        if has_text_regions and near_text:
            return True  # Near text, likely a leader
        
        # If no text regions but it's line-like, allow it (user might be selecting manually)
        if not has_text_regions:
            return True  # No text to check against, but it's line-like with endpoints
        
        # If has text regions but not near text and no arrow, not a leader
        return False
    
    def _detect_objects_in_rectangle(self, page: PageTab, x_min: int, y_min: int, x_max: int, y_max: int) -> List[np.ndarray]:
        """
        Detect connected components (objects) within a rectangle area.
        
        Uses the working image (with text/hatch hidden if needed) to detect objects.
        If category is mark_line, filters to only include leader lines.
        
        Returns:
            List of binary masks, one for each detected connected component
        """
        h, w = page.original_image.shape[:2]
        
        # Clamp rectangle to image bounds
        x_min = max(0, min(x_min, w - 1))
        x_max = max(0, min(x_max, w - 1))
        y_min = max(0, min(y_min, h - 1))
        y_max = max(0, min(y_max, h - 1))
        
        if x_max <= x_min or y_max <= y_min:
            return []
        
        # Use working image (respects category visibility - hides mark_text/hatch/line if categories are unchecked)
        # This ensures rectangle selection only finds objects that are currently visible
        working_image = self._get_working_image(page)
        
        # Extract rectangle region
        roi = working_image[y_min:y_max, x_min:x_max]
        print(f"DEBUG _detect_objects_in_rectangle: ROI extracted, shape: {roi.shape}")
        
        # Get category name early (needed for morphological operations)
        cat_name = self.category_var.get()
        
        # Convert to grayscale if needed
        if len(roi.shape) == 3:
            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        else:
            gray = roi
        
        # Threshold to get binary image (white paper = 255, lines/text = darker)
        # Try multiple thresholding methods for better detection
        roi_h, roi_w = gray.shape[:2]
        
        # Use adaptive threshold for larger regions, Otsu for smaller ones
        if roi_w > 50 and roi_h > 50:
            # Adaptive threshold for varying lighting
            thresh = cv2.adaptiveThreshold(
                gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2
            )
        else:
            # For small regions, use Otsu's method
            _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        
        # Also try simple threshold as fallback if adaptive doesn't find much
        # (Some images might have uniform background)
        simple_thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)[1]
        
        # Combine both threshold results (union)
        combined_thresh = cv2.bitwise_or(thresh, simple_thresh)
        
        # For mark_line category, DON'T use aggressive morphological operations
        # This ensures we don't lose small features like arrowheads
        # The user is manually selecting a rectangle, so trust their selection
        if cat_name == "mark_line":
            print(f"DEBUG: mark_line mode - using original threshold without aggressive morphology ({np.sum(combined_thresh > 0)} pixels)")
        
        # Find connected components
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(combined_thresh, connectivity=8)
        print(f"DEBUG: Found {num_labels - 1} connected components (excluding background)")
        
        detected_masks = []
        # cat_name already defined above
        filter_leaders_only = (cat_name == "mark_line")
        
        for i in range(1, num_labels):  # Skip label 0 (background)
            # Get component mask
            component_mask = (labels == i).astype(np.uint8) * 255
            
            # Filter out very small components (noise)
            pixel_count = np.sum(component_mask > 0)
            if pixel_count < 50:  # Minimum 50 pixels
                print(f"DEBUG: Component {i} filtered out (too small: {pixel_count} pixels)")
                continue
            
            # Create full-size mask and place component at correct position
            full_mask = np.zeros((h, w), dtype=np.uint8)
            full_mask[y_min:y_max, x_min:x_max] = component_mask
            
            # If filtering for leader lines only, apply lenient checks
            if filter_leaders_only:
                # Calculate dimensions for debug
                ys, xs = np.where(full_mask > 0)
                if len(xs) > 0:
                    x_min_bb, x_max_bb = int(np.min(xs)), int(np.max(xs))
                    y_min_bb, y_max_bb = int(np.min(ys)), int(np.max(ys))
                    width_bb = x_max_bb - x_min_bb + 1
                    height_bb = y_max_bb - y_min_bb + 1
                    aspect_ratio = max(width_bb, height_bb) / max(min(width_bb, height_bb), 1)
                    
                    # Very lenient check - if aspect ratio > 1.2, it's elongated enough
                    # Or if it's small enough (potential arrow), include it
                    is_elongated = aspect_ratio > 1.2
                    is_small = pixel_count < 500  # Small objects might be arrows
                    
                    print(f"DEBUG: Component {i} ({pixel_count} pixels, {width_bb}x{height_bb}, aspect={aspect_ratio:.2f}): elongated={is_elongated}, small={is_small}")
                    
                    if is_elongated or is_small:
                        detected_masks.append(full_mask)
                    else:
                        print(f"DEBUG: Component {i} filtered out (not elongated and not small)")
                else:
                    print(f"DEBUG: Component {i} has no pixels (empty mask)")
            else:
                # Include all components
                print(f"DEBUG: Component {i} ({pixel_count} pixels): included")
                detected_masks.append(full_mask)
        
        print(f"DEBUG: Returning {len(detected_masks)} detected masks")
        return detected_masks
    
    def _detect_object_in_polyline(self, page: PageTab, polyline_mask: np.ndarray) -> Optional[np.ndarray]:
        """
        Detect the actual object shape within a polyline selection area.
        Uses the working image to find connected components within the polyline mask.
        Returns the largest line-like component, or None if nothing found.
        """
        h, w = page.original_image.shape[:2]
        
        # Ensure mask is correct size
        if polyline_mask.shape != (h, w):
            return None
        
        # Get working image (respects category visibility)
        working_image = self._get_working_image(page)
        
        # Convert to grayscale
        if len(working_image.shape) == 3:
            gray = cv2.cvtColor(working_image, cv2.COLOR_BGR2GRAY)
        else:
            gray = working_image
        
        # Threshold to get binary image
        _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
        
        # Apply polyline mask to restrict detection to selected area
        masked_thresh = cv2.bitwise_and(thresh, polyline_mask)
        
        # Find connected components within the masked area
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(masked_thresh, connectivity=8)
        
        if num_labels <= 1:  # Only background
            return None
        
        # Find the largest component that is line-like
        best_label = None
        best_pixel_count = 0
        
        for i in range(1, num_labels):  # Skip label 0 (background)
            component_mask = (labels == i).astype(np.uint8) * 255
            pixel_count = np.sum(component_mask > 0)
            
            # Filter out very small components
            if pixel_count < 50:
                continue
            
            # Check if it's line-like (elongated shape)
            ys, xs = np.where(component_mask > 0)
            if len(xs) > 0:
                x_min_bb, x_max_bb = int(np.min(xs)), int(np.max(xs))
                y_min_bb, y_max_bb = int(np.min(ys)), int(np.max(ys))
                width_bb = x_max_bb - x_min_bb + 1
                height_bb = y_max_bb - y_min_bb + 1
                aspect_ratio = max(width_bb, height_bb) / max(min(width_bb, height_bb), 1)
                
                # Prefer elongated shapes (lines) or small shapes (arrows)
                is_line_like = aspect_ratio > 1.2 or pixel_count < 500
                
                if is_line_like and pixel_count > best_pixel_count:
                    best_pixel_count = pixel_count
                    best_label = i
        
        if best_label is not None:
            # Create full-size mask from the best label
            full_mask = (labels == best_label).astype(np.uint8) * 255
            return full_mask
        
        return None
    
    def _create_object_from_mask(self, page: PageTab, cat_name: str, mask: np.ndarray):
        """Create a mark_* object from a binary mask."""
        cat = self.categories.get(cat_name)
        if not cat:
            return
        
        # For mark_line, use _add_manual_line_region to get proper naming (ml-1, ll-1, etc.)
        if cat_name == "mark_line":
            self._add_manual_line_region(page, mask, [], "rect")
        else:
            # Generate element ID
            element_id = f"{cat_name}_{uuid.uuid4().hex[:8]}"
            
            # Create element
            elem = SegmentElement(
                element_id=element_id,
                category=cat_name,
                mode="rect",  # Mark as created via rectangle selection
                points=[],  # No points for rectangle-selected objects
                mask=mask,
                color=cat.color_rgb,
                label_position=self.label_position
            )
            
            # Add to category using existing _add_element method
            self._add_element(elem)
            
            self.status_var.set(f"Created {cat_name} object from rectangle selection")
    
    def _create_combined_object_from_masks(self, page: PageTab, cat_name: str, 
                                          all_masks: List[np.ndarray], selected_indices: List[int]):
        """
        Create a single combined object from multiple selected masks.
        
        The combined object has an outer boundary (union of all masks) and can have
        exclusion regions for objects that are completely nested inside others.
        
        Args:
            page: The page to create the object on
            cat_name: Category name for the object
            all_masks: List of all detected masks
            selected_indices: Indices of masks to combine
        """
        if not selected_indices or len(selected_indices) < 2:
            return
        
        cat = self.categories.get(cat_name)
        if not cat:
            return
        
        h, w = page.original_image.shape[:2]
        
        # Get selected masks
        selected_masks = []
        for idx in selected_indices:
            if 0 <= idx < len(all_masks):
                mask = all_masks[idx]
                if mask.shape == (h, w):
                    selected_masks.append(mask)
        
        if not selected_masks:
            return
        
        # Create outer boundary: union of all selected masks
        combined_mask = np.zeros((h, w), dtype=np.uint8)
        for mask in selected_masks:
            combined_mask = np.maximum(combined_mask, mask)
        
        # Detect nested objects (objects completely inside other objects) for exclusions
        # An object is nested if all its pixels are within another object's mask
        exclusion_masks = []
        
        for i, mask_i in enumerate(selected_masks):
            mask_i_pixels = np.sum(mask_i > 0)
            if mask_i_pixels == 0:
                continue
            
            # Check if this mask is completely inside any other mask
            is_nested = False
            for j, mask_j in enumerate(selected_masks):
                if i == j:
                    continue
                
                # Check if all pixels of mask_i are within mask_j
                overlap = np.sum((mask_i > 0) & (mask_j > 0))
                if overlap == mask_i_pixels:
                    # mask_i is completely inside mask_j - it's an exclusion
                    is_nested = True
                    break
            
            if is_nested:
                exclusion_masks.append(mask_i)
        
        # Start with union of all masks as outer boundary
        final_mask = combined_mask.copy()
        
        # Subtract nested objects (exclusions) from the outer boundary
        for exclusion_mask in exclusion_masks:
            final_mask = np.maximum(0, final_mask.astype(np.int16) - exclusion_mask.astype(np.int16)).astype(np.uint8)
        
        # For mark_line, use _add_manual_line_region
        if cat_name == "mark_line":
            self._add_manual_line_region(page, final_mask, [], "rect_combined")
        else:
            # Generate element ID
            element_id = f"{cat_name}_combined_{uuid.uuid4().hex[:8]}"
            
            # Create element with combined mask
            elem = SegmentElement(
                element_id=element_id,
                category=cat_name,
                mode="rect_combined",  # Mark as created via combined rectangle selection
                points=[],  # No points for rectangle-selected objects
                mask=final_mask,
                color=cat.color_rgb,
                label_position=self.label_position
            )
            
            # Add to category using existing _add_element method
            self._add_element(elem)
        
        exclusion_count = len(exclusion_masks)
        if exclusion_count > 0:
            self.status_var.set(f"Created combined {cat_name} object with {exclusion_count} exclusion region(s)")
        else:
            self.status_var.set(f"Created combined {cat_name} object from {len(selected_masks)} selections")
    
    def _show_rectangle_selection_dialog(self, page: PageTab, cat_name: str, 
                                        detected_masks: List[np.ndarray],
                                        x_min: int, y_min: int, x_max: int, y_max: int):
        """Show dialog for selecting which detected objects to create."""
        from replan.desktop.dialogs import RectangleSelectionDialog
        
        # Check which masks are leader lines (for highlighting in dialog)
        leader_flags = []
        for mask in detected_masks:
            is_leader = self._is_leader_line(page, mask)
            leader_flags.append(is_leader)
        
        # Get working image (respects category visibility) for dialog preview
        working_image = self._get_working_image(page)
        
        dialog = RectangleSelectionDialog(
            self.root, page, detected_masks, cat_name, self.theme,
            x_min, y_min, x_max, y_max, leader_flags=leader_flags,
            working_image=working_image
        )
        
        if dialog.result:
            if dialog.create_combined:
                # Create a single combined object from all selected masks
                self._create_combined_object_from_masks(page, cat_name, detected_masks, dialog.result)
                self.status_var.set(f"Created 1 combined {cat_name} object from {len(dialog.result)} selections")
            else:
                # Create separate objects for each selected mask
                for idx in dialog.result:
                    if 0 <= idx < len(detected_masks):
                        self._create_object_from_mask(page, cat_name, detected_masks[idx])
                
                self.status_var.set(f"Created {len(dialog.result)} {cat_name} object(s)")
            self._update_display()
    
    # Tree management
    def _save_tree_expansion_state(self) -> dict:
        """Save which categories/nodes are expanded in the tree."""
        expanded_items = set()
        if hasattr(self, 'tree_grouping_var') and self.tree_grouping_var.get() == "category":
            for item in self.object_tree.get_children():
                if item.startswith("cat_"):
                    if self.object_tree.item(item, "open"):
                        expanded_items.add(item)
                # Also check object nodes that might be expanded
                for child in self.object_tree.get_children(item):
                    if self.object_tree.item(child, "open"):
                        expanded_items.add(child)
        return {'expanded_items': expanded_items}
    
    def _restore_tree_expansion_state(self, state: dict):
        """Restore which categories/nodes are expanded in the tree."""
        if not state or 'expanded_items' not in state:
            return
        expanded_items = state.get('expanded_items', set())
        if hasattr(self, 'tree_grouping_var') and self.tree_grouping_var.get() == "category":
            for item in self.object_tree.get_children():
                if item.startswith("cat_"):
                    if item in expanded_items:
                        self.object_tree.item(item, open=True)
                    else:
                        self.object_tree.item(item, open=False)
                # Also restore object node expansion
                for child in self.object_tree.get_children(item):
                    if child in expanded_items:
                        self.object_tree.item(child, open=True)
    
    def _update_tree(self, preserve_state: bool = True, select_object_id: Optional[str] = None):
        """Full tree rebuild - shows ALL objects across all pages."""
        # Save expansion state if requested
        tree_state = None
        if preserve_state:
            tree_state = self._save_tree_expansion_state()
        
        self.object_tree.delete(*self.object_tree.get_children())
        
        # Update mark_text, mark_hatch, and mark_line counts
        if hasattr(self, 'mark_text_count_label'):
            mark_text_count = sum(1 for o in self.all_objects if o.category == "mark_text")
            self.mark_text_count_label.config(text=f"Mark Text: {mark_text_count}")
        
        if hasattr(self, 'mark_hatch_count_label'):
            mark_hatch_count = sum(1 for o in self.all_objects if o.category == "mark_hatch")
            self.mark_hatch_count_label.config(text=f"Mark Hatch: {mark_hatch_count}")
        
        if hasattr(self, 'mark_line_count_label'):
            mark_line_count = sum(1 for o in self.all_objects if o.category == "mark_line")
            self.mark_line_count_label.config(text=f"Mark Line: {mark_line_count}")
        
        grouping = self.tree_grouping_var.get() if hasattr(self, 'tree_grouping_var') else "category"
        
        if grouping == "none":
            # Flat list - all objects
            for obj in self.all_objects:
                self._add_tree_item(obj)
        elif grouping == "category":
            # Group by category
            categories_used = {}
            for obj in self.all_objects:
                cat_name = obj.category or "Uncategorized"
                if cat_name not in categories_used:
                    categories_used[cat_name] = []
                categories_used[cat_name].append(obj)
            
            for cat_name in sorted(categories_used.keys()):
                icon = self._get_tree_icon(cat_name)
                # Check if this category should be expanded (from saved state)
                cat_node_id = f"cat_{cat_name}"
                should_expand = tree_state and cat_node_id in tree_state.get('expanded_items', set())
                cat_node = self.object_tree.insert("", "end", iid=cat_node_id, 
                                                   text=f"📁 {cat_name} ({len(categories_used[cat_name])})",
                                                   image=icon, open=should_expand)
                for obj in categories_used[cat_name]:
                    self._add_tree_item(obj, parent=cat_node)
        elif grouping == "view":
            # Group by view type - each instance under its own view
            # Structure: view -> (obj, instance) pairs
            views_used = {}
            
            for obj in self.all_objects:
                for inst in obj.instances:
                    # Get view from instance attributes or view_type
                    view_name = inst.attributes.view or inst.view_type or ""
                    if not view_name:
                        view_name = "Unassigned"
                    
                    if view_name not in views_used:
                        views_used[view_name] = []
                    views_used[view_name].append((obj, inst))
            
            # Sort views with "Unassigned" last
            sorted_views = sorted([v for v in views_used.keys() if v != "Unassigned"])
            if "Unassigned" in views_used:
                sorted_views.append("Unassigned")
            
            for view_name in sorted_views:
                items = views_used[view_name]
                view_node = self.object_tree.insert("", "end", iid=f"view_{view_name}",
                                                    text=f"👁 {view_name} ({len(items)})",
                                                    open=True)
                
                for obj, inst in items:
                    icon = self._get_tree_icon(obj.category)
                    # Show object name with instance number if multiple instances
                    if len(obj.instances) > 1:
                        label = f"{obj.name} [Inst {inst.instance_num}]"
                    else:
                        label = obj.name
                    
                    # Create unique ID combining object and instance
                    item_id = f"vi_{obj.object_id}_{inst.instance_id}"
                    
                    if len(inst.elements) == 1:
                        self.object_tree.insert(view_node, "end", iid=item_id, text=label, image=icon)
                    else:
                        node = self.object_tree.insert(view_node, "end", iid=item_id,
                                                       text=f"{label} ({len(inst.elements)} elem)", 
                                                       image=icon, open=False)
                        for i, elem in enumerate(inst.elements):
                            self.object_tree.insert(node, "end", iid=f"ve_{elem.element_id}", 
                                                    text=f"├ element {i+1}")
        
        # Restore expansion state if provided
        if preserve_state and tree_state:
            self._restore_tree_expansion_state(tree_state)
        
        # Select the specified object if provided
        if select_object_id:
            item_id = f"o_{select_object_id}"
            if self.object_tree.exists(item_id):
                self.object_tree.selection_set(item_id)
                self.object_tree.see(item_id)
                # Also expand parent category if grouped by category
                if grouping == "category":
                    parent = self.object_tree.parent(item_id)
                    if parent and parent.startswith("cat_"):
                        self.object_tree.item(parent, open=True)
    
    def _get_tree_icon(self, category: str):
        """Get or create icon for a category."""
        cat = self.categories.get(category)
        if cat:
            key = f"{cat.color_rgb[0]}_{cat.color_rgb[1]}_{cat.color_rgb[2]}"
            if key not in self.tree_icons:
                img = Image.new('RGB', (12, 12), cat.color_rgb)
                ImageDraw.Draw(img).rectangle([0, 0, 11, 11], outline=(0, 0, 0))
                self.tree_icons[key] = ImageTk.PhotoImage(img)
            return self.tree_icons[key]
        return ""
    
    def _add_tree_item(self, obj: SegmentedObject, parent: str = ""):
        """Add a single object to the tree (incremental)."""
        grouping = self.tree_grouping_var.get() if hasattr(self, 'tree_grouping_var') else "none"
        icon = self._get_tree_icon(obj.category)
        
        # Handle grouping modes
        if grouping == "category" and not parent:
            # Ensure category group exists and add under it
            parent = self._ensure_category_group(obj.category)
        elif grouping == "view" and not parent:
            # View grouping needs special handling - add to _update_tree instead
            # For now, do a full rebuild
            self._update_tree()
            return
        
        parent_node = parent if parent else ""
        
        if obj.is_simple:
            self.object_tree.insert(parent_node, "end", iid=f"o_{obj.object_id}", text=obj.name, image=icon)
        elif not obj.has_multiple_instances:
            node = self.object_tree.insert(parent_node, "end", iid=f"o_{obj.object_id}",
                                           text=f"{obj.name} ({obj.element_count})", image=icon, open=False)
            for i, elem in enumerate(obj.instances[0].elements):
                self.object_tree.insert(node, "end", iid=f"e_{elem.element_id}", text=f"├ element {i+1}")
        else:
            node = self.object_tree.insert(parent_node, "end", iid=f"o_{obj.object_id}",
                                           text=f"{obj.name} ({len(obj.instances)} inst)", image=icon, open=False)
            for inst in obj.instances:
                inode = self.object_tree.insert(node, "end", iid=f"i_{inst.instance_id}",
                                                text=f"Instance {inst.instance_num}", open=False)
                for i, elem in enumerate(inst.elements):
                    self.object_tree.insert(inode, "end", iid=f"e_{elem.element_id}", text=f"├ elem {i+1}")
        
        # Update category group count if grouped by category
        if grouping == "category":
            self._update_category_group_count(obj.category)
    
    def _ensure_category_group(self, category: str) -> str:
        """Ensure category group exists in tree and return its ID."""
        group_id = f"cat_{category}"
        cat_name = category or "Uncategorized"
        
        # Check if group already exists
        if not self.object_tree.exists(group_id):
            icon = self._get_tree_icon(category)
            self.object_tree.insert("", "end", iid=group_id, 
                                   text=f"📁 {cat_name} (0)", image=icon, open=True)
        return group_id
    
    def _update_category_group_count(self, category: str):
        """Update the count in a category group header."""
        group_id = f"cat_{category}"
        cat_name = category or "Uncategorized"
        
        if self.object_tree.exists(group_id):
            # Count children
            children = self.object_tree.get_children(group_id)
            count = len(children)
            icon = self._get_tree_icon(category)
            self.object_tree.item(group_id, text=f"📁 {cat_name} ({count})", image=icon)
    
    def _update_tree_item(self, obj: SegmentedObject):
        """Update a single object in the tree (incremental)."""
        grouping = self.tree_grouping_var.get() if hasattr(self, 'tree_grouping_var') else "none"
        
        # For view grouping, do full rebuild (view can change)
        if grouping == "view":
            self._update_tree()
            return
        
        # Remove old item
        try:
            self.object_tree.delete(f"o_{obj.object_id}")
        except:
            pass
        
        # Determine parent for grouped modes
        parent = ""
        if grouping == "category":
            parent = self._ensure_category_group(obj.category)
        
        # Re-add with updated state
        self._add_tree_item(obj, parent=parent)
    
    def _remove_tree_item(self, object_id: str):
        """Remove a single object from the tree."""
        grouping = self.tree_grouping_var.get() if hasattr(self, 'tree_grouping_var') else "none"
        
        # Find the object to get its category before deletion
        category = None
        for obj in self.all_objects:
            if obj.object_id == object_id:
                category = obj.category
                break
        
        try:
            self.object_tree.delete(f"o_{object_id}")
        except:
            pass
        
        # Update category group count
        if grouping == "category" and category:
            self._update_category_group_count(category)
            # Remove empty category group
            group_id = f"cat_{category}"
            if self.object_tree.exists(group_id):
                if not self.object_tree.get_children(group_id):
                    self.object_tree.delete(group_id)
    
    def _on_tree_select(self, event):
        selection = self.object_tree.selection()
        self.selected_object_ids.clear()
        self.selected_instance_ids.clear()
        self.selected_element_ids.clear()
        
        target_page_id = None  # Page to switch to
        
        # Track what's explicitly selected
        for item in selection:
            if item.startswith("o_"):
                self.selected_object_ids.add(item[2:])
            elif item.startswith("i_"):
                self.selected_instance_ids.add(item[2:])
            elif item.startswith("e_"):
                self.selected_element_ids.add(item[2:])
            elif item.startswith("vi_"):
                # View-grouped instance: vi_objid_instid
                parts = item[3:].split("_", 1)
                if len(parts) == 2:
                    self.selected_object_ids.add(parts[0])
                    self.selected_instance_ids.add(parts[1])
            elif item.startswith("ve_"):
                # View-grouped element: ve_elemid
                self.selected_element_ids.add(item[3:])
            elif item.startswith("cat_") or item.startswith("view_"):
                # Group header - select all children
                pass  # Could expand to select all in group
        
        # Only auto-switch pages if the checkbox is enabled
        if getattr(self, 'auto_show_image_var', None) and self.auto_show_image_var.get():
            # Determine which page to switch to based on selection
            target_page_id = self._get_page_for_selection()
            if target_page_id and target_page_id != self.current_page_id:
                self._switch_to_page(target_page_id)
        
        # Always update display when selection changes (for highlighting)
        self._update_display()
        
        # Update current view selector based on selection
        self._update_view_from_selection()
    
    def _on_view_changed(self, event=None):
        """Handle current view combo change."""
        # Just store the value - it will be used when creating new objects
        pass
    
    def _update_view_from_selection(self):
        """Update current view combo based on selected object."""
        if not self.selected_object_ids:
            return
        
        # Get the first selected object
        obj_id = next(iter(self.selected_object_ids))
        obj = self._get_object_by_id(obj_id)
        if not obj:
            return
        
        # Check if all instances have the same view
        views = set()
        for inst in obj.instances:
            view = getattr(inst, 'view_type', '') or inst.attributes.view if hasattr(inst, 'attributes') else ''
            views.add(view)
        
        # Only update if there's a single consistent view
        if len(views) == 1:
            view = views.pop()
            if view and hasattr(self, 'current_view_var'):
                self.current_view_var.set(view)
    
    def _get_page_for_selection(self) -> Optional[str]:
        """
        Determine which page the selected items belong to.
        Returns None if selection spans multiple pages or has no page.
        """
        page_ids = set()
        
        # Check selected instances
        for inst_id in self.selected_instance_ids:
            for obj in self.all_objects:
                for inst in obj.instances:
                    if inst.instance_id == inst_id and inst.page_id:
                        page_ids.add(inst.page_id)
        
        # Check selected elements
        for elem_id in self.selected_element_ids:
            for obj in self.all_objects:
                for inst in obj.instances:
                    for elem in inst.elements:
                        if elem.element_id == elem_id and inst.page_id:
                            page_ids.add(inst.page_id)
        
        # Check selected objects - use first instance's page
        for obj_id in self.selected_object_ids:
            obj = self._get_object_by_id(obj_id)
            if obj and obj.instances:
                # Check if all instances are on same page
                obj_pages = set(inst.page_id for inst in obj.instances if inst.page_id)
                if len(obj_pages) == 1:
                    page_ids.update(obj_pages)
                elif len(obj_pages) > 1:
                    # Object spans multiple pages - don't switch
                    return None
        
        # Return page if exactly one
        if len(page_ids) == 1:
            return page_ids.pop()
        return None
    
    def _switch_to_page(self, page_id: str):
        """Switch to a specific page tab."""
        if page_id in self.pages:
            page = self.pages[page_id]
            if hasattr(page, 'frame'):
                self.notebook.select(page.frame)
                self.current_page_id = page_id
                # Invalidate cache when switching pages (different page/image)
                self._invalidate_working_image_cache()
    
    def _get_object_by_id(self, obj_id: str) -> Optional[SegmentedObject]:
        """Get object by ID from global list."""
        for obj in self.all_objects:
            if obj.object_id == obj_id:
                return obj
        return None
    
    def _get_element_at_point(self, page_id: str, x: int, y: int):
        """Find element at point on a specific page."""
        for obj in self.all_objects:
            for inst in obj.instances:
                if inst.page_id == page_id:
                    for elem in inst.elements:
                        if elem.mask is not None and elem.mask[y, x] > 0:
                            return (obj, inst, elem)
        return None
    
    def _get_selected_object_for_adding(self) -> Optional[str]:
        """Get the object ID to add elements to (from any selection type)."""
        page = self._get_current_page()
        if not page:
            return None
        
        # Direct object selection
        if self.selected_object_ids:
            return next(iter(self.selected_object_ids))
        
        # Instance selected - find parent object
        if self.selected_instance_ids:
            inst_id = next(iter(self.selected_instance_ids))
            for obj in self.all_objects:
                for inst in obj.instances:
                    if inst.instance_id == inst_id:
                        return obj.object_id
        
        # Element selected - find parent object
        if self.selected_element_ids:
            elem_id = next(iter(self.selected_element_ids))
            for obj in self.all_objects:
                for inst in obj.instances:
                    for elem in inst.elements:
                        if elem.element_id == elem_id:
                            return obj.object_id
        
        return None
    
    def _on_tree_click(self, event):
        """Handle click on tree - deselect if clicking empty area."""
        item = self.object_tree.identify_row(event.y)
        if not item:
            # Clicked on empty area - deselect all
            self.object_tree.selection_remove(*self.object_tree.selection())
            self.selected_object_ids.clear()
            self.selected_instance_ids.clear()
            self.selected_element_ids.clear()
            self._update_display()
            self.status_var.set("Deselected - new elements will create new objects")
    
    def _on_tree_right_click(self, event):
        """Show context menu on right-click."""
        item = self.object_tree.identify_row(event.y)
        
        # Select the item under cursor if not already selected
        if item and item not in self.object_tree.selection():
            self.object_tree.selection_set(item)
            self._on_tree_select(None)
        
        # Create context menu
        menu = tk.Menu(self.root, tearoff=0, bg=self.theme["menu_bg"], 
                      fg=self.theme["menu_fg"],
                      activebackground=self.theme["menu_hover"],
                      activeforeground=self.theme["selection_fg"])
        
        # Determine what's selected
        num_objects = len(self.selected_object_ids)
        num_instances = len(self.selected_instance_ids)
        num_elements = len(self.selected_element_ids)
        
        # Check if selected objects are same category (for merge)
        same_category = False
        if num_objects >= 2:
            categories = set()
            for obj_id in self.selected_object_ids:
                obj = self._get_object_by_id(obj_id)
                if obj:
                    categories.add(obj.category)
            same_category = len(categories) == 1
        
        # Object actions
        if num_objects >= 1:
            menu.add_command(label="Add Instance", command=self._add_instance,
                           state="normal" if num_objects == 1 else "disabled")
            menu.add_command(label="Duplicate", command=self._duplicate_object,
                           state="normal" if num_objects == 1 else "disabled")
            menu.add_command(label="Move", command=self._start_move_objects,
                           state="normal" if num_objects >= 1 else "disabled")
            menu.add_command(label="Move to Page", command=self._move_object_to_page,
                           state="normal" if num_objects >= 1 else "disabled")
            menu.add_command(label="Rename", command=lambda: self._start_inline_edit(f"o_{next(iter(self.selected_object_ids))}") if self.selected_object_ids else None,
                           state="normal" if num_objects == 1 else "disabled")
            menu.add_command(label="Edit Attributes", command=self._edit_attributes)
            menu.add_command(label="Draw Perimeter", command=self._draw_perimeter,
                           state="normal" if num_objects == 1 else "disabled")
            menu.add_separator()
            
            # Merge options
            menu.add_command(label="Merge → Instances", command=self._merge_as_instances,
                           state="normal" if num_objects >= 2 and same_category else "disabled")
            menu.add_command(label="Merge → Group", command=self._merge_as_group,
                           state="normal" if num_objects >= 2 and same_category else "disabled")
            
            # Separate instances (if one object with multiple instances selected)
            if num_objects == 1 and num_instances >= 2:
                menu.add_command(label="Separate Instances", command=self._separate_instances)
            
            menu.add_separator()
        
        # Instance actions (when instance is selected but not through object menu)
        elif num_instances >= 1 and num_objects == 0:
            menu.add_command(label="Move", command=self._start_move_objects)
            menu.add_command(label="Move to Page", command=self._move_instance_to_page)
            menu.add_command(label="Edit Attributes", command=self._edit_attributes)
            menu.add_separator()
        
        # Element actions
        if num_elements >= 1:
            if num_objects == 0 and num_instances == 0:  # Only elements selected
                menu.add_command(label="Move", command=self._start_move_objects)
                menu.add_separator()
        
        # Expand/collapse
        if item:
            menu.add_command(label="Expand", command=lambda: self.object_tree.item(item, open=True))
            menu.add_command(label="Collapse", command=lambda: self.object_tree.item(item, open=False))
            menu.add_separator()
        
        menu.add_command(label="Expand All", command=self._expand_all_tree)
        menu.add_command(label="Collapse All", command=self._collapse_all_tree)
        
        if num_objects >= 1 or num_instances >= 1 or num_elements >= 1:
            menu.add_separator()
            menu.add_command(label="Delete", command=self._delete_selected)
        
        # Debug option
        if num_objects >= 1:
            menu.add_separator()
            menu.add_command(label="Debug Redraw", command=self._debug_redraw_selected)
        
        # Show menu
        menu.tk_popup(event.x_root, event.y_root)
    
    def _expand_all_tree(self):
        """Expand all tree items."""
        def expand_children(item):
            self.object_tree.item(item, open=True)
            for child in self.object_tree.get_children(item):
                expand_children(child)
        
        for item in self.object_tree.get_children():
            expand_children(item)
    
    def _collapse_all_tree(self):
        """Collapse all tree items."""
        def collapse_children(item):
            for child in self.object_tree.get_children(item):
                collapse_children(child)
            self.object_tree.item(item, open=False)
        
        for item in self.object_tree.get_children():
            collapse_children(item)
    
    def _debug_redraw_selected(self):
        """Debug: Redraw selected object with detailed logging."""
        if not self.selected_object_ids:
            print("DEBUG: No object selected")
            return
        
        obj_id = next(iter(self.selected_object_ids))
        obj = self._get_object_by_id(obj_id)
        if not obj:
            print(f"DEBUG: Object {obj_id} not found")
            return
        
        page = self._get_current_page()
        if not page:
            print("DEBUG: No current page")
            return
        
        print("=" * 60)
        print(f"DEBUG REDRAW: Object '{obj.name}' (ID: {obj_id})")
        print("=" * 60)
        
        # 1. Object info
        print(f"  Category: {obj.category}")
        print(f"  Instances: {len(obj.instances)}")
        
        total_mask_pixels = 0
        for i, inst in enumerate(obj.instances):
            print(f"  Instance {i+1}: {len(inst.elements)} elements")
            for j, elem in enumerate(inst.elements):
                if elem.mask is not None:
                    mask_pixels = np.sum(elem.mask > 0)
                    total_mask_pixels += mask_pixels
                    print(f"    Element {j+1}: mode={elem.mode}, mask={elem.mask.shape}, pixels={mask_pixels}")
                else:
                    print(f"    Element {j+1}: mode={elem.mode}, mask=None")
        
        print(f"  Total object mask pixels: {total_mask_pixels}")
        
        # 2. Page state
        h, w = page.original_image.shape[:2]
        print(f"\n  Page: {page.display_name}")
        print(f"  Image size: {w}x{h}")
        print(f"  hide_text: {getattr(page, 'hide_text', False)}")
        print(f"  hide_hatching: {getattr(page, 'hide_hatching', False)}")
        
        # 3. Text mask info
        text_mask = getattr(page, 'combined_text_mask', None)
        if text_mask is not None:
            text_pixels = np.sum(text_mask > 0)
            print(f"\n  Text mask: shape={text_mask.shape}, pixels={text_pixels}")
            
            # Check overlap between object mask and text mask
            obj_mask = np.zeros((h, w), dtype=np.uint8)
            for inst in obj.instances:
                for elem in inst.elements:
                    if elem.mask is not None and elem.mask.shape == (h, w):
                        obj_mask = np.maximum(obj_mask, elem.mask)
            
            text_overlap = np.sum((obj_mask > 0) & (text_mask > 0))
            print(f"  Overlap (object mask AND text mask): {text_overlap} pixels")
            
            if text_overlap > 0:
                print(f"  *** WARNING: {text_overlap} pixels of text are INSIDE the object! ***")
                print(f"      These pixels should be WHITE in base image before overlay")
        else:
            print(f"\n  Text mask: None (hide_text may be False)")
        
        # 4. Hatching mask info
        hatch_mask = getattr(page, 'combined_hatch_mask', None)
        if hatch_mask is not None:
            hatch_pixels = np.sum(hatch_mask > 0)
            print(f"\n  Hatch mask: shape={hatch_mask.shape}, pixels={hatch_pixels}")
            
            # Check hatch overlap
            hatch_overlap = np.sum((obj_mask > 0) & (hatch_mask > 0))
            print(f"  Overlap (object mask AND hatch mask): {hatch_overlap} pixels")
            
            if hatch_overlap > 0:
                print(f"  *** WARNING: {hatch_overlap} pixels of hatch are INSIDE the object! ***")
        
        # 5. Force re-render
        print(f"\n  Invalidating cache and forcing re-render...")
        self.renderer.invalidate_cache()
        
        # Get masks for render
        render_text_mask = text_mask if getattr(page, 'hide_text', False) else None
        render_hatch_mask = hatch_mask if getattr(page, 'hide_hatching', False) else None
        
        print(f"  Rendering with:")
        print(f"    text_mask: {render_text_mask is not None} ({np.sum(render_text_mask > 0) if render_text_mask is not None else 0} pixels)")
        print(f"    hatch_mask: {render_hatch_mask is not None} ({np.sum(render_hatch_mask > 0) if render_hatch_mask is not None else 0} pixels)")
        
        self._update_display()
        
        # 6. Save debug images
        print(f"\n  Saving debug images...")
        try:
            debug_dir = Path("debug_output")
            debug_dir.mkdir(exist_ok=True)
            
            # Save original
            cv2.imwrite(str(debug_dir / "1_original.png"), page.original_image)
            
            # Save text mask
            if text_mask is not None:
                cv2.imwrite(str(debug_dir / "2_text_mask.png"), text_mask)
            
            # Save object mask
            obj_mask = np.zeros((h, w), dtype=np.uint8)
            for inst in obj.instances:
                for elem in inst.elements:
                    if elem.mask is not None and elem.mask.shape == (h, w):
                        obj_mask = np.maximum(obj_mask, elem.mask)
            cv2.imwrite(str(debug_dir / "3_object_mask.png"), obj_mask)
            
            # Save base image with text hidden
            base_with_text_hidden = page.original_image.copy()
            if text_mask is not None and getattr(page, 'hide_text', False):
                base_with_text_hidden[text_mask > 0] = [255, 255, 255]
            cv2.imwrite(str(debug_dir / "4_base_text_hidden.png"), base_with_text_hidden)
            
            # Save overlap visualization
            overlap_vis = page.original_image.copy()
            if text_mask is not None:
                # Highlight text mask in red
                overlap_vis[text_mask > 0] = [0, 0, 255]
            # Highlight object mask in green (over red where overlap)
            overlap_vis[obj_mask > 0, 1] = 255
            cv2.imwrite(str(debug_dir / "5_overlap_visualization.png"), overlap_vis)
            
            print(f"  Debug images saved to: {debug_dir.absolute()}")
        except Exception as e:
            print(f"  Error saving debug images: {e}")
        
        print("=" * 60)
        print("DEBUG REDRAW COMPLETE")
        print("=" * 60)
    
    def _separate_instances(self):
        """Separate selected instances into individual objects."""
        if not self.selected_object_ids or len(self.selected_instance_ids) < 2:
            return
        
        obj_id = next(iter(self.selected_object_ids))
        obj = self._get_object_by_id(obj_id)
        if not obj:
            return
        
        # Find instances to separate
        instances_to_separate = []
        for inst in obj.instances:
            if inst.instance_id in self.selected_instance_ids:
                instances_to_separate.append(inst)
        
        if len(instances_to_separate) < 2:
            return
        
        # Keep first instance in original object, create new objects for rest
        for i, inst in enumerate(instances_to_separate[1:], start=1):
            # Remove from original
            obj.instances.remove(inst)
            
            # Create new object
            new_obj = SegmentedObject(
                name=f"{obj.name}_{i}",
                category=obj.category
            )
            inst.instance_num = 1
            new_obj.instances.append(inst)
            self.all_objects.append(new_obj)
        
        # Renumber remaining instances
        self._renumber_instances(obj)
        
        self.workspace_modified = True
        self.renderer.invalidate_cache()
        self._update_tree()
        self._update_display()
        self.status_var.set(f"Separated {len(instances_to_separate)} instances")
    
    def _on_tree_double_click(self, event):
        """Handle double-click on tree - start inline editing of object name."""
        item = self.object_tree.identify_row(event.y)
        if not item:
            return
        
        # Only allow editing object names (items starting with 'o_')
        if item.startswith("o_"):
            self._start_inline_edit(item)
        else:
            # For instances/elements, open attributes dialog
            self._edit_attributes()
    
    def _start_inline_edit(self, item_id: str):
        """Start inline editing of tree item."""
        if not item_id.startswith("o_"):
            return
            
        obj_id = item_id[2:]  # Remove 'o_' prefix
        obj = self._get_object_by_id(obj_id)
        if not obj:
            return
        
        # Ensure item is visible
        self.object_tree.see(item_id)
        self.object_tree.update_idletasks()
        
        # Get item bounding box
        bbox = self.object_tree.bbox(item_id)
        if not bbox:
            # Try again after a short delay
            self.root.after(100, lambda: self._do_inline_edit(item_id, obj))
            return
        
        self._do_inline_edit(item_id, obj, bbox)
    
    def _do_inline_edit(self, item_id: str, obj, bbox=None):
        """Actually perform inline editing."""
        if bbox is None:
            bbox = self.object_tree.bbox(item_id)
            if not bbox:
                return
        
        x, y, width, height = bbox
        
        # Destroy any existing edit entry
        if hasattr(self, '_inline_entry') and self._inline_entry:
            try:
                self._inline_entry.destroy()
            except:
                pass
        
        # Create entry widget for editing
        self._inline_entry = tk.Entry(self.object_tree, font=("Segoe UI", 9),
                                      bg=self.theme.get("input_bg", "#3c3c3c"),
                                      fg=self.theme.get("input_fg", "#cccccc"),
                                      insertbackground=self.theme.get("fg", "#cccccc"),
                                      relief="solid", borderwidth=1)
        self._inline_entry.insert(0, obj.name)
        self._inline_entry.select_range(0, tk.END)
        self._inline_entry.place(x=x + 20, y=y, width=max(width - 25, 100), height=height)
        self._inline_entry.focus_set()
        
        def finish_edit(event=None):
            if not hasattr(self, '_inline_entry') or not self._inline_entry:
                return
            try:
                new_name = self._inline_entry.get().strip()
                if new_name and new_name != obj.name:
                    obj.name = new_name
                    self.workspace_modified = True
                    self.renderer.invalidate_cache()
                    self._update_tree()
                    self._update_display()
                self._inline_entry.destroy()
                self._inline_entry = None
            except:
                pass
        
        def cancel_edit(event=None):
            if hasattr(self, '_inline_entry') and self._inline_entry:
                try:
                    self._inline_entry.destroy()
                    self._inline_entry = None
                except:
                    pass
        
        self._inline_entry.bind("<Return>", finish_edit)
        self._inline_entry.bind("<Escape>", cancel_edit)
        self._inline_entry.bind("<FocusOut>", finish_edit)
    
    # Object operations
    def _rename_object(self):
        if not self.selected_object_ids:
            return
        page = self._get_current_page()
        if not page:
            return
        
        obj_id = next(iter(self.selected_object_ids))
        obj = page.get_object_by_id(obj_id)
        if not obj:
            return
        
        name = simpledialog.askstring("Rename", f"New name:", initialvalue=obj.name, parent=self.root)
        if name:
            obj.name = name
            self.workspace_modified = True
            self._update_tree_item(obj)  # Incremental update
    
    def _add_instance(self):
        """Add a new empty instance to the selected object without prompting."""
        if not self.selected_object_ids:
            messagebox.showinfo("Info", "Select an object first")
            return
        page = self._get_current_page()
        if not page:
            return
        
        obj_id = next(iter(self.selected_object_ids))
        obj = self._get_object_by_id(obj_id)
        if not obj:
            return
        
        # Change category selector to match the object's category
        if obj.category and obj.category in self.categories:
            self.category_var.set(obj.category)
            # Also update mode if needed
            cat = self.categories[obj.category]
            if cat.selection_mode and cat.selection_mode != "select":
                self._set_mode(cat.selection_mode)
        
        # Renumber instances to ensure sequential numbering
        self._renumber_instances(obj)
        
        # Add instance silently - no dialog needed
        inst = obj.add_instance("", page.tab_id)
        self.workspace_modified = True
        # Note: empty instance doesn't need cache invalidate - no visual change
        self._update_tree_item(obj)  # Incremental update
        
        # Keep the object selected so subsequent elements go to this new instance
        self.selected_object_ids = {obj.object_id}
        self.selected_instance_ids = {inst.instance_id}
        self.selected_element_ids.clear()
        
        # Select in tree view
        tree_id = f"o_{obj.object_id}"
        if self.object_tree.exists(tree_id):
            self.object_tree.selection_set(tree_id)
        
        self._update_display()
        self.status_var.set(f"Instance {inst.instance_num} added to {obj.name} - now add elements")
    
    def _renumber_instances(self, obj: SegmentedObject):
        """Ensure instances have sequential numbering starting from 1."""
        for idx, inst in enumerate(obj.instances):
            inst.instance_num = idx + 1
    
    def _move_object_to_page(self):
        """Move selected object(s) to a different page."""
        if not self.selected_object_ids:
            return
        
        current_page = self._get_current_page()
        if not current_page:
            messagebox.showwarning("No Page", "No current page selected.")
            return
        
        # Show page selection dialog
        dialog = PageSelectionDialog(self.root, self.pages, current_page.tab_id, self.theme)
        
        if dialog.result is None:
            # User cancelled
            return
        
        target_page_id = dialog.result
        target_page = self.pages.get(target_page_id)
        
        if not target_page:
            messagebox.showerror("Error", "Target page not found.")
            return
        
        if target_page_id == current_page.tab_id:
            messagebox.showinfo("Info", "Object is already on this page.")
            return
        
        # Get dimensions for both pages to handle resizing if needed
        src_h, src_w = current_page.original_image.shape[:2]
        dst_h, dst_w = target_page.original_image.shape[:2]
        needs_resize = (src_h != dst_h) or (src_w != dst_w)
        
        # Move instances of selected objects to the target page
        moved_count = 0
        for obj_id in self.selected_object_ids:
            obj = self._get_object_by_id(obj_id)
            if not obj:
                continue
            
            # Find instances on the current page and move them to target page
            for inst in obj.instances:
                if inst.page_id == current_page.tab_id:
                    # Update page ID
                    inst.page_id = target_page_id
                    
                    # Resize masks if pages have different dimensions
                    if needs_resize:
                        for elem in inst.elements:
                            if elem.mask is not None and elem.mask.shape == (src_h, src_w):
                                # Resize mask to fit target page
                                elem.mask = cv2.resize(elem.mask, (dst_w, dst_h), interpolation=cv2.INTER_NEAREST)
                            # Also adjust points if they exist
                            if elem.points:
                                scale_x = dst_w / src_w
                                scale_y = dst_h / src_h
                                elem.points = [(int(px * scale_x), int(py * scale_y)) for px, py in elem.points]
                    
                    moved_count += 1
        
        if moved_count > 0:
            self.workspace_modified = True
            self.renderer.invalidate_cache()
            
            # Update tree to reflect changes
            self._update_tree()
            
            # Switch to target page to show moved objects
            self._switch_to_page(target_page_id)
            
            # Update display after page switch
            self._update_display()
            
            # Start move mode so user can position the moved objects
            # Keep the same selection (objects are still selected)
            self._start_move_objects()
            self.status_var.set(f"Moved {moved_count} instance(s) to {target_page.display_name} - Click and drag to position, or press Escape to cancel")
        else:
            messagebox.showinfo("Info", "No instances found on current page to move.")
    
    def _move_instance_to_page(self):
        """Move selected instance(s) to a different page."""
        if not self.selected_instance_ids:
            return
        
        current_page = self._get_current_page()
        if not current_page:
            messagebox.showwarning("No Page", "No current page selected.")
            return
        
        # Show page selection dialog
        dialog = PageSelectionDialog(self.root, self.pages, current_page.tab_id, self.theme)
        
        if dialog.result is None:
            # User cancelled
            return
        
        target_page_id = dialog.result
        target_page = self.pages.get(target_page_id)
        
        if not target_page:
            messagebox.showerror("Error", "Target page not found.")
            return
        
        if target_page_id == current_page.tab_id:
            messagebox.showinfo("Info", "Instance is already on this page.")
            return
        
        # Get dimensions for both pages to handle resizing if needed
        src_h, src_w = current_page.original_image.shape[:2]
        dst_h, dst_w = target_page.original_image.shape[:2]
        needs_resize = (src_h != dst_h) or (src_w != dst_w)
        
        # Move selected instances to the target page
        moved_count = 0
        for inst_id in self.selected_instance_ids:
            for obj in self.all_objects:
                for inst in obj.instances:
                    if inst.instance_id == inst_id and inst.page_id == current_page.tab_id:
                        # Update page ID
                        inst.page_id = target_page_id
                        
                        # Resize masks if pages have different dimensions
                        if needs_resize:
                            for elem in inst.elements:
                                if elem.mask is not None and elem.mask.shape == (src_h, src_w):
                                    # Resize mask to fit target page
                                    elem.mask = cv2.resize(elem.mask, (dst_w, dst_h), interpolation=cv2.INTER_NEAREST)
                                # Also adjust points if they exist
                                if elem.points:
                                    scale_x = dst_w / src_w
                                    scale_y = dst_h / src_h
                                    elem.points = [(int(px * scale_x), int(py * scale_y)) for px, py in elem.points]
                        
                        moved_count += 1
                        break
        
        if moved_count > 0:
            self.workspace_modified = True
            self.renderer.invalidate_cache()
            
            # Update tree to reflect changes
            self._update_tree()
            
            # Switch to target page to show moved instances
            self._switch_to_page(target_page_id)
            
            # Update display after page switch
            self._update_display()
            
            # Start move mode so user can position the moved instances
            # Keep the same selection (instances are still selected)
            self._start_move_objects()
            self.status_var.set(f"Moved {moved_count} instance(s) to {target_page.display_name} - Click and drag to position, or press Escape to cancel")
        else:
            messagebox.showinfo("Info", "No instances found on current page to move.")
    
    def _draw_perimeter(self):
        """Draw a line around the perimeter of the selected object."""
        if not self.selected_object_ids or len(self.selected_object_ids) != 1:
            return
        
        page = self._get_current_page()
        if not page:
            return
        
        obj_id = next(iter(self.selected_object_ids))
        obj = self._get_object_by_id(obj_id)
        if not obj:
            return
        
        h, w = page.original_image.shape[:2]
        
        # Get combined mask of all elements on current page
        combined_mask = np.zeros((h, w), dtype=np.uint8)
        for inst in obj.instances:
            if inst.page_id == page.tab_id:
                for elem in inst.elements:
                    if elem.mask is not None and elem.mask.shape == (h, w):
                        combined_mask = np.maximum(combined_mask, elem.mask)
        
        if np.sum(combined_mask > 0) == 0:
            messagebox.showinfo("Info", "Object has no mask on current page.")
            return
        
        # Find the contour of the mask
        contours, _ = cv2.findContours(combined_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            messagebox.showinfo("Info", "Could not find perimeter contour.")
            return
        
        # Use the largest contour (in case there are multiple)
        largest_contour = max(contours, key=cv2.contourArea)
        
        # Convert contour to points list [(x, y), ...]
        # Contour is in shape (N, 1, 2), we need to reshape to (N, 2) and convert to list
        contour_points = largest_contour.reshape(-1, 2).tolist()
        # Convert from numpy int32 to Python int
        points = [(int(p[0]), int(p[1])) for p in contour_points]
        
        # Calculate average line thickness from category's line elements
        # Look for line elements in the same category
        line_thickness = self.engine.line_thickness  # Default
        thicknesses = []
        
        for other_obj in self.all_objects:
            if other_obj.category == obj.category:
                for other_inst in other_obj.instances:
                    for other_elem in other_inst.elements:
                        # If it's a line element, try to estimate thickness from mask
                        if other_elem.mode in ["line", "polyline"] and other_elem.mask is not None:
                            # Estimate thickness by finding average width of line mask
                            mask = other_elem.mask
                            if mask.shape == (h, w):
                                # Find contours and measure thickness
                                line_contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                                if line_contours:
                                    # Use bounding box width as approximation
                                    x, y, w_box, h_box = cv2.boundingRect(line_contours[0])
                                    # For lines, thickness is usually the smaller dimension
                                    thickness = min(w_box, h_box)
                                    if thickness > 0:
                                        thicknesses.append(thickness)
        
        if thicknesses:
            line_thickness = int(np.mean(thicknesses))
            # Ensure reasonable bounds
            line_thickness = max(1, min(line_thickness, 20))
        
        # Get category color
        cat = self.categories.get(obj.category)
        if not cat:
            return
        
        # Create a line mask for the perimeter that lies INSIDE the object
        # We'll use morphological erosion to create an inner border
        # This ensures the perimeter is visible (drawn on dark object pixels, not white background)
        
        # Ensure minimum thickness of 2 for visibility
        line_thickness = max(2, line_thickness)
        
        # Method: Create inner perimeter by finding the difference between
        # the original mask and an eroded version of it
        erode_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (line_thickness, line_thickness))
        eroded_mask = cv2.erode(combined_mask, erode_kernel, iterations=1)
        
        # The perimeter is the original mask minus the eroded mask
        line_mask = cv2.subtract(combined_mask, eroded_mask)
        
        # Check if perimeter mask has content
        perimeter_pixels = np.sum(line_mask > 0)
        if perimeter_pixels == 0:
            messagebox.showinfo("Info", "Could not create perimeter - object may be too small or thin.")
            return
        
        # Store the points for reference (contour points)
        if len(points) > 2 and points[0] != points[-1]:
            points = points + [points[0]]
        
        # Create a new line element
        elem = SegmentElement(
            category=obj.category,
            mode="perimeter",
            points=points,
            mask=line_mask,
            color=cat.color_rgb,
            label_position=self.label_position
        )
        
        # Add to the last instance on current page, or create new instance if none exists
        target_inst = None
        for inst in obj.instances:
            if inst.page_id == page.tab_id:
                target_inst = inst
                break
        
        if target_inst is None:
            # Create new instance on current page
            target_inst = obj.add_instance("", page.tab_id)
            self._renumber_instances(obj)
        
        # Add element to instance
        target_inst.elements.append(elem)
        
        self.workspace_modified = True
        self.renderer.invalidate_cache()
        self._update_tree_item(obj)
        self._update_display()
        self.status_var.set(f"Added perimeter line to {obj.name}")
    
    def _edit_attributes(self):
        """Edit attributes for selected instance (or first instance of selected object)."""
        page = self._get_current_page()
        if not page:
            return
        
        # Find target instance and object
        target_inst = None
        target_obj = None
        obj_name = ""
        
        # Priority: selected instance > selected object's first instance
        if self.selected_instance_ids:
            inst_id = next(iter(self.selected_instance_ids))
            for obj in self.all_objects:
                for inst in obj.instances:
                    if inst.instance_id == inst_id:
                        target_inst = inst
                        target_obj = obj
                        obj_name = obj.name
                        break
                if target_inst:
                    break
        elif self.selected_object_ids:
            obj_id = next(iter(self.selected_object_ids))
            target_obj = self._get_object_by_id(obj_id)
            if target_obj and target_obj.instances:
                target_inst = target_obj.instances[0]
                obj_name = target_obj.name
        
        if not target_inst or not target_obj:
            messagebox.showinfo("Info", "Select an object or instance first", parent=self.root)
            return
        
        dialog = AttributeDialog(self.root, target_inst, obj_name)
        result = dialog.show()
        if result:
            target_inst.attributes = result
            # Check if name was changed
            if hasattr(dialog, 'new_name') and dialog.new_name and dialog.new_name != target_obj.name:
                target_obj.name = dialog.new_name
                # Invalidate cache since name label will change
                self.renderer.invalidate_cache()
            self.workspace_modified = True
            self._update_tree()
            self._update_display()
    
    def _duplicate_object(self):
        """Create a duplicate of the selected object."""
        if not self.selected_object_ids:
            messagebox.showinfo("Info", "Select an object to duplicate")
            return
        
        page = self._get_current_page()
        if not page:
            return
        
        obj_id = next(iter(self.selected_object_ids))
        obj = self._get_object_by_id(obj_id)
        if not obj:
            messagebox.showwarning("Error", "Selected object not found")
            return
        
        if not obj.instances:
            messagebox.showwarning("Error", "Object has no instances to duplicate")
            return
        
        import copy
        
        # Create new object with copied properties
        new_obj = SegmentedObject(
            name=f"{obj.name}_copy",
            category=obj.category
        )
        
        # Copy all instances
        total_elements = 0
        for inst in obj.instances:
            new_inst = ObjectInstance(
                instance_num=inst.instance_num,
                page_id=inst.page_id,
                view_type=getattr(inst, 'view_type', ''),
                attributes=copy.deepcopy(inst.attributes) if hasattr(inst, 'attributes') and inst.attributes else None
            )
            # Copy elements with new IDs
            for elem in inst.elements:
                new_elem = SegmentElement(
                    category=elem.category,
                    mode=elem.mode,
                    mask=elem.mask.copy() if elem.mask is not None else None,
                    points=elem.points.copy() if elem.points else [],
                    color=elem.color,
                    label_position=elem.label_position
                )
                new_inst.elements.append(new_elem)
                total_elements += 1
            
            # Only add instance if it has elements
            if new_inst.elements:
                new_obj.instances.append(new_inst)
        
        # Only add object if it has instances with elements
        if not new_obj.instances:
            messagebox.showwarning("Error", "Object has no elements to duplicate")
            return
        
        self.all_objects.append(new_obj)
        self.workspace_modified = True
        self.renderer.invalidate_cache()
        self._add_tree_item(new_obj)
        
        # Select the new object
        self.selected_object_ids = {new_obj.object_id}
        self.selected_instance_ids.clear()
        self.selected_element_ids.clear()
        self._update_tree()
        self._update_display()
        
        # Start move mode so user can position the duplicate
        self._start_move_objects()
        self.status_var.set(f"Duplicated {obj.name} - Click and drag to position, or press Escape to cancel")
    
    def _duplicate_selected(self):
        """Duplicate selected objects or elements."""
        if len(self.selected_object_ids) > 0:
            self._duplicate_object()
        elif len(self.selected_element_ids) > 0:
            # Duplicate selected elements as new objects
            self._duplicate_elements()
        elif self.selected_pixel_mask is not None:
            self._duplicate_pixel_selection()
    
    def _duplicate_elements(self):
        """Duplicate selected elements as new objects."""
        if not self.selected_element_ids:
            return
        
        page = self._get_current_page()
        if not page:
            return
        
        # Find all selected elements
        selected_elements = []
        for obj in self.all_objects:
            for inst in obj.instances:
                if inst.page_id == page.tab_id:
                    for elem in inst.elements:
                        if elem.element_id in self.selected_element_ids:
                            selected_elements.append((obj, inst, elem))
        
        if not selected_elements:
            return
        
        # Create new objects for each selected element
        new_objects = []
        for obj, inst, elem in selected_elements:
            # Create new element with copied mask
            new_elem = SegmentElement(
                category=elem.category,
                mode=elem.mode,
                points=elem.points.copy() if elem.points else [],
                mask=elem.mask.copy() if elem.mask is not None else None,
                color=elem.color,
                label_position=elem.label_position
            )
            
            # Create new instance with the element
            new_inst = ObjectInstance(
                instance_num=1,
                page_id=inst.page_id,
                view_type=getattr(inst, 'view_type', ''),
                elements=[new_elem]
            )
            
            # Create new object
            new_obj = SegmentedObject(
                name=f"{obj.name}_copy",
                category=obj.category,
                instances=[new_inst]
            )
            
            new_objects.append(new_obj)
            self.all_objects.append(new_obj)
        
        self.workspace_modified = True
        self.renderer.invalidate_cache()
        for obj in new_objects:
            self._add_tree_item(obj)
        
        # Select the new objects and start move mode
        if new_objects:
            self.selected_object_ids = {obj.object_id for obj in new_objects}
            self.selected_instance_ids.clear()
            self.selected_element_ids.clear()
            self._update_tree()
            self._update_display()
            
            # Start move mode so user can position the duplicates
            self._start_move_objects()
            self.status_var.set(f"Duplicated {len(new_objects)} element(s) - Click and drag to position, or press Escape to cancel")
        else:
            self._update_display()
            self.status_var.set(f"Duplicated {len(new_objects)} element(s)")
    
    # Pixel selection and editing functions
    def _set_pixel_selection(self, mask: np.ndarray):
        """Set the current pixel selection from a mask."""
        page = self._get_current_page()
        if not page:
            return
        
        h, w = page.original_image.shape[:2]
        if mask.shape != (h, w):
            # Resize mask if needed
            mask = cv2.resize(mask.astype(np.uint8), (w, h), interpolation=cv2.INTER_NEAREST)
        
        self.selected_pixel_mask = (mask > 0).astype(np.uint8) * 255
        
        # Calculate bounding box
        ys, xs = np.where(self.selected_pixel_mask > 0)
        if len(xs) > 0:
            self.selected_pixel_bbox = (int(np.min(xs)), int(np.min(ys)), 
                                       int(np.max(xs)) + 1, int(np.max(ys)) + 1)
        else:
            self.selected_pixel_bbox = None
        
        # Clear object selections when pixel selection is active
        self.selected_object_ids.clear()
        self.selected_instance_ids.clear()
        self.selected_element_ids.clear()
        
        self._update_display()
    
    def _clear_pixel_selection(self):
        """Clear the current pixel selection."""
        self.selected_pixel_mask = None
        self.selected_pixel_bbox = None
        self.is_moving_pixels = False
        self.pixel_move_start = None
        self.pixel_move_offset = None
        self._update_display()
    
    def _start_move_pixels(self):
        """Start moving the selected pixels."""
        if self.selected_pixel_mask is None:
            return
        
        self.is_moving_pixels = True
        page = self._get_current_page()
        if page and hasattr(page, 'canvas'):
            page.canvas.config(cursor="fleur")
        self.status_var.set("Click and drag to move selected pixels. Right-click to cancel.")
    
    def _finish_move_pixels(self, offset_x: int, offset_y: int):
        """Finish moving pixels by applying the offset."""
        if self.selected_pixel_mask is None:
            return
        
        page = self._get_current_page()
        if not page:
            return
        
        h, w = page.original_image.shape[:2]
        
        # Create new image with moved pixels
        new_image = page.original_image.copy()
        
        # Extract selected pixels
        selected_pixels = np.zeros_like(page.original_image)
        selected_pixels[self.selected_pixel_mask > 0] = page.original_image[self.selected_pixel_mask > 0]
        
        # Clear original location (set to white)
        new_image[self.selected_pixel_mask > 0] = 255
        
        # Calculate new position
        if self.selected_pixel_bbox:
            x_min, y_min, x_max, y_max = self.selected_pixel_bbox
            new_x_min = max(0, min(w, x_min + offset_x))
            new_y_min = max(0, min(h, y_min + offset_y))
            new_x_max = max(0, min(w, x_max + offset_x))
            new_y_max = max(0, min(h, y_max + offset_y))
            
            # Create new mask at new position
            new_mask = np.zeros((h, w), dtype=np.uint8)
            old_h = y_max - y_min
            old_w = x_max - x_min
            new_h = new_y_max - new_y_min
            new_w = new_x_max - new_x_min
            
            if new_h > 0 and new_w > 0 and old_h > 0 and old_w > 0:
                # Extract the selected region
                old_region = selected_pixels[y_min:y_max, x_min:x_max]
                # Resize if needed (shouldn't be, but handle edge cases)
                if new_h != old_h or new_w != old_w:
                    old_region = cv2.resize(old_region, (new_w, new_h), interpolation=cv2.INTER_NEAREST)
                
                # Place at new location
                new_image[new_y_min:new_y_max, new_x_min:new_x_max] = old_region
                new_mask[new_y_min:new_y_max, new_x_min:new_x_max] = 255
                
                # Update selection
                self.selected_pixel_mask = new_mask
                self.selected_pixel_bbox = (new_x_min, new_y_min, new_x_max, new_y_max)
        
        # Update page image
        page.original_image = new_image
        
        # Invalidate caches
        self.renderer.invalidate_cache()
        self._working_image_cache = None
        
        self.workspace_modified = True
        self._update_display()
        self.status_var.set(f"Moved pixels by ({offset_x}, {offset_y})")
    
    def _add_pixels_to_hidden_category(self, category: str):
        """Add selected pixels to a hidden category (mark_text, mark_hatch, mark_line)."""
        if self.selected_pixel_mask is None:
            return
        
        page = self._get_current_page()
        if not page:
            return
        
        h, w = page.original_image.shape[:2]
        
        if category == "mark_text":
            self._add_manual_text_region(page, self.selected_pixel_mask, None, "pixel_selection")
        elif category == "mark_hatch":
            self._add_manual_hatch_region(page, self.selected_pixel_mask, None, "pixel_selection")
        elif category == "mark_line":
            # For mark_line, we need points - use bounding box corners
            if self.selected_pixel_bbox:
                x_min, y_min, x_max, y_max = self.selected_pixel_bbox
                points = [(x_min, y_min), (x_max, y_min), (x_max, y_max), (x_min, y_max)]
            else:
                points = []
            self._add_manual_line_region(page, self.selected_pixel_mask, points, "pixel_selection")
        
        # Clear selection after adding
        self._clear_pixel_selection()
        self.status_var.set(f"Added pixels to {category}")
    
    def _add_elements_to_hidden_category(self, category: str):
        """Add selected elements to a hidden category."""
        if not self.selected_element_ids:
            return
        
        page = self._get_current_page()
        if not page:
            return
        
        # Find all selected elements and combine their masks
        combined_mask = None
        h, w = page.original_image.shape[:2]
        
        for obj in self.all_objects:
            for inst in obj.instances:
                if inst.page_id == page.tab_id:
                    for elem in inst.elements:
                        if elem.element_id in self.selected_element_ids:
                            if elem.mask is not None and elem.mask.shape == (h, w):
                                if combined_mask is None:
                                    combined_mask = np.zeros((h, w), dtype=np.uint8)
                                combined_mask = np.maximum(combined_mask, elem.mask)
        
        if combined_mask is None or np.sum(combined_mask > 0) == 0:
            return
        
        # Add to hidden category
        if category == "mark_text":
            self._add_manual_text_region(page, combined_mask, None, "element_selection")
        elif category == "mark_hatch":
            self._add_manual_hatch_region(page, combined_mask, None, "element_selection")
        elif category == "mark_line":
            # Use bounding box for points
            ys, xs = np.where(combined_mask > 0)
            if len(xs) > 0:
                x_min, x_max = int(np.min(xs)), int(np.max(xs))
                y_min, y_max = int(np.min(ys)), int(np.max(ys))
                points = [(x_min, y_min), (x_max, y_min), (x_max, y_max), (x_min, y_max)]
            else:
                points = []
            self._add_manual_line_region(page, combined_mask, points, "element_selection")
        
        # Remove the elements from their objects (they're now hidden)
        for obj in self.all_objects[:]:  # Copy list to avoid modification during iteration
            for inst in obj.instances[:]:
                if inst.page_id == page.tab_id:
                    inst.elements = [e for e in inst.elements if e.element_id not in self.selected_element_ids]
                    if not inst.elements:
                        obj.instances.remove(inst)
            if not obj.instances:
                self.all_objects.remove(obj)
        
        # Clear selections
        self.selected_element_ids.clear()
        self.selected_object_ids.clear()
        self.selected_instance_ids.clear()
        
        self.workspace_modified = True
        self.renderer.invalidate_cache()
        self._update_tree()
        self._update_display()
        self.status_var.set(f"Added elements to {category}")
    
    def _duplicate_pixel_selection(self):
        """Duplicate the selected pixels as a new object."""
        if self.selected_pixel_mask is None:
            return
        
        page = self._get_current_page()
        if not page:
            return
        
        h, w = page.original_image.shape[:2]
        
        # Get the current category
        cat_name = self.category_var.get()
        if not cat_name:
            cat_name = "textbox"  # Default category
        
        cat = self.categories.get(cat_name)
        if not cat:
            return
        
        # Create element from pixel selection
        elem = SegmentElement(
            category=cat_name,
            mode="pixel_selection",
            points=[],
            mask=self.selected_pixel_mask.copy(),
            color=cat.color_rgb,
            label_position=self.label_position
        )
        
        # Create new object manually so we can select it
        prefix = cat.prefix if cat else cat_name[0].upper()
        count = sum(1 for o in self.all_objects if o.category == cat_name) + 1
        
        current_view = getattr(self, 'current_view_var', None)
        view_type = current_view.get() if current_view else ""
        
        new_obj = SegmentedObject(name=f"{prefix}{count}", category=cat_name)
        inst = ObjectInstance(instance_num=1, page_id=page.tab_id, view_type=view_type)
        inst.elements.append(elem)
        new_obj.instances.append(inst)
        self.all_objects.append(new_obj)
        
        self.workspace_modified = True
        self.renderer.invalidate_cache()
        self._add_tree_item(new_obj)
        
        # Clear pixel selection
        self._clear_pixel_selection()
        
        # Select the new object and start move mode
        self.selected_object_ids = {new_obj.object_id}
        self.selected_instance_ids.clear()
        self.selected_element_ids.clear()
        self._update_tree()
        self._update_display()
        
        # Start move mode so user can position the duplicate
        self._start_move_objects()
        self.status_var.set("Duplicated pixels as new object - Click and drag to position, or press Escape to cancel")
    
    def _start_move_objects(self):
        """Start moving selected objects/elements."""
        if not (self.selected_object_ids or self.selected_instance_ids or self.selected_element_ids):
            return
        
        # Switch to select mode so click/drag works properly
        self.current_mode = "select"
        self.mode_var.set("select")
        
        self.is_moving_objects = True
        self.object_move_start = None  # Will be set on first click
        self.object_move_offset = None
        
        page = self._get_current_page()
        if page and hasattr(page, 'canvas'):
            page.canvas.config(cursor="fleur")
            # Focus the canvas so it receives mouse events
            page.canvas.focus_set()
            
        # Update the display to show the selection
        self._update_display()
        self.status_var.set("Click and drag to move selected objects. Right-click or Escape to cancel.")
    
    def _finish_move_objects(self, offset_x: int, offset_y: int):
        """Finish moving objects/elements by applying the offset."""
        if offset_x == 0 and offset_y == 0:
            self.is_moving_objects = False
            self.object_move_start = None
            self.object_move_offset = None
            return
        
        page = self._get_current_page()
        if not page:
            return
        
        h, w = page.original_image.shape[:2]
        moved_count = 0
        
        # CRITICAL: First collect ORIGINAL masks before moving them
        # We need the original masks to extract pixels from the old location
        original_masks = []
        elements_to_move = []
        
        # Collect original masks and elements
        if self.selected_object_ids:
            for obj_id in self.selected_object_ids:
                obj = self._get_object_by_id(obj_id)
                if not obj:
                    continue
                for inst in obj.instances:
                    if inst.page_id == page.tab_id:
                        for elem in inst.elements:
                            if elem.mask is not None and elem.mask.shape == (h, w):
                                original_masks.append(elem.mask.copy())  # Copy before modifying
                                elements_to_move.append(elem)
                                moved_count += 1
        
        if self.selected_instance_ids:
            for inst_id in self.selected_instance_ids:
                for obj in self.all_objects:
                    for inst in obj.instances:
                        if inst.instance_id == inst_id and inst.page_id == page.tab_id:
                            for elem in inst.elements:
                                if elem.mask is not None and elem.mask.shape == (h, w):
                                    original_masks.append(elem.mask.copy())
                                    elements_to_move.append(elem)
                                    moved_count += 1
        
        if self.selected_element_ids:
            for elem_id in self.selected_element_ids:
                for obj in self.all_objects:
                    for inst in obj.instances:
                        if inst.page_id == page.tab_id:
                            for elem in inst.elements:
                                if elem.element_id == elem_id:
                                    if elem.mask is not None and elem.mask.shape == (h, w):
                                        original_masks.append(elem.mask.copy())
                                        elements_to_move.append(elem)
                                        moved_count += 1
        
        if moved_count > 0 and original_masks:
            # Actually move pixels in the original image
            new_image = page.original_image.copy()
            
            # Combine all original masks
            combined_mask = np.zeros((h, w), dtype=np.uint8)
            for mask in original_masks:
                combined_mask = np.maximum(combined_mask, mask)
            
            # Translate mask to new location
            M = np.float32([[1, 0, offset_x], [0, 1, offset_y]])
            translated_mask = cv2.warpAffine(combined_mask, M, (w, h),
                                           flags=cv2.INTER_NEAREST,
                                           borderMode=cv2.BORDER_CONSTANT,
                                           borderValue=0)
            
            # Check if there are other objects at the destination location
            # Get IDs of objects being moved (to exclude them from overlap check)
            moved_object_ids = set()
            moved_element_ids = set()
            if self.selected_object_ids:
                moved_object_ids.update(self.selected_object_ids)
            if self.selected_instance_ids:
                for inst_id in self.selected_instance_ids:
                    for obj in self.all_objects:
                        for inst in obj.instances:
                            if inst.instance_id == inst_id:
                                moved_object_ids.add(obj.object_id)
            if self.selected_element_ids:
                moved_element_ids.update(self.selected_element_ids)
            
            # Check for overlap with other objects at destination
            has_overlap = False
            page_objects = self._get_objects_for_page(page.tab_id)
            for obj in page_objects:
                # Skip objects being moved
                if obj.object_id in moved_object_ids:
                    continue
                
                # Skip mark categories (they don't have visible pixels)
                if obj.category in ["mark_text", "mark_hatch", "mark_line"]:
                    continue
                
                # Check if any element of this object overlaps with translated mask
                for inst in obj.instances:
                    if inst.page_id == page.tab_id:
                        for elem in inst.elements:
                            # Skip elements being moved
                            if elem.element_id in moved_element_ids:
                                continue
                            
                            if elem.mask is not None and elem.mask.shape == (h, w):
                                # Check pixel overlap
                                overlap = np.sum((elem.mask > 0) & (translated_mask > 0))
                                if overlap > 0:
                                    has_overlap = True
                                    break
                        if has_overlap:
                            break
                if has_overlap:
                    break
            
            # Extract pixels from old location using ORIGINAL mask
            if len(new_image.shape) == 3:
                # BGR image
                selected_pixels = np.zeros_like(new_image)
                mask_3d = combined_mask[:, :, np.newaxis]
                selected_pixels = np.where(mask_3d > 0, new_image, 0)
            else:
                # Grayscale
                selected_pixels = np.where(combined_mask > 0, new_image, 0)
            
            # Translate the selected pixels to the new location
            M = np.float32([[1, 0, offset_x], [0, 1, offset_y]])
            translated_pixels = cv2.warpAffine(selected_pixels, M, (w, h),
                                              flags=cv2.INTER_NEAREST,
                                              borderMode=cv2.BORDER_CONSTANT,
                                              borderValue=0)
            
            if has_overlap:
                # COPY pixels: Place at new location without clearing old location
                # This allows multiple objects to share the same pixels
                if len(new_image.shape) == 3:
                    mask_3d = translated_mask[:, :, np.newaxis]
                    # Blend: place new pixels where mask is set, keep existing where not
                    new_image = np.where(mask_3d > 0, translated_pixels, new_image)
                else:
                    new_image = np.where(translated_mask > 0, translated_pixels, new_image)
                action = "Copied"
            else:
                # MOVE pixels: Clear old location and place at new location
                # Clear old location (set to white)
                if len(new_image.shape) == 3:
                    new_image[combined_mask > 0] = [255, 255, 255]
                    # Place translated pixels where the translated mask is set
                    mask_3d = translated_mask[:, :, np.newaxis]
                    new_image = np.where(mask_3d > 0, translated_pixels, new_image)
                else:
                    new_image[combined_mask > 0] = 255
                    new_image = np.where(translated_mask > 0, translated_pixels, new_image)
                action = "Moved"
            
            # Update page image
            page.original_image = new_image
            
            # NOW move the masks and points
            M = np.float32([[1, 0, offset_x], [0, 1, offset_y]])
            for elem in elements_to_move:
                if elem.mask is not None and elem.mask.shape == (h, w):
                    # Translate mask
                    elem.mask = cv2.warpAffine(elem.mask, M, (w, h),
                                              flags=cv2.INTER_NEAREST,
                                              borderMode=cv2.BORDER_CONSTANT,
                                              borderValue=0)
                    # Translate points
                    if elem.points:
                        elem.points = [(x + offset_x, y + offset_y) 
                                      for x, y in elem.points]
            
            self.renderer.invalidate_cache()
            self._working_image_cache = None
            self.workspace_modified = True
            self._update_display()
            self.status_var.set(f"{action} {moved_count} element(s) by ({offset_x}, {offset_y})")
        else:
            self.status_var.set("No elements to move")
        
        self.is_moving_objects = False
        self.object_move_start = None
        self.object_move_offset = None
    
    def _delete_pixels_from_objects(self, objects_to_delete, instances_to_delete, elements_to_delete):
        """
        Delete pixels from original_image for the given objects/instances/elements.
        Sets pixels in mask areas to white.
        """
        # Group masks by page
        page_masks = {}  # page_id -> list of masks
        
        # Collect masks from objects to delete
        for obj in objects_to_delete:
            for inst in obj.instances:
                page_id = inst.page_id
                if page_id not in page_masks:
                    page_masks[page_id] = []
                
                for elem in inst.elements:
                    if elem.mask is not None:
                        page_masks[page_id].append(elem.mask)
        
        # Collect masks from instances to delete
        for obj, inst in instances_to_delete:
            page_id = inst.page_id
            if page_id not in page_masks:
                page_masks[page_id] = []
            
            for elem in inst.elements:
                if elem.mask is not None:
                    page_masks[page_id].append(elem.mask)
        
        # Collect masks from elements to delete
        for obj, inst, elem in elements_to_delete:
            page_id = inst.page_id
            if page_id not in page_masks:
                page_masks[page_id] = []
            
            if elem.mask is not None:
                page_masks[page_id].append(elem.mask)
        
        # For each page, combine masks and delete pixels
        for page_id, masks in page_masks.items():
            page = self.pages.get(page_id)
            if not page or page.original_image is None:
                continue
            
            h, w = page.original_image.shape[:2]
            
            # Combine all masks for this page
            combined_mask = np.zeros((h, w), dtype=np.uint8)
            for mask in masks:
                if mask is not None and mask.shape == (h, w):
                    combined_mask = np.maximum(combined_mask, mask)
            
            # Set pixels to white where mask is active
            if np.any(combined_mask > 0):
                if len(page.original_image.shape) == 3:
                    # BGR image
                    mask_3channel = cv2.cvtColor(combined_mask, cv2.COLOR_GRAY2BGR)
                    page.original_image[mask_3channel > 0] = [255, 255, 255]
                else:
                    # Grayscale image
                    page.original_image[combined_mask > 0] = 255
                
                # Invalidate cache for this page since original_image changed
                self.renderer.invalidate_cache()
                print(f"DEBUG: Deleted pixels from page {page_id} (mask size: {np.sum(combined_mask > 0)} pixels)")
    
    def _delete_selected(self):
        # First, collect all objects/elements that will be deleted and their masks
        # to show dialog and handle pixel deletion if needed
        objects_to_delete = []
        elements_to_delete = []
        instances_to_delete = []
        
        # Collect objects to delete
        for obj_id in self.selected_object_ids:
            obj = self._get_object_by_id(obj_id)
            if obj:
                objects_to_delete.append(obj)
        
        # Collect instances to delete
        for inst_id in self.selected_instance_ids:
            for obj in self.all_objects:
                for inst in obj.instances:
                    if inst.instance_id == inst_id:
                        instances_to_delete.append((obj, inst))
        
        # Collect elements to delete
        for elem_id in self.selected_element_ids:
            for obj in self.all_objects:
                for inst in obj.instances:
                    for elem in inst.elements:
                        if elem.element_id == elem_id:
                            elements_to_delete.append((obj, inst, elem))
        
        # Count total items to delete
        total_count = len(objects_to_delete) + len(instances_to_delete) + len(elements_to_delete)
        
        # Show dialog if there are items to delete
        if total_count == 0:
            return
        
        # Show deletion dialog
        dialog = DeleteObjectDialog(self.root, total_count, self.theme)
        
        if dialog.result is None:
            # User cancelled
            return
        
        pixel_action = dialog.result  # "delete_pixels" or "revert_pixels"
        
        # If "delete_pixels", collect all masks and delete pixels from original_image
        if pixel_action == "delete_pixels":
            self._delete_pixels_from_objects(objects_to_delete, instances_to_delete, elements_to_delete)
        
        # Now proceed with normal deletion logic
        modified_objs = set()
        deleted_objs = set()
        page_ids_to_update = set()  # Track page IDs that need mask updates (use IDs since PageTab is not hashable)
        
        # Handle element deletions - also remove from page region lists if mark_text/hatch/line
        for elem_id in self.selected_element_ids:
            for obj in self.all_objects:
                for inst in obj.instances:
                    for elem in inst.elements:
                        if elem.element_id == elem_id:
                            # If this is a mark_text/hatch/line element, remove from page regions
                            if obj.category in ["mark_text", "mark_hatch", "mark_line"]:
                                page = self.pages.get(inst.page_id)
                                if page:
                                    page_ids_to_update.add(inst.page_id)
                                    # Find and remove the corresponding region (from both auto and manual lists)
                                    if obj.category == "mark_text":
                                        if hasattr(page, 'manual_text_regions'):
                                            page.manual_text_regions = [r for r in page.manual_text_regions 
                                                                        if r.get('id') != elem_id]
                                        if hasattr(page, 'auto_text_regions'):
                                            page.auto_text_regions = [r for r in page.auto_text_regions 
                                                                      if r.get('id') != elem_id]
                                    elif obj.category == "mark_hatch":
                                        if hasattr(page, 'manual_hatch_regions'):
                                            page.manual_hatch_regions = [r for r in page.manual_hatch_regions 
                                                                         if r.get('id') != elem_id]
                                    elif obj.category == "mark_line":
                                        if hasattr(page, 'manual_line_regions'):
                                            page.manual_line_regions = [r for r in page.manual_line_regions 
                                                                        if str(r.get('id', '')) != str(elem_id)]
                    
                    old_len = len(inst.elements)
                    inst.elements = [e for e in inst.elements if e.element_id != elem_id]
                    if len(inst.elements) != old_len:
                        modified_objs.add(obj.object_id)
                obj.instances = [i for i in obj.instances if i.elements]
        
        # Handle instance deletions - also remove from page region lists if mark_text/hatch/line
        for inst_id in self.selected_instance_ids:
            for obj in self.all_objects:
                for inst in obj.instances:
                    if inst.instance_id == inst_id:
                        # If this instance has mark_text/hatch/line elements, remove from page regions
                        if obj.category in ["mark_text", "mark_hatch", "mark_line"]:
                            page = self.pages.get(inst.page_id)
                            if page:
                                page_ids_to_update.add(inst.page_id)
                                for elem in inst.elements:
                                    if obj.category == "mark_text":
                                        if hasattr(page, 'manual_text_regions'):
                                            page.manual_text_regions = [r for r in page.manual_text_regions 
                                                                        if r.get('id') != elem.element_id]
                                        if hasattr(page, 'auto_text_regions'):
                                            page.auto_text_regions = [r for r in page.auto_text_regions 
                                                                      if r.get('id') != elem.element_id]
                                    elif obj.category == "mark_hatch":
                                        if hasattr(page, 'manual_hatch_regions'):
                                            page.manual_hatch_regions = [r for r in page.manual_hatch_regions 
                                                                         if r.get('id') != elem.element_id]
                                    elif obj.category == "mark_line":
                                        if hasattr(page, 'manual_line_regions'):
                                            page.manual_line_regions = [r for r in page.manual_line_regions 
                                                                        if str(r.get('id', '')) != str(elem.element_id)]
                
                old_len = len(obj.instances)
                obj.instances = [i for i in obj.instances if i.instance_id != inst_id]
                if len(obj.instances) != old_len:
                    modified_objs.add(obj.object_id)
        
        # Handle object deletions - also remove from page region lists if mark_text/hatch/line
        for obj_id in self.selected_object_ids:
            obj = self._get_object_by_id(obj_id)
            if obj:
                # If this object has mark_text/hatch/line elements, remove from page regions
                if obj.category in ["mark_text", "mark_hatch", "mark_line"]:
                    for inst in obj.instances:
                        page = self.pages.get(inst.page_id)
                        if page:
                            page_ids_to_update.add(inst.page_id)
                            for elem in inst.elements:
                                if obj.category == "mark_text":
                                    if hasattr(page, 'manual_text_regions'):
                                        page.manual_text_regions = [r for r in page.manual_text_regions 
                                                                    if r.get('id') != elem.element_id]
                                    if hasattr(page, 'auto_text_regions'):
                                        page.auto_text_regions = [r for r in page.auto_text_regions 
                                                                  if r.get('id') != elem.element_id]
                                elif obj.category == "mark_hatch":
                                    if hasattr(page, 'manual_hatch_regions'):
                                        page.manual_hatch_regions = [r for r in page.manual_hatch_regions 
                                                                     if r.get('id') != elem.element_id]
                                elif obj.category == "mark_line":
                                    if hasattr(page, 'manual_line_regions'):
                                        page.manual_line_regions = [r for r in page.manual_line_regions 
                                                                    if str(r.get('id', '')) != str(elem.element_id)]
            deleted_objs.add(obj_id)
        
        # Remove deleted objects
        self.all_objects = [o for o in self.all_objects if o.object_id not in deleted_objs]
        
        # Clean up empty objects
        for obj in self.all_objects[:]:
            if not obj.instances:
                deleted_objs.add(obj.object_id)
                self.all_objects.remove(obj)
        
        # Update combined masks for affected pages (optimize for mark_line deletion)
        print(f"DEBUG _delete_selected: Updating masks for {len(page_ids_to_update)} pages")
        import time
        start_time = time.time()
        
        for page_id in page_ids_to_update:
            page = self.pages.get(page_id)
            if page:
                # Only update masks if we actually deleted mark_text/hatch/line objects
                deleted_mark_text = any(
                    obj.category == "mark_text" for obj_id in deleted_objs 
                    for obj in [self._get_object_by_id(obj_id)] if obj
                )
                deleted_mark_hatch = any(
                    obj.category == "mark_hatch" for obj_id in deleted_objs 
                    for obj in [self._get_object_by_id(obj_id)] if obj
                )
                deleted_mark_line = any(
                    obj.category == "mark_line" for obj_id in deleted_objs 
                    for obj in [self._get_object_by_id(obj_id)] if obj
                )
                
                if deleted_mark_text and hasattr(page, 'manual_text_regions'):
                    print(f"DEBUG: Updating text mask for page {page_id}")
                    self._update_combined_text_mask(page, force_recompute=True)
                if deleted_mark_hatch and hasattr(page, 'manual_hatch_regions'):
                    print(f"DEBUG: Updating hatch mask for page {page_id}")
                    self._update_combined_hatch_mask(page, force_recompute=True)
                if deleted_mark_line:
                    print(f"DEBUG: Updating line mask for page {page_id}")
                    # Recompute combined line mask from all remaining objects
                    self._update_combined_line_mask(page, force_recompute=True)
        
        elapsed = time.time() - start_time
        print(f"DEBUG _delete_selected: Mask update took {elapsed:.3f} seconds")
        
        # Save tree state before rebuild (which categories are expanded)
        expanded_categories = set()
        if hasattr(self, 'tree_grouping_var') and self.tree_grouping_var.get() == "category":
            for item in self.object_tree.get_children():
                if item.startswith("cat_"):
                    if self.object_tree.item(item, "open"):
                        expanded_categories.add(item)
        
        # Determine if we deleted mark_line objects and should select the category heading
        deleted_mark_line = any(
            obj.category == "mark_line" for obj_id in deleted_objs 
            for obj in [self._get_object_by_id(obj_id)] if obj
        )
        
        self.selected_object_ids.clear()
        self.selected_instance_ids.clear()
        self.selected_element_ids.clear()
        self.workspace_modified = True
        self.renderer.invalidate_cache()  # Objects changed
        
        # Full tree rebuild since objects have been removed
        # (Incremental update doesn't work well after objects are removed from all_objects)
        self._update_tree()
        
        # Restore tree state (which categories are expanded)
        if hasattr(self, 'tree_grouping_var') and self.tree_grouping_var.get() == "category":
            for item in self.object_tree.get_children():
                if item.startswith("cat_"):
                    if item in expanded_categories:
                        self.object_tree.item(item, open=True)
                    else:
                        self.object_tree.item(item, open=False)
        
        # If mark_line objects were deleted, select the mark_line category heading
        if deleted_mark_line:
            mark_line_cat_id = "cat_mark_line"
            if self.object_tree.exists(mark_line_cat_id):
                self.object_tree.selection_set(mark_line_cat_id)
                self.object_tree.see(mark_line_cat_id)
        
        self._update_display()
    
    def _merge_as_instances(self):
        if len(self.selected_object_ids) < 2:
            messagebox.showinfo("Info", "Select at least 2 objects")
            return
        
        objs = [self._get_object_by_id(oid) for oid in self.selected_object_ids]
        objs = [o for o in objs if o]
        if len(objs) < 2:
            return
        
        target = objs[0]
        name = simpledialog.askstring("Merge", "Merged name:", initialvalue=target.name, parent=self.root)
        if not name:
            return
        
        for other in objs[1:]:
            for inst in other.instances:
                inst.instance_num = len(target.instances) + 1
                target.instances.append(inst)
            self.all_objects.remove(other)
            self._remove_tree_item(other.object_id)
        
        target.name = name
        self.workspace_modified = True
        self.renderer.invalidate_cache()
        self._update_tree_item(target)
        self._update_display()
    
    def _merge_as_group(self):
        if len(self.selected_object_ids) < 2 and len(self.selected_element_ids) < 2:
            messagebox.showinfo("Info", "Select at least 2 items")
            return
        
        page = self._get_current_page()
        if not page:
            return
        
        # Collect all elements
        elements = []
        obj_ids_to_remove = set()
        
        for obj_id in self.selected_object_ids:
            obj = self._get_object_by_id(obj_id)
            if obj:
                for inst in obj.instances:
                    elements.extend(inst.elements)
                obj_ids_to_remove.add(obj_id)
        
        for elem_id in self.selected_element_ids:
            for obj in self.all_objects:
                for inst in obj.instances:
                    for elem in inst.elements:
                        if elem.element_id == elem_id and elem not in elements:
                            elements.append(elem)
        
        if len(elements) < 2:
            return
        
        cat_name = self.category_var.get() or "R"
        name = simpledialog.askstring("Merge", f"Name ({len(elements)} elements):", parent=self.root)
        if not name:
            return
        
        # Remove old objects
        for obj_id in obj_ids_to_remove:
            self._remove_tree_item(obj_id)
        self.all_objects = [o for o in self.all_objects if o.object_id not in obj_ids_to_remove]
        
        # Create new grouped object
        obj = SegmentedObject(name=name, category=cat_name)
        inst = ObjectInstance(instance_num=1, page_id=page.tab_id)
        inst.elements = elements
        obj.instances.append(inst)
        self.all_objects.append(obj)
        
        self.workspace_modified = True
        self.renderer.invalidate_cache()
        self._add_tree_item(obj)
        self._update_display()
    
    # File operations
    def _open_pdf(self):
        if self.pages and self.workspace_modified:
            r = messagebox.askyesnocancel("Save?", "Save workspace first?")
            if r is None:
                return
            if r:
                self._save_workspace()
        
        path = filedialog.askopenfilename(title="Open PDF", filetypes=[("PDF", "*.pdf")])
        if not path:
            return
        
        self._open_pdf_from_path(path)
    
    def _open_pdf_from_path(self, path: str):
        """Open PDF from a specific path (used by both dialog and command line)."""
        # Load with dimension information
        pages = self.pdf_reader.load_with_dimensions(path)
        if not pages:
            messagebox.showerror("Error", "Failed to load PDF")
            return
        
        dialog = PDFLoaderDialog(self.root, path, pages, dpi=self.settings.default_dpi)
        result = dialog.show()
        if not result:
            return
        
        # Close existing and reset workspace
        for tid in list(self.pages.keys()):
            if hasattr(self.pages[tid], 'frame'):
                self.notebook.forget(self.pages[tid].frame)
            del self.pages[tid]
        
        # Reset all workspace data
        self.all_objects = []  # Clear object list
        self.categories = create_default_categories()
        self._refresh_categories()
        self.selected_object_ids.clear()
        self.selected_instance_ids.clear()
        self.selected_element_ids.clear()
        self._update_tree()  # Clear tree view
        self.workspace_file = None
        self.workspace_modified = True
        
        for page_data in result:
            page = PageTab(
                model_name=page_data['model_name'],
                page_name=page_data['page_name'],
                original_image=page_data['image'],
                source_path=path,
                rotation=page_data.get('rotation', 0),
                dpi=page_data.get('dpi', self.settings.default_dpi),
                pdf_width_inches=page_data.get('width_inches', 0),
                pdf_height_inches=page_data.get('height_inches', 0),
            )
            self._add_page(page)
        
        self.status_var.set(f"Loaded {len(result)} pages")
    
    def _save_workspace(self):
        if not self.workspace_file:
            self._save_workspace_as()
            return
        
        # Collect view state
        view_state = self._get_view_state()
        
        # Update page-level view state (zoom, scroll)
        for page in self.pages.values():
            page.zoom_level = self.zoom_level  # Current zoom
            if hasattr(page, 'canvas'):
                # Save scroll position
                page.scroll_x = page.canvas.xview()[0]
                page.scroll_y = page.canvas.yview()[0]
        
        if self.workspace_mgr.save(self.workspace_file, list(self.pages.values()), 
                                   self.categories, self.all_objects, view_state):
            self.workspace_modified = False
            self.status_var.set(f"Saved: {Path(self.workspace_file).name}")
    
    def _save_workspace_as(self):
        path = filedialog.asksaveasfilename(title="Save Workspace", defaultextension=".pmw",
                                            filetypes=[("PlanMod Workspace", "*.pmw")])
        if path:
            self.workspace_file = path
            self._save_workspace()
    
    def _load_startup_file(self):
        """Load workspace or PDF specified via command line arguments."""
        import os
        
        if self._startup_workspace:
            path = self._startup_workspace
            if os.path.exists(path):
                print(f"Loading startup workspace: {path}")
                self._load_workspace_from_path(path)
            else:
                messagebox.showerror("Error", f"Workspace file not found: {path}")
        elif self._startup_pdf:
            path = self._startup_pdf
            if os.path.exists(path):
                print(f"Loading startup PDF: {path}")
                self._open_pdf_from_path(path)
            else:
                messagebox.showerror("Error", f"PDF file not found: {path}")
    
    def _load_workspace(self):
        if self.pages and self.workspace_modified:
            r = messagebox.askyesnocancel("Save?", "Save workspace first?")
            if r is None:
                return
            if r:
                self._save_workspace()
        
        path = filedialog.askopenfilename(title="Open Workspace", filetypes=[("PlanMod Workspace", "*.pmw")])
        if not path:
            return
        
        self._load_workspace_from_path(path)
    
    def _load_workspace_from_path(self, path: str):
        """Load workspace from a specific path (used by both dialog and command line)."""
        data = self.workspace_mgr.load(path)
        if not data:
            messagebox.showerror("Error", "Failed to load workspace")
            return
        
        # Close existing and reset workspace
        for tid in list(self.pages.keys()):
            if hasattr(self.pages[tid], 'frame'):
                self.notebook.forget(self.pages[tid].frame)
            del self.pages[tid]
        
        # Invalidate cache when loading new workspace (different pages/images)
        self._invalidate_working_image_cache()
        
        # Clear selections
        self.selected_object_ids.clear()
        self.selected_instance_ids.clear()
        self.selected_element_ids.clear()
        
        self.categories = data.categories
        if not self.categories:
            self.categories = create_default_categories()
        
        # Ensure mark_text and mark_hatch exist for backwards compatibility
        if "mark_text" not in self.categories:
            self.categories["mark_text"] = DynamicCategory(
                name="mark_text", prefix="mark_text", full_name="Mark as Text",
                color_rgb=(255, 200, 0), selection_mode="flood"
            )
        if "mark_hatch" not in self.categories:
            self.categories["mark_hatch"] = DynamicCategory(
                name="mark_hatch", prefix="mark_hatch", full_name="Mark as Hatching",
                color_rgb=(200, 0, 255), selection_mode="flood"
            )
        if "mark_line" not in self.categories:
            self.categories["mark_line"] = DynamicCategory(
                name="mark_line", prefix="mark_line", full_name="Mark as Leader Line",
                color_rgb=(0, 255, 255), selection_mode="flood"
            )

        self._refresh_categories()
        
        # Load global objects
        self.all_objects = data.objects if data.objects else []
        
        # First pass: add all pages (this triggers delayed display updates)
        for page in data.pages:
            self._add_page(page, from_workspace=True)
        
        # Second pass: rebuild all masks AFTER pages are added (optimized batch processing)
        # This ensures masks exist before any display update happens
        self.status_var.set("Building masks...")
        self.root.update()
        
        for i, page in enumerate(data.pages):
            # Update progress for large workspaces
            if len(data.pages) > 1:
                self.status_var.set(f"Building masks... {i+1}/{len(data.pages)}")
                self.root.update()
            
            # ALWAYS rebuild combined masks to ensure they're initialized
            self._update_combined_text_mask(page, force_recompute=True)
            self._update_combined_hatch_mask(page, force_recompute=True)
            
            # Add existing text regions to mark_text category
            self._add_existing_text_regions_to_category(page)
            # Add existing line regions to mark_line category (repairs masks)
            print(f"DEBUG _load_workspace: Calling _add_existing_line_regions_to_category for page {page.tab_id}")
            self._add_existing_line_regions_to_category(page)
            
            # Rebuild combined_line_mask from all mark_line objects (including those loaded from workspace)
            self._update_combined_line_mask(page, force_recompute=True)
        
        self.status_var.set("Loading complete")
        
        # CRITICAL: Invalidate renderer cache AFTER masks are built
        # This forces re-render with correct masks when display updates
        self.renderer.invalidate_cache()
        
        self._update_tree()  # Rebuild tree with loaded objects
        
        # Update view menu (no longer needs hide_text state)
        self._update_view_menu_labels()
        
        self.workspace_file = path
        self.workspace_modified = False
        self.status_var.set(f"Loaded: {Path(path).name}")
        
        # Restore view state (current page, zoom, etc.)
        if data.view_state:
            self._restore_view_state(data.view_state)
        
        # Only render the current/active page - other pages will be rendered lazily when selected
        def _final_refresh():
            # Only render the current page
            page = self._get_current_page()
            if page:
                self.renderer.invalidate_cache()
                self._update_display()
                self._draw_rulers(page)
                # Restore scroll position if available
                if hasattr(page, 'scroll_x') and hasattr(page, 'scroll_y'):
                    page.canvas.xview_moveto(page.scroll_x)
                    page.canvas.yview_moveto(page.scroll_y)
            # Update zoom display
            if hasattr(self, 'zoom_label'):
                zoom_text = f"{int(self.zoom_level * 100)}%"
                self.zoom_label.config(text=zoom_text)
            if hasattr(self, 'status_bar'):
                self.status_bar.set_item_text("zoom", f"{int(self.zoom_level * 100)}%")
        
        self.root.after(500, _final_refresh)  # Increased delay to ensure masks are ready
    
    def _export_image(self):
        page = self._get_current_page()
        if not page:
            return
        
        path = filedialog.asksaveasfilename(title="Export Image", defaultextension=".png",
                                            initialfile=page.segmented_filename,
                                            filetypes=[("PNG", "*.png")])
        if path:
            from replan.desktop.io.export import ImageExporter
            ImageExporter(self.renderer).export_page(path, page, self.categories)
            self.status_var.set(f"Exported: {Path(path).name}")
    
    def _export_data(self):
        page = self._get_current_page()
        if not page:
            return
        
        path = filedialog.asksaveasfilename(title="Export Data", defaultextension=".json",
                                            filetypes=[("JSON", "*.json")])
        if path:
            from replan.desktop.io.export import DataExporter
            DataExporter().export_page(path, page)
            self.status_var.set(f"Exported: {Path(path).name}")
    
    def _create_view_tab_from_planform(self):
        """Create a new working tab from the selected planform object with only objects inside its boundary."""
        page = self._get_current_page()
        if not page:
            messagebox.showwarning("No Page", "No page is currently open.")
            return
        
        # Check if a planform object is selected
        if not self.selected_object_ids:
            messagebox.showwarning("No Selection", "Please select a planform object first.")
            return
        
        # Get the selected planform object
        selected_obj_id = next(iter(self.selected_object_ids))
        planform_obj = None
        for obj in self.all_objects:
            if obj.object_id == selected_obj_id and obj.category == "planform":
                planform_obj = obj
                break
        
        if not planform_obj:
            messagebox.showwarning("Invalid Selection", "Please select a planform object.")
            return
        
        # CRITICAL: Recreate planform mask from polyline points, not from stored mask
        # The stored mask might include pixels from other planforms or be corrupted
        # Recreating from points ensures we get the exact polyline shape
        h, w = page.original_image.shape[:2]
        planform_mask = np.zeros((h, w), dtype=np.uint8)
        planform_points = []
        
        for inst in planform_obj.instances:
            if inst.page_id == page.tab_id:
                for elem in inst.elements:
                    if elem.mode == "polyline" and len(elem.points) >= 3:
                        # Recreate mask from polyline points - this is the true planform shape
                        elem_mask = self.engine.create_polygon_mask((h, w), elem.points)
                        planform_mask = np.maximum(planform_mask, elem_mask)
                        planform_points.extend(elem.points)
                    elif elem.mask is not None and elem.mask.shape == (h, w):
                        # Fallback: use stored mask if points are not available
                        planform_mask = np.maximum(planform_mask, elem.mask)
        
        planform_pixel_count = np.sum(planform_mask > 0)
        print(f"DEBUG: Recreated planform mask from points has {planform_pixel_count} non-white pixels (shape: {h}x{w})")
        
        if planform_pixel_count == 0:
            messagebox.showwarning("Invalid Planform", "The selected planform has no valid mask.")
            return
        
        # Debug: Check if planform mask looks like a rectangle (bounding box filled)
        ys, xs = np.where(planform_mask > 0)
        if len(xs) > 0:
            x_min_debug, x_max_debug = int(np.min(xs)), int(np.max(xs)) + 1
            y_min_debug, y_max_debug = int(np.min(ys)), int(np.max(ys)) + 1
            bbox_area = (x_max_debug - x_min_debug) * (y_max_debug - y_min_debug)
            fill_ratio = planform_pixel_count / bbox_area if bbox_area > 0 else 0
            print(f"DEBUG: Planform bounding box: ({x_min_debug}, {y_min_debug}) to ({x_max_debug}, {y_max_debug})")
            print(f"DEBUG: Planform bounding box area: {bbox_area} pixels")
            print(f"DEBUG: Planform fill ratio: {fill_ratio:.2%} (100% = rectangle, lower = polyline shape)")
            if fill_ratio > 0.95:
                print(f"WARNING: Planform mask appears to be a filled rectangle, not a polyline!")
            else:
                print(f"DEBUG: Planform mask appears to be a polyline shape (not a rectangle)")
        
        # Get the working image (with hidden pixels removed) and crop to planform bounds
        working_image = self._get_working_image(page)
        
        # Find bounding box of planform to crop image
        ys, xs = np.where(planform_mask > 0)
        if len(xs) == 0:
            messagebox.showwarning("Invalid Planform", "The selected planform has no pixels.")
            return
        
        x_min, x_max = int(np.min(xs)), int(np.max(xs)) + 1
        y_min, y_max = int(np.min(ys)), int(np.max(ys)) + 1
        
        # Add some padding
        padding = 20
        x_min = max(0, x_min - padding)
        y_min = max(0, y_min - padding)
        x_max = min(w, x_max + padding)
        y_max = min(h, y_max + padding)
        
        # Crop the working image to the planform area
        cropped_image = working_image[y_min:y_max, x_min:x_max].copy()
        cropped_h, cropped_w = cropped_image.shape[:2]
        
        # Adjust planform mask coordinates for cropped image
        cropped_planform_mask = planform_mask[y_min:y_max, x_min:x_max].copy()
        cropped_planform_pixel_count = np.sum(cropped_planform_mask > 0)
        print(f"DEBUG: Cropped planform mask has {cropped_planform_pixel_count} non-white pixels (cropped shape: {cropped_h}x{cropped_w})")
        
        # CRITICAL: Mask the cropped image to only include pixels within the planform polyline boundary
        # Set all pixels outside the polyline to white (background)
        # This ensures we only copy pixels that are within the exact polyline boundary, not the entire bounding box
        pixels_inside_polyline = np.sum(cropped_planform_mask > 0)
        total_cropped_pixels = cropped_h * cropped_w
        
        # Create a boolean mask for pixels inside the polyline
        inside_mask = cropped_planform_mask > 0
        
        # Apply mask to image - set pixels outside polyline to white
        if len(cropped_image.shape) == 3:  # BGR or RGB image (3 channels)
            # Broadcast mask to 3 channels: (H, W) -> (H, W, 1) -> (H, W, 3)
            inside_mask_3d = inside_mask[:, :, np.newaxis]
            # Set pixels outside planform to white (255, 255, 255) for BGR
            cropped_image = np.where(inside_mask_3d, cropped_image, 255)
        else:  # Grayscale image (2D)
            # Set pixels outside planform to white (255)
            cropped_image = np.where(inside_mask, cropped_image, 255)
        
        print(f"DEBUG: Cropped image has {total_cropped_pixels:,} total pixels")
        print(f"DEBUG: Only {pixels_inside_polyline:,} pixels are within planform polyline ({pixels_inside_polyline/total_cropped_pixels*100:.2f}%)")
        print(f"DEBUG: {total_cropped_pixels - pixels_inside_polyline:,} pixels outside polyline have been set to white (background)")
        
        # Ask for a name for the new view tab
        view_name = simpledialog.askstring(
            "Create View Tab",
            "Enter a name for the new view tab:",
            initialvalue=f"{planform_obj.name}_view"
        )
        if not view_name:
            return
        
        # Create new PageTab with the cropped cleaned image
        new_page = PageTab(
            tab_id=str(uuid.uuid4())[:8],
            model_name=page.model_name,
            page_name=view_name,
            original_image=cropped_image,  # Use cropped cleaned image as original
            source_path=page.source_path,
            rotation=page.rotation,
            active=True,
            dpi=page.dpi,
            pdf_width_inches=page.pdf_width_inches,
            pdf_height_inches=page.pdf_height_inches
        )
        
        # Copy only the selected planform and objects inside its boundary
        mark_categories = {"mark_text", "mark_hatch", "mark_line"}
        copied_count = 0
        
        # First, copy the planform object itself
        new_planform_instances = []
        for inst in planform_obj.instances:
            if inst.page_id == page.tab_id:
                # Adjust element masks and points for cropped coordinates
                new_elements = []
                for elem in inst.elements:
                    # CRITICAL: Recreate element mask from points if it's a polyline
                    # This ensures we only copy the exact polyline shape, not corrupted stored masks
                    if elem.mode == "polyline" and len(elem.points) >= 3:
                        # Recreate mask from points - this is the true planform shape
                        elem_mask_recreated = self.engine.create_polygon_mask((h, w), elem.points)
                    elif elem.mask is not None and elem.mask.shape == (h, w):
                        # Use stored mask for other modes
                        elem_mask_recreated = elem.mask.copy()
                    else:
                        continue
                    
                    # CRITICAL: Filter to only include pixels within the recreated planform polyline
                    # This ensures we don't copy corners of other planforms
                    elem_mask_inside_planform = elem_mask_recreated.copy()
                    elem_mask_inside_planform[planform_mask == 0] = 0  # Remove pixels outside polyline
                    
                    # Check if element has any pixels after filtering
                    if np.sum(elem_mask_inside_planform > 0) == 0:
                        continue  # Element is completely outside planform polyline
                    
                    # Crop the filtered mask to bounding box
                    cropped_elem_mask = elem_mask_inside_planform[y_min:y_max, x_min:x_max].copy()
                    
                    # Double-check: ensure all pixels are within cropped planform mask
                    cropped_planform_mask = planform_mask[y_min:y_max, x_min:x_max]
                    cropped_elem_mask = cropped_elem_mask & cropped_planform_mask
                    
                    # Only include if there are pixels after filtering
                    cropped_elem_pixel_count = np.sum(cropped_elem_mask > 0)
                    if cropped_elem_pixel_count == 0:
                        continue
                    
                    # Debug: Show original vs filtered pixel counts
                    original_elem_pixel_count = np.sum(elem_mask_recreated > 0)
                    filtered_elem_pixel_count = np.sum(elem_mask_inside_planform > 0)
                    print(f"DEBUG: Planform element {elem.element_id}:")
                    print(f"  Recreated mask pixels: {original_elem_pixel_count}")
                    print(f"  After filtering to planform polyline: {filtered_elem_pixel_count}")
                    print(f"  After cropping to bounding box: {cropped_elem_pixel_count}")
                    
                    # Adjust points (filter to only points within cropped area AND planform polyline)
                    adjusted_points = []
                    for x, y in elem.points:
                        # Check if point is within bounding box
                        if x_min <= x < x_max and y_min <= y < y_max:
                            # Check if point is within planform mask (polyline)
                            if planform_mask[y, x] > 0:
                                adjusted_points.append((x - x_min, y - y_min))
                    
                    new_elem = SegmentElement(
                        element_id=elem.element_id,
                        category=elem.category,
                        mode=elem.mode,
                        points=adjusted_points,
                        mask=cropped_elem_mask,
                        color=elem.color,
                        label_position=elem.label_position
                    )
                    new_elements.append(new_elem)
                
                if new_elements:
                    new_inst = ObjectInstance(
                        instance_id=f"{inst.instance_id}_{new_page.tab_id}",
                        instance_num=inst.instance_num,
                        elements=new_elements,
                        page_id=new_page.tab_id,
                        view_type=inst.view_type,
                        attributes=inst.attributes
                    )
                    new_planform_instances.append(new_inst)
        
        if new_planform_instances:
            # Debug: Count total pixels in copied planform
            total_copied_planform_pixels = 0
            for inst in new_planform_instances:
                for elem in inst.elements:
                    if elem.mask is not None:
                        total_copied_planform_pixels += np.sum(elem.mask > 0)
            print(f"DEBUG: Copied planform has {total_copied_planform_pixels} non-white pixels")
            print(f"DEBUG: Expected {cropped_planform_pixel_count} pixels (from cropped planform mask)")
            if abs(total_copied_planform_pixels - cropped_planform_pixel_count) > 10:
                print(f"WARNING: Pixel count mismatch! Copied: {total_copied_planform_pixels}, Expected: {cropped_planform_pixel_count}")
            else:
                print(f"DEBUG: Pixel counts match! ✓")
            
            new_planform_obj = SegmentedObject(
                object_id=f"{planform_obj.object_id}_{new_page.tab_id}",
                name=view_name,  # Use view name to distinguish from original planform
                category=planform_obj.category,
                instances=new_planform_instances
            )
            self.all_objects.append(new_planform_obj)
            copied_count += 1
        
        # CRITICAL: Use the stored list of objects that were within the planform at creation time
        # This ensures we only copy objects that were actually within the polyline boundaries
        objects_within_planform = self.planform_objects.get(planform_obj.object_id, [])
        
        if not objects_within_planform:
            # Fallback: if no stored list, find objects now (for backward compatibility)
            print(f"DEBUG: No stored objects list for planform {planform_obj.object_id}, finding objects now...")
            objects_within_planform = self._find_objects_within_planform(page, planform_mask, planform_obj.object_id)
            self.planform_objects[planform_obj.object_id] = objects_within_planform
        
        print(f"DEBUG: Planform {planform_obj.object_id} has {len(objects_within_planform)} stored objects within boundaries")
        for obj_id in objects_within_planform:
            obj = self._get_object_by_id(obj_id)
            if obj:
                print(f"  - {obj.name} ({obj_id})")
        
        # Now copy only the stored objects that were within the planform at creation time
        for obj_id in objects_within_planform:
            obj = self._get_object_by_id(obj_id)
            if not obj:
                continue
            
            # Verify object still exists and is on this page
            has_instance_on_page = any(inst.page_id == page.tab_id for inst in obj.instances)
            if not has_instance_on_page:
                continue
            
            # Copy the object
            # Create a copy of the object with adjusted coordinates
            # Only include parts of the object that are within the planform
            new_instances = []
            for inst in obj.instances:
                if inst.page_id == page.tab_id:
                    # Adjust element masks and points for cropped coordinates
                    new_elements = []
                    for elem in inst.elements:
                        if elem.mask is not None and elem.mask.shape == (h, w):
                            # CRITICAL: First filter element mask to only include pixels within planform polyline
                            # This uses the actual polyline shape, not the bounding box
                            elem_mask_inside_planform = elem.mask.copy()
                            elem_mask_inside_planform[planform_mask == 0] = 0  # Remove pixels outside polyline
                            
                            # Check if element has any pixels after filtering to planform
                            if np.sum(elem_mask_inside_planform > 0) == 0:
                                continue  # Element is completely outside planform polyline
                            
                            # Now crop to bounding box for the new view
                            cropped_elem_mask = elem_mask_inside_planform[y_min:y_max, x_min:x_max].copy()
                            
                            # Double-check: ensure all pixels are within cropped planform mask
                            cropped_planform_mask = planform_mask[y_min:y_max, x_min:x_max]
                            cropped_elem_mask = cropped_elem_mask & cropped_planform_mask
                            
                            # Only include element if it has pixels after filtering
                            copied_elem_pixel_count = np.sum(cropped_elem_mask > 0)
                            if copied_elem_pixel_count == 0:
                                continue
                            
                            # Debug: Show pixel counts for copied object
                            original_obj_pixels = np.sum(elem.mask > 0)
                            filtered_obj_pixels = np.sum(elem_mask_inside_planform > 0)
                            print(f"DEBUG: Copying object {obj.object_id} ({obj.name}), element {elem.element_id}:")
                            print(f"  Original pixels: {original_obj_pixels}")
                            print(f"  After filtering to planform: {filtered_obj_pixels}")
                            print(f"  After cropping: {copied_elem_pixel_count}")
                            
                            # Adjust points (filter to only points within cropped area AND planform polyline)
                            adjusted_points = []
                            for x, y in elem.points:
                                # Check if point is within bounding box
                                if x_min <= x < x_max and y_min <= y < y_max:
                                    # Check if point is within planform mask (polyline)
                                    if planform_mask[y, x] > 0:
                                        adjusted_points.append((x - x_min, y - y_min))
                            
                            new_elem = SegmentElement(
                                element_id=elem.element_id,
                                category=elem.category,
                                mode=elem.mode,
                                points=adjusted_points,
                                mask=cropped_elem_mask,
                                color=elem.color,
                                label_position=elem.label_position
                            )
                            new_elements.append(new_elem)
                    
                    if new_elements:
                        new_inst = ObjectInstance(
                            instance_id=f"{inst.instance_id}_{new_page.tab_id}",
                            instance_num=inst.instance_num,
                            elements=new_elements,
                            page_id=new_page.tab_id,
                            view_type=inst.view_type,
                            attributes=inst.attributes
                        )
                        new_instances.append(new_inst)
            
            if new_instances:
                # Create new object with copied instances
                new_obj = SegmentedObject(
                    object_id=f"{obj.object_id}_{new_page.tab_id}",
                    name=obj.name,
                    category=obj.category,
                    instances=new_instances
                )
                self.all_objects.append(new_obj)
                copied_count += 1
        
        # Initialize empty masks for the new page (no mark_* objects)
        new_page.combined_text_mask = None
        new_page.combined_hatch_mask = None
        new_page.combined_line_mask = None
        
        # Add the new page to the notebook
        self._add_page(new_page, from_workspace=False)
        
        # Switch to the new page
        self.current_page_id = new_page.tab_id
        self.notebook.select(self.pages[new_page.tab_id].frame)
        
        # Update display
        self._update_display()
        self._update_tree()
        
        self.status_var.set(f"Created view tab '{view_name}' with {copied_count} visible objects")
        self.workspace_modified = True
    
    def _scan_labels(self):
        pages = [p for p in self.pages.values() if p.original_image is not None]
        if not pages:
            messagebox.showinfo("Info", "No pages to scan")
            return
        
        dialog = LabelScanDialog(self.root, pages)
        result = dialog.show()
        
        if result:
            for prefix, full_name in result.items():
                if prefix not in self.categories:
                    color = get_next_color(len(self.categories))
                    self.categories[prefix] = DynamicCategory(
                        name=prefix, prefix=prefix, full_name=full_name,
                        color_rgb=color, selection_mode="flood"
                    )
            self._refresh_categories()
            self.workspace_modified = True
            self.status_var.set(f"Added {len(result)} categories")
    
    def _get_view_state(self) -> dict:
        """Get current view state for workspace saving."""
        return {
            "current_page_id": self.current_page_id,
            "zoom_level": self.zoom_level,
            "group_by": self.group_by_var.get() if hasattr(self, 'group_by_var') else "category",
            "show_labels": self.show_labels,
            "current_view": self.current_view_var.get() if hasattr(self, 'current_view_var') else "",
        }
    
    def _restore_view_state(self, view_state: dict):
        """Restore view state from loaded workspace."""
        if not view_state:
            return
        
        # Restore zoom level
        self.zoom_level = view_state.get("zoom_level", 1.0)
        if hasattr(self, 'zoom_var'):
            self.zoom_var.set(f"{int(self.zoom_level * 100)}%")
        
        # Restore group by
        if hasattr(self, 'group_by_var'):
            self.group_by_var.set(view_state.get("group_by", "category"))
        
        # Restore show labels
        self.show_labels = view_state.get("show_labels", True)
        if hasattr(self, 'show_labels_var'):
            self.show_labels_var.set(self.show_labels)
        
        # Restore current view
        if hasattr(self, 'current_view_var'):
            self.current_view_var.set(view_state.get("current_view", ""))
        
        # Restore current page (done after all pages loaded)
        target_page_id = view_state.get("current_page_id")
        if target_page_id and target_page_id in self.pages:
            self._switch_to_page(target_page_id)
    
    def _on_close(self):
        if self.workspace_modified:
            r = messagebox.askyesnocancel("Save?", "Save workspace before closing?")
            if r is None:
                return
            if r:
                self._save_workspace()
        
        # Save window geometry
        self.settings.window_width = self.root.winfo_width()
        self.settings.window_height = self.root.winfo_height()
        self.settings.window_x = self.root.winfo_x()
        self.settings.window_y = self.root.winfo_y()
        save_settings(self.settings)
        self.root.quit()
    
    def run(self):
        """Run the application."""
        self.root.mainloop()

