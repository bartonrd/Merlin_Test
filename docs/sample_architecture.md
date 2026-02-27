# Platform Architecture Overview

## Services
The platform consists of the following core services:
- **api-gateway**: Nginx-based reverse proxy, handles TLS termination and rate limiting
- **order-processor**: Java Spring Boot service handling order lifecycle (3 replicas)
- **user-service**: Node.js service for authentication and user management
- **inventory-service**: Python FastAPI service for stock management
- **notification-service**: Go service for email/SMS notifications

## Database Layer
- **Primary DB**: PostgreSQL 15 on RDS (db.r6g.2xlarge), connection pooled via PgBouncer
- **Cache**: Redis 7 cluster (3 nodes) for session data and rate limiting
- **Search**: Elasticsearch 8 for product catalog search

## Configuration
- DB_POOL_MAX_SIZE: Maximum database connections per service instance (default: 20)
- REDIS_TIMEOUT_MS: Redis operation timeout (default: 500ms)
- API_GATEWAY_UPSTREAM_TIMEOUT: Nginx upstream timeout (default: 30s)

## Deployment
All services run on Kubernetes (EKS). Deployments managed via Helm charts in the infra-charts repository.
