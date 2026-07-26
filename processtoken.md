# Processing token

The token provided to the mcp server for the function call are of the
for mat given below.
{
  "sub": "3d4a93a8-552f-4097-b0f1-5747a47d58d9",
  "nbf": 1784732100,
  "original_jti": "eyJhbGciOiJSUzI1NiIsInR5cCIgOiAiSldUIiwia2lkIiA6ICJ5Vl9lSDA0UTdRVFljSUhEYkhYU1E0RG1YUVdhTFZGaHZfeXpJc1hRMzFnIn0.eyJleHAiOjE3ODQ3MzMwMDAsImlhdCI6MTc4NDczMjEwMCwianRpIjoiM2M1ZmY5MmYtM2U1ZS1kNmQzLTNiZWItYjVlOGI4NDA2OTBjIiwiaXNzIjoiaHR0cDovL2xvY2FsaG9zdDo4MDAyL3JlYWxtcy9haV9nYXRld2F5IiwiYXVkIjoiYWlfZ2F0ZXdheV9jbGllbnQiLCJzdWIiOiIzZDRhOTNhOC01NTJmLTQwOTctYjBmMS01NzQ3YTQ3ZDU4ZDkiLCJ0eXAiOiJJRCIsImF6cCI6ImFpX2dhdGV3YXlfY2xpZW50Iiwic2lkIjoiX0x6bU5iU0lrb1p2ZjFKZTA1cDNUb0xKIiwiYXRfaGFzaCI6InBQTTg2cUN0VVBZeVE3aE5oaGtPdVEiLCJhY3IiOiIxIiwidXBuIjoiYWFhIiwiZW1haWxfdmVyaWZpZWQiOmZhbHNlLCJuYW1lIjoiYWFhIGFhYSIsImdyb3VwcyI6WyJvZmZsaW5lX2FjY2VzcyIsImRlZmF1bHQtcm9sZXMtYWlfZ2F0ZXdheSIsInVtYV9hdXRob3JpemF0aW9uIl0sInByZWZlcnJlZF91c2VybmFtZSI6ImFhYSIsImdpdmVuX25hbWUiOiJhYWEiLCJmYW1pbHlfbmFtZSI6ImFhYSIsImVtYWlsIjoiYWFhQGFhYS5jb20ifQ.TLKYPRZEAWl_A5MghZPeJ3IWySAiiyGMzwJzVJIURI9m0gLpOVF3q2BQcZKhy5fxbk8ceOD7JQ0KGj2n1tT7-rl2uPIyacQlzGaFlDC5_2hmEw9EpLrd0Re9mwoE1ABzZSmXwgqQ_PqgRBIaeS6LZcUMKJs5iF-y9OEkscqNsJTdVvcplRPRxo7a0b69cSK9BZn2AZ-hW9afXTST4PL_v_kmQwAWPS6B5ji7c3YnXZlRIgOsUes9OzB30d8v4B21SThb_Ch1HdF2zrma6MnDOptbLvtQH3rxks821X45UGKBCMg06Wfk82_e-9fAc48w1HmD_nMvD9-gMHkspkFP_A",
  "roles": [
    "offline_access",
    "default-roles-ai_gateway",
    "uma_authorization",
    "manage-account",
    "manage-account-links",
    "view-profile",
    "PURCHASER",
    "CHAT_USER",
    "ADD_PAYMENT",
    "AGENT_RUN"
  ],
  "iss": "http://localhost:8888",
  "preferred_username": "aaa",
  "exp": 1784733000,
  "iat": 1784732100,
  "Patty": "Thendi",
  "jti": "aa5657f5-b17f-43fd-8115-91e34b12f419",
  "authorities": [
    "ROLE_offline_access",
    "ROLE_default-roles-ai_gateway",
    "ROLE_uma_authorization",
    "ROLE_manage-account",
    "ROLE_manage-account-links",
    "ROLE_view-profile",
    "ROLE_PURCHASER",
    "ROLE_CHAT_USER",
    "ROLE_ADD_PAYMENT",
    "ROLE_AGENT_RUN"
  ],
  "email": "aaa@aaa.com"
}

All the tool call that is going to be made to the openemr server will be
using the toke provided in the original_jti field.

Can you add a supporting funcrtion to extract this token and use it for the 
openemr server call?