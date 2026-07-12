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

### Exact evaluation runtime settings

The current identity repository always begins with development seed users. A
Kubernetes evaluation must therefore use the guarded `dev` mode below, not
`staging` or `prod`:

```text
COEUS_ENVIRONMENT=dev
COEUS_ALLOW_DEV_SEED_USERS=true
COEUS_LOCAL_SEED_CREDENTIAL=<non-default secret, at least 12 characters>
COEUS_DATABASE_URL=<PostgreSQL URL from a Kubernetes Secret>
COEUS_SESSION_SECRET=<at least 32 characters from a Kubernetes Secret>
COEUS_CSRF_SECRET=<at least 32 characters from a Kubernetes Secret>
COEUS_ASSET_TOKEN_SECRET=<at least 32 characters from a Kubernetes Secret>
COEUS_SECURE_COOKIES=true
COEUS_ALLOWED_CORS_ORIGINS=["https://<web-origin>"]
COEUS_PERSISTENCE_PROVIDER=postgres
COEUS_OBJECT_STORAGE_PROVIDER=local
COEUS_LOCAL_OBJECT_STORAGE_PATH=/var/lib/coeus/objects
COEUS_PUBSUB_ENABLED=false
```

Keep one API replica and mount the object path on its persistent volume. The
published local seed credential must never be used. These settings deliberately
enable development identities and are unsupported for production or real
organisational users. Renaming the environment to `staging` or `prod` is not an
identity migration: startup fails closed until a persistent production account
store or approved identity provider replaces the seed repository.

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
