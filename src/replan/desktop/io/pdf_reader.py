"""PDF reading and rasterization."""

from pathlib import Path
from typing import List, Optional
import cv2
import numpy as np

from replan.desktop.utils.profiling import timed


class PDFReader:
    """
    Reads and rasterizes PDF files.
    
    Uses PyMuPDF (fitz) for PDF rendering.
    """
    
    def __init__(self, dpi: int = 150, max_dimension: int = 4000):
        """
        Initialize PDF reader.
        
        Args:
            dpi: Resolution for rasterization (dots per inch)
            max_dimension: Maximum width or height in pixels (to prevent memory issues)
        """
        self.dpi = dpi
        self.max_dimension = max_dimension
    
    def load(self, path: str) -> List[np.ndarray]:
        """
        Load a PDF and rasterize all pages.
        
        Args:
            path: Path to PDF file
            
        Returns:
            List of page images (BGR format)
        """
        try:
            import fitz  # PyMuPDF
            
            doc = fitz.open(path)
            pages = []
            
            for page in doc:
                pix = page.get_pixmap(dpi=self.dpi)
                
                # Convert to numpy array
                img = np.frombuffer(pix.samples, dtype=np.uint8)
                img = img.reshape(pix.height, pix.width, pix.n)
                
                # Convert to BGR
                if pix.n == 4:
                    img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
                elif pix.n == 3:
                    img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
                
                # Resize if image is too large to prevent memory issues
                h, w = img.shape[:2]
                if max(h, w) > self.max_dimension:
                    scale = self.max_dimension / max(h, w)
                    new_w = int(w * scale)
                    new_h = int(h * scale)
                    img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
                    print(f"Resized image from {w}x{h} to {new_w}x{new_h} to fit memory limits")
                
                pages.append(img)
            
            doc.close()
            return pages
            
        except ImportError:
            print("Error: PyMuPDF (fitz) not installed. Run: pip install PyMuPDF")
            return []
        except Exception as e:
            print(f"Error loading PDF: {e}")
            return []
    
    @timed("pdf_load")
    def load_with_dimensions(self, path: str) -> List[dict]:
        """
        Load a PDF and return pages with dimension information.
        
        Args:
            path: Path to PDF file
            
        Returns:
            List of dicts with 'image', 'width_inches', 'height_inches', 'dpi'
        """
        try:
            import fitz  # PyMuPDF
            
            doc = fitz.open(path)
            pages = []
            
            for page in doc:
                # Get page dimensions in points (72 points = 1 inch)
                rect = page.rect
                width_pts = rect.width
                height_pts = rect.height
                width_inches = width_pts / 72.0
                height_inches = height_pts / 72.0
                
                # Rasterize
                pix = page.get_pixmap(dpi=self.dpi)
                
                # Convert to numpy array
                img = np.frombuffer(pix.samples, dtype=np.uint8)
                img = img.reshape(pix.height, pix.width, pix.n)
                
                # Convert to BGR
                if pix.n == 4:
                    img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
                elif pix.n == 3:
                    img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
                
                # Resize if image is too large to prevent memory issues
                h, w = img.shape[:2]
                if max(h, w) > self.max_dimension:
                    scale = self.max_dimension / max(h, w)
                    new_w = int(w * scale)
                    new_h = int(h * scale)
                    img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
                    print(f"Resized image from {w}x{h} to {new_w}x{new_h} to fit memory limits")
                
                pages.append({
                    'image': img,
                    'width_inches': width_inches,
                    'height_inches': height_inches,
                    'dpi': self.dpi,
                })
            
            doc.close()
            return pages
            
        except ImportError:
            print("Error: PyMuPDF (fitz) not installed. Run: pip install PyMuPDF")
            return []
        except Exception as e:
            print(f"Error loading PDF: {e}")
            return []
    
    def get_page_dimensions(self, path: str) -> List[dict]:
        """
        Get page dimensions without rasterizing.
        
        Returns:
            List of dicts with 'width_inches', 'height_inches'
        """
        try:
            import fitz
            doc = fitz.open(path)
            dims = []
            
            for page in doc:
                rect = page.rect
                dims.append({
                    'width_inches': rect.width / 72.0,
                    'height_inches': rect.height / 72.0,
                })
            
            doc.close()
            return dims
        except:
            return []
    
    def load_page(self, path: str, page_num: int) -> Optional[np.ndarray]:
        """
        Load a single page from a PDF.
        
        Args:
            path: Path to PDF file
            page_num: Page number (0-indexed)
            
        Returns:
            Page image or None if failed
        """
        try:
            import fitz
            
            doc = fitz.open(path)
            
            if page_num < 0 or page_num >= len(doc):
                doc.close()
                return None
            
            page = doc[page_num]
            pix = page.get_pixmap(dpi=self.dpi)
            
            img = np.frombuffer(pix.samples, dtype=np.uint8)
            img = img.reshape(pix.height, pix.width, pix.n)
            
            if pix.n == 4:
                img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
            elif pix.n == 3:
                img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
            
            # Resize if image is too large to prevent memory issues
            h, w = img.shape[:2]
            if max(h, w) > self.max_dimension:
                scale = self.max_dimension / max(h, w)
                new_w = int(w * scale)
                new_h = int(h * scale)
                img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
                print(f"Resized image from {w}x{h} to {new_w}x{new_h} to fit memory limits")
            
            doc.close()
            return img
            
        except Exception as e:
            print(f"Error loading page: {e}")
            return None
    
    def get_page_count(self, path: str) -> int:
        """Get the number of pages in a PDF."""
        try:
            import fitz
            doc = fitz.open(path)
            count = len(doc)
            doc.close()
            return count
        except:
            return 0
    
    @staticmethod
    def rotate_image(image: np.ndarray, degrees: int) -> np.ndarray:
        """
        Rotate an image by 90-degree increments.
        
        Args:
            image: Input image
            degrees: Rotation in degrees (90, 180, 270, -90, etc.)
            
        Returns:
            Rotated image
        """
        # Normalize to 0, 90, 180, 270
        degrees = degrees % 360
        
        if degrees == 0:
            return image
        elif degrees == 90:
            return cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
        elif degrees == 180:
            return cv2.rotate(image, cv2.ROTATE_180)
        elif degrees == 270:
            return cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE)
        else:
            # For arbitrary angles, use warpAffine
            h, w = image.shape[:2]
            center = (w // 2, h // 2)
            matrix = cv2.getRotationMatrix2D(center, -degrees, 1.0)
            return cv2.warpAffine(image, matrix, (w, h))
    
    @staticmethod
    def get_default_model_name(path: str) -> str:
        """Extract a default model name from file path."""
        stem = Path(path).stem
        # Clean up common patterns
        name = stem.replace('_', ' ').replace('-', ' ')
        # Title case
        name = name.title()
        # Take first word or two
        words = name.split()[:2]
        return ' '.join(words)

