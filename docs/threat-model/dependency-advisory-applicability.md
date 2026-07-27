# Dependency advisory applicability

## Scope

Production dependency audit exceptions that are bounded by an absent execution
mode, with evidence that the affected mode is not part of Coeus.

## GHSA-qwww-vcr4-c8h2

Status: not applicable to the current browser-only frontend architecture.

The advisory affects React Router's unstable React Server Components (RSC) APIs.
Coeus is a Vite single-page application. It uses `createBrowserRouter` and
`react-router-dom` in the browser, has no React Router server runtime, RSC
request handler or server action, and sends state-changing requests to FastAPI
through the existing CSRF-protected API client.

The production audit therefore ignores only `GHSA-qwww-vcr4-c8h2`. All other
moderate-or-higher advisories remain release-blocking. The exact exception lives
in `pnpm-workspace.yaml`, and the root `audit:production` script is shared by
local and CI evaluation so the gate cannot drift.

## Change and expiry controls

- Remove the exception when a compatible patched React Router release is
  adopted.
- Reassess before introducing React Server Components, React Router framework
  mode, server actions or any server-side React Router request handler.
- Dependency updates must continue to run the production audit, frontend tests,
  build and the normal security workflows.
- A future advisory with a different identifier is not covered by this
  exception.

## Residual risk

Package-level tooling reports affected versions without considering whether RSC
is reachable. The repository therefore carries the vulnerable package version
until a compatible upgrade is available, but the described vulnerable execution
path is absent. Accidental introduction of that path without updating this
record would invalidate the exception, so the architecture search and code
review checks above remain mandatory.
