-- Shared schema (SQLite). Effective price is computed at query time: max(price - instant_discount, 0).
CREATE TABLE IF NOT EXISTS stores(
  id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE,
  type TEXT NOT NULL CHECK(type IN ('marketplace','brand','chain','local')),
  country TEXT NOT NULL, city TEXT, website TEXT);            -- city NULL = online store for the whole country
CREATE TABLE IF NOT EXISTS products(
  id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, brand TEXT, category TEXT);
CREATE TABLE IF NOT EXISTS offers(
  id INTEGER PRIMARY KEY,
  product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  store_id INTEGER NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
  price REAL NOT NULL CHECK(price > 0), currency TEXT NOT NULL,
  instant_discount REAL NOT NULL DEFAULT 0 CHECK(instant_discount >= 0), discount_note TEXT,
  in_stock INTEGER, url TEXT,
  source TEXT NOT NULL CHECK(source IN ('community','collector','admin')),
  observed_at INTEGER NOT NULL);                               -- milliseconds since epoch
CREATE INDEX IF NOT EXISTS ix_offers ON offers(product_id, store_id, observed_at);
