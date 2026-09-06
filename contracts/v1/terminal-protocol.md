# Terminal protocol v1

All payloads use UTF-8 JSON over HTTPS. Times are UTC RFC 3339. IDs are UUIDs.

## Claim command

`POST /api/v1/terminal/commands/claim`

The authenticated node submits its platform, account login, last acknowledged sequence and capabilities. The API returns zero or one command. A command contains `command_id`, `intent_id`, `sequence`, `kind`, `expires_at`, `account`, `instrument`, `order`, `protection`, `idempotency_key` and `signature`.

Command kinds: `PLACE`, `MODIFY`, `CANCEL`, `CLOSE`, `CLOSE_ALL`, `SYNC`.

## Execution events

`POST /api/v1/terminal/events`

Event kinds: `CLAIMED`, `SUBMITTED`, `ACCEPTED`, `PARTIAL`, `FILLED`, `REJECTED`, `CANCELLED`, `EXPIRED`, `UNKNOWN`, `SNAPSHOT`.

Every event includes `event_id`, `command_id`, `intent_id`, `sequence`, terminal timestamps and a broker response. Repeating the same `event_id` is safe.

## Heartbeat

`POST /api/v1/terminal/heartbeat`

Reports EA version, terminal build, broker, server, account mode, trading permission, market connection, clock skew and last processed sequence.
