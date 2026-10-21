"""Backup engine services: encryption, storage drivers, GFS rotation, and webhook alerts."""

import ctypes
import ctypes.util
import gzip
import ipaddress
import json
import logging
import os
import re
import subprocess
import urllib.parse
from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple, Optional

import requests
from django.conf import settings
from django.utils import timezone as dj_timezone

from vibarr.models.backup import BackupConfiguration, BackupRecord

logger = logging.getLogger(__name__)

ENCRYPTION_MAGIC = b"VIBRANC1"


# ---------------------------------------------------------------------------
# 1. AES-256-GCM Encryption / Decryption Layer
# ---------------------------------------------------------------------------

def encrypt_payload(data: bytes, passphrase: str) -> bytes:
    """Encrypt payload using AES-256-GCM with PBKDF2-HMAC-SHA256 key derivation."""
    if not passphrase:
        return data

    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes

    salt = os.urandom(16)
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=200_000,
    )
    key = kdf.derive(passphrase.encode('utf-8'))
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, data, None)

    return ENCRYPTION_MAGIC + salt + nonce + ciphertext


def decrypt_payload(data: bytes, passphrase: str) -> bytes:
    """Decrypt an AES-256-GCM encrypted payload, or return as-is if unencrypted."""
    valid_magics = [ENCRYPTION_MAGIC, b"BLABENC1", b"SLABENC1", b"GLABENC1"]
    matched_magic = None
    for m in valid_magics:
        if data.startswith(m):
            matched_magic = m
            break

    if not matched_magic:
        return data

    if not passphrase:
        raise ValueError("Passphrase required to decrypt encrypted backup payload.")

    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes

    m_len = len(matched_magic)
    salt = data[m_len:m_len + 16]
    nonce = data[m_len + 16:m_len + 28]
    ciphertext = data[m_len + 28:]

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=200_000,
    )
    key = kdf.derive(passphrase.encode('utf-8'))
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ciphertext, None)


# ---------------------------------------------------------------------------
# 2. SSRF-Protected Webhook Notifications
# ---------------------------------------------------------------------------

def is_safe_webhook_url(url: str) -> bool:
    """Validates destination webhook URL to mitigate SSRF attacks against internal network."""
    try:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ('http', 'https'):
            return False

        hostname = parsed.hostname
        if not hostname:
            return False

        # Disallow loopback / link-local / non-routable targets
        if hostname.lower() in ('localhost', '127.0.0.1', '::1', 'metadata.google.internal', '169.254.169.254'):
            return False

        # If it's an IP, verify global routability
        try:
            ip = ipaddress.ip_address(hostname)
            if not ip.is_global:
                return False
        except ValueError:
            pass

        return True
    except Exception:
        return False


def send_backup_failure_alert(config: BackupConfiguration, error_message: str, backup_name: str = "") -> None:
    """Sends JSON notification payload to configured Discord/Slack/Gotify/ntfy webhook."""
    if not config.webhook_url or not is_safe_webhook_url(config.webhook_url):
        return

    payload = {
        "text": f"🚨 [Vibarr] Database Backup Failed: {backup_name}\nError: {error_message}\nTimestamp: {datetime.now(timezone.utc).isoformat()}",
        "content": f"🚨 **[Vibarr] Backup Failure Alert**\nSnapshot: `{backup_name}`\nError: `{error_message}`",
        "title": "Vibarr DB Backup Failure",
        "message": f"Snapshot {backup_name} failed: {error_message}",
        "priority": 8,
    }

    try:
        requests.post(config.webhook_url, json=payload, timeout=8)
    except Exception as exc:
        logger.warning(f"Failed to transmit backup failure webhook: {exc}")


# ---------------------------------------------------------------------------
# 3. Pluggable Storage Drivers
# ---------------------------------------------------------------------------

class BaseStorageDriver:
    """Abstract interface for backup snapshot persistence backends."""
    def test_connection(self) -> Tuple[bool, str]:
        raise NotImplementedError

    def store_file(self, filename: str, data: bytes) -> None:
        raise NotImplementedError

    def retrieve_file(self, filename: str) -> bytes:
        raise NotImplementedError

    def delete_file(self, filename: str) -> bool:
        raise NotImplementedError


