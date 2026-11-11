# Plan: Support External Access Token In `OAuth2TokenManager`

## Goal

Allow this MCP server to use tokens that are sent on every inbound MCP request, instead of always generating a new OpenEMR token with `client_id`, `client_secret`, `username`, and `password`.

The target outcome is:

- If an inbound bearer token is provided on a request, OpenEMR API calls triggered by that request use that token directly.
- If an inbound refresh token is also provided, the server can use it only within that same request context when refresh is needed.
- The authenticated user context for tool behavior comes from the inbound token associated with that request.
- The inbound access token is the same token format and trust domain that OpenEMR itself accepts.
- The server does not trust request origin, network location, or upstream service identity by itself.
- If no valid inbound token is provided, the request should fail in strict mode.
- The change is safe for the MCP server transport being used, especially `streamable-http`.

## Current State

Today the auth flow is global and process-level:

1. `src/openemr_mcp/data_source.py`
   - `get_http_client()` creates `_OpenEMRClient`.
   - `_OpenEMRClient` creates `OAuth2TokenManager(settings)`.
   - `_get_headers()` always calls `get_valid_access_token()`.

2. `src/openemr_mcp/auth.py`
   - `OAuth2TokenManager` assumes responsibility for:
   - client registration
   - client enablement
   - password grant
   - refresh grant
   - in-memory token caching

3. `src/openemr_mcp/config.py`
   - only supports env-based OAuth credentials today.

This means the server currently owns authentication, rather than accepting a caller-provided token.

## Design Decision

The correct model is request-scoped token handling.

Each inbound MCP HTTP request may include:

- `Authorization: Bearer <access_token>`
- optionally a refresh token header

That means:

- `listTools`
- `callTool`
- and any other MCP HTTP request

must be processed against the auth context from that same request only.

This rules out a process-wide token design for your primary use case.

## Trust Model

Assume zero trust with respect to request origin.

That means:

- the server cannot assume a request is safe because it came from an internal network or known host
- the server cannot assume one upstream microservice identity is enough for all requests
- every MCP request must carry its own auth context
- authorization decisions and downstream OpenEMR access must be based on the token attached to that request

Because of this, request auth should be treated as mandatory for HTTP mode unless you deliberately enable a separate compatibility mode.

## Token Trust Boundary

The inbound bearer token is already trusted by OpenEMR itself.

That means the MCP server does not need to invent a second authentication system for normal operation. Its primary responsibility is:

- receive the OpenEMR-trusted access token on the inbound MCP request
- bind it to the current request context
- use that same token on outbound OpenEMR API calls

In other words, the MCP server should mostly be forwarding an OpenEMR-valid token, not exchanging it for a different one.

## Recommended Direction

Use a phased approach:

1. Add request-scoped auth context to the HTTP server path.
2. Refactor `OAuth2TokenManager` so it can consume request-scoped access/refresh tokens first.
3. Use the token-derived user identity for all downstream OpenEMR operations triggered by that request.
4. Make strict request-token mode the default behavior for HTTP deployments where request origin is unknown.
5. Keep env/config-based OAuth as a compatibility fallback only if you still want non-token-based operation.

Reason:
You clarified that every MCP request will carry bearer authentication. That means the token is part of the request identity and must not escape that request boundary.

## Proposed Auth Model

Add a unified token resolution strategy inside `OAuth2TokenManager`:

1. If a request-scoped access token is present, return it directly.
2. Else if request-scoped refresh token is present and strict forwarding rules allow refresh, refresh within that same request context.
3. Else if a cached internally-managed token is valid, return it.
4. Else run the existing OpenEMR OAuth flow, only if fallback mode is enabled.

Because the inbound token is already OpenEMR-trusted, step 1 should be the normal production path.

For your stated scenario, the intended production behavior should be stricter:

1. Require request-scoped access token.
2. Optionally use request-scoped refresh token only if enabled.
3. If request auth is missing or invalid, fail the request.
4. Do not silently fall back to process-owned OAuth credentials.

This preserves one public method:

- `get_valid_access_token(force_refresh: bool = False) -> str`

That is important because tests already enforce that method contract.

## Proposed Implementation Plan

### Phase 1: Refactor `OAuth2TokenManager` to support request token source

Planned changes:

- Introduce the concept of a request-scoped auth token provider.
- Keep current password-grant logic intact as fallback.
- Separate these responsibilities more explicitly:
  - request-scoped token resolution
  - request-scoped refresh handling
  - internally managed token acquisition
  - internal cache validation

Important implementation bias:

