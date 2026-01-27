"""Dialog for selecting multiple objects detected in rectangle selection."""

import tkinter as tk
from tkinter import ttk
import cv2
import numpy as np
from PIL import Image, ImageTk
from typing import List, Optional

from replan.desktop.models import PageTab


class RectangleSelectionDialog:
    """Dialog for selecting which detected objects to create from rectangle selection."""
    
    def __init__(self, parent, page: PageTab, detected_masks: List[np.ndarray],
                 category: str, theme: dict, x_min: int, y_min: int, x_max: int, y_max: int,
                 leader_flags: List[bool] = None, working_image: np.ndarray = None):
        self.parent = parent
        self.page = page
        self.detected_masks = detected_masks
        self.category = category
        self.theme = theme
        self.leader_flags = leader_flags or [False] * len(detected_masks)
        self.result: Optional[List[int]] = None
        self.create_combined: bool = False  # Flag for combined object creation
        
        # Store ROI coordinates
        h, w = page.original_image.shape[:2]
        self.x_min = max(0, min(x_min, w - 1))
        self.x_max = max(0, min(x_max, w - 1))
        self.y_min = max(0, min(y_min, h - 1))
        self.y_max = max(0, min(y_max, h - 1))
        
        # Extract ROI for preview - use working_image if provided (respects category visibility)
        if working_image is not None:
            self.roi_image = working_image[self.y_min:self.y_max, self.x_min:self.x_max].copy()
        else:
            self.roi_image = page.original_image[self.y_min:self.y_max, self.x_min:self.x_max].copy()
        self.roi_h, self.roi_w = self.roi_image.shape[:2]
        
        # Extract ROI masks (crop full masks to ROI region)
        self.roi_masks = []
        for mask in detected_masks:
            roi_mask = mask[self.y_min:self.y_max, self.x_min:self.x_max]
            self.roi_masks.append(roi_mask)
        
        # Generate distinct colors for each object
        self.colors = self._generate_colors(len(detected_masks))
        
        # Create dialog window
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"Select {category} Objects")
        self.dialog.configure(bg=theme["bg"])
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Center dialog (smaller size)
        self.dialog.update_idletasks()
        width = 600
        height = 500
        x = (self.dialog.winfo_screenwidth() // 2) - (width // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (height // 2)
        self.dialog.geometry(f"{width}x{height}+{x}+{y}")
        
        # Selected indices
        self.selected_indices = set(range(len(detected_masks)))  # All selected by default
        
        # Create UI
        self._create_ui()
        
        # Wait for dialog to close
        self.dialog.wait_window()
    
    def _create_ui(self):
        """Create the dialog UI."""
        t = self.theme
        
        # Main frame
        main_frame = tk.Frame(self.dialog, bg=t["bg"])
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Instructions
        info_label = tk.Label(
            main_frame,
            text=f"Found {len(self.detected_masks)} object(s) in rectangle. Select which ones to create:",
            bg=t["bg"], fg=t["fg"], font=("Segoe UI", 10)
        )
        info_label.pack(anchor=tk.W, pady=(0, 10))
        
        # Content frame (image + checkboxes)
        content_frame = tk.Frame(main_frame, bg=t["bg"])
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        # Left side: Image display
        left_frame = tk.Frame(content_frame, bg=t["bg"])
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        # Image label
        self.image_label = tk.Label(left_frame, bg=t["bg"])
        self.image_label.pack(fill=tk.BOTH, expand=True)
        
        # Right side: Checkbox list with scrollbar
        right_frame = tk.Frame(content_frame, bg=t["bg"], width=200)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH)
        right_frame.pack_propagate(False)
        
        # Scrollable frame for object list
        canvas = tk.Canvas(right_frame, bg=t["bg"], highlightthickness=0, width=200)
        scrollbar = ttk.Scrollbar(right_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=t["bg"])
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Create checkboxes for each detected object
        self.checkboxes = []
        
        for i, (mask, color) in enumerate(zip(self.roi_masks, self.colors)):
            item_frame = tk.Frame(scrollable_frame, bg=t["bg"], relief=tk.RAISED, bd=1)
            item_frame.pack(fill=tk.X, padx=5, pady=2)
            
            # Checkbox with label indicating if it's a leader line
            var = tk.BooleanVar(value=True)  # Selected by default
            
            is_leader = i < len(self.leader_flags) and self.leader_flags[i]
            label_text = f"Object {i+1}"
            if is_leader:
                label_text += " (Leader)"
            
            checkbox = ttk.Checkbutton(
                item_frame,
                text=label_text,
                variable=var,
                command=lambda idx=i, v=var: self._toggle_selection(idx, v)
            )
            checkbox.pack(side=tk.LEFT, padx=5, pady=2)
            self.checkboxes.append((var, checkbox))
        
        # Pack scrollable area
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Buttons at bottom (outside content frame)
        button_frame = tk.Frame(main_frame, bg=t["bg"])
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(
            button_frame,
            text="Select All",
            command=self._select_all
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            button_frame,
            text="Deselect All",
            command=self._deselect_all
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            button_frame,
            text="Cancel",
            command=self._cancel
        ).pack(side=tk.RIGHT, padx=5)
        
        # Only show combined button if multiple objects are detected
        if len(self.detected_masks) > 1:
            ttk.Button(
                button_frame,
                text="Create as Combined Object",
                command=self._ok_combined
            ).pack(side=tk.RIGHT, padx=5)
        
        ttk.Button(
            button_frame,
            text="Create Selected",
            command=self._ok
        ).pack(side=tk.RIGHT, padx=5)
        
        # Initial image update
        self._update_image()
    
    def _generate_colors(self, count: int) -> List[tuple]:
        """Generate distinct colors for highlighting objects."""
        colors = []
        for i in range(count):
            # Generate HSV colors evenly spaced
            hue = int((i * 180) / max(count, 1))  # 0-180 for OpenCV
            color_hsv = np.uint8([[[hue, 255, 255]]])
            color_bgr = cv2.cvtColor(color_hsv, cv2.COLOR_HSV2BGR)[0][0]
            colors.append(tuple(int(c) for c in color_bgr))
        return colors
    
    def _update_image(self):
        """Update the displayed image with highlights for selected objects."""
        # Start with the original ROI image
        display_image = self.roi_image.copy()
        
        # Highlight selected objects
        for idx in self.selected_indices:
            if 0 <= idx < len(self.roi_masks):
                mask = self.roi_masks[idx]
                color = self.colors[idx]
                
                # Create overlay
                overlay = display_image.copy()
                mask_region = mask > 0
                overlay[mask_region] = color
                
                # Blend with original (50% opacity)
                alpha = 0.5
                display_image = cv2.addWeighted(display_image, 1 - alpha, overlay, alpha, 0)
        
        # Resize to fit available space (max 400px width/height)
        max_dim = 400
        h, w = display_image.shape[:2]
        scale = min(max_dim / max(h, w), 1.0)
        
        if scale < 1.0:
            new_w = int(w * scale)
            new_h = int(h * scale)
            display_image = cv2.resize(display_image, (new_w, new_h), interpolation=cv2.INTER_AREA)
        else:
            new_w, new_h = w, h
        
        # Convert to PIL Image for Tkinter
        rgb = cv2.cvtColor(display_image, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb)
        photo = ImageTk.PhotoImage(pil_img)
        
        # Update label
        self.image_label.config(image=photo)
        self.image_label.image = photo  # Keep reference
    
    def _toggle_selection(self, idx: int, var: tk.BooleanVar):
        """Toggle selection of an object and update image."""
        if var.get():
            self.selected_indices.add(idx)
        else:
            self.selected_indices.discard(idx)
        
        # Update image to show/hide highlight
        self._update_image()
    
    def _select_all(self):
        """Select all objects."""
        for var, _ in self.checkboxes:
            var.set(True)
        self.selected_indices = set(range(len(self.detected_masks)))
        self._update_image()
    
    def _deselect_all(self):
        """Deselect all objects."""
        for var, _ in self.checkboxes:
            var.set(False)
        self.selected_indices.clear()
        self._update_image()
    
    def _ok(self):
        """OK button - return selected indices."""
        self.result = sorted(self.selected_indices)
        self.create_combined = False
        self.dialog.destroy()
    
    def _ok_combined(self):
        """OK button for combined object - return selected indices with combined flag."""
        if len(self.selected_indices) < 2:
            # Need at least 2 objects to combine
            import tkinter.messagebox as mb
            mb.showwarning("Invalid Selection", "Please select at least 2 objects to combine.")
            return
        self.result = sorted(self.selected_indices)
        self.create_combined = True
        self.dialog.destroy()
    
    def _cancel(self):
        """Cancel button - return None."""
        self.result = None
        self.create_combined = False
        self.dialog.destroy()