class LocalStorageDriver(BaseStorageDriver):
    """Stores backups on local filesystem container volume mount."""
    def __init__(self, directory: str = "/backups"):
        self.directory = directory

    def _ensure_dir(self):
        os.makedirs(self.directory, exist_ok=True)

    def test_connection(self) -> Tuple[bool, str]:
        try:
            self._ensure_dir()
            test_file = os.path.join(self.directory, ".test_write.tmp")
            with open(test_file, 'wb') as f:
                f.write(b"test")
            os.remove(test_file)
            return True, f"Local directory '{self.directory}' is writable."
        except Exception as e:
            return False, f"Local storage error: {e}"

    def store_file(self, filename: str, data: bytes) -> None:
        self._ensure_dir()
        target = os.path.join(self.directory, filename)
        with open(target, 'wb') as f:
            f.write(data)
        try:
            os.chmod(target, 0o600)
        except OSError:
            pass

    def retrieve_file(self, filename: str) -> bytes:
        target = os.path.join(self.directory, filename)
        if not os.path.exists(target):
            raise FileNotFoundError(f"Local backup '{filename}' not found.")
        with open(target, 'rb') as f:
            return f.read()

    def delete_file(self, filename: str) -> bool:
        target = os.path.join(self.directory, filename)
        if os.path.exists(target):
            os.remove(target)
            return True
        return False


class S3StorageDriver(BaseStorageDriver):
    """Stores backups on Amazon S3 or S3-compatible endpoints (MinIO, R2, B2)."""
    def __init__(self, config: BackupConfiguration):
        self.config = config

    def _get_client(self):
        import boto3
        from botocore.config import Config
        cfg = Config(signature_version='s3v4', retries={'max_attempts': 3, 'mode': 'standard'})
        kwargs = {
            'service_name': 's3',
            'region_name': self.config.s3_region or 'us-east-1',
            'aws_access_key_id': self.config.s3_access_key,
            'aws_secret_access_key': self.config.s3_secret_key,
            'config': cfg,
        }
        if self.config.s3_endpoint_url:
            kwargs['endpoint_url'] = self.config.s3_endpoint_url
        return boto3.client(**kwargs)

    def _full_key(self, filename: str) -> str:
        prefix = self.config.s3_prefix or ''
        if prefix and not prefix.endswith('/'):
            prefix += '/'
        return f"{prefix}{filename}"

    def test_connection(self) -> Tuple[bool, str]:
        try:
            s3 = self._get_client()
            s3.head_bucket(Bucket=self.config.s3_bucket)
            return True, f"Successfully authenticated with S3 bucket '{self.config.s3_bucket}'."
        except Exception as e:
            return False, f"S3 connection failed: {e}"

    def store_file(self, filename: str, data: bytes) -> None:
        s3 = self._get_client()
        s3.put_object(
            Bucket=self.config.s3_bucket,
            Key=self._full_key(filename),
            Body=data,
            ServerSideEncryption='AES256'
        )

    def retrieve_file(self, filename: str) -> bytes:
        s3 = self._get_client()
        res = s3.get_object(Bucket=self.config.s3_bucket, Key=self._full_key(filename))
        return res['Body'].read()

    def delete_file(self, filename: str) -> bool:
        s3 = self._get_client()
        s3.delete_object(Bucket=self.config.s3_bucket, Key=self._full_key(filename))
        return True


