"""Privacy-conscious analytics ledger used by the in-app dashboard."""
import hashlib
import time

import db

ALLOWED_EVENTS = {
    "search", "comparison_complete", "comparison_error", "insight_view",
    "buy_click", "similar_product_click", "local_store_click",
    "youtube_review_click", "rating_source_click", "review_source_click",
}

def _anon(value: str | None) -> str | None:
    if not value:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:32]

def record(name: str, *, client_id: str | None = None, user_id: str | None = None,
           product: str | None = None, store: str | None = None, metadata: dict | None = None) -> None:
    if name not in ALLOWED_EVENTS:
        return
    try:
        db.analytics_event_create(
            name, _anon(client_id), _anon(user_id),
            (product or "").strip()[:120] or None,
            (store or "").strip()[:120] or None,
            metadata or {}, time.time(),
        )
    except Exception:
        return

def dashboard(days: int = 30) -> dict:
    return db.analytics_dashboard(max(1, min(days, 90)))
