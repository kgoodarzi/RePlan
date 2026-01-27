"""
Trace leader lines based on user-provided points.
1. User provides start, mid, and end points
2. Convert image to black and white in memory
3. Skeletonize the image
4. Find nearest skeleton points to user points
5. Trace the line between points
6. Measure line thickness from original image
7. Select pixels based on thickness, handling collisions
"""

import cv2
import numpy as np
from pathlib import Path
import argparse
from skimage.morphology import skeletonize
from skimage import img_as_ubyte


def convert_to_monochrome(image):
    """
    Convert image to true black and white (monochrome).
    
    Args:
        image: BGR or grayscale image
    
    Returns:
        Binary black and white image (0 or 255)
    """
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()
    
    # Use Otsu's thresholding for automatic threshold selection
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    return binary


def skeletonize_image(binary_image):
    """
    Skeletonize a binary image to single-pixel thickness.
    
    Args:
        binary_image: Binary image (0 = black line, 255 = white background)
    
    Returns:
        Skeletonized binary image
    """
    # Invert for skeletonize (works on white foreground on black background)
    inverted = 255 - binary_image
    
    # Convert to boolean (True for foreground, False for background)
    binary_bool = inverted > 127
    
    # Skeletonize
    skeleton_bool = skeletonize(binary_bool)
    
    # Convert back to uint8
    skeleton = img_as_ubyte(skeleton_bool)
    
    # Invert back to original color scheme (black lines on white background)
    skeleton = 255 - skeleton
    
    return skeleton


def find_nearest_skeleton_point(skeleton, x, y, search_radius=50):
    """
    Find the nearest skeleton point to a given coordinate.
    
    Args:
        skeleton: Skeletonized binary image (0 = black line, 255 = white)
        x, y: Target point
        search_radius: Maximum distance to search
    
    Returns:
        (nearest_x, nearest_y) if found, None otherwise
    """
    h, w = skeleton.shape
    x, y = int(x), int(y)
    
    min_dist = float('inf')
    nearest_point = None
    
    # Search in expanding circles
    for radius in range(1, search_radius + 1):
        # Check all points in a square around the center
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                # Only check points on the circle perimeter (for efficiency)
                dist = np.sqrt(dx*dx + dy*dy)
                if radius - 0.5 <= dist <= radius + 0.5:
                    test_x = x + dx
                    test_y = y + dy
                    
                    if 0 <= test_x < w and 0 <= test_y < h:
                        # Check if this pixel is on skeleton (black)
                        if skeleton[test_y, test_x] < 127:
                            if dist < min_dist:
                                min_dist = dist
                                nearest_point = (test_x, test_y)
        
        # If we found a point, return it (closest one)
        if nearest_point:
            return nearest_point
    
    return None


def trace_between_points(skeleton, start_x, start_y, end_x, end_y):
    """
    Trace a line on the skeleton between two points.
    Uses A* or simple path following along the skeleton.
    
    Args:
        skeleton: Skeletonized binary image
        start_x, start_y: Start point (on skeleton)
        end_x, end_y: End point (on skeleton)
    
    Returns:
        List of (x, y) points along the traced path
    """
    h, w = skeleton.shape
    
    # Simple path following: at each point, move towards the end point
    # while staying on the skeleton
    current_x, current_y = int(start_x), int(start_y)
    end_x, end_y = int(end_x), int(end_y)
    
    path = [(current_x, current_y)]
    visited = set()
    visited.add((current_x, current_y))
    
    max_steps = 2000  # Prevent infinite loops
    step = 0
    
    while step < max_steps:
        # Check if we've reached the end (within 3 pixels)
        dist_to_end = np.sqrt((current_x - end_x)**2 + (current_y - end_y)**2)
        if dist_to_end < 3:
            path.append((end_x, end_y))
            break
        
        # Find next point: look at 8-neighborhood, prefer direction towards end
        best_next = None
        best_score = float('inf')
        
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue
                
                next_x = current_x + dx
                next_y = current_y + dy
                
                if 0 <= next_x < w and 0 <= next_y < h:
                    if (next_x, next_y) not in visited:
                        # Check if on skeleton
                        if skeleton[next_y, next_x] < 127:
                            # Score: distance to end + small penalty for path length
                            dist_to_end_from_next = np.sqrt((next_x - end_x)**2 + (next_y - end_y)**2)
                            score = dist_to_end_from_next
                            
                            if score < best_score:
                                best_score = score
                                best_next = (next_x, next_y)
        
        if best_next is None:
            # No valid next point, try expanding search
            found = False
            for radius in range(2, 5):
                for dx in range(-radius, radius + 1):
                    for dy in range(-radius, radius + 1):
                        if dx == 0 and dy == 0:
                            continue
                        next_x = current_x + dx
                        next_y = current_y + dy
                        if 0 <= next_x < w and 0 <= next_y < h:
                            if (next_x, next_y) not in visited:
                                if skeleton[next_y, next_x] < 127:
                                    dist_to_end_from_next = np.sqrt((next_x - end_x)**2 + (next_y - end_y)**2)
                                    if dist_to_end_from_next < dist_to_end:
                                        best_next = (next_x, next_y)
                                        found = True
                                        break
                    if found:
                        break
                if found:
                    break
            
            if best_next is None:
                # Can't find path, return what we have
                break
        
        if best_next is None or len(best_next) != 2:
            # Can't find path, return what we have
            break
        
        current_x, current_y = best_next
        path.append((current_x, current_y))
        visited.add((current_x, current_y))
        step += 1
    
    return path


