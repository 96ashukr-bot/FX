from uuid import UUID

from django.db import transaction
from django.http import FileResponse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from trading.models import Position, TradeIntent, TradingAccount
from trading.services import process_account_snapshot

from .authentication import ExecutionNodeAuthentication
from .models import AccountSnapshot, ExecutionEvent, ExecutionNode, TerminalCommand

EVENT_STATE_MAP = {
    "CLAIMED": TradeIntent.State.CLAIMED,
    "SUBMITTED": TradeIntent.State.SUBMITTED,
    "ACCEPTED": TradeIntent.State.ACCEPTED,
    "PARTIAL": TradeIntent.State.PARTIAL,
    "FILLED": TradeIntent.State.FILLED,
    "REJECTED": TradeIntent.State.REJECTED,
    "CANCELLED": TradeIntent.State.CANCELLED,
    "EXPIRED": TradeIntent.State.EXPIRED,
    "UNKNOWN": TradeIntent.State.UNKNOWN,
}


class NodeAPIView(APIView):
    authentication_classes = [ExecutionNodeAuthentication]
    permission_classes = []


class CommandClaimView(NodeAPIView):
    def post(self, request):
        node = request.execution_node
        with transaction.atomic():
            command = (
                TerminalCommand.objects.select_for_update(skip_locked=True)
                .filter(
                    node=node,
                    status=TerminalCommand.Status.QUEUED,
                    expires_at__gt=timezone.now(),
                )
                .order_by("priority", "sequence")
                .first()
            )
            if not command:
                return Response(status=status.HTTP_204_NO_CONTENT)
            command.status = TerminalCommand.Status.CLAIMED
            command.claimed_at = timezone.now()
            command.save(update_fields=["status", "claimed_at", "updated_at"])
            TradeIntent.objects.filter(pk=command.intent_id, state=TradeIntent.State.QUEUED).update(
                state=TradeIntent.State.CLAIMED,
                updated_at=timezone.now(),
            )
        return Response(
            {
                "command_id": command.id,
                "intent_id": command.intent_id,
                "sequence": command.sequence,
                "kind": command.kind,
                "expires_at": command.expires_at,
                "payload": command.payload,
            }
        )


class EventIngestView(NodeAPIView):
    def post(self, request):
        node = request.execution_node
        try:
            event_id = UUID(str(request.data.get("event_id") or ""))
        except (TypeError, ValueError, AttributeError):
            return Response({"detail": "A valid event_id is required"}, status=400)
        terminal_time = parse_datetime(str(request.data.get("terminal_time") or ""))
        if terminal_time is None:
            return Response({"detail": "A valid terminal_time is required"}, status=400)
        payload = request.data.get("payload") or {}
        if not isinstance(payload, dict):
            return Response({"detail": "payload must be an object"}, status=400)
        command = TerminalCommand.objects.filter(pk=request.data.get("command_id"), node=node).first()
        if not command:
            return Response({"detail": "Unknown command"}, status=404)
        event_type = str(request.data.get("event_type") or "").upper()
        if event_type not in EVENT_STATE_MAP and event_type != "SNAPSHOT":
            return Response({"detail": "Unsupported event type"}, status=400)
        if event_type in {"PARTIAL", "FILLED"}:
            try:
                filled_volume = float(payload.get("filled_volume") or 0)
            except (TypeError, ValueError):
                filled_volume = 0
            snapshot = payload.get("execution_snapshot") or payload
            if filled_volume <= 0:
                return Response({"detail": "A positive filled_volume is required"}, status=400)
            if not isinstance(snapshot, dict) or not (
                snapshot.get("deal_ticket") or snapshot.get("order_ticket") or snapshot.get("position_ticket")
            ):
                return Response({"detail": "Broker execution identifiers are required"}, status=400)
        with transaction.atomic():
            event, created = ExecutionEvent.objects.get_or_create(
                event_id=event_id,
                defaults={
                    "tenant": node.tenant,
                    "node": node,
                    "command": command,
                    "intent": command.intent,
                    "event_type": event_type,
                    "terminal_time": terminal_time,
                    "payload": payload,
                },
            )
            if created and event_type in EVENT_STATE_MAP:
                updates = {"state": EVENT_STATE_MAP[event_type], "updated_at": timezone.now()}
                payload = event.payload
                if event_type in {"PARTIAL", "FILLED"} and payload.get("filled_volume") is not None:
                    updates["filled_volume"] = payload["filled_volume"]
                if event_type == "FILLED":
                    updates["execution_snapshot"] = payload.get("execution_snapshot") or payload
                if event_type == "REJECTED":
                    updates["failure_code"] = str(payload.get("code") or "TERMINAL_REJECTED")
                    updates["failure_message"] = str(payload.get("message") or "Terminal rejected command")
                TradeIntent.objects.filter(pk=command.intent_id).update(**updates)
                if event_type == "FILLED":
                    intent = command.intent
                    snapshot = payload.get("execution_snapshot") or payload
                    if intent.action == TradeIntent.Action.OPEN:
                        Position.objects.update_or_create(
                            opening_intent=intent,
                            defaults={
                                "tenant": intent.tenant,
                                "account": intent.account,
                                "canonical_symbol": intent.canonical_symbol,
                                "broker_symbol": str(
                                    snapshot.get("broker_symbol") or intent.canonical_symbol
                                ),
                                "side": intent.side,
                                "broker_position_ticket": str(snapshot.get("position_ticket") or ""),
                                "broker_order_ticket": str(snapshot.get("order_ticket") or ""),
                                "volume": payload.get("filled_volume") or intent.requested_volume,
                                "open_price": payload.get("average_price")
                                or snapshot.get("open_price")
                                or intent.requested_price
                                or 0,
                                "stop_loss": intent.stop_loss,
                                "take_profit": intent.take_profit,
                                "is_open": True,
                                "broker_snapshot": snapshot,
                            },
                        )
                    elif intent.action == TradeIntent.Action.CLOSE and intent.parent_intent_id:
                        Position.objects.filter(opening_intent_id=intent.parent_intent_id).update(
                            is_open=False, updated_at=timezone.now()
                        )
                if event_type in {"FILLED", "REJECTED", "CANCELLED", "EXPIRED"}:
                    command.status = TerminalCommand.Status.TERMINAL
                    command.save(update_fields=["status", "updated_at"])
        return Response({"accepted": True, "duplicate": not created})


