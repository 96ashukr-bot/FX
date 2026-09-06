# Delivery plan

## Phase 1 — platform foundation

- Tenant/domain/branding model
- Users, roles and client ownership
- MT4/MT5 account and execution-node registration
- Durable command and execution-event schemas
- PostgreSQL, Redis, worker and local containers
- Authentication, permissions, audit and health endpoints

## Phase 2 — execution

- MT4 EA and MT5 EA activation, heartbeat and command claiming
- Market/pending order placement, modify, cancel and close
- Exact ticket/position binding and idempotency
- Partial-fill, timeout and restart reconciliation
- Broker-side SL/TP plus central protection monitoring

## Phase 3 — product workflows

- Manual trade ticket
- TradingView webhook ingestion and strategy mapping
- Copy-trading leaders, followers and allocation
- Risk profiles, trade limits and emergency controls
- Live orders, positions, P&L and history

## Phase 4 — white-label operations

- Tenant dashboard and branding studio
- Custom-domain verification and certificate automation
- Plans, licensing and feature entitlements
- Notifications, reports and operational diagnostics

## Phase 5 — release safety

- MT4/MT5 broker-matrix tests
- Failure injection for disconnects and uncertain submissions
- Load test for simultaneous account execution
- Staging soak test and phased production rollout