- request token forwarding should be the default success path
- internal OAuth acquisition should be treated as compatibility fallback, not as the primary auth flow

Possible shape:

- constructor injection:
  - `OAuth2TokenManager(settings, request_auth_provider=...)`

Request auth provider returns:

- access token
- optional refresh token
- optional parsed claims/user identity
- request mode flags

Recommendation:
Prefer provider/context-based injection over mutable global setter methods, because setter methods are unsafe under concurrent HTTP requests.

### Phase 2: Introduce request/auth context at the server boundary

Planned changes:

- Add a request-scoped auth context for streamable HTTP requests.
- Extract bearer token from the inbound request sent to the MCP server.
- Extract optional refresh token from a defined header.
- Parse token claims or user identity metadata if needed for downstream user-aware behavior.
- Make that token available to the code path that eventually calls `data_source.get_http_client()`.
- Reject requests early when required auth headers are missing or malformed.

Likely requirement:

- a context-local storage mechanism such as `contextvars`, because the comment in `data_source.py` explicitly says there is no per-request context today.

Target behavior:

- Incoming request header:
  - `Authorization: Bearer <caller_token>`
- Optional incoming request header:
  - for example `X-Refresh-Token: <refresh_token>` or another agreed header name
- MCP server:
  - reads the caller token
  - reads optional refresh token
  - stores both in request context
  - derives user context from token/claims for that same request
  - OpenEMR client uses that same access token for that request's outbound OpenEMR API calls

Important:
The refresh token should not be accepted in the same `Authorization` header. It needs its own explicit header contract.

Important:
Request authentication should happen for every MCP HTTP operation, not only tool execution. If the transport exposes operations such as initialization, listing tools, or invoking tools through different request paths, they all need the same auth-context setup.

### Phase 3: Update `data_source.py` to read from auth context

Planned changes:

- Replace the current purely global `OAuth2TokenManager(settings)` usage with a token manager that can check:
  - request context token first
  - request context refresh token second, if refresh is allowed
  - optional env-configured static token third
  - internal OAuth flow last, if fallback is allowed

This is the narrowest place to adapt behavior because `_get_headers()` is already the common path for OpenEMR API calls.

### Phase 4: Add config for controlled fallback modes

Add explicit config knobs so behavior is not ambiguous.

Proposed env vars:

- `OPENEMR_AUTH_MODE`
  - possible values:
    - `oauth`
    - `request_token`
    - `auto`
- `OPENEMR_REFRESH_TOKEN_HEADER`
  - header name to read refresh token from, if enabled
- `OPENEMR_ENABLE_REQUEST_TOKEN_REFRESH`
  - `true|false`
- `OPENEMR_REQUIRE_REQUEST_AUTH`
  - `true|false`
- `OPENEMR_VALIDATE_REQUEST_TOKEN_LOCALLY`
  - `true|false`

Recommended semantics:

- `auto`:
  - use request token if present
  - else optional env token if present
  - else OAuth credentials
- `request_token`:
  - require inbound request token; do not attempt password grant unless explicitly allowed
- `oauth`:
  - current behavior only

This avoids hidden fallback that could surprise operators.

Recommended production setting for your use case:

- `OPENEMR_AUTH_MODE=request_token`
- `OPENEMR_REQUIRE_REQUEST_AUTH=true`

### Phase 5: Documentation updates

Update:

- `README.md`
- env var documentation
- HTTP deployment examples

Need to document clearly whether:

- the caller sends token to the MCP server
- the MCP server forwards that same OpenEMR-trusted token to OpenEMR as-is
- the MCP server can optionally refresh using a caller-provided refresh token for that same request only
- token validation is delegated to OpenEMR rather than locally introspected
- user context is derived from the inbound request token
- requests without valid auth are rejected regardless of origin

### Phase 6: Tests

Add tests for:

1. `OAuth2TokenManager`
   - returns request token when present
   - refreshes with request refresh token only when enabled
   - falls back to cached internal token when no request token exists
   - falls back to password grant when needed

2. `data_source`
   - `_get_headers()` uses request token when available
   - `_get_headers()` uses fallback token path when request token absent

3. transport/server behavior
   - HTTP request with bearer token leads to forwarded OpenEMR authorization
   - HTTP request with optional refresh token can refresh only inside that request path
   - `listTools` and `callTool` both establish auth context correctly
   - unauthenticated HTTP requests fail before tool logic runs
   - no cross-request token leakage

4. negative cases
   - missing token in `request_token` mode fails cleanly
   - malformed auth header fails cleanly
   - invalid refresh token fails cleanly

