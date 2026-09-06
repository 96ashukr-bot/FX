from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from terminal.models import TerminalCommand

from .models import TradeIntent, TradingAccount

EXIT_SOURCES = {
    TradeIntent.Source.STOP_LOSS,
    TradeIntent.Source.TAKE_PROFIT,
    TradeIntent.Source.KILL_SWITCH,
}


class IntentError(ValueError):
    pass


def _json_safe(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _normalize_side(value):
    side = str(value or "").upper()
    if side not in {"BUY", "SELL"}:
        raise IntentError("side must be BUY or SELL")
    return side


def _normalize_order_type(value):
    order_type = str(value or "MARKET").upper()
    if order_type not in {"MARKET", "LIMIT", "STOP", "STOP_LIMIT"}:
        raise IntentError("Unsupported order type")
    return order_type


@transaction.atomic
def create_trade_intent(*, account, source, action, idempotency_key, payload, strategy=None, parent=None):
    account = TradingAccount.objects.select_for_update().select_related("tenant").get(pk=account.pk)
    if not account.tenant.is_active:
        raise IntentError("Tenant is disabled")
    subscription = getattr(account.tenant, "subscription", None)
    if not subscription or not subscription.permits_trading:
        raise IntentError("Tenant subscription does not permit trading")
    if not account.is_enabled:
        raise IntentError("Trading account is disabled")
    node = getattr(account, "execution_node", None)
    if not node or not node.is_active:
        raise IntentError("No active MT4/MT5 execution node is connected")

    existing = TradeIntent.objects.filter(account=account, idempotency_key=idempotency_key).first()
    if existing:
        return existing, False

    side = _normalize_side(payload.get("side"))
    order_type = _normalize_order_type(payload.get("order_type"))
    volume = Decimal(str(payload.get("volume") or "0"))
    if volume <= 0:
        raise IntentError("volume must be greater than zero")
    symbol = str(payload.get("symbol") or "").strip().upper()
    if not symbol:
        raise IntentError("symbol is required")

    intent = TradeIntent.objects.create(
        tenant=account.tenant,
        account=account,
        strategy=strategy,
        parent_intent=parent,
        source=source,
        action=action,
        state=TradeIntent.State.QUEUED,
        idempotency_key=idempotency_key,
        canonical_symbol=symbol,
        side=side,
        order_type=order_type,
        requested_volume=volume,
        requested_price=payload.get("price"),
        stop_loss=payload.get("stop_loss"),
        take_profit=payload.get("take_profit"),
        request_snapshot=_json_safe(payload),
    )
    last_sequence = TerminalCommand.objects.filter(node=node).aggregate(value=Max("sequence"))["value"] or 0
    kind = {
        TradeIntent.Action.OPEN: TerminalCommand.Kind.PLACE,
        TradeIntent.Action.CLOSE: TerminalCommand.Kind.CLOSE,
        TradeIntent.Action.MODIFY: TerminalCommand.Kind.MODIFY,
        TradeIntent.Action.CANCEL: TerminalCommand.Kind.CANCEL,
    }[action]
    priority = 10 if action == TradeIntent.Action.CLOSE or source in EXIT_SOURCES else 50
    TerminalCommand.objects.create(
        tenant=account.tenant,
        node=node,
        intent=intent,
        sequence=last_sequence + 1,
        kind=kind,
        priority=priority,
        expires_at=timezone.now() + timedelta(seconds=settings.TERMINAL_COMMAND_TTL_SECONDS),
        payload={
            "account": {
                "platform": account.platform,
                "login": account.login,
                "server": account.broker_server,
                "mode": account.account_mode,
            },
            "instrument": {"canonical_symbol": symbol},
            "order": {
                "side": side,
                "type": order_type,
                "volume": str(volume),
                "price": str(payload.get("price")) if payload.get("price") is not None else None,
            },
            "protection": {
                "stop_loss": str(payload.get("stop_loss")) if payload.get("stop_loss") is not None else None,
                "take_profit": str(payload.get("take_profit"))
                if payload.get("take_profit") is not None
                else None,
            },
            "close_snapshot": payload.get("execution_snapshot") or {},
            "idempotency_key": idempotency_key,
        },
    )
    return intent, True
