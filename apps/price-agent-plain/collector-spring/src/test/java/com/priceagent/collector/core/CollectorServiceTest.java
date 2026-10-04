package com.priceagent.collector.core;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicInteger;
import org.junit.jupiter.api.Test;

class CollectorServiceTest {
    private static Source src(String product, String url) {
        return new Source(product, "Shop", "marketplace", "India", null, url);
    }

    private static String page(String body) {
        return "<script type=\"application/ld+json\">" + body + "</script>";
    }

    @Test
    void buildsItemsReportsSkipsAndSleepsBetweenPages() {
        Map<String, String> pages = Map.of(
                "https://a.example/1", page("{\"@type\":\"Product\",\"offers\":{\"price\":100,\"priceCurrency\":\"INR\",\"availability\":\"InStock\"}}"),
                "https://c.example/3", "<html>no data</html>",
                "https://e.example/5", page("{\"@type\":\"Product\",\"offers\":{\"price\":50}}"));   // price without currency
        PageFetcher fetcher = url -> {
            String p = pages.get(url);
            if (p == null) throw new FetchException("boom", 0);
            return p;
        };
        RobotsChecker robots = new RobotsChecker(u -> "User-agent: *\nDisallow: /blocked\n", "PriceAgentCollector");
        AtomicInteger sleeps = new AtomicInteger();
        CollectorService svc = new CollectorService(fetcher, robots, new JsonLdExtractor(), 5, ms -> sleeps.incrementAndGet());

        CollectorService.Result r = svc.collect(List.of(src("A", "https://a.example/1"), src("B", "https://b.example/blocked/2"),
                src("C", "https://c.example/3"), src("D", "https://d.example/4"), src("E", "https://e.example/5")));

        assertEquals(1, r.items().size());
        IngestItem item = r.items().get(0);
        assertEquals("A", item.product());
        assertEquals(100.0, item.price());
        assertEquals("INR", item.currency());
        assertEquals(Boolean.TRUE, item.inStock());
        assertNull(item.city());
        String all = String.join(" | ", r.report().stream().map(CollectorService.Report::status).toList());
        for (String expected : new String[]{"robots.txt disallows", "no structured price", "boom"}) assertTrue(all.contains(expected), expected);
        assertEquals(4, sleeps.get());                                   // between 5 pages, not after the last
    }
}
