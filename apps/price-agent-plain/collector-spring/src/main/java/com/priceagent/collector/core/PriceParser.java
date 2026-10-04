package com.priceagent.collector.core;

import com.fasterxml.jackson.databind.JsonNode;
import java.util.OptionalDouble;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** Turns "1,299.00", "₹ 1299", "1.299,00", 1299 into a positive double. Empty if it is not a usable single price (ranges, negatives, text). */
public final class PriceParser {
    private static final Pattern NUMBER = Pattern.compile("\\d[\\d.,]*\\d|\\d");

    private PriceParser() { }

    public static OptionalDouble parse(JsonNode v) {
        if (v == null || v.isNull() || v.isBoolean()) return OptionalDouble.empty();
        if (v.isNumber()) return positive(v.asDouble());
        if (v.isTextual()) return parse(v.asText());
        return OptionalDouble.empty();
    }

    public static OptionalDouble parse(String raw) {
        if (raw == null || raw.trim().startsWith("-")) return OptionalDouble.empty();   // negative
        Matcher m = NUMBER.matcher(raw);
        if (!m.find()) return OptionalDouble.empty();
        String s = m.group();
        if (m.find()) return OptionalDouble.empty();      // two numbers (a range like "1,299 - 1,499") is ambiguous: refuse
        int commas = count(s, ','), dots = count(s, '.');
        if (commas > 0 && dots > 0) {
            // Both present: whichever appears last is the decimal separator.
            if (s.lastIndexOf(',') > s.lastIndexOf('.')) s = s.replace(".", "").replace(',', '.');
            else s = s.replace(",", "");
        } else if (commas == 1 && s.length() - s.indexOf(',') - 1 <= 2) {
            s = s.replace(',', '.');                       // 12,50 -> decimal comma
        } else if (commas > 0) {
            s = s.replace(",", "");                        // 1,299 or 1,299,000 -> thousands
        } else if (dots > 1) {
            s = s.replace(".", "");                        // 1.299.000 -> thousands
        }
        try {
            return positive(Double.parseDouble(s));
        } catch (NumberFormatException e) {
            return OptionalDouble.empty();
        }
    }

    private static OptionalDouble positive(double d) {
        return d > 0 && Double.isFinite(d) ? OptionalDouble.of(d) : OptionalDouble.empty();
    }

    private static int count(String s, char c) {
        int n = 0;
        for (int i = 0; i < s.length(); i++) if (s.charAt(i) == c) n++;
        return n;
    }
}
