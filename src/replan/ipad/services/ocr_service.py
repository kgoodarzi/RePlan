"""OCR Service using Apple Vision framework.

This replaces pytesseract from the desktop version.
Uses iOS Vision framework via PyObjC/rubicon-objc.
"""

import numpy as np
from typing import List, Dict, Set, Tuple, Optional
from PIL import Image
import os
import tempfile

from ..utils.ocr import KNOWN_PREFIXES, LABEL_PATTERNS, parse_labels_from_text, group_labels


def is_vision_available() -> bool:
    """Check if Apple Vision framework is available."""
    try:
        from rubicon.objc import ObjCClass
        VNRecognizeTextRequest = ObjCClass('VNRecognizeTextRequest')
        return True
    except:
        return False


class OCRService:
    """
    OCR service using Apple Vision framework.
    
    Falls back to simple pattern matching if Vision is not available.
    """
    
    def __init__(self):
        self._vision_available = is_vision_available()
    
    def extract_text(self, image: np.ndarray) -> str:
        """
        Extract text from an image.
        
        Args:
            image: Input image (RGB numpy array)
            
        Returns:
            Extracted text
        """
        if self._vision_available:
            return self._extract_text_vision(image)
        else:
            return ""
    
    def _extract_text_vision(self, image: np.ndarray) -> str:
        """Extract text using Apple Vision framework."""
        try:
            from rubicon.objc import ObjCClass
            from rubicon.objc.api import NSData, NSURL
            
            VNRecognizeTextRequest = ObjCClass('VNRecognizeTextRequest')
            VNImageRequestHandler = ObjCClass('VNImageRequestHandler')
            
            # Save image to temp file
            pil_img = Image.fromarray(image)
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
                pil_img.save(f.name, 'PNG')
                temp_path = f.name
            
            try:
                # Create Vision request
                url = NSURL.fileURLWithPath_(temp_path)
                handler = VNImageRequestHandler.alloc().initWithURL_options_(url, None)
                
                request = VNRecognizeTextRequest.alloc().init()
                request.setRecognitionLevel_(1)  # Accurate
                request.setUsesLanguageCorrection_(True)
                
                # Perform request
                handler.performRequests_error_([request], None)
                
                # Get results
                results = request.results()
                text_parts = []
                
                if results:
                    for observation in results:
                        candidates = observation.topCandidates_(1)
                        if candidates and len(candidates) > 0:
                            text_parts.append(str(candidates[0].string()))
                
                return '\n'.join(text_parts)
                
            finally:
                # Clean up temp file
                os.unlink(temp_path)
                
        except Exception as e:
            print(f"Vision OCR error: {e}")
            return ""
    
    def find_labels(self, image: np.ndarray) -> Dict[str, Set[str]]:
        """
        Find component labels in an image.
        
        Args:
            image: Input image (RGB numpy array)
            
        Returns:
            Dictionary mapping prefix to set of found labels
        """
        text = self.extract_text(image)
        return parse_labels_from_text(text)
    
    def scan_pages_for_labels(self, images: List[np.ndarray],
                              progress_callback: callable = None) -> Dict[str, Set[str]]:
        """
        Scan multiple pages for labels.
        
        Args:
            images: List of page images
            progress_callback: Optional callback(current, total)
            
        Returns:
            Combined dictionary of found labels
        """
        all_found: Dict[str, Set[str]] = {}
        
        for i, image in enumerate(images):
            if progress_callback:
                progress_callback(i + 1, len(images))
            
            page_labels = self.find_labels(image)
            
            for prefix, instances in page_labels.items():
                if prefix not in all_found:
                    all_found[prefix] = set()
                all_found[prefix].update(instances)
        
        return all_found
    
    def get_grouped_labels(self, image: np.ndarray) -> List[Tuple[str, str, List[str]]]:
        """
        Get labels grouped for user selection.
        
        Returns:
            List of (prefix, full_name, instances) tuples
        """
        labels = self.find_labels(image)
        return group_labels(labels)


# Convenience function
def extract_text_from_image(image: np.ndarray) -> str:
    """Extract text from an image using the default OCR service."""
    service = OCRService()
    return service.extract_text(image)

