"""Parametric part generation for formers, ribs, and other standard parts."""

import numpy as np
import cv2
from typing import List, Tuple, Optional
from dataclasses import dataclass

from replan.desktop.models import SegmentElement, ObjectInstance, SegmentedObject, ObjectAttributes


@dataclass
class RibParameters:
    """Parameters for generating a rib."""
    chord: float  # Width in inches
    thickness: float  # Thickness in inches
    lightening_holes: List[Tuple[float, float, float]] = None  # List of (x, y, radius) in inches
    tabs: List[Tuple[float, float, float, float]] = None  # List of (x, y, width, height) in inches
    
    def __post_init__(self):
        if self.lightening_holes is None:
            self.lightening_holes = []
        if self.tabs is None:
            self.tabs = []


@dataclass
class FormerParameters:
    """Parameters for generating a former."""
    diameter: float  # Outer diameter in inches
    thickness: float  # Wall thickness in inches
    lightening_holes: List[Tuple[float, float, float]] = None  # List of (x, y, radius) in inches
    cutouts: List[Tuple[float, float, float, float]] = None  # List of (x, y, width, height) in inches
    
    def __post_init__(self):
        if self.lightening_holes is None:
            self.lightening_holes = []
        if self.cutouts is None:
            self.cutouts = []


class ParametricPartGenerator:
    """Generates parts from parameters."""
    
    def __init__(self, dpi: float = 150.0):
        """
        Initialize the generator.
        
        Args:
            dpi: DPI for converting inches to pixels
        """
        self.dpi = dpi
    
    def inches_to_pixels(self, inches: float) -> int:
        """Convert inches to pixels."""
        return int(inches * self.dpi)
    
    def generate_rib(self, params: RibParameters) -> SegmentedObject:
        """
        Generate a rib from parameters.
        
        Args:
            params: Rib parameters
            
        Returns:
            SegmentedObject representing the rib
        """
        # Convert to pixels
        chord_px = self.inches_to_pixels(params.chord)
        thickness_px = self.inches_to_pixels(params.thickness)
        
        # Create base rectangle mask
        mask = np.zeros((thickness_px, chord_px), dtype=np.uint8)
        mask.fill(255)
        
        # Cut out lightening holes
        for x_in, y_in, radius_in in params.lightening_holes:
            x = self.inches_to_pixels(x_in)
            y = self.inches_to_pixels(y_in)
            radius = self.inches_to_pixels(radius_in)
            cv2.circle(mask, (x, y), radius, 0, -1)
        
        # Add tabs (extend mask)
        for x_in, y_in, w_in, h_in in params.tabs:
            x = self.inches_to_pixels(x_in)
            y = self.inches_to_pixels(y_in)
            w = self.inches_to_pixels(w_in)
            h = self.inches_to_pixels(h_in)
            # Extend mask for tab
            if 0 <= y < thickness_px and 0 <= x < chord_px:
                tab_h = min(h, thickness_px - y)
                tab_w = min(w, chord_px - x)
                if tab_h > 0 and tab_w > 0:
                    mask[y:y+tab_h, x:x+tab_w] = 255
        
        # Create element
        elem = SegmentElement(
            element_id="",
            category="rib",
            mode="rect",
            points=[(0, 0), (chord_px, 0), (chord_px, thickness_px), (0, thickness_px)],
            mask=mask
        )
        
        # Create instance
        inst = ObjectInstance(
            instance_id="",
            instance_num=1,
            page_id="",
            elements=[elem],
            attributes=ObjectAttributes(
                width=params.chord,
                height=params.thickness,
                obj_type="rib"
            )
        )
        
        # Create object
        obj = SegmentedObject(
            object_id="",
            name=f"Rib {params.chord}\"x{params.thickness}\"",
            category="rib",
            instances=[inst]
        )
        
        return obj
    
    def generate_former(self, params: FormerParameters) -> SegmentedObject:
        """
        Generate a former from parameters.
        
        Args:
            params: Former parameters
            
        Returns:
            SegmentedObject representing the former
        """
        # Convert to pixels
        diameter_px = self.inches_to_pixels(params.diameter)
        thickness_px = self.inches_to_pixels(params.thickness)
        radius_px = diameter_px // 2
        
        # Create circular mask
        mask = np.zeros((diameter_px, diameter_px), dtype=np.uint8)
        center = (radius_px, radius_px)
        cv2.circle(mask, center, radius_px, 255, -1)
        
        # Cut out inner circle (hollow former)
        inner_radius = radius_px - thickness_px
        if inner_radius > 0:
            cv2.circle(mask, center, inner_radius, 0, -1)
        
        # Cut out lightening holes
        for x_in, y_in, radius_in in params.lightening_holes:
            x = self.inches_to_pixels(x_in) + radius_px
            y = self.inches_to_pixels(y_in) + radius_px
            radius = self.inches_to_pixels(radius_in)
            cv2.circle(mask, (x, y), radius, 0, -1)
        
        # Cut out rectangular cutouts
        for x_in, y_in, w_in, h_in in params.cutouts:
            x = self.inches_to_pixels(x_in) + radius_px
            y = self.inches_to_pixels(y_in) + radius_px
            w = self.inches_to_pixels(w_in)
            h = self.inches_to_pixels(h_in)
            cv2.rectangle(mask, (x, y), (x + w, y + h), 0, -1)
        
        # Create element with circular points
        points = []
        num_points = 64  # Smooth circle
        for i in range(num_points):
            angle = 2 * np.pi * i / num_points
            px = int(center[0] + radius_px * np.cos(angle))
            py = int(center[1] + radius_px * np.sin(angle))
            points.append((px, py))
        
        elem = SegmentElement(
            element_id="",
            category="former",
            mode="polyline",
            points=points,
            mask=mask
        )
        
        # Create instance
        inst = ObjectInstance(
            instance_id="",
            instance_num=1,
            page_id="",
            elements=[elem],
            attributes=ObjectAttributes(
                width=params.diameter,
                height=params.diameter,
                depth=params.thickness,
                obj_type="former"
            )
        )
        
        # Create object
        obj = SegmentedObject(
            object_id="",
            name=f"Former {params.diameter}\"",
            category="former",
            instances=[inst]
        )
        
        return obj
