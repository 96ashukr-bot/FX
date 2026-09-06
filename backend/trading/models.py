from django.db import models

from core.models import TimeStampedModel


class TradingAccount(TimeStampedModel):
    class Platform(models.TextChoices):
        MT4 = "MT4"
        MT5 = "MT5"

    class AccountMode(models.TextChoices):
        MT4_TICKETS = "MT4_TICKETS"
        MT5_HEDGING = "MT5_HEDGING"
        MT5_NETTING = "MT5_NETTING"

    tenant = models.ForeignKey("tenancy.Tenant", related_name="trading_accounts", on_delete=models.PROTECT)
    client = models.ForeignKey("core.User", related_name="trading_accounts", on_delete=models.PROTECT)
    platform = models.CharField(max_length=3, choices=Platform.choices)
    account_mode = models.CharField(max_length=16, choices=AccountMode.choices)
    broker_name = models.CharField(max_length=160)
    broker_server = models.CharField(max_length=160)
    login = models.CharField(max_length=64)
    currency = models.CharField(max_length=8, default="USD")
    leverage = models.PositiveIntegerField(null=True, blank=True)
    is_demo = models.BooleanField(default=False)
    is_enabled = models.BooleanField(default=True)
    last_equity = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)
    last_balance = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "platform", "broker_server", "login"],
                name="unique_terminal_account",
            )
        ]


class Strategy(TimeStampedModel):
    tenant = models.ForeignKey("tenancy.Tenant", related_name="strategies", on_delete=models.PROTECT)
    name = models.CharField(max_length=160)
    slug = models.SlugField()
    is_active = models.BooleanField(default=True)
    webhook_secret_ciphertext = models.TextField(blank=True)
    settings = models.JSONField(default=dict, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["tenant", "slug"], name="unique_tenant_strategy")]

    def set_webhook_secret(self, value):
        from core.crypto import encrypt_text

        self.webhook_secret_ciphertext = encrypt_text(value)

    def get_webhook_secret(self):
        from core.crypto import decrypt_text

        return decrypt_text(self.webhook_secret_ciphertext)


class RiskProfile(TimeStampedModel):
    account = models.OneToOneField(TradingAccount, related_name="risk_profile", on_delete=models.CASCADE)
    max_lot_per_order = models.DecimalField(max_digits=12, decimal_places=4)
    max_open_lots = models.DecimalField(max_digits=12, decimal_places=4)
    max_daily_loss = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)
    max_daily_profit = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)
    max_spread_points = models.PositiveIntegerField(null=True, blank=True)
    max_slippage_points = models.PositiveIntegerField(null=True, blank=True)
    trading_enabled = models.BooleanField(default=True)