class HeartbeatView(NodeAPIView):
    def post(self, request):
        node = request.execution_node
        node.last_heartbeat_at = timezone.now()
        node.agent_version = str(request.data.get("agent_version") or "")[:32]
        node.terminal_build = str(request.data.get("terminal_build") or "")[:32]
        node.capabilities = request.data.get("capabilities") or {}
        node.save(
            update_fields=[
                "last_heartbeat_at",
                "agent_version",
                "terminal_build",
                "capabilities",
                "updated_at",
            ]
        )
        return Response({"server_time": timezone.now(), "node_id": node.id})


class SnapshotView(NodeAPIView):
    def post(self, request):
        node = request.execution_node
        _snapshot, created = AccountSnapshot.objects.update_or_create(
            node=node,
            sequence=request.data.get("sequence"),
            defaults={
                "tenant": node.tenant,
                "captured_at": request.data.get("captured_at"),
                "account": request.data.get("account") or {},
                "orders": request.data.get("orders") or [],
                "positions": request.data.get("positions") or [],
            },
        )
        account_data = request.data.get("account") or {}
        TradingAccount.objects.filter(pk=node.account_id).update(
            last_balance=account_data.get("balance"),
            last_equity=account_data.get("equity"),
            last_seen_at=timezone.now(),
            updated_at=timezone.now(),
        )
        queued = process_account_snapshot(
            node=node,
            captured_at=request.data.get("captured_at") or timezone.now(),
            positions=request.data.get("positions") or [],
        )
        return Response({"accepted": True, "duplicate": not created, "protection_exits": queued})


class NodeProvisionView(APIView):
    def post(self, request):
        tenant = getattr(request, "tenant", None) or request.user.tenant
        account_query = TradingAccount.objects.filter(pk=request.data.get("account_id"))
        if request.user.role != request.user.Role.PLATFORM_ADMIN:
            account_query = account_query.filter(tenant=tenant)
        account = account_query.first()
        if not account or (
            request.user.role == request.user.Role.CLIENT and account.client_id != request.user.id
        ):
            return Response({"detail": "Trading account not found"}, status=404)
        device_id = str(request.data.get("device_id") or "").strip()
        if not device_id:
            return Response({"detail": "device_id is required"}, status=400)
        with transaction.atomic():
            if ExecutionNode.objects.filter(account=account).exists():
                return Response({"detail": "This account already has an execution node"}, status=409)
            node = ExecutionNode(
                tenant=account.tenant,
                account=account,
                name=str(request.data.get("name") or f"{account.platform} terminal")[:160],
                device_id=device_id,
            )
            credential = node.issue_credential()
            node.save()
        return Response(
            {"node_id": node.id, "credential": credential, "credential_prefix": node.credential_prefix},
            status=201,
        )


class AgentDownloadView(APIView):
    """Serve the reviewed EA source that matches this API protocol."""

    def get(self, request, platform):
        platform = platform.lower()
        filenames = {"mt4": "BridgeSparkFXAgent.mq4", "mt5": "BridgeSparkFXAgent.mq5"}
        filename = filenames.get(platform)
        if not filename:
            return Response({"detail": "Unsupported terminal platform"}, status=404)
        try:
            return FileResponse(
                open(f"/agents/{platform}/{filename}", "rb"),
                as_attachment=True,
                filename=filename,
            )
        except FileNotFoundError:
            return Response({"detail": "Agent package is unavailable"}, status=503)
