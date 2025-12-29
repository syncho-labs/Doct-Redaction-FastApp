# PDF Redactor API

A FastAPI-based REST API service for redacting PII (Personally Identifiable Information) from PDF documents using PyMuPDF, with centralized logging and automated log management.

## Features

- 🚀 **Fast & Efficient**: Built with FastAPI for high performance
- 📄 **PDF Redaction**: Permanently removes PII from PDFs based on coordinates
- 📊 **Centralized Logging**: JSON-structured logging with daily rotation
- 🔍 **Log Query API**: Query and filter logs with flexible parameters
- 🧹 **Automatic Log Cleanup**: Scheduled cleanup of old logs (3-day retention)
- 🔒 **Secure**: Validates inputs and handles files safely with Bearer token authentication
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

3. **Configure environment** (optional):
```bash
cp .env.example .env.local
# Edit .env.local with your settings
```

4. **Run the server**:
```bash
python3 main.py
# Or using uvicorn directly:
uvicorn main:app --reload
```

5. **Access the API**:
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

### Core Endpoints

#### `GET /`
Welcome endpoint with API information.

**Response**:
```json
{
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
```

#### `GET /health`
Health check endpoint.

**Response**:
```json
{
  "status": "healthy",
  "service": "PDF Redactor API",
  "version": "1.0.0"
}
```

#### `POST /redact`
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
- Header `X-Redactions-Applied` contains the count of redactions applied

**Example**:
```bash
curl -X POST "http://localhost:8000/redact" \
  -F "file=@input.pdf" \
  -F 'redactions=[{"pageIndex":0,"x":100,"y":200,"width":150,"height":20}]' \
  --output redacted.pdf
```

### Logging API Endpoints

All logging endpoints require Bearer token authentication (unless `API_BEARER_TOKEN` is not configured).

#### `POST /api/logs`
Ingest a log entry from external services (Node.js app, n8n, etc.).

**Request Headers**:
- `Content-Type`: `application/json`
- `Authorization`: `Bearer <your-token>` (if configured)

**Request Body**:
```json
{
  "timestamp": "2025-12-18T20:42:21+05:00",
  "level": "ERROR",
  "service": "nodejs-app",
  "message": "Test error message",
  "context": {
    "request_id": "123",
    "user_id": "456"
  },
  "error": {
    "type": "ValidationError",
    "message": "Invalid input",
    "stack": "Error stack trace..."
  }
}
```

**Response**:
```json
{
  "status": "success",
  "message": "Log entry recorded",
  "timestamp": "2025-12-18T20:42:21.123456"
}
```

**Example**:
```bash
curl -X POST "http://localhost:8000/api/logs" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-token-here" \
  -d '{
    "timestamp": "2025-12-18T20:42:21+05:00",
    "level": "ERROR",
    "service": "nodejs-app",
    "message": "Test error"
  }'
```

#### `GET /api/logs`
Query logs with filtering options.

**Query Parameters**:
- `service` (optional): Filter by service name (e.g., "nodejs-app", "pdf-processing")
- `level` (optional): Filter by log level (e.g., "ERROR", "INFO", "WARNING")
- `start_date` (optional): Start time - ISO 8601 or relative (e.g., "5m", "1h", "3d")
- `end_date` (optional): End time - ISO 8601 format
- `limit` (optional): Max results (default: 100, max: 10000)

**Request Headers**:
- `Authorization`: `Bearer <your-token>` (if configured)

**Response**:
```json
{
  "logs": [
    {
      "timestamp": "2025-12-18T20:42:21+05:00",
      "level": "ERROR",
      "service": "nodejs-app",
      "message": "Test error",
      "context": {"request_id": "123"}
    }
  ],
  "count": 1,
  "query": {
    "service": "nodejs-app",
    "level": "ERROR",
    "start_date": "5m",
    "end_date": null,
    "limit": 100
  }
}
```

**Examples**:
```bash
# Get last 100 logs (default)
curl -X GET "http://localhost:8000/api/logs" \
  -H "Authorization: Bearer your-token-here"

# Get last 5 minutes of errors from nodejs-app
curl -X GET "http://localhost:8000/api/logs?service=nodejs-app&level=ERROR&start_date=5m" \
  -H "Authorization: Bearer your-token-here"

# Get all logs from last 3 days (up to 1000)
curl -X GET "http://localhost:8000/api/logs?start_date=3d&limit=1000" \
  -H "Authorization: Bearer your-token-here"

# Get INFO logs from pdf-processing service in the last hour
curl -X GET "http://localhost:8000/api/logs?service=pdf-processing&level=INFO&start_date=1h" \
  -H "Authorization: Bearer your-token-here"
```

