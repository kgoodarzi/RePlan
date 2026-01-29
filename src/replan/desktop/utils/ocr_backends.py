"""OCR Backend implementations for various AI services.

Supports:
- Tesseract (local)
- Google Cloud Vision API
- AWS Textract
- Azure Computer Vision
- OpenAI Vision API
"""

import base64
import io
import os
from abc import ABC, abstractmethod
from typing import List, Dict, Tuple, Optional
import cv2
import numpy as np
from PIL import Image


class OCRBackend(ABC):
    """Abstract base class for OCR backends."""
    
    @abstractmethod
    def extract_text_with_boxes(self, image: np.ndarray) -> List[Dict]:
        """
        Extract text with bounding boxes from an image.
        
        Args:
            image: Input image (BGR or RGB numpy array)
            
        Returns:
            List of dicts with keys:
            - 'bbox': (x1, y1, x2, y2) bounding box coordinates
            - 'text': Detected text string
            - 'confidence': Confidence score (0-100)
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if this backend is available/configured."""
        pass


class TesseractBackend(OCRBackend):
    """Tesseract OCR backend (local)."""
    
    def __init__(self):
        self._available = self._check_availability()
    
    def _check_availability(self) -> bool:
        """Check if Tesseract is available."""
        try:
            import pytesseract
            
            # Configure Tesseract path for Windows
            from pathlib import Path
            TESSERACT_PATHS = [
                r'C:\Program Files\Tesseract-OCR\tesseract.exe',
                r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
                r'C:\Users\*\AppData\Local\Programs\Tesseract-OCR\tesseract.exe',
            ]
            
            for path in TESSERACT_PATHS:
                if '*' in path:
                    import glob
                    matches = glob.glob(path)
                    if matches:
                        pytesseract.pytesseract.tesseract_cmd = matches[0]
                        return True
                elif Path(path).exists():
                    pytesseract.pytesseract.tesseract_cmd = path
                    return True
            
            # Try to get version to verify it works
            pytesseract.get_tesseract_version()
            return True
        except:
            return False
    
    def is_available(self) -> bool:
        return self._available
    
    def extract_text_with_boxes(self, image: np.ndarray) -> List[Dict]:
        """Extract text with bounding boxes using Tesseract."""
        if not self._available:
            raise RuntimeError("Tesseract is not available")
        
        import pytesseract
        
        # Convert to grayscale
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
        
        # Use PSM 11 (sparse text) for technical drawings
        custom_config = r'--oem 3 --psm 11'
        data = pytesseract.image_to_data(gray, output_type=pytesseract.Output.DICT, config=custom_config)
        
        text_blocks = []
        n_boxes = len(data['level'])
        
        for i in range(n_boxes):
            # Only consider word-level detections (level 5)
            if data['level'][i] != 5:
                continue
            
            conf = int(data['conf'][i]) if data['conf'][i] != '-1' else 0
            if conf < 30:  # Minimum confidence threshold
                continue
            
            x = data['left'][i]
            y = data['top'][i]
            bw = data['width'][i]
            bh = data['height'][i]
            
            text = data['text'][i].strip()
            if not text:
                continue
            
            text_blocks.append({
                'bbox': (x, y, x + bw, y + bh),
                'text': text,
                'confidence': conf
            })
        
        return text_blocks


