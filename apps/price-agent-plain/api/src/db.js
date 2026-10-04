// Opens SQLite (built into Node 22: node:sqlite, no native modules, no cost) and applies the shared schema.
import { DatabaseSync } from 'node:sqlite';
import { mkdirSync, readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const SCHEMA = resolve(dirname(fileURLToPath(import.meta.url)), '../../sql/schema.sql');

export function openDb(path = process.env.DATABASE_PATH || 'data/plain.db') {
  if (path !== ':memory:') mkdirSync(dirname(path), { recursive: true });
  const db = new DatabaseSync(path);
  db.exec('PRAGMA foreign_keys = ON; PRAGMA journal_mode = WAL;');
  db.exec(readFileSync(SCHEMA, 'utf8'));
  return db;
}
