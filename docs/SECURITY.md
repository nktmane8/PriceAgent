# Security and privacy notes

## Controls in place
- Environment files hold no secrets (they are committed); secrets come only from the real environment. Staging/production refuse to start with weak or missing config.
- Secrets only from environment variables; tokens, auth codes and OAuth state stored hashed (SHA-256); passwords with scrypt and per-user salt.
- OAuth: PKCE S256 mandatory, exact redirect-URI matching (loopback port-agnostic), https-only redirects, single-use codes, refresh rotation with reuse detection, audience-bound tokens, login brute-force limits (per IP and per account), `X-Frame-Options: DENY` + CSP on the sign-in page, HTML-escaped output.
- MCP endpoint: Host and Origin validation (DNS-rebinding protection), read-only tool annotations.
- Model output is validated: types, sizes, http(s)-only URLs; the UI uses `textContent`, never `innerHTML`.
- Prompt injection: the system prompt marks page content as data, and output cleaning limits damage. It cannot be eliminated.
- Persisted rate limits per IP, user and key; hard cap on searches per comparison; admin stats behind a key.

## Known gaps (do before real users)
- No email verification or password reset (account deletion exists via API). Add them or delegate sign-in to an identity provider.
- Registration is open (rate limited) and there are no admin tools to revoke clients.
- Auth-code replay does not revoke already issued tokens.
- Single instance; the database file needs backups. IP limits can be bypassed with many IPs.
- This is hand-written OAuth. Have a security review before listing publicly.

## Personal data
| Data | Where | Retention |
|---|---|---|
| Email, password hash | `users` | Until deleted by you |
| Coordinates (rounded ~1 km) | Sent to OpenStreetMap; not stored here | None here |
| Product + region queries | OpenAI API, `jobs` table | Jobs 7 days; check OpenAI data-retention terms |
| IP addresses | `usage` (rate limits) | 24 hours |
| Price history (product, store, price; no user data) | `price_history` | 180 days |

Publish a privacy policy (draft from this table, reviewed by a lawyer) before sharing. India's DPDP Act 2023 and GDPR may apply.
