# AI OCR Backends

RePlan supports multiple OCR backends, including AI-powered cloud services for better accuracy.

## Available Backends

1. **Tesseract** (default, local) - Free, no API key required
2. **Google Cloud Vision API** - High accuracy, requires API key
3. **AWS Textract** - Good for documents, requires AWS credentials
4. **Azure Computer Vision** - Microsoft's OCR service, requires endpoint and API key
5. **OpenAI Vision API** - GPT-4 Vision (limited bounding box support)

## Usage

### Using Tesseract (Default)

```python
from replan.desktop.utils.ocr import visualize_text_blocks_from_file

# Uses Tesseract automatically
annotated_image, text_blocks = visualize_text_blocks_from_file(
    'plan.png',
    'plan_annotated.png'
)
```

### Using Google Cloud Vision API

```python
from replan.desktop.utils.ocr import visualize_text_blocks_from_file
from replan.desktop.utils.ocr_backends import get_backend_by_name

# Option 1: Using API key
backend = get_backend_by_name('google', api_key='YOUR_API_KEY')

# Option 2: Using service account credentials file
backend = get_backend_by_name('google', credentials_path='path/to/credentials.json')

annotated_image, text_blocks = visualize_text_blocks_from_file(
    'plan.png',
    'plan_annotated.png',
    backend=backend
)
```

### Using AWS Textract

```python
from replan.desktop.utils.ocr import visualize_text_blocks_from_file
from replan.desktop.utils.ocr_backends import get_backend_by_name

backend = get_backend_by_name(
    'aws',
    aws_access_key_id='YOUR_KEY',
    aws_secret_access_key='YOUR_SECRET',
    region_name='us-east-1'
)

annotated_image, text_blocks = visualize_text_blocks_from_file(
    'plan.png',
    'plan_annotated.png',
    backend=backend
)
```

### Using Azure Computer Vision

```python
from replan.desktop.utils.ocr import visualize_text_blocks_from_file
from replan.desktop.utils.ocr_backends import get_backend_by_name

backend = get_backend_by_name(
    'azure',
    endpoint='https://YOUR_REGION.api.cognitive.microsoft.com',
    api_key='YOUR_API_KEY'
)

annotated_image, text_blocks = visualize_text_blocks_from_file(
    'plan.png',
    'plan_annotated.png',
    backend=backend
)
```

## Command Line Usage

### Using the AI-enabled script:

```bash
# Tesseract (default)
python visualize_text_blocks_ai.py plan.png output.png

# Google Cloud Vision
python visualize_text_blocks_ai.py plan.png output.png \
    --backend google --api-key YOUR_API_KEY

# AWS Textract
python visualize_text_blocks_ai.py plan.png output.png \
    --backend aws --aws-key YOUR_KEY --aws-secret YOUR_SECRET

# Azure Vision
python visualize_text_blocks_ai.py plan.png output.png \
    --backend azure --endpoint URL --api-key YOUR_KEY
```

## Installation

### Tesseract (Default)
```bash
# Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki
# macOS: brew install tesseract
# Linux: sudo apt-get install tesseract-ocr
pip install pytesseract
```

### Google Cloud Vision
```bash
pip install google-cloud-vision
# Or for REST API (simpler):
pip install requests
```

### AWS Textract
```bash
pip install boto3
```

### Azure Computer Vision
```bash
pip install requests
```

## Configuration

### Environment Variables

You can also configure backends using environment variables:

- **Google**: `GOOGLE_APPLICATION_CREDENTIALS` (path to credentials JSON)
- **AWS**: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION`
- **OpenAI**: `OPENAI_API_KEY`

## Performance Comparison

- **Tesseract**: Fast, local, free, good accuracy for printed text
- **Google Vision**: Very high accuracy, handles complex layouts well, requires internet
- **AWS Textract**: Excellent for documents, good accuracy, requires internet
- **Azure Vision**: Good accuracy, handles multiple languages well, requires internet
- **OpenAI Vision**: Best for understanding context, but limited bounding box support

## Cost Considerations

- **Tesseract**: Free
- **Google Vision**: ~$1.50 per 1,000 images (first 1,000/month free)
- **AWS Textract**: ~$1.50 per 1,000 pages (first 1,000/month free)
- **Azure Vision**: ~$1.00 per 1,000 transactions (first 5,000/month free)
- **OpenAI Vision**: ~$0.01-0.03 per image depending on resolution

## Recommendations

- **For development/testing**: Use Tesseract (free, local)
- **For production/high accuracy**: Use Google Cloud Vision or AWS Textract
- **For multi-language**: Use Azure Computer Vision
- **For complex layouts**: Use Google Cloud Vision
