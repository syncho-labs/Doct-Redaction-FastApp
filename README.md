# PDF Redactor API

A FastAPI-based REST API service for redacting PII (Personally Identifiable Information) from PDF documents using PyMuPDF.

## Features

- 🚀 **Fast & Efficient**: Built with FastAPI for high performance
- 📄 **PDF Redaction**: Permanently removes PII from PDFs based on coordinates
- 🔒 **Secure**: Validates inputs and handles files safely
- 🐳 **Docker Ready**: Includes Dockerfile and docker-compose for easy deployment
- 📚 **Interactive Docs**: Auto-generated API documentation with Swagger UI
- ✅ **Validated**: Comprehensive input validation using Pydantic

## Quick Start

### Local Installation

1. **Clone the repository** (or navigate to the project directory)

2. **Install dependencies**:
```bash
pip install -r requirements.txt
```

3. **Run the server**:
```bash
uvicorn main:app --reload
```

4. **Access the API**:
   - API: http://localhost:8000
   - Interactive Docs: http://localhost:8000/docs
   - ReDoc: http://localhost:8000/redoc

### Docker Installation

1. **Build the Docker image**:
```bash
docker build -t pdf-redactor-api .
```

2. **Run the container**:
```bash
docker run -p 8000:8000 pdf-redactor-api
```

Or use **docker-compose**:
```bash
docker-compose up -d
```

## API Endpoints

### `GET /`
Welcome endpoint with API information.

**Response**:
```json
{
  "service": "PDF Redactor API",
  "version": "1.0.0",
  "endpoints": {
    "health": "/health",
    "redact": "/redact (POST)",
    "docs": "/docs"
  }
}
```

### `GET /health`
Health check endpoint.

**Response**:
```json
{
  "status": "healthy",
  "service": "PDF Redactor API",
  "version": "1.0.0"
}
```

### `POST /redact`
Redact a PDF file based on provided coordinates.

**Request**:
- **Content-Type**: `multipart/form-data`
- **Parameters**:
  - `file`: PDF file to redact (required)
  - `redactions`: JSON string with redaction coordinates (required)

**Redactions JSON Format**:
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

**Response**:
- Returns the redacted PDF file with filename `{original}_redacted.pdf`

## Usage Examples

### Using cURL

```bash
curl -X POST "http://localhost:8000/redact" \
  -F "file=@input.pdf" \
  -F 'redactions=[{"pageIndex":0,"x":100,"y":200,"width":150,"height":20}]' \
  --output redacted.pdf
```

### Using Python Requests

```python
import requests
import json

# Prepare the redaction coordinates
redactions = [
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

# Make the request
with open('input.pdf', 'rb') as pdf_file:
    files = {'file': pdf_file}
    data = {'redactions': json.dumps(redactions)}
    
    response = requests.post(
        'http://localhost:8000/redact',
        files=files,
        data=data
    )
    
    # Save the redacted PDF
    if response.status_code == 200:
        with open('redacted.pdf', 'wb') as output:
            output.write(response.content)
        print("PDF redacted successfully!")
    else:
        print(f"Error: {response.status_code}")
        print(response.json())
```

### Using JavaScript/Fetch

```javascript
const formData = new FormData();
formData.append('file', pdfFile); // File object from input
formData.append('redactions', JSON.stringify([
  {
    pageIndex: 0,
    x: 100.0,
    y: 200.0,
    width: 150.0,
    height: 20.0,
    text: "John Doe",
    category: "Person"
  }
]));

fetch('http://localhost:8000/redact', {
  method: 'POST',
  body: formData
})
.then(response => response.blob())
.then(blob => {
  // Download the redacted PDF
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'redacted.pdf';
  a.click();
});
```

## Redaction Coordinate Format

Each redaction object must include:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `pageIndex` | integer | Yes | Zero-based page index (0 = first page) |
| `x` | float | Yes | X coordinate (left edge) |
| `y` | float | Yes | Y coordinate (top edge) |
| `width` | float | Yes | Width of redaction area |
| `height` | float | Yes | Height of redaction area |
| `text` | string | No | The PII text being redacted (for logging) |
| `category` | string | No | PII category (e.g., "Person", "Email") |

