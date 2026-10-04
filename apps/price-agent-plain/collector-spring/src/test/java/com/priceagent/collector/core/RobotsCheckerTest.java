package com.priceagent.collector.core;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.concurrent.atomic.AtomicInteger;
import org.junit.jupiter.api.Test;

class RobotsCheckerTest {
    @Test
    void agentTokenIsTheProductName() {
        assertEquals("PriceAgentCollector", RobotsChecker.agentToken("PriceAgentCollector/1.0 (+respects robots.txt)"));
    }

    @Test
    void usesRulesCachesPerSiteAndAppliesRfcFallbacks() {
        AtomicInteger fetches = new AtomicInteger();
        PageFetcher f = url -> {
            fetches.incrementAndGet();
            if (url.startsWith("https://a.example")) return "User-agent: *\nDisallow: /cart\n";
            if (url.startsWith("https://b.example")) throw new FetchException("HTTP 404", 404);
            if (url.startsWith("https://c.example")) throw new FetchException("HTTP 503", 503);
            throw new FetchException("fetch failed", 0);
        };
        RobotsChecker c = new RobotsChecker(f, "PriceAgentCollector");
        assertTrue(c.allowed("https://a.example/product/1?x=1"));
        assertFalse(c.allowed("https://a.example/cart/view"));
        assertEquals(1, fetches.get());                                  // robots.txt fetched once per site
        assertTrue(c.allowed("https://b.example/anything"));            // 404: no restrictions
        assertFalse(c.allowed("https://c.example/anything"));           // 5xx: stay away
        assertFalse(c.allowed("https://d.example/anything"));           // network failure: stay away
    }
}
