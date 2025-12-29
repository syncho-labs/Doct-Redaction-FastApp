# Multi-stage build for optimized image size
FROM python:3.11-slim AS builder

# Set working directory
WORKDIR /app

# Install system dependencies required for compilation (if needed)
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --user -r requirements.txt

# Pre-download YOLOS model from HuggingFace (baked into image)
RUN python -c "from transformers import AutoImageProcessor, AutoModelForObjectDetection; \
    AutoImageProcessor.from_pretrained('mdefrance/yolos-small-signature-detection'); \
    AutoModelForObjectDetection.from_pretrained('mdefrance/yolos-small-signature-detection'); \
    print('✓ YOLOS model downloaded successfully')"

# Final stage
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    mupdf-tools \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copy Python dependencies from builder
COPY --from=builder /root/.local /root/.local

# Copy HuggingFace cache with pre-downloaded model
COPY --from=builder /root/.cache/huggingface /root/.cache/huggingface

# Copy application files
COPY main.py .
COPY redactor.py .
COPY centralized_logging/ ./centralized_logging/

# Copy YOLOS signature detection
COPY signature_detector_yolo.py .

# Make sure scripts are in PATH
ENV PATH=/root/.local/bin:$PATH

# Environment variable to use cached model (no internet needed at runtime)
ENV TRANSFORMERS_OFFLINE=1
ENV HF_HUB_OFFLINE=1

# Create directory for temporary files
RUN mkdir -p /tmp/pdf-redactor

# Expose port
EXPOSE 8000

# Health check endpoint available at /health
# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

