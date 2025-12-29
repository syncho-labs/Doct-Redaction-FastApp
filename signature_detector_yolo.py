#!/usr/bin/env python3
"""
YOLOS-based signature detection module
Uses YOLOS transformer model from HuggingFace (88.7% mAP50)
Specifically trained for handwritten signature detection

Model source: https://huggingface.co/mdefrance/yolos-small-signature-detection
"""

import os
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import io

import fitz  # PyMuPDF
import numpy as np
from PIL import Image

# Configure logging - use centralized logger from pdf-processing
logger = logging.getLogger("pdf-processing")

# Global model instance (lazy loaded)
_model = None
_processor = None
_model_available = False

# Default confidence threshold (25% - balance between catching signatures and avoiding false positives)
DEFAULT_CONFIDENCE = 0.25


def _get_model():
    """
    Lazy load the YOLOS transformer model from HuggingFace
    Returns the model instance or None if not available
    """
    global _model, _processor, _model_available
    
    if _model is not None:
        return _model
    
    try:
        from transformers import AutoImageProcessor, AutoModelForObjectDetection
        
        model_name = "mdefrance/yolos-small-signature-detection"
        logger.info(f"Loading YOLOS transformer model from HuggingFace: {model_name}")
        
        _processor = AutoImageProcessor.from_pretrained(model_name)
        _model = AutoModelForObjectDetection.from_pretrained(model_name)
        _model_available = True
        logger.info("YOLOS signature model loaded successfully (88.7% mAP50)")
        print("✓ YOLOS signature detector loaded successfully (HuggingFace, 88.7% accuracy)")
        return _model
    except ImportError as e:
        logger.error(f"Transformers library not installed: {e}")
        logger.error("Install with: pip install transformers")
        print("✗ YOLOS not available - install transformers: pip install transformers")
    except Exception as e:
        logger.error(f"Failed to load YOLOS model: {e}")
        print(f"✗ Failed to load YOLOS model: {e}")
    
    _model_available = False
    return None


def is_yolo_available() -> bool:
    """Check if YOLOS signature detection is available"""
    model = _get_model()
    return model is not None





def pdf_page_to_image(page: fitz.Page, zoom: float = 2.0) -> np.ndarray:
    """
    Convert a PyMuPDF page to a numpy array (RGB format)
    
    Args:
        page: PyMuPDF page object
        zoom: Zoom factor for higher resolution (default 2.0 = 144 DPI)
        
    Returns:
        Numpy array of the page image in RGB format
    """
    # Create transformation matrix for zoom
    mat = fitz.Matrix(zoom, zoom)
    
    # Render page to pixmap
    pix = page.get_pixmap(matrix=mat, alpha=False)
    
    # Convert to numpy array
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
    
    return img


def detect_signatures_yolo(
    pdf_bytes: bytes,
    existing_signatures: Optional[List[Dict]] = None,
    confidence_threshold: float = None,  # Uses DEFAULT_CONFIDENCE if not specified
    zoom: float = 2.0  # Reduced zoom for speed
) -> List[Dict]:
    """
    Detect signatures in a PDF using YOLOS transformer model
    
    Args:
        pdf_bytes: PDF file as bytes
        existing_signatures: Already detected signatures to avoid duplicates
        confidence_threshold: Minimum confidence for detections (default 0.50)
        zoom: Zoom factor for page rendering (default 2.0)
        
    Returns:
        List of signature redaction coordinates
    """
    if confidence_threshold is None:
        confidence_threshold = DEFAULT_CONFIDENCE
    
    model = _get_model()
    if model is None:
        logger.warning("YOLOS model not available, returning empty list")
        return []
    
    existing_signatures = existing_signatures or []
    detected_signatures = []
    
    try:
        import torch
        
        # Open PDF
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        logger.info(f"Processing PDF with {len(doc)} pages for YOLOS signature detection (confidence >= {confidence_threshold:.0%})")
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            page_rect = page.rect
            
            # Create transformation matrix for zoom
            mat = fitz.Matrix(zoom, zoom)
            
            # Render full page to pixmap
            pix = page.get_pixmap(matrix=mat, alpha=False)
            
            # Convert to numpy array
            img_array = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
            
            # Convert to PIL Image
            pil_image = Image.fromarray(img_array)
            
            # Run YOLOS inference
            inputs = _processor(images=pil_image, return_tensors="pt")
            with torch.no_grad():
                outputs = model(**inputs)
            
            # Convert outputs to COCO format
            target_sizes = torch.tensor([pil_image.size[::-1]])  # height, width
            results = _processor.post_process_object_detection(
                outputs, 
                threshold=confidence_threshold, 
                target_sizes=target_sizes
            )[0]
            
            # Process detections
            for score, box in zip(results["scores"], results["boxes"]):
                conf = score.item()
                x1_img, y1_img, x2_img, y2_img = box.tolist()
                
                # Scale back to PDF coordinates (accounting for zoom)
                x1 = x1_img / zoom
                y1 = y1_img / zoom
                x2 = x2_img / zoom
                y2 = y2_img / zoom
                
                # Calculate width and height
                width = x2 - x1
                height = y2 - y1
                
                # Add small padding around the signature (5% on each side)
                padding_x = width * 0.05
                padding_y = height * 0.05
                
                x1 = max(0, x1 - padding_x)
                y1 = max(0, y1 - padding_y)
                width = width + (2 * padding_x)
                height = height + (2 * padding_y)
                
                # Ensure we don't exceed page bounds
                if x1 + width > page_rect.width:
                    width = page_rect.width - x1
                if y1 + height > page_rect.height:
                    height = page_rect.height - y1
                
                # Create signature detection record
                signature = {
                    "pageIndex": page_num,
                    "x": float(x1),
                    "y": float(y1),
                    "width": float(width),
                    "height": float(height),
                    "text": f"Signature (YOLOS: {conf:.0%})",
                    "category": "Signature",
                    "confidence": conf
                }
                
                # Check for duplicates with existing signatures
                if not _is_duplicate(signature, existing_signatures, detected_signatures):
                    detected_signatures.append(signature)
                    logger.info(
                        f"YOLOS detected signature on page {page_num + 1}: "
                        f"({x1:.0f}, {y1:.0f}) size {width:.0f}x{height:.0f} confidence {conf:.0%}"
                    )
        
        doc.close()
        logger.info(f"YOLOS found {len(detected_signatures)} signatures in PDF")
        
    except Exception as e:
        logger.error(f"Error during YOLOS signature detection: {e}", exc_info=True)
        return []
    
    return detected_signatures