class CIFSStorageDriver(BaseStorageDriver):
    """Stores backups on SMB/CIFS Windows Network Shares."""
    def __init__(self, config: BackupConfiguration):
        self.config = config

    def _get_connection(self):
        import smbclient
        smbclient.ClientConfig().set(
            username=self.config.cifs_username,
            password=self.config.cifs_password,
            domain_controller=self.config.cifs_domain or None
        )
        share_root = f"\\\\{self.config.cifs_server}\\{self.config.cifs_share}"
        subpath = self.config.cifs_subpath.replace('/', '\\').strip('\\')
        full_dir = f"{share_root}\\{subpath}" if subpath else share_root
        return smbclient, full_dir

    def test_connection(self) -> Tuple[bool, str]:
        try:
            smbclient, full_dir = self._get_connection()
            smbclient.makedirs(full_dir, exist_ok=True)
            test_file = f"{full_dir}\\.test_write.tmp"
            with smbclient.open_file(test_file, mode='wb') as f:
                f.write(b"test")
            smbclient.remove(test_file)
            return True, f"Successfully wrote to CIFS share '{self.config.cifs_share}'."
        except Exception as e:
            return False, f"CIFS connection error: {e}"

    def store_file(self, filename: str, data: bytes) -> None:
        smbclient, full_dir = self._get_connection()
        smbclient.makedirs(full_dir, exist_ok=True)
        path = f"{full_dir}\\{filename}"
        with smbclient.open_file(path, mode='wb') as f:
            f.write(data)

    def retrieve_file(self, filename: str) -> bytes:
        smbclient, full_dir = self._get_connection()
        path = f"{full_dir}\\{filename}"
        with smbclient.open_file(path, mode='rb') as f:
            return f.read()

    def delete_file(self, filename: str) -> bool:
        smbclient, full_dir = self._get_connection()
        path = f"{full_dir}\\{filename}"
        try:
            smbclient.remove(path)
            return True
        except Exception:
            return False


class NFSStorageDriver(BaseStorageDriver):
    """Direct userspace NFSv3/NFSv4 driver using libnfs ctypes binding."""
    def __init__(self, config: BackupConfiguration):
        self.config = config
        self._lib = None
        self._load_lib()

    def _load_lib(self):
        lib_names = ['libnfs.so.14', 'libnfs.so.13', 'libnfs.so', 'libnfs.dylib']
        for name in lib_names:
            try:
                self._lib = ctypes.CDLL(name)
                break
            except OSError:
                continue

        if not self._lib:
            found = ctypes.util.find_library('nfs')
            if found:
                try:
                    self._lib = ctypes.CDLL(found)
                except OSError:
                    pass

        if not self._lib:
            raise RuntimeError("libnfs shared library not installed. Install via apt-get install -y libnfs14 libnfs-dev.")

        self._lib.nfs_init_context.restype = ctypes.c_void_p
        self._lib.nfs_destroy_context.argtypes = [ctypes.c_void_p]
        self._lib.nfs_mount.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p]
        self._lib.nfs_mount.restype = ctypes.c_int
        self._lib.nfs_get_error.argtypes = [ctypes.c_void_p]
        self._lib.nfs_get_error.restype = ctypes.c_char_p

        self._lib.nfs_open.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int, ctypes.POINTER(ctypes.c_void_p)]
        self._lib.nfs_open.restype = ctypes.c_int
        self._lib.nfs_close.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        self._lib.nfs_close.restype = ctypes.c_int

        self._lib.nfs_write.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_char_p]
        self._lib.nfs_write.restype = ctypes.c_int
        self._lib.nfs_read.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_char_p]
        self._lib.nfs_read.restype = ctypes.c_int
        self._lib.nfs_unlink.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        self._lib.nfs_unlink.restype = ctypes.c_int

    def _get_context(self):
        ctx = self._lib.nfs_init_context()
        if not ctx:
            raise RuntimeError("Failed to initialize libnfs context.")
        srv = self.config.nfs_server.encode('utf-8')
        exp = self.config.nfs_export.encode('utf-8')
        res = self._lib.nfs_mount(ctx, srv, exp)
        if res != 0:
            err = self._lib.nfs_get_error(ctx).decode('utf-8')
            self._lib.nfs_destroy_context(ctx)
            raise ConnectionError(f"NFS mount failed: {err}")
        return ctx

    def _nfs_path(self, filename: str) -> bytes:
        sub = self.config.nfs_subpath.strip('/')
        if sub:
            return f"/{sub}/{filename}".encode('utf-8')
        return f"/{filename}".encode('utf-8')

    def test_connection(self) -> Tuple[bool, str]:
        ctx = None
        try:
            ctx = self._get_context()
            test_path = self._nfs_path(".test_write.tmp")
            fh = ctypes.c_void_p()
            # O_CREAT | O_RDWR | O_TRUNC = 0x200 | 0x2 = 0x242
            res = self._lib.nfs_open(ctx, test_path, 0x242, ctypes.byref(fh))
            if res != 0:
                err = self._lib.nfs_get_error(ctx).decode('utf-8')
                return False, f"NFS open write failed: {err}"
            self._lib.nfs_close(ctx, fh)
            self._lib.nfs_unlink(ctx, test_path)
            return True, f"Successfully mounted and verified NFS export '{self.config.nfs_export}'."
        except Exception as e:
            return False, f"NFS connection error: {e}"
        finally:
            if ctx:
                self._lib.nfs_destroy_context(ctx)

    def store_file(self, filename: str, data: bytes) -> None:
        ctx = self._get_context()
        try:
            path = self._nfs_path(filename)
            fh = ctypes.c_void_p()
            res = self._lib.nfs_open(ctx, path, 0x242, ctypes.byref(fh))
            if res != 0:
                err = self._lib.nfs_get_error(ctx).decode('utf-8')
                raise IOError(f"NFS open for write failed: {err}")
            written = self._lib.nfs_write(ctx, fh, len(data), data)
            self._lib.nfs_close(ctx, fh)
            if written < len(data):
                raise IOError("NFS incomplete write.")
        finally:
            self._lib.nfs_destroy_context(ctx)

    def retrieve_file(self, filename: str) -> bytes:
        ctx = self._get_context()
        try:
            path = self._nfs_path(filename)
            fh = ctypes.c_void_p()
            res = self._lib.nfs_open(ctx, path, 0x0, ctypes.byref(fh))  # O_RDONLY = 0
            if res != 0:
                err = self._lib.nfs_get_error(ctx).decode('utf-8')
                raise IOError(f"NFS open for read failed: {err}")

            chunks = []
            buf_len = 65536
            buf = ctypes.create_string_buffer(buf_len)
            while True:
                n = self._lib.nfs_read(ctx, fh, buf_len, buf)
                if n < 0:
                    self._lib.nfs_close(ctx, fh)
                    err = self._lib.nfs_get_error(ctx).decode('utf-8')
                    raise IOError(f"NFS read error: {err}")
                if n == 0:
                    break
                chunks.append(buf.raw[:n])
            self._lib.nfs_close(ctx, fh)
            return b"".join(chunks)
        finally:
            self._lib.nfs_destroy_context(ctx)

    def delete_file(self, filename: str) -> bool:
        ctx = self._get_context()
        try:
            path = self._nfs_path(filename)
            return self._lib.nfs_unlink(ctx, path) == 0
        finally:
            self._lib.nfs_destroy_context(ctx)


