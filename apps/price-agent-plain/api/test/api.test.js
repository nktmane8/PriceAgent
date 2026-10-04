import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { createApp } from '../src/app.js';
import { openDb } from '../src/db.js';
import { seedIfEmpty } from '../src/seed.js';

let server, base, db;
const ADMIN = { 'x-admin-key': 'adm' }, INGEST = { 'x-ingest-key': 'ing' };
const j = (path, opts = {}) => fetch(base + path, { ...opts, headers: { 'content-type': 'application/json', ...(opts.headers || {}) },
  body: opts.body ? JSON.stringify(opts.body) : undefined }).then(async (r) => ({ status: r.status, body: await r.json().catch(() => null), headers: r.headers }));

before(async () => {
  db = openDb(':memory:');
  seedIfEmpty(db);
  const app = createApp(db, { adminKey: 'adm', ingestKey: 'ing', communityLimit: 3 });
  server = app.listen(0);
  base = `http://127.0.0.1:${server.address().port}`;
});
after(() => server.close());

test('health, security headers, unknown api route', async () => {
  const h = await j('/api/health');
  assert.equal(h.status, 200);
  assert.match(h.headers.get('content-security-policy'), /default-src 'self'/);
  assert.equal((await j('/api/nope')).status, 404);
});

test('compare ranks by effective price, filters region, flags stock and labels data', async () => {
  const p = (await j('/api/products?q=phone x')).body[0];
  const r = (await j(`/api/compare?productId=${p.id}&country=India&city=Pune`)).body;
  assert.equal(r.currency, 'INR');
  const prices = r.offers.map((o) => o.effectivePrice);
  assert.deepEqual(prices, [...prices].sort((a, b) => a - b));
  assert.ok(r.offers.some((o) => o.storeType === 'local' && o.city === 'Pune'));
  assert.equal(r.offers.find((o) => o.store.includes('Marketplace')).effectivePrice, 29000);   // 30000 - 1000 instant discount
  assert.ok(r.offers.every((o) => o.verified === true));                                         // seed source is admin
  assert.equal(r.best.inStock, true);
  const other = (await j(`/api/compare?productId=${p.id}&country=France`)).body;
  assert.equal(other.offers.length, 0);                                                          // no French stores
  assert.equal((await j('/api/compare?productId=abc')).status, 404);
});

test('stale offers are flagged', async () => {
  db.prepare("INSERT INTO products(name) VALUES('Old Item')").run();
  const pid = db.prepare("SELECT id FROM products WHERE name='Old Item'").get().id;
  const sid = db.prepare('SELECT id FROM stores LIMIT 1').get().id;
  db.prepare("INSERT INTO offers(product_id,store_id,price,currency,source,observed_at) VALUES(?,?,100,'INR','admin',?)").run(pid, sid, Date.now() - 20 * 86400000);
  assert.equal((await j(`/api/compare?productId=${pid}`)).body.offers[0].stale, true);
});

test('history returns daily lows', async () => {
  const p = (await j('/api/products?q=phone x')).body[0];
  const h = (await j(`/api/history?productId=${p.id}&days=90`)).body.days;
  assert.ok(h.length >= 4 && h.every((d) => d.low > 0));
});

test('admin endpoints need the key and validate input', async () => {
  const store = { name: 'Test Shop', type: 'local', country: 'India', city: 'Pune' };
  assert.equal((await j('/api/stores', { method: 'POST', body: store })).status, 401);
  assert.equal((await j('/api/stores', { method: 'POST', body: { ...store, type: 'nope' }, headers: ADMIN })).status, 422);
  assert.equal((await j('/api/stores', { method: 'POST', body: store, headers: ADMIN })).status, 201);
  assert.equal((await j('/api/stores', { method: 'POST', body: store, headers: ADMIN })).status, 422);   // duplicate
});

test('community offers: validated, labelled, sanity-checked and rate limited', async () => {
  const p = (await j('/api/products?q=phone x')).body[0];
  const s = (await j('/api/stores?country=India')).body[0];
  const ok = await j('/api/offers', { method: 'POST', body: { productId: p.id, storeId: s.id, price: 30100, currency: 'INR' } });
  assert.equal(ok.status, 201);
  const labelled = (await j(`/api/compare?productId=${p.id}`)).body.offers.find((o) => o.source === 'community');
  assert.equal(labelled.verified, false);
  const noNote = await j('/api/offers', { method: 'POST', body: { productId: p.id, storeId: s.id, price: 30000, currency: 'INR', instantDiscount: 500 } });
  assert.match(noNote.body.error, /discountNote/);                                                    // unexplained discounts rejected
  assert.equal((await j('/api/offers', { method: 'POST', body: { productId: p.id, storeId: s.id, price: 5, currency: 'INR' } })).status, 422);  // far from median
  assert.equal((await j('/api/offers', { method: 'POST', body: { productId: p.id, storeId: s.id, price: 100, currency: 'inr' } })).status, 429);  // 4th request hits the limit of 3
});

test('ingest needs key, validates, and is all-or-nothing', async () => {
  const item = { product: 'Ingested Gadget 1', store: 'Ingest Shop', storeType: 'marketplace', country: 'India', price: 500, currency: 'INR', url: 'https://shop.example/g1' };
  assert.equal((await j('/api/ingest', { method: 'POST', body: { items: [item] } })).status, 401);
  const bad = await j('/api/ingest', { method: 'POST', body: { items: [item, { ...item, price: -1 }] }, headers: INGEST });
  assert.equal(bad.status, 422);
  assert.equal((await j('/api/products?q=Ingested')).body.length, 0);                                  // nothing saved from the bad batch
  assert.equal((await j('/api/ingest', { method: 'POST', body: { items: [item] }, headers: INGEST })).status, 201);
  assert.equal((await j('/api/products?q=Ingested')).body.length, 1);
  assert.equal((await j('/api/ingest', { method: 'POST', body: { items: [{ ...item, url: 'javascript:alert(1)' }] }, headers: INGEST })).status, 422);
});

test('malformed JSON gives 400, not a crash', async () => {
  const r = await fetch(base + '/api/offers', { method: 'POST', headers: { 'content-type': 'application/json' }, body: '{oops' });
  assert.equal(r.status, 400);
});