def _is_duplicate(
    new_sig: Dict,
    existing_signatures: List[Dict],
    detected_signatures: List[Dict],
    overlap_threshold: float = 0.5
) -> bool:
    """
    Check if a signature detection overlaps significantly with existing ones
    
    Args:
        new_sig: New signature detection
        existing_signatures: Previously detected signatures
        detected_signatures: Signatures detected in this run
        overlap_threshold: IoU threshold for considering as duplicate (default 0.5)
        
    Returns:
        True if this is a duplicate detection
    """
    all_existing = existing_signatures + detected_signatures
    
    for existing in all_existing:
        # Only compare signatures on the same page
        if existing.get("pageIndex") != new_sig["pageIndex"]:
            continue
        
        # Calculate IoU (Intersection over Union)
        iou = _calculate_iou(new_sig, existing)
        
        if iou > overlap_threshold:
            return True
    
    return False


def _calculate_iou(box1: Dict, box2: Dict) -> float:
    """
    Calculate Intersection over Union between two bounding boxes
    
    Args:
        box1, box2: Dictionaries with x, y, width, height
        
    Returns:
        IoU value between 0 and 1
    """
    # Calculate box coordinates
    x1_1, y1_1 = box1["x"], box1["y"]
    x2_1, y2_1 = x1_1 + box1["width"], y1_1 + box1["height"]
    
    x1_2, y1_2 = box2["x"], box2["y"]
    x2_2, y2_2 = x1_2 + box2["width"], y1_2 + box2["height"]
    
    # Calculate intersection
    xi1 = max(x1_1, x1_2)
    yi1 = max(y1_1, y1_2)
    xi2 = min(x2_1, x2_2)
    yi2 = min(y2_1, y2_2)
    
    if xi2 <= xi1 or yi2 <= yi1:
        return 0.0
    
    intersection = (xi2 - xi1) * (yi2 - yi1)
    
    # Calculate union
    area1 = box1["width"] * box1["height"]
    area2 = box2["width"] * box2["height"]
    union = area1 + area2 - intersection
    
    if union <= 0:
        return 0.0
    
    return intersection / union


def detect_all_signatures_yolo(
    pdf_bytes: bytes,
    existing_signatures: Optional[List[Dict]] = None,
    confidence_threshold: float = None  # Uses DEFAULT_CONFIDENCE if not specified
) -> List[Dict]:
    """
    Main entry point for YOLOS signature detection
    
    Args:
        pdf_bytes: PDF file as bytes
        existing_signatures: Already detected signatures to avoid duplicates
        confidence_threshold: Minimum confidence for detections (default 0.50)
        
    Returns:
        List of signature redaction coordinates
    """
    if confidence_threshold is None:
        confidence_threshold = DEFAULT_CONFIDENCE
    
    return detect_signatures_yolo(
        pdf_bytes=pdf_bytes,
        existing_signatures=existing_signatures,
        confidence_threshold=confidence_threshold
    )



# For testing
if __name__ == '__main__':
    import sys
    
    # Configure logging for testing
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    if len(sys.argv) < 2:
        print("Usage: python signature_detector_yolo.py <pdf_path> [confidence]")
        print(f"\nDefault confidence threshold: {DEFAULT_CONFIDENCE:.0%}")
        print("\nChecking YOLOS availability...")
        
        if is_yolo_available():
            print("✓ YOLOS signature detection is available")
        else:
            print("✗ YOLOS signature detection is NOT available")
            print("  Install transformers: pip install transformers")
        
        sys.exit(0)
    
    pdf_path = sys.argv[1]
    confidence = float(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_CONFIDENCE
    
    print(f"\nProcessing: {pdf_path}")
    print(f"Confidence threshold: {confidence:.0%}")
    print("-" * 50)
    
    with open(pdf_path, 'rb') as f:
        pdf_bytes = f.read()
    
    signatures = detect_all_signatures_yolo(
        pdf_bytes,
        confidence_threshold=confidence
    )
    
    print("\n" + "=" * 50)
    print("DETECTED SIGNATURES (YOLOS):")
    print("=" * 50)
    
    if not signatures:
        print("  No signatures detected")
    else:
        for sig in signatures:
            print(
                f"  Page {sig['pageIndex']+1}: "
                f"({sig['x']:.0f}, {sig['y']:.0f}) "
                f"size {sig['width']:.0f}x{sig['height']:.0f} "
                f"confidence {sig['confidence']:.0%}"
            )
    
    print(f"\nTotal: {len(signatures)} signatures found")