def measure_line_thickness(original_image, traced_path, sample_length=20):
    """
    Measure the actual line thickness from the original image.
    Samples the first section of the traced path.
    
    Args:
        original_image: Original grayscale or BGR image
        traced_path: List of (x, y) points along the traced line
        sample_length: Number of points to sample for thickness measurement
    
    Returns:
        Average line thickness in pixels
    """
    if len(original_image.shape) == 3:
        gray = cv2.cvtColor(original_image, cv2.COLOR_BGR2GRAY)
    else:
        gray = original_image.copy()
    
    # Sample first section of path
    sample_points = traced_path[:min(sample_length, len(traced_path))]
    
    if len(sample_points) < 2:
        return 3  # Default thickness
    
    # For each point, measure perpendicular thickness
    thicknesses = []
    
    for i in range(len(sample_points) - 1):
        if len(sample_points[i]) != 2 or len(sample_points[i + 1]) != 2:
            continue  # Skip invalid points
        x1, y1 = sample_points[i]
        x2, y2 = sample_points[i + 1]
        
        # Direction vector
        dx = x2 - x1
        dy = y2 - y1
        length = np.sqrt(dx*dx + dy*dy)
        if length == 0:
            continue
        
        # Normalize
        dx_norm = dx / length
        dy_norm = dy / length
        
        # Perpendicular direction
        perp_dx = -dy_norm
        perp_dy = dx_norm
        
        # Measure thickness in perpendicular direction
        # Find edges on both sides
        center_x, center_y = int((x1 + x2) / 2), int((y1 + y2) / 2)
        
        # Search outward in perpendicular direction
        h, w = gray.shape
        max_search = 20
        
        # Find left edge (one side)
        left_edge = None
        for dist in range(1, max_search):
            test_x = int(center_x + perp_dx * dist)
            test_y = int(center_y + perp_dy * dist)
            if 0 <= test_x < w and 0 <= test_y < h:
                # Check if we've left the line (bright pixel)
                if gray[test_y, test_x] > 200:  # Threshold for background
                    left_edge = dist
                    break
        
        # Find right edge (other side)
        right_edge = None
        for dist in range(1, max_search):
            test_x = int(center_x - perp_dx * dist)
            test_y = int(center_y - perp_dy * dist)
            if 0 <= test_x < w and 0 <= test_y < h:
                if gray[test_y, test_x] > 200:
                    right_edge = dist
                    break
        
        if left_edge is not None and right_edge is not None:
            thickness = left_edge + right_edge
            thicknesses.append(thickness)
    
    if thicknesses:
        avg_thickness = np.mean(thicknesses)
        return max(1, int(avg_thickness))
    else:
        return 3  # Default