def get_storage_driver(config: BackupConfiguration) -> BaseStorageDriver:
    """Factory selecting the storage driver for the active configuration."""
    if config.storage_type == 'LOCAL':
        return LocalStorageDriver(config.local_path)
    elif config.storage_type == 'S3':
        return S3StorageDriver(config)
    elif config.storage_type == 'CIFS':
        return CIFSStorageDriver(config)
    elif config.storage_type == 'NFS':
        return NFSStorageDriver(config)
    raise ValueError(f"Unsupported storage backend: {config.storage_type}")


# ---------------------------------------------------------------------------
# 4. GFS Retention Rotation
# ---------------------------------------------------------------------------

def cleanup_gfs_retention(config: BackupConfiguration, driver: BaseStorageDriver) -> None:
    """Enforces Grandfather-Father-Son retention quotas across storage catalogs."""
    records_to_delete: List[BackupRecord] = []

    # Daily tier
    daily_records = list(BackupRecord.objects.filter(tier='DAILY', status='SUCCESS').order_by('-created_at'))
    if len(daily_records) > config.keep_daily:
        records_to_delete.extend(daily_records[config.keep_daily:])

    # Weekly tier
    weekly_records = list(BackupRecord.objects.filter(tier='WEEKLY', status='SUCCESS').order_by('-created_at'))
    if len(weekly_records) > config.keep_weekly:
        records_to_delete.extend(weekly_records[config.keep_weekly:])

    # Monthly tier
    monthly_records = list(BackupRecord.objects.filter(tier='MONTHLY', status='SUCCESS').order_by('-created_at'))
    if len(monthly_records) > config.keep_monthly:
        records_to_delete.extend(monthly_records[config.keep_monthly:])

    for rec in records_to_delete:
        try:
            driver.delete_file(rec.filename)
            logger.info(f"Purged expired GFS backup '{rec.filename}' ({rec.tier})")
        except Exception as e:
            logger.warning(f"Could not purge remote backup '{rec.filename}': {e}")
        rec.delete()


