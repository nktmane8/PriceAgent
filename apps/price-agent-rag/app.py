"""AI + RAG product assistant: FastAPI app. Ask questions, answers come only from the indexed sources, with citations."""
import hmac
import time
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from ragapp import answer, config, ingest, retrieve, store

app = FastAPI(title="Price Agent RAG")
Type = Literal["publication", "video", "user", "specs", "price", "other"]


def db():
    c = store.connect()
    try:
        yield c
    finally:
        c.close()


def admin(x_admin_key: str | None = Header(default=None)):
    """Ingest and delete are admin-only (they fetch URLs and change the knowledge base)."""
    if not config.ADMIN_KEY or not x_admin_key or not hmac.compare_digest(x_admin_key, config.ADMIN_KEY):
        raise HTTPException(401, "Admin key required (set ADMIN_KEY and send X-Admin-Key).")


def limited(c, request: Request):
    """Per-IP hourly limit stored in SQLite so it survives restarts."""
    who = (request.headers.get("x-forwarded-for", "").split(",")[0].strip()) or (request.client.host if request.client else "?")
    now = time.time()
    n = c.execute("SELECT COUNT(*) FROM usage WHERE who=? AND ts>?", (who, now - 3600)).fetchone()[0]
    if n >= config.ASK_RATE_LIMIT:
        raise HTTPException(429, "Hourly question limit reached. Try again later.")
    c.execute("INSERT INTO usage(who, ts) VALUES(?,?)", (who, now))
    c.execute("DELETE FROM usage WHERE ts<?", (now - 86400,))
    c.commit()


class Meta(BaseModel):
    product: str = Field("", max_length=120)
    country: str = Field("", max_length=60)
    source_type: Type = "other"
    published: str = Field("", max_length=30)


class TextIn(Meta):
    title: str = Field(..., min_length=1, max_length=200)
    text: str = Field(..., min_length=20, max_length=200_000)
    url: str = Field("", max_length=500, pattern=r"^(https?://.*)?$")


class UrlIn(Meta):
    url: str = Field(..., max_length=500)


class RssIn(UrlIn):
    limit: int = Field(20, ge=1, le=50)


class PriceRow(BaseModel):
    product: str = Field(..., min_length=2, max_length=120)
    store: str = Field(..., min_length=1, max_length=80)
    price: float = Field(..., gt=0, lt=1e9)
    currency: str = Field(..., pattern=r"^[A-Z]{3}$")
    date: str = Field("", max_length=30)


class PricesIn(BaseModel):
    country: str = Field("", max_length=60)
    rows: list[PriceRow] = Field(..., min_length=1, max_length=500)


class AskIn(BaseModel):
    question: str = Field(..., min_length=3, max_length=500)
    product: str = Field("", max_length=120)
    country: str = Field("", max_length=60)


def meta(m: Meta):
    return {"product": m.product, "country": m.country, "source_type": m.source_type, "published": m.published}


@app.post("/api/ingest/text", dependencies=[Depends(admin)])
def ingest_text(b: TextIn, c=Depends(db)):
    doc_id, n, created = ingest.add_text(c, b.title, b.text, {**meta(b), "url": b.url})
    return {"doc_id": doc_id, "chunks": n, "created": created}


@app.post("/api/ingest/url", dependencies=[Depends(admin)])
def ingest_url(b: UrlIn, c=Depends(db)):
    try:
        doc_id, n, created = ingest.add_url(c, b.url, meta(b))
    except (ingest.FetchError, ValueError) as e:
        raise HTTPException(422, str(e))
    return {"doc_id": doc_id, "chunks": n, "created": created}


@app.post("/api/ingest/rss", dependencies=[Depends(admin)])
def ingest_rss(b: RssIn, c=Depends(db)):
    try:
        return {"documents_added": ingest.add_rss(c, b.url, meta(b), b.limit)}
    except (ingest.FetchError, ValueError, Exception) as e:
        raise HTTPException(422, f"Could not read feed: {e}")


@app.post("/api/ingest/prices", dependencies=[Depends(admin)])
def ingest_prices(b: PricesIn, c=Depends(db)):
    """Price rows become text documents, so questions like 'who lists it cheapest?' can be answered with citations."""
    by = {}
    for r in b.rows:
        by.setdefault(r.product, []).append(f"On {r.date or 'an unknown date'}, {r.store} listed {r.product} at {r.currency} {r.price:,.2f}.")
    for product, lines in by.items():
        ingest.add_text(c, f"Price observations: {product}", " ".join(lines),
                        {"product": product, "country": b.country, "source_type": "price"})
    return {"products": len(by), "rows": len(b.rows)}


@app.get("/api/documents")
def documents(c=Depends(db)):
    return store.list_documents(c)


@app.delete("/api/documents/{doc_id}", dependencies=[Depends(admin)])
def delete_document(doc_id: int, c=Depends(db)):
    if not store.delete_document(c, doc_id):
        raise HTTPException(404, "Unknown document.")
    return {"deleted": doc_id}


@app.get("/api/search")
def search(request: Request, q: str = Query(..., min_length=2, max_length=300), product: str = "", country: str = "",
           k: int = Query(config.TOP_K, ge=1, le=20), c=Depends(db)):
    limited(c, request)
    return retrieve.search(c, q, k, product or None, country or None)


@app.post("/api/ask")
def ask(b: AskIn, request: Request, c=Depends(db)):
    limited(c, request)
    return answer.ask(c, b.question, b.product or None, b.country or None, config.TOP_K)


@app.get("/api/health")
def health():
    from ragapp import llm
    return {"status": "ok", "env": config.APP_ENV, "llm": llm.enabled(), "embeddings": llm.embeddings_enabled()}


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(Path(__file__).parent / "static" / "index.html")