class GoogleVisionBackend(OCRBackend):
    """Google Cloud Vision API backend."""
    
    def __init__(self, api_key: Optional[str] = None, credentials_path: Optional[str] = None):
        """
        Initialize Google Vision backend.
        
        Args:
            api_key: API key (for REST API)
            credentials_path: Path to service account JSON file (for gRPC)
        """
        self.api_key = api_key
        self.credentials_path = credentials_path
        self._client = None
        self._available = self._check_availability()
    
    def _check_availability(self) -> bool:
        """Check if Google Vision is available."""
        try:
            if self.api_key:
                # REST API with API key
                return True
            elif self.credentials_path:
                # Service account credentials
                from google.cloud import vision
                return True
            else:
                # Try default credentials
                from google.cloud import vision
                return True
        except ImportError:
            return False
    
    def is_available(self) -> bool:
        return self._available
    
    def _get_client(self):
        """Get or create Vision client."""
        if self._client is None:
            if self.credentials_path:
                from google.cloud import vision
                import os
                os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = self.credentials_path
                self._client = vision.ImageAnnotatorClient()
            elif self.api_key:
                # Use REST API
                self._client = {'api_key': self.api_key}
            else:
                from google.cloud import vision
                self._client = vision.ImageAnnotatorClient()
        return self._client
    
    def extract_text_with_boxes(self, image: np.ndarray) -> List[Dict]:
        """Extract text with bounding boxes using Google Vision."""
        if not self._available:
            raise RuntimeError("Google Vision is not available")
        
        client = self._get_client()
        
        # Convert image to bytes
        if len(image.shape) == 3:
            # BGR to RGB
            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        else:
            image_rgb = image
        
        pil_image = Image.fromarray(image_rgb)
        img_bytes = io.BytesIO()
        pil_image.save(img_bytes, format='PNG')
        img_bytes = img_bytes.getvalue()
        
        if isinstance(client, dict):
            # REST API
            import requests
            url = f"https://vision.googleapis.com/v1/images:annotate?key={client['api_key']}"
            payload = {
                "requests": [{
                    "image": {"content": base64.b64encode(img_bytes).decode()},
                    "features": [{"type": "TEXT_DETECTION"}]
                }]
            }
            response = requests.post(url, json=payload)
            response.raise_for_status()
            result = response.json()
            
            text_blocks = []
            if 'responses' in result and len(result['responses']) > 0:
                annotations = result['responses'][0].get('textAnnotations', [])
                # Skip first annotation (full text)
                for ann in annotations[1:]:
                    vertices = ann.get('boundingPoly', {}).get('vertices', [])
                    if len(vertices) >= 2:
                        x_coords = [v.get('x', 0) for v in vertices]
                        y_coords = [v.get('y', 0) for v in vertices]
                        x1, y1 = min(x_coords), min(y_coords)
                        x2, y2 = max(x_coords), max(y_coords)
                        
                        text_blocks.append({
                            'bbox': (x1, y1, x2, y2),
                            'text': ann.get('description', ''),
                            'confidence': 95  # Google Vision doesn't provide per-word confidence
                        })
            return text_blocks
        else:
            # gRPC client
            from google.cloud import vision
            image_obj = vision.Image(content=img_bytes)
            response = client.text_detection(image=image_obj)
            
            text_blocks = []
            for annotation in response.text_annotations[1:]:  # Skip first (full text)
                vertices = annotation.bounding_poly.vertices
                if len(vertices) >= 2:
                    x_coords = [v.x for v in vertices]
                    y_coords = [v.y for v in vertices]
                    x1, y1 = min(x_coords), min(y_coords)
                    x2, y2 = max(x_coords), max(y_coords)
                    
                    text_blocks.append({
                        'bbox': (x1, y1, x2, y2),
                        'text': annotation.description,
                        'confidence': 95
                    })
            return text_blocks


