// All SQL lives here (repository layer). Routes never build SQL.
export const effective = (price, discount) => Math.round(Math.max(price - (discount || 0), 0) * 100) / 100;

export const listStores = (db, country) =>
  db.prepare('SELECT id, name, type, country, city, website FROM stores WHERE (:c IS NULL OR country = :c COLLATE NOCASE) ORDER BY name')
    .all({ c: country ?? null });

export const regions = (db) => db.prepare('SELECT DISTINCT country, city FROM stores ORDER BY country, city').all();

export function addStore(db, s) {
  const r = db.prepare('INSERT INTO stores(name,type,country,city,website) VALUES(?,?,?,?,?)')
    .run(s.name, s.type, s.country, s.city ?? null, s.website ?? null);
  return Number(r.lastInsertRowid);
}

export const listProducts = (db, q) =>
  db.prepare(`SELECT p.id, p.name, p.brand, p.category, COUNT(o.id) AS offers FROM products p LEFT JOIN offers o ON o.product_id = p.id
              WHERE (:q IS NULL OR instr(lower(p.name), lower(:q)) > 0) GROUP BY p.id ORDER BY offers DESC, p.name LIMIT 20`)
    .all({ q: q || null });

export function addProduct(db, p) {
  const r = db.prepare('INSERT INTO products(name,brand,category) VALUES(?,?,?)').run(p.name, p.brand ?? null, p.category ?? null);
  return Number(r.lastInsertRowid);
}

export const getProduct = (db, id) => db.prepare('SELECT id, name, brand, category FROM products WHERE id = ?').get(id);
export const getStore = (db, id) => db.prepare('SELECT id FROM stores WHERE id = ?').get(id);

export function latestOffers(db, productId, country, city) {
  return db.prepare(`
    SELECT o.id, o.price, o.currency, o.instant_discount AS instantDiscount, o.discount_note AS discountNote, o.in_stock AS inStock,
           o.url, o.source, o.observed_at AS observedAt, s.id AS storeId, s.name AS store, s.type AS storeType, s.country, s.city
    FROM offers o JOIN stores s ON s.id = o.store_id
    WHERE o.product_id = :pid
      AND o.id = (SELECT o2.id FROM offers o2 WHERE o2.product_id = o.product_id AND o2.store_id = o.store_id
                  ORDER BY o2.observed_at DESC, o2.id DESC LIMIT 1)
      AND (:country IS NULL OR s.country = :country COLLATE NOCASE)
      AND (:city IS NULL OR s.city IS NULL OR s.city = :city COLLATE NOCASE)`)
    .all({ pid: productId, country: country ?? null, city: city ?? null });
}

export function insertOffer(db, o) {
  const r = db.prepare(`INSERT INTO offers(product_id,store_id,price,currency,instant_discount,discount_note,in_stock,url,source,observed_at)
                        VALUES(?,?,?,?,?,?,?,?,?,?)`)
    .run(o.productId, o.storeId, o.price, o.currency, o.instantDiscount || 0, o.discountNote ?? null,
      o.inStock == null ? null : (o.inStock ? 1 : 0), o.url || null, o.source, o.observedAt ?? Date.now());
  return Number(r.lastInsertRowid);
}

export function medianPrice(db, productId, currency) {
  const rows = latestOffers(db, productId, null, null).filter((o) => o.currency === currency).map((o) => o.price).sort((a, b) => a - b);
  return rows.length ? rows[Math.floor(rows.length / 2)] : null;
}

export const history = (db, productId, days) =>
  db.prepare(`SELECT date(observed_at / 1000, 'unixepoch') AS day, MIN(max(price - instant_discount, 0)) AS low, currency
              FROM offers WHERE product_id = ? AND observed_at > ? GROUP BY day, currency ORDER BY day`)
    .all(productId, Date.now() - days * 86400000);

// Bulk upsert used by the collector and the seed script. Creates missing stores/products. One transaction: all or nothing.
export function upsertItems(db, items, source) {
  const store = db.prepare('SELECT id FROM stores WHERE name = ?');
  const prod = db.prepare('SELECT id FROM products WHERE name = ?');
  db.exec('BEGIN');
  try {
    for (const it of items) {
      let s = store.get(it.store)?.id;
      if (!s) s = addStore(db, { name: it.store, type: it.storeType || 'marketplace', country: it.country, city: it.city, website: it.website });
      let p = prod.get(it.product)?.id;
      if (!p) p = addProduct(db, { name: it.product, brand: it.brand, category: it.category });
      insertOffer(db, { ...it, productId: p, storeId: s, source });
    }
    db.exec('COMMIT');
  } catch (e) {
    db.exec('ROLLBACK');
    throw e;
  }
  return items.length;
}
