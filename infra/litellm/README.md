# LiteLLM provider routes

This directory contains secret-free example routes for connecting an
operator-managed LiteLLM Proxy to AWS Bedrock and GCP Vertex AI.

- `model-routes.example.yaml` maps stable Istari aliases to operator-selected
  cloud models.
- `provider.env.example` documents the non-secret model, project and region
  inputs used by those routes.

The examples are fragments, not a production LiteLLM deployment. Merge the
required routes into the deployment's reviewed LiteLLM configuration and supply
cloud identity through the platform credential chain. Do not add access keys,
service-account keys, LiteLLM master keys or virtual keys to this directory.

See the [LiteLLM Provider Connectivity Runbook](../../docs/runbooks/litellm-provider-connectivity.md)
for end-to-end AWS, GCP, virtual-key, Istari admin, verification and production
instructions.
