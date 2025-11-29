#!/usr/bin/env python3
"""
PDF Redaction Script using PyMuPDF
Permanently removes PII from PDFs by applying redaction annotations
"""

import fitz  # PyMuPDF
import json
import sys
import os

def redact_pdf(input_path, redactions_path, output_path):
    """
    Redact a PDF based on coordinate data
    
    Args:
        input_path: Path to input PDF
        redactions_path: Path to JSON file with redaction coordinates
        output_path: Path to save redacted PDF
    """
    try:
        # Open the PDF
        doc = fitz.open(input_path)
        print(f"Opened PDF: {input_path}")
        print(f"Total pages: {len(doc)}")
        
        # Load redaction coordinates
        with open(redactions_path, 'r') as f:
            redactions = json.load(f)
        
        print(f"Total redactions to apply: {len(redactions)}")
        
        # Group redactions by page for efficiency
        redactions_by_page = {}
        for redaction in redactions:
            page_idx = redaction['pageIndex']
            if page_idx not in redactions_by_page:
                redactions_by_page[page_idx] = []
            redactions_by_page[page_idx].append(redaction)
        
        # Apply redactions page by page
        for page_idx, page_redactions in redactions_by_page.items():
            if page_idx >= len(doc):
                print(f"Warning: Page index {page_idx} out of range, skipping")
                continue
            
            page = doc[page_idx]
            print(f"Processing page {page_idx + 1}: {len(page_redactions)} redactions")
            
            for redaction in page_redactions:
                # Create rectangle for redaction
                # PyMuPDF uses (x0, y0, x1, y1) format
                rect = fitz.Rect(
                    redaction['x'],
                    redaction['y'],
                    redaction['x'] + redaction['width'],
                    redaction['y'] + redaction['height']
                )
                
                # Add redaction annotation with black fill
                # text_color: color of overlay text (if any)
                # fill: color to fill redacted area
                annot = page.add_redact_annot(
                    rect,
                    text="",  # No replacement text
                    fill=(0, 0, 0),  # black fill (RGB 0-1 scale)
                    text_color=(0, 0, 0)
                )
                
                print(f"  Added redaction at ({redaction['x']:.1f}, {redaction['y']:.1f})")
        
        # Apply all redactions - this permanently removes the text
        print("Applying redactions (permanently removing text)...")
        redaction_count = 0
        for page in doc:
            redaction_count += page.apply_redactions(
                images=fitz.PDF_REDACT_IMAGE_NONE  # Don't redact images, only text
            )
        
        print(f"Applied {redaction_count} redactions successfully")
        
        # Save the redacted PDF
        doc.save(
            output_path,
            garbage=4,  # Maximum garbage collection
            deflate=True,  # Compress
            clean=True  # Clean up unused objects
        )
        doc.close()
        
        print(f"Redacted PDF saved to: {output_path}")
        return True
        
    except Exception as e:
        print(f"Error during redaction: {str(e)}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return False

def main():
    if len(sys.argv) != 4:
        print("Usage: python3 redactor.py <input_pdf> <redactions_json> <output_pdf>")
        print("\nRedactions JSON format:")
        print('[')
        print('  {')
        print('    "pageIndex": 0,')
        print('    "x": 100,')
        print('    "y": 200,')
        print('    "width": 150,')
        print('    "height": 20,')
        print('    "text": "PII text (optional)",')
        print('    "category": "Person (optional)"')
        print('  }')
        print(']')
        sys.exit(1)
    
    input_pdf = sys.argv[1]
    redactions_json = sys.argv[2]
    output_pdf = sys.argv[3]
    
    # Validate input files exist
    if not os.path.exists(input_pdf):
        print(f"Error: Input PDF not found: {input_pdf}", file=sys.stderr)
        sys.exit(1)
    
    if not os.path.exists(redactions_json):
        print(f"Error: Redactions JSON not found: {redactions_json}", file=sys.stderr)
        sys.exit(1)
    
    # Perform redaction
    success = redact_pdf(input_pdf, redactions_json, output_pdf)
    
    sys.exit(0 if success else 1)

if __name__ == '__main__':
    main()