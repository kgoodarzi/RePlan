"""Utility modules for iPad segmenter."""

from .geometry import (
    distance, snap_to_point, point_in_polygon,
    polygon_area, polygon_centroid, bounding_box,
    line_length, simplify_polyline
)

__all__ = [
    "distance",
    "snap_to_point", 
    "point_in_polygon",
    "polygon_area",
    "polygon_centroid",
    "bounding_box",
    "line_length",
    "simplify_polyline",
]

