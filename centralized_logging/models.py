"""
Pydantic models for log validation and API request/response schemas
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, Any, Literal
from datetime import datetime, timedelta
import re


class LogError(BaseModel):
    """Error details in a log entry"""
    type: Optional[str] = Field(None, description="Error type/class name")
    message: Optional[str] = Field(None, description="Error message")
    stack: Optional[str] = Field(None, description="Stack trace")


class LogEntry(BaseModel):
    """Model for a single log entry"""
    timestamp: str = Field(..., description="ISO 8601 timestamp with timezone")
    level: Literal["DEBUG", "INFO", "WARN", "WARNING", "ERROR", "CRITICAL"] = Field(
        ..., description="Log level"
    )
    service: str = Field(..., description="Service name: pdf-processing, nodejs-app, n8n")
    message: str = Field(..., description="Log message")
    context: Optional[Dict[str, Any]] = Field(
        default_factory=dict, 
        description="Additional context data"
    )
    error: Optional[LogError] = Field(None, description="Error details if level is ERROR/CRITICAL")

    @field_validator('timestamp')
    @classmethod
    def validate_timestamp(cls, v: str) -> str:
        """Validate timestamp is in ISO 8601 format"""
        try:
            datetime.fromisoformat(v.replace('Z', '+00:00'))
            return v
        except ValueError:
            raise ValueError(f"Invalid timestamp format. Expected ISO 8601, got: {v}")

    @field_validator('level')
    @classmethod
    def normalize_level(cls, v: str) -> str:
        """Normalize log level (WARNING -> WARN)"""
        return "WARN" if v == "WARNING" else v


class LogQueryParams(BaseModel):
    """Query parameters for GET /api/logs endpoint"""
    service: Optional[str] = Field(None, description="Filter by service name")
    level: Optional[Literal["DEBUG", "INFO", "WARN", "ERROR", "CRITICAL"]] = Field(
        None, description="Filter by log level"
    )
    start_date: Optional[str] = Field(
        None, 
        description="Start datetime (ISO 8601) or relative time (e.g., '5m', '1h', '3d')"
    )
    end_date: Optional[str] = Field(
        None, 
        description="End datetime (ISO 8601), defaults to now"
    )
    limit: int = Field(
        100, 
        ge=1, 
        le=10000, 
        description="Maximum number of log entries to return"
    )

    def parse_start_datetime(self) -> Optional[datetime]:
        """
        Parse start_date, supporting both ISO 8601 and relative time formats.
        
        Relative formats:
        - '5m' = 5 minutes ago
        - '1h' = 1 hour ago
        - '3d' = 3 days ago
        - '2w' = 2 weeks ago
        """
        if not self.start_date:
            return None
        
        # Try relative time format first (e.g., "5m", "1h", "3d")
        relative_pattern = re.match(r'^(\d+)([mhdw])$', self.start_date.lower())
        if relative_pattern:
            value = int(relative_pattern.group(1))
            unit = relative_pattern.group(2)
            
            now = datetime.now()
            if unit == 'm':  # minutes
                return now - timedelta(minutes=value)
            elif unit == 'h':  # hours
                return now - timedelta(hours=value)
            elif unit == 'd':  # days
                return now - timedelta(days=value)
            elif unit == 'w':  # weeks
                return now - timedelta(weeks=value)
        
        # Try ISO 8601 format
        try:
            return datetime.fromisoformat(self.start_date.replace('Z', '+00:00'))
        except ValueError:
            raise ValueError(
                f"Invalid start_date format. Use ISO 8601 or relative format "
                f"(e.g., '5m', '1h', '3d', '2w'). Got: {self.start_date}"
            )
    
    def parse_end_datetime(self) -> Optional[datetime]:
        """
        Parse end_date to datetime object.
        Returns None if not provided (no upper time limit).
        """
        if not self.end_date:
            return None
        
        try:
            return datetime.fromisoformat(self.end_date.replace('Z', '+00:00'))
        except ValueError:
            raise ValueError(f"Invalid end_date format. Expected ISO 8601, got: {self.end_date}")


class LogIngestResponse(BaseModel):
    """Response for POST /api/logs"""
    status: str = "success"
    message: str = "Log entry recorded"
    timestamp: str


class LogQueryResponse(BaseModel):
    """Response for GET /api/logs"""
    logs: list[LogEntry]
    count: int
    query: Dict[str, Any]
