from django.core.management import call_command
import logging

logger = logging.getLogger('vibarr')

def run_database_backup():
    """Runs the database backup management command as a background task."""
    logger.info("Database Backup - Info - Starting background database backup.")
    try:
        call_command('backup_db')
    except Exception as e:
        logger.error(f"Database Backup - Error - Background database backup failed: {e}")
