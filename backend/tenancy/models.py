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


class SubscriptionPlan(TimeStampedModel):
    name = models.CharField(max_length=120)
    code = models.SlugField(unique=True)
    monthly_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    currency = models.CharField(max_length=8, default="USD")
    account_limit = models.PositiveIntegerField(default=1)
    client_limit = models.PositiveIntegerField(default=1)
    features = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class TenantSubscription(TimeStampedModel):
    class Status(models.TextChoices):
        TRIAL = "TRIAL"
        ACTIVE = "ACTIVE"
        PAST_DUE = "PAST_DUE"
        SUSPENDED = "SUSPENDED"
        CANCELLED = "CANCELLED"
        EXPIRED = "EXPIRED"

    tenant = models.OneToOneField(Tenant, related_name="subscription", on_delete=models.PROTECT)
    plan = models.ForeignKey(SubscriptionPlan, related_name="subscriptions", on_delete=models.PROTECT)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.TRIAL)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    metadata = models.JSONField(default=dict, blank=True)

    @property
    def permits_trading(self):
        from django.utils import timezone

        return (
            self.status in {self.Status.TRIAL, self.Status.ACTIVE}
            and self.starts_at <= timezone.now() < self.ends_at
        )
