"""Geometry utility functions.

This module is 100% portable from desktop - pure math, no dependencies.
"""

import math
from typing import List, Tuple, Optional


def distance(p1: Tuple[int, int], p2: Tuple[int, int]) -> float:
    """Calculate Euclidean distance between two points."""
    return math.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)


def snap_to_point(current: Tuple[int, int], 
                  target: Tuple[int, int],
                  snap_distance: int) -> Optional[Tuple[int, int]]:
    """
    Snap to target point if within snap distance.
    
    Returns:
        Target point if within snap distance, None otherwise.
    """
    if distance(current, target) <= snap_distance:
        return target
    return None


def point_in_polygon(point: Tuple[int, int], 
                     polygon: List[Tuple[int, int]]) -> bool:
    """
    Check if a point is inside a polygon using ray casting.
    
    Args:
        point: (x, y) point to test
        polygon: List of (x, y) vertices
        
    Returns:
        True if point is inside polygon
    """
    x, y = point
    n = len(polygon)
    inside = False
    
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    
    return inside


def polygon_area(polygon: List[Tuple[int, int]]) -> float:
    """
    Calculate the area of a polygon using the shoelace formula.
    
    Args:
        polygon: List of (x, y) vertices
        
    Returns:
        Area (always positive)
    """
    n = len(polygon)
    if n < 3:
        return 0.0
    
    area = 0.0
    j = n - 1
    for i in range(n):
        area += (polygon[j][0] + polygon[i][0]) * (polygon[j][1] - polygon[i][1])
        j = i
    
    return abs(area / 2.0)


def polygon_centroid(polygon: List[Tuple[int, int]]) -> Tuple[float, float]:
    """
    Calculate the centroid of a polygon.
    
    Args:
        polygon: List of (x, y) vertices
        
    Returns:
        (cx, cy) centroid coordinates
    """
    n = len(polygon)
    if n == 0:
        return (0.0, 0.0)
    if n == 1:
        return (float(polygon[0][0]), float(polygon[0][1]))
    if n == 2:
        return ((polygon[0][0] + polygon[1][0]) / 2,
                (polygon[0][1] + polygon[1][1]) / 2)
    
    area = polygon_area(polygon)
    if area == 0:
        # Degenerate polygon, return average of points
        cx = sum(p[0] for p in polygon) / n
        cy = sum(p[1] for p in polygon) / n
        return (cx, cy)
    
    cx = 0.0
    cy = 0.0
    j = n - 1
    for i in range(n):
        cross = polygon[j][0] * polygon[i][1] - polygon[i][0] * polygon[j][1]
        cx += (polygon[j][0] + polygon[i][0]) * cross
        cy += (polygon[j][1] + polygon[i][1]) * cross
        j = i
    
    cx /= (6.0 * area)
    cy /= (6.0 * area)
    
    return (abs(cx), abs(cy))


def bounding_box(points: List[Tuple[int, int]]) -> Tuple[int, int, int, int]:
    """
    Get bounding box of a set of points.
    
    Returns:
        (x_min, y_min, x_max, y_max)
    """
    if not points:
        return (0, 0, 0, 0)
    
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    
    return (min(xs), min(ys), max(xs), max(ys))


def line_length(points: List[Tuple[int, int]]) -> float:
    """Calculate total length of a polyline."""
    if len(points) < 2:
        return 0.0
    
    total = 0.0
    for i in range(len(points) - 1):
        total += distance(points[i], points[i + 1])
    
    return total


def simplify_polyline(points: List[Tuple[int, int]], 
                      tolerance: float) -> List[Tuple[int, int]]:
    """
    Simplify a polyline using Douglas-Peucker algorithm.
    
    Args:
        points: List of (x, y) points
        tolerance: Maximum allowed deviation
        
    Returns:
        Simplified list of points
    """
    if len(points) <= 2:
        return points
    
    # Find the point with maximum distance from the line between first and last
    max_dist = 0
    max_idx = 0
    
    for i in range(1, len(points) - 1):
        dist = _point_line_distance(points[i], points[0], points[-1])
        if dist > max_dist:
            max_dist = dist
            max_idx = i
    
    # If max distance is greater than tolerance, recursively simplify
    if max_dist > tolerance:
        left = simplify_polyline(points[:max_idx + 1], tolerance)
        right = simplify_polyline(points[max_idx:], tolerance)
        return left[:-1] + right
    else:
        return [points[0], points[-1]]


def _point_line_distance(point: Tuple[int, int],
                         line_start: Tuple[int, int],
                         line_end: Tuple[int, int]) -> float:
    """Calculate perpendicular distance from point to line."""
    x0, y0 = point
    x1, y1 = line_start
    x2, y2 = line_end
    
    dx = x2 - x1
    dy = y2 - y1
    
    if dx == 0 and dy == 0:
        return distance(point, line_start)
    
    t = max(0, min(1, ((x0 - x1) * dx + (y0 - y1) * dy) / (dx * dx + dy * dy)))
    
    proj_x = x1 + t * dx
    proj_y = y1 + t * dy
    
    return distance(point, (int(proj_x), int(proj_y)))

