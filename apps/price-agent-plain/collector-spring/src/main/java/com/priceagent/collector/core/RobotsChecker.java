package com.priceagent.collector.core;

import java.net.URI;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Asks "may we fetch this URL?" using the site's robots.txt (cached per site).
 * RFC 9309: robots.txt missing (4xx) = allowed. Server error, redirect or network failure = skip the site for now.
 */
public final class RobotsChecker {
    private final PageFetcher fetcher;
    private final String agentToken;
    private final Map<String, RobotsRules> cache = new ConcurrentHashMap<>();

    public RobotsChecker(PageFetcher fetcher, String agentToken) {
        this.fetcher = fetcher;
        this.agentToken = agentToken;
    }

    /** "PriceAgentCollector/1.0 (+info)" -> "PriceAgentCollector" */
    public static String agentToken(String userAgent) {
        String first = userAgent.trim().split("[\\s/]")[0];
        return first.isEmpty() ? "*" : first;
    }

    public boolean allowed(String url) {
        URI u = URI.create(url);
        String origin = u.getScheme() + "://" + u.getRawAuthority();
        RobotsRules rules = cache.computeIfAbsent(origin, this::load);
        String path = (u.getRawPath() == null || u.getRawPath().isEmpty() ? "/" : u.getRawPath())
                + (u.getRawQuery() != null ? "?" + u.getRawQuery() : "");
        return rules.isAllowed(path);
    }

    private RobotsRules load(String origin) {
        try {
            return RobotsRules.parse(fetcher.fetch(origin + "/robots.txt"), agentToken);
        } catch (FetchException e) {
            return e.status() >= 400 && e.status() < 500 ? RobotsRules.allowAll() : RobotsRules.disallowAll();
        }
    }
}
