"""PDF Service using iOS PDFKit framework.

This replaces PyMuPDF (fitz) from the desktop version.
Uses iOS PDFKit via PyObjC/rubicon-objc.
"""

import numpy as np
from typing import List, Dict, Optional, Tuple
from PIL import Image
import os


def is_pdfkit_available() -> bool:
    """Check if iOS PDFKit is available."""
    try:
        from rubicon.objc import ObjCClass
        PDFDocument = ObjCClass('PDFDocument')
        return True
    except:
        return False


class PDFService:
    """
    PDF reading service using iOS PDFKit.
    
    Falls back to returning empty results if PDFKit is not available.
    On desktop (for testing), can use PyMuPDF if available.
    """
    
    def __init__(self, dpi: int = 150):
        """
        Initialize PDF service.
        
        Args:
            dpi: Resolution for rasterization
        """
        self.dpi = dpi
        self._pdfkit_available = is_pdfkit_available()
        self._pymupdf_available = self._check_pymupdf()
    
    def _check_pymupdf(self) -> bool:
        """Check if PyMuPDF is available (for desktop testing)."""
        try:
            import fitz
            return True
        except:
            return False
    
    def load(self, path: str) -> List[np.ndarray]:
        """
        Load a PDF and rasterize all pages.
        
        Args:
            path: Path to PDF file
            
        Returns:
            List of page images (RGB format)
        """
        if self._pdfkit_available:
            return self._load_pdfkit(path)
        elif self._pymupdf_available:
            return self._load_pymupdf(path)
        else:
            print("No PDF library available")
            return []
    
    def _load_pdfkit(self, path: str) -> List[np.ndarray]:
        """Load PDF using iOS PDFKit."""
        try:
            from rubicon.objc import ObjCClass
            from rubicon.objc.api import NSURL, NSData
            
            PDFDocument = ObjCClass('PDFDocument')
            
            url = NSURL.fileURLWithPath_(path)
            doc = PDFDocument.alloc().initWithURL_(url)
            
            if not doc:
                print(f"Could not open PDF: {path}")
                return []
            
            pages = []
            page_count = doc.pageCount()
            
            for i in range(page_count):
                page = doc.pageAtIndex_(i)
                if page:
                    # Get page bounds
                    bounds = page.boundsForBox_(0)  # kPDFDisplayBoxMediaBox
                    width = int(bounds.size.width * self.dpi / 72)
                    height = int(bounds.size.height * self.dpi / 72)
                    
                    # Render to image using Core Graphics
                    # Note: This is a simplified version - full implementation
                    # would use CGContext for rendering
                    
                    # For now, create a placeholder
                    # Real implementation would render the PDF page
                    img = np.ones((height, width, 3), dtype=np.uint8) * 255
                    pages.append(img)
            
            return pages
            
        except Exception as e:
            print(f"PDFKit error: {e}")
            return []
    
    def _load_pymupdf(self, path: str) -> List[np.ndarray]:
        """Load PDF using PyMuPDF (for desktop testing)."""
        try:
            import fitz
            
            doc = fitz.open(path)
            pages = []
            
            for page in doc:
                pix = page.get_pixmap(dpi=self.dpi)
                img = np.frombuffer(pix.samples, dtype=np.uint8)
                img = img.reshape(pix.height, pix.width, pix.n)
                
                # Convert to RGB
                if pix.n == 4:
                    img = img[:, :, :3]  # Remove alpha
                
                pages.append(img)
            
            doc.close()
            return pages
            
        except Exception as e:
            print(f"PyMuPDF error: {e}")
            return []
    
    def load_with_dimensions(self, path: str) -> List[Dict]:
        """
        Load PDF with dimension information.
        
        Returns:
            List of dicts with 'image', 'width_inches', 'height_inches', 'dpi'
        """
        if self._pymupdf_available:
            return self._load_with_dims_pymupdf(path)
        
        # Fallback: load images and estimate dimensions
        images = self.load(path)
        results = []
        
        for img in images:
            h, w = img.shape[:2]
            results.append({
                'image': img,
                'width_inches': w / self.dpi,
                'height_inches': h / self.dpi,
                'dpi': self.dpi,
            })
        
        return results
    
    def _load_with_dims_pymupdf(self, path: str) -> List[Dict]:
        """Load with dimensions using PyMuPDF."""
        try:
            import fitz
            
            doc = fitz.open(path)
            pages = []
            
            for page in doc:
                rect = page.rect
                width_inches = rect.width / 72.0
                height_inches = rect.height / 72.0
                
                pix = page.get_pixmap(dpi=self.dpi)
                img = np.frombuffer(pix.samples, dtype=np.uint8)
                img = img.reshape(pix.height, pix.width, pix.n)
                
                if pix.n == 4:
                    img = img[:, :, :3]
                
                pages.append({
                    'image': img,
                    'width_inches': width_inches,
                    'height_inches': height_inches,
                    'dpi': self.dpi,
                })
            
            doc.close()
            return pages
            
        except Exception as e:
            print(f"PyMuPDF error: {e}")
            return []
    
    def get_page_count(self, path: str) -> int:
        """Get number of pages in a PDF."""
        if self._pdfkit_available:
            try:
                from rubicon.objc import ObjCClass
                from rubicon.objc.api import NSURL
                
                PDFDocument = ObjCClass('PDFDocument')
                url = NSURL.fileURLWithPath_(path)
                doc = PDFDocument.alloc().initWithURL_(url)
                
                return doc.pageCount() if doc else 0
            except:
                return 0
        
        elif self._pymupdf_available:
            try:
                import fitz
                doc = fitz.open(path)
                count = len(doc)
                doc.close()
                return count
            except:
                return 0
        
        return 0
    
    def load_page(self, path: str, page_num: int) -> Optional[np.ndarray]:
        """Load a single page from a PDF."""
        pages = self.load(path)
        if 0 <= page_num < len(pages):
            return pages[page_num]
        return None
    
    @staticmethod
    def rotate_image(image: np.ndarray, degrees: int) -> np.ndarray:
        """Rotate an image by 90-degree increments."""
        degrees = degrees % 360
        
        if degrees == 0:
            return image
        
        pil_img = Image.fromarray(image)
        
        if degrees == 90:
            pil_img = pil_img.transpose(Image.Transpose.ROTATE_270)
        elif degrees == 180:
            pil_img = pil_img.transpose(Image.Transpose.ROTATE_180)
        elif degrees == 270:
            pil_img = pil_img.transpose(Image.Transpose.ROTATE_90)
        else:
            pil_img = pil_img.rotate(-degrees, expand=True)
        
        return np.array(pil_img)
    
    @staticmethod
    def get_default_model_name(path: str) -> str:
        """Extract a default model name from file path."""
        from pathlib import Path
        stem = Path(path).stem
        name = stem.replace('_', ' ').replace('-', ' ')
        name = name.title()
        words = name.split()[:2]
        return ' '.join(words)

