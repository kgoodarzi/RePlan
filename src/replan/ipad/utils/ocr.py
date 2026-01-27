"""OCR patterns and constants for iPad.

This module contains the label patterns and known prefixes from the desktop version.
The actual OCR functionality is in services/ocr_service.py using Apple Vision.
"""

from typing import Dict, List, Set, Tuple
import re

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

# Regex patterns to search for component labels
LABEL_PATTERNS = [
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


def parse_labels_from_text(text: str) -> Dict[str, Set[str]]:
    """
    Parse component labels from OCR text.
    
    Looks for patterns like:
    - R1, R2, R3 (ribs)
    - F1, F2 (formers)
    - FS1, FS2 (fuselage sides)
    - etc.
    
    Args:
        text: OCR-extracted text
        
    Returns:
        Dictionary mapping prefix to set of found labels
    """
    found: Dict[str, Set[str]] = {}
    
    for pattern, force_prefix in LABEL_PATTERNS:
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
        labels: Dictionary from parse_labels_from_text()
        
    Returns:
        List of (prefix, full_name, instances) tuples
    """
    result = []
    
    for prefix in sorted(labels.keys()):
        instances = sorted(labels[prefix])
        full_name = KNOWN_PREFIXES.get(prefix, prefix)
        result.append((prefix, full_name, instances))
    
    return result

