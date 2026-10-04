package com.priceagent.collector;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.boot.context.properties.bind.DefaultValue;

/** Settings under "collector.*" (see application.yml). The ingest key is a secret: set it only through the environment. */
@ConfigurationProperties(prefix = "collector")
public record CollectorProperties(
        @DefaultValue("http://localhost:3000") String apiUrl,
        String ingestKey,
        @DefaultValue("sources.json") String sourcesFile,
        @DefaultValue("2000") long delayMillis,
        @DefaultValue("PriceAgentCollector/1.0 (+respects robots.txt)") String userAgent,
        @DefaultValue("true") boolean runOnStartup,
        @DefaultValue("true") boolean exitAfterRun,
        @DefaultValue("false") boolean dryRun) { }
