// Input validation. Every public endpoint checks its input here; nothing trusts the client.
export const isStr = (v, min, max) => typeof v === 'string' && v.trim().length >= min && v.trim().length <= max;
export const isNum = (v) => typeof v === 'number' && Number.isFinite(v);
export const isHttp = (v) => {
  try { const u = new URL(v); return ['http:', 'https:'].includes(u.protocol) && v.length <= 500; } catch { return false; }
};
export const STORE_TYPES = ['marketplace', 'brand', 'chain', 'local'];

/** Validate the price part of an offer. Returns an error message or null. */
export function checkOffer(o) {
  if (!isNum(o.price) || o.price <= 0 || o.price >= 1e9) return 'price must be a positive number';
  if (typeof o.currency !== 'string' || !/^[A-Z]{3}$/.test(o.currency)) return 'currency must be a 3-letter code like INR';
  const d = o.instantDiscount ?? 0;
  if (!isNum(d) || d < 0 || d >= o.price) return 'instantDiscount must be 0 or more and less than price';
  if (d > 0 && !isStr(o.discountNote, 3, 200)) return 'discountNote is required when instantDiscount is set (say where the discount is shown)';
  if (o.discountNote != null && !isStr(o.discountNote, 0, 200)) return 'discountNote must be at most 200 characters';
  if (o.inStock != null && typeof o.inStock !== 'boolean') return 'inStock must be true or false';
  if (o.url != null && o.url !== '' && !isHttp(o.url)) return 'url must start with http:// or https://';
  return null;
}

export function checkStore(s) {
  if (!isStr(s.name, 2, 80)) return 'store name must be 2-80 characters';
  if (!STORE_TYPES.includes(s.type)) return `type must be one of ${STORE_TYPES.join(', ')}`;
  if (!isStr(s.country, 2, 60)) return 'country must be 2-60 characters';
  if (s.city != null && !isStr(s.city, 1, 60)) return 'city must be 1-60 characters';
  if (s.website != null && s.website !== '' && !isHttp(s.website)) return 'website must be an http(s) URL';
  return null;
}
