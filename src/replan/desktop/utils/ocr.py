"""OCR (Optical Character Recognition) utilities using Tesseract."""

import re
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
import cv2
import numpy as np

# Try to import pytesseract
try:
    import pytesseract
    
    # Configure Tesseract path for Windows
    TESSERACT_PATHS = [
        r'C:\Program Files\Tesseract-OCR\tesseract.exe',
        r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
        r'C:\Users\*\AppData\Local\Programs\Tesseract-OCR\tesseract.exe',
    ]
    
    for path in TESSERACT_PATHS:
        if '*' in path:
            # Glob pattern
            import glob
            matches = glob.glob(path)
            if matches:
                pytesseract.pytesseract.tesseract_cmd = matches[0]
                break
        elif Path(path).exists():
            pytesseract.pytesseract.tesseract_cmd = path
            break
    
    HAS_TESSERACT = True
except ImportError:
    HAS_TESSERACT = False


# Known prefixes for model aircraft plans
KNOWN_PREFIXES: Dict[str, str] = {
    "F": "Former",
    "R": "Rib",
    "FS": "Fuselage Side",
    "WT": "Wing Tip",
    "T": "Tail",
    "TS": "Tail Surface",
    "M": "Motor Mount",
    "UC": "Undercarriage",
    "B": "Misc Part",
    "L": "Longeron",
    "W": "Wing",
    "E": "Elevator",
    "S": "Spar",
    "N": "Nose",
}


def is_tesseract_available() -> bool:
    """Check if Tesseract is available."""
    if not HAS_TESSERACT:
        return False
    try:
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def extract_text(image: np.ndarray, 
                 preprocess: bool = True) -> str:
    """
    Extract text from an image using OCR.
    
    Args:
        image: Input image (BGR)
        preprocess: Whether to preprocess for better results
        
    Returns:
        Extracted text
    """
    if not is_tesseract_available():
        return ""
    
    # Convert to grayscale
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image
    
    if preprocess:
        # Apply thresholding to improve OCR
        gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    
    try:
        text = pytesseract.image_to_string(gray)
        return text
    except Exception as e:
        print(f"OCR error: {e}")
        return ""


def find_labels(image: np.ndarray) -> Dict[str, Set[str]]:
    """
    Find component labels in an image.
    
    Looks for patterns like:
    - R1, R2, R3 (ribs)
    - F1, F2 (formers)
    - FS1, FS2 (fuselage sides)
    - etc.
    
    Args:
        image: Input image (BGR)
        
    Returns:
        Dictionary mapping prefix to set of found labels
    """
    if not is_tesseract_available():
        return {}
    
    text = extract_text(image)
    
    found: Dict[str, Set[str]] = {}
    
    # Patterns to search for
    patterns = [
        (r'\b([RF])[-\s]?(\d+)\b', None),        # R1, F1, R-1, F 1
        (r'\b(FS)[-\s]?(\d+)\b', None),           # FS1, FS-1
        (r'\b(WT)(\d*)\b', None),                 # WT, WT1
        (r'\b(TS)[-\s]?(\d*)\b', None),           # TS, TS1
        (r'\b([T])[-\s]?(\d+)\b', None),          # T1, T2
        (r'\b(UC)(\d*)\b', None),                 # UC, UC1
        (r'\b([LM])[-\s]?(\d+)\b', None),         # L1, M1
        (r'\bRIB\s*([A-Z0-9]*)\b', 'R'),          # RIB, RIB A
        (r'\bFORMER\s*([A-Z0-9]*)\b', 'F'),       # FORMER, FORMER A
        (r'\b([A-G])[-\s]?(\d*)\b(?=\s|$|[,.])', None),  # A, B, C (formers)
        (r'\b(W)[-\s]?(\d+)\b', None),            # W1 (wing)
        (r'\b(E)[-\s]?(\d+)\b', None),            # E1 (elevator)
        (r'\b(S)[-\s]?(\d+)\b', None),            # S1 (spar)
    ]
    
    for pattern, force_prefix in patterns:
        for match in re.findall(pattern, text, re.IGNORECASE):
            if isinstance(match, tuple):
                prefix = (force_prefix or match[0]).upper()
                suffix = match[1] if len(match) > 1 else ""
                instance = f"{prefix}{suffix}".strip()
            else:
                prefix = (force_prefix or match).upper()
                instance = prefix
            
            if prefix not in found:
                found[prefix] = set()
            if instance:
                found[prefix].add(instance)
    
    return found


def group_labels(labels: Dict[str, Set[str]]) -> List[Tuple[str, str, List[str]]]:
    """
    Group found labels for user selection.
    
    Args:
        labels: Dictionary from find_labels()
        
    Returns:
        List of (prefix, full_name, instances) tuples
    """
    result = []
    
    for prefix in sorted(labels.keys()):
        instances = sorted(labels[prefix])
        full_name = KNOWN_PREFIXES.get(prefix, prefix)
        result.append((prefix, full_name, instances))
    
    return result