# ---------------------------------------------------------------------------
# 5. Backup & Restore Operations
# ---------------------------------------------------------------------------

def _resolve_db_credentials() -> Dict[str, str]:
    db_cfg = settings.DATABASES['default']
    return {
        'NAME': db_cfg.get('NAME') or os.environ.get('POSTGRES_DB', 'vibarr'),
        'USER': db_cfg.get('USER') or os.environ.get('POSTGRES_USER', 'vibarr'),
        'PASSWORD': db_cfg.get('PASSWORD') or os.environ.get('POSTGRES_PASSWORD', 'vibarr'),
        'HOST': db_cfg.get('HOST') or os.environ.get('SQL_HOST', 'db'),
        'PORT': str(db_cfg.get('PORT') or os.environ.get('SQL_PORT', '5432')),
    }


def execute_backup(progress_callback=None, manual: bool = False) -> BackupRecord:
    """Creates a compressed, optionally encrypted PostgreSQL snapshot."""
    config = BackupConfiguration.get_config()
    driver = get_storage_driver(config)

    def _progress(pct: int, msg: str = ""):
        if progress_callback:
            progress_callback(pct, msg)

    _progress(10, "Extracting database credentials...")
    creds = _resolve_db_credentials()

    now = datetime.now(timezone.utc)
    date_str = now.strftime('%Y%m%d_%H%M%S')

    # Determine GFS retention tier
    if manual:
        tier = 'MANUAL'
    elif now.day == config.monthly_day:
        tier = 'MONTHLY'
    elif now.weekday() == config.weekly_day:
        tier = 'WEEKLY'
    else:
        tier = 'DAILY'

    filename = f"vibarr_backup_{date_str}_{tier.lower()}.sql.gz"

    _progress(25, "Running pg_dump snapshot...")
    dump_cmd = [
        'pg_dump',
        '-h', creds['HOST'],
        '-p', creds['PORT'],
        '-U', creds['USER'],
        '-d', creds['NAME'],
        '--no-owner',
        '--no-acl',
    ]

    env = os.environ.copy()
    if creds['PASSWORD']:
        env['PGPASSWORD'] = creds['PASSWORD']

    try:
        proc = subprocess.Popen(
            dump_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env
        )
        stdout, stderr = proc.communicate()
        if proc.returncode != 0:
            err_text = stderr.decode('utf-8', errors='replace').strip()
            raise RuntimeError(f"pg_dump exited with error ({proc.returncode}): {err_text}")
    except Exception as e:
        config.last_status = 'FAILED'
        config.last_error = str(e)
        config.last_run_at = dj_timezone.now()
        config.save()
        send_backup_failure_alert(config, str(e), filename)
        raise

    _progress(50, "Compressing snapshot data...")
    compressed = gzip.compress(stdout, compresslevel=6)

    is_encrypted = bool(config.encryption_passphrase)
    if is_encrypted:
        _progress(65, "Encrypting snapshot with AES-256-GCM...")
        payload = encrypt_payload(compressed, config.encryption_passphrase)
    else:
        payload = compressed

    _progress(80, f"Dispatching snapshot to {config.storage_type} storage...")
    try:
        driver.store_file(filename, payload)
    except Exception as e:
        config.last_status = 'FAILED'
        config.last_error = f"Storage persistence failed: {e}"
        config.last_run_at = dj_timezone.now()
        config.save()
        send_backup_failure_alert(config, f"Storage transfer failed: {e}", filename)
        raise

    _progress(90, "Registering catalog entry & enforcing GFS retention...")
    record = BackupRecord.objects.create(
        filename=filename,
        tier=tier,
        storage_type=config.storage_type,
        file_size=len(payload),
        is_encrypted=is_encrypted,
        status='SUCCESS',
    )

    cleanup_gfs_retention(config, driver)

    config.last_status = 'SUCCESS'
    config.last_error = ''
    config.last_run_at = dj_timezone.now()
    config.save()

    _progress(100, "Backup complete.")
    return record


