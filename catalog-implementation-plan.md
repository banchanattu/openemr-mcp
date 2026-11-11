# Catalog Implementation Plan

## Purpose

This document translates the requirements in `catalog.md` into a concrete implementation plan for this repository, without making functional code changes yet.

Goal: add `.well-known` discovery support so this MCP server can be discovered and configured by ARD-compatible clients, while preserving the current streamable HTTP transport and authentication behavior for `/mcp`.

Date: 2026-09-01

## Current Repository Findings

### Relevant existing code

- `src/openemr_mcp/http_server.py`
  - Builds the FastMCP streamable HTTP app.
  - Applies `RequestAuthMiddleware` to the entire HTTP app.
  - Currently exposes the MCP transport path only, configured by `OPENEMR_MCP_PATH` / `--path` and defaulting to `/mcp`.
- `src/openemr_mcp/server.py`
  - CLI entrypoint for `stdio` and `streamable-http`.
  - Normalizes transport and path, then calls `run_streamable_http(...)`.
- `src/openemr_mcp/config.py`
  - Central settings object driven by environment variables.
  - Does not currently have any discovery/card-specific configuration.
- `tests/test_request_auth.py`
  - Covers the current request-auth middleware behavior.
  - No `.well-known` route coverage exists yet.
- `examples/smoke_test_http.py`
  - Verifies only the MCP endpoint itself.

### Important implementation implication

Today, `RequestAuthMiddleware` is mounted on the whole HTTP app. If `OPENEMR_REQUIRE_REQUEST_AUTH=true` or request-token mode is enabled, any new `.well-known` route added inside that same app would currently be rejected unless the middleware is explicitly taught to bypass those paths.

That is the main architectural issue to solve first.

## Recommended Design

### High-level approach

Wrap the FastMCP-generated app inside a small top-level Starlette app that owns:

- `GET /.well-known/mcp.json`
- `GET /.well-known/mcp/server-card.json`
- `OPTIONS /.well-known/mcp.json`
- `OPTIONS /.well-known/mcp/server-card.json`
- `GET /.well-known/oauth-protected-resource`
- `OPTIONS /.well-known/oauth-protected-resource`
- The mounted MCP transport app at the configured path, such as `/mcp`

This is safer than trying to patch FastMCP internals because:

- `.well-known` endpoints stay ordinary Starlette routes.
- We can cleanly keep them unauthenticated.
- Existing MCP behavior remains isolated behind the current middleware.
- Testing becomes straightforward with route-level assertions.

### Auth boundary

Keep `RequestAuthMiddleware` applied only to the mounted MCP transport app, not to the outer Starlette app.

Result:

- `.well-known` endpoints remain public as required by ARD discovery.
- `/mcp` continues using the current bearer-token enforcement rules.

### Payload generation strategy

Generate the discovery JSON dynamically from configuration rather than hardcoding hostnames.

This repository already supports configurable host, port, and MCP path. The card and protected resource metadata should derive from:

- externally configured public base URL, when present
- otherwise request-derived scheme/host headers as a fallback
- configured MCP path for the streamable HTTP endpoint URL

This avoids publishing internal bind addresses like `127.0.0.1` when the service runs behind a reverse proxy.

## Proposed Implementation Phases

## Phase 1: Add discovery configuration

### Files likely to change

- `src/openemr_mcp/config.py`
- `README.md`
- `.env.example` if present in the working tree at implementation time

### Add new settings

Recommended new environment variables:

- `OPENEMR_MCP_PUBLIC_BASE_URL`
  - Example: `https://mcp.example.com`
  - Primary source for absolute URLs emitted in `.well-known` responses.
- `OPENEMR_MCP_SERVER_NAME`
  - Default: `openemr-mcp-server`
- `OPENEMR_MCP_SERVER_TITLE`
  - Default: `OpenEMR Healthcare MCP Server`
- `OPENEMR_MCP_SERVER_DESCRIPTION`
  - Default can match or closely follow the catalog spec.
- `OPENEMR_MCP_SERVER_ICON_URL`
  - Optional absolute URL.
- `OPENEMR_MCP_VENDOR_NAME`
  - Default: `OpenEMR Community / Internal Tech Team`
- `OPENEMR_MCP_VENDOR_URL`
  - Optional. If omitted, derive from public base URL.
- `OPENEMR_MCP_AUTHORIZATION_SERVER`
  - Optional explicit OAuth authorization server URL.
- `OPENEMR_MCP_AUTH_SCOPES`
  - Comma-separated list. Example: `openid,fhirUser,patient/*.read`
- `OPENEMR_MCP_ENABLE_SSE_CARD_ENTRY`
  - Boolean, default `false` unless SSE support is actually implemented.

### Reasoning

The catalog sample uses absolute URLs. Those should be configurable for production deployment, especially behind ingress, TLS termination, or path-based routing.

## Phase 2: Introduce a discovery/card builder module

### Files likely to change

- New file: `src/openemr_mcp/discovery.py`

### Responsibilities

Create a focused module to:

