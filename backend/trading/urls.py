from django.urls import path

from .views import AccountListView, IntentListView, ManualTradeView, TradingViewWebhookView

urlpatterns = [
    path("accounts", AccountListView.as_view()),
    path("intents", IntentListView.as_view()),
    path("trades/manual", ManualTradeView.as_view()),
    path("webhooks/tradingview/<slug:tenant_slug>/<slug:strategy_slug>", TradingViewWebhookView.as_view()),
]
