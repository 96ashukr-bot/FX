from decimal import Decimal

from rest_framework import serializers

from .models import CopyRelationship, Position, RiskProfile, Strategy, TradeIntent, TradingAccount


class TradingAccountSerializer(serializers.ModelSerializer):
    connection_status = serializers.SerializerMethodField()

    class Meta:
        model = TradingAccount
        fields = (
            "id",
            "client",
            "platform",
            "account_mode",
            "broker_name",
            "broker_server",
            "login",
            "currency",
            "leverage",
            "is_demo",
            "is_enabled",
            "last_equity",
            "last_balance",
            "last_seen_at",
            "connection_status",
        )
        read_only_fields = ("last_equity", "last_balance", "last_seen_at", "connection_status")

    def get_connection_status(self, instance):
        node = getattr(instance, "execution_node", None)
        return "CONNECTED" if node and node.is_active and node.last_heartbeat_at else "OFFLINE"


class TradeIntentSerializer(serializers.ModelSerializer):
    class Meta:
        model = TradeIntent
        fields = (
            "id",
            "account",
            "strategy",
            "source",
            "action",
            "state",
            "idempotency_key",
            "canonical_symbol",
            "side",
            "order_type",
            "requested_volume",
            "filled_volume",
            "requested_price",
            "stop_loss",
            "take_profit",
            "current_price",
            "current_profit",
            "last_broker_seen_at",
            "protection_revision",
            "execution_snapshot",
            "failure_code",
            "failure_message",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("current_price", "current_profit", "last_broker_seen_at", "protection_revision")


class PositionProtectionSerializer(serializers.Serializer):
    stop_loss = serializers.DecimalField(max_digits=20, decimal_places=8, required=False, allow_null=True)
    take_profit = serializers.DecimalField(max_digits=20, decimal_places=8, required=False, allow_null=True)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("Provide stop_loss or take_profit")
        return attrs


class ManualTradeSerializer(serializers.Serializer):
    account_id = serializers.UUIDField()
    idempotency_key = serializers.CharField(max_length=160)
    symbol = serializers.CharField(max_length=64)
    side = serializers.ChoiceField(choices=("BUY", "SELL"))
    order_type = serializers.ChoiceField(choices=("MARKET", "LIMIT", "STOP", "STOP_LIMIT"), default="MARKET")
    volume = serializers.DecimalField(max_digits=12, decimal_places=4, min_value=Decimal("0.0001"))
    price = serializers.DecimalField(max_digits=20, decimal_places=8, required=False)
    stop_loss = serializers.DecimalField(max_digits=20, decimal_places=8, required=False)
    take_profit = serializers.DecimalField(max_digits=20, decimal_places=8, required=False)


class StrategySerializer(serializers.ModelSerializer):
    webhook_secret = serializers.CharField(write_only=True, required=False, min_length=16)

    class Meta:
        model = Strategy
        fields = ("id", "name", "slug", "is_active", "settings", "webhook_secret", "created_at")

    def create(self, validated_data):
        secret = validated_data.pop("webhook_secret", None)
        strategy = Strategy.objects.create(tenant=self.context["tenant"], **validated_data)
        if secret:
            strategy.set_webhook_secret(secret)
            strategy.save(update_fields=["webhook_secret_ciphertext", "updated_at"])
        return strategy


class RiskProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = RiskProfile
        exclude = ("id", "created_at", "updated_at")
        read_only_fields = ("account",)


class PositionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Position
        fields = (
            "id",
            "account",
            "canonical_symbol",
            "broker_symbol",
            "side",
            "broker_position_ticket",
            "volume",
            "open_price",
            "stop_loss",
            "take_profit",
            "is_open",
            "created_at",
            "updated_at",
        )


class CopyRelationshipSerializer(serializers.ModelSerializer):
    class Meta:
        model = CopyRelationship
        fields = (
            "id",
            "leader",
            "follower",
            "allocation",
            "allocation_value",
            "is_active",
            "symbol_map",
            "created_at",
        )

    def validate(self, attrs):
        tenant = self.context["tenant"]
        if attrs["leader"].tenant_id != tenant.id or attrs["follower"].tenant_id != tenant.id:
            raise serializers.ValidationError("Both accounts must belong to the active tenant")
        return attrs

    def create(self, validated_data):
        return CopyRelationship.objects.create(tenant=self.context["tenant"], **validated_data)
