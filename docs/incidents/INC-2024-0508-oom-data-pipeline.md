# Incident Report: INC-2024-0508 – Kubernetes OOMKill Wave

**Date:** 2024-05-08  
**Severity:** P2  
**Duration:** 22 minutes  
**Reported by:** On-call engineer  

## What Happened

Between 09:15 and 09:37 UTC, approximately 30% of pods in the `data-pipeline`
namespace were OOMKilled within 10 minutes following a deployment of version
`pipeline-v1.9.0`.

## Signals

- Kubernetes events: `OOMKilled` for `data-worker` pods
- Alert fired: `container_memory_usage_bytes > 90% of limit` for 8 pods
- Error in application logs (prior to kill):
  ```
  FATAL  heap allocation failed: out of memory
  java.lang.OutOfMemoryError: Java heap space
    at com.company.pipeline.transform.DataTransformer.process(DataTransformer.java:142)
  ```
- Deployment diff showed new in-memory cache added in v1.9.0

## Root Cause

`pipeline-v1.9.0` introduced an unbounded in-memory LRU cache for feature
lookups.  Under full load the cache grew to ~1.8 GB per pod, exceeding the
512Mi memory limit.

## Fix

1. Rolled back deployment to `pipeline-v1.8.3`:
   ```bash
   kubectl rollout undo deployment/data-worker -n data-pipeline
   ```
2. All pods stabilised within 5 minutes of rollback.

## Prevention

- Added JVM heap size flag `-Xmx400m` and bounded LRU cache size to 50k entries.
- Increased pod memory limit to 1Gi as medium-term mitigation.
- Added memory usage dashboard panel for data-pipeline namespace.

## Action Items

- [ ] Add cache size bounds to code review checklist
- [ ] Load-test with production-representative data volumes before releases
