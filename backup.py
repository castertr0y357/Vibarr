#!/usr/bin/env python
"""Database Backup and Restore utility for Vibarr using Docker Compose."""

import os
import sys
import subprocess
import gzip
import re
from datetime import datetime

# Default container runner (nerdctl or docker fallback)
CONTAINER_CMD = os.environ.get('CONTAINER_CMD', 'nerdctl' if subprocess.run(['where', 'nerdctl'], capture_output=True).returncode == 0 else 'docker')
DB_NAME = os.environ.get('POSTGRES_DB', 'vibarr')
DB_USER = os.environ.get('POSTGRES_USER', 'vibarr')
BACKUP_DIR = 'backups'


def load_env_file():
    """Manually parse .env file to load env vars for local run."""
    if os.path.exists('.env'):
        with open('.env') as f:
            for line in f:
                stripped = line.strip()
                if stripped and not stripped.startswith('#') and '=' in stripped:
                    try:
                        k, v = stripped.split('=', 1)
                        v = v.strip('"').strip("'")
                        os.environ.setdefault(k.strip(), v.strip())
                    except ValueError:
                        pass


def backup():
    """Execute pg_dump against the database container and save a compressed backup."""
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)
        print(f"Created backup directory: {BACKUP_DIR}")

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = os.path.join(BACKUP_DIR, f"backup_{timestamp}.sql.gz")

    print(f"[STARTUP] Starting database backup protocol for '{DB_NAME}'...")

    command = [CONTAINER_CMD, 'compose', 'exec', '-T', 'db', 'pg_dump', '--no-owner', '--no-acl', '-U', DB_USER, DB_NAME]

    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()

        if process.returncode != 0:
            print(f"[ERROR] Backup failed: {stderr.decode('utf-8').strip()}")
            return False

        with gzip.open(backup_file, 'wb') as f:
            f.write(stdout)

        print(f"[SUCCESS] Backup successfully created: {backup_file}")
        return True
    except Exception as e:
        print(f"[ERROR] Backup execution failed: {e}")
        return False


def restore(backup_path: str):
    """Restore the database from a compressed backup file."""
    if not os.path.exists(backup_path):
        print(f"[ERROR] Backup file not found: {backup_path}")
        return False

    print(f"[STARTUP] Initiating restore protocol from '{backup_path}'...")

    try:
        with open(backup_path, 'rb') as raw_f:
            magic = raw_f.read(2)
        if magic == b'\x1f\x8b':
            with gzip.open(backup_path, 'rb') as f:
                sql_content = f.read()
        else:
            with open(backup_path, 'rb') as f:
                sql_content = f.read()

        # Sanitize cross-version parameters (e.g. SET transaction_timeout in PG 17+ dumps on PG 16/15)
        pattern = rb'(?im)^([ \t]*(?:SET\s+transaction_timeout|SELECT\s+pg_catalog\.set_config\(\s*\'transaction_timeout).*)$'
        sql_content = re.sub(pattern, rb'-- \1', sql_content)
    except Exception as e:
        print(f"[ERROR] Failed to read/decompress backup: {e}")
        return False

    clean_command = [
        CONTAINER_CMD, 'compose', 'exec', '-T', 'db', 'psql', 
        '-U', DB_USER, '-d', DB_NAME, 
        '-c', 'DROP SCHEMA public CASCADE; CREATE SCHEMA public;'
    ]
    
    try:
        print("[CLEANUP] Cleaning database schemas...")
        clean_proc = subprocess.run(clean_command, capture_output=True, check=True)
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Database cleanup failed: {e.stderr.decode('utf-8').strip()}")
        return False

    restore_command = [CONTAINER_CMD, 'compose', 'exec', '-T', 'db', 'psql', '-U', DB_USER, '-d', DB_NAME]

    try:
        restore_proc = subprocess.Popen(restore_command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = restore_proc.communicate(input=sql_content)

        if restore_proc.returncode != 0:
            print(f"[ERROR] Restore failed: {stderr.decode('utf-8').strip()}")
            return False

        print("[SUCCESS] Database successfully restored and calibrated.")
        return True
    except Exception as e:
        print(f"[ERROR] Restore execution failed: {e}")
        return False


def main():
    load_env_file()
    
    global DB_NAME, DB_USER
    DB_NAME = os.environ.get('POSTGRES_DB', DB_NAME)
    DB_USER = os.environ.get('POSTGRES_USER', DB_USER)

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python backup.py --backup              (Create compressed database backup)")
        print("  python backup.py --restore [path]      (Restore database from a compressed backup file)")
        sys.exit(1)

    action = sys.argv[1]
    if action == '--backup':
        success = backup()
    elif action == '--restore':
        if len(sys.argv) < 3:
            print("[ERROR] Error: Please specify the path of the backup file to restore.")
            sys.exit(1)
        success = restore(sys.argv[2])
    else:
        print(f"Unknown action: {action}")
        sys.exit(1)

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
