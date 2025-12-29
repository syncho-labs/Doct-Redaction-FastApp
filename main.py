"""
FastAPI PDF Redactor Service
Provides REST API endpoints for PDF redaction using PyMuPDF
"""

from dotenv import load_dotenv
import os

# Load environment variables from .env.local (or .env if not found)
load_dotenv('.env.local')
load_dotenv()  # Fallback to .env

from fastapi import FastAPI, File, UploadFile, HTTPException, Form, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
import io
import logging
from pathlib import Path
from contextlib import asynccontextmanager
import tempfile
import json

from redactor import redact_pdf, redact_signatures_from_bytes

# Try to import YOLOS signature detector
try:
    from signature_detector_yolo import detect_all_signatures_yolo, is_yolo_available
    YOLO_AVAILABLE = is_yolo_available()
    # Note: Message is now printed in signature_detector_yolo.py
except Exception as e:
    YOLO_AVAILABLE = False
    print(f"Warning: YOLOS signature detector not available: {e}")



from centralized_logging import (
    log_router,
    get_logger,
    setup_logging,
    ContextLogger,
    start_log_cleanup_scheduler,
    stop_log_cleanup_scheduler
)

# Setup and get logger
setup_logging(log_dir="logs", service_name="pdf-processing")
logger = get_logger("pdf-processing")

