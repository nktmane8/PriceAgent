package com.priceagent.collector;

import com.priceagent.collector.core.CollectorService;
import com.priceagent.collector.core.IngestClient;
import com.priceagent.collector.core.Source;
import com.priceagent.collector.core.SourceLoader;
import java.io.IOException;
import java.nio.file.Path;
import java.util.List;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.boot.SpringApplication;
import org.springframework.context.ConfigurableApplicationContext;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

/**
 * Runs a collection: once at start-up (collector.run-on-startup) and/or on a cron schedule (collector.cron).
 * Exit codes mirror the Python collector: 0 ok, 1 nothing collected, 2 configuration or API problem.
 */
@Component
public class CollectionJob implements ApplicationRunner {
    private static final Logger log = LoggerFactory.getLogger(CollectionJob.class);

    private final CollectorProperties props;
    private final CollectorService service;
    private final IngestClient client;
    private final SourceLoader loader;
    private final ConfigurableApplicationContext context;

    public CollectionJob(CollectorProperties props, CollectorService service, IngestClient client,
                         SourceLoader loader, ConfigurableApplicationContext context) {
        this.props = props;
        this.service = service;
        this.client = client;
        this.loader = loader;
        this.context = context;
    }

    @Scheduled(cron = "${collector.cron:-}")   // "-" means disabled
    public void scheduledRun() {
        runOnce();
    }

    @Override
    public void run(ApplicationArguments args) {
        if (!props.runOnStartup()) return;
        int code = runOnce();
        if (props.exitAfterRun()) System.exit(SpringApplication.exit(context, () -> code));
    }

    synchronized int runOnce() {
        final List<Source> sources;
        try {
            sources = loader.load(Path.of(props.sourcesFile()));
        } catch (IOException | IllegalArgumentException e) {
            log.error("Cannot read sources from {}: {}", props.sourcesFile(), e.getMessage());
            return 2;
        }
        CollectorService.Result result = service.collect(sources);
        result.report().forEach(r -> log.info("{}  {}", r.status(), r.url()));
        log.info("{} item(s) ready", result.items().size());
        if (result.items().isEmpty()) return 1;
        if (props.dryRun()) {
            result.items().forEach(i -> log.info("dry-run item: {}", i));
            return 0;
        }
        try {
            log.info("sent {} item(s) to {}", client.send(result.items()), props.apiUrl());
            return 0;
        } catch (IllegalStateException | IOException e) {
            log.error("Could not send to the API: {}", e.getMessage());
            return 2;
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            return 2;
        }
    }
}
