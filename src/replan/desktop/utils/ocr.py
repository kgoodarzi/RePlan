"""OCR (Optical Character Recognition) utilities using Tesseract."""

import re
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional, TYPE_CHECKING
import cv2
import numpy as np

if TYPE_CHECKING:
    from .ocr_backends import OCRBackend

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


def detect_textboxes_with_whitespace(image: np.ndarray,
                                     min_whitespace_ratio: float = 0.3,
                                     min_textbox_size: int = 50) -> List[Tuple[int, int, int, int]]:
    """
    Detect textboxes by finding regions with text content surrounded by clear white space.
    
    This approach focuses on finding actual textboxes (like notes/labels) that are
    isolated from structural elements, rather than trying to OCR everything.
    
    Args:
        image: Input grayscale image
        min_whitespace_ratio: Minimum ratio of white space around textbox (default 0.3 = 30%)
        min_textbox_size: Minimum size of textbox in pixels (default 50)
        
    Returns:
        List of (x, y, width, height) bounding boxes for textboxes with white space
    """
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image
    
    h, w = gray.shape
    textboxes = []
    
    # Threshold to find text (dark pixels)
    # Use adaptive threshold to handle varying lighting
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    
    # Find contours of text regions
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    for contour in contours:
        # Get bounding box
        x, y, bw, bh = cv2.boundingRect(contour)
        
        # Skip very small regions
        if bw < min_textbox_size or bh < min_textbox_size:
            continue
        
        # Expand bounding box to check for white space around it
        # Add padding proportional to textbox size
        padding = max(bw, bh) * 0.5  # 50% padding
        check_x1 = max(0, int(x - padding))
        check_y1 = max(0, int(y - padding))
        check_x2 = min(w, int(x + bw + padding))
        check_y2 = min(h, int(y + bh + padding))
        
        # Extract region to check for white space
        check_region = gray[check_y1:check_y2, check_x1:check_x2]
        if check_region.size == 0:
            continue
        
        # Calculate white space ratio
        # White space = pixels above threshold (light background)
        _, white_mask = cv2.threshold(check_region, 200, 255, cv2.THRESH_BINARY)
        white_pixels = np.sum(white_mask > 0)
        total_pixels = check_region.size
        whitespace_ratio = white_pixels / total_pixels if total_pixels > 0 else 0
        
        # Also check border regions specifically
        border_width = max(5, int(min(bw, bh) * 0.2))  # 20% of smallest dimension, min 5px
        border_region = np.zeros_like(check_region)
        border_region[:border_width, :] = 255  # Top
        border_region[-border_width:, :] = 255  # Bottom
        border_region[:, :border_width] = 255  # Left
        border_region[:, -border_width:] = 255  # Right
        
        border_mask = (white_mask > 0) & (border_region > 0)
        border_whitespace = np.sum(border_mask) / np.sum(border_region > 0) if np.sum(border_region > 0) > 0 else 0
        
        # Require both overall white space and border white space
        if whitespace_ratio >= min_whitespace_ratio and border_whitespace >= min_whitespace_ratio:
            textboxes.append((x, y, bw, bh))
    
    # Merge overlapping textboxes
    merged_textboxes = []
    for x, y, bw, bh in textboxes:
        merged = False
        for i, (mx, my, mw, mh) in enumerate(merged_textboxes):
            # Check if textboxes overlap significantly
            overlap_x = max(0, min(x + bw, mx + mw) - max(x, mx))
            overlap_y = max(0, min(y + bh, my + mh) - max(y, my))
            overlap_area = overlap_x * overlap_y
            area1 = bw * bh
            area2 = mw * mh
            min_area = min(area1, area2)
            
            # If overlap is significant (>30% of smaller box), merge
            if overlap_area > min_area * 0.3:
                new_x = min(x, mx)
                new_y = min(y, my)
                new_w = max(x + bw, mx + mw) - new_x
                new_h = max(y + bh, my + mh) - new_y
                merged_textboxes[i] = (new_x, new_y, new_w, new_h)
                merged = True
                break
        
        if not merged:
            merged_textboxes.append((x, y, bw, bh))
    
    return merged_textboxes


