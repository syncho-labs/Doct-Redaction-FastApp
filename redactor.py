#!/usr/bin/env python3
"""
PDF Redaction Script using PyMuPDF
Permanently removes PII from PDFs by applying redaction annotations
"""

import fitz  # PyMuPDF
import json
import sys
import os

def transform_rect_for_rotation(rect, rotation, mediabox):
    """
    Transform a rectangle from displayed coordinates to internal coordinates
    based on page rotation.
    
    Args:
        rect: fitz.Rect in displayed (visual) coordinates
        rotation: Page rotation in degrees (0, 90, 180, 270)
        mediabox: Page mediabox (internal dimensions)
    
    Returns:
        fitz.Rect in internal coordinates
    """
    if rotation == 0:
        return rect
    
    x, y, x2, y2 = rect.x0, rect.y0, rect.x1, rect.y1
    w = x2 - x
    h = y2 - y
    
    if rotation == 90:
        # 90 clockwise
        new_x = mediabox.height - y - h
        new_y = x
        new_w = h
        new_h = w
        return fitz.Rect(new_x, new_y, new_x + new_w, new_y + new_h)
    elif rotation == 180:
        # 180
        new_x = mediabox.width - x - w
        new_y = mediabox.height - y - h
        return fitz.Rect(new_x, new_y, new_x + w, new_y + h)
    elif rotation == 270:
        # 270
        new_x = mediabox.width - y - h
        new_y = x
        new_w = h
        new_h = w
        return fitz.Rect(new_x, new_y, new_x + new_w, new_y + new_h)
    
    return rect


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
            rotation = page.rotation
            page_rect = page.rect
            mediabox = page.mediabox
            
            print(f"Processing page {page_idx + 1}: {len(page_redactions)} redactions (rotation: {rotation}°, size: {page_rect.width:.0f}x{page_rect.height:.0f})")
            
            for redaction in page_redactions:
                # Get coordinates from Azure (already converted to points)
                x = redaction['x']
                y = redaction['y']
                w = redaction['width']
                h = redaction['height']
                
                # Safety check: Skip redactions that are too large (likely coordinate errors)
                max_width = page_rect.width * 0.5  # Max 50% of page width
                max_height = page_rect.height * 0.5  # Max 50% of page height
                if w > max_width or h > max_height:
                    category = redaction.get('category', 'Unknown')
                    print(f"  SKIPPED oversized redaction [{category}] at ({x:.1f}, {y:.1f}) size {w:.1f}x{h:.1f}")
                    continue
                
                # Create rectangle in displayed coordinates
                rect = fitz.Rect(x, y, x + w, y + h)
                
                # Transform for rotated pages
                internal_rect = transform_rect_for_rotation(rect, rotation, mediabox)
                
                # Add redaction annotation - this marks content for removal
                # Using white fill so redacted areas look clean
                page.add_redact_annot(
                    internal_rect,
                    text="",  # No replacement text
                    fill=(1, 1, 1),  # White fill
                    cross_out=False
                )
                
                category = redaction.get('category', 'Unknown')
                print(f"  Added redaction [{category}] at ({x:.1f}, {y:.1f}) size {w:.1f}x{h:.1f}")
        
        # Apply all redactions - THIS PERMANENTLY REMOVES THE CONTENT
        print("Applying redactions (permanently removing text and image content)...")
        redacted_pages = 0
        for page in doc:
            # PDF_REDACT_IMAGE_PIXELS: Redact specific pixels in images within redaction areas
            # This preserves the rest of the image (important for scanned PDFs)
            # PDF_REDACT_IMAGE_REMOVE would remove entire images, which is wrong for scans
            count = page.apply_redactions(
                images=fitz.PDF_REDACT_IMAGE_PIXELS
            )
            if count > 0:
                redacted_pages += 1
        
        print(f"Applied redactions on {redacted_pages} pages")
        
        # Save the redacted PDF - optimized to minimize file size
        doc.save(
            output_path,
            garbage=4,        # Maximum garbage collection - removes ALL unused objects
            deflate=True,     # Compress streams
            deflate_images=True,  # Also compress images
            deflate_fonts=True,   # Also compress fonts
            clean=True,       # Clean up cross-references
            pretty=False,     # Don't add whitespace (smaller file)
            linear=False      # Don't linearize (faster, similar size)
        )
        doc.close()
        
        print(f"Redacted PDF saved to: {output_path}")
        return True
        
    except Exception as e:
        print(f"Error during redaction: {str(e)}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return False


def redact_signatures_from_bytes(pdf_bytes: bytes, signatures: list) -> bytes:
    """
    Redact signatures from a PDF given as bytes.
    Uses white rectangles drawn OVER the content (not modifying underlying images).
    This approach minimizes file size increase.
    
    Args:
        pdf_bytes: PDF file as bytes
        signatures: List of signature coordinates, each with:
            - pageIndex: Zero-based page index
            - x, y: Top-left corner coordinates
            - width, height: Size of the signature area
            
    Returns:
        Redacted PDF as bytes
    """
    import io
    
    # Open PDF from bytes
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    
    # Group signatures by page
    signatures_by_page = {}
    for sig in signatures:
        page_idx = sig['pageIndex']
        if page_idx not in signatures_by_page:
            signatures_by_page[page_idx] = []
        signatures_by_page[page_idx].append(sig)
    
    # Apply white rectangles page by page (drawn over content, not modifying images)
    for page_idx, page_signatures in signatures_by_page.items():
        if page_idx >= len(doc):
            print(f"Warning: Page index {page_idx} out of range, skipping")
            continue
        
        page = doc[page_idx]
        rotation = page.rotation
        mediabox = page.mediabox
        
        for sig in page_signatures:
            x = sig['x']
            y = sig['y']
            w = sig['width']
            h = sig['height']
            
            # Create rectangle in displayed coordinates
            rect = fitz.Rect(x, y, x + w, y + h)
            
            # Transform for rotated pages
            internal_rect = transform_rect_for_rotation(rect, rotation, mediabox)
            
            # Draw white rectangle OVER the content (this doesn't modify underlying image data)
            # This is much more efficient than apply_redactions(images=PDF_REDACT_IMAGE_PIXELS)
            shape = page.new_shape()
            shape.draw_rect(internal_rect)
            shape.finish(
                color=None,      # No border
                fill=(1, 1, 1),  # White fill
                width=0          # No stroke width
            )
            shape.commit()
            
            confidence = sig.get('confidence', 0)
            print(f"  Added signature cover on page {page_idx + 1} at ({x:.1f}, {y:.1f}) size {w:.1f}x{h:.1f} confidence {confidence:.2%}")
    
    # Save to bytes - optimized to minimize file size
    # Using incremental=False and no image modification keeps size small
    output_buffer = io.BytesIO()
    doc.save(
        output_buffer,
        garbage=4,          # Maximum garbage collection
        deflate=True,       # Compress streams
        deflate_images=True,
        deflate_fonts=True,
        clean=True,
        pretty=False,       # Don't add whitespace (smaller file)
        linear=False        # Don't linearize (faster, similar size)
    )
    doc.close()
    
    return output_buffer.getvalue()



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