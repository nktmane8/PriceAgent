# Price Agent (AI + RAG): answers only from your sources, free to run

Ask questions such as "Is the battery good on Phone X?" or "Which store lists it cheapest?". The app retrieves the most relevant passages from a knowledge base **you** build (reviews, specs, articles, price rows), gives them to a language model, and returns an answer with citations. If the sources do not contain the answer, it says so instead of guessing.

## How RAG works here
```
ingest (text | URL | RSS | price rows) -> chunk (120 words, 20 overlap) -> SQLite: chunks + FTS5 index (+ optional embeddings)
question -> retrieve: BM25 keyword search (+ vector search if embeddings enabled) -> Reciprocal Rank Fusion -> top 5 chunks
         -> prompt: "answer ONLY from the numbered sources, cite [n]" -> LLM
         -> validate: keep only real citations; no valid citation = discard the model text and show the passages instead
```
| Step | File | Notes |
|---|---|---|
| Chunking | `ragapp/chunk.py` | Overlapping word windows |
| Storage and keyword index | `ragapp/store.py` | SQLite + FTS5 (built in, BM25 ranking) |
| Retrieval | `ragapp/retrieve.py` | Hybrid: BM25 + cosine vectors, fused with RRF; filters by product and country |
| Generation | `ragapp/llm.py`, `answer.py` | Any OpenAI-compatible server; guardrails and fallbacks |
| Ingestion | `ragapp/ingest.py` | Text, price rows, RSS/Atom, web pages (SSRF-safe, robots.txt) |
| API and page | `app.py`, `static/index.html` | FastAPI, admin key for ingest |

## Cost: Rs 0 and no paid key
- **No model at all** (`LLM_PROVIDER=none`, default): retrieval still works and the app shows the best matching passages with citations.
- **Free local model:** install Ollama, run `ollama pull llama3.2:3b`, set `LLM_PROVIDER=openai_compatible` (the default base URL `http://localhost:11434/v1` is Ollama's). Small models need a few GB of RAM and give simpler answers than big hosted ones. Add `EMBED_MODEL` (for example `nomic-embed-text`, pulled the same way) to turn on vector search.
- **Hosted free tiers:** any OpenAI-compatible endpoint works through `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`. I did not verify any provider's free limits; they change often.

## Run
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export ADMIN_KEY="a-long-random-string"           # enables ingest/delete
uvicorn app:app --reload                          # http://127.0.0.1:8000
```
Add knowledge (admin) and ask:
```bash
curl -X POST localhost:8000/api/ingest/text -H "X-Admin-Key: $ADMIN_KEY" -H "Content-Type: application/json" \
  -d '{"title":"Phone X review","text":"The battery lasts two days...","product":"Phone X","country":"India","source_type":"publication","url":"https://paper.example/x"}'
curl -X POST localhost:8000/api/ingest/rss -H "X-Admin-Key: $ADMIN_KEY" -H "Content-Type: application/json" -d '{"url":"https://site.example/feed.xml","product":"Phone X"}'
curl -X POST localhost:8000/api/ask -H "Content-Type: application/json" -d '{"question":"How is the battery?","product":"Phone X"}'
```
Settings: `env/.env.<APP_ENV>`, `.env.example`; real environment variables win.

## API
`POST /api/ask` · `GET /api/search?q=` · `GET /api/documents` · `POST /api/ingest/{text,url,rss,prices}` (admin) · `DELETE /api/documents/{id}` (admin) · `GET /api/health`. Questions are limited per IP per hour (`ASK_RATE_LIMIT`).

## Safety and honesty built in
- Never answers when nothing was retrieved (the model is not even called). Citations the model invents are removed; an answer with no valid citation is discarded.
- Sources are treated as data: the prompt tells the model to ignore instructions inside them (not a guarantee against prompt injection).
- URL ingestion blocks private, loopback and cloud-metadata addresses, non-80/443 ports and redirects, caps size and respects robots.txt. Residual risk: DNS rebinding between check and fetch.
- Ingest and delete need `ADMIN_KEY`; the knowledge base is only as trustworthy as what you put in. The app cannot tell whether a review is genuine.

## Tests
`pip install -r requirements-dev.txt && python -m pytest -q tests` (10 offline tests; the model and embeddings are faked).

## Limits
Pure-Python vector search is for up to a few thousand chunks. Small local models can still misread sources, which is why citations and fallbacks exist. No live web search: knowledge is what you ingest. No accounts. Single process.
