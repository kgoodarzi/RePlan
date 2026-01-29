"""Helper functions for OCR backend configuration."""

from typing import Optional
from replan.desktop.config import AppSettings
from replan.desktop.utils.ocr_backends import get_backend_by_name, OCRBackend


def get_configured_ocr_backend(settings: AppSettings) -> Optional[OCRBackend]:
    """
    Get the configured OCR backend based on settings.
    
    Args:
        settings: AppSettings instance with OCR configuration
        
    Returns:
        OCRBackend instance or None if not available/configured
    """
    backend_name = getattr(settings, 'ocr_backend', 'tesseract')
    
    kwargs = {}
    
    if backend_name == 'aws':
        # Get AWS configuration from settings
        aws_profile = getattr(settings, 'aws_profile', '')
        aws_region = getattr(settings, 'aws_region', 'us-east-1')
        
        if aws_profile:
            kwargs['aws_profile'] = aws_profile
        kwargs['region_name'] = aws_region
    
    elif backend_name == 'google':
        # Google Vision would need API key or credentials path
        # For now, use defaults
        pass
    
    elif backend_name == 'azure':
        # Azure would need endpoint and API key
        # For now, use defaults
        pass
    
    elif backend_name == 'openai':
        # OpenAI would need API key
        # For now, use defaults
        pass
    
    backend = get_backend_by_name(backend_name, **kwargs)
    return backend
