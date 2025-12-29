"""
Log cleanup scheduler - automatically deletes old log files
"""

from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
from pathlib import Path
import logging
import sys

# Configure logger to output to console
logging.basicConfig(
    level=logging.INFO,
    format='INFO:     %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

# Configuration
LOG_DIR = Path("logs")
RETENTION_DAYS = 3  # Keep only last 3 days of logs


def cleanup_old_logs():
    """
    Delete log files older than RETENTION_DAYS.
    Runs daily at midnight.
    """
    try:
        if not LOG_DIR.exists():
            logger.warning(f"Log directory {LOG_DIR} does not exist")
            return
        
        # Calculate cutoff date
        cutoff_date = datetime.now() - timedelta(days=RETENTION_DAYS)
        cutoff_date_str = cutoff_date.strftime('%Y-%m-%d')
        
        deleted_count = 0
        kept_count = 0
        
        # Find all log files
        log_files = sorted(LOG_DIR.glob("app-*.log"))
        
        for log_file in log_files:
            try:
                # Extract date from filename (format: app-YYYY-MM-DD.log)
                filename = log_file.name
                date_str = filename.replace('app-', '').replace('.log', '')
                
                # Parse date
                file_date = datetime.strptime(date_str, '%Y-%m-%d')
                
                # Delete if older than retention period
                if file_date < cutoff_date:
                    log_file.unlink()
                    deleted_count += 1
                    logger.info(f"Deleted old log file: {filename} (date: {date_str})")
                else:
                    kept_count += 1
                    
            except (ValueError, OSError) as e:
                logger.error(f"Error processing log file {log_file}: {e}")
                continue
        
        logger.info(
            f"Log cleanup completed: deleted {deleted_count} files, "
            f"kept {kept_count} files (retention: {RETENTION_DAYS} days)"
        )
        
    except Exception as e:
        logger.error(f"Log cleanup failed: {e}", exc_info=True)


def start_log_cleanup_scheduler():
    """
    Start the background scheduler for log cleanup.
    Runs cleanup daily at 2:00 AM.
    """
    scheduler = BackgroundScheduler()
    
    # Schedule cleanup to run daily at 2:00 AM
    scheduler.add_job(
        cleanup_old_logs,
        trigger='cron',
        hour=2,
        minute=0,
        id='log_cleanup',
        name='Daily log cleanup',
        replace_existing=True
    )
    
    scheduler.start()
    
    # Log to both file and console
    logger.info(f"Log cleanup scheduler started (retention: {RETENTION_DAYS} days, runs daily at 2:00 AM)")
    
    return scheduler


def stop_log_cleanup_scheduler(scheduler):
    """Stop the log cleanup scheduler"""
    if scheduler:
        scheduler.shutdown()
        logger.info("Log cleanup scheduler stopped")
