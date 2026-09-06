# Architecture

## System boundary

FX is a standalone platform. It does not import code, share a database, consume queues, or depend on deployments from either existing trading product.

```text
Tenant UI / TradingView / Admin
              |
          HTTPS API
              |
     Durable trading intents
              |
       Account dispatcher
              |
  Signed terminal command queue
              |
     MT4 EA / MT5 EA on VPS
              |
        Forex broker server
              |
  Execution reports and snapshots
              |
       Reconciliation engine
```

## Tenancy

Every business record carries an immutable `tenant_id`. Tenant resolution uses a verified custom domain and never trusts a tenant identifier submitted by a browser. Database services require an explicit tenant context; background tasks carry both tenant and object identifiers.

Tenant-configurable branding includes name, logos, colours, email identity, legal text, timezone, enabled features and custom domains. Broker accounts and terminal nodes belong to clients within exactly one tenant.

## Trading lifecycle

An inbound request creates one immutable intent with an idempotency key:

```text
RECEIVED -> VALIDATED -> QUEUED -> CLAIMED -> SUBMITTED
         -> ACCEPTED -> PARTIAL -> FILLED -> RECONCILED
```

Terminal or broker failures end in `REJECTED`, `CANCELLED` or `EXPIRED`. A transport timeout becomes `UNKNOWN`, which is reconciled before any resubmission. Commands are never blindly duplicated.

All commands for one MetaTrader account are serialized. Exit commands have priority over new entries. Different accounts can execute concurrently.

## MT4 and MT5 gateway

Each client terminal runs a signed EA distributed from this repository. The EA:

1. Registers using a one-time activation token.
2. Receives a rotated device credential bound to tenant, client and trading account.
3. Long-polls or claims commands over TLS.
4. Checks command expiry and idempotency before calling the terminal API.
5. Returns submission, fill, rejection and snapshot events.
6. Sends heartbeats and open-order/position snapshots for reconciliation.

MT4 exits bind to broker ticket(s). MT5 exits bind to position tickets in hedging mode or symbol/account position in netting mode. Symbol aliases and broker volume constraints are learned from the connected terminal and stored in an immutable execution snapshot.

## Entry snapshot

Every confirmed entry stores:

- platform (`MT4` or `MT5`)
- login/account identifier and broker server
- broker symbol and canonical symbol
- order, deal and position tickets
- side, requested volume and filled volume
- execution mode (MT5 netting/hedging or MT4 ticket model)
- digits, point, tick size, contract size and volume limits
- order type, fill policy and time policy
- average fill price and broker timestamps
- strategy, source signal and copy-parent identifiers

Every SL/TP, webhook close, copy close and kill-switch exit uses this broker-confirmed snapshot.

## SL/TP ownership

Where supported, protective SL/TP is submitted to the broker immediately after entry confirmation. The central risk worker also reconciles protection and can issue a market close if broker-side protection is absent or rejected. A trade is marked closed only after broker/terminal confirmation.

## Copy trading

A leader fill creates follower intents, not direct terminal calls. Allocation supports fixed lots, equity ratio, balance ratio and risk percentage. Each follower independently validates symbol mapping, volume steps, margin policy, spread, session and daily limits. One follower failure does not block other accounts.

## Security

- TLS only; no terminal password is sent to the central API.
- One-time activation tokens are hashed and expire quickly.
- Device credentials are scoped, rotated and revocable.
- Commands and events have IDs, nonces, timestamps and signatures.
- Webhooks use tenant-specific secrets, timestamps and replay protection.
- Sensitive configuration is encrypted at rest.
- All administrative and trading actions are audited.
- Strict tenant isolation is tested at the service and API layers.