def find_skeleton_junctions(skeleton):
    """
    Find junction points in the skeleton where multiple lines intersect.
    A junction is a point with 3 or more skeleton neighbors.
    
    Args:
        skeleton: Skeletonized binary image (0 = line, 255 = background)
    
    Returns:
        List of (x, y) junction points
    """
    h, w = skeleton.shape
    junctions = []
    
    # Convert to binary (0 = line, 1 = background for easier checking)
    skeleton_binary = (skeleton < 127).astype(np.uint8)
    
    # Check each pixel
    for y in range(1, h - 1):
        for x in range(1, w - 1):
            if skeleton_binary[y, x] == 0:  # Not a skeleton point
                continue
            
            # Count 8-connected neighbors that are skeleton points
            neighbors = 0
            for dy in [-1, 0, 1]:
                for dx in [-1, 0, 1]:
                    if dx == 0 and dy == 0:
                        continue
                    if skeleton_binary[y + dy, x + dx] == 1:
                        neighbors += 1
            
            # Junction: 3 or more neighbors (endpoint = 1, line = 2, junction = 3+)
            if neighbors >= 3:
                junctions.append((x, y))
    
    return junctions


def detect_collisions_from_deformations(traced_path, user_points, thickness):
    """
    Detect intersections by finding sharp deformations/deviations from the ideal straight line.
    Only flags sharp deviations that indicate actual intersections, not gradual curves.
    
    Args:
        traced_path: List of (x, y) points along the traced line
        user_points: List of (x, y) user-provided points (defines ideal line segments)
        thickness: Line thickness in pixels
    
    Returns:
        List of collision points (x, y) along the path
    """
    if len(user_points) < 2:
        return []
    
    collision_points = []
    # Use a much higher threshold - only flag sharp deviations (actual intersections)
    # Not gradual curves or normal path following
    deviation_threshold = max(thickness * 3, 10)  # Increased threshold
    
    # For each segment between user points, check for SHARP deviations only
    for seg_idx in range(len(user_points) - 1):
        start_pt = user_points[seg_idx]
        end_pt = user_points[seg_idx + 1]
        
        segment_length = np.sqrt((end_pt[0] - start_pt[0])**2 + (end_pt[1] - start_pt[1])**2)
        if segment_length == 0:
            continue
        
        dx = end_pt[0] - start_pt[0]
        dy = end_pt[1] - start_pt[1]
        
        # Find points that belong to this segment (within reasonable distance)
        segment_points = []
        for pt in traced_path:
            # Project point onto line segment
            t = max(0, min(1, ((pt[0] - start_pt[0]) * dx + (pt[1] - start_pt[1]) * dy) / (segment_length**2)))
            
            # Check if point is within the segment bounds (with some margin)
            ideal_x = start_pt[0] + t * dx
            ideal_y = start_pt[1] + t * dy
            dist_along_segment = t * segment_length
            
            # Only consider points that are actually on this segment (not beyond it)
            if dist_along_segment >= -segment_length * 0.1 and dist_along_segment <= segment_length * 1.1:
                deviation = np.sqrt((pt[0] - ideal_x)**2 + (pt[1] - ideal_y)**2)
                segment_points.append((pt, deviation, t))
        
        # Look for sharp deviations (sudden changes, not gradual curves)
        # Check for clusters of high deviations
        if len(segment_points) > 0:
            # Find points with significant deviations
            high_deviation_points = [p for p, dev, t in segment_points if dev > deviation_threshold]
            
            # Only flag if there's a cluster of high deviations (actual intersection)
            # Not just a single point or gradual curve
            if len(high_deviation_points) >= 3:  # Need at least 3 points with high deviation
                # Find the center of the deviation cluster
                avg_x = sum(p[0] for p in high_deviation_points) / len(high_deviation_points)
                avg_y = sum(p[1] for p in high_deviation_points) / len(high_deviation_points)
                
                # Avoid duplicates
                is_duplicate = False
                for cx, cy in collision_points:
                    if np.sqrt((avg_x - cx)**2 + (avg_y - cy)**2) < thickness * 2:
                        is_duplicate = True
                        break
                
                if not is_duplicate:
                    collision_points.append((int(avg_x), int(avg_y)))
    
    return collision_points


