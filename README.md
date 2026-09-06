# FX Trading Platform

Independent, white-label-first platform for executing and managing Forex trades through MetaTrader 4 and MetaTrader 5 terminals.

This repository is intentionally isolated from SparkBridge SaaS and AlgoView Development. It has its own API, database, queues, terminal agents, frontend and deployment lifecycle.

## First release

- Multi-tenant white labelling and custom domains
- Tenant admins, clients and role-based access
- Multiple MT4/MT5 accounts per client
- Manual orders and TradingView webhook strategies
- Copy trading with allocation and risk controls
- Market, limit and stop orders
- Broker-confirmed order, deal and position reconciliation
- Trade-level stop loss, take profit, trailing stop and partial close
- Emergency account and tenant kill switches
- Durable, idempotent execution commands
- Complete audit trail

## Repository layout

- `backend/` — Django API, execution orchestration and workers
- `frontend/` — tenant-aware React application
- `agents/mt4/` — MQL4 terminal execution agent
- `agents/mt5/` — MQL5 terminal execution agent
- `contracts/` — versioned API schemas shared with terminal agents
- `deploy/` — local and production deployment assets
- `docs/` — architecture, security and operating documentation

See [architecture](docs/architecture.md) and [delivery plan](docs/delivery-plan.md).