## API/Behavior Rules To Keep Clear

These rules should be explicit in implementation:

1. The MCP server should not log inbound bearer tokens.
2. Inbound bearer tokens should not be cached globally.
3. Inbound refresh tokens should not be persisted beyond the request scope.
4. `force_refresh=True` should only apply to request refresh logic if request refresh is enabled.
5. If the token is caller-provided and already OpenEMR-trusted, the MCP server should treat it as opaque unless claim parsing is explicitly needed for user context.
6. The fallback to username/password OAuth should be disabled when running in strict request-token mode.
7. User identity used by tools must come from the current request's token context, not from process-global config.
8. Request origin must not be used as an authentication signal.

## Risks

### 1. Multi-user token leakage

If external token support is implemented with a global mutable variable, one request can use another request's token. This is the main thing to avoid.

### 2. Transport limitations

`FastMCP` may not expose raw HTTP headers in the current integration path as directly as a normal FastAPI handler would. If that is true, request-scoped token extraction may require a wrapper layer around the MCP app or a custom middleware approach.

### 3. Token expiry handling

If the upstream microservice sends expired tokens, OpenEMR will reject them. The MCP server should not silently swap to password-grant mode unless that fallback is explicitly allowed by config.

### 4. Refresh-token handling

If the server accepts refresh tokens directly, the header contract and refresh rules must be explicit. Otherwise the server can accidentally become a secondary auth system instead of a thin downstream token-forwarding layer.

### 5. Mixed trust boundaries

If the same server accepts both caller tokens and its own OAuth credentials, precedence must be deterministic and documented. Otherwise debugging auth failures will be messy.

### 6. Authentication gaps outside tool execution

If auth context is wired only for tool calls but not for other MCP HTTP operations, an unknown caller may still interact with server capabilities in ways you did not intend. The auth hook must be placed at the transport boundary, not only inside tool handlers.

## Open Questions

These should be resolved before implementation:

1. Will this MCP server be used only over `streamable-http`, or also via `stdio`?
2. Are these many user-specific tokens, with user context derived from each token?
3. Should the MCP server ever fall back to its own OAuth credentials, or must it fail if caller token is absent?
4. Should refresh be done by the upstream microservice only, or may the MCP server perform refresh when a refresh token header is present?
5. What exact refresh-token header name should be supported?
6. Do you want local claim parsing only for user identification, or should OpenEMR remain the source of truth by simply honoring the forwarded access token?

## TODO

- Decide whether optional local JWT inspection should remain enabled as a feature. The current idea is best-effort payload/expiry validation only, not full signature verification. Confirm whether that extra parsing step is worth the overhead and operational complexity for your deployment, or whether the server should simply forward the OpenEMR-trusted token and let OpenEMR remain the only validator.

## Recommended Final Shape

If I were implementing this for your stated scenario, I would target this architecture:

1. Add request-scoped auth context using `contextvars`.
2. Capture inbound bearer token from every streamable HTTP MCP request.
3. Capture optional refresh token from a separate configured header.
4. Build request user context from token claims or a validated identity extraction step.
5. Make `OAuth2TokenManager.get_valid_access_token()` resolve token in this order:
   - request access token
   - request refresh token, only if enabled
   - optional static env token
   - internal OAuth flow, only if allowed
6. Add strict config mode so the server can be run as "request token required".
7. Add tests specifically proving there is no cross-request auth leakage.

For production, I would default to:

1. unknown request origin is not trusted
2. request token is mandatory
3. the same OpenEMR-trusted token is forwarded downstream
4. request fails closed if auth is absent or invalid
5. no fallback to process-owned credentials unless deliberately enabled

## Suggested Implementation Order

1. Refactor `auth.py` internals without changing public method name.
2. Add auth context helper module.
3. Wire HTTP request token extraction for all MCP HTTP request types.
4. Wire optional refresh-token extraction.
5. Update `data_source.py` to consume the new resolution flow.
6. Add config flags.
7. Add tests.
8. Update README examples.

## Why This Plan Fits Your Use Case

Your microservice already performs authentication and then calls this MCP server on every request with bearer auth, and possibly refresh token metadata. You also clarified that the MCP server cannot trust where requests come from, and that the inbound access token is already trusted by OpenEMR itself. Because of that, the MCP server should act as a zero-trust, request-scoped downstream OpenEMR API proxy that forwards the same OpenEMR-valid token, not as the primary credential owner. The safest long-term design is to require auth on every request, derive user context only from that request's token, forward that same token to OpenEMR APIs, and fail closed when request auth is absent or invalid.
