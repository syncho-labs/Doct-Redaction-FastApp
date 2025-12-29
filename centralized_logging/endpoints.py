"""
Log API endpoints for centralized log collection
"""

from fastapi import APIRouter, HTTPException, Header, Query, Depends
from fastapi.responses import JSONResponse
from typing import Optional, Annotated
from datetime import datetime
from pathlib import Path
import json
import os

from .models import (
    LogEntry, 
    LogQueryParams, 
    LogIngestResponse, 
    LogQueryResponse
)
from .config import get_logger, JSONFormatter
import logging

# Create router
router = APIRouter(prefix="/api", tags=["logs"])

# Get logger
logger = get_logger("log-api")

# Log storage configuration
LOG_DIR = Path("logs")


def verify_bearer_token(authorization: Annotated[Optional[str], Header()] = None) -> None:
    """
    Verify Bearer token from Authorization header
    
    Args:
        authorization: Authorization header value
        
    Raises:
        HTTPException: If token is missing or invalid
    """
    expected_token = os.environ.get("API_BEARER_TOKEN")
    
    if not expected_token:
        # If no token configured, allow access (development mode)
        logger.warning("API_BEARER_TOKEN not configured - authentication disabled!")
        return
    
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Please provide Authorization header with Bearer token."
        )
    
    # Extract token from "Bearer <token>"
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=401,
            detail="Invalid Authorization header format. Expected: Bearer <token>"
        )
    
    token = parts[1]
    
    if token != expected_token:
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication token"
        )


@router.post("/logs", response_model=LogIngestResponse, status_code=201)
async def ingest_log(
    log_entry: LogEntry,
    _: None = Depends(verify_bearer_token)
) -> LogIngestResponse:
    """
    Ingest a log entry from external services (Node.js app, n8n)
    
    Requires Bearer token authentication via Authorization header.
    
    Example:
    ```bash
    curl -X POST http://localhost:8000/api/logs \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer your-token-here" \
      -d '{
        "timestamp": "2025-12-16T20:42:21+05:00",
        "level": "ERROR",
        "service": "nodejs-app",
        "message": "Test error",
        "context": {"request_id": "123"}
      }'
    ```
    """
    try:
        # Create logs directory if it doesn't exist
        LOG_DIR.mkdir(exist_ok=True)
        
        # Determine log file based on current date
        today = datetime.now().strftime('%Y-%m-%d')
        log_file = LOG_DIR / f"app-{today}.log"
        
        # Convert LogEntry to JSON
        log_json = log_entry.model_dump(exclude_none=True)
        
        # Write to log file (append mode)
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_json, ensure_ascii=False) + '\n')
        
        logger.info(
            f"Log ingested from {log_entry.service}",
            extra={
                'context': {
                    'service': log_entry.service,
                    'level': log_entry.level
                }
            }
        )
        
        return LogIngestResponse(
            status="success",
            message="Log entry recorded",
            timestamp=datetime.now().isoformat()
        )
        
    except Exception as e:
        logger.error(f"Failed to ingest log: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to record log entry: {str(e)}"
        )


