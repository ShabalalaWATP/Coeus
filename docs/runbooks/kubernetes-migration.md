# Kubernetes Migration Guide

## Current status

Kubernetes is not part of the supported Istari runtime. The repository contains
no Kubernetes manifests, Helm chart, Kustomize configuration or Kubernetes
deployment workflow. The existing OCI images provide a useful boundary for a
future migration, but deploying them unchanged would not create a supported
production system.

## What can be reused

- `infra/docker/api.Dockerfile`: non-root FastAPI image, port 8000, one Uvicorn
  worker.
- `infra/docker/web-prod.Dockerfile`: static React build served by non-root nginx
  on port 8080.
- `/api/v1/health/live` and `/api/v1/health/ready` for probes.
- PostgreSQL persistence configuration and Alembic migrations.
- Environment-variable configuration, CORS controls and secure-cookie checks.

The web API URL is a Vite build-time value. Build the web image with the real
public API origin; setting `VITE_API_BASE_URL` on a running container does not
change an already-built bundle.

## Constrained evaluation topology

A non-production Kubernetes evaluation can preserve current semantics with:

1. One API Deployment with `replicas: 1`; do not add an HPA.
2. One web Deployment using the production nginx image.
3. An external PostgreSQL service with pgvector and a least-privilege app user.
4. A single-writer persistent volume mounted at `/var/lib/coeus/objects`, with
   `COEUS_OBJECT_STORAGE_PROVIDER=local` and
   `COEUS_LOCAL_OBJECT_STORAGE_PATH=/var/lib/coeus/objects`.
5. Kubernetes Secrets for database, session, CSRF and asset-token secrets.
6. An HTTPS Ingress routing the web and API origins, with matching CORS and
   secure-cookie settings.
7. A one-shot migration Job running `alembic upgrade head` before the API rollout.

This topology is for evaluation only. A local filesystem volume and one API
replica are deliberate constraints, not a highly available design.

## Production readiness gates

Before authoring production manifests or a Helm chart:

- replace whole-namespace, single-writer state with transactional shared
  persistence and distributed rate-limit/session controls;
- implement and test shared object storage instead of a pod-local or RWO volume;
- provide a production identity lifecycle and remove development seed accounts;
- implement automated database and object backup/restore with recovery tests;
- export audit evidence to retained, access-controlled storage;
- define resource requests/limits, disruption budgets, network policies,
  monitoring, alerts, incident response and rollback;
- validate ingress upload limits, timeouts, CSP, TLS, CORS and cookie behaviour;
- security-review the cluster, registry, images, secrets and supply chain.

## Migration sequence

1. Complete and independently verify the production readiness gates above.
2. Publish immutable API and web images by digest to an approved registry.
3. Provision PostgreSQL and shared object storage outside application pods.
4. Create namespace, service accounts, secrets and deny-by-default network policy.
5. Run the migration Job and record its result.
6. Deploy the single API replica and verify readiness before deploying the web.
7. Build the web image with the final HTTPS API URL, then deploy it.
8. Configure HTTPS Ingress, CORS and secure cookies; run role and object-access
   smoke tests.
9. Exercise backup restoration and rollback before admitting real users.
10. Increase API replicas only after the distributed-state redesign is complete.

No ready-to-apply manifests are supplied because the storage, identity, ingress
and operational choices are organisation-specific and the present API is
intentionally single-writer.
