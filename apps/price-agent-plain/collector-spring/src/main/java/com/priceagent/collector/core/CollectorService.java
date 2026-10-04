package com.priceagent.collector.core;

import java.util.ArrayList;
import java.util.List;

/** Orchestrates one collection run: robots check, fetch, extract, build items. Never throws for a single bad page. */
public final class CollectorService {
    @FunctionalInterface
    public interface Sleeper {
        void sleep(long millis) throws InterruptedException;
    }

    public record Report(String url, String status) { }

    public record Result(List<IngestItem> items, List<Report> report) { }

    private final PageFetcher fetcher;
    private final RobotsChecker robots;
    private final JsonLdExtractor extractor;
    private final long delayMillis;
    private final Sleeper sleeper;

    public CollectorService(PageFetcher fetcher, RobotsChecker robots, JsonLdExtractor extractor, long delayMillis, Sleeper sleeper) {
        this.fetcher = fetcher;
        this.robots = robots;
        this.extractor = extractor;
        this.delayMillis = delayMillis;
        this.sleeper = sleeper;
    }

    public Result collect(List<Source> sources) {
        List<IngestItem> items = new ArrayList<>();
        List<Report> report = new ArrayList<>();
        for (int i = 0; i < sources.size(); i++) {
            Source s = sources.get(i);
            try {
                if (!robots.allowed(s.url())) {
                    report.add(new Report(s.url(), "skipped: robots.txt disallows or is unavailable"));
                } else {
                    ParsedOffer offer = extractor.extract(fetcher.fetch(s.url())).stream()
                            .filter(o -> !o.currency().isEmpty()).findFirst().orElse(null);
                    if (offer == null) {
                        report.add(new Report(s.url(), "skipped: no structured price (with currency) on the page"));
                    } else {
                        items.add(itemFrom(s, offer));
                        report.add(new Report(s.url(), "ok " + offer.currency() + " " + offer.price()));
                    }
                }
            } catch (FetchException e) {
                report.add(new Report(s.url(), "skipped: " + e.getMessage()));
            }
            if (i < sources.size() - 1) {
                try {
                    sleeper.sleep(delayMillis);          // be polite to the shop
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                    report.add(new Report("-", "interrupted: stopping early"));
                    break;
                }
            }
        }
        return new Result(items, report);
    }

    static IngestItem itemFrom(Source s, ParsedOffer o) {
        return new IngestItem(s.product(), s.store(), s.storeType(), s.country(), s.city(), o.price(), o.currency(), o.inStock(), s.url());
    }
}