def restore_backup(
    backup_uuid: Optional[str] = None,
    progress_callback=None,
    passphrase: Optional[str] = None,
    uploaded_file_bytes: Optional[bytes] = None
) -> None:
    """Restores the database from a registered catalog record or uploaded file."""
    config = BackupConfiguration.get_config()

    def _progress(pct: int, msg: str = ""):
        if progress_callback:
            progress_callback(pct, msg)

    _progress(10, "Fetching snapshot payload...")
    if uploaded_file_bytes:
        raw_data = uploaded_file_bytes
    elif backup_uuid:
        record = BackupRecord.objects.get(uuid=backup_uuid)
        driver = get_storage_driver(config)
        raw_data = driver.retrieve_file(record.filename)
    else:
        raise ValueError("Must provide either backup_uuid or uploaded_file_bytes.")

    _progress(30, "Decrypting and decompressing archive...")
    effective_passphrase = passphrase or config.encryption_passphrase or ""
    try:
        decrypted = decrypt_payload(raw_data, effective_passphrase)
    except Exception as e:
        raise ValueError(f"Failed to decrypt backup. Verify your encryption passphrase: {e}")

    # Check for gzip signature
    if decrypted.startswith(b"\x1f\x8b"):
        sql_bytes = gzip.decompress(decrypted)
    else:
        sql_bytes = decrypted

    # Sanitize cross-version Postgres parameters (e.g. SET transaction_timeout in PG 17+ dumps on PG 16/15)
    pattern = rb'(?im)^([ \t]*(?:SET\s+transaction_timeout|SELECT\s+pg_catalog\.set_config\(\s*\'transaction_timeout).*)$'
    sql_bytes = re.sub(pattern, rb'-- \1', sql_bytes)

    # Optionally snapshot current BackupConfiguration to preserve across restore
    preserved_config = None
    if config.preserve_config_on_restore:
        preserved_config = BackupConfiguration.objects.filter(pk=1).values().first()

    _progress(55, "Resetting database schemas...")
    creds = _resolve_db_credentials()
    env = os.environ.copy()
    if creds['PASSWORD']:
        env['PGPASSWORD'] = creds['PASSWORD']

    clean_cmd = [
        'psql',
        '-h', creds['HOST'],
        '-p', creds['PORT'],
        '-U', creds['USER'],
        '-d', creds['NAME'],
        '-v', 'ON_ERROR_STOP=1',
        '-c', 'DROP SCHEMA public CASCADE; CREATE SCHEMA public;',
    ]

    clean_proc = subprocess.run(clean_cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if clean_proc.returncode != 0:
        err = clean_proc.stderr.decode('utf-8', errors='replace').strip()
        raise RuntimeError(f"Database schema wipe failed: {err}")

    _progress(75, "Injecting snapshot SQL tables & records...")
    restore_cmd = [
        'psql',
        '-h', creds['HOST'],
        '-p', creds['PORT'],
        '-U', creds['USER'],
        '-d', creds['NAME'],
        '-v', 'ON_ERROR_STOP=1',
    ]

    restore_proc = subprocess.Popen(restore_cmd, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = restore_proc.communicate(input=sql_bytes)
    if restore_proc.returncode != 0:
        err = stderr.decode('utf-8', errors='replace').strip()
        raise RuntimeError(f"Database restore failed: {err}")

    if preserved_config and config.preserve_config_on_restore:
        _progress(95, "Restoring preserved backup configuration...")
        try:
            preserved_config.pop('id', None)
            BackupConfiguration.objects.update_or_create(pk=1, defaults=preserved_config)
        except Exception as e:
            logger.warning(f"Could not restore preserved backup configuration: {e}")

    _progress(100, "Database successfully restored.")
