"""Utilities for working with AWS Textract results."""

import json
from typing import List, Dict, Tuple, Optional
import cv2
import numpy as np
from pathlib import Path


def parse_textract_blocks(textract_json: dict, image_shape: Tuple[int, int]) -> List[Dict]:
    """
    Parse Textract JSON response and convert to text regions with bounding boxes.
    
    Args:
        textract_json: Textract response dictionary (from analyze_document_json)
        image_shape: (height, width) of the image
        
    Returns:
        List of text region dicts with:
        - 'bbox': (x1, y1, x2, y2) bounding box in pixels
        - 'text': Detected text
        - 'confidence': Confidence score (0-100)
        - 'block_id': Textract block ID
        - 'block_type': 'WORD' or 'LINE'
        - 'mask': Binary mask for the text region
    """
    h, w = image_shape[:2]
    regions = []
    
    blocks = textract_json.get('blocks', [])
    if not blocks:
        blocks = textract_json.get('Blocks', [])
    
    for block in blocks:
        block_type = block.get('BlockType', '')
        
        # Process WORD and LINE blocks
        if block_type in ['WORD', 'LINE']:
            geometry = block.get('Geometry', {})
            bbox = geometry.get('BoundingBox', {})
            
            if not bbox:
                continue
            
            # Textract returns normalized coordinates (0-1)
            left = bbox.get('Left', 0)
            top = bbox.get('Top', 0)
            width = bbox.get('Width', 0)
            height = bbox.get('Height', 0)
            
            # Convert to pixel coordinates
            x1 = int(left * w)
            y1 = int(top * h)
            x2 = int((left + width) * w)
            y2 = int((top + height) * h)
            
            # Ensure coordinates are within image bounds
            x1 = max(0, min(x1, w))
            y1 = max(0, min(y1, h))
            x2 = max(0, min(x2, w))
            y2 = max(0, min(y2, h))
            
            if x2 <= x1 or y2 <= y1:
                continue
            
            text = block.get('Text', '').strip()
            if not text:
                continue
            
            confidence = int(block.get('Confidence', 0))
            block_id = block.get('Id', '')
            
            # Create mask for this region
            mask = np.zeros((h, w), dtype=np.uint8)
            mask[y1:y2, x1:x2] = 255
            
            regions.append({
                'bbox': (x1, y1, x2, y2),
                'text': text,
                'confidence': confidence,
                'block_id': block_id,
                'block_type': block_type,
                'mask': mask
            })
    
    return regions


def group_textract_regions_by_line(regions: List[Dict], 
                                   max_vertical_gap: float = 0.02) -> List[Dict]:
    """
    Group Textract word regions into lines based on vertical alignment.
    
    Args:
        regions: List of word regions from parse_textract_blocks
        max_vertical_gap: Maximum vertical gap as fraction of image height to group words
        
    Returns:
        List of grouped regions, where each group represents a line of text
    """
    if not regions:
        return []
    
    # Sort regions by y-coordinate (top to bottom)
    sorted_regions = sorted(regions, key=lambda r: (r['bbox'][1], r['bbox'][0]))
    
    # Estimate image height from bounding boxes
    max_y = max(r['bbox'][3] for r in regions) if regions else 0
    max_gap_pixels = int(max_vertical_gap * max_y)
    
    groups = []
    current_line = []
    
    for region in sorted_regions:
        if not current_line:
            current_line = [region]
            continue
        
        # Check if this region is on the same line as the last one
        last_region = current_line[-1]
        y1_last = last_region['bbox'][1]
        y1_current = region['bbox'][1]
        
        # Check vertical overlap or small gap
        y_overlap = min(last_region['bbox'][3], region['bbox'][3]) - max(y1_last, y1_current)
        vertical_gap = abs(y1_current - y1_last)
        
        if y_overlap > 0 or vertical_gap <= max_gap_pixels:
            # Same line
            current_line.append(region)
        else:
            # New line - save current line and start new one
            if current_line:
                groups.append(_create_line_group(current_line))
            current_line = [region]
    
    # Add last line
    if current_line:
        groups.append(_create_line_group(current_line))
    
    return groups


def _create_line_group(regions: List[Dict]) -> Dict:
    """Create a grouped region from a list of word regions."""
    if not regions:
        return {}
    
    # Calculate combined bounding box
    x1 = min(r['bbox'][0] for r in regions)
    y1 = min(r['bbox'][1] for r in regions)
    x2 = max(r['bbox'][2] for r in regions)
    y2 = max(r['bbox'][3] for r in regions)
    
    # Combine text
    text = ' '.join(r['text'] for r in sorted(regions, key=lambda r: r['bbox'][0]))
    
    # Average confidence
    avg_confidence = sum(r['confidence'] for r in regions) / len(regions) if regions else 0
    
    # Combine masks
    if regions and 'mask' in regions[0]:
        h, w = regions[0]['mask'].shape
        combined_mask = np.zeros((h, w), dtype=np.uint8)
        for r in regions:
            if 'mask' in r and r['mask'].shape == (h, w):
                combined_mask = np.maximum(combined_mask, r['mask'])
    else:
        combined_mask = None
    
    return {
        'bbox': (x1, y1, x2, y2),
        'text': text,
        'confidence': int(avg_confidence),
        'block_type': 'LINE',
        'mask': combined_mask,
        'word_regions': regions  # Keep individual words for editing
    }


def save_textract_json(textract_response: dict, output_path: str):
    """Save Textract JSON response to file."""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(textract_response, f, indent=2, ensure_ascii=False)


def load_textract_json(json_path: str) -> dict:
    """Load Textract JSON response from file."""
    with open(json_path, 'r', encoding='utf-8') as f:
        return json.load(f)
