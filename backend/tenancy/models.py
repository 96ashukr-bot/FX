from django.db import models

from core.models import TimeStampedModel


class Tenant(TimeStampedModel):
    name = models.CharField(max_length=160)
    slug = models.SlugField(unique=True)
    legal_name = models.CharField(max_length=200, blank=True)
    support_email = models.EmailField(blank=True)
    timezone = models.CharField(max_length=64, default="UTC")
    is_active = models.BooleanField(default=True)
    features = models.JSONField(default=dict, blank=True)
    branding = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return self.name


class TenantDomain(TimeStampedModel):
    tenant = models.ForeignKey(Tenant, related_name="domains", on_delete=models.CASCADE)
    hostname = models.CharField(max_length=253, unique=True)
    is_primary = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    verification_token = models.CharField(max_length=128, blank=True)
    certificate_status = models.CharField(max_length=32, default="PENDING")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tenant"],
                condition=models.Q(is_primary=True),
                name="one_primary_domain_per_tenant",
            )
        ]


class TenantMembership(TimeStampedModel):
    tenant = models.ForeignKey(Tenant, related_name="memberships", on_delete=models.CASCADE)
    user = models.ForeignKey("core.User", related_name="tenant_memberships", on_delete=models.CASCADE)
    role = models.CharField(max_length=32)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["tenant", "user"], name="unique_tenant_member")]
