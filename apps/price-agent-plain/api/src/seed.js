// Loads DEMO data (clearly fake names) so the UI works on first run. Real data comes from the collector or community reports.
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { openDb } from './db.js';
import { upsertItems } from './repo.js';

export function seedIfEmpty(db) {
  if (db.prepare('SELECT COUNT(*) AS n FROM products').get().n > 0) return 0;
  const file = resolve(dirname(fileURLToPath(import.meta.url)), '../data/seed.json');
  const day = 86400000;
  const items = JSON.parse(readFileSync(file, 'utf8')).items.map((i) => ({ ...i, observedAt: Date.now() - (i.daysAgo || 0) * day }));
  return upsertItems(db, items, 'admin');
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const db = openDb();
  console.log(`seeded ${seedIfEmpty(db)} demo offers`);
}
