from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from core.models import User
from tenancy.models import SubscriptionPlan, Tenant, TenantSubscription
from terminal.models import ExecutionNode, TerminalCommand
from trading.models import Position, TradeIntent, TradingAccount
from trading.serializers import TradingAccountSerializer
from trading.services import create_trade_intent, process_account_snapshot


class ExecutionLifecycleTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Northstar Markets", slug="northstar")
        plan = SubscriptionPlan.objects.create(name="Test", code="test", account_limit=10, client_limit=10)
        TenantSubscription.objects.create(
            tenant=self.tenant,
            plan=plan,
            status=TenantSubscription.Status.ACTIVE,
            starts_at=timezone.now() - timedelta(days=1),
            ends_at=timezone.now() + timedelta(days=30),
        )
        self.client = User.objects.create_user(
            username="client",
            email="client@example.com",
            password="not-used-here",
            tenant=self.tenant,
        )
        self.account = TradingAccount.objects.create(
            tenant=self.tenant,
            client=self.client,
            platform=TradingAccount.Platform.MT5,
            account_mode=TradingAccount.AccountMode.MT5_HEDGING,
            broker_name="Test Broker",
            broker_server="TestBroker-Demo",
            login="100001",
            is_demo=True,
        )
        self.node = ExecutionNode.objects.create(
            tenant=self.tenant,
            account=self.account,
            name="Client VPS",
            device_id="device-1",
            credential_hash="hash",
            credential_prefix="prefix",
        )

    def test_duplicate_idempotency_key_returns_original_intent(self):
        values = {
            "account": self.account,
            "source": TradeIntent.Source.MANUAL,
            "action": TradeIntent.Action.OPEN,
            "idempotency_key": "manual-1",
            "payload": {"symbol": "EURUSD", "side": "BUY", "order_type": "MARKET", "volume": "0.10"},
        }
        first, first_created = create_trade_intent(**values)
        second, second_created = create_trade_intent(**values)

        self.assertTrue(first_created)
        self.assertFalse(second_created)
        self.assertEqual(first.id, second.id)
        self.assertEqual(TerminalCommand.objects.count(), 1)

    def test_exit_command_has_priority_over_entry(self):
        entry, _ = create_trade_intent(
            account=self.account,
            source=TradeIntent.Source.MANUAL,
            action=TradeIntent.Action.OPEN,
            idempotency_key="entry-1",
            payload={"symbol": "EURUSD", "side": "BUY", "order_type": "MARKET", "volume": "0.10"},
        )
        exit_intent, _ = create_trade_intent(
            account=self.account,
            source=TradeIntent.Source.KILL_SWITCH,
            action=TradeIntent.Action.CLOSE,
            idempotency_key="exit-1",
            payload={
                "symbol": "EURUSD",
                "side": "SELL",
                "order_type": "MARKET",
                "volume": "0.10",
                "execution_snapshot": {"position_ticket": "98765"},
            },
        )

        self.assertEqual(entry.commands.get().priority, 50)
        self.assertEqual(exit_intent.commands.get().priority, 10)
        self.assertEqual(exit_intent.commands.get().payload["close_snapshot"]["position_ticket"], "98765")

    def test_same_idempotency_key_is_isolated_by_account(self):
        second_account = TradingAccount.objects.create(
            tenant=self.tenant,
            client=self.client,
            platform=TradingAccount.Platform.MT4,
            account_mode=TradingAccount.AccountMode.MT4_TICKETS,
            broker_name="Test Broker",
            broker_server="TestBroker-Demo",
            login="100002",
            is_demo=True,
        )
        ExecutionNode.objects.create(
            tenant=self.tenant,
            account=second_account,
            name="Second VPS",
            device_id="device-2",
            credential_hash="hash-2",
            credential_prefix="prefix-2",
        )
        payload = {"symbol": "GBPUSD", "side": "BUY", "order_type": "MARKET", "volume": "0.10"}
        first, _ = create_trade_intent(
            account=self.account,
            source=TradeIntent.Source.MANUAL,
            action=TradeIntent.Action.OPEN,
            idempotency_key="shared-key",
            payload=payload,
        )
        second, _ = create_trade_intent(
            account=second_account,
            source=TradeIntent.Source.MANUAL,
            action=TradeIntent.Action.OPEN,
            idempotency_key="shared-key",
            payload=payload,
        )
        self.assertNotEqual(first.id, second.id)

    def test_decimal_api_payload_is_saved_as_json(self):
        intent, _ = create_trade_intent(
            account=self.account,
            source=TradeIntent.Source.MANUAL,
            action=TradeIntent.Action.OPEN,
            idempotency_key="decimal-payload",
            payload={
                "symbol": "EURUSD",
                "side": "BUY",
                "order_type": "LIMIT",
                "volume": Decimal("0.10"),
                "price": Decimal("1.12500"),
            },
        )
        intent.refresh_from_db()
        self.assertEqual(intent.request_snapshot["volume"], "0.10")
        self.assertEqual(intent.request_snapshot["price"], "1.12500")

    def test_terminal_snapshot_queues_exact_stop_loss_exit_once(self):
        opening, _ = create_trade_intent(
            account=self.account,
            source=TradeIntent.Source.MANUAL,
            action=TradeIntent.Action.OPEN,
            idempotency_key="open-protected",
            payload={"symbol": "EURUSD", "side": "BUY", "order_type": "MARKET", "volume": "0.10"},
        )
        position = Position.objects.create(
            tenant=self.tenant,
            account=self.account,
            opening_intent=opening,
            canonical_symbol="EURUSD",
            broker_symbol="EURUSD.a",
            side="BUY",
            broker_position_ticket="98765",
            volume="0.10",
            open_price="1.10000",
            stop_loss="1.09000",
            take_profit="1.12000",
            broker_snapshot={"position_ticket": "98765", "broker_symbol": "EURUSD.a"},
        )
        snapshot = [{"position_ticket": "98765", "current_price": "1.08990", "profit": "-10"}]
        first = process_account_snapshot(node=self.node, captured_at=timezone.now(), positions=snapshot)
        second = process_account_snapshot(node=self.node, captured_at=timezone.now(), positions=snapshot)
        self.assertTrue(first[0]["created"])
        self.assertFalse(second[0]["created"])
        close = TradeIntent.objects.get(parent_intent=opening, source=TradeIntent.Source.STOP_LOSS)
        self.assertEqual(close.commands.get().payload["close_snapshot"]["position_ticket"], "98765")
        position.refresh_from_db()
        self.assertEqual(position.current_price, Decimal("1.08990000"))

    def test_stale_terminal_heartbeat_is_offline(self):
        self.node.last_heartbeat_at = timezone.now() - timedelta(minutes=2)
        self.node.save(update_fields=["last_heartbeat_at"])
        self.assertEqual(TradingAccountSerializer(self.account).data["connection_status"], "OFFLINE")
        self.node.last_heartbeat_at = timezone.now()
        self.node.save(update_fields=["last_heartbeat_at"])
        self.assertEqual(TradingAccountSerializer(self.account).data["connection_status"], "CONNECTED")

    def test_platform_and_account_mode_must_match(self):
        serializer = TradingAccountSerializer(data={
            "client": self.client.id,
            "platform": "MT4",
            "account_mode": "MT5_HEDGING",
            "broker_name": "Test Broker",
            "broker_server": "TestBroker-Demo",
            "login": "100003",
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn("account_mode", serializer.errors)
