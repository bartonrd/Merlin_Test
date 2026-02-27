# PostgreSQL High CPU Runbook

## Overview

This runbook covers steps to diagnose and resolve high CPU utilisation on PostgreSQL database servers.

## Symptoms

- CPU usage above 80% sustained for more than 5 minutes
- Slow query alerts firing in monitoring
- Application latency spikes correlated with DB CPU

## Cause

Common causes include:
- Long-running unindexed queries performing sequential scans
- Autovacuum runaway on large tables
- Connection pool exhaustion causing queued connections
- Missing indexes on foreign keys after schema migrations

## Procedure

1. Connect to the database host and check `pg_stat_activity`:
   ```sql
   SELECT pid, now() - query_start AS duration, state, query
   FROM pg_stat_activity
   WHERE state != 'idle'
   ORDER BY duration DESC
   LIMIT 20;
   ```
2. Identify queries running longer than 30 seconds.
3. Check for sequential scans with `pg_stat_user_tables`:
   ```sql
   SELECT relname, seq_scan, idx_scan FROM pg_stat_user_tables
   ORDER BY seq_scan DESC LIMIT 10;
   ```
4. If autovacuum is the cause, check:
   ```sql
   SELECT relname, last_autovacuum, last_autoanalyze FROM pg_stat_user_tables
   ORDER BY last_autovacuum DESC NULLS LAST;
   ```

## Verification

- CPU drops below 40% within 5 minutes of mitigating the culprit query.
- No new slow query alerts fire.

## Rollback

If mitigation steps cause instability:
1. Revert any `ALTER INDEX` or schema changes using the migration rollback script.
2. Restart connection pool (PgBouncer): `systemctl restart pgbouncer`

## References

- Internal wiki: /docs/architecture/database-architecture.md
- PagerDuty escalation policy: DB On-Call Team
