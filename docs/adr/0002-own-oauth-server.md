# ADR 0002: Own OAuth 2.1 server
- Status: accepted
- Date: 2026-10-01
## Context
AI clients (Claude, ChatGPT) need OAuth with PKCE and dynamic client registration to connect.
## Decision
Implement a minimal authorization server in `oauth.py` with email + password accounts.
## Consequences
Self-contained and tested, but it is security-sensitive code without email verification or password reset. Alternative: delegate to an identity provider. Needs external review (TODO #3).
