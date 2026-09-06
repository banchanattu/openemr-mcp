Here is a developer-focused spec you can hand directly to your OpenEMR MCP server engineering team to implement Card and Catalog support for Agent-Ready / Agent-Direct (ARD) discovery.

Technical Specification: ARD & Catalog Discovery Endpoint for openemr-mcp
Target System: openemr-mcp Service

Objective: Expose standardized .well-known discovery cards to enable ARD (Agent-Ready / Agent-Direct) discovery, automated registry cataloging, and pre-handshake capabilities checks.

1. Functional Requirements
Expose the MCP Server Card at /.well-known/mcp.json.

Support legacy/fallback path at /.well-known/mcp/server-card.json (301 redirect to /.well-known/mcp.json).

Maintain CORS, cache control, and RFC compliance for all .well-known endpoints.

Integrate with OpenEMR OAuth 2.0 / OIDC infrastructure for protected resource discovery.

2. Endpoint Implementation
Primary Route
GET /.well-known/mcp.json

Secondary / Legacy Route
GET /.well-known/mcp/server-card.json

Behavior: Issue HTTP 301 redirect to /.well-known/mcp.json.

HTTP Headers Requirements
Content-Type: application/json

Access-Control-Allow-Origin: * (or target Gateway origin)

Access-Control-Allow-Methods: GET, OPTIONS

Access-Control-Allow-Headers: Content-Type, Authorization

Cache-Control: public, max-age=3600

X-Content-Type-Options: nosniff

3. Server Card Schema (/.well-known/mcp.json)
Ensure the endpoint serves the following payload (adjust hostnames dynamically based on environment configuration):

JSON
{
  "$schema": "https://static.modelcontextprotocol.io/schemas/2025-10-17/server.schema.json",
  "name": "openemr-mcp-server",
  "title": "OpenEMR Healthcare MCP Server",
  "version": "1.0.0",
  "description": "Provides secure Model Context Protocol access to OpenEMR EHR data, FHIR/REST primitives, patient lookup, and appointment scheduling.",
  "icon": "https://<your-openemr-domain>/public/images/openemr-icon.png",
  "vendor": {
    "name": "OpenEMR Community / Internal Tech Team",
    "url": "https://<your-openemr-domain>"
  },
  "remotes": [
    {
      "type": "streamable-http",
      "url": "https://<your-openemr-domain>/mcp"
    },
    {
      "type": "sse",
      "url": "https://<your-openemr-domain>/mcp/sse"
    }
  ],
  "capabilities": {
    "tools": { "listChanged": true },
    "resources": { "subscribe": false, "listChanged": true },
    "prompts": { "listChanged": false }
  },
  "authentication": {
    "required": true,
    "type": "oauth2",
    "authorizationServer": "https://<your-openemr-domain>/oauth2/default",
    "scopes": [
      "openid",
      "fhirUser",
      "patient/*.read"
    ]
  }
}
4. Complementary OAuth Protected Resource Metadata
To allow ARD clients and AI Gateways to automatically configure token exchange, also expose RFC 9728 metadata at:

GET /.well-known/oauth-protected-resource

JSON
{
  "resource": "https://<your-openemr-domain>/mcp",
  "authorization_servers": [
    "https://<your-openemr-domain>/oauth2/default"
  ],
  "scopes_supported": [
    "openid",
    "fhirUser",
    "patient/*.read"
  ],
  "bearer_methods_supported": [
    "header"
  ]
}
5. Acceptance & Testing Criteria
Unauthenticated Access: Verify that issuing a GET request to /.well-known/mcp.json returns HTTP 200 without requiring an OAuth Bearer token.

CORS Verification: Verify OPTIONS /.well-known/mcp.json returns appropriate pre-flight headers.

Redirect Verification: Confirm GET /.well-known/mcp/server-card.json returns 301 Moved Permanently pointing to /.well-known/mcp.json.

Validation: Validate the JSON against the official schema at [https://static.modelcontextprotocol.io/schemas/2025-10-17/server.schema.json](https://static.modelcontextprotocol.io/schemas/2025-10-17/server.schema.json)
