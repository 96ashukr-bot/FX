import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models


class TimeStampedModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class User(AbstractUser):
    class Role(models.TextChoices):
        PLATFORM_ADMIN = "PLATFORM_ADMIN"
        TENANT_ADMIN = "TENANT_ADMIN"
        DEALER = "DEALER"
        CLIENT = "CLIENT"
        AUDITOR = "AUDITOR"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=32, choices=Role.choices, default=Role.CLIENT)
    tenant = models.ForeignKey("tenancy.Tenant", null=True, blank=True, on_delete=models.PROTECT)
    timezone = models.CharField(max_length=64, default="UTC")

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]


class AuditEvent(TimeStampedModel):
    tenant = models.ForeignKey("tenancy.Tenant", null=True, blank=True, on_delete=models.PROTECT)
    actor = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    category = models.CharField(max_length=64)
    action = models.CharField(max_length=128)
    object_type = models.CharField(max_length=128, blank=True)
    object_id = models.CharField(max_length=128, blank=True)
    source_ip = models.GenericIPAddressField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [models.Index(fields=["tenant", "category", "created_at"])]
