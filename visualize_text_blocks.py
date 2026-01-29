#!/usr/bin/env python3
"""
Script to visualize text blocks in an image by drawing rectangles around detected text.

Usage:
    python visualize_text_blocks.py <input_image> [output_image]
    
Example:
    python visualize_text_blocks.py plan.png plan_with_text_blocks.png
"""

import sys
import cv2
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from replan.desktop.utils.ocr import visualize_text_blocks_from_file, is_tesseract_available


def main():
    if len(sys.argv) < 2:
        print("Usage: python visualize_text_blocks.py <input_image> [output_image]")
        print("\nExample:")
        print("  python visualize_text_blocks.py plan.png plan_with_text_blocks.png")
        sys.exit(1)
    
    input_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None
    
    # If no output path provided, create one based on input path
    if output_path is None:
        input_file = Path(input_path)
        output_path = str(input_file.parent / f"{input_file.stem}_text_blocks{input_file.suffix}")
    
    # Check if Tesseract is available
    if not is_tesseract_available():
        print("Error: Tesseract OCR is not available.")
        print("Please install Tesseract OCR from: https://github.com/tesseract-ocr/tesseract")
        sys.exit(1)
    
    print(f"Processing image: {input_path}")
    print(f"Output will be saved to: {output_path}")
    print("Detecting text blocks...")
    
    try:
        # Detect and visualize text blocks
        annotated_image, text_blocks = visualize_text_blocks_from_file(
            input_path,
            output_path=output_path,
            rectangle_color=(0, 255, 0),  # Green rectangles
            rectangle_thickness=2,
            min_confidence=30,
            group_text_blocks=True
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
