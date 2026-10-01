# Publishing the agent so other AI apps can use it

The web page is for people. Other AI apps need a machine interface. This project exposes three:

| Interface | File / URL | Used by |
|---|---|---|
| REST + OpenAPI | `POST /api/v1/compare`, schema at `/openapi.json` | Custom GPT Actions, any HTTP client, RapidAPI-style marketplaces |
| MCP server (stdio) | `python mcp_server.py` | Claude Desktop, Claude Code, Cursor, other MCP clients (local) |
| Remote MCP + OAuth | `https://your-app/mcp` (built in) | Claude connectors, ChatGPT apps, registries, any MCP client |

## Step 0 - Prepare (do this before any portal)
1. Deploy the app on Render (see README) over HTTPS.
2. Set env vars: `ANTHROPIC_API_KEY`, `PUBLIC_URL` (exact https URL; it is the OAuth issuer), `NOMINATIM_CONTACT`, optional `API_KEYS` for partners.
3. Set an Anthropic monthly spend limit. A public listing can send traffic you did not plan for.
4. Write a privacy policy and terms (location is personal data) and a support email. Every directory asks for them.
5. Latency is handled: sync calls return a `job_id` after ~50 s and clients poll.

## A. Use it locally in Claude Desktop / Cursor (no review needed)
```bash
pip install -r requirements.txt
```
Add to the client's MCP config:
```json
{"mcpServers": {"price-agent": {"command": "python", "args": ["/path/to/mcp_server.py"],
  "env": {"PRICE_AGENT_URL": "https://your-app.onrender.com", "PRICE_AGENT_API_KEY": "your-key"}}}}
```

## B. Custom GPT (ChatGPT Actions) via OpenAPI
1. Set `PUBLIC_URL`, redeploy, and open `https://your-app/openapi.json`.
2. In ChatGPT: create a GPT > Configure > Actions > import the schema URL.
3. Authentication: API Key, custom header `X-API-Key`.
4. Test with "cheapest iPhone 15 128GB in Pune". Check current Actions limits (timeouts, schema size) in OpenAI's docs.

## C. Official MCP Registry (discovery for MCP clients)
The registry stores metadata only; it points to a package or a remote URL.
1. The registry accepts a remote URL: use `https://your-app/mcp` (or a PyPI package for the stdio script).
2. Install the CLI (`brew install mcp-publisher`, or download from the registry's GitHub releases).
3. `mcp-publisher init` (creates `server.json`), then `mcp-publisher login github`.
4. For a `io.github.<you>/...` name, GitHub login proves ownership; for your own domain, add the DNS/HTTP proof it asks for.
5. `mcp-publisher publish`. The registry is in preview, so details can change.

## D. Claude Connectors Directory
- Accepts remote MCP servers (submitted in the Claude.ai admin portal; by default org Owners manage listings), desktop extensions (MCPB) and MCP Apps.
- Expect: public HTTPS endpoint, Origin-header validation, tool annotations (this project sets `readOnlyHint`), OAuth for authenticated servers (callback `https://claude.ai/api/mcp/auth_callback`), privacy policy, docs, test access, support contact.
- **Already built:** OAuth 2.1 + PKCE + dynamic client registration, Origin/Host validation, read-only annotations, HTTPS via Render. To try it before submitting: Claude Settings > Connectors > add a custom connector with `https://your-app/mcp`.
- **Still needed:** privacy policy URL (`docs/PRIVACY.md` is a draft), support contact, test account for reviewers, logo, and a security review of the hand-written OAuth.

## E. ChatGPT Apps Directory
- Built on MCP. Needs a verified OpenAI Platform organization (Owner role), a public MCP server, a CSP if you ship UI, tool annotations, a domain-verification token served at `/.well-known/openai-apps-challenge`, test cases and screenshots, and a review.
- OAuth and MCP are in place; you still need the verification token file, annotations review, test cases and screenshots. Check OpenAI's current submission guidelines before building; commerce rules apply.

## F. Other places
Community MCP directories (e.g. Smithery, Glama, PulseMCP), GitHub topic `mcp-server`, and API marketplaces such as RapidAPI (wrap `/api/v1/compare`, they handle keys and billing).

## What is not done in this project
Email verification and password reset, account deletion, per-partner billing, usage dashboards, a hardened/audited OAuth. See `docs/SECURITY.md`. Directory rules change often; follow each portal's current docs.
