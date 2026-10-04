package com.priceagent.collector;

import com.priceagent.collector.core.CollectorService;
import com.priceagent.collector.core.HttpPageFetcher;
import com.priceagent.collector.core.IngestClient;
import com.priceagent.collector.core.JsonLdExtractor;
import com.priceagent.collector.core.PageFetcher;
import com.priceagent.collector.core.RobotsChecker;
import com.priceagent.collector.core.SourceLoader;
import com.priceagent.collector.core.UrlGuard;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/** Wires the plain-Java core classes together. The core has no Spring dependency, so it is easy to test. */
@Configuration
public class CollectorConfig {
    private static final int MAX_PAGE_BYTES = 1_500_000;

    @Bean
    UrlGuard urlGuard() {
        return new UrlGuard();
    }

    @Bean
    PageFetcher pageFetcher(UrlGuard guard, CollectorProperties props) {
        return new HttpPageFetcher(guard::isPublicUrl, props.userAgent(), MAX_PAGE_BYTES);
    }

    @Bean
    RobotsChecker robotsChecker(PageFetcher fetcher, CollectorProperties props) {
        return new RobotsChecker(fetcher, RobotsChecker.agentToken(props.userAgent()));
    }

    @Bean
    CollectorService collectorService(PageFetcher fetcher, RobotsChecker robots, CollectorProperties props) {
        return new CollectorService(fetcher, robots, new JsonLdExtractor(), props.delayMillis(), Thread::sleep);
    }

    @Bean
    IngestClient ingestClient(CollectorProperties props) {
        return new IngestClient(props.apiUrl(), props.ingestKey());
    }

    @Bean
    SourceLoader sourceLoader() {
        return new SourceLoader();
    }
}