**Relative Time Formats**:
- `5m` - 5 minutes ago
- `1h` - 1 hour ago
- `3d` - 3 days ago
- `2w` - 2 weeks ago

## Logging System

### Features

- **JSON Structured Logging**: All logs are stored in JSON format for easy parsing
- **Daily Log Rotation**: Logs rotate daily with filename format `app-YYYY-MM-DD.log`
- **Automatic Cleanup**: Scheduler runs daily at 2:00 AM to delete logs older than 3 days
- **Centralized Storage**: All logs stored in `logs/` directory
- **Multi-Service Support**: Logs from multiple services (PDF processing, Node.js app, etc.)

### Log File Structure

```
logs/
├── app-2025-12-16.log
├── app-2025-12-17.log
└── app-2025-12-18.log
```

### Log Entry Format

Each log entry is a JSON object:
```json
{
  "timestamp": "2025-12-18T20:42:21.123456",
  "level": "INFO",
  "service": "pdf-processing",
  "message": "Processing redaction request",
  "context": {
    "filename": "document.pdf",
    "redaction_count": 5
  }
}
```

### Log Cleanup Scheduler

The application includes an automatic log cleanup scheduler:

- **Schedule**: Runs daily at 2:00 AM
- **Retention**: Keeps logs for the last 3 days
- **Automatic**: Starts with the application, stops on shutdown
- **Configurable**: Modify `RETENTION_DAYS` in `centralized_logging/cleanup.py`

**Testing the Scheduler**:
```bash
# Test cleanup function directly
python3 -c "from centralized_logging.cleanup import cleanup_old_logs; cleanup_old_logs()"

# Create old test logs and verify cleanup
touch -t $(date -v-5d +%Y%m%d0000) logs/app-$(date -v-5d +%Y-%m-%d).log
python3 -c "from centralized_logging.cleanup import cleanup_old_logs; cleanup_old_logs()"
```

## Configuration

### Environment Variables

Create a `.env.local` file for local development:

```bash
# CORS Configuration
CORS_ORIGINS=http://localhost:3000,https://yourdomain.com

# API Authentication (optional)
API_BEARER_TOKEN=your-secret-token-here

# Server Configuration (optional)
HOST=0.0.0.0
PORT=8000
LOG_LEVEL=info
```

**Available Options**:
- `CORS_ORIGINS`: Comma-separated list of allowed origins for CORS
- `API_BEARER_TOKEN`: Bearer token for log API authentication (if not set, auth is disabled)
- `HOST`: Server host (default: 0.0.0.0)
- `PORT`: Server port (default: 8000)
- `LOG_LEVEL`: Logging level (default: info)

### Log Retention Configuration

Edit `centralized_logging/cleanup.py`:
```python
RETENTION_DAYS = 3  # Keep only last 3 days of logs
```

## Usage Examples

### PDF Redaction with Python

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

### Log Ingestion from Node.js

```javascript
const axios = require('axios');

async function sendLog(logEntry) {
  try {
    const response = await axios.post('http://localhost:8000/api/logs', {
      timestamp: new Date().toISOString(),
      level: 'INFO',
      service: 'nodejs-app',
      message: 'User action completed',
      context: {
        user_id: '123',
        action: 'upload'
      }
    }, {
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer your-token-here'
      }
    });
    
    console.log('Log sent:', response.data);
  } catch (error) {
    console.error('Failed to send log:', error.message);
  }
}
```

### Query Logs with Python