def detect_collisions(gray, traced_path, thickness, skeleton=None, user_points=None, collision_threshold=200):
    """
    Detect collision points where the line intersects other objects.
    Uses multiple methods:
    1. Deformations from ideal line (if user_points provided)
    2. Skeleton junctions
    3. All-direction checking
    
    Args:
        gray: Grayscale image
        traced_path: List of (x, y) points along the traced line
        thickness: Line thickness in pixels
        skeleton: Skeletonized image (optional, but recommended for better detection)
        user_points: User-provided points defining ideal line (optional, for deformation detection)
        collision_threshold: Threshold for background
    
    Returns:
        List of collision points (x, y) along the path
    """
    collision_points = []
    
    # Method 1: Use deformations from ideal line (only for sharp deviations/intersections)
    # Disabled for now - too aggressive, was flagging normal path segments
    # if user_points is not None and len(user_points) >= 2:
    #     deformation_collisions = detect_collisions_from_deformations(traced_path, user_points, thickness)
    #     collision_points.extend(deformation_collisions)
    
    # Method 2: Use skeleton junctions if available
    if skeleton is not None:
        junctions = find_skeleton_junctions(skeleton)
        junction_threshold = max(thickness, 5)
        
        for jx, jy in junctions:
            # Check if this junction is near the traced path
            for px, py in traced_path:
                dist = np.sqrt((px - jx)**2 + (py - jy)**2)
                if dist <= junction_threshold:
                    # Avoid duplicates
                    is_duplicate = False
                    for cx, cy in collision_points:
                        if np.sqrt((jx - cx)**2 + (jy - cy)**2) < thickness:
                            is_duplicate = True
                            break
                    
                    if not is_duplicate:
                        collision_points.append((int(jx), int(jy)))
                    break
    
    return collision_points


