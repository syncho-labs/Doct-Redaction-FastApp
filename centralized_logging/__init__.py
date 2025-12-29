"""
Centralized Logging Package

This package provides comprehensive logging functionality including:
- Structured JSON logging
- Log ingestion API endpoints
- Log query and retrieval
- Automatic log cleanup scheduler
"""

from .config import get_logger, setup_logging, ContextLogger
from .endpoints import router as log_router
from .cleanup import start_log_cleanup_scheduler, stop_log_cleanup_scheduler, cleanup_old_logs

__all__ = [
    'get_logger',
    'setup_logging',
    'ContextLogger',
    'log_router',
    'start_log_cleanup_scheduler',
    'stop_log_cleanup_scheduler',
    'cleanup_old_logs',
]