```python
import requests

# Query recent errors
response = requests.get(
    'http://localhost:8000/api/logs',
    params={
        'level': 'ERROR',
        'start_date': '1h',
        'limit': 50
    },
    headers={
        'Authorization': 'Bearer your-token-here'
    }
)

logs = response.json()
print(f"Found {logs['count']} error logs")
for log in logs['logs']:
    print(f"{log['timestamp']} - {log['service']}: {log['message']}")
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

## Development

### Project Structure

```
pdf_processing/
├── main.py                      # FastAPI application
├── redactor.py                  # Core redaction logic
├── requirements.txt             # Python dependencies
├── Dockerfile                   # Docker configuration
├── docker-compose.yml           # Docker Compose configuration
├── .env.local                   # Local environment variables
├── centralized_logging/         # Logging package
│   ├── __init__.py             # Package exports
│   ├── config.py               # Logging configuration
│   ├── models.py               # Pydantic models for logs
│   ├── endpoints.py            # Log API endpoints
│   ├── cleanup.py              # Log cleanup scheduler
│   └── README.md               # Logging documentation
├── logs/                        # Log files directory
│   ├── app-2025-12-16.log
│   ├── app-2025-12-17.log
│   └── app-2025-12-18.log
└── README.md                    # This file
```

### Running Tests

```bash
# Install test dependencies
pip install pytest httpx

# Run tests
pytest

# Test specific functionality
python3 -c "from centralized_logging.cleanup import cleanup_old_logs; cleanup_old_logs()"
```

### Development Mode

The application runs with auto-reload enabled:
```bash
python3 main.py
# Or
uvicorn main:app --reload
```

Changes to Python files will automatically restart the server.

## Deployment

### Docker Hub

The image is available on Docker Hub:
```bash
docker pull gosignmedia/pdf-redactor-api
docker run -p 8000:8000 gosignmedia/pdf-redactor-api
```

### Coolify (Recommended)

1. Run deployment helper:
```bash
./deploy.sh
```

2. In Coolify:
   - Click **"+ New Resource"**
   - Select **"Public/Private Repository"**
   - Enter repository URL
   - Build Pack: **"Dockerfile"**
   - Port: **8000**
   - Add environment variables if needed
   - Click **"Deploy"**

### Production Considerations

1. **CORS**: Update `CORS_ORIGINS` environment variable to restrict origins
2. **Authentication**: Set `API_BEARER_TOKEN` for log API security
3. **File Cleanup**: Temporary files are automatically cleaned up via BackgroundTasks
4. **Log Retention**: Adjust `RETENTION_DAYS` based on your requirements
5. **Monitoring**: Logs are available via API for integration with monitoring tools
6. **Scaling**: Use reverse proxy (nginx) and multiple workers for high traffic

## Troubleshooting

### Common Issues

**Issue**: `NameError: name 'FileResponse' is not defined`
- **Solution**: This has been fixed. Ensure you have the latest version with `FileResponse` imported.

**Issue**: Scheduler not running
- **Solution**: Check logs for "Log cleanup scheduler started" message. Verify APScheduler is installed.

**Issue**: Logs not being created
- **Solution**: Ensure `logs/` directory exists and is writable. Check `setup_logging()` is called.

**Issue**: Authentication errors on log API
- **Solution**: Either set `API_BEARER_TOKEN` environment variable or leave it unset for development mode.

**Issue**: Old logs not being deleted
- **Solution**: Scheduler runs at 2:00 AM. Test manually with `cleanup_old_logs()` function.

**Issue**: `ModuleNotFoundError: No module named 'fitz'`
- **Solution**: Install PyMuPDF: `pip install PyMuPDF`

**Issue**: Docker build fails on PyMuPDF installation
- **Solution**: Ensure system dependencies are installed (see Dockerfile)

**Issue**: Redacted PDF is empty or corrupted
- **Solution**: Verify redaction coordinates are within page bounds

## API Documentation

Full interactive API documentation is available at:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## License

This project is provided as-is for PDF redaction purposes.

## Support

For issues or questions:
1. Check the interactive API docs at `/docs`
2. Review the logs in `logs/` directory or via `/api/logs` endpoint
3. Verify input format matches the examples
4. Check the scheduler status in application logs

## Contributing

Contributions are welcome! Please ensure:
- Code follows PEP 8 style guidelines
- All endpoints include proper error handling
- Documentation is updated for new features
- Tests are added for new functionality

## Version History

### v1.0.0 (Current)
- ✅ PDF redaction with PyMuPDF
- ✅ Centralized JSON logging
- ✅ Log query API with filtering
- ✅ Automatic log cleanup scheduler
- ✅ Bearer token authentication
- ✅ Docker support
- ✅ Interactive API documentation
