# Kubernetes Pod OOMKilled Runbook

## Overview

Resolving Kubernetes pods killed due to Out-of-Memory (OOMKill) events.

## Symptoms

- Pods in `CrashLoopBackOff` state
- Pod events showing `OOMKilled` reason
- `kubectl describe pod <name>` shows `OOMKilled` in last state
- Memory usage alerts firing (e.g., container_memory_usage_bytes near limits)

## Cause

- Memory limit set too low for the workload
- Memory leak in application code
- Large in-memory caches not bounded
- Sudden traffic spike causing memory burst

## Procedure

1. Identify the affected pod:
   ```bash
   kubectl get pods -n <namespace> | grep CrashLoopBackOff
   kubectl describe pod <pod-name> -n <namespace>
   ```

2. Check memory metrics for the past hour in Grafana (dashboard: K8s / Pod Resources).

3. Review the application logs before the crash:
   ```bash
   kubectl logs <pod-name> --previous -n <namespace> | tail -200
   ```

4. If a memory leak is suspected, enable heap profiling and redeploy with a higher limit temporarily:
   ```bash
   kubectl set resources deployment/<name> --limits=memory=2Gi -n <namespace>
   ```

5. Investigate the root cause in code (heap snapshots, profiler output).

## Verification

- Pod stays in `Running` state for at least 30 minutes.
- Memory usage stabilises below 80% of the new limit.

## Rollback

If increasing the limit causes cluster resource pressure:
1. Scale down the deployment: `kubectl scale deployment/<name> --replicas=1`
2. Notify the on-call engineer for capacity planning.

## Escalation

Escalate to the Platform team if OOMKills continue after limit increase.