def group_text_regions(regions: List[dict], 
                       max_horizontal_gap: float = 0.25,
                       max_vertical_gap: float = 0.4,
                       min_group_size: int = 2,
                       max_group_size: int = 10) -> List[dict]:
    """
    Group nearby text regions into logical textboxes/notes.
    
    Uses a two-stage approach:
    1. First groups regions into lines (horizontally aligned)
    2. Then groups lines into textboxes (vertically aligned with similar left/right edges)
    
    Args:
        regions: List of text region dicts with 'bbox' (x1, y1, x2, y2) and 'text' keys
        max_horizontal_gap: Maximum horizontal gap as fraction of average text height (default 0.25)
        max_vertical_gap: Maximum vertical gap as fraction of average text height (default 0.4)
        min_group_size: Minimum number of regions to form a group (default 2)
        max_group_size: Maximum number of regions in a group to prevent over-grouping (default 10)
        
    Returns:
        List of grouped regions. Each group is a dict with:
        - 'id': Combined ID
        - 'text': Combined text (space-separated)
        - 'bbox': Bounding box encompassing all regions in group
        - 'mask': Combined mask
        - 'regions': List of original region IDs in this group
    """
    if not regions or len(regions) < min_group_size:
        return regions
    
    # Calculate average text height for gap thresholds
    heights = []
    for r in regions:
        bbox = r.get('bbox', (0, 0, 0, 0))
        if len(bbox) == 4:
            heights.append(bbox[3] - bbox[1])
    avg_height = sum(heights) / len(heights) if heights else 20
    
    # Convert to list of dicts for easier processing
    region_data = []
    for i, r in enumerate(regions):
        bbox = r.get('bbox', (0, 0, 0, 0))
        if len(bbox) == 4:
            x1, y1, x2, y2 = bbox
            region_data.append({
                'index': i,
                'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2,
                'cx': (x1 + x2) / 2,  # Center x
                'cy': (y1 + y2) / 2,  # Center y
                'width': x2 - x1,
                'height': y2 - y1,
                'region': r
            })
    
    if len(region_data) < min_group_size:
        return regions
    
    # Stage 1: Group regions into lines (horizontally aligned)
    lines = []
    used_indices = set()
    
    for i, r1 in enumerate(region_data):
        if i in used_indices:
            continue
        
        # Start a new line with this region
        line = [r1]
        used_indices.add(i)
        
        # Find horizontally aligned regions (same line)
        for j, r2 in enumerate(region_data):
            if j in used_indices or j == i:
                continue
            
            # Check if r2 is on the same line as r1
            y_overlap = min(r1['y2'], r2['y2']) - max(r1['y1'], r2['y1'])
            y_overlap_ratio = y_overlap / min(r1['height'], r2['height']) if min(r1['height'], r2['height']) > 0 else 0
            
            # Require significant vertical overlap (at least 40%) for same line
            if y_overlap_ratio > 0.4:
                # Check horizontal gap
                if r1['x2'] < r2['x1']:
                    gap = r2['x1'] - r1['x2']
                elif r2['x2'] < r1['x1']:
                    gap = r1['x1'] - r2['x2']
                else:
                    gap = 0  # Overlapping horizontally
                
                # If gap is reasonable, add to line
                if gap <= avg_height * max_horizontal_gap * 2:  # More lenient for same line
                    line.append(r2)
                    used_indices.add(j)
        
        # Sort line by x-coordinate (left to right)
        line.sort(key=lambda x: x['x1'])
        lines.append(line)
    
    # Stage 2: Group lines into textboxes (vertically aligned with similar edges)
    textboxes = []
    used_line_indices = set()
    
    for i, line1 in enumerate(lines):
        if i in used_line_indices:
            continue
        
        # Start a new textbox with this line
        textbox_lines = [line1]
        used_line_indices.add(i)
        
        # Calculate textbox bounds from current lines
        textbox_x1 = min(r['x1'] for r in line1)
        textbox_x2 = max(r['x2'] for r in line1)
        textbox_y1 = min(r['y1'] for r in line1)
        textbox_y2 = max(r['y2'] for r in line1)
        
        # Find other lines that belong to the same textbox
        changed = True
        while changed:
            changed = False
            for j, line2 in enumerate(lines):
                if j in used_line_indices or j == i:
                    continue
                
                # Calculate line2 bounds
                line2_x1 = min(r['x1'] for r in line2)
                line2_x2 = max(r['x2'] for r in line2)
                line2_y1 = min(r['y1'] for r in line2)
                line2_y2 = max(r['y2'] for r in line2)
                
                # Check if line2 belongs to the same textbox
                # Criteria:
                # 1. Left edges are aligned (within tolerance)
                # 2. Right edges are aligned (within tolerance) OR significant horizontal overlap
                # 3. Vertical gap is reasonable
                
                left_edge_diff = abs(textbox_x1 - line2_x1)
                right_edge_diff = abs(textbox_x2 - line2_x2)
                
                # Check horizontal overlap
                x_overlap = min(textbox_x2, line2_x2) - max(textbox_x1, line2_x1)
                x_overlap_ratio = x_overlap / min(textbox_x2 - textbox_x1, line2_x2 - line2_x1) if min(textbox_x2 - textbox_x1, line2_x2 - line2_x1) > 0 else 0
                
                # Check vertical gap
                if textbox_y2 < line2_y1:
                    vertical_gap = line2_y1 - textbox_y2
                elif line2_y2 < textbox_y1:
                    vertical_gap = textbox_y1 - line2_y2
                else:
                    vertical_gap = 0  # Overlapping vertically
                
                # Determine if lines belong to same textbox
                # Left edges aligned AND (right edges aligned OR significant overlap) AND reasonable vertical gap
                edge_tolerance = avg_height * 0.5  # More lenient for textbox alignment
                
                if (left_edge_diff <= edge_tolerance and 
                    (right_edge_diff <= edge_tolerance or x_overlap_ratio > 0.3) and
                    vertical_gap <= avg_height * max_vertical_gap * 1.5):  # More lenient for multi-line textboxes
                    
                    textbox_lines.append(line2)
                    used_line_indices.add(j)
                    changed = True
                    
                    # Update textbox bounds
                    textbox_x1 = min(textbox_x1, line2_x1)
                    textbox_x2 = max(textbox_x2, line2_x2)
                    textbox_y1 = min(textbox_y1, line2_y1)
                    textbox_y2 = max(textbox_y2, line2_y2)
        
        # Flatten textbox lines into a single group of regions
        textbox_regions = []
        for line in textbox_lines:
            textbox_regions.extend(line)
        
        # Only create textbox if it has minimum size
        if len(textbox_regions) >= min_group_size and len(textbox_regions) <= max_group_size:
            textboxes.append(textbox_regions)
        else:
            # Return individual regions that don't form valid textboxes
            for line in textbox_lines:
                for r in line:
                    used_indices.discard(r['index'])
    
    # Build final groups from textboxes
    groups = textboxes
    
    # Create grouped regions
    grouped_regions = []
    
    # Add grouped regions
    for group in groups:
        # Calculate combined bounding box
        x1 = min(r['x1'] for r in group)
        y1 = min(r['y1'] for r in group)
        x2 = max(r['x2'] for r in group)
        y2 = max(r['y2'] for r in group)
        
        # Combine text (space-separated, sorted by position)
        texts = []
        for r in sorted(group, key=lambda x: (x['y1'], x['x1'])):  # Sort top-to-bottom, left-to-right
            text = r['region'].get('text', '').strip()
            if text:
                texts.append(text)
        
        combined_text = ' '.join(texts) if texts else f"text_group_{len(grouped_regions)}"
        
        # Combine masks
        first_region = group[0]['region']
        mask = first_region.get('mask')
        if mask is not None:
            h, w = mask.shape[:2]
            combined_mask = np.zeros((h, w), dtype=np.uint8)
            for r in group:
                r_mask = r['region'].get('mask')
                if r_mask is not None and r_mask.shape == (h, w):
                    combined_mask = np.maximum(combined_mask, r_mask)
        else:
            # Create mask from bounding box if no mask available
            h, w = first_region.get('mask', np.zeros((100, 100))).shape[:2] if first_region.get('mask') is not None else (y2 - y1, x2 - x1)
            combined_mask = np.zeros((h, w), dtype=np.uint8)
            combined_mask[y1:min(y2, h), x1:min(x2, w)] = 255
        
        # Get region IDs
        region_ids = [r['region'].get('id', f"region_{r['index']}") for r in group]
        
        grouped_regions.append({
            'id': f"group_{len(grouped_regions)}",
            'text': combined_text,
            'bbox': (x1, y1, x2, y2),
            'mask': combined_mask,
            'regions': region_ids,
            'mode': 'auto_grouped',
            'confidence': max(r['region'].get('confidence', 0) for r in group)
        })
    
    # Add ungrouped regions (regions that didn't form valid textboxes)
    for i, r_data in enumerate(region_data):
        if i not in used_indices:
            grouped_regions.append(r_data['region'])
    
    return grouped_regions


def scan_pages_for_labels(images: List[np.ndarray],
                          progress_callback: callable = None) -> Dict[str, Set[str]]:
    """
    Scan multiple pages for labels.
    
    Args:
        images: List of page images
        progress_callback: Optional callback(current, total) for progress
        
    Returns:
        Combined dictionary of found labels
    """
    all_found: Dict[str, Set[str]] = {}
    
    for i, image in enumerate(images):
        if progress_callback:
            progress_callback(i + 1, len(images))
        
        page_labels = find_labels(image)
        
        for prefix, instances in page_labels.items():
            if prefix not in all_found:
                all_found[prefix] = set()
            all_found[prefix].update(instances)
    
    return all_found


