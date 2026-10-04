package com.priceagent.collector.core;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.net.URI;
import java.net.URISyntaxException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Set;

/** Reads and validates sources.json. Throws IllegalArgumentException with the entry number on bad input. */
public final class SourceLoader {
    private static final ObjectMapper MAPPER = new ObjectMapper();
    private static final Set<String> TYPES = Set.of("marketplace", "brand", "chain", "local");

    public List<Source> load(Path file) throws IOException {
        return parse(Files.readString(file));
    }

    public List<Source> parse(String json) {
        final JsonNode root;
        try {
            root = MAPPER.readTree(json);
        } catch (JsonProcessingException e) {
            throw new IllegalArgumentException("sources file is not valid JSON");
        }
        if (root == null || !root.isArray()) throw new IllegalArgumentException("sources must be a JSON array");
        List<Source> out = new ArrayList<>();
        for (int i = 0; i < root.size(); i++) {
            JsonNode n = root.get(i);
            String where = "source #" + (i + 1) + ": ";
            String product = req(n, "product", 2, 120, where), store = req(n, "store", 2, 80, where);
            String country = req(n, "country", 2, 60, where), url = req(n, "url", 8, 500, where);
            String type = n.hasNonNull("store_type") ? n.get("store_type").asText() : "marketplace";
            if (!TYPES.contains(type)) throw new IllegalArgumentException(where + "store_type must be one of " + TYPES);
            String city = n.hasNonNull("city") ? n.get("city").asText().trim() : null;
            if (!(url.startsWith("http://") || url.startsWith("https://"))) throw new IllegalArgumentException(where + "url must start with http:// or https://");
            try {
                new URI(url);
            } catch (URISyntaxException e) {
                throw new IllegalArgumentException(where + "url is not valid");
            }
            out.add(new Source(product, store, type, country, city == null || city.isEmpty() ? null : city, url));
        }
        return out;
    }

    private static String req(JsonNode n, String field, int min, int max, String where) {
        String v = n.hasNonNull(field) && n.get(field).isTextual() ? n.get(field).asText().trim() : "";
        if (v.length() < min || v.length() > max) throw new IllegalArgumentException(where + field + " must be " + min + "-" + max + " characters");
        return v;
    }
}
