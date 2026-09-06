from django.contrib import admin

from .models import CopyRelationship, Position, RiskProfile, Strategy, TradeIntent, TradingAccount

admin.site.register((TradingAccount, Strategy, RiskProfile, TradeIntent, Position, CopyRelationship))
