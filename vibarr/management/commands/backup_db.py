import os
import gzip
import shutil
from datetime import datetime
from django.core.management.base import BaseCommand
from django.conf import settings
import subprocess
import logging

logger = logging.getLogger('vibarr')

class Command(BaseCommand):
    help = 'Backs up the database to a compressed file'

    def handle(self, *args, **options):
        db_config = settings.DATABASES['default']
        backup_dir = os.path.join(settings.BASE_DIR, 'data', 'backups')
        os.makedirs(backup_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        engine = db_config['ENGINE']
        
        if 'postgresql' in engine:
            db_name = db_config['NAME']
            db_user = db_config['USER']
            db_password = db_config['PASSWORD']
            db_host = db_config['HOST']
            db_port = db_config['PORT']
            
            backup_file = os.path.join(backup_dir, f'db_backup_{timestamp}.sql')
            compressed_file = backup_file + '.gz'
            
            # Setup environment with password to avoid interactive prompt
            env = os.environ.copy()
            if db_password:
                env['PGPASSWORD'] = db_password
                
            cmd = ['pg_dump', '-h', db_host, '-p', str(db_port), '-U', db_user, '-d', db_name, '-f', backup_file]
            
            try:
                subprocess.run(cmd, env=env, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
                with open(backup_file, 'rb') as f_in:
                    with gzip.open(compressed_file, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                        
                os.remove(backup_file)
                os.chmod(compressed_file, 0o600)
                self.stdout.write(self.style.SUCCESS(f"Successfully backed up PostgreSQL database to {compressed_file}"))
                logger.info(f"Database - Info - Successfully backed up PostgreSQL database to {compressed_file}")
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Backup failed: {str(e)}"))
                logger.error(f"Database - Error - PostgreSQL backup failed: {str(e)}")
                if os.path.exists(backup_file):
                    os.remove(backup_file)
                
        elif 'sqlite3' in engine:
            db_path = db_config['NAME']
            if not os.path.exists(db_path):
                self.stdout.write(self.style.ERROR("Sqlite3 database file does not exist"))
                return
                
            compressed_file = os.path.join(backup_dir, f'db_backup_{timestamp}.sqlite3.gz')
            try:
                with open(db_path, 'rb') as f_in:
                    with gzip.open(compressed_file, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                os.chmod(compressed_file, 0o600)
                self.stdout.write(self.style.SUCCESS(f"Successfully backed up SQLite database to {compressed_file}"))
                logger.info(f"Database - Info - Successfully backed up SQLite database to {compressed_file}")
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Backup failed: {str(e)}"))
                logger.error(f"Database - Error - SQLite backup failed: {str(e)}")
