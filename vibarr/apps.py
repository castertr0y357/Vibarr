from django.apps import AppConfig
import os
import sys
import time
import logging

logger = logging.getLogger('vibarr')

class VibarrConfig(AppConfig):
    name = 'vibarr'

    def ready(self):
        # Don't run validation during migrations, collectstatic, showmigrations or tests
        if any(cmd in sys.argv for cmd in ['test', 'migrate', 'collectstatic', 'showmigrations', 'makemigrations']):
            return
            
        # Verify required variables
        db_type = os.environ.get('DATABASE', 'sqlite')
        db_url = os.environ.get('DATABASE_URL', '')
        secret_key = os.environ.get('SECRET_KEY', '')
        
        if db_type == 'postgres':
            if not db_url:
                logger.critical("[Startup] - Configuration - DATABASE_URL must be specified when DATABASE=postgres")
                sys.exit(1)
            if not (db_url.startswith('postgres://') or db_url.startswith('postgresql://')):
                logger.critical("[Startup] - Configuration - DATABASE_URL is malformed. Must start with postgres:// or postgresql://")
                sys.exit(1)
                
        if not secret_key:
            logger.critical("[Startup] - Configuration - SECRET_KEY is not set.")
            sys.exit(1)

        # Pre-flight Database connectivity check with exponential backoff
        from django.db import connections
        from django.db.utils import OperationalError
        
        db_conn = connections['default']
        retries = 5
        backoff = 2
        for i in range(retries):
            try:
                db_conn.ensure_connection()
                logger.info("[Startup] - Database - Connection successful.")
                break
            except OperationalError as e:
                if i == retries - 1:
                    logger.critical(f"[Startup] - Database - Connection failed after {retries} attempts. Terminating.")
                    sys.exit(1)
                wait = backoff ** i
                logger.warning(f"[Startup] - Database - Connection failed, retrying in {wait}s: {e}")
                time.sleep(wait)

        # Pre-flight Redis connectivity check
        try:
            import redis
            from django.conf import settings
            redis_url = settings.Q_CLUSTER.get('redis', 'redis://redis:6379/0')
            r = redis.Redis.from_url(redis_url)
            
            for i in range(retries):
                try:
                    r.ping()
                    logger.info("[Startup] - Redis - Connection successful.")
                    break
                except Exception as e:
                    if i == retries - 1:
                        logger.critical(f"[Startup] - Redis - Connection failed after {retries} attempts. Terminating.")
                        sys.exit(1)
                    wait = backoff ** i
                    logger.warning(f"[Startup] - Redis - Connection failed, retrying in {wait}s: {e}")
                    time.sleep(wait)
        except ImportError:
            logger.warning("[Startup] - Redis - redis-py not installed, skipping Redis pre-flight check.")
