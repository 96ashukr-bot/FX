import hashlib
import secrets

from django.db import models

from core.models import TimeStampedModel


class ExecutionNode(TimeStampedModel):
    tenant = models.ForeignKey("tenancy.Tenant", related_name="execution_nodes", on_delete=models.PROTECT)
    account = models.OneToOneField("trading.TradingAccount", related_name="execution_node", on_delete=models.PROTECT)
    name = models.CharField(max_length=160)
    device_id = models.CharField(max_length=128, unique=True)
    credential_hash = models.CharField(max_length=128)
    credential_prefix = models.CharField(max_length=16)
    is_active = models.BooleanField(default=True)
    last_sequence = models.PositiveBigIntegerField(default=0)
    last_heartbeat_at = models.DateTimeField(null=True, blank=True)
    agent_version = models.CharField(max_length=32, blank=True)
    terminal_build = models.CharField(max_length=32, blank=True)
    capabilities = models.JSONField(default=dict, blank=True)

    @staticmethod
    def hash_credential(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def issue_credential(self) -> str:
        value = f"fxn_{secrets.token_urlsafe(40)}"
        self.credential_prefix = value[:12]
        self.credential_hash = self.hash_credential(value)
        return value


class TerminalCommand(TimeStampedModel):
    class Kind(models.TextChoices):
        PLACE = "PLACE"
        MODIFY = "MODIFY"
        CANCEL = "CANCEL"
        CLOSE = "CLOSE"
        CLOSE_ALL = "CLOSE_ALL"
        SYNC = "SYNC"

    class Status(models.TextChoices):
        QUEUED = "QUEUED"
        CLAIMED = "CLAIMED"
        ACKNOWLEDGED = "ACKNOWLEDGED"
        TERMINAL = "TERMINAL"

    tenant = models.ForeignKey("tenancy.Tenant", related_name="terminal_commands", on_delete=models.PROTECT)
    node = models.ForeignKey(ExecutionNode, related_name="commands", on_delete=models.PROTECT)
    intent = models.ForeignKey("trading.TradeIntent", related_name="commands", on_delete=models.PROTECT)
    sequence = models.PositiveBigIntegerField()
    kind = models.CharField(max_length=16, choices=Kind.choices)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.QUEUED)
    priority = models.PositiveSmallIntegerField(default=50)
    payload = models.JSONField(default=dict)
    expires_at = models.DateTimeField()
    claimed_at = models.DateTimeField(null=True, blank=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["node", "sequence"], name="unique_node_sequence")]
        indexes = [models.Index(fields=["node", "status", "priority", "sequence"])]


class ExecutionEvent(TimeStampedModel):
    tenant = models.ForeignKey("tenancy.Tenant", related_name="execution_events", on_delete=models.PROTECT)
    node = models.ForeignKey(ExecutionNode, related_name="events", on_delete=models.PROTECT)
    command = models.ForeignKey(TerminalCommand, related_name="events", on_delete=models.PROTECT)
    intent = models.ForeignKey("trading.TradeIntent", related_name="execution_events", on_delete=models.PROTECT)
    event_id = models.UUIDField(unique=True)
    event_type = models.CharField(max_length=24)
    terminal_time = models.DateTimeField()
    payload = models.JSONField(default=dict)


class AccountSnapshot(TimeStampedModel):
    tenant = models.ForeignKey("tenancy.Tenant", related_name="account_snapshots", on_delete=models.PROTECT)
    node = models.ForeignKey(ExecutionNode, related_name="snapshots", on_delete=models.PROTECT)
    sequence = models.PositiveBigIntegerField()
    captured_at = models.DateTimeField()
    account = models.JSONField(default=dict)
    orders = models.JSONField(default=list)
    positions = models.JSONField(default=list)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["node", "sequence"], name="unique_snapshot_sequence")]
