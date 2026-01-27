"""iOS-specific services for iPad segmenter."""

from .ocr_service import OCRService, is_vision_available
from .pdf_service import PDFService, is_pdfkit_available

__all__ = [
    "OCRService",
    "is_vision_available",
    "PDFService", 
    "is_pdfkit_available",
]

