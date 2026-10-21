import threading
import time
import logging

logger = logging.getLogger('vibarr')


def backup_scheduler_loop():
    """Periodic daemon loop checking every 60s if a scheduled GFS backup is due."""
    logger.info("BackupScheduler - Started automated GFS backup daemon thread.")
    while True:
        try:
            from django.db import connection
            from django.utils import timezone
            from vibarr.models.backup import BackupConfiguration
            from vibarr.services.backup_service import execute_backup

            config = BackupConfiguration.get_config()
            if config.is_enabled:
                now = timezone.now()
                target_hour, target_min = map(int, config.backup_time.split(':'))
                is_due_time = (now.hour > target_hour) or (now.hour == target_hour and now.minute >= target_min)
                not_run_today = (config.last_run_at is None) or (config.last_run_at.date() < now.date())

                if is_due_time and not_run_today:
                    # Acquire advisory lock to prevent multiple workers from running duplicate backups
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT pg_try_advisory_lock(987654322);")
                        locked = cursor.fetchone()[0]

                    if locked:
                        try:
                            config.refresh_from_db()
                            if (config.last_run_at is None) or (config.last_run_at.date() < now.date()):
                                logger.info("BackupScheduler - Executing scheduled database backup...")
                                execute_backup(manual=False)
                                logger.info("BackupScheduler - Scheduled database backup succeeded.")
                        finally:
                            with connection.cursor() as cursor:
                                cursor.execute("SELECT pg_advisory_unlock(987654322);")
        except Exception as e:
            logger.error(f"BackupScheduler - Error in scheduler loop: {e}", exc_info=True)

        time.sleep(60)


def start_backup_scheduler_task():
    thread = threading.Thread(target=backup_scheduler_loop, daemon=True, name="VibarrBackupSchedulerThread")
    thread.start()
    logger.info("BackupScheduler - Dispatched automated GFS backup daemon thread.")