class OpenAIVisionBackend(OCRBackend):
    """OpenAI Vision API backend."""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize OpenAI Vision backend.
        
        Args:
            api_key: OpenAI API key (or use OPENAI_API_KEY env var)
        """
        self.api_key = api_key
        self._available = self._check_availability()
    
    def _check_availability(self) -> bool:
        """Check if OpenAI Vision is available."""
        try:
            import openai
            return True
        except ImportError:
            return False
    
    def is_available(self) -> bool:
        return self._available
    
    def extract_text_with_boxes(self, image: np.ndarray) -> List[Dict]:
        """Extract text with bounding boxes using OpenAI Vision."""
        if not self._available:
            raise RuntimeError("OpenAI Vision is not available")
        
        import openai
        from openai import OpenAI
        
        # Get API key
        api_key = self.api_key or openai.api_key
        if not api_key:
            api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise RuntimeError("OpenAI API key not provided")
        
        client = OpenAI(api_key=api_key)
        
        # Convert image to base64
        if len(image.shape) == 3:
            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        else:
            image_rgb = image
        
        pil_image = Image.fromarray(image_rgb)
        img_bytes = io.BytesIO()
        pil_image.save(img_bytes, format='PNG')
        img_base64 = base64.b64encode(img_bytes.getvalue()).decode()
        
        # Note: OpenAI Vision API doesn't provide bounding boxes directly
        # We'll need to use a workaround or combine with another method
        # For now, return empty list with a note
        # TODO: Implement bounding box extraction using GPT-4V with structured output
        
        response = client.chat.completions.create(
            model="gpt-4-vision-preview",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Extract all text blocks from this technical drawing. For each text block, provide the bounding box coordinates (x1, y1, x2, y2) and the text content."},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{img_base64}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=4000
        )
        
        # Parse response (this is a simplified version - OpenAI Vision doesn't natively support bounding boxes)
        # You might need to use a different approach or combine with another OCR method
        text_content = response.choices[0].message.content
        
        # For now, return empty - OpenAI Vision API doesn't provide bounding boxes
        # Consider using it for text extraction and combining with Tesseract for boxes
        return []


class AWSTextractBackend(OCRBackend):
    """AWS Textract backend."""
    
    def __init__(self, aws_access_key_id: Optional[str] = None,
                 aws_secret_access_key: Optional[str] = None,
                 aws_profile: Optional[str] = None,
                 region_name: str = 'us-east-1'):
        """
        Initialize AWS Textract backend.
        
        Args:
            aws_access_key_id: AWS access key ID (optional if using profile)
            aws_secret_access_key: AWS secret access key (optional if using profile)
            aws_profile: AWS profile name from ~/.aws/credentials (optional)
            region_name: AWS region
        """
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key
        self.aws_profile = aws_profile
        self.region_name = region_name
        self._client = None
        self._available = self._check_availability()
    
    def _check_availability(self) -> bool:
        """Check if AWS Textract is available."""
        try:
            import boto3
            # Try to create a session to verify boto3 works
            # Don't create client yet - that requires credentials
            return True
        except ImportError:
            return False
    
    def is_available(self) -> bool:
        return self._available
    
    def _get_client(self):
        """Get or create Textract client."""
        if self._client is None:
            import boto3
            try:
                if self.aws_access_key_id and self.aws_secret_access_key:
                    # Use explicit credentials
                    self._client = boto3.client(
                        'textract',
                        aws_access_key_id=self.aws_access_key_id,
                        aws_secret_access_key=self.aws_secret_access_key,
                        region_name=self.region_name
                    )
                elif self.aws_profile:
                    # Use AWS profile (like PlanMod app)
                    try:
                        session = boto3.Session(profile_name=self.aws_profile)
                        # Verify profile exists and has credentials
                        credentials = session.get_credentials()
                        if credentials is None:
                            raise RuntimeError(f"AWS profile '{self.aws_profile}' not found or has no credentials. "
                                             f"Please check ~/.aws/credentials file.")
                        self._client = session.client('textract', region_name=self.region_name)
                    except Exception as e:
                        if 'profile' in str(e).lower() or 'credentials' in str(e).lower():
                            raise RuntimeError(f"Failed to load AWS profile '{self.aws_profile}': {str(e)}\n\n"
                                             f"Please verify:\n"
                                             f"1. Profile exists in ~/.aws/credentials\n"
                                             f"2. Profile name is spelled correctly\n"
                                             f"3. Profile has valid credentials")
                        raise
                else:
                    # Use default credentials (from environment or ~/.aws/credentials)
                    session = boto3.Session()
                    credentials = session.get_credentials()
                    if credentials is None:
                        raise RuntimeError("No AWS credentials found. Please configure credentials using:\n"
                                         "1. AWS Profile in Preferences > OCR tab, OR\n"
                                         "2. Environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY), OR\n"
                                         "3. Default profile in ~/.aws/credentials")
                    self._client = boto3.client('textract', region_name=self.region_name)
            except RuntimeError:
                # Re-raise our custom errors
                raise
            except Exception as e:
                raise RuntimeError(f"Failed to create Textract client: {str(e)}")
        return self._client
    
    def extract_text_with_boxes(self, image: np.ndarray) -> List[Dict]:
        """Extract text with bounding boxes using AWS Textract."""
        if not self._available:
            raise RuntimeError("AWS Textract is not available")
        
        client = self._get_client()
        
        # Convert image to bytes
        if len(image.shape) == 3:
            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        else:
            image_rgb = image
        
        pil_image = Image.fromarray(image_rgb)
        img_bytes = io.BytesIO()
        pil_image.save(img_bytes, format='PNG')
        img_bytes = img_bytes.getvalue()
        
        # Call Textract
        response = client.detect_document_text(Document={'Bytes': img_bytes})
        
        text_blocks = []
        for block in response.get('Blocks', []):
            if block['BlockType'] == 'WORD':
                geometry = block.get('Geometry', {})
                bbox = geometry.get('BoundingBox', {})
                
                # Textract returns normalized coordinates (0-1)
                h, w = image.shape[:2]
                x1 = int(bbox.get('Left', 0) * w)
                y1 = int(bbox.get('Top', 0) * h)
                x2 = int((bbox.get('Left', 0) + bbox.get('Width', 0)) * w)
                y2 = int((bbox.get('Top', 0) + bbox.get('Height', 0)) * h)
                
                confidence = int(block.get('Confidence', 0))
                
                text_blocks.append({
                    'bbox': (x1, y1, x2, y2),
                    'text': block.get('Text', ''),
                    'confidence': confidence
                })
        
        return text_blocks
    
    def analyze_document(self, document_bytes: bytes) -> dict:
        """
        Analyze a document (PDF or image) and return full Textract JSON response.
        
        Args:
            document_bytes: PDF or image file bytes
            
        Returns:
            Full Textract response dictionary with all blocks and metadata
        """
        if not self._available:
            raise RuntimeError("AWS Textract is not available. Please install boto3: pip install boto3")
        
        try:
            client = self._get_client()
        except RuntimeError:
            # Re-raise our custom RuntimeErrors as-is
            raise
        except Exception as e:
            raise RuntimeError(f"Failed to create Textract client: {str(e)}\n"
                             "Please check your AWS credentials configuration.")
        
        # Validate credentials by attempting a simple operation (optional - can be removed if too slow)
        # This helps catch credential issues before processing the document
        
        try:
            # Use AnalyzeDocument for better results (supports PDFs and images)
            # Note: FeatureTypes may not be supported for all document types, so we'll catch errors
            try:
                response = client.analyze_document(
                    Document={'Bytes': document_bytes},
                    FeatureTypes=['TABLES', 'FORMS']  # Get additional structure info
                )
            except Exception as e:
                # If FeatureTypes causes an error, try without it
                if 'FeatureTypes' in str(e) or 'InvalidParameter' in str(e):
                    response = client.analyze_document(
                        Document={'Bytes': document_bytes}
                    )
                else:
                    raise
        
        except Exception as e:
            error_msg = str(e)
            error_type = type(e).__name__
            
            # Check for botocore ClientError which wraps AWS API errors
            try:
                from botocore.exceptions import ClientError
                if isinstance(e, ClientError) and 'Error' in e.response:
                    aws_error_code = e.response.get('Error', {}).get('Code', '')
                    aws_error_msg = e.response.get('Error', {}).get('Message', error_msg)
                    
                    if aws_error_code == 'UnrecognizedClientException' or 'UnrecognizedClientException' in str(e):
                        profile_info = f" (profile: '{self.aws_profile}')" if self.aws_profile else " (using default credentials)"
                        raise RuntimeError(f"Invalid AWS credentials{profile_info}.\n\n"
                                         f"AWS Error: {aws_error_msg}\n\n"
                                         "The security token/credentials are invalid or expired.\n\n"
                                         "Please check:\n"
                                         "1. AWS Profile name is correct in Preferences > OCR (if using profile)\n"
                                         "2. Credentials in ~/.aws/credentials are valid and not expired\n"
                                         "3. If using environment variables, AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY are correct\n"
                                         "4. Credentials have not been rotated/changed\n\n"
                                         "To test your credentials, run:\n"
                                         f"  aws sts get-caller-identity{' --profile ' + self.aws_profile if self.aws_profile else ''}")
                    elif aws_error_code == 'InvalidClientTokenId' or 'InvalidClientTokenId' in str(e):
                        raise RuntimeError(f"Invalid AWS Access Key ID.\n\n"
                                         f"AWS Error: {aws_error_msg}\n\n"
                                         "Please verify your AWS Access Key ID is correct.")
                    elif aws_error_code == 'AccessDeniedException' or 'AccessDenied' in aws_error_code:
                        raise RuntimeError("Access denied. Please ensure your AWS credentials have Textract permissions.\n\n"
                                         f"AWS Error: {aws_error_msg}\n\n"
                                         "Required IAM permission: textract:AnalyzeDocument\n"
                                         "You can add the 'AmazonTextractFullAccess' managed policy to your IAM user/role.")
            except ImportError:
                pass  # botocore not available, fall through to generic error handling
            
            # Handle specific AWS errors (fallback for non-botocore exceptions)
            if "NoCredentialsError" in error_type or "credentials" in error_msg.lower():
                raise RuntimeError("AWS credentials not found. Please configure AWS credentials.")
            elif "UnrecognizedClientException" in error_msg or "InvalidClientTokenId" in error_msg:
                profile_info = f" (profile: '{self.aws_profile}')" if self.aws_profile else ""
                raise RuntimeError(f"Invalid AWS credentials{profile_info}.\n\n"
                                 "The security token/credentials are invalid or expired.\n\n"
                                 "Please check:\n"
                                 "1. AWS Profile name is correct (if using profile)\n"
                                 "2. Credentials in ~/.aws/credentials are valid\n"
                                 "3. Credentials haven't expired\n"
                                 "4. AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY are correct (if using env vars)\n\n"
                                 f"Test credentials: aws sts get-caller-identity{' --profile ' + self.aws_profile if self.aws_profile else ''}")
            elif "AccessDenied" in error_msg or "UnauthorizedOperation" in error_msg:
                raise RuntimeError("Access denied. Please ensure your AWS credentials have Textract permissions.\n\n"
                                 "Required IAM permission: textract:AnalyzeDocument")
            elif "InvalidParameterException" in error_msg:
                raise RuntimeError(f"Invalid parameter: {error_msg}")
            else:
                raise RuntimeError(f"Textract API error: {error_msg}")
        
        return response
    
    def analyze_document_json(self, document_bytes: bytes) -> dict:
        """
        Analyze a document and return parsed JSON with text blocks grouped by type.
        
        Args:
            document_bytes: PDF or image file bytes
            
        Returns:
            Dictionary with:
            - 'blocks': List of all blocks with full metadata
            - 'words': List of word blocks with bounding boxes
            - 'lines': List of line blocks with bounding boxes
            - 'pages': List of page blocks
            - 'raw_response': Full Textract response
        """
        response = self.analyze_document(document_bytes)
        
        blocks = response.get('Blocks', [])
        words = []
        lines = []
        pages = []
        
        for block in blocks:
            block_type = block.get('BlockType', '')
            if block_type == 'WORD':
                words.append(block)
            elif block_type == 'LINE':
                lines.append(block)
            elif block_type == 'PAGE':
                pages.append(block)
        
        return {
            'blocks': blocks,
            'words': words,
            'lines': lines,
            'pages': pages,
            'raw_response': response
        }


class AzureVisionBackend(OCRBackend):
    """Azure Computer Vision backend."""
    
    def __init__(self, endpoint: Optional[str] = None, api_key: Optional[str] = None):
        """
        Initialize Azure Vision backend.
        
        Args:
            endpoint: Azure endpoint URL
            api_key: Azure API key
        """
        self.endpoint = endpoint
        self.api_key = api_key
        self._available = self._check_availability()
    
    def _check_availability(self) -> bool:
        """Check if Azure Vision is available."""
        try:
            import requests
            return True
        except ImportError:
            return False
    
    def is_available(self) -> bool:
        return self._available and self.endpoint and self.api_key
    
    def extract_text_with_boxes(self, image: np.ndarray) -> List[Dict]:
        """Extract text with bounding boxes using Azure Vision."""
        if not self.is_available():
            raise RuntimeError("Azure Vision is not available or not configured")
        
        import requests
        
        # Convert image to bytes
        if len(image.shape) == 3:
            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        else:
            image_rgb = image
        
        pil_image = Image.fromarray(image_rgb)
        img_bytes = io.BytesIO()
        pil_image.save(img_bytes, format='PNG')
        img_bytes = img_bytes.getvalue()
        
        # Call Azure Vision API
        url = f"{self.endpoint}/vision/v3.2/read/analyze"
        headers = {
            'Ocp-Apim-Subscription-Key': self.api_key,
            'Content-Type': 'application/octet-stream'
        }
        
        response = requests.post(url, headers=headers, data=img_bytes)
        response.raise_for_status()
        
        # Get operation location
        operation_location = response.headers.get('Operation-Location')
        if not operation_location:
            raise RuntimeError("No operation location returned")
        
        # Poll for results
        import time
        while True:
            result_response = requests.get(operation_location, headers={'Ocp-Apim-Subscription-Key': self.api_key})
            result_response.raise_for_status()
            result = result_response.json()
            
            if result.get('status') == 'succeeded':
                break
            elif result.get('status') == 'failed':
                raise RuntimeError("Azure Vision API failed")
            
            time.sleep(1)
        
        # Parse results
        text_blocks = []
        for read_result in result.get('analyzeResult', {}).get('readResults', []):
            for line in read_result.get('lines', []):
                bbox = line.get('boundingBox', [])
                if len(bbox) >= 8:  # 4 points (x, y pairs)
                    x_coords = [bbox[i] for i in range(0, len(bbox), 2)]
                    y_coords = [bbox[i] for i in range(1, len(bbox), 2)]
                    x1, y1 = int(min(x_coords)), int(min(y_coords))
                    x2, y2 = int(max(x_coords)), int(max(y_coords))
                    
                    text_blocks.append({
                        'bbox': (x1, y1, x2, y2),
                        'text': line.get('text', ''),
                        'confidence': 95  # Azure doesn't provide per-word confidence
                    })
        
        return text_blocks


def get_available_backends() -> List[OCRBackend]:
    """Get list of available OCR backends."""
    backends = []
    
    # Try Tesseract (always try first as it's local)
    tesseract = TesseractBackend()
    if tesseract.is_available():
        backends.append(tesseract)
    
    # Try Google Vision (if credentials available)
    google = GoogleVisionBackend()
    if google.is_available():
        backends.append(google)
    
    # Try AWS Textract (if credentials available)
    aws = AWSTextractBackend()
    if aws.is_available():
        backends.append(aws)
    
    # Try Azure (requires explicit configuration)
    # azure = AzureVisionBackend()  # Won't be available without config
    # if azure.is_available():
    #     backends.append(azure)
    
    return backends


def get_backend_by_name(name: str, **kwargs) -> Optional[OCRBackend]:
    """
    Get a specific OCR backend by name.
    
    Args:
        name: Backend name ('tesseract', 'google', 'aws', 'azure', 'openai')
        **kwargs: Backend-specific configuration
        
    Returns:
        OCRBackend instance or None if not available
    """
    name_lower = name.lower()
    
    if name_lower == 'tesseract':
        backend = TesseractBackend()
        return backend if backend.is_available() else None
    
    elif name_lower == 'google':
        backend = GoogleVisionBackend(
            api_key=kwargs.get('api_key'),
            credentials_path=kwargs.get('credentials_path')
        )
        return backend if backend.is_available() else None
    
    elif name_lower == 'aws':
        backend = AWSTextractBackend(
            aws_access_key_id=kwargs.get('aws_access_key_id'),
            aws_secret_access_key=kwargs.get('aws_secret_access_key'),
            aws_profile=kwargs.get('aws_profile'),
            region_name=kwargs.get('region_name', 'us-east-1')
        )
        return backend if backend.is_available() else None
    
    elif name_lower == 'azure':
        backend = AzureVisionBackend(
            endpoint=kwargs.get('endpoint'),
            api_key=kwargs.get('api_key')
        )
        return backend if backend.is_available() else None
    
    elif name_lower == 'openai':
        backend = OpenAIVisionBackend(api_key=kwargs.get('api_key'))
        return backend if backend.is_available() else None
    
    return None
