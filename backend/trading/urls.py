from django.urls import path

from .views import (
    AccountDetailView,
    AccountListView,
    CopyRelationshipListCreateView,
    IntentListView,
    ManualTradeView,
    PositionCloseView,
    PositionListView,
    StrategyListCreateView,
    TradingViewWebhookView,
)

urlpatterns = [
    path("accounts", AccountListView.as_view()),
    path("accounts/<uuid:pk>", AccountDetailView.as_view()),
    path("intents", IntentListView.as_view()),
    path("positions", PositionListView.as_view()),
    path("positions/<uuid:position_id>/close", PositionCloseView.as_view()),
    path("strategies", StrategyListCreateView.as_view()),
    path("copy-relationships", CopyRelationshipListCreateView.as_view()),
    path("trades/manual", ManualTradeView.as_view()),
    path("webhooks/tradingview/<slug:tenant_slug>/<slug:strategy_slug>", TradingViewWebhookView.as_view()),
]
