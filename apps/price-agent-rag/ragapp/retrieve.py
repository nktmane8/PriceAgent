"""Hybrid retrieval: BM25 keyword search (SQLite FTS5) + optional dense vectors, merged with Reciprocal Rank Fusion."""
import json
import math
import re

from . import llm

STOP = {"the", "a", "an", "and", "or", "of", "to", "is", "in", "on", "for", "with", "it", "this", "that", "are", "be", "i", "my",
        "what", "which", "why", "how", "should", "buy", "does", "do"}
RRF_K = 60


def fts_query(q: str) -> str:
    """Make a safe FTS5 query: quoted words joined by OR (user text can never inject FTS syntax)."""
    toks = [t for t in re.findall(r"\w+", q.lower()) if len(t) > 1 and t not in STOP]
    return " OR ".join(f'"{t}"' for t in dict.fromkeys(toks))


def _filters(product, country):
    sql, args = "", []
    if product:
        sql += " AND instr(lower(d.product), ?) > 0"
        args.append(product.lower())
    if country:
        sql += " AND lower(d.country) = ?"
        args.append(country.lower())
    return sql, args


COLS = "c.id, c.text, c.embedding, d.title, d.url, d.source_type, d.published"


def bm25(c, query, k, product=None, country=None):
    fq = fts_query(query)
    if not fq:
        return []
    f, args = _filters(product, country)
    rows = c.execute(f"SELECT {COLS} FROM chunks_fts JOIN chunks c ON c.id = chunks_fts.rowid JOIN docs d ON d.id = c.doc_id "
                     f"WHERE chunks_fts MATCH ?{f} ORDER BY bm25(chunks_fts) LIMIT ?", [fq, *args, k]).fetchall()
    return [dict(r) for r in rows]


def cosine(a, b):
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(x * x for x in b))
    return sum(x * y for x, y in zip(a, b)) / (na * nb) if na and nb else 0.0


def dense(c, query, k, product=None, country=None):
    """Brute-force cosine over stored vectors: fine up to a few thousand chunks (pure Python, zero cost)."""
    if not llm.embeddings_enabled():
        return []
    qv = llm.embed([query])[0]
    f, args = _filters(product, country)
    rows = c.execute(f"SELECT {COLS} FROM chunks c JOIN docs d ON d.id = c.doc_id WHERE c.embedding IS NOT NULL{f}", args).fetchall()
    scored = sorted(((cosine(qv, json.loads(r["embedding"])), dict(r)) for r in rows), key=lambda x: -x[0])
    return [r for s, r in scored[:k] if s > 0]


def search(c, query, k=5, product=None, country=None):
    """Return up to k chunks, best first, with which retrievers found them."""
    lists = {"keyword": bm25(c, query, k * 3, product, country)}
    try:
        lists["vector"] = dense(c, query, k * 3, product, country)
    except llm.LLMError:
        lists["vector"] = []          # embeddings down: keyword search still works
    fused, by_id = {}, {}
    for name, rows in lists.items():
        for rank, r in enumerate(rows):
            fused[r["id"]] = fused.get(r["id"], 0) + 1 / (RRF_K + rank + 1)
            by_id.setdefault(r["id"], {**r, "via": []})["via"].append(name)
    best = sorted(fused, key=fused.get, reverse=True)[:k]
    return [{**{kk: v for kk, v in by_id[i].items() if kk != "embedding"}, "score": round(fused[i], 5)} for i in best]