def detect_text_dense_regions(image: np.ndarray, 
                                min_text_density: float = 0.02,
                                window_size: int = 100) -> List[Tuple[int, int, int, int]]:
    """
    Legacy function - now uses textbox detection with white space.
    
    Kept for backward compatibility but delegates to detect_textboxes_with_whitespace.
    """
    return detect_textboxes_with_whitespace(image, min_whitespace_ratio=0.3, min_textbox_size=50)


def load_false_positive_patterns(config_path: str = None) -> List[str]:
    """
    Load false positive patterns from a config file.
    
    Args:
        config_path: Optional path to .txt file with patterns (one per line).
                     If None, looks for 'ocr_false_positives.txt' in project root.
    
    Returns:
        List of patterns to filter (empty list if file doesn't exist)
    """
    if config_path is None:
        # Try to find config file in project root or current directory
        import os
        from pathlib import Path
        
        # Check current directory and parent directories
        current_dir = Path.cwd()
        possible_paths = [
            current_dir / 'ocr_false_positives.txt',
            current_dir.parent / 'ocr_false_positives.txt',
            Path.home() / '.replan_ocr_false_positives.txt',
        ]
        
        for path in possible_paths:
            if path.exists():
                config_path = str(path)
                break
        
        if config_path is None:
            return []  # No config file found, return empty list
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            patterns = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
            return patterns
    except FileNotFoundError:
        return []
    except Exception as e:
        print(f"Warning: Could not load false positive patterns from {config_path}: {e}")
        return []


def filter_structural_false_positives(regions: List[dict], 
                                      image: np.ndarray,
                                      false_positive_patterns: List[str] = None) -> List[dict]:
    """
    Filter out false positives that are structural elements, not text.
    
    Filters based on:
    - Character spacing consistency (real text has uniform spacing)
    - Text size consistency within regions
    - Optional false positive patterns from config file
    
    Args:
        regions: List of text region dicts
        image: Original image for context
        false_positive_patterns: Optional list of patterns to filter (loaded from config if None)
        
    Returns:
        Filtered list of regions
    """
    if not regions:
        return regions
    
    # Load false positive patterns from config file if not provided
    if false_positive_patterns is None:
        false_positive_patterns = load_false_positive_patterns()
    
    filtered = []
    
    # Calculate average text characteristics for consistency checking
    heights = []
    widths = []
    for r in regions:
        bbox = r.get('bbox', (0, 0, 0, 0))
        if len(bbox) == 4:
            x1, y1, x2, y2 = bbox
            heights.append(y2 - y1)
            widths.append(x2 - x1)
    
    if heights:
        avg_height = sum(heights) / len(heights)
        avg_width = sum(widths) / len(widths)
        height_std = np.std(heights) if len(heights) > 1 else 0
    else:
        avg_height = 20
        avg_width = 50
        height_std = 0
    
    for r in regions:
        text = r.get('text', '').strip()
        bbox = r.get('bbox', (0, 0, 0, 0))
        
        if not text or len(bbox) != 4:
            continue
        
        x1, y1, x2, y2 = bbox
        height = y2 - y1
        width = x2 - x1
        
        # Filter based on config file patterns (case-insensitive)
        is_false_positive = False
        text_upper = text.upper()
        for pattern in false_positive_patterns:
            # Support both exact match and regex patterns
            if pattern.startswith('^') or '*' in pattern:
                # Treat as regex pattern
                try:
                    if re.match(pattern, text, re.IGNORECASE):
                        is_false_positive = True
                        break
                except re.error:
                    # Invalid regex, treat as literal
                    if text_upper == pattern.upper():
                        is_false_positive = True
                        break
            else:
                # Exact match
                if text_upper == pattern.upper():
                    is_false_positive = True
                    break
        
        if is_false_positive:
            continue
        
        # Check if region is connected to structural lines (for short text)
        if len(text) <= 3:
            # Analyze the region to see if it's connected to structural lines
            # Extract region from image with padding to check connectivity
            try:
                padding = 10
                check_x1 = max(0, x1 - padding)
                check_y1 = max(0, y1 - padding)
                check_x2 = min(image.shape[1], x2 + padding)
                check_y2 = min(image.shape[0], y2 + padding)
                
                region_img = image[check_y1:check_y2, check_x1:check_x2]
                if region_img.size > 0:
                    # Convert to grayscale if needed
                    if len(region_img.shape) == 3:
                        region_gray = cv2.cvtColor(region_img, cv2.COLOR_BGR2GRAY)
                    else:
                        region_gray = region_img
                    
                    # Check for line-like structures (high edge density suggests structural lines)
                    edges = cv2.Canny(region_gray, 50, 150)
                    edge_density = np.sum(edges > 0) / (region_gray.size) if region_gray.size > 0 else 0
                    
                    # If edge density is very high (>40%), likely structural lines, not text
                    if edge_density > 0.4:
                        continue
                    
                    # Check if region has many intersecting lines (structural pattern)
                    # Use HoughLinesP to detect line segments
                    lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=5, minLineLength=5, maxLineGap=2)
                    if lines is not None and len(lines) > 3:  # More than 3 line segments suggests structure
                        continue
            except:
                pass
        
        # Filter based on size consistency - text in plans is usually uniform
        # If height deviates significantly from average, might be structural
        if heights and height_std > 0:
            height_z_score = abs(height - avg_height) / height_std if height_std > 0 else 0
            # If more than 2 standard deviations from mean, likely not uniform text
            if height_z_score > 2.0 and len(text) <= 2:
                continue
        
        # Filter very small single/double characters that are likely structural
        if len(text) <= 2 and height < avg_height * 0.5:
            continue
        
        # Filter regions that are too wide relative to text length (likely lines/structure)
        if len(text) > 0:
            char_width = width / len(text) if len(text) > 0 else width
            # If characters are unusually wide, might be structural
            if char_width > avg_height * 2.0 and len(text) <= 3:
                continue
        
        # Filter single/double character regions that are likely structural labels (R1, R2, etc.)
        # These are usually smaller and isolated
        if len(text) <= 2 and height < avg_height * 0.7:
            # Check if it's a common structural label pattern
            if re.match(r'^[RFWTSEBLMNUC][0-9]*$', text, re.IGNORECASE):
                # These are likely part labels, not text notes - skip them
                continue
        
        filtered.append(r)
    
    return filtered


