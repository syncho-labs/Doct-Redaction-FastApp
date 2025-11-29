#!/usr/bin/env python3
"""
FastAPI PDF Redactor Service
Provides REST API endpoints for PDF redaction using PyMuPDF
"""

from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
import tempfile
import os
import json
import shutil
from pathlib import Path
import logging

# Import the redactor function from redactor.py
from redactor import redact_pdf

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="PDF Redactor API",
    description="API for redacting PII from PDF documents",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this for production
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
    redactions: List[RedactionCoordinate] = Field(..., min_length=1)

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
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
ALLOWED_EXTENSIONS = {'.pdf'}


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
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "redact": "/redact (POST)",
            "docs": "/docs",
            "redoc": "/redoc"
        },
        "description": "Upload a PDF and redaction coordinates to get a redacted PDF back"
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        service="PDF Redactor API",
        version="1.0.0"
    )


@app.post("/redact")
async def redact_pdf_endpoint(
    file: UploadFile = File(..., description="PDF file to redact"),
    redactions: str = Form(..., description="JSON string of redaction coordinates")
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
        
        if len(redactions_data) == 0:
            raise HTTPException(
                status_code=400,
                detail="At least one redaction coordinate is required"
            )
        
        # Validate each redaction coordinate
        try:
            validated_redactions = [RedactionCoordinate(**r) for r in redactions_data]
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid redaction coordinate: {str(e)}"
            )
        
        logger.info(f"Processing redaction request for file: {file.filename}")
        logger.info(f"Number of redactions: {len(validated_redactions)}")
        
        # Create temporary files
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_input_file:
            temp_input = temp_input_file.name
            # Read and save uploaded file
            content = await file.read()
            
            # Check file size
            if len(content) > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=400,
                    detail=f"File too large. Maximum size is {MAX_FILE_SIZE / (1024*1024)}MB"
                )
            
            temp_input_file.write(content)
        
        # Create temporary file for redactions JSON
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as temp_redactions_file:
            temp_redactions = temp_redactions_file.name
            json.dump(redactions_data, temp_redactions_file)
        
        # Create temporary file for output
        temp_output = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf').name
        
        # Perform redaction
        logger.info(f"Starting redaction process...")
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
        
        logger.info(f"Redaction completed successfully")
        
        # Generate output filename
        original_name = Path(file.filename).stem
        output_filename = f"{original_name}_redacted.pdf"
        
        # Return the redacted PDF
        return FileResponse(
            path=temp_output,
            media_type='application/pdf',
            filename=output_filename,
            background=None  # We'll clean up manually
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Unexpected error during redaction: {str(e)}", exc_info=True)
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
                    logger.warning(f"Failed to delete temporary file {temp_file}: {e}")


@app.post("/redact-json")
async def redact_pdf_json_endpoint(
    file: UploadFile = File(..., description="PDF file to redact"),
    redaction_request: RedactionRequest = None
):
    """
    Alternative endpoint that accepts redactions as JSON body instead of form data
    
    Note: This endpoint is less practical for file uploads but provided for completeness.
    Use the /redact endpoint for standard usage.
    """
    # Convert RedactionRequest to JSON string and call main endpoint
    redactions_json = json.dumps([r.dict() for r in redaction_request.redactions])
    return await redact_pdf_endpoint(file=file, redactions=redactions_json)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
