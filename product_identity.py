"""Deterministic product identity normalization for cross-store matching.

This is deliberately conservative: it normalizes wording and formatting but does not
claim two products are identical unless their material variant tokens agree.
"""
import re
import unicodedata

BRANDS = (
    "apple", "samsung", "lg", "sony", "dyson", "oneplus", "xiaomi", "realme",
    "motorola", "google", "bosch", "whirlpool", "haier", "godrej", "voltas",
    "panasonic", "philips", "asus", "lenovo", "hp", "dell", "acer", "tcl",
)

COLORS = {
    "black", "white", "blue", "green", "red", "pink", "purple", "silver",
    "gold", "grey", "gray", "yellow", "orange", "brown", "beige", "cream",
    "graphite", "midnight", "starlight", "natural", "titanium",
}

STOPWORDS = {
    "new", "latest", "official", "buy", "online", "price", "prices", "best",
    "deal", "offers", "offer", "with", "the", "for", "in", "on", "and",
}

def _tokens(value: str) -> list[str]:
    value = unicodedata.normalize("NFKC", value or "").lower()
    value = value.replace("×", "x")
    value = re.sub(r"(?<=\d)\s+(?=gb|tb|inch|in|cm|kg|mm)\b", "", value)
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return [t for t in value.split() if t and t not in STOPWORDS]

def _storage(tokens: list[str]) -> str:
    for token in tokens:
        if re.fullmatch(r"\d+(gb|tb)", token):
            return token
    return ""

def _variant(tokens: list[str]) -> list[str]:
    return sorted(set(
        t for t in tokens
        if t not in COLORS and not re.fullmatch(r"\d+(gb|tb)", t)
    ))

def normalize(product: str) -> dict:
    tokens = _tokens(product)
    brand = next((b for b in BRANDS if b in tokens), "")
    color = next((c for c in tokens if c in COLORS), "")
    storage = _storage(tokens)
    variant = _variant(tokens)
    canonical_key = "|".join(filter(None, [
        brand, " ".join(variant), storage, color,
    ]))
    if not canonical_key:
        canonical_key = " ".join(sorted(set(tokens)))
    return {
        "canonical_key": canonical_key[:500],
        "display_name": " ".join(tokens)[:200],
        "brand": brand,
        "storage": storage,
        "color": color,
        "variant": " ".join(variant)[:300],
    }