def analyze_text_characteristics(regions: List[dict]) -> dict:
    """
    Analyze text characteristics to determine uniformity.
    
    Returns statistics about text size, spacing, etc. to help filter false positives.
    
    Args:
        regions: List of text region dicts
        
    Returns:
        Dictionary with statistics: avg_height, avg_width, height_std, width_std, etc.
    """
    if not regions:
        return {}
    
    heights = []
    widths = []
    char_counts = []
    
    for r in regions:
        bbox = r.get('bbox', (0, 0, 0, 0))
        text = r.get('text', '').strip()
        
        if len(bbox) == 4 and text:
            x1, y1, x2, y2 = bbox
            heights.append(y2 - y1)
            widths.append(x2 - x1)
            char_counts.append(len(text))
    
    if not heights:
        return {}
    
    return {
        'avg_height': sum(heights) / len(heights),
        'avg_width': sum(widths) / len(widths),
        'height_std': np.std(heights) if len(heights) > 1 else 0,
        'width_std': np.std(widths) if len(widths) > 1 else 0,
        'avg_chars': sum(char_counts) / len(char_counts) if char_counts else 0,
        'total_regions': len(regions)
    }


def group_text_regions(regions: List[dict], 
                       max_horizontal_gap: float = 0.25,
                       max_vertical_gap: float = 0.4,
                       min_group_size: int = 2,
                       max_group_size: int = 50,
                       max_group_width: float = 0.3,
                       max_group_height: float = 0.2) -> List[dict]:
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
        max_group_size: Maximum number of regions in a group to prevent over-grouping (default 50)
        max_group_width: Maximum group width as fraction of image width (default 0.3 = 30%)
        max_group_height: Maximum group height as fraction of image height (default 0.2 = 20%)
        
    Returns:
        List of grouped regions. Each group is a dict with:
        - 'id': Combined ID
        - 'text': Combined text (space-separated)
        - 'bbox': Bounding box encompassing all regions in group
        - 'mask': Combined mask
        - 'regions': List of original region IDs in this group
    """
    # Allow single regions if min_group_size is 1 (for fragmented text grouping)
    if not regions:
        return regions
    if min_group_size > 1 and len(regions) < min_group_size:
        return regions
    
    # Calculate average text height for gap thresholds
    heights = []
    image_width = 0
    image_height = 0
    for r in regions:
        bbox = r.get('bbox', (0, 0, 0, 0))
        if len(bbox) == 4:
            heights.append(bbox[3] - bbox[1])
            # Estimate image dimensions from bounding boxes
            image_width = max(image_width, bbox[2])
            image_height = max(image_height, bbox[3])
    
    avg_height = sum(heights) / len(heights) if heights else 20
    
    # Absolute maximum distances (in pixels) to prevent over-grouping
    max_horizontal_gap_pixels = max(avg_height * max_horizontal_gap * 2.0, avg_height * 1.5, 50)  # Stricter: 50px or 1.5x height
    max_vertical_gap_pixels = max(avg_height * max_vertical_gap * 2.0, avg_height * 2.0, 60)  # Stricter: 60px or 2x height
    max_group_width_pixels = image_width * max_group_width if image_width > 0 else 1000
    max_group_height_pixels = image_height * max_group_height if image_height > 0 else 500
    
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
            
            # Require significant vertical overlap (at least 40%) for same line - stricter
            # Also check if regions are on similar y-level (center y within line height)
            y_center_diff = abs(r1['cy'] - r2['cy'])
            same_line_by_center = y_center_diff <= avg_height * 0.6  # Stricter: centers within 0.6x line height
            
            if y_overlap_ratio > 0.4 or same_line_by_center:  # Stricter: require 40% overlap
                # Check horizontal gap
                if r1['x2'] < r2['x1']:
                    gap = r2['x1'] - r1['x2']
                elif r2['x2'] < r1['x1']:
                    gap = r1['x1'] - r2['x2']
                else:
                    gap = 0  # Overlapping horizontally
                
                # Stricter gap tolerance with absolute maximum
                if gap <= max_horizontal_gap_pixels:
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
                
                # Stricter criteria for textbox grouping:
                # Calculate edge tolerance - stricter alignment required
                edge_tolerance = max(avg_height * 1.0, 30)  # Stricter: 30px or 1x avg height
                
                # Check if lines have similar width (within 30% difference) - stricter
                textbox_width = textbox_x2 - textbox_x1
                line2_width = line2_x2 - line2_x1
                width_ratio = min(textbox_width, line2_width) / max(textbox_width, line2_width) if max(textbox_width, line2_width) > 0 else 0
                
                # Check if grouping would exceed maximum group dimensions
                potential_x1 = min(textbox_x1, line2_x1)
                potential_x2 = max(textbox_x2, line2_x2)
                potential_y1 = min(textbox_y1, line2_y1)
                potential_y2 = max(textbox_y2, line2_y2)
                potential_width = potential_x2 - potential_x1
                potential_height = potential_y2 - potential_y1
                
                # Reject if group would be too large
                if potential_width > max_group_width_pixels or potential_height > max_group_height_pixels:
                    continue
                
                # Stricter vertical gap - use absolute maximum
                vertical_close = vertical_gap <= max_vertical_gap_pixels
                
                # Horizontal relationship - stricter requirements:
                # Require BOTH strong alignment AND significant overlap
                edge_aligned = (left_edge_diff <= edge_tolerance) or (right_edge_diff <= edge_tolerance)
                significant_overlap = x_overlap_ratio > 0.3  # Stricter: require 30% overlap
                similar_width = width_ratio > 0.5  # Stricter: require 50% width match
                
                # Require edge alignment AND (significant overlap OR similar width)
                horizontal_related = edge_aligned and (significant_overlap or similar_width)
                
                # Group only if:
                # 1. Vertically close
                # 2. AND horizontally related (stricter criteria)
                # 3. AND group dimensions are reasonable
                if vertical_close and horizontal_related:
                    textbox_lines.append(line2)
                    used_line_indices.add(j)
                    changed = True
                    
                    # Update textbox bounds
                    textbox_x1 = potential_x1
                    textbox_x2 = potential_x2
                    textbox_y1 = potential_y1
                    textbox_y2 = potential_y2
        
        # Flatten textbox lines into a single group of regions
        textbox_regions = []
        for line in textbox_lines:
            textbox_regions.extend(line)
        
        # Only create textbox if it has minimum size
        # Don't enforce max_group_size here - let larger textboxes group (we'll handle it in final output)
        if len(textbox_regions) >= min_group_size:
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
        # If group exceeds max_group_size, we still create it but it will be one large group
        # (The max_group_size is more of a guideline to prevent excessive grouping)
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


def visualize_text_blocks(image: np.ndarray,
                          rectangle_color: Tuple[int, int, int] = (0, 255, 0),
                          rectangle_thickness: int = 2,
                          min_confidence: int = 30,
                          group_text_blocks: bool = True,
                          backend: Optional['OCRBackend'] = None) -> Tuple[np.ndarray, List[dict]]:
    """
    Detect all text blocks in an image and draw rectangles around them.
    
    This function uses OCR to detect text blocks, optionally groups nearby text
    into logical textboxes, and draws rectangles around each detected text block.
    
    Args:
        image: Input image (BGR format)
        rectangle_color: Color for rectangles in BGR format (default: green)
        rectangle_thickness: Thickness of rectangle lines (default: 2)
        min_confidence: Minimum OCR confidence threshold (default: 30)
        group_text_blocks: Whether to group nearby text into textboxes (default: True)
        backend: Optional OCR backend instance (from ocr_backends module).
                 If None, uses Tesseract by default.
        
    Returns:
        Tuple of (annotated_image, text_blocks) where:
        - annotated_image: Image with rectangles drawn around text blocks
        - text_blocks: List of dicts with 'bbox' (x1, y1, x2, y2), 'text', and 'confidence' keys
    """
    # Import backend system
    try:
        from .ocr_backends import OCRBackend, TesseractBackend, get_backend_by_name
    except ImportError:
        # Fallback if backends module not available
        OCRBackend = None
        TesseractBackend = None
        get_backend_by_name = None
    
    # Determine which backend to use
    if backend is None:
        # Try to use backend system if available
        if OCRBackend is not None:
            backend = TesseractBackend()
            if not backend.is_available():
                raise RuntimeError("No OCR backend is available. Please install Tesseract OCR or configure an AI backend.")
        else:
            # Fallback to direct Tesseract usage
            if not is_tesseract_available():
                raise RuntimeError("Tesseract OCR is not available. Please install Tesseract OCR.")
            backend = None  # Signal to use direct pytesseract
    
    # Ensure image is BGR
    if len(image.shape) == 2:
        image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    elif len(image.shape) == 3 and image.shape[2] == 3:
        # Assume RGB, convert to BGR
        image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
    
    h, w = image.shape[:2]
    text_blocks = []
    
    try:
        # Use backend if available, otherwise fall back to direct Tesseract
        if backend is not None and hasattr(backend, 'extract_text_with_boxes'):
            # Use AI backend
            text_blocks = backend.extract_text_with_boxes(image)
            
            # Filter by confidence
            text_blocks = [b for b in text_blocks if b.get('confidence', 0) >= min_confidence]
            
            # Apply additional filtering
            filtered_blocks = []
            for block in text_blocks:
                x1, y1, x2, y2 = block['bbox']
                bw = x2 - x1
                bh = y2 - y1
                
                # Skip if box is too large (> 5% of image) or too small
                if bw * bh > (w * h * 0.05) or bw < 8 or bh < 8:
                    continue
                
                # Filter by aspect ratio
                aspect_ratio = bw / bh if bh > 0 else 0
                if aspect_ratio > 10 or aspect_ratio < 0.1:
                    continue
                
                text = block.get('text', '').strip()
                if not text:
                    continue
                
                # Filter out single character detections (unless alphanumeric)
                if len(text) == 1 and text not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789':
                    continue
                
                # Filter out text that's mostly symbols/punctuation
                alphanumeric_count = sum(1 for c in text if c.isalnum())
                if len(text) > 0 and alphanumeric_count / len(text) < 0.5:
                    continue
                
                filtered_blocks.append(block)
            
            text_blocks = filtered_blocks
        else:
            # Fallback to direct Tesseract usage
            # Convert to grayscale for OCR
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # Use PSM 11 (sparse text) for better detection of text blocks in technical drawings
            custom_config = r'--oem 3 --psm 11'
            
            # Get OCR data with bounding boxes
            data = pytesseract.image_to_data(gray, output_type=pytesseract.Output.DICT, config=custom_config)
            
            # Extract text blocks from OCR data
            n_boxes = len(data['level'])
            for i in range(n_boxes):
                # Only consider word-level detections (level 5)
                if data['level'][i] != 5:
                    continue
                
                # Filter by confidence
                conf = int(data['conf'][i]) if data['conf'][i] != '-1' else 0
                if conf < min_confidence:
                    continue
                
                # Get bounding box coordinates
                x = data['left'][i]
                y = data['top'][i]
                bw = data['width'][i]
                bh = data['height'][i]
                
                # Skip if box is too large (> 5% of image) or too small
                if bw * bh > (w * h * 0.05) or bw < 8 or bh < 8:
                    continue
                
                # Filter by aspect ratio
                aspect_ratio = bw / bh if bh > 0 else 0
                if aspect_ratio > 10 or aspect_ratio < 0.1:
                    continue
                
                # Get detected text
                text = data['text'][i].strip()
                if not text:
                    continue
                
                # Filter out single character detections (unless alphanumeric)
                if len(text) == 1 and text not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789':
                    continue
                
                # Filter out text that's mostly symbols/punctuation
                alphanumeric_count = sum(1 for c in text if c.isalnum())
                if len(text) > 0 and alphanumeric_count / len(text) < 0.5:
                    continue
                
                # Store text block info
                text_blocks.append({
                    'bbox': (x, y, x + bw, y + bh),  # (x1, y1, x2, y2)
                    'text': text,
                    'confidence': conf
                })
        
        # Optionally group text blocks into logical textboxes
        if group_text_blocks and text_blocks:
            # Convert to format expected by group_text_regions
            regions = []
            for i, block in enumerate(text_blocks):
                regions.append({
                    'id': f'block_{i}',
                    'bbox': block['bbox'],
                    'text': block['text'],
                    'confidence': block['confidence']
                })
            
            # Group nearby text blocks
            grouped_regions = group_text_regions(
                regions,
                max_horizontal_gap=0.25,
                max_vertical_gap=0.4,
                min_group_size=1,  # Allow single blocks
                max_group_size=50,
                max_group_width=0.3,
                max_group_height=0.2
            )
            
            # Convert back to text_blocks format
            text_blocks = []
            for region in grouped_regions:
                bbox = region.get('bbox', (0, 0, 0, 0))
                if len(bbox) == 4:
                    text_blocks.append({
                        'bbox': bbox,
                        'text': region.get('text', ''),
                        'confidence': region.get('confidence', 0)
                    })
        
        # Create annotated image by drawing rectangles
        annotated_image = image.copy()
        
        for block in text_blocks:
            x1, y1, x2, y2 = block['bbox']
            # Draw rectangle
            cv2.rectangle(annotated_image, (x1, y1), (x2, y2), rectangle_color, rectangle_thickness)
        
        return annotated_image, text_blocks
        
    except Exception as e:
        raise RuntimeError(f"Error during OCR processing: {e}")


def visualize_text_blocks_from_file(image_path: str,
                                    output_path: str = None,
                                    rectangle_color: Tuple[int, int, int] = (0, 255, 0),
                                    rectangle_thickness: int = 2,
                                    min_confidence: int = 30,
                                    group_text_blocks: bool = True,
                                    backend: Optional['OCRBackend'] = None) -> Tuple[np.ndarray, List[dict]]:
    """
    Load an image from file, detect text blocks, and optionally save the annotated result.
    
    Args:
        image_path: Path to input image file
        output_path: Optional path to save annotated image (if None, image is not saved)
        rectangle_color: Color for rectangles in BGR format (default: green)
        rectangle_thickness: Thickness of rectangle lines (default: 2)
        min_confidence: Minimum OCR confidence threshold (default: 30)
        group_text_blocks: Whether to group nearby text into textboxes (default: True)
        
    Returns:
        Tuple of (annotated_image, text_blocks) - same as visualize_text_blocks()
    """
    # Load image
    image = cv2.imread(image_path)
    if image is None:
        raise ValueError(f"Could not load image from {image_path}")
    
    # Detect and visualize text blocks
    annotated_image, text_blocks = visualize_text_blocks(
        image,
        rectangle_color=rectangle_color,
        rectangle_thickness=rectangle_thickness,
        min_confidence=min_confidence,
        group_text_blocks=group_text_blocks,
        backend=backend
    )
    
    # Save if output path provided
    if output_path:
        cv2.imwrite(output_path, annotated_image)
        print(f"Annotated image saved to {output_path}")
        print(f"Found {len(text_blocks)} text blocks")
    
    return annotated_image, text_blocks

