"""
Interactive tool to trace leader lines by clicking points on the image.
Shows results in real-time and allows selecting multiple lines sequentially.
"""

import cv2
import numpy as np
from pathlib import Path
import argparse
from skimage.morphology import skeletonize
from skimage import img_as_ubyte

# Import functions from trace_with_points
from trace_with_points import (
    convert_to_monochrome,
    skeletonize_image,
    find_nearest_skeleton_point,
    trace_between_points,
    measure_line_thickness,
    select_line_pixels,
    detect_collisions
)


class InteractiveTracer:
    def __init__(self, image_path):
        self.image_path = image_path
        self.original_img = cv2.imread(str(image_path))
        if self.original_img is None:
            raise ValueError(f"Could not read image: {image_path}")
        
        self.h, self.w = self.original_img.shape[:2]
        self.current_points = []
        self.all_lines = []  # List of dicts: {'points': [...], 'mask': ..., 'contours': ...}
        
        # Zoom and pan state
        self.zoom_level = 1.0
        self.pan_x = 0
        self.pan_y = 0
        self.is_panning = False
        self.pan_start_x = 0
        self.pan_start_y = 0
        self.min_zoom = 0.1
        self.max_zoom = 10.0
        
        # UI layout dimensions
        self.control_panel_height = 50  # Fixed height for buttons at top
        self.scrollbar_width = 20  # Width of vertical scrollbar
        self.scrollbar_height = 20  # Height of horizontal scrollbar
        self.button_size = 35  # Size of zoom buttons (square)
        self.button_spacing = 5  # Spacing between buttons
        
        # Preprocess images once
        print("Preprocessing image...")
        self.binary = convert_to_monochrome(self.original_img)
        self.skeleton = skeletonize_image(self.binary)
        print("Ready!")
        
        # Check if GUI is available
        self.gui_available = self.check_gui_support()
        
        if self.gui_available:
            # Create display window (larger size)
            self.window_name = "Interactive Line Tracer"
            cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
            # Set initial window size
            cv2.resizeWindow(self.window_name, 1400, 1000)
            cv2.setMouseCallback(self.window_name, self.mouse_callback)
            
            # Viewport dimensions (will be calculated based on window size in update_display)
            self.viewport_w = 1400 - self.scrollbar_width
            self.viewport_h = 1000 - self.control_panel_height - self.scrollbar_height
            
            # Display initial image
            self.update_display()
        else:
            print("Warning: GUI not available. Using file-based interaction mode.")
            print("Points will be read from input. Saving visualization after each line.")
            self.window_name = None
    
    def check_gui_support(self):
        """Check if OpenCV GUI functions are available."""
        try:
            # Try to create a test window
            test_window = "test_gui_check"
            cv2.namedWindow(test_window, cv2.WINDOW_NORMAL)
            cv2.destroyWindow(test_window)
            return True
        except cv2.error:
            return False
    
    def screen_to_image_coords(self, screen_x, screen_y):
        """Convert screen coordinates to image coordinates accounting for zoom and pan."""
        # Account for viewport offset (scrollbar on left, control panel on top)
        viewport_x = screen_x - self.scrollbar_width
        viewport_y = screen_y - self.control_panel_height
        
        # Convert to image coordinates (accounting for pan and zoom)
        img_x = (viewport_x - self.pan_x) / self.zoom_level
        img_y = (viewport_y - self.pan_y) / self.zoom_level
        
        return int(img_x), int(img_y)
    
    def zoom_at_point(self, screen_x, screen_y, zoom_factor):
        """Zoom towards a specific screen point."""
        try:
            old_zoom = self.zoom_level
            self.zoom_level *= zoom_factor
            self.zoom_level = max(self.min_zoom, min(self.max_zoom, self.zoom_level))
            
            # Adjust pan to zoom towards the point
            if old_zoom != self.zoom_level:
                # Convert screen position to image coordinates
                img_x, img_y = self.screen_to_image_coords(screen_x, screen_y)
                # Clamp image coordinates to valid range
                img_x = max(0, min(self.w - 1, img_x))
                img_y = max(0, min(self.h - 1, img_y))
                # Adjust pan to keep the point under mouse fixed
                self.pan_x = screen_x - img_x * self.zoom_level
                self.pan_y = screen_y - img_y * self.zoom_level
            
            self.update_display()
        except Exception as e:
            print(f"Error in zoom_at_point: {e}")
            import traceback
            traceback.print_exc()
    
    def get_max_pan(self):
        """Calculate maximum pan values based on current zoom and viewport size."""
        zoomed_w = self.w * self.zoom_level
        zoomed_h = self.h * self.zoom_level
        max_pan_x = max(0, int(zoomed_w - self.viewport_w))
        max_pan_y = max(0, int(zoomed_h - self.viewport_h))
        return max_pan_x, max_pan_y
    
    def fit_to_viewport(self):
        """Fit image to viewport."""
        # Calculate zoom to fit image in viewport
        zoom_x = self.viewport_w / self.w
        zoom_y = self.viewport_h / self.h
        self.zoom_level = min(zoom_x, zoom_y) * 0.95  # 95% to leave some margin
        self.zoom_level = max(self.min_zoom, min(self.max_zoom, self.zoom_level))
        
        # Center the image
        zoomed_w = self.w * self.zoom_level
        zoomed_h = self.h * self.zoom_level
        self.pan_x = max(0, int((zoomed_w - self.viewport_w) / 2))
        self.pan_y = max(0, int((zoomed_h - self.viewport_h) / 2))
        
        self.update_display()
    
    def zoom_in(self):
        """Zoom in by 20%."""
        old_zoom = self.zoom_level
        self.zoom_level = min(self.max_zoom, self.zoom_level * 1.2)
        
        # Adjust pan to keep center of viewport fixed
        if old_zoom != self.zoom_level:
            center_x = self.viewport_w // 2
            center_y = self.viewport_h // 2
            img_x = (center_x - self.pan_x) / old_zoom
            img_y = (center_y - self.pan_y) / old_zoom
            self.pan_x = center_x - img_x * self.zoom_level
            self.pan_y = center_y - img_y * self.zoom_level
            
            # Clamp pan to valid range
            max_pan_x, max_pan_y = self.get_max_pan()
            self.pan_x = max(0, min(max_pan_x, self.pan_x))
            self.pan_y = max(0, min(max_pan_y, self.pan_y))
        
        self.update_display()
    
    def zoom_out(self):
        """Zoom out by 20%."""
        old_zoom = self.zoom_level
        self.zoom_level = max(self.min_zoom, self.zoom_level / 1.2)
        
        # Adjust pan to keep center of viewport fixed
        if old_zoom != self.zoom_level:
            center_x = self.viewport_w // 2
            center_y = self.viewport_h // 2
            img_x = (center_x - self.pan_x) / old_zoom
            img_y = (center_y - self.pan_y) / old_zoom
            self.pan_x = center_x - img_x * self.zoom_level
            self.pan_y = center_y - img_y * self.zoom_level
            
            # Clamp pan to valid range
            max_pan_x, max_pan_y = self.get_max_pan()
            self.pan_x = max(0, min(max_pan_x, self.pan_x))
            self.pan_y = max(0, min(max_pan_y, self.pan_y))
        
        self.update_display()
    
    def is_point_in_button(self, x, y, button_x, button_y, button_w, button_h):
        """Check if a point is inside a button."""
        return (button_x <= x <= button_x + button_w and 
                button_y <= y <= button_y + button_h)
    
    def mouse_callback(self, event, x, y, flags, param):
        """Handle mouse events: clicks on buttons, scrollbars, and image."""
        if event == cv2.EVENT_LBUTTONDOWN:
            # Check if click is in control panel (buttons)
            if y < self.control_panel_height:
                button_y = (self.control_panel_height - self.button_size) // 2
                
                # Zoom In button (+)
                zoom_in_x = self.button_spacing
                if self.is_point_in_button(x, y, zoom_in_x, button_y, 
                                          self.button_size, self.button_size):
                    self.zoom_in()
                    return
                
                # Zoom Out button (-)
                zoom_out_x = zoom_in_x + self.button_size + self.button_spacing
                if self.is_point_in_button(x, y, zoom_out_x, button_y,
                                          self.button_size, self.button_size):
                    self.zoom_out()
                    return
                
                # Fit button
                fit_x = zoom_out_x + self.button_size + self.button_spacing
                if self.is_point_in_button(x, y, fit_x, button_y,
                                          self.button_size, self.button_size):
                    self.fit_to_viewport()
                    return
            
            # Check if click is in vertical scrollbar (left side)
            elif x < self.scrollbar_width and y >= self.control_panel_height:
                max_pan_x, max_pan_y = self.get_max_pan()
                if max_pan_y > 0:
                    # Calculate pan position from click
                    scrollbar_h = self.viewport_h
                    click_y_rel = y - self.control_panel_height
                    self.pan_y = int((click_y_rel / scrollbar_h) * max_pan_y)
                    self.pan_y = max(0, min(max_pan_y, self.pan_y))
                    self.update_display()
                return
            
            # Check if click is in horizontal scrollbar (bottom)
            elif y >= self.control_panel_height + self.viewport_h and x >= self.scrollbar_width:
                max_pan_x, max_pan_y = self.get_max_pan()
                if max_pan_x > 0:
                    # Calculate pan position from click
                    scrollbar_w = self.viewport_w
                    click_x_rel = x - self.scrollbar_width
                    self.pan_x = int((click_x_rel / scrollbar_w) * max_pan_x)
                    self.pan_x = max(0, min(max_pan_x, self.pan_x))
                    self.update_display()
                return
            
            # Click is in viewport - treat as image click
            elif (x >= self.scrollbar_width and x < self.scrollbar_width + self.viewport_w and
                  y >= self.control_panel_height and y < self.control_panel_height + self.viewport_h):
                img_x, img_y = self.screen_to_image_coords(x, y)
                # Clamp to image bounds
                img_x = max(0, min(self.w - 1, img_x))
                img_y = max(0, min(self.h - 1, img_y))
                
                self.current_points.append((img_x, img_y))
                print(f"Added point {len(self.current_points)}: ({img_x}, {img_y})")
                
                # If we have at least 2 points, trace the line
                if len(self.current_points) >= 2:
                    self.trace_current_line()
                
                self.update_display()
    
    def trace_current_line(self):
        """Trace the line for the current set of points."""
        if len(self.current_points) < 2:
            return
        
        print(f"\nTracing line with {len(self.current_points)} points...")
        
        # Find nearest skeleton points
        skeleton_points = []
        for x, y in self.current_points:
            nearest = find_nearest_skeleton_point(self.skeleton, x, y, search_radius=50)
            if nearest:
                skeleton_points.append(nearest)
            else:
                skeleton_points.append((x, y))
        
        # Trace line between points
        all_traced_points = []
        for i in range(len(skeleton_points) - 1):
            start_x, start_y = skeleton_points[i]
            end_x, end_y = skeleton_points[i + 1]
            
            segment_path = trace_between_points(self.skeleton, start_x, start_y, end_x, end_y)
            if segment_path:
                all_traced_points.extend(segment_path)
        
        if not all_traced_points or len(all_traced_points) < 5:
            print("  Warning: Could not trace sufficient path")
            return
        
        print(f"  Traced {len(all_traced_points)} points")
        
        # Measure thickness
        thickness = measure_line_thickness(self.original_img, all_traced_points)
        print(f"  Measured thickness: {thickness} pixels")
        
        # Select line pixels with collision handling (pass skeleton and user points for better detection)
        line_mask = select_line_pixels(self.original_img, all_traced_points, thickness, self.skeleton, self.current_points)
        
        # Get contours
        contours, _ = cv2.findContours(line_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Store this line
        self.all_lines.append({
            'user_points': self.current_points.copy(),
            'traced_points': all_traced_points,
            'mask': line_mask,
            'contours': contours,
            'thickness': thickness
        })
        
        print(f"  Line added! Total lines: {len(self.all_lines)}")
    
    def draw_button(self, img, text, x, y, size, color=(100, 100, 100), text_color=(255, 255, 255)):
        """Draw a square button on the image."""
        # Draw button background
        cv2.rectangle(img, (x, y), (x + size, y + size), color, -1)
        cv2.rectangle(img, (x, y), (x + size, y + size), (200, 200, 200), 2)
        
        # Draw text centered
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.8
        thickness = 2
        (text_w, text_h), baseline = cv2.getTextSize(text, font, font_scale, thickness)
        text_x = x + (size - text_w) // 2
        text_y = y + (size + text_h) // 2
        cv2.putText(img, text, (text_x, text_y), font, font_scale, text_color, thickness)
    
    def draw_scrollbar_vertical(self, img, x, y, h, max_value, current_value):
        """Draw a vertical scrollbar."""
        if max_value <= 0:
            # Draw disabled scrollbar
            cv2.rectangle(img, (x, y), (x + self.scrollbar_width, y + h), (200, 200, 200), -1)
            return
        
        # Draw scrollbar track
        cv2.rectangle(img, (x, y), (x + self.scrollbar_width, y + h), (180, 180, 180), -1)
        cv2.rectangle(img, (x, y), (x + self.scrollbar_width, y + h), (120, 120, 120), 1)
        
        # Calculate thumb position and size
        thumb_size = max(20, int(h * (h / (h + max_value))))
        thumb_pos = int((current_value / max_value) * (h - thumb_size)) if max_value > 0 else 0
        
        # Draw thumb
        thumb_y = y + thumb_pos
        cv2.rectangle(img, (x + 2, thumb_y), 
                     (x + self.scrollbar_width - 2, thumb_y + thumb_size), 
                     (100, 100, 100), -1)
        cv2.rectangle(img, (x + 2, thumb_y), 
                     (x + self.scrollbar_width - 2, thumb_y + thumb_size), 
                     (60, 60, 60), 1)
    
    def draw_scrollbar_horizontal(self, img, x, y, w, max_value, current_value):
        """Draw a horizontal scrollbar."""
        if max_value <= 0:
            # Draw disabled scrollbar
            cv2.rectangle(img, (x, y), (x + w, y + self.scrollbar_height), (200, 200, 200), -1)
            return
        
        # Draw scrollbar track
        cv2.rectangle(img, (x, y), (x + w, y + self.scrollbar_height), (180, 180, 180), -1)
        cv2.rectangle(img, (x, y), (x + w, y + self.scrollbar_height), (120, 120, 120), 1)
        
        # Calculate thumb position and size
        thumb_size = max(20, int(w * (w / (w + max_value))))
        thumb_pos = int((current_value / max_value) * (w - thumb_size)) if max_value > 0 else 0
        
        # Draw thumb
        thumb_x = x + thumb_pos
        cv2.rectangle(img, (thumb_x, y + 2), 
                     (thumb_x + thumb_size, y + self.scrollbar_height - 2), 
                     (100, 100, 100), -1)
        cv2.rectangle(img, (thumb_x, y + 2), 
                     (thumb_x + thumb_size, y + self.scrollbar_height - 2), 
                     (60, 60, 60), 1)
    
    def update_display(self):
        """Update the display with current state, accounting for zoom and pan."""
        # Get window size to calculate viewport
        try:
            window_rect = cv2.getWindowImageRect(self.window_name)
            window_w = window_rect[2]
            window_h = window_rect[3]
        except:
            window_w = 1400
            window_h = 1000
        
        # Update viewport dimensions
        self.viewport_w = window_w - self.scrollbar_width
        self.viewport_h = window_h - self.control_panel_height - self.scrollbar_height
        
        # Create canvas
        canvas = np.ones((window_h, window_w, 3), dtype=np.uint8) * 240  # Light gray background
        
        # Draw control panel background at top
        cv2.rectangle(canvas, (0, 0), (window_w, self.control_panel_height), (220, 220, 220), -1)
        cv2.rectangle(canvas, (0, self.control_panel_height), (window_w, self.control_panel_height), (150, 150, 150), 2)
        
        # Draw buttons in control panel
        button_y = (self.control_panel_height - self.button_size) // 2
        
        # Zoom In button (+)
        self.draw_button(canvas, "+", 
                        self.button_spacing, 
                        button_y,
                        self.button_size,
                        (80, 150, 80), (255, 255, 255))
        
        # Zoom Out button (-)
        self.draw_button(canvas, "-",
                        self.button_spacing + self.button_size + self.button_spacing,
                        button_y,
                        self.button_size,
                        (150, 80, 80), (255, 255, 255))
        
        # Fit button
        self.draw_button(canvas, "Fit",
                        self.button_spacing + 2 * (self.button_size + self.button_spacing),
                        button_y,
                        self.button_size,
                        (100, 100, 150), (255, 255, 255))
        
        # Draw status text
        status_text = f"Lines: {len(self.all_lines)} | Points: {len(self.current_points)} | Zoom: {self.zoom_level:.2f}x"
        text_x = self.button_spacing + 3 * (self.button_size + self.button_spacing) + 20
        cv2.putText(canvas, status_text,
                   (text_x, button_y + self.button_size // 2 + 5),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
        
        # Create the image display area
        display_img = self.original_img.copy()
        
        # Draw all completed lines
        for line_idx, line_data in enumerate(self.all_lines):
            # Draw mask contours in red (thick outline)
            if len(line_data['contours']) > 0:
                cv2.drawContours(display_img, line_data['contours'], -1, (0, 0, 255), 3)  # Red, 3px thick
            
            # Draw traced path in cyan (thin center line)
            if len(line_data['traced_points']) > 1:
                pts = np.array(line_data['traced_points'], dtype=np.int32)
                cv2.polylines(display_img, [pts], False, (255, 255, 0), 1)  # Cyan, 1px
            
            # Draw user points in green
            for x, y in line_data['user_points']:
                cv2.circle(display_img, (x, y), 5, (0, 255, 0), -1)
        
        # Draw current line being traced (if any points selected)
        if len(self.current_points) > 0:
            # Draw current points in yellow
            for x, y in self.current_points:
                cv2.circle(display_img, (x, y), 5, (0, 255, 255), -1)
            
            # If we have 2+ points, show temporary trace
            if len(self.current_points) >= 2:
                # Find skeleton points
                skeleton_points = []
                for x, y in self.current_points:
                    nearest = find_nearest_skeleton_point(self.skeleton, x, y, search_radius=50)
                    if nearest:
                        skeleton_points.append(nearest)
                    else:
                        skeleton_points.append((x, y))
                
                # Draw temporary trace
                for i in range(len(skeleton_points) - 1):
                    start_x, start_y = skeleton_points[i]
                    end_x, end_y = skeleton_points[i + 1]
                    segment_path = trace_between_points(self.skeleton, start_x, start_y, end_x, end_y)
                    if segment_path and len(segment_path) > 1:
                        pts = np.array(segment_path, dtype=np.int32)
                        cv2.polylines(display_img, [pts], False, (255, 255, 255), 1)  # White for temp
        
        # Apply zoom to image (uniform for both axes)
        zoomed_w = int(self.w * self.zoom_level)
        zoomed_h = int(self.h * self.zoom_level)
        if zoomed_w != self.w or zoomed_h != self.h:
            display_img = cv2.resize(display_img, (zoomed_w, zoomed_h), interpolation=cv2.INTER_LINEAR)
        
        # Get max pan values
        max_pan_x, max_pan_y = self.get_max_pan()
        
        # Clamp pan values
        self.pan_x = max(0, min(max_pan_x, self.pan_x))
        self.pan_y = max(0, min(max_pan_y, self.pan_y))
        
        # Draw vertical scrollbar (left side) - only if needed
        if max_pan_y > 0:
            self.draw_scrollbar_vertical(canvas, 0, self.control_panel_height, 
                                         self.viewport_h, max_pan_y, self.pan_y)
        else:
            # Draw disabled scrollbar
            cv2.rectangle(canvas, (0, self.control_panel_height), 
                         (self.scrollbar_width, self.control_panel_height + self.viewport_h), 
                         (200, 200, 200), -1)
        
        # Draw horizontal scrollbar (bottom) - only if needed
        if max_pan_x > 0:
            self.draw_scrollbar_horizontal(canvas, self.scrollbar_width, 
                                          self.control_panel_height + self.viewport_h,
                                          self.viewport_w, max_pan_x, self.pan_x)
        else:
            # Draw disabled scrollbar
            cv2.rectangle(canvas, (self.scrollbar_width, self.control_panel_height + self.viewport_h),
                         (self.scrollbar_width + self.viewport_w, 
                          self.control_panel_height + self.viewport_h + self.scrollbar_height),
                         (200, 200, 200), -1)
        
        # Place zoomed image in viewport with pan offset
        viewport_x = self.scrollbar_width
        viewport_y = self.control_panel_height
        
        # Calculate source region from zoomed image
        src_x1 = max(0, self.pan_x)
        src_y1 = max(0, self.pan_y)
        src_x2 = min(zoomed_w, self.pan_x + self.viewport_w)
        src_y2 = min(zoomed_h, self.pan_y + self.viewport_h)
        
        # Calculate destination region in canvas
        dst_x1 = viewport_x
        dst_y1 = viewport_y
        dst_x2 = viewport_x + (src_x2 - src_x1)
        dst_y2 = viewport_y + (src_y2 - src_y1)
        
        # Copy image region to viewport
        if src_x2 > src_x1 and src_y2 > src_y1 and dst_x2 > dst_x1 and dst_y2 > dst_y1:
            canvas[dst_y1:dst_y2, dst_x1:dst_x2] = display_img[src_y1:src_y2, src_x1:src_x2]
        
        # Draw viewport border
        cv2.rectangle(canvas, (viewport_x, viewport_y), 
                     (viewport_x + self.viewport_w, viewport_y + self.viewport_h), 
                     (100, 100, 100), 1)
        
        if self.gui_available and self.window_name:
            cv2.imshow(self.window_name, canvas)
        else:
            # Save to file instead
            output_path = Path(self.image_path).parent / "interactive_preview.jpg"
            cv2.imwrite(str(output_path), canvas)
            print(f"Preview saved to: {output_path}")
    
    def clear_current(self):
        """Clear current points (start new line)."""
        if self.current_points:
            print(f"Cleared {len(self.current_points)} current points")
            self.current_points = []
            self.update_display()
    
    def reset_all(self):
        """Reset all lines and points."""
        print(f"Resetting all lines ({len(self.all_lines)} lines)")
        self.current_points = []
        self.all_lines = []
        self.update_display()
    
    def save_results(self):
        """Save all traced lines to files."""
        if not self.all_lines:
            print("No lines to save!")
            return
        
        input_path = Path(self.image_path)
        base_name = input_path.stem
        
        # Create output image with all lines
        output_img = self.original_img.copy()
        
        for line_idx, line_data in enumerate(self.all_lines):
            # Draw mask contours in red (thick outline)
            if len(line_data['contours']) > 0:
                cv2.drawContours(output_img, line_data['contours'], -1, (0, 0, 255), 3)  # Red, 3px thick
            
            # Draw traced path in cyan (thin center line)
            if len(line_data['traced_points']) > 1:
                pts = np.array(line_data['traced_points'], dtype=np.int32)
                cv2.polylines(output_img, [pts], False, (255, 255, 0), 1)  # Cyan, 1px
            
            # Draw user points in green
            for x, y in line_data['user_points']:
                cv2.circle(output_img, (x, y), 5, (0, 255, 0), -1)
        
        # Save combined output
        output_path = input_path.parent / f"{base_name}_interactive_traced.jpg"
        cv2.imwrite(str(output_path), output_img)
        print(f"\nSaved combined output to: {output_path}")
        
        # Save individual line masks
        combined_mask = np.zeros((self.h, self.w), dtype=np.uint8)
        for line_idx, line_data in enumerate(self.all_lines):
            combined_mask = cv2.bitwise_or(combined_mask, line_data['mask'])
            
            # Also save individual mask
            individual_mask_path = input_path.parent / f"{base_name}_line_{line_idx + 1}_mask.png"
            cv2.imwrite(str(individual_mask_path), line_data['mask'])
        
        # Save combined mask
        combined_mask_path = input_path.parent / f"{base_name}_interactive_combined_mask.png"
        cv2.imwrite(str(combined_mask_path), combined_mask)
        print(f"Saved combined mask to: {combined_mask_path}")
        print(f"Saved {len(self.all_lines)} individual line masks")
    
    def run(self):
        """Main interactive loop."""
        print("\n" + "="*60)
        print("Interactive Line Tracer")
        print("="*60)
        print("Instructions:")
        print("  - Click on the image to add points for a line")
        print("  - Add at least 2 points to trace a line")
        print("  - Use +, -, and Fit buttons to control zoom")
        print("  - Use scrollbars (left and bottom) to pan when zoomed in")
        print("  - Press 'c' to clear current points (start new line)")
        print("  - Press 'r' to reset all lines")
        print("  - Press 's' to save results")
        print("  - Press 'q' to quit")
        print("="*60 + "\n")
        
        if not self.gui_available:
            print("ERROR: GUI not available. Cannot run interactive mode.")
            print("Please ensure opencv-python (not opencv-python-headless) is installed.")
            return
        
        while True:
            key = cv2.waitKey(1) & 0xFF
            
            if key == ord('q'):
                print("\nQuitting...")
                break
            elif key == ord('c'):
                self.clear_current()
            elif key == ord('r'):
                self.reset_all()
            elif key == ord('s'):
                self.save_results()
            elif key == ord('0'):  # Reset zoom (keyboard shortcut)
                self.zoom_level = 1.0
                self.pan_x = 0
                self.pan_y = 0
                cv2.setTrackbarPos('Zoom', self.window_name, 10)  # 1.0x = position 10
                cv2.setTrackbarPos('Pan X', self.window_name, 0)
                cv2.setTrackbarPos('Pan Y', self.window_name, 0)
                self.update_display()
            
            # Small delay to prevent high CPU usage
            cv2.waitKey(10)
        
        cv2.destroyAllWindows()


def main():
    parser = argparse.ArgumentParser(
        description='Interactive tool to trace leader lines by clicking points'
    )
    parser.add_argument('input_image', type=str,
                       help='Input image path')
    
    args = parser.parse_args()
    
    try:
        tracer = InteractiveTracer(args.input_image)
        tracer.run()
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()