**Coordinate System**: PyMuPDF uses a coordinate system where:
- Origin (0,0) is at the **top-left** corner of the page
- X increases to the right
- Y increases downward

## Configuration

### Environment Variables

Create a `.env` file based on `.env.example`:

```bash
cp .env.example .env
```

Available configuration options:

- `HOST`: Server host (default: 0.0.0.0)
- `PORT`: Server port (default: 8000)
- `LOG_LEVEL`: Logging level (default: info)
- `MAX_FILE_SIZE_MB`: Maximum upload size in MB (default: 50)
- `ALLOWED_ORIGINS`: CORS allowed origins (default: *)

### File Size Limits

The default maximum file size is 50MB. To change this, modify the `MAX_FILE_SIZE` constant in `main.py`:

```python
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
```

## Deployment

#### Coolify (Recommended)

**Quick Deploy:**
```bash
# Run deployment helper
./deploy.sh

# Commit and push to your Git repository
git commit -m "Initial commit - PDF Redactor API"
git remote add origin https://github.com/yourusername/pdf-redactor-api.git
git push -u origin main
```

**In Coolify:**
1. Click **"+ New Resource"**
2. Select **"Public/Private Repository"**
3. Enter repository URL
4. Build Pack: **"Dockerfile"**
5. Port: **8000**
6. Click **"Deploy"**

📚 **Detailed Guide:** See [COOLIFY_DEPLOYMENT.md](./COOLIFY_DEPLOYMENT.md) for complete instructions.

#### AWS (Elastic Beanstalk)
```bash
eb init -p docker pdf-redactor-api
eb create pdf-redactor-env
eb deploy
```

#### Google Cloud Run
```bash
gcloud builds submit --tag gcr.io/PROJECT_ID/pdf-redactor-api
gcloud run deploy pdf-redactor-api --image gcr.io/PROJECT_ID/pdf-redactor-api --platform managed
```

#### Azure Container Instances
```bash
az container create --resource-group myResourceGroup \
  --name pdf-redactor-api \
  --image pdf-redactor-api \
  --dns-name-label pdf-redactor \
  --ports 8000
```

#### Heroku
```bash
heroku create pdf-redactor-api
heroku container:push web
heroku container:release web
```

### Production Considerations

1. **CORS**: Update the `allow_origins` in `main.py` to restrict origins in production
2. **File Cleanup**: Implement background tasks to clean up temporary files
3. **Rate Limiting**: Add rate limiting middleware for production use
4. **Authentication**: Add API key or OAuth authentication if needed
5. **Monitoring**: Integrate with monitoring services (e.g., Sentry, DataDog)
6. **Scaling**: Use a reverse proxy (nginx) and multiple workers for high traffic

## Development

### Project Structure

```
DGA-FastAPP/
├── main.py              # FastAPI application
├── redactor.py          # Core redaction logic
├── requirements.txt     # Python dependencies
├── Dockerfile          # Docker configuration
├── docker-compose.yml  # Docker Compose configuration
├── .dockerignore       # Docker ignore patterns
├── .env.example        # Example environment variables
└── README.md           # This file
```

### Running Tests

```bash
# Install test dependencies
pip install pytest httpx

# Run tests
pytest
```

## Troubleshooting

### Common Issues

**Issue**: `ModuleNotFoundError: No module named 'fitz'`
- **Solution**: Install PyMuPDF: `pip install PyMuPDF`

**Issue**: Docker build fails on PyMuPDF installation
- **Solution**: Ensure system dependencies are installed (see Dockerfile)

**Issue**: Redacted PDF is empty or corrupted
- **Solution**: Verify redaction coordinates are within page bounds

**Issue**: File upload fails
- **Solution**: Check file size is under the limit (default 50MB)

## License

This project is provided as-is for PDF redaction purposes.

## Support

For issues or questions:
1. Check the interactive API docs at `/docs`
2. Review the logs for error messages
3. Verify input format matches the examples

## Contributing

Contributions are welcome! Please ensure:
- Code follows PEP 8 style guidelines
- All endpoints include proper error handling
- Documentation is updated for new features
