"""Backup, restore, and snapshot management views for Vibarr."""

import gzip
import json
import logging
import os
import re
import subprocess
import sys
from typing import Dict, Any, Tuple

from django.conf import settings
from django.core.management import call_command
from django.db import connections
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from vibarr.models.backup import BackupConfiguration, BackupRecord, BackgroundExecutionTask
from vibarr.tasks_registry import submit_task

logger = logging.getLogger(__name__)


def _get_db_env_and_params() -> Tuple[Dict[str, str], str, str, str, str]:
    """Extract database connection parameters and build subprocess environment."""
    db_conf = settings.DATABASES.get('default', {})
    db_name = str(db_conf.get('NAME') or os.environ.get('POSTGRES_DB', 'vibarr'))
    db_user = str(db_conf.get('USER') or os.environ.get('POSTGRES_USER', 'vibarr'))
    db_password = str(db_conf.get('PASSWORD') or os.environ.get('POSTGRES_PASSWORD', 'vibarr'))
    db_host = str(db_conf.get('HOST') or os.environ.get('SQL_HOST', 'localhost'))
    db_port = str(db_conf.get('PORT') or os.environ.get('SQL_PORT', '5432'))

    env = os.environ.copy()
    env['PGPASSWORD'] = db_password
    return env, db_name, db_user, db_host, db_port


def _sanitize_sql_for_compat(sql_bytes: bytes) -> bytes:
    """Sanitize SQL dump to ensure cross-version PostgreSQL compatibility.

    PostgreSQL 17+ pg_dump emits 'SET transaction_timeout = 0;' which causes PostgreSQL <= 16
    to fail with 'ERROR: unrecognized configuration parameter "transaction_timeout"' when
    executed with ON_ERROR_STOP=1.
    """
    pattern = rb'(?im)^([ \t]*(?:SET\s+transaction_timeout|SELECT\s+pg_catalog\.set_config\(\s*\'transaction_timeout).*)$'
    return re.sub(pattern, rb'-- \1', sql_bytes)


def _extract_and_validate_sql_payload(raw_bytes: bytes) -> bytes:
    """Validate file magic bytes (gzip or plain SQL) and return uncompressed SQL bytes."""
    if not raw_bytes:
        raise ValueError("Uploaded backup file is empty.")

    # Check gzip magic signature (1f 8b)
    if raw_bytes.startswith(b'\x1f\x8b'):
        try:
            sql_bytes = gzip.decompress(raw_bytes)
        except Exception as exc:
            raise ValueError("Corrupted gzip backup archive.") from exc
    else:
        sql_bytes = raw_bytes

    sample = sql_bytes[:2048].lstrip()
    if sample.startswith(b'\xef\xbb\xbf'):
        sample = sample[3:].lstrip()

    try:
        sample_str = sample.decode('utf-8')
    except UnicodeDecodeError as exc:
        raise ValueError("Invalid file signature. File is not a valid SQL or .sql.gz database backup.") from exc

    valid_prefixes = (
        '--',
        '/*',
        'SET ',
        'SELECT ',
        'CREATE ',
        'DROP ',
        'ALTER ',
        'INSERT ',
        'COPY ',
        'BEGIN',
        '\\connect',
        '\\restrict',
    )
    if not sample_str or not any(sample_str.upper().startswith(p.upper()) for p in valid_prefixes):
        raise ValueError("Invalid file signature. File is not a valid SQL or .sql.gz database backup.")

    return _sanitize_sql_for_compat(sql_bytes)


