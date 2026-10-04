import { useEffect, useState } from 'react';
import { api, money, ago, isHttp, guessCountry } from './api.js';

function Sparkline({ days }) {
  if (days.length < 2) return <p className="muted">Not enough history yet.</p>;
  const w = 300, h = 60, lows = days.map((d) => d.low), min = Math.min(...lows), max = Math.max(...lows);
  const pts = lows.map((v, i) => `${(i / (days.length - 1)) * w},${h - ((v - min) / (max - min || 1)) * (h - 8) - 4}`).join(' ');
  return (
    <svg viewBox={`0 0 ${w} ${h}`} role="img" aria-label="Lowest price per day" className="spark">
      <polyline points={pts} fill="none" stroke="currentColor" strokeWidth="2" />
    </svg>
  );
}

function OfferCard({ o, currency, best }) {
  return (
    <div className={`card${best ? ' best' : ''}`}>
      {best && <div className="muted">Best price in stock</div>}
      <div className="row">
        <span className="store">{o.store}</span>
        <span className="price">{money(o.effectivePrice, currency)}</span>
      </div>
      <div className="muted">{[o.storeType, o.city].filter(Boolean).join(', ')}</div>
      {o.instantDiscount > 0 && <div className="muted">Listed {money(o.price, currency)}, instant discount {money(o.instantDiscount, currency)}: {o.discountNote}</div>}
      <div className="tags">
        {o.inStock === false && <span className="tag bad">Out of stock</span>}
        {!o.verified && <span className="tag">Community report, not verified</span>}
        {o.stale && <span className="tag bad">Older than 7 days</span>}
        <span className="tag">Seen {ago(o.observedAt)}</span>
      </div>
      {isHttp(o.url) && <a className="open" href={o.url} target="_blank" rel="noopener noreferrer">Open product</a>}
    </div>
  );
}

function AddPrice({ product, currency, stores, onSaved }) {
  const [f, setF] = useState({ storeId: '', price: '', discount: '', note: '', url: '' });
  const [msg, setMsg] = useState('');
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  async function submit(e) {
    e.preventDefault();
    try {
      const body = { productId: product.id, storeId: Number(f.storeId), price: Number(f.price), currency: currency || 'INR' };
      if (f.discount) { body.instantDiscount = Number(f.discount); body.discountNote = f.note; }
      if (f.url) body.url = f.url;
      const r = await api('/api/offers', { method: 'POST', body });
      setMsg(r.note); setF({ storeId: '', price: '', discount: '', note: '', url: '' }); onSaved();
    } catch (err) { setMsg(err.message); }
  }
  return (
    <details className="card">
      <summary>Report a price you saw</summary>
      <form onSubmit={submit}>
        <select required value={f.storeId} onChange={set('storeId')}>
          <option value="">Store…</option>
          {stores.map((s) => <option key={s.id} value={s.id}>{s.name}{s.city ? ` (${s.city})` : ''}</option>)}
        </select>
        <input required type="number" min="1" step="any" placeholder="Listed price" value={f.price} onChange={set('price')} />
        <input type="number" min="0" step="any" placeholder="Instant discount (optional)" value={f.discount} onChange={set('discount')} />
        {f.discount && <input required minLength="3" placeholder="Where is the discount shown?" value={f.note} onChange={set('note')} />}
        <input type="url" placeholder="Product link (optional)" value={f.url} onChange={set('url')} />
        <button>Submit</button>
        {msg && <p className="muted" role="status">{msg}</p>}
      </form>
    </details>
  );
}

export default function App() {
  const [q, setQ] = useState('');
  const [country, setCountry] = useState(() => { try { return localStorage.getItem('pa_country') || guessCountry(); } catch { return guessCountry(); } });
  const [city, setCity] = useState(() => { try { return localStorage.getItem('pa_city') || ''; } catch { return ''; } });
  const [options, setOptions] = useState([]);
  const [product, setProduct] = useState(null);
  const [result, setResult] = useState(null);
  const [history, setHistory] = useState([]);
  const [stores, setStores] = useState([]);
  const [error, setError] = useState('');

  useEffect(() => { // product suggestions
    const t = setTimeout(() => api(`/api/products?q=${encodeURIComponent(q)}`).then(setOptions).catch(() => {}), 200);
    return () => clearTimeout(t);
  }, [q]);

  async function load(p = product) {
    if (!p) return;
    setError('');
    try {
      try { localStorage.setItem('pa_country', country); localStorage.setItem('pa_city', city); } catch { /* storage may be blocked */ }
      const params = new URLSearchParams({ productId: p.id, ...(country && { country }), ...(city && { city }) });
      const [r, h, s] = await Promise.all([api(`/api/compare?${params}`), api(`/api/history?productId=${p.id}`), api(`/api/stores${country ? `?country=${encodeURIComponent(country)}` : ''}`)]);
      setResult(r); setHistory(h.days); setStores(s);
    } catch (err) { setError(err.message); }
  }
  const pick = (p) => { setProduct(p); setQ(p.name); load(p); };

  return (
    <main>
      <h1>Price Agent</h1>
      <div className="row">
        <input value={country} onChange={(e) => setCountry(e.target.value)} placeholder="Country" aria-label="Country" />
        <input value={city} onChange={(e) => setCity(e.target.value)} placeholder="City (optional)" aria-label="City" />
      </div>
      <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search a product…" aria-label="Product" />
      <ul className="options">
        {options.map((p) => <li key={p.id}><button type="button" className="link" onClick={() => pick(p)}>{p.name} <span className="muted">({p.offers} prices)</span></button></li>)}
      </ul>
      {error && <p className="error" role="alert">{error}</p>}
      {result && (
        <>
          <h2>{result.product.name}</h2>
          {result.offers.length === 0 && <p className="muted">No prices for this region yet. Report one below.</p>}
          {result.offers.map((o) => <OfferCard key={o.id} o={o} currency={result.currency} best={result.best?.id === o.id} />)}
          {result.excludedOtherCurrency > 0 && <p className="muted">{result.excludedOtherCurrency} offer(s) in another currency are not ranked.</p>}
          <div className="card"><h3>Price history (lowest per day)</h3><Sparkline days={history} /></div>
          <AddPrice product={result.product} currency={result.currency} stores={stores} onSaved={() => load()} />
        </>
      )}
      <p className="muted">Prices come from the collector, admins and community reports. They change quickly: confirm on the store before buying.</p>
    </main>
  );
}
