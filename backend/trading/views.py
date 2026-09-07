import hashlib
import hmac
import json
import time

from django.conf import settings
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import IsPlatformAdmin, IsTenantAdmin, IsTenantOperator

from .models import CopyRelationship, Position, Strategy, TradeIntent, TradingAccount
from .serializers import (
    CopyRelationshipSerializer,
    ManualTradeSerializer,
    PositionProtectionSerializer,
    PositionSerializer,
    StrategySerializer,
    TradeIntentSerializer,
    TradingAccountSerializer,
)
from .services import IntentError, create_trade_intent, queue_position_close


def tenant_for_request(request):
    tenant = getattr(request, "tenant", None) or getattr(request.user, "tenant", None)
    if not tenant:
        raise IntentError("No tenant context")
    if request.user.tenant_id and request.user.tenant_id != tenant.id:
        raise IntentError("Tenant mismatch")
    return tenant


class AccountListView(generics.ListCreateAPIView):
    serializer_class = TradingAccountSerializer

    def get_queryset(self):
        tenant = tenant_for_request(self.request)
        queryset = TradingAccount.objects.filter(tenant=tenant).select_related("execution_node")
        if self.request.user.role == self.request.user.Role.CLIENT:
            queryset = queryset.filter(client=self.request.user)
        return queryset.order_by("broker_name", "login")

    def perform_create(self, serializer):
        tenant = tenant_for_request(self.request)
        subscription = getattr(tenant, "subscription", None)
        if subscription and TradingAccount.objects.filter(tenant=tenant, is_enabled=True).count() >= subscription.plan.account_limit:
            from rest_framework.exceptions import ValidationError

            raise ValidationError("This company's trading-account limit has been reached")
        client = serializer.validated_data["client"]
        if client.tenant_id != tenant.id:
            from rest_framework.exceptions import ValidationError

            raise ValidationError("Client must belong to the active tenant")
        if self.request.user.role == self.request.user.Role.CLIENT and client.id != self.request.user.id:
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("Clients may only add their own trading accounts")
        serializer.save(tenant=tenant)


class PlatformAccountListView(generics.ListCreateAPIView):
    serializer_class = TradingAccountSerializer
    permission_classes = [IsPlatformAdmin]

    def get_queryset(self):
        queryset = TradingAccount.objects.select_related("tenant", "client", "execution_node")
        client_id = self.request.query_params.get("client")
        return queryset.filter(client_id=client_id).order_by("tenant__name", "broker_name", "login") if client_id else queryset.order_by("tenant__name", "broker_name", "login")

    def perform_create(self, serializer):
        from rest_framework.exceptions import ValidationError

        from core.models import User

        client = serializer.validated_data["client"]
        if client.role != User.Role.CLIENT or not client.tenant_id or not client.is_active:
            raise ValidationError("Select an active client belonging to a company")
        tenant = client.tenant
        subscription = getattr(tenant, "subscription", None)
        if subscription and TradingAccount.objects.filter(tenant=tenant, is_enabled=True).count() >= subscription.plan.account_limit:
            raise ValidationError("This company's trading-account limit has been reached")
        serializer.save(tenant=tenant)


class AccountDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = TradingAccountSerializer

    def get_queryset(self):
        queryset = TradingAccount.objects.filter(tenant=tenant_for_request(self.request))
        if self.request.user.role == self.request.user.Role.CLIENT:
            queryset = queryset.filter(client=self.request.user)
        return queryset


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
        account = TradingAccount.objects.filter(
            pk=serializer.validated_data["account_id"], tenant=tenant
        ).first()
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
        strategy = (
            Strategy.objects.select_related("tenant")
            .filter(
                tenant__slug=tenant_slug,
                slug=strategy_slug,
                tenant__is_active=True,
                is_active=True,
            )
            .first()
        )
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
        expected = hmac.new(
            webhook_secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256
        ).hexdigest()
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
                    action=TradeIntent.Action.OPEN
                    if payload.get("action", "OPEN").upper() == "OPEN"
                    else TradeIntent.Action.CLOSE,
                    idempotency_key=key,
                    payload=payload,
                    strategy=strategy,
                )
                results.append({"account_id": account.id, "intent_id": intent.id, "created": created})
            except IntentError as exc:
                results.append({"account_id": account.id, "error": str(exc)})
        return Response({"accepted": True, "results": results}, status=status.HTTP_202_ACCEPTED)


