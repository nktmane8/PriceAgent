package com.priceagent.collector.core;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.Test;

class RobotsRulesTest {
    private static final String ME = "PriceAgentCollector";

    @Test
    void starGroupDisallowAndLongestMatchWins() {
        RobotsRules r = RobotsRules.parse("User-agent: *\nDisallow: /private\nAllow: /private/public\n# comment\n", ME);
        assertFalse(r.isAllowed("/private/x"));
        assertTrue(r.isAllowed("/private/public/page"));
        assertTrue(r.isAllowed("/products/1"));
    }

    @Test
    void specificGroupBeatsStarAndEmptyDisallowAllowsAll() {
        String txt = "User-agent: *\nDisallow: /\n\nUser-agent: PriceAgentCollector\nDisallow:\n";
        assertTrue(RobotsRules.parse(txt, ME).isAllowed("/anything"));
        String blockedUs = "User-agent: *\nAllow: /\n\nUser-agent: priceagentcollector\nDisallow: /shop\n";
        assertFalse(RobotsRules.parse(blockedUs, ME).isAllowed("/shop/phone"));
        assertTrue(RobotsRules.parse(blockedUs, ME).isAllowed("/about"));
    }

    @Test
    void wildcardsAnchorsAndTieGoesToAllow() {
        RobotsRules r = RobotsRules.parse("User-agent: *\nDisallow: /*.pdf$\nDisallow: /tmp*cache\nDisallow: /a\nAllow: /a\n", ME);
        assertFalse(r.isAllowed("/docs/file.pdf"));
        assertTrue(r.isAllowed("/docs/file.pdf?download=1"));     // $ anchors the end
        assertFalse(r.isAllowed("/tmp/x/cache"));
        assertTrue(r.isAllowed("/a/b"));                            // same length: allow wins
    }

    @Test
    void multipleAgentLinesShareOneGroupAndEmptyFileAllowsAll() {
        RobotsRules r = RobotsRules.parse("User-agent: otherbot\nUser-agent: PriceAgent\nDisallow: /x\n", ME);
        assertFalse(r.isAllowed("/x/1"));                           // "PriceAgent" is a prefix of our token
        assertTrue(RobotsRules.parse("", ME).isAllowed("/x"));
        assertTrue(RobotsRules.allowAll().isAllowed("/"));
        assertFalse(RobotsRules.disallowAll().isAllowed("/"));
    }
}
