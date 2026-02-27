# Database Connection Pool Exhaustion Runbook

## Symptoms
- Application returns HTTP 503 errors
- Log messages: "Connection pool timeout", "HikariPool-1 - Connection is not available"
- Database connection count at maximum (check: `SELECT count(*) FROM pg_stat_activity`)

## Cause
Connection pool exhaustion occurs when all database connections are in use and no connections are returned within the timeout period. Common causes:
- Long-running queries holding connections
- Application bug causing connection leaks
- Sudden spike in traffic exceeding pool capacity
- Database performance degradation causing slow queries

## Procedure
1. Check current connection count: `SELECT count(*), state FROM pg_stat_activity GROUP BY state`
2. Identify long-running queries: `SELECT pid, now() - pg_stat_activity.query_start AS duration, query FROM pg_stat_activity WHERE state != 'idle' ORDER BY duration DESC`
3. If connection leak: restart application pods (kubectl rollout restart deployment/app-server)
4. If long-running queries: terminate blocking queries with `SELECT pg_terminate_backend(pid)`
5. Increase pool size temporarily if traffic spike (config: DB_POOL_MAX_SIZE)

## Verification
- Connection count returns to normal (<50)
- HTTP 503 errors stop
- Application health check passes: `curl http://app-server/health`

## Rollback
- If pool size increase causes memory issues, revert: kubectl set env deployment/app-server DB_POOL_MAX_SIZE=20
