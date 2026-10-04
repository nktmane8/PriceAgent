import { createApp } from './app.js';
import { openDb } from './db.js';
import { seedIfEmpty } from './seed.js';

const db = openDb();
if (process.env.SEED_ON_EMPTY !== 'false') console.log(`seeded ${seedIfEmpty(db)} demo offers (set SEED_ON_EMPTY=false in production)`);
const app = createApp(db, { adminKey: process.env.ADMIN_KEY || '', ingestKey: process.env.INGEST_KEY || '' });
const port = Number(process.env.PORT) || 3000;
app.listen(port, () => console.log(`API and web on http://localhost:${port}`));
