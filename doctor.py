import os
import sys
import django
import importlib.util

# Setup Django environment
sys.path.append('/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vibarr_project.settings')

try:
    django.setup()
except Exception as e:
    print(f"💥 Failed to initialize Django: {e}")
    sys.exit(1)

from django.conf import settings
from django.db import connection
from django.test import Client
from django.urls import reverse

def check_database() -> bool:
    print("Checking Database Connection...")
    try:
        connection.ensure_connection()
        print("  ✅ Database connection successful.")
        return True
    except Exception as e:
        print(f"  ❌ Database connection failed: {e}")
        return False

def check_migrations() -> bool:
    print("Checking Database Migrations...")
    from django.core.management import call_command
    from io import StringIO
    try:
        out = StringIO()
        call_command('showmigrations', stdout=out)
        output = out.getvalue()
        unapplied = []
        for line in output.split('\n'):
            if '[ ]' in line:
                unapplied.append(line.strip())
        if unapplied:
            print("  ❌ Unapplied migrations found:")
            for m in unapplied:
                print(f"    - {m}")
            return False
        else:
            print("  ✅ All database migrations are applied.")
            return True
    except Exception as e:
        print(f"  ❌ Failed checking migrations: {e}")
        return False

def check_redis() -> bool:
    print("Checking Redis Connection...")
    try:
        import redis
        redis_url = settings.Q_CLUSTER.get('redis', 'redis://redis:6379/0')
        r = redis.Redis.from_url(redis_url)
        r.ping()
        print("  ✅ Redis connection successful.")
        return True
    except Exception as e:
        print(f"  ❌ Redis connection failed: {e}")
        return False

def check_connections() -> bool:
    print("Checking Third-Party Services...")
    # Load verify_connections_logic dynamically to avoid path/import issues with dot-directories
    script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.gemini', 'scripts', 'verify_connections_logic.py')
    if not os.path.exists(script_path):
        print(f"  ❌ verify_connections_logic.py not found at {script_path}")
        return False
        
    try:
        spec = importlib.util.spec_from_file_location("verify_connections_logic", script_path)
        if spec is None or spec.loader is None:
            print("  ❌ Could not load spec for verify_connections_logic")
            return False
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        results = module.verify()
        
        all_ok = True
        for svc, status in results.items():
            print(f"    {svc:15}: {status}")
            if "❌" in status:
                all_ok = False
        return all_ok
    except Exception as e:
        print(f"  ❌ Failed to run connection verification: {e}")
        return False

def check_smoke_test() -> bool:
    print("Running Smoke Test on Web UI endpoints...")
    client = Client()
    endpoints = [
        ('dashboard', {}),
        ('settings', {}),
    ]
    # Ensure setup is complete and auth mode is NONE during tests
    from vibarr.models import AppConfig, AuthMode
    config = AppConfig.get_solo()
    old_setup = config.setup_complete
    old_auth = config.auth_mode
    
    config.setup_complete = True
    config.auth_mode = AuthMode.NONE
    config.save()
    
    all_ok = True
    try:
        for name, kwargs in endpoints:
            try:
                url = reverse(name, kwargs=kwargs)
                res = client.get(url)
                if res.status_code == 200:
                    print(f"    ✅ {name:20} | Status: 200")
                else:
                    print(f"    ❌ {name:20} | Status: {res.status_code} (Expected 200)")
                    all_ok = False
            except Exception as e:
                print(f"    💥 {name:20} | CRASHED: {e}")
                all_ok = False
    finally:
        # Restore configuration
        config.setup_complete = old_setup
        config.auth_mode = old_auth
        config.save()
        
    return all_ok

def main() -> None:
    print("-" * 50)
    print("VIBARR WORKSPACE HEALTH DIAGNOSTIC (DOCTOR)")
    print("-" * 50)
    
    db_ok = check_database()
    migrations_ok = check_migrations() if db_ok else False
    redis_ok = check_redis()
    connections_ok = check_connections()
    smoke_ok = check_smoke_test() if db_ok else False
    
    print("-" * 50)
    if db_ok and migrations_ok and redis_ok and connections_ok and smoke_ok:
        print("RESULT: ALL SYSTEMS RUNNING HEALTHY! 🩺💚")
        sys.exit(0)
    else:
        print("RESULT: CRITICAL ISSUES DETECTED! 🩺🚨")
        sys.exit(1)

if __name__ == "__main__":
    main()
