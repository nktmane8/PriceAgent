package com.priceagent.collector.core;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;
import org.junit.jupiter.api.Test;

class JsonLdExtractorTest {
    private final JsonLdExtractor x = new JsonLdExtractor();

    private static String page(String json) {
        return "<html><head><script type=\"application/ld+json\">" + json + "</script></head></html>";
    }

    @Test
    void singleProductWithOfferAndStock() {
        ParsedOffer o = x.extract(page("{\"@type\":\"Product\",\"name\":\"P\",\"offers\":{\"@type\":\"Offer\",\"price\":\"1,299.00\","
                + "\"priceCurrency\":\"inr\",\"availability\":\"https://schema.org/InStock\",\"url\":\"https://s/p\"}}")).get(0);
        assertEquals(1299.0, o.price());
        assertEquals("INR", o.currency());
        assertEquals(Boolean.TRUE, o.inStock());
        assertEquals("https://s/p", o.url());
        assertEquals(Boolean.FALSE, x.extract(page("{\"@type\":\"Product\",\"offers\":{\"price\":5,\"priceCurrency\":\"USD\",\"availability\":\"OutOfStock\"}}")).get(0).inStock());
        assertNull(x.extract(page("{\"@type\":\"Product\",\"offers\":{\"price\":5,\"priceCurrency\":\"USD\"}}")).get(0).inStock());
    }

    @Test
    void graphListsAggregateOffersAndBrokenJson() {
        String g = "{\"@graph\":[{\"@type\":\"WebSite\"},{\"@type\":[\"Thing\",\"Product\"],\"name\":\"G\",\"offers\":["
                + "{\"price\":\"10\",\"priceCurrency\":\"EUR\"},{\"@type\":\"AggregateOffer\",\"lowPrice\":8,\"priceCurrency\":\"EUR\"}]}]}";
        List<ParsedOffer> offers = x.extract(page(g));
        assertEquals(List.of(10.0, 8.0), offers.stream().map(ParsedOffer::price).toList());
        assertTrue(x.extract("<script type=\"application/ld+json\">{broken</script>").isEmpty());
        assertTrue(x.extract(null).isEmpty());
    }

    @Test
    void attributeOrderAndCaseDoNotMatter() {
        String html = "<SCRIPT data-x='1' TYPE='application/ld+json' id=a>{\"@type\":\"Product\",\"offers\":{\"price\":3,\"priceCurrency\":\"GBP\"}}</SCRIPT>";
        assertEquals(1, x.extract(html).size());
    }

    @Test
    void metaTagFallbackAndNoDataCase() {
        String html = "<meta property=\"product:price:amount\" content=\"499.50\"><meta content=\"INR\" property=\"product:price:currency\">"
                + "<meta property=\"og:title\" content=\"Gadget &amp; Co\">";
        ParsedOffer o = x.extract(html).get(0);
        assertEquals(499.5, o.price());
        assertEquals("INR", o.currency());
        assertEquals("Gadget & Co", o.name());
        assertFalse(x.extract("<html>nothing here</html>").iterator().hasNext());
    }
}
