#!/usr/bin/env python3
"""
Script to visualize text blocks using AI OCR backends.

Usage:
    # Use Tesseract (default)
    python visualize_text_blocks_ai.py <input_image> [output_image]
    
    # Use Google Cloud Vision
    python visualize_text_blocks_ai.py <input_image> [output_image] --backend google --api-key YOUR_KEY
    
    # Use AWS Textract
    python visualize_text_blocks_ai.py <input_image> [output_image] --backend aws --aws-key YOUR_KEY --aws-secret YOUR_SECRET
    
    # Use Azure Vision
    python visualize_text_blocks_ai.py <input_image> [output_image] --backend azure --endpoint URL --api-key YOUR_KEY
"""

import sys
import argparse
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from replan.desktop.utils.ocr import visualize_text_blocks_from_file
from replan.desktop.utils.ocr_backends import get_backend_by_name, get_available_backends


def main():
    parser = argparse.ArgumentParser(description='Visualize text blocks using AI OCR backends')
    parser.add_argument('input_image', help='Input image file')
    parser.add_argument('output_image', nargs='?', help='Output image file (optional)')
    parser.add_argument('--backend', choices=['tesseract', 'google', 'aws', 'azure', 'openai'],
                       default='tesseract', help='OCR backend to use')
    parser.add_argument('--api-key', help='API key (for Google/Azure/OpenAI)')
    parser.add_argument('--credentials-path', help='Path to credentials file (for Google)')
    parser.add_argument('--aws-key', help='AWS access key ID')
    parser.add_argument('--aws-secret', help='AWS secret access key')
    parser.add_argument('--aws-region', default='us-east-1', help='AWS region')
    parser.add_argument('--endpoint', help='Azure endpoint URL')
    parser.add_argument('--min-confidence', type=int, default=30, help='Minimum confidence threshold')
    
    args = parser.parse_args()
    
    input_path = args.input_image
    output_path = args.output_image
    
    # If no output path provided, create one based on input path
    if output_path is None:
        input_file = Path(input_path)
        output_path = str(input_file.parent / f"{input_file.stem}_text_blocks{input_file.suffix}")
    
    print(f"Processing image: {input_path}")
    print(f"Using backend: {args.backend}")
    print(f"Output will be saved to: {output_path}")
    
    # Get backend
    backend_kwargs = {}
    if args.backend == 'google':
        if args.api_key:
            backend_kwargs['api_key'] = args.api_key
        if args.credentials_path:
            backend_kwargs['credentials_path'] = args.credentials_path
    elif args.backend == 'aws':
        if args.aws_key:
            backend_kwargs['aws_access_key_id'] = args.aws_key
        if args.aws_secret:
            backend_kwargs['aws_secret_access_key'] = args.aws_secret
        backend_kwargs['region_name'] = args.aws_region
    elif args.backend == 'azure':
        if not args.endpoint or not args.api_key:
            print("Error: Azure backend requires --endpoint and --api-key")
            sys.exit(1)
        backend_kwargs['endpoint'] = args.endpoint
        backend_kwargs['api_key'] = args.api_key
    elif args.backend == 'openai':
        if args.api_key:
            backend_kwargs['api_key'] = args.api_key
    
    backend = get_backend_by_name(args.backend, **backend_kwargs)
    
    if backend is None:
        print(f"Error: {args.backend} backend is not available or not configured.")
        print("\nAvailable backends:")
        available = get_available_backends()
        for b in available:
            print(f"  - {b.__class__.__name__}")
        sys.exit(1)
    
    print("Detecting text blocks...")
    
    try:
        # Detect and visualize text blocks
        annotated_image, text_blocks = visualize_text_blocks_from_file(
            input_path,
            output_path=output_path,
            rectangle_color=(0, 255, 0),  # Green rectangles
            rectangle_thickness=2,
            min_confidence=args.min_confidence,
            group_text_blocks=True,
            backend=backend
        )
        
        print(f"\n✓ Successfully detected {len(text_blocks)} text blocks")
        print(f"✓ Annotated image saved to: {output_path}")
        
        # Print summary of detected text blocks
        if text_blocks:
            print("\nDetected text blocks:")
            print("-" * 80)
            for i, block in enumerate(text_blocks[:10], 1):  # Show first 10
                x1, y1, x2, y2 = block['bbox']
                text = block['text'][:50]  # Truncate long text
                conf = block['confidence']
                print(f"{i:3d}. [{x1:4d}, {y1:4d}, {x2:4d}, {y2:4d}] "
                      f"conf={conf:3d} | {text}")
            if len(text_blocks) > 10:
                print(f"... and {len(text_blocks) - 10} more blocks")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