- build the server card payload
- build the OAuth protected resource metadata payload
- normalize public URLs safely
- derive defaults from settings and/or the incoming request
- centralize response headers for `.well-known` routes

### Recommended functions

- `build_public_base_url(request) -> str`
- `build_mcp_server_card(request, mcp_path: str, version: str) -> dict`
- `build_oauth_protected_resource(request, mcp_path: str) -> dict`
- `well_known_json_response(payload: dict) -> JSONResponse`
- `well_known_options_response() -> Response`

### Reasoning

Keeping this logic out of `http_server.py` reduces the risk of turning the transport bootstrap into a large mixed-responsibility module.

## Phase 3: Restructure the HTTP app composition

### Files likely to change

- `src/openemr_mcp/http_server.py`

### Planned changes

Refactor the current flow into two layers:

1. Inner MCP app
   - built from `FastMCP.streamable_http_app()`
   - still receives `RequestAuthMiddleware`

2. Outer Starlette app
   - owns `.well-known` routes
   - mounts the inner MCP app at the configured MCP path

### Candidate structure

- Keep `build_http_server(host, port, path) -> FastMCP` as-is or close to it.
- Replace `build_streamable_http_app(...)` with something like:
  - `build_authenticated_mcp_app(host, port, path)`
  - `build_root_http_app(host, port, path)`

### Routes to add

- `GET /.well-known/mcp.json`
  - returns JSON card, status `200`
- `GET /.well-known/mcp/server-card.json`
  - returns `301` redirect to `/.well-known/mcp.json`
- `GET /.well-known/oauth-protected-resource`
  - returns JSON metadata, status `200`
- `OPTIONS` handlers for all three paths
  - return empty `200` or `204` with required CORS headers

### Required response headers

Apply on `.well-known` responses:

- `Content-Type: application/json` for JSON responses
- `Access-Control-Allow-Origin: *`
- `Access-Control-Allow-Methods: GET, OPTIONS`
- `Access-Control-Allow-Headers: Content-Type, Authorization`
- `Cache-Control: public, max-age=3600`
- `X-Content-Type-Options: nosniff`

For the redirect response:

- include CORS and cache headers there as well

### Decision note on CORS

The catalog spec allows `*` or a gateway-specific origin. Start with `*` unless you need a narrower deployment policy. It is simpler and aligns with discovery endpoints being public metadata.

## Phase 4: Decide the truthfulness of the `remotes` section

### Critical issue

`catalog.md` proposes advertising both:

- `streamable-http` at `/mcp`
- `sse` at `/mcp/sse`

This repository currently implements streamable HTTP only. I did not find SSE transport support in the codebase.

### Recommendation

Do not advertise SSE in the first implementation unless SSE is actually added and tested.

Safer initial `remotes` output:

```json
[
  {
    "type": "streamable-http",
    "url": "https://<public-base-url>/mcp"
  }
]
```

### Optional future enhancement

If ARD or a target client strictly expects SSE metadata, then SSE support should be implemented as a separate scoped task, not implied in this card change.

## Phase 5: Define the authentication metadata policy

### Current repo reality

The server supports multiple auth modes:

- mock / server-owned OAuth behavior toward OpenEMR
- request-token enforcement for incoming MCP requests
- optional local JWT validation

### Planning decision needed

The server card’s `authentication.required` field must describe client-to-MCP authentication, not just downstream OpenEMR auth.

### Recommendation

Publish OAuth discovery metadata only when this MCP deployment is actually configured to require/request bearer tokens from callers.

Proposed behavior:

- If `OPENEMR_REQUIRE_REQUEST_AUTH=true` or `OPENEMR_AUTH_MODE=request_token`
  - emit:
    - `"authentication": {"required": true, "type": "oauth2", ...}`
    - `/.well-known/oauth-protected-resource`
- Otherwise
  - either:
    - omit the `authentication` block entirely, or
    - emit `"required": false` with no misleading authorization server

### Reasoning

If the card always claims OAuth is required, but the running server accepts anonymous MCP traffic, ARD clients will be configured incorrectly.

## Phase 6: Version and schema handling

### Server card version field

Use the package version from `pyproject.toml` / installed metadata instead of hardcoding `1.0.0`.

Recommended approach:

- expose package version from `openemr_mcp.__init__` or read installed package metadata
- reuse that version in the card payload

### `$schema` field

Use the schema URL specified in `catalog.md`, but keep it isolated as a constant so it can be updated later without touching route logic.

## Phase 7: Testing plan

### Files likely to change

- `tests/test_request_auth.py`
- New file recommended: `tests/test_discovery.py`

### Test coverage to add

#### Discovery route behavior

- `GET /.well-known/mcp.json` returns `200`
- `GET /.well-known/mcp.json` does not require bearer auth even when MCP auth is enabled
- `GET /.well-known/mcp/server-card.json` returns `301`
- redirect `Location` header is exactly `/.well-known/mcp.json`
- `GET /.well-known/oauth-protected-resource` returns `200`

#### Response headers

- JSON route includes all required CORS/cache/security headers
- redirect route includes expected headers
- `OPTIONS` requests return CORS headers correctly

#### Payload correctness

