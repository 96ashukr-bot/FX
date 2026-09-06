from decimal import Decimal

from rest_framework import serializers

from .models import TradeIntent, TradingAccount


class TradingAccountSerializer(serializers.ModelSerializer):
    connection_status = serializers.SerializerMethodField()

    class Meta:
        model = TradingAccount
        fields = (
            "id", "platform", "account_mode", "broker_name", "broker_server", "login",
            "currency", "leverage", "is_demo", "is_enabled", "last_equity", "last_balance",
            "last_seen_at", "connection_status",
        )

    def get_connection_status(self, instance):
        node = getattr(instance, "execution_node", None)
        return "CONNECTED" if node and node.is_active and node.last_heartbeat_at else "OFFLINE"


class TradeIntentSerializer(serializers.ModelSerializer):
    class Meta:
        model = TradeIntent
        fields = (
            "id", "account", "strategy", "source", "action", "state", "idempotency_key",
            "canonical_symbol", "side", "order_type", "requested_volume", "filled_volume",
            "requested_price", "stop_loss", "take_profit", "execution_snapshot",
            "failure_code", "failure_message", "created_at", "updated_at",
        )


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