class StrategyListCreateView(generics.ListCreateAPIView):
    serializer_class = StrategySerializer
    permission_classes = [IsTenantOperator]

    def get_queryset(self):
        return Strategy.objects.filter(tenant=tenant_for_request(self.request)).order_by("name")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["tenant"] = tenant_for_request(self.request)
        return context


class PositionListView(ListAPIView):
    serializer_class = PositionSerializer

    def get_queryset(self):
        queryset = Position.objects.filter(tenant=tenant_for_request(self.request)).select_related("account")
        if self.request.user.role == self.request.user.Role.CLIENT:
            queryset = queryset.filter(account__client=self.request.user)
        open_value = self.request.query_params.get("open")
        if open_value is not None:
            queryset = queryset.filter(is_open=open_value.lower() == "true")
        return queryset.order_by("-updated_at")[:500]


class CopyRelationshipListCreateView(generics.ListCreateAPIView):
    serializer_class = CopyRelationshipSerializer
    permission_classes = [IsTenantAdmin]

    def get_queryset(self):
        return CopyRelationship.objects.filter(tenant=tenant_for_request(self.request)).select_related(
            "leader", "follower"
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["tenant"] = tenant_for_request(self.request)
        return context


class PositionCloseView(APIView):
    def post(self, request, position_id):
        tenant = tenant_for_request(request)
        position = (
            Position.objects.select_related("account", "opening_intent")
            .filter(pk=position_id, tenant=tenant, is_open=True)
            .first()
        )
        if not position or (
            request.user.role == request.user.Role.CLIENT and position.account.client_id != request.user.id
        ):
            return Response({"detail": "Open position not found"}, status=404)
        idempotency_key = str(
            request.data.get("idempotency_key") or f"close:{position.id}:{timezone.now().timestamp()}"
        )
        try:
            intent, created = create_trade_intent(
                account=position.account,
                source=TradeIntent.Source.KILL_SWITCH,
                action=TradeIntent.Action.CLOSE,
                idempotency_key=idempotency_key,
                parent=position.opening_intent,
                payload={
                    "symbol": position.canonical_symbol,
                    "side": "SELL" if position.side == "BUY" else "BUY",
                    "order_type": "MARKET",
                    "volume": position.volume,
                    "execution_snapshot": position.broker_snapshot,
                },
            )
        except IntentError as exc:
            return Response({"detail": str(exc)}, status=409)
        return Response(TradeIntentSerializer(intent).data, status=201 if created else 200)


class PositionProtectionView(APIView):
    def patch(self, request, position_id):
        tenant = tenant_for_request(request)
        position = Position.objects.filter(pk=position_id, tenant=tenant, is_open=True).first()
        if not position or (request.user.role == request.user.Role.CLIENT and position.account.client_id != request.user.id):
            return Response({"detail": "Open position not found"}, status=404)
        serializer = PositionProtectionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        for field in ("stop_loss", "take_profit"):
            if field in serializer.validated_data:
                setattr(position, field, serializer.validated_data[field])
        position.protection_revision += 1
        position.save(update_fields=["stop_loss", "take_profit", "protection_revision", "updated_at"])
        return Response(PositionSerializer(position).data)


class AccountKillSwitchView(APIView):
    def post(self, request, account_id):
        tenant = tenant_for_request(request)
        account = TradingAccount.objects.filter(pk=account_id, tenant=tenant).first()
        if not account or (request.user.role == request.user.Role.CLIENT and account.client_id != request.user.id):
            return Response({"detail": "Trading account not found"}, status=404)
        results = []
        for position in Position.objects.select_related("account", "opening_intent").filter(account=account, is_open=True):
            try:
                intent, created = queue_position_close(position, TradeIntent.Source.KILL_SWITCH, "Account kill switch")
                results.append({"position_id": position.id, "intent_id": intent.id, "created": created})
            except IntentError as exc:
                results.append({"position_id": position.id, "error": str(exc)})
        return Response({"accepted": True, "results": results}, status=202)
