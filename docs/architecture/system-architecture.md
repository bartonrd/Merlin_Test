# System Architecture Overview

## Overview

This document describes the high-level architecture of the backend platform.
All services run on Kubernetes (EKS) in AWS us-east-1.

## Components

### API Gateway

- **Technology:** Kong Gateway (self-hosted)
- **Function:** TLS termination, rate limiting, JWT validation, routing
- **Replicas:** 3 across AZs

### Payments Service

- **Language:** Python 3.11 / FastAPI
- **Database:** PostgreSQL 15 via PgBouncer (connection pooling)
- **Cache:** Redis 7 (session store + idempotency keys)
- **Replicas:** 5 (HPA min=3, max=10)

### Data Pipeline

- **Language:** Java 17 (Spring Batch)
- **Message broker:** Apache Kafka 3.6
- **Database:** PostgreSQL (separate cluster, analytics schema)
- **Replicas:** 8 (HPA min=4, max=20)

### PostgreSQL Clusters

- Two clusters: `payments-db` and `analytics-db`
- Each cluster: 1 primary + 2 read replicas
- Connection pooling via PgBouncer (pool_size=100 per database)
- Backup: pg_dump to S3 daily + WAL streaming to standby

### Monitoring

- Prometheus + Grafana for metrics
- Loki for log aggregation
- PagerDuty for alerting

## Network

All inter-service communication is over private VPC; no public endpoints
except the API Gateway.  Services use Kubernetes service DNS
(`<service>.<namespace>.svc.cluster.local`).

## Deployment

- GitLab CI/CD with Helm charts
- Production deployments require two approvals
- Rollback: `kubectl rollout undo deployment/<name>`
