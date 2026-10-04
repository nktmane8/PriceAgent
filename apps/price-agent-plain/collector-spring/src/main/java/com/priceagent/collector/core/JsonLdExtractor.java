package com.priceagent.collector.core;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.OptionalDouble;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Finds prices WITHOUT AI: reads schema.org JSON-LD that shops publish for search engines, then falls back to
 * Open Graph / product meta tags. Uses regular expressions (no HTML library), which is enough for these two patterns.
 */
public final class JsonLdExtractor {
    private static final ObjectMapper MAPPER = new ObjectMapper();
    private static final Pattern LD = Pattern.compile(
            "<script\\b[^>]*\\btype\\s*=\\s*[\"']application/ld\\+json[\"'][^>]*>(.*?)</script>",
            Pattern.CASE_INSENSITIVE | Pattern.DOTALL);
    private static final Pattern META = Pattern.compile("<meta\\b([^>]*)>", Pattern.CASE_INSENSITIVE | Pattern.DOTALL);
    private static final Pattern ATTR = Pattern.compile("([a-zA-Z:_-]+)\\s*=\\s*(?:\"([^\"]*)\"|'([^']*)')");

    /** Offers found on the page, best first. Empty if the page has no structured price data. */
    public List<ParsedOffer> extract(String html) {
        List<ParsedOffer> out = new ArrayList<>();
        Matcher m = LD.matcher(html == null ? "" : html);
        while (m.find()) {
            try {
                JsonNode root = MAPPER.readTree(m.group(1).trim());
                if (root != null) walk(root, out);
            } catch (JsonProcessingException e) {
                // broken JSON in one block: ignore it and keep looking
            }
        }
        if (out.isEmpty()) metaFallback(html == null ? "" : html, out);
        return out;
    }

    private void walk(JsonNode n, List<ParsedOffer> out) {
        if (n.isArray()) {
            n.forEach(c -> walk(c, out));
        } else if (n.isObject()) {
            if (isProduct(n)) collectOffers(n, out);
            n.elements().forEachRemaining(c -> {
                if (c.isContainerNode()) walk(c, out);
            });
        }
    }

    private boolean isProduct(JsonNode n) {
        JsonNode t = n.get("@type");
        if (t == null) return false;
        if (t.isArray()) {
            for (JsonNode x : t) if ("Product".equals(x.asText())) return true;
            return false;
        }
        return "Product".equals(t.asText());
    }

    private void collectOffers(JsonNode product, List<ParsedOffer> out) {
        JsonNode offers = product.get("offers");
        if (offers == null) return;
        List<JsonNode> list = new ArrayList<>();
        if (offers.isArray()) offers.forEach(list::add);
        else list.add(offers);
        for (JsonNode off : list) {
            if (!off.isObject()) continue;
            OptionalDouble price = PriceParser.parse(off.has("price") ? off.get("price") : off.get("lowPrice"));
            if (price.isEmpty()) continue;
            String url = text(off.get("url"));
            out.add(new ParsedOffer(cut(text(product.get("name")), 200), price.getAsDouble(),
                    currency(text(off.get("priceCurrency"))), stock(text(off.get("availability"))),
                    url.isEmpty() ? text(product.get("url")) : url));
        }
    }

    private void metaFallback(String html, List<ParsedOffer> out) {
        Map<String, String> meta = new HashMap<>();
        Matcher tags = META.matcher(html);
        while (tags.find()) {
            Map<String, String> attrs = new HashMap<>();
            Matcher a = ATTR.matcher(tags.group(1));
            while (a.find()) attrs.put(a.group(1).toLowerCase(Locale.ROOT), a.group(2) != null ? a.group(2) : a.group(3));
            String key = attrs.containsKey("property") ? attrs.get("property") : attrs.get("name");
            if (key != null && attrs.get("content") != null) meta.put(key, attrs.get("content"));
        }
        OptionalDouble price = PriceParser.parse(meta.getOrDefault("product:price:amount", meta.get("og:price:amount")));
        if (price.isEmpty()) return;
        out.add(new ParsedOffer(meta.getOrDefault("og:title", "").replace("&amp;", "&"), price.getAsDouble(),
                currency(meta.getOrDefault("product:price:currency", meta.getOrDefault("og:price:currency", ""))),
                stock(meta.getOrDefault("product:availability", meta.getOrDefault("og:availability", ""))),
                meta.getOrDefault("og:url", "")));
    }

    static Boolean stock(String availability) {
        String a = availability == null ? "" : availability.toLowerCase(Locale.ROOT);
        if (a.contains("outofstock") || a.contains("soldout") || a.contains("discontinued")) return Boolean.FALSE;
        if (a.contains("instock") || a.contains("limitedavailability") || a.contains("onlineonly")) return Boolean.TRUE;
        return null;
    }

    private static String currency(String c) {
        String u = c == null ? "" : c.trim().toUpperCase(Locale.ROOT);
        return u.length() > 3 ? u.substring(0, 3) : u;
    }

    private static String text(JsonNode n) {
        return n != null && n.isValueNode() && !n.isNull() ? n.asText() : "";
    }

    private static String cut(String s, int max) {
        return s.length() > max ? s.substring(0, max) : s;
    }
}
