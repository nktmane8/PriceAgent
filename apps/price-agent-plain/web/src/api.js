// Thin fetch wrapper: throws Error(message) using the API's { error } body.
export async function api(path, options = {}) {
  const res = await fetch(path, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    body: options.body ? JSON.stringify(options.body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `Request failed (${res.status})`);
  return data;
}

export function money(n, currency) {
  if (typeof n !== 'number' || !Number.isFinite(n)) return 'n/a';
  try {
    return new Intl.NumberFormat(undefined, { style: 'currency', currency, maximumFractionDigits: 0 }).format(n);
  } catch {
    return `${currency || ''} ${n}`;
  }
}

export function ago(ms) {
  const d = Math.floor((Date.now() - ms) / 86400000);
  return d <= 0 ? 'today' : d === 1 ? '1 day ago' : `${d} days ago`;
}

export const isHttp = (u) => typeof u === 'string' && /^https?:\/\//.test(u);

// Guess the shopper's country from the browser locale (en-IN -> India). Empty if unknown.
export function guessCountry() {
  try {
    const m = (navigator.language || '').match(/-([A-Za-z]{2})$/);
    return m ? new Intl.DisplayNames(['en'], { type: 'region' }).of(m[1].toUpperCase()) || '' : '';
  } catch {
    return '';
  }
}