class TradeIntent(TimeStampedModel):
    class Source(models.TextChoices):
        MANUAL = "MANUAL"
        WEBHOOK = "WEBHOOK"
        STRATEGY = "STRATEGY"
        COPY = "COPY"
        STOP_LOSS = "STOP_LOSS"
        TAKE_PROFIT = "TAKE_PROFIT"
        KILL_SWITCH = "KILL_SWITCH"
        RECONCILIATION = "RECONCILIATION"

    class Action(models.TextChoices):
        OPEN = "OPEN"
        CLOSE = "CLOSE"
        MODIFY = "MODIFY"
        CANCEL = "CANCEL"

    class State(models.TextChoices):
        RECEIVED = "RECEIVED"
        VALIDATED = "VALIDATED"
        QUEUED = "QUEUED"
        CLAIMED = "CLAIMED"
        SUBMITTED = "SUBMITTED"
        ACCEPTED = "ACCEPTED"
        PARTIAL = "PARTIAL"
        FILLED = "FILLED"
        RECONCILED = "RECONCILED"
        REJECTED = "REJECTED"
        CANCELLED = "CANCELLED"
        EXPIRED = "EXPIRED"
        UNKNOWN = "UNKNOWN"

    tenant = models.ForeignKey("tenancy.Tenant", related_name="trade_intents", on_delete=models.PROTECT)
    account = models.ForeignKey(TradingAccount, related_name="trade_intents", on_delete=models.PROTECT)
    strategy = models.ForeignKey(Strategy, null=True, blank=True, on_delete=models.SET_NULL)
    parent_intent = models.ForeignKey(
        "self", null=True, blank=True, related_name="child_intents", on_delete=models.PROTECT
    )
    source = models.CharField(max_length=24, choices=Source.choices)
    action = models.CharField(max_length=12, choices=Action.choices)
    state = models.CharField(max_length=16, choices=State.choices, default=State.RECEIVED)
    idempotency_key = models.CharField(max_length=160)
    canonical_symbol = models.CharField(max_length=64)
    side = models.CharField(max_length=4, choices=(("BUY", "BUY"), ("SELL", "SELL")))
    order_type = models.CharField(max_length=16)
    requested_volume = models.DecimalField(max_digits=12, decimal_places=4)
    filled_volume = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    requested_price = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    stop_loss = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    take_profit = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    request_snapshot = models.JSONField(default=dict)
    execution_snapshot = models.JSONField(default=dict, blank=True)
    failure_code = models.CharField(max_length=64, blank=True)
    failure_message = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["account", "idempotency_key"], name="unique_account_intent")
        ]
        indexes = [
            models.Index(fields=["tenant", "state", "created_at"]),
            models.Index(fields=["account", "state", "created_at"]),
        ]


class Position(TimeStampedModel):
    tenant = models.ForeignKey("tenancy.Tenant", related_name="positions", on_delete=models.PROTECT)
    account = models.ForeignKey(TradingAccount, related_name="positions", on_delete=models.PROTECT)
    opening_intent = models.ForeignKey(TradeIntent, related_name="opened_positions", on_delete=models.PROTECT)
    canonical_symbol = models.CharField(max_length=64)
    broker_symbol = models.CharField(max_length=64)
    side = models.CharField(max_length=4)
    broker_position_ticket = models.CharField(max_length=64, blank=True)
    broker_order_ticket = models.CharField(max_length=64, blank=True)
    volume = models.DecimalField(max_digits=12, decimal_places=4)
    open_price = models.DecimalField(max_digits=20, decimal_places=8)
    stop_loss = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    take_profit = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    current_price = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    current_profit = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)
    last_broker_seen_at = models.DateTimeField(null=True, blank=True)
    protection_revision = models.PositiveIntegerField(default=1)
    is_open = models.BooleanField(default=True)
    broker_snapshot = models.JSONField(default=dict)

    class Meta:
        indexes = [models.Index(fields=["account", "is_open", "canonical_symbol"])]


class CopyRelationship(TimeStampedModel):
    class Allocation(models.TextChoices):
        FIXED_LOT = "FIXED_LOT"
        EQUITY_RATIO = "EQUITY_RATIO"
        BALANCE_RATIO = "BALANCE_RATIO"
        RISK_PERCENT = "RISK_PERCENT"

    tenant = models.ForeignKey("tenancy.Tenant", related_name="copy_relationships", on_delete=models.PROTECT)
    leader = models.ForeignKey(TradingAccount, related_name="copy_followers", on_delete=models.PROTECT)
    follower = models.ForeignKey(TradingAccount, related_name="copy_leaders", on_delete=models.PROTECT)
    allocation = models.CharField(max_length=20, choices=Allocation.choices)
    allocation_value = models.DecimalField(max_digits=12, decimal_places=4)
    is_active = models.BooleanField(default=True)
    symbol_map = models.JSONField(default=dict, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["leader", "follower"], name="unique_copy_relationship"),
            models.CheckConstraint(
                condition=~models.Q(leader=models.F("follower")), name="copy_accounts_differ"
            ),
        ]
