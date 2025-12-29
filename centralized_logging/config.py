"""
Centralized logging configuration with JSON formatting and daily rotation
"""

import logging
import json
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from datetime import datetime
from typing import Any, Dict


class JSONFormatter(logging.Formatter):
    """Custom formatter that outputs logs as JSON"""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON"""
        # Base log entry
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "service": getattr(record, 'service', 'pdf-processing'),
            "message": record.getMessage(),
        }
        
        # Add context if present
        if hasattr(record, 'context') and record.context:
            log_entry["context"] = record.context
        
        # Add error details if present
        if record.exc_info:
            log_entry["error"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "stack": self.formatException(record.exc_info) if record.exc_info else None
            }
        elif hasattr(record, 'error') and record.error:
            log_entry["error"] = record.error
        
        return json.dumps(log_entry, ensure_ascii=False)


def setup_logging(log_dir: str = "logs", service_name: str = "pdf-processing") -> logging.Logger:
    """
    Set up centralized logging with JSON formatting and daily rotation
    
    Args:
        log_dir: Directory to store log files
        service_name: Name of the service for log identification
        
    Returns:
        Configured logger instance
    """
    # Create logs directory if it doesn't exist
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)
    
    # Create logger
    logger = logging.getLogger(service_name)
    logger.setLevel(logging.DEBUG)
    
    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()
    
    # Create daily rotating file handler
    log_file = log_path / f"app-{datetime.now().strftime('%Y-%m-%d')}.log"
    file_handler = TimedRotatingFileHandler(
        filename=log_file,
        when='midnight',
        interval=1,
        backupCount=30,  # Keep 30 days of logs
        encoding='utf-8'
    )
    file_handler.suffix = "%Y-%m-%d"  # Suffix for rotated files
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(JSONFormatter())
    
    # Create console handler for development (non-JSON for readability)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(console_formatter)
    
    # Add handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger


def get_logger(name: str = "pdf-processing") -> logging.Logger:
    """Get or create a logger instance"""
    return logging.getLogger(name)


# Custom adapter for adding context to logs
class ContextLogger(logging.LoggerAdapter):
    """Logger adapter that adds context to all log records"""
    
    def process(self, msg: str, kwargs: Dict[str, Any]) -> tuple:
        """Add context to log record"""
        # Get context from kwargs or use empty dict
        context = kwargs.pop('context', {})
        
        # Merge with adapter's extra context
        if self.extra:
            context.update(self.extra)
        
        # Add context to record
        kwargs['extra'] = kwargs.get('extra', {})
        kwargs['extra']['context'] = context
        kwargs['extra']['service'] = self.extra.get('service', 'pdf-processing')
        
        return msg, kwargs
