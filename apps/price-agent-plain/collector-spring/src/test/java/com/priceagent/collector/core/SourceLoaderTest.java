package com.priceagent.collector.core;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;
import org.junit.jupiter.api.Test;

class SourceLoaderTest {
    private final SourceLoader loader = new SourceLoader();

    @Test
    void parsesValidEntriesWithDefaults() {
        List<Source> s = loader.parse("[{\"product\":\"Phone X\",\"store\":\"Shop\",\"country\":\"India\",\"city\":\"\",\"url\":\"https://shop.example/p\"}]");
        assertEquals("marketplace", s.get(0).storeType());
        assertNull(s.get(0).city());
        assertEquals("Phone X", s.get(0).product());
    }

    @Test
    void rejectsBadInputWithTheEntryNumber() {
        String base = "{\"product\":\"Phone X\",\"store\":\"Shop\",\"country\":\"India\",\"url\":\"https://shop.example/p\"";
        assertThrows(IllegalArgumentException.class, () -> loader.parse("{not json"));
        assertThrows(IllegalArgumentException.class, () -> loader.parse("{}"));
        assertTrue(assertThrows(IllegalArgumentException.class, () -> loader.parse("[" + base + "}," + base.replace("https", "ftp") + "}]"))
                .getMessage().startsWith("source #2"));
        assertThrows(IllegalArgumentException.class, () -> loader.parse("[" + base + ",\"store_type\":\"mall\"}]"));
        assertThrows(IllegalArgumentException.class, () -> loader.parse("[" + base.replace("Phone X", "P") + "}]"));
    }
}
