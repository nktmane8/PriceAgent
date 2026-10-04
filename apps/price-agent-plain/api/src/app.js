// Express app factory: routes, auth, rate limits, security headers. Exported for tests (no network needed to build it).
import express from 'express';
import crypto from 'node:crypto';
import { existsSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import * as repo from './repo.js';
import { checkOffer, checkStore, isStr, STORE_TYPES } from './validate.js';

const STALE_MS = 7 * 86400000;
const WEB_DIST = resolve(dirname(fileURLToPath(import.meta.url)), '../../web/dist');

function rateLimit(limit, windowMs = 3600000) {
  const hits = new Map();
  return (req, res, next) => {
    const now = Date.now();
    const recent = (hits.get(req.ip) || []).filter((t) => now - t < windowMs);
    if (recent.length >= limit) return res.status(429).json({ error: 'Too many requests. Try again later.' });
    recent.push(now);
    hits.set(req.ip, recent);
    if (hits.size > 10000) hits.clear();   // crude memory guard
    next();
  };
}

// Constant-time key check. An empty configured key disables the endpoint.
function requireKey(header, expected) {
  const digest = (s) => crypto.createHash('sha256').update(String(s)).digest();
  return (req, res, next) => {
    const given = req.get(header);
    if (!expected || !given || !crypto.timingSafeEqual(digest(given), digest(expected))) {
      return res.status(401).json({ error: `Valid ${header} header required.` });
    }
    next();
  };
}

export function createApp(db, cfg = {}) {
  const c = { adminKey: '', ingestKey: '', communityLimit: 10, ...cfg };
  const app = express();
  app.set('trust proxy', 1);
  app.disable('x-powered-by');
  app.use(express.json({ limit: '1mb' }));
  app.use((req, res, next) => {
    res.set({ 'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'no-referrer',
      'Content-Security-Policy': "default-src 'self'; img-src 'self' data:; frame-ancestors 'none'" });
    next();
  });
  const admin = requireKey('x-admin-key', c.adminKey);
  const ingestKey = requireKey('x-ingest-key', c.ingestKey);
  const bad = (res, msg) => res.status(422).json({ error: msg });
  const optStr = (v) => (typeof v === 'string' && v.trim() ? v.trim() : undefined);

  app.get('/api/health', (req, res) => res.json({ status: 'ok' }));
  app.get('/api/regions', (req, res) => res.json(repo.regions(db)));
  app.get('/api/stores', (req, res) => res.json(repo.listStores(db, optStr(req.query.country))));

  app.post('/api/stores', admin, (req, res) => {
    const err = checkStore(req.body || {});
    if (err) return bad(res, err);
    try { res.status(201).json({ id: repo.addStore(db, req.body) }); }
    catch (e) { if (/UNIQUE/.test(e.message)) return bad(res, 'store already exists'); throw e; }
  });

  app.get('/api/products', (req, res) => res.json(repo.listProducts(db, optStr(req.query.q)?.slice(0, 80))));
  app.post('/api/products', admin, (req, res) => {
    if (!isStr(req.body?.name, 2, 120)) return bad(res, 'product name must be 2-120 characters');
    try { res.status(201).json({ id: repo.addProduct(db, req.body) }); }
    catch (e) { if (/UNIQUE/.test(e.message)) return bad(res, 'product already exists'); throw e; }
  });

  // Compare: latest offer per store, region-filtered, sorted by effective price. Mixed currencies are never ranked together.
  app.get('/api/compare', (req, res) => {
    const pid = Number(req.query.productId);
    const product = Number.isInteger(pid) ? repo.getProduct(db, pid) : null;
    if (!product) return res.status(404).json({ error: 'Unknown product.' });
    const rows = repo.latestOffers(db, pid, optStr(req.query.country), optStr(req.query.city));
    const counts = {};
    rows.forEach((o) => { counts[o.currency] = (counts[o.currency] || 0) + 1; });
    const currency = optStr(req.query.currency) || Object.keys(counts).sort((a, b) => counts[b] - counts[a])[0] || null;
    const now = Date.now();
    const offers = rows.filter((o) => o.currency === currency).map((o) => ({
      ...o, inStock: o.inStock == null ? null : !!o.inStock,
      effectivePrice: repo.effective(o.price, o.instantDiscount),
      verified: o.source !== 'community', stale: now - o.observedAt > STALE_MS,
    })).sort((a, b) => a.effectivePrice - b.effectivePrice);
    res.json({ product, currency, offers, best: offers.find((o) => o.inStock !== false) || null,
      excludedOtherCurrency: rows.length - offers.length });
  });

  app.get('/api/history', (req, res) => {
    const pid = Number(req.query.productId);
    const days = Math.min(Math.max(Number(req.query.days) || 90, 1), 365);
    if (!Number.isInteger(pid) || !repo.getProduct(db, pid)) return res.status(404).json({ error: 'Unknown product.' });
    res.json({ days: repo.history(db, pid, days) });
  });

  // Community-reported price: public but limited, clearly labelled, and rejected if wildly off the median.
  app.post('/api/offers', rateLimit(c.communityLimit), (req, res) => {
    const o = req.body || {};
    const product = repo.getProduct(db, Number(o.productId));
    if (!product || !repo.getStore(db, Number(o.storeId))) return bad(res, 'unknown productId or storeId');
    const err = checkOffer(o);
    if (err) return bad(res, err);
    const med = repo.medianPrice(db, product.id, o.currency);
    if (med && (repo.latestOffers(db, product.id, null, null).length >= 3) && (o.price < med * 0.1 || o.price > med * 10)) {
      return bad(res, 'price is far from other reports for this product; please double-check it');
    }
    const id = repo.insertOffer(db, { ...o, productId: product.id, storeId: Number(o.storeId), source: 'community' });
    res.status(201).json({ id, note: 'Saved as a community report (not verified).' });
  });

  // Bulk ingest for the collector (Python) and import scripts. Needs the ingest key.
  app.post('/api/ingest', ingestKey, (req, res) => {
    const items = req.body?.items;
    if (!Array.isArray(items) || items.length < 1 || items.length > 500) return bad(res, 'items must be an array of 1-500');
    for (const [i, it] of items.entries()) {
      const err = !isStr(it.product, 2, 120) ? 'product required'
        : !isStr(it.store, 2, 80) ? 'store required'
        : !isStr(it.country, 2, 60) ? 'country required'
        : it.storeType != null && !STORE_TYPES.includes(it.storeType) ? 'bad storeType'
        : checkOffer(it);
      if (err) return bad(res, `item ${i}: ${err}`);
    }
    res.status(201).json({ ingested: repo.upsertItems(db, items.map((i) => ({ ...i, product: i.product.trim(), store: i.store.trim() })), 'collector') });
  });

  if (existsSync(WEB_DIST)) {            // serve the built React app from the same process
    app.use(express.static(WEB_DIST));
    app.get(/^(?!\/api\/).*/, (req, res) => res.sendFile(resolve(WEB_DIST, 'index.html')));
  }
  app.use('/api', (req, res) => res.status(404).json({ error: 'Not found.' }));
  app.use((err, req, res, next) => {      // malformed JSON etc.
    if (err.type === 'entity.parse.failed') return res.status(400).json({ error: 'Invalid JSON.' });
    console.error(err);
    res.status(500).json({ error: 'Server error.' });
  });
  return app;
}