- card includes expected `name`, `title`, `description`, `version`
- `remotes[0].url` uses configured public base URL + configured MCP path
- no SSE remote appears unless explicitly enabled
- auth metadata matches config state
- OAuth protected resource payload points to the same public MCP URL

#### Existing auth regression checks

- `/mcp` still returns `401` when bearer auth is required and no token is supplied
- `/mcp` still accepts bearer auth exactly as before

### Optional stronger test

Use `httpx.ASGITransport` against the composed outer Starlette app rather than only the inner MCP app. That will validate the real route stack.

## Phase 8: Documentation updates

### Files likely to change

- `README.md`
- possibly `catalog.md` if you want the repo spec adjusted to match actual implementation choices

### README additions

Add a short section such as `ARD Discovery` covering:

- discovery endpoints exposed
- requirement to set `OPENEMR_MCP_PUBLIC_BASE_URL` in real deployments
- whether OAuth metadata is conditional
- whether SSE is currently unsupported

### Example documentation snippet to add later

- `/.well-known/mcp.json`
- `/.well-known/mcp/server-card.json`
- `/.well-known/oauth-protected-resource`

## Phase 9: Validation and rollout

### Local verification steps to run after implementation

1. Start the server in streamable HTTP mode.
2. Fetch `/.well-known/mcp.json` without auth.
3. Fetch `/.well-known/oauth-protected-resource` without auth.
4. Confirm `/mcp` still enforces auth when request-token mode is enabled.
5. Confirm the legacy server-card path redirects correctly.
6. Run the existing smoke test against `/mcp`.

### Suggested curl checks

```bash
curl -i http://127.0.0.1:8305/.well-known/mcp.json
curl -i http://127.0.0.1:8305/.well-known/mcp/server-card.json
curl -i http://127.0.0.1:8305/.well-known/oauth-protected-resource
curl -i -X OPTIONS http://127.0.0.1:8305/.well-known/mcp.json
curl -i http://127.0.0.1:8305/mcp
```

### Proxy/deployment verification

If deployed behind Nginx, Traefik, a Kubernetes ingress, or an API gateway, verify that:

- forwarded scheme and host are preserved correctly
- the card emits public HTTPS URLs, not internal bind addresses
- `/.well-known/*` is not intercepted or blocked by proxy rules

## Proposed File Touch List

These are the files I expect the implementation to touch when you approve coding:

- `src/openemr_mcp/config.py`
- `src/openemr_mcp/http_server.py`
- `src/openemr_mcp/__init__.py` or another version source module
- `src/openemr_mcp/discovery.py` (new)
- `tests/test_request_auth.py`
- `tests/test_discovery.py` (new)
- `README.md`
- `.env.example` if present and if you want the new config documented there

## Risks and Tradeoffs

### Risk 1: Misstating supported transports

Advertising SSE now would be inaccurate and could break client discovery. The plan should treat SSE as unsupported unless implemented separately.

### Risk 2: Publishing wrong hostnames

If the card derives URLs from bind host/port instead of a public base URL, ARD clients may receive unusable URLs in reverse-proxy deployments.

### Risk 3: Auth mismatch

If discovery metadata says OAuth is required but the server does not enforce it, client setup will drift from real behavior.

### Risk 4: Middleware bypass done incorrectly

If `.well-known` routes are inserted into the current app without adjusting auth scope, discovery endpoints may incorrectly require bearer tokens.

## Recommended Acceptance Criteria For The First Approved Implementation

I recommend narrowing the first implementation to this minimum truthful scope:

1. Add public unauthenticated support for:
   - `/.well-known/mcp.json`
   - `/.well-known/mcp/server-card.json`
   - `/.well-known/oauth-protected-resource`
2. Advertise only `streamable-http` in `remotes`.
3. Use a configurable public base URL.
4. Keep `/mcp` auth behavior unchanged.
5. Add tests for route behavior, headers, redirect, and auth separation.

This gets ARD discovery in place without overcommitting to unsupported transport metadata.

## Open Questions Requiring Your Review

Please review and answer these before implementation:

1. Should the initial server card advertise only `streamable-http`, or do you want SSE implemented as a separate follow-up before we publish the card?
2. What public base URL should the card use in your target deployment, and do you want that controlled by `OPENEMR_MCP_PUBLIC_BASE_URL`?
3. Do you want the `authentication` block always present, or only when incoming MCP bearer auth is actually required by config?
4. What should the production `vendor.name`, `vendor.url`, and `icon` values be?
5. Should CORS remain `Access-Control-Allow-Origin: *`, or do you already know the exact ARD gateway/client origin you want to restrict to?
6. Do you want me to keep the first implementation limited to discovery endpoints only, or also update README and sample env documentation in the same change set?

## Recommendation Summary

When you approve implementation, I recommend:

- compose an outer Starlette app for `.well-known` routes
- keep auth middleware only on the mounted MCP app
- dynamically generate the card from configuration
- avoid advertising SSE until the code actually supports it
- make auth metadata reflect real runtime enforcement
- add dedicated discovery tests before considering the task complete

Do all the above recommendations