def _is_intersection_at_point(gray, x, y, thickness, collision_threshold):
    """
    Check if a point is an actual intersection by verifying dark pixels in multiple directions.
    """
    h, w = gray.shape
    if not (0 <= x < w and 0 <= y < h):
        return False
    
    # Check 8 directions around the point
    directions = [
        (1, 0), (1, 1), (0, 1), (-1, 1),
        (-1, 0), (-1, -1), (0, -1), (1, -1)
    ]
    
    check_dist = max(2, thickness // 2)
    dark_directions = 0
    
    for dx, dy in directions:
        check_x = int(x + dx * check_dist)
        check_y = int(y + dy * check_dist)
        
        if 0 <= check_x < w and 0 <= check_y < h:
            if gray[check_y, check_x] < collision_threshold:
                dark_directions += 1
    
    # If 3+ directions have dark pixels, it's likely an intersection
    return dark_directions >= 3


def _has_intersection_in_all_directions(gray, center_x, center_y, half_thickness, 
                                        thickness, collision_threshold):
    """
    Check all directions around a point for intersections (no directional bias).
    """
    h, w = gray.shape
    check_radius = half_thickness + 2  # Check just beyond the line edge
    
    # Check multiple directions (not just perpendicular)
    num_directions = 16  # Check 16 directions for better coverage
    dark_directions = 0
    
    for angle_idx in range(num_directions):
        angle = (2 * np.pi * angle_idx) / num_directions
        dx = np.cos(angle)
        dy = np.sin(angle)
        
        # Check at the edge and beyond
        for dist in [check_radius, check_radius + 2]:
            check_x = int(center_x + dx * dist)
            check_y = int(center_y + dy * dist)
            
            if 0 <= check_x < w and 0 <= check_y < h:
                if gray[check_y, check_x] < collision_threshold:
                    # Verify this is not part of the line itself
                    # Check closer to center - should also be dark if it's the line
                    inner_x = int(center_x + dx * (half_thickness - 1))
                    inner_y = int(center_y + dy * (half_thickness - 1))
                    
                    if 0 <= inner_x < w and 0 <= inner_y < h:
                        inner_value = gray[inner_y, inner_x]
                        # If inner is dark (line) and outer is dark (object), it's an intersection
                        if inner_value < collision_threshold:
                            dark_directions += 1
                            break
    
    # If we find dark pixels in multiple non-adjacent directions, it's likely an intersection
    return dark_directions >= 3


def select_line_pixels(original_image, traced_path, thickness, skeleton=None, user_points=None, collision_threshold=200):
    """
    Select all pixels belonging to the line based on thickness.
    Excludes areas where line edges are in contact with other dark pixels (collisions).
    
    The line is assumed to be crossing other objects from underneath, so when
    the edge of the line touches other dark pixels, exclusion rectangles are created
    to split the line at those collision points.
    
    Args:
        original_image: Original grayscale or BGR image
        traced_path: List of (x, y) points along the traced line
        thickness: Line thickness in pixels
        skeleton: Skeletonized image (optional, but recommended for better collision detection)
        collision_threshold: Threshold for background (pixels brighter than this are background)
    
    Returns:
        Binary mask (255 for line pixels, 0 for background)
    """
    if len(original_image.shape) == 3:
        gray = cv2.cvtColor(original_image, cv2.COLOR_BGR2GRAY)
    else:
        gray = original_image.copy()
    
    h, w = gray.shape
    mask = np.zeros((h, w), dtype=np.uint8)
    
    # Pass 1: Create full line mask based on thickness
    half_thickness = thickness / 2
    
    print(f"  Creating mask from {len(traced_path)} traced points...")
    segments_processed = 0
    
    for i in range(len(traced_path) - 1):
        if len(traced_path[i]) != 2 or len(traced_path[i + 1]) != 2:
            continue
        
        x1, y1 = traced_path[i]
        x2, y2 = traced_path[i + 1]
        
        dx = x2 - x1
        dy = y2 - y1
        length = np.sqrt(dx*dx + dy*dy)
        if length == 0:
            continue
        
        dx_norm = dx / length
        dy_norm = dy / length
        perp_dx = -dy_norm
        perp_dy = dx_norm
        
        # Sample points along the segment (more samples for better coverage)
        num_samples = max(5, int(length * 3))  # Increased sampling
        for j in range(num_samples + 1):
            t = j / num_samples if num_samples > 0 else 0
            center_x = x1 + dx * t
            center_y = y1 + dy * t
            
            # Include pixels on both sides up to half_thickness
            # Use a circular/elliptical region for better coverage
            for side in [-1, 1]:
                for perp_dist in range(int(half_thickness) + 1):
                    test_x = int(center_x + side * perp_dx * perp_dist)
                    test_y = int(center_y + side * perp_dy * perp_dist)
                    
                    if 0 <= test_x < w and 0 <= test_y < h:
                        # Include pixel if it's dark (part of line) OR if it's within the thickness radius
                        # This ensures we get the full line even if some pixels are slightly brighter
                        pixel_value = gray[test_y, test_x]
                        if pixel_value < collision_threshold:
                            mask[test_y, test_x] = 255
        
        segments_processed += 1
    
    print(f"  Processed {segments_processed} segments, mask has {np.sum(mask > 0)} pixels")
    
    # Pass 2: Detect collisions and create exclusion zones
    print("  Detecting collisions...")
    collision_points = detect_collisions(gray, traced_path, thickness, skeleton, user_points, collision_threshold)
    print(f"  Found {len(collision_points)} collision point(s)")
    
    if collision_points:
        # Create exclusion rectangles around collision points
        # Use tighter exclusion zones - only exclude the immediate collision area
        exclusion_size = max(thickness * 1.5, 15)  # Reduced from 3*thickness to 1.5*thickness
        exclusion_width = thickness * 1.5  # Reduced from 2*thickness to 1.5*thickness
        
        for col_x, col_y in collision_points:
            # Find the direction of the line at this collision point
            # Find nearest point in traced_path
            min_dist = float('inf')
            nearest_idx = 0
            for idx, (px, py) in enumerate(traced_path):
                dist = np.sqrt((px - col_x)**2 + (py - col_y)**2)
                if dist < min_dist:
                    min_dist = dist
                    nearest_idx = idx
            
            # Get line direction at this point
            if nearest_idx < len(traced_path) - 1:
                dx = traced_path[nearest_idx + 1][0] - traced_path[nearest_idx][0]
                dy = traced_path[nearest_idx + 1][1] - traced_path[nearest_idx][1]
            elif nearest_idx > 0:
                dx = traced_path[nearest_idx][0] - traced_path[nearest_idx - 1][0]
                dy = traced_path[nearest_idx][1] - traced_path[nearest_idx - 1][1]
            else:
                dx, dy = 1, 0  # Default direction
            
            length = np.sqrt(dx*dx + dy*dy)
            if length > 0:
                dx_norm = dx / length
                dy_norm = dy / length
            else:
                dx_norm, dy_norm = 1, 0
            
            # Create exclusion rectangle perpendicular to line direction
            perp_dx = -dy_norm
            perp_dy = dx_norm
            
            # Rectangle extends along line direction and perpendicular
            rect_length = exclusion_size
            rect_width = exclusion_width
            
            # Create rectangle corners
            corners = []
            for side_len in [-rect_length/2, rect_length/2]:
                for side_width in [-rect_width/2, rect_width/2]:
                    corner_x = int(col_x + dx_norm * side_len + perp_dx * side_width)
                    corner_y = int(col_y + dy_norm * side_len + perp_dy * side_width)
                    corners.append((corner_x, corner_y))
            
            # Fill exclusion rectangle in mask (set to 0)
            # Use a more precise circular exclusion around collision point
            exclusion_radius = exclusion_size / 2
            
            # Only exclude pixels within the exclusion radius of the collision point
            for ex_y in range(max(0, int(col_y - exclusion_radius)), min(h, int(col_y + exclusion_radius) + 1)):
                for ex_x in range(max(0, int(col_x - exclusion_radius)), min(w, int(col_x + exclusion_radius) + 1)):
                    dist_to_collision = np.sqrt((ex_x - col_x)**2 + (ex_y - col_y)**2)
                    if dist_to_collision <= exclusion_radius:
                        mask[ex_y, ex_x] = 0
    
    final_pixels = np.sum(mask > 0)
    print(f"  Final mask has {final_pixels} pixels after exclusions")
    
    return mask


def main():
    parser = argparse.ArgumentParser(
        description='Trace leader lines based on user-provided points'
    )
    parser.add_argument('input_image', type=str,
                       help='Input image path')
    parser.add_argument('-o', '--output', type=str, default=None,
                       help='Output image path (default: adds _traced suffix)')
    parser.add_argument('--points', type=str, required=True,
                       help='Points as "x1,y1 x2,y2 x3,y3" (start, mid, end)')
    parser.add_argument('--show-skeleton', action='store_true',
                       help='Show skeletonized image in output')
    
    args = parser.parse_args()
    
    # Read original image
    print(f"Loading image: {args.input_image}")
    original_img = cv2.imread(str(args.input_image))
    if original_img is None:
        raise ValueError(f"Could not read image: {args.input_image}")
    
    print(f"Image size: {original_img.shape[1]}x{original_img.shape[0]} pixels")
    
    # Parse user points
    points_str = args.points.split()
    if len(points_str) < 2:
        raise ValueError("Need at least 2 points (start and end). Use format: 'x1,y1 x2,y2 [x3,y3 ...]'")
    
    user_points = []
    for pt_str in points_str:
        parts = pt_str.split(',')
        if len(parts) == 2:
            # Normal case: x,y
            try:
                x, y = int(parts[0]), int(parts[1])
                user_points.append((x, y))
            except ValueError as e:
                raise ValueError(f"Invalid point format: '{pt_str}'. Coordinates must be integers. Error: {e}")
        elif len(parts) == 4:
            # Missing space: x1,y1,x2,y2 - split into two points
            try:
                x1, y1 = int(parts[0]), int(parts[1])
                x2, y2 = int(parts[2]), int(parts[3])
                user_points.append((x1, y1))
                user_points.append((x2, y2))
                print(f"  Note: Split '{pt_str}' into two points: ({x1}, {y1}) and ({x2}, {y2})")
            except ValueError as e:
                raise ValueError(f"Invalid point format: '{pt_str}'. Could not parse as two points. Error: {e}")
        else:
            raise ValueError(f"Invalid point format: '{pt_str}'. Expected 'x,y' format. If you have multiple points, separate them with spaces.")
    
    print(f"User provided {len(user_points)} points: {user_points}")
    
    # Step 1: Convert to monochrome in memory
    print("\nStep 1: Converting to monochrome...")
    binary = convert_to_monochrome(original_img)
    
    # Step 2: Skeletonize
    print("Step 2: Skeletonizing image...")
    skeleton = skeletonize_image(binary)
    
    # Step 3: Find nearest skeleton points
    print("Step 3: Finding nearest skeleton points...")
    skeleton_points = []
    for x, y in user_points:
        nearest = find_nearest_skeleton_point(skeleton, x, y)
        if nearest:
            print(f"  User point ({x}, {y}) -> Skeleton point {nearest}")
            skeleton_points.append(nearest)
        else:
            print(f"  Warning: No skeleton point found near ({x}, {y})")
            skeleton_points.append((x, y))  # Use original point as fallback
    
    # Step 4: Trace line between points
    print("Step 4: Tracing line between points...")
    all_traced_points = []
    
    for i in range(len(skeleton_points) - 1):
        if len(skeleton_points[i]) != 2 or len(skeleton_points[i + 1]) != 2:
            print(f"  Warning: Invalid point format at index {i}, skipping segment")
            continue
        start_x, start_y = skeleton_points[i]
        end_x, end_y = skeleton_points[i + 1]
        
        print(f"  Tracing from {skeleton_points[i]} to {skeleton_points[i+1]}...")
        segment_path = trace_between_points(skeleton, start_x, start_y, end_x, end_y)
        
        if segment_path:
            print(f"    Traced {len(segment_path)} points")
            all_traced_points.extend(segment_path)
        else:
            print(f"    Warning: Could not trace between points")
    
    if not all_traced_points:
        print("Error: Could not trace any path")
        return
    
    print(f"Total traced path: {len(all_traced_points)} points")
    
    # Step 5: Measure line thickness from original image
    print("Step 5: Measuring line thickness...")
    thickness = measure_line_thickness(original_img, all_traced_points)
    print(f"  Measured thickness: {thickness} pixels")
    
    # Step 6: Select line pixels based on thickness, handling collisions
    print("Step 6: Selecting line pixels (handling collisions)...")
    line_mask = select_line_pixels(original_img, all_traced_points, thickness, skeleton, user_points)
    
    # Also get collision points for visualization
    if len(original_img.shape) == 3:
        gray = cv2.cvtColor(original_img, cv2.COLOR_BGR2GRAY)
    else:
        gray = original_img.copy()
    collision_points = detect_collisions(gray, all_traced_points, thickness, skeleton, user_points)
    
    # Create output visualization
    output_img = original_img.copy()
    
    # Find and draw mask contours in red
    print("Step 7: Drawing mask contours...")
    contours, _ = cv2.findContours(line_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    print(f"  Found {len(contours)} contour(s)")
    cv2.drawContours(output_img, contours, -1, (0, 0, 255), 2)  # Red contours, 2px thick
    
    # Mark collision points in magenta
    for col_x, col_y in collision_points:
        cv2.circle(output_img, (col_x, col_y), 5, (255, 0, 255), -1)  # Magenta circles
    
    # Draw traced skeleton path in cyan (for comparison)
    if len(all_traced_points) > 1:
        pts = np.array(all_traced_points, dtype=np.int32)
        cv2.polylines(output_img, [pts], False, (255, 255, 0), 1)  # Cyan for skeleton path
    
    # Mark user points in green
    for x, y in user_points:
        cv2.circle(output_img, (x, y), 5, (0, 255, 0), -1)
    
    # Mark skeleton points in blue
    for x, y in skeleton_points:
        cv2.circle(output_img, (x, y), 3, (255, 0, 0), -1)
    
    # If requested, show skeleton
    if args.show_skeleton:
        skeleton_vis = cv2.cvtColor(skeleton, cv2.COLOR_GRAY2BGR)
        # Combine with output
        h, w = output_img.shape[:2]
        skeleton_vis = cv2.resize(skeleton_vis, (w, h))
        output_img = np.hstack([output_img, skeleton_vis])
    
    # Save output
    if args.output is None:
        input_path = Path(args.input_image)
        output_path = input_path.parent / f"{input_path.stem}_traced_points{input_path.suffix}"
    else:
        output_path = args.output
    
    cv2.imwrite(str(output_path), output_img)
    print(f"\nSaved output to: {output_path}")
    
    # Also save the line mask
    mask_path = Path(output_path).parent / f"{Path(output_path).stem}_mask.png"
    cv2.imwrite(str(mask_path), line_mask)
    print(f"Saved line mask to: {mask_path}")


if __name__ == '__main__':
    main()

