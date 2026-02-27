# Incident INC-2024-0142: API Gateway Timeout Storm

## What Happened
On 2024-03-15 at 14:32 UTC, the API gateway began returning HTTP 504 Gateway Timeout errors for approximately 45% of requests. The incident lasted 28 minutes before mitigation.

## Signals
- Alert: "API Gateway P95 latency > 5s" fired at 14:32 UTC
- Error rate spiked from 0.1% to 45% within 2 minutes
- Log signature: `upstream timed out (110: Connection timed out) while reading response header from upstream`
- Downstream service (order-processor) showing high CPU: 95%+
- Database slow query log: queries taking 8-12 seconds

## Root Cause
A database schema migration deployed at 14:28 UTC added an index to the orders table (42M rows) without CONCURRENTLY flag, causing table lock for the duration of the migration. All writes to the orders table blocked, causing the order-processor service to exhaust its thread pool, which cascaded to API gateway timeouts.

## Fix
1. Identified blocking migration: `SELECT pid, query FROM pg_stat_activity WHERE wait_event_type = 'Lock'`
2. Terminated the migration: `SELECT pg_terminate_backend(pid)`
3. Redeployed previous schema version via Helm rollback
4. Connection counts normalized within 3 minutes

## Prevention
- Added pre-deployment check: detect non-CONCURRENTLY index creation on tables > 1M rows
- Updated migration runbook to require CONCURRENTLY for all production indexes
- Added database lock wait monitoring alert