@router.get("/logs", response_model=LogQueryResponse)
async def query_logs(
    service: Optional[str] = Query(None, description="Filter by service name"),
    level: Optional[str] = Query(None, description="Filter by log level"),
    start_date: Optional[str] = Query(
        None, 
        description="Start time - ISO 8601 or relative (e.g., '5m', '1h', '3d')"
    ),
    end_date: Optional[str] = Query(None, description="End time - ISO 8601"),
    limit: int = Query(100, ge=1, le=10000, description="Max results"),
    _: None = Depends(verify_bearer_token)
) -> LogQueryResponse:
    """
    Query logs with filtering options
    
    Requires Bearer token authentication via Authorization header.
    
    Time-based filtering supports:
    - ISO 8601 format: "2025-12-16T20:42:21+05:00"
    - Relative time: "5m" (5 minutes), "1h" (1 hour), "3d" (3 days), "2w" (2 weeks)
    
    Examples:
    ```bash
    # Get last 5 minutes of errors from nodejs-app
    curl -X GET "http://localhost:8000/api/logs?service=nodejs-app&level=ERROR&start_date=5m" \
      -H "Authorization: Bearer your-token-here"
    
    # Get all logs from last 3 days
    curl -X GET "http://localhost:8000/api/logs?start_date=3d&limit=1000" \
      -H "Authorization: Bearer your-token-here"
    ```
    """
    try:
        # Parse query parameters
        query_params = LogQueryParams(
            service=service,
            level=level,
            start_date=start_date,
            end_date=end_date,
            limit=limit
        )
        
        # Parse datetime filters
        start_dt = query_params.parse_start_datetime()
        end_dt = query_params.parse_end_datetime()
        
        # Collect matching log entries
        matching_logs = []
        
        # Determine which log files to search
        log_files = sorted(LOG_DIR.glob("app-*.log"), reverse=True)
        
        if not log_files:
            return LogQueryResponse(
                logs=[],
                count=0,
                query={
                    "service": service,
                    "level": level,
                    "start_date": start_date,
                    "end_date": end_date,
                    "limit": limit
                }
            )
        
        # Search through log files
        for log_file in log_files:
            # Read and parse log file
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        
                        try:
                            log_data = json.loads(line)
                            
                            # Parse timestamp and make it timezone-aware if needed
                            timestamp_str = log_data['timestamp']
                            try:
                                log_timestamp = datetime.fromisoformat(
                                    timestamp_str.replace('Z', '+00:00')
                                )
                            except ValueError:
                                # Handle timestamps without timezone (naive datetime)
                                log_timestamp = datetime.fromisoformat(timestamp_str)
                                # Assume local timezone if no timezone info
                                from datetime import timezone
                                log_timestamp = log_timestamp.replace(tzinfo=None)
                            
                            # Make comparison timestamps timezone-naive for consistency
                            log_ts_naive = log_timestamp.replace(tzinfo=None) if log_timestamp.tzinfo else log_timestamp
                            
                            # Handle None values properly before accessing tzinfo
                            if start_dt:
                                start_naive = start_dt.replace(tzinfo=None) if start_dt.tzinfo else start_dt
                            else:
                                start_naive = None
                                
                            if end_dt:
                                end_naive = end_dt.replace(tzinfo=None) if end_dt.tzinfo else end_dt
                            else:
                                end_naive = None
                            
                            # Apply time filters
                            if start_naive and log_ts_naive < start_naive:
                                continue
                            if end_naive and log_ts_naive > end_naive:
                                continue
                            
                            # Apply service filter
                            if service and log_data.get('service') != service:
                                continue
                            
                            # Apply level filter
                            if level and log_data.get('level') != level:
                                continue
                            
                            # Add to results
                            matching_logs.append(LogEntry(**log_data))
                                
                        except (json.JSONDecodeError, KeyError, ValueError) as e:
                            # Skip malformed log entries
                            logger.warning(f"Skipping malformed log entry: {e}")
                            continue
                            
            except Exception as e:
                logger.error(f"Error reading log file {log_file}: {e}")
                continue
        
        
        # Sort by timestamp (newest first) - handle timezone-aware and naive timestamps
        def get_sort_key(log_entry):
            try:
                ts = datetime.fromisoformat(log_entry.timestamp.replace('Z', '+00:00'))
                # Make timezone-naive for consistent sorting
                return ts.replace(tzinfo=None) if ts.tzinfo else ts
            except:
                # Fallback to string comparison if parsing fails
                return log_entry.timestamp
        
        matching_logs.sort(key=get_sort_key, reverse=True)
        
        # Apply limit
        limited_logs = matching_logs[:limit]
        
        return LogQueryResponse(
            logs=limited_logs,
            count=len(limited_logs),  # Count of logs actually returned
            query={
                "service": service,
                "level": level,
                "start_date": start_date,
                "end_date": end_date,
                "limit": limit,
                "parsed_start": start_dt.isoformat() if start_dt else None,
                "parsed_end": end_dt.isoformat() if end_dt else None
            }
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to query logs: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to query logs: {str(e)}"
        )