# Global scheduler instance
scheduler = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events
    """
    global scheduler
    
    # Startup: Start log cleanup scheduler
    logger.info("Starting application...")
    scheduler = start_log_cleanup_scheduler()
    
    yield
    
    # Shutdown: Stop log cleanup scheduler
    logger.info("Shutting down application...")
    stop_log_cleanup_scheduler(scheduler)


# Create FastAPI app with lifespan
app = FastAPI(
    title="PDF Redactor API",
    description="API for redacting PII from PDF documents",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Include log API router
app.include_router(log_router)

# CORS configuration from environment variable
# In production, set CORS_ORIGINS="https://yourdomain.com,https://app.yourdomain.com"
ALLOWED_ORIGINS = os.environ.get(
    "CORS_ORIGINS",
    "https://dga-document-agent.gosign.de/"  # Default for production
    # "http://localhost:3000,http://localhost:8080"  # Default for dev
).split(",")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models for request/response validation
class RedactionCoordinate(BaseModel):
    """Model for a single redaction coordinate"""
    pageIndex: int = Field(..., ge=0, description="Zero-based page index")
    x: float = Field(..., ge=0, description="X coordinate")
    y: float = Field(..., ge=0, description="Y coordinate")
    width: float = Field(..., gt=0, description="Width of redaction area")
    height: float = Field(..., gt=0, description="Height of redaction area")
    text: Optional[str] = Field(None, description="Optional: PII text being redacted")
    category: Optional[str] = Field(None, description="Optional: PII category")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "pageIndex": 0,
                "x": 100.0,
                "y": 200.0,
                "width": 150.0,
                "height": 20.0,
                "text": "John Doe",
                "category": "Person"
            }
        }
    )


class RedactionRequest(BaseModel):
    """Model for redaction request"""
    redactions: List[RedactionCoordinate] = Field(..., min_length=0)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "redactions": [
                    {
                        "pageIndex": 0,
                        "x": 100.0,
                        "y": 200.0,
                        "width": 150.0,
                        "height": 20.0,
                        "text": "John Doe",
                        "category": "Person"
                    }
                ]
            }
        }
    )


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    service: str
    version: str


# Configuration
ALLOWED_EXTENSIONS = {'.pdf'}


def cleanup_file(path: str) -> None:
    """Delete a temporary file if it exists"""
    try:
        if path and os.path.exists(path):
            os.unlink(path)
            logger.debug(f"Cleaned up temporary file: {path}", extra={'context': {'file': path}})
    except Exception as e:
        logger.warning(f"Failed to cleanup temporary file {path}: {e}", extra={'context': {'file': path, 'error': str(e)}})


def validate_pdf_file(file: UploadFile) -> None:
    """Validate uploaded PDF file"""
    # Check file extension
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Only PDF files are allowed. Got: {file_ext}"
        )
    
    # Check content type
    if file.content_type not in ['application/pdf', 'application/x-pdf']:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid content type. Expected application/pdf, got: {file.content_type}"
        )


@app.get("/", response_model=dict)
async def root():
    """Root endpoint with API information"""
    return {
        "service": "PDF Redactor API",
        "version": "1.1.0",
        "endpoints": {
            "health": "/health",
            "redact": "/redact (POST)",
            "detect_signatures": "/detect-signatures (POST)",
            "detect_and_redact_signatures": "/detect-and-redact-signatures (POST)",
            "docs": "/docs",
            "redoc": "/redoc"
        },
        "signature_detection": {
            "yolo_available": YOLO_AVAILABLE
        },
        "description": "Upload a PDF and redaction coordinates to get a redacted PDF back. Also supports AI-powered signature detection and redaction."
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        service="PDF Redactor API",
        version="1.0.0"
    )


@app.post("/detect-signatures")
async def detect_signatures_endpoint(
    file: UploadFile = File(..., description="PDF file to scan for signatures"),
    existing_signatures: str = Form(default="[]", description="JSON array of already detected signatures to avoid duplicates"),
    confidence: float = Form(default=0.25, description="Minimum confidence threshold (0.0-1.0)")
):
    """
    Detect handwritten signatures in a PDF using YOLOS AI model
    
    Args:
        file: PDF file to scan
        existing_signatures: JSON array of already detected signatures (optional)
        confidence: Minimum confidence threshold for detections (default 0.25)
        
    Returns:
        JSON array of detected signature coordinates
    """
    if not YOLO_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="YOLOS signature detection is not available on this server"
        )
    
    try:
        # Validate PDF file
        validate_pdf_file(file)
        
        # Read PDF content
        pdf_content = await file.read()
        
        # Parse existing signatures
        try:
            existing = json.loads(existing_signatures)
        except json.JSONDecodeError:
            existing = []
        
        logger.info(f"Detecting signatures in {file.filename}", 
                    extra={'context': {'filename': file.filename, 'confidence': confidence}})
        
        # Detect signatures using YOLOS
        signatures = detect_all_signatures_yolo(pdf_content, existing)
        
        logger.info(f"YOLOS found {len(signatures)} signatures", 
                    extra={'context': {'filename': file.filename, 'count': len(signatures)}})
        
        return {
            "success": True,
            "signatures": signatures,
            "count": len(signatures),
            "method": "yolo"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Signature detection failed: {str(e)}", extra={'context': {'error': str(e)}})
        raise HTTPException(
            status_code=500,
            detail=f"Signature detection failed: {str(e)}"
        )


@app.post("/detect-and-redact-signatures")
async def detect_and_redact_signatures_endpoint(
    file: UploadFile = File(..., description="PDF file to detect and redact signatures from"),
    existing_signatures: str = Form(default="[]", description="JSON array of additional signature coordinates to redact"),
    confidence: float = Form(default=0.25, description="Minimum confidence threshold for detection (0.0-1.0)")
):
    """
    Detect and redact handwritten signatures in a PDF in one step.
    
    Uses YOLOS AI model to detect signatures, then covers them with white rectangles.
    Works on image-based signatures that Azure OCR cannot detect.
    
    Args:
        file: PDF file to process
        existing_signatures: JSON array of additional signature coordinates to redact
        confidence: Minimum confidence for detections (default 0.25)
        
    Returns:
        Redacted PDF file with signatures covered by white rectangles
    """
    if not YOLO_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="YOLOS signature detection is not available on this server"
        )
    
    try:
        # Validate PDF file
        validate_pdf_file(file)
        
        # Read PDF content
        pdf_content = await file.read()
        
        # Parse existing signatures (additional ones to include)
        try:
            existing = json.loads(existing_signatures)
        except json.JSONDecodeError:
            existing = []
        
        logger.info(f"Detecting and redacting signatures in {file.filename}", 
                    extra={'context': {'filename': file.filename, 'confidence': confidence}})
        
        # Detect signatures using YOLOS
        detected_signatures = detect_all_signatures_yolo(pdf_content, existing)
        
        logger.info(f"YOLOS found {len(detected_signatures)} signatures", 
                    extra={'context': {'filename': file.filename, 'count': len(detected_signatures)}})
        
        # Combine with any existing signatures provided
        all_signatures = existing + detected_signatures
        
        if not all_signatures:
            logger.info(f"No signatures found in {file.filename}, returning original PDF")
            return StreamingResponse(
                io.BytesIO(pdf_content),
                media_type='application/pdf',
                headers={
                    "Content-Disposition": f'attachment; filename="{Path(file.filename).stem}_redacted.pdf"',
                    "X-Signatures-Detected": "0",
                    "X-Signatures-Redacted": "0",
                    "X-Detection-Method": "yolo"
                }
            )
        
        logger.info(f"Redacting {len(all_signatures)} signatures from {file.filename}",
                    extra={'context': {'filename': file.filename, 'signature_count': len(all_signatures)}})
        
        # Redact all detected signatures
        redacted_pdf_bytes = redact_signatures_from_bytes(pdf_content, all_signatures)
        
        logger.info(f"Successfully redacted {len(all_signatures)} signatures from {file.filename}",
                    extra={'context': {
                        'filename': file.filename,
                        'signatures_detected': len(detected_signatures),
                        'signatures_redacted': len(all_signatures)
                    }})
        
        # Return the redacted PDF
        return StreamingResponse(
            io.BytesIO(redacted_pdf_bytes),
            media_type='application/pdf',
            headers={
                "Content-Disposition": f'attachment; filename="{Path(file.filename).stem}_signatures_redacted.pdf"',
                "X-Signatures-Detected": str(len(detected_signatures)),
                "X-Signatures-Redacted": str(len(all_signatures)),
                "X-Detection-Method": "yolo"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Signature detection and redaction failed: {str(e)}", 
                     extra={'context': {'error': str(e), 'filename': file.filename}})
        raise HTTPException(
            status_code=500,
            detail=f"Signature detection and redaction failed: {str(e)}"
        )


@app.post("/redact")
async def redact_pdf_endpoint(
    file: UploadFile = File(..., description="PDF file to redact"),
    redactions: str = Form(..., description="JSON string of redaction coordinates"),
    background_tasks: BackgroundTasks = None
):
    """
    Redact a PDF file based on provided coordinates
    
    Args:
        file: PDF file to redact
        redactions: JSON string containing array of redaction coordinates
        
    Returns:
        Redacted PDF file
        
    Example redactions JSON:
    ```json
    [
        {
            "pageIndex": 0,
            "x": 100.0,
            "y": 200.0,
            "width": 150.0,
            "height": 20.0,
            "text": "John Doe",
            "category": "Person"
        }
    ]
    ```
    """
    temp_input = None
    temp_redactions = None
    temp_output = None
    
    try:
        # Validate PDF file
        validate_pdf_file(file)
        
        # Parse redactions JSON
        try:
            redactions_data = json.loads(redactions)
        except json.JSONDecodeError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid JSON in redactions parameter: {str(e)}"
            )
        
        # Validate redactions data
        if not isinstance(redactions_data, list):
            raise HTTPException(
                status_code=400,
                detail="Redactions must be an array of coordinate objects"
            )
        
        # If no redactions, return the original PDF unchanged
        if len(redactions_data) == 0:
            logger.info(
                f"No redactions requested for file: {file.filename}, returning original PDF",
                extra={
                    'context': {'filename': file.filename, 'redaction_count': 0}
                }
            )
            
            # Save the uploaded file to a temp location and return it
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                temp_output = temp_file.name
                content = await file.read()
                temp_file.write(content)
            
            # Generate output filename
            original_name = Path(file.filename).stem
            output_filename = f"{original_name}_redacted.pdf"
            
            # Schedule cleanup
            if background_tasks:
                background_tasks.add_task(cleanup_file, temp_output)
            
            return FileResponse(
                path=temp_output,
                media_type='application/pdf',
                filename=output_filename,
                headers={"X-Redactions-Applied": "0"}
            )
        
        # Validate each redaction coordinate
        try:
            validated_redactions = [RedactionCoordinate(**r) for r in redactions_data]
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid redaction coordinate: {str(e)}"
            )
        
        logger.info(
            f"Processing redaction request for file: {file.filename}",
            extra={
                'context': {
                    'filename': file.filename,
                    'redaction_count': len(validated_redactions)
                }
            }
        )
        
        # Create temporary files
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_input_file:
            temp_input = temp_input_file.name
            # Read and save uploaded file
            content = await file.read()
            temp_input_file.write(content)
        
        # Create temporary file for redactions JSON
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as temp_redactions_file:
            temp_redactions = temp_redactions_file.name
            json.dump(redactions_data, temp_redactions_file)
        
        # Create temporary file for output
        temp_output = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf').name
        
        # Perform redaction
        logger.info(
            f"Starting redaction process for {file.filename}",
            extra={
                'context': {'filename': file.filename, 'temp_input': temp_input, 'temp_output': temp_output}
            }
        )
        success = redact_pdf(temp_input, temp_redactions, temp_output)
        
        if not success:
            raise HTTPException(
                status_code=500,
                detail="Redaction process failed. Check server logs for details."
            )
        
        # Verify output file exists and has content
        if not os.path.exists(temp_output) or os.path.getsize(temp_output) == 0:
            raise HTTPException(
                status_code=500,
                detail="Redaction completed but output file is invalid"
            )
        
        logger.info(
            f"Redaction completed successfully for {file.filename}",
            extra={
                'context': {'filename': file.filename, 'output_size': os.path.getsize(temp_output)}
            }
        )
        
        # Generate output filename
        original_name = Path(file.filename).stem
        output_filename = f"{original_name}_redacted.pdf"
        
        # Schedule cleanup of temp_output after response is sent
        if background_tasks:
            background_tasks.add_task(cleanup_file, temp_output)
        
        # Return the redacted PDF
        return FileResponse(
            path=temp_output,
            media_type='application/pdf',
            filename=output_filename
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(
            f"Unexpected error during redaction: {str(e)}",
            exc_info=True,
            extra={'context': {'filename': file.filename if file else 'unknown'}}
        )
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )
    finally:
        # Clean up temporary files
        # Note: temp_output is returned as FileResponse, so we can't delete it immediately
        # In production, implement a cleanup task or use background tasks
        for temp_file in [temp_input, temp_redactions]:
            if temp_file and os.path.exists(temp_file):
                try:
                    os.unlink(temp_file)
                except Exception as e:
                    logger.warning(
                        f"Failed to delete temporary file {temp_file}: {e}",
                        extra={
                            'context': {'temp_file': temp_file, 'error': str(e)}
                        }
                    )


@app.post("/redact-json")
async def redact_pdf_json_endpoint(
    redaction_request: RedactionRequest,
    file: UploadFile = File(..., description="PDF file to redact"),
    background_tasks: BackgroundTasks = None
):
    """
    Alternative endpoint that accepts redactions as JSON body instead of form data
    
    Note: This endpoint is less practical for file uploads but provided for completeness.
    Use the /redact endpoint for standard usage.
    """
    # Convert RedactionRequest to JSON string and call main endpoint
    redactions_json = json.dumps([r.model_dump() for r in redaction_request.redactions])
    return await redact_pdf_endpoint(file=file, redactions=redactions_json, background_tasks=background_tasks)


if __name__ == "__main__":
    import uvicorn
    import logging
    
    # Suppress watchfiles "changes detected" messages
    logging.getLogger("watchfiles").setLevel(logging.WARNING)
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