def _restore_sql_into_database(sql_content: bytes, preserve_config: bool = True) -> None:
    """Executes schema clean, psql restore, migrations, and optional backup config preservation."""
    sql_content = _sanitize_sql_for_compat(sql_content)
    env, db_name, db_user, db_host, db_port = _get_db_env_and_params()

    saved_backup_config_data = None
    if preserve_config:
        try:
            saved_backup_config_data = BackupConfiguration.objects.filter(pk=1).values().first()
        except Exception as exc:
            logger.warning(f"Failed to capture existing backup configuration before restore: {exc}")

    # Wipe existing schema public
    clean_cmd = [
        'psql',
        '-h', db_host,
        '-p', db_port,
        '-U', db_user,
        '-d', db_name,
        '-v', 'ON_ERROR_STOP=1',
        '-c', 'DROP SCHEMA public CASCADE; CREATE SCHEMA public;',
    ]
    clean_proc = subprocess.run(clean_cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if clean_proc.returncode != 0:
        err = clean_proc.stderr.decode('utf-8', errors='replace').strip()
        raise RuntimeError(f"Database schema wipe failed: {err}")

    # Restore SQL
    restore_cmd = [
        'psql',
        '-h', db_host,
        '-p', db_port,
        '-U', db_user,
        '-d', db_name,
        '-v', 'ON_ERROR_STOP=1',
    ]
    restore_proc = subprocess.Popen(restore_cmd, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = restore_proc.communicate(input=sql_content)
    if restore_proc.returncode != 0:
        err = stderr.decode('utf-8', errors='replace').strip()
        raise RuntimeError(f"Database restore failed: {err}")

    # Close existing database connections
    for conn in connections.all():
        conn.close()

    # Run migrations
    try:
        call_command('migrate', interactive=False)
    except Exception as exc:
        logger.warning(f"Post-restore migrations warning: {exc}")

    # Restore preserved backup configuration
    if preserve_config and saved_backup_config_data:
        try:
            saved_backup_config_data.pop('id', None)
            BackupConfiguration.objects.update_or_create(pk=1, defaults=saved_backup_config_data)
        except Exception as exc:
            logger.warning(f"Failed to restore preserved backup configuration: {exc}")


@csrf_exempt
@require_http_methods(["POST"])
def save_backup_config_api(request: HttpRequest) -> JsonResponse:
    """Save automated GFS backup schedule and storage target configuration."""
    try:
        data = json.loads(request.body)
        config = BackupConfiguration.get_config()

        config.is_enabled = bool(data.get('is_enabled', False))
        config.backup_time = data.get('backup_time', '02:00').strip()
        config.weekly_day = int(data.get('weekly_day', 6))
        config.monthly_day = int(data.get('monthly_day', 1))
        config.keep_daily = max(0, int(data.get('keep_daily', 7)))
        config.keep_weekly = max(0, int(data.get('keep_weekly', 4)))
        config.keep_monthly = max(0, int(data.get('keep_monthly', 3)))
        config.preserve_config_on_restore = bool(data.get('preserve_config_on_restore', True))

        config.storage_type = data.get('storage_type', 'LOCAL')
        config.local_path = data.get('local_path', '/backups').strip()

        config.s3_endpoint_url = data.get('s3_endpoint_url', '').strip() or None
        config.s3_bucket = data.get('s3_bucket', '').strip()
        config.s3_region = data.get('s3_region', 'us-east-1').strip()
        config.s3_access_key = data.get('s3_access_key', '').strip()
        config.s3_secret_key = data.get('s3_secret_key', '').strip()
        config.s3_prefix = data.get('s3_prefix', 'vibarr/').strip()

        config.cifs_server = data.get('cifs_server', '').strip()
        config.cifs_share = data.get('cifs_share', '').strip()
        config.cifs_subpath = data.get('cifs_subpath', '').strip()
        config.cifs_username = data.get('cifs_username', '').strip()
        config.cifs_password = data.get('cifs_password', '').strip()
        config.cifs_domain = data.get('cifs_domain', '').strip()

        config.nfs_server = data.get('nfs_server', '').strip()
        config.nfs_export = data.get('nfs_export', '').strip()
        config.nfs_subpath = data.get('nfs_subpath', '').strip()

        config.encryption_passphrase = data.get('encryption_passphrase', '').strip()
        config.webhook_url = data.get('webhook_url', '').strip()

        config.save()
        return JsonResponse({'status': 'success', 'message': 'Backup configuration saved successfully.'})
    except Exception as e:
        logger.error(f"BackupConfig - Error - Failed to save backup configuration: {e}")
        return JsonResponse({'error': str(e)}, status=400)


@csrf_exempt
@require_http_methods(["POST"])
def test_backup_storage_api(request: HttpRequest) -> JsonResponse:
    """Test read/write connection to the active or requested storage target."""
    try:
        from vibarr.services.backup_service import get_storage_driver
        data = json.loads(request.body) if request.body else {}
        config = BackupConfiguration.get_config()

        if data.get('storage_type'):
            config.storage_type = data.get('storage_type')
        if data.get('local_path'):
            config.local_path = data.get('local_path')
        if 's3_bucket' in data:
            config.s3_bucket = data.get('s3_bucket')
            config.s3_endpoint_url = data.get('s3_endpoint_url') or None
            config.s3_region = data.get('s3_region') or 'us-east-1'
            config.s3_access_key = data.get('s3_access_key')
            config.s3_secret_key = data.get('s3_secret_key')
            config.s3_prefix = data.get('s3_prefix')
        if 'cifs_server' in data:
            config.cifs_server = data.get('cifs_server')
            config.cifs_share = data.get('cifs_share')
            config.cifs_subpath = data.get('cifs_subpath')
            config.cifs_username = data.get('cifs_username')
            config.cifs_password = data.get('cifs_password')
            config.cifs_domain = data.get('cifs_domain')
        if 'nfs_server' in data:
            config.nfs_server = data.get('nfs_server')
            config.nfs_export = data.get('nfs_export')
            config.nfs_subpath = data.get('nfs_subpath')

        driver = get_storage_driver(config)
        success, message = driver.test_connection()
        return JsonResponse({'status': 'success' if success else 'failed', 'message': message})
    except Exception as e:
        logger.error(f"BackupStorage - Error - Test connection failed: {e}")
        return JsonResponse({'status': 'failed', 'message': str(e)})


def _run_backup_now_task(update_progress):
    from vibarr.services.backup_service import execute_backup
    execute_backup(progress_callback=update_progress, manual=True)


@csrf_exempt
@require_http_methods(["POST"])
def run_backup_now_api(request: HttpRequest) -> JsonResponse:
    """Dispatches an asynchronous backup task, returning task_id for progress polling."""
    try:
        task = submit_task("Database Backup Snapshot", _run_backup_now_task)
        return JsonResponse({
            'status': 'accepted',
            'task_id': str(task.uuid),
            'message': 'Backup protocol initiated.'
        }, status=202)
    except Exception as e:
        logger.error(f"BackupNow - Error - Failed to dispatch backup task: {e}")
        return JsonResponse({'error': str(e)}, status=500)


def task_status_api(request: HttpRequest, uuid: str) -> JsonResponse:
    """Fetch status and telemetry of a background task."""
    task = get_object_or_404(BackgroundExecutionTask, uuid=uuid)
    return JsonResponse({
        'uuid': str(task.uuid),
        'task_name': task.task_name,
        'status': task.status,
        'progress': task.progress,
        'error_message': task.error_message,
        'result_data': task.result_data,
        'created_at': task.created_at.isoformat()
    })


def download_backup_file(request: HttpRequest, uuid: Any) -> HttpResponse:
    """Stream a backup file directly from its storage driver."""
    try:
        record = BackupRecord.objects.get(uuid=uuid)
        config = BackupConfiguration.get_config()
        original_type = config.storage_type
        config.storage_type = record.storage_type
        from vibarr.services.backup_service import get_storage_driver
        driver = get_storage_driver(config)
        config.storage_type = original_type

        file_bytes = driver.retrieve_file(record.filename)
        content_type = 'application/octet-stream' if record.is_encrypted else 'application/gzip'
        response = HttpResponse(file_bytes, content_type=content_type)
        response['Content-Disposition'] = f'attachment; filename="{record.filename}"'
        return response
    except BackupRecord.DoesNotExist:
        return HttpResponse("Backup not found", status=404)
    except Exception as e:
        logger.error(f"BackupDownload - Error - Failed to download backup {uuid}: {e}")
        return HttpResponse(f"Download failed: {str(e)}", status=500)


@csrf_exempt
@require_http_methods(["POST"])
def restore_backup_record_api(request: HttpRequest, uuid: Any) -> JsonResponse:
    """Restore the database from an existing BackupRecord in storage (one-click restore)."""
    try:
        record = BackupRecord.objects.get(uuid=uuid)
        config = BackupConfiguration.get_config()

        data = json.loads(request.body) if request.body else {}
        passphrase = data.get('passphrase', '').strip() or config.encryption_passphrase

        original_type = config.storage_type
        config.storage_type = record.storage_type
        from vibarr.services.backup_service import get_storage_driver, decrypt_payload
        driver = get_storage_driver(config)
        config.storage_type = original_type

        raw_bytes = driver.retrieve_file(record.filename)
        if record.is_encrypted or any(raw_bytes.startswith(m) for m in [b"VIBRANC1", b"BLABENC1", b"SLABENC1", b"GLABENC1"]):
            raw_bytes = decrypt_payload(raw_bytes, passphrase)

        sql_content = _extract_and_validate_sql_payload(raw_bytes)
        _restore_sql_into_database(sql_content, preserve_config=config.preserve_config_on_restore)

        logger.info(f"BackupRestore - Info - Successfully restored from snapshot {record.filename}")
        return JsonResponse({
            'status': 'success',
            'message': f"Database successfully restored from snapshot '{record.filename}'."
        })
    except BackupRecord.DoesNotExist:
        return JsonResponse({'error': 'Backup record not found.'}, status=404)
    except Exception as e:
        logger.error(f"BackupRestore - Error - Failed to restore snapshot {uuid}: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def delete_backup_record_api(request: HttpRequest, uuid: Any) -> JsonResponse:
    """Delete a backup from storage and delete its catalog record."""
    try:
        record = BackupRecord.objects.get(uuid=uuid)
        config = BackupConfiguration.get_config()
        original_type = config.storage_type
        config.storage_type = record.storage_type
        from vibarr.services.backup_service import get_storage_driver
        driver = get_storage_driver(config)
        config.storage_type = original_type

        driver.delete_file(record.filename)
        record.delete()
        logger.info(f"BackupDelete - Info - Deleted snapshot {record.filename}")
        return JsonResponse({'status': 'success', 'message': 'Snapshot deleted successfully.'})
    except BackupRecord.DoesNotExist:
        return JsonResponse({'error': 'Backup record not found.'}, status=404)
    except Exception as e:
        logger.error(f"BackupDelete - Error - Failed to delete snapshot {uuid}: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def upload_backup_file_api(request: HttpRequest) -> JsonResponse:
    """Restore database from a direct file upload."""
    try:
        if 'backup_file' not in request.FILES:
            return JsonResponse({'error': 'No backup file uploaded.'}, status=400)

        uploaded = request.FILES['backup_file']
        raw_bytes = uploaded.read()
        passphrase = request.POST.get('passphrase', '').strip()

        from vibarr.services.backup_service import decrypt_payload
        if any(raw_bytes.startswith(m) for m in [b"VIBRANC1", b"BLABENC1", b"SLABENC1", b"GLABENC1"]):
            raw_bytes = decrypt_payload(raw_bytes, passphrase)

        config = BackupConfiguration.get_config()
        sql_content = _extract_and_validate_sql_payload(raw_bytes)
        _restore_sql_into_database(sql_content, preserve_config=config.preserve_config_on_restore)

        return JsonResponse({
            'status': 'success',
            'message': f"Database successfully restored from '{uploaded.name}'."
        })
    except Exception as e:
        logger.error(f"BackupUpload - Error - Restore from upload failed: {e}")
        return JsonResponse({'error': str(e)}, status=500)
