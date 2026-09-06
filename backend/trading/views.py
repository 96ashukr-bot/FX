import hashlib
import hmac
import json
import time

from django.conf import settings
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Strategy, TradeIntent, TradingAccount
from .serializers import ManualTradeSerializer, TradeIntentSerializer, TradingAccountSerializer
from .services import IntentError, create_trade_intent


def tenant_for_request(request):
    tenant = getattr(request, "tenant", None) or getattr(request.user, "tenant", None)
    if not tenant:
        raise IntentError("No tenant context")
    if request.user.tenant_id and request.user.tenant_id != tenant.id:
        raise IntentError("Tenant mismatch")
    return tenant


class AccountListView(ListAPIView):
    serializer_class = TradingAccountSerializer

    def get_queryset(self):
        tenant = tenant_for_request(self.request)
        queryset = TradingAccount.objects.filter(tenant=tenant).select_related("execution_node")
        if self.request.user.role == self.request.user.Role.CLIENT:
            queryset = queryset.filter(client=self.request.user)
        return queryset.order_by("broker_name", "login")


class IntentListView(ListAPIView):
    serializer_class = TradeIntentSerializer

    def get_queryset(self):
        tenant = tenant_for_request(self.request)
        queryset = TradeIntent.objects.filter(tenant=tenant).select_related("account", "strategy")
        if self.request.user.role == self.request.user.Role.CLIENT:
            queryset = queryset.filter(account__client=self.request.user)
        state = self.request.query_params.get("state")
        if state:
            queryset = queryset.filter(state=state.upper())
        return queryset.order_by("-created_at")[:500]


class ManualTradeView(APIView):
    def post(self, request):
        serializer = ManualTradeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tenant = tenant_for_request(request)
        account = TradingAccount.objects.filter(pk=serializer.validated_data["account_id"], tenant=tenant).first()
        if not account:
            return Response({"detail": "Trading account not found"}, status=404)
        if request.user.role == request.user.Role.CLIENT and account.client_id != request.user.id:
            return Response({"detail": "Trading account not found"}, status=404)
        payload = dict(serializer.validated_data)
        payload.pop("account_id")
        idempotency_key = payload.pop("idempotency_key")
        try:
            intent, created = create_trade_intent(
                account=account,
                source=TradeIntent.Source.MANUAL,
                action=TradeIntent.Action.OPEN,
                idempotency_key=idempotency_key,
                payload=payload,
            )
        except IntentError as exc:
            return Response({"detail": str(exc)}, status=409)
        return Response(TradeIntentSerializer(intent).data, status=201 if created else 200)


class TradingViewWebhookView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request, tenant_slug, strategy_slug):
        strategy = Strategy.objects.select_related("tenant").filter(
            tenant__slug=tenant_slug,
            slug=strategy_slug,
            tenant__is_active=True,
            is_active=True,
        ).first()
        if not strategy:
            return Response({"detail": "Webhook not found"}, status=404)
        timestamp = request.headers.get("X-FX-Timestamp", "")
        signature = request.headers.get("X-FX-Signature", "")
        try:
            if abs(int(time.time()) - int(timestamp)) > settings.WEBHOOK_CLOCK_SKEW_SECONDS:
                raise ValueError
        except (TypeError, ValueError):
            return Response({"detail": "Expired webhook timestamp"}, status=401)
        body = request.body
        try:
            webhook_secret = strategy.get_webhook_secret()
        except RuntimeError:
            return Response({"detail": "Webhook secret is unavailable"}, status=503)
        expected = hmac.new(webhook_secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return Response({"detail": "Invalid webhook signature"}, status=401)
        payload = json.loads(body)
        account_ids = payload.get("account_ids") or []
        accounts = TradingAccount.objects.filter(tenant=strategy.tenant, id__in=account_ids, is_enabled=True)
        results = []
        for account in accounts:
            key = f"webhook:{payload.get('signal_id')}:{account.id}"
            try:
                intent, created = create_trade_intent(
                    account=account,
                    source=TradeIntent.Source.WEBHOOK,
                    action=TradeIntent.Action.OPEN if payload.get("action", "OPEN").upper() == "OPEN" else TradeIntent.Action.CLOSE,
                    idempotency_key=key,
                    payload=payload,
                    strategy=strategy,
                )
                results.append({"account_id": account.id, "intent_id": intent.id, "created": created})
            except IntentError as exc:
                results.append({"account_id": account.id, "error": str(exc)})
        return Response({"accepted": True, "results": results}, status=status.HTTP_202_ACCEPTED)
