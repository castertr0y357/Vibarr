from django.contrib.auth.hashers import make_password, check_password
import secrets
from django.db import models
from django.utils import timezone

class APIKey(models.Model):
    name = models.CharField(max_length=100, help_text="Friendly name for this key (e.g. 'Discord Bot')")
    key_hash = models.CharField(max_length=128, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    @classmethod
    def create_key(cls, name):
        """Creates a new APIKey and returns the (APIKey object, raw_key)."""
        raw_key = f"vb-{secrets.token_hex(24)}"
        key_hash = make_password(raw_key)
        obj = cls.objects.create(name=name, key_hash=key_hash)
        return obj, raw_key

    def verify_key(self, raw_key):
        """Verifies a raw key against the stored hash."""
        return check_password(raw_key, self.key_hash)

    def __str__(self):
        return f"{self.name} (Hashed)"
