"""Post-deploy smoke test: proves the app, OAuth discovery and the MCP endpoint are reachable.

  python tools/smoke.py https://priceagent.onrender.com            # free checks only
  python tools/smoke.py https://priceagent.onrender.com --key KEY  # also one real comparison (costs searches)
Exit code 0 = all checks passed. Uses only the standard library.
"""
import json
import sys
import urllib.error
import urllib.request

TIMEOUT = 90  # Render free/standard instances can take a while to wake up


def call(method, url, body=None, headers=None):
    """Return (status, headers, text) without raising on HTTP errors."""
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None,
                                 method=method, headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.status, dict(r.headers), r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read().decode()


def main(argv):
    """Run the checks; print PASS/FAIL per line."""
    base = argv[1].rstrip("/") if len(argv) > 1 else "http://127.0.0.1:8000"
    key = argv[argv.index("--key") + 1] if "--key" in argv else ""
    failed = 0

    def check(name, ok, detail=""):
        nonlocal failed
        failed += 0 if ok else 1
        print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail else ""))

    s, _, t = call("GET", base + "/healthz")
    check("healthz returns ok (app + database)", s == 200 and '"ok"' in t, f"HTTP {s}")
    s, _, t = call("GET", base + "/.well-known/oauth-authorization-server")
    meta = json.loads(t) if s == 200 else {}
    check("OAuth server metadata", s == 200 and meta.get("issuer", "").rstrip("/") == base, f"HTTP {s}, issuer={meta.get('issuer')}")
    s, _, t = call("GET", base + "/.well-known/oauth-protected-resource")
    check("OAuth protected-resource metadata", s == 200, f"HTTP {s}")
    s, h, _ = call("POST", base + "/mcp", {"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
                   {"Accept": "application/json, text/event-stream"})
    check("/mcp rejects anonymous calls with 401 + WWW-Authenticate (endpoint is alive)",
          s == 401 and "www-authenticate" in {k.lower() for k in h}, f"HTTP {s}")
    if key:
        s, _, t = call("POST", base + "/api/v1/compare", {"product": "iPhone 15 128GB Black", "country": "India"}, {"X-API-Key": key})
        ok = s in (200, 202)
        detail = f"HTTP {s}"
        if s == 200:
            data = json.loads(t)
            res = (data.get("result") or data).get("results", [])
            ok = bool(res)
            detail += f", {len(res)} store results"
        check("real comparison returns store records (OpenAI + web search path)", ok, detail + ("" if ok else f" body={t[:200]}"))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
