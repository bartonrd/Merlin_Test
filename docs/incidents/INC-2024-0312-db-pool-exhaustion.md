# Incident Report: INC-2024-0312 – Database Connection Pool Exhaustion

**Date:** 2024-03-12  
**Severity:** P1  
**Duration:** 47 minutes  
**Reported by:** Alerting (PagerDuty)  

## What Happened

At 14:23 UTC the payments service began returning HTTP 500 errors.
Root cause was exhaustion of the PgBouncer connection pool leading to
connection timeouts and cascading failures in the payments API.

## Signals

- PagerDuty alert: `payments_api_error_rate > 5%`
- Logs showed: `FATAL: remaining connection slots are reserved for non-replication superuser connections`
- DB CPU was stable (40%) — queries were queuing, not running
- PgBouncer stats: `cl_waiting = 450`, `pool_size = 100`

## Root Cause

A background job (nightly report generator) was introduced in deploy
`v2.3.4` without connection pooling configuration. It opened one
connection per report row (up to 500 rows), exhausting the pool.

## Fix

1. Killed the rogue background job process: `kill -9 <pid>`
2. Restarted PgBouncer to flush waiting connections:  
   `systemctl restart pgbouncer`
3. Services recovered within 5 minutes of the restart.

## Prevention

- Added connection pool limit to the report generator (max 5 connections).
- Added a Grafana alert for `pgbouncer_pool_waiting_clients > 50`.
- Code review checklist updated to include DB connection pool usage.

## Action Items

- [ ] Implement connection pool exhaustion runbook (due: 2024-03-19)
- [ ] Add integration test for connection pool limits (due: 2024-03-26)
