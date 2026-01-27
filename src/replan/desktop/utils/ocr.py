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


