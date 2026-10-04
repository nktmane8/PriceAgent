package com.priceagent.collector.core;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.sun.net.httpserver.HttpServer;
import java.io.IOException;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.concurrent.atomic.AtomicInteger;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

/** Talks to a tiny in-process HTTP server (no internet needed). */
class HttpAndIngestTest {
    private HttpServer server;
    private String base;
    private final List<String> bodies = new CopyOnWriteArrayList<>();
    private final List<String> keys = new CopyOnWriteArrayList<>();
    private final AtomicInteger apiStatus = new AtomicInteger(201);

    @BeforeEach
    void start() throws IOException {
        server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.createContext("/ok", ex -> reply(ex, 200, "<html>hello</html>"));
        server.createContext("/missing", ex -> reply(ex, 404, "nope"));
        server.createContext("/moved", ex -> { ex.getResponseHeaders().add("Location", "/ok"); reply(ex, 301, ""); });
        server.createContext("/big", ex -> reply(ex, 200, "x".repeat(500)));
        server.createContext("/api/ingest", ex -> {
            bodies.add(new String(ex.getRequestBody().readAllBytes(), StandardCharsets.UTF_8));
            keys.add(String.valueOf(ex.getRequestHeaders().getFirst("x-ingest-key")));
            reply(ex, apiStatus.get(), "{\"ingested\":1}");
        });
        server.start();
        base = "http://127.0.0.1:" + server.getAddress().getPort();
    }

    @AfterEach
    void stop() {
        server.stop(0);
    }

    private static void reply(com.sun.net.httpserver.HttpExchange ex, int status, String body) throws IOException {
        byte[] b = body.getBytes(StandardCharsets.UTF_8);
        ex.sendResponseHeaders(status, b.length == 0 ? -1 : b.length);
        if (b.length > 0) ex.getResponseBody().write(b);
        ex.close();
    }

    @Test
    void fetcherReturnsBodyAndRefusesRedirectsErrorsBigPagesAndBlockedUrls() throws Exception {
        HttpPageFetcher f = new HttpPageFetcher(u -> true, "TestAgent/1.0", 100);
        assertEquals("<html>hello</html>", f.fetch(base + "/ok"));
        assertEquals(404, assertThrows(FetchException.class, () -> f.fetch(base + "/missing")).status());
        FetchException moved = assertThrows(FetchException.class, () -> f.fetch(base + "/moved"));
        assertEquals(301, moved.status());
        assertTrue(moved.getMessage().contains("redirects are not followed"));
        assertTrue(assertThrows(FetchException.class, () -> f.fetch(base + "/big")).getMessage().contains("too large"));
        assertTrue(assertThrows(FetchException.class, () -> new HttpPageFetcher(u -> false, "T/1", 100).fetch(base + "/ok"))
                .getMessage().contains("not a public"));
    }

    @Test
    void ingestClientSendsKeyJsonAndBatchesOf500() throws Exception {
        List<IngestItem> items = new ArrayList<>();
        for (int i = 0; i < 501; i++) items.add(new IngestItem("Phone " + i, "Shop", "local", "India", null, 10.5, "INR", null, "https://s/p"));
        assertEquals(501, new IngestClient(base + "/", "secret").send(items));
        assertEquals(2, bodies.size());
        assertEquals(List.of("secret", "secret"), keys);
        JsonNode first = new ObjectMapper().readTree(bodies.get(0));
        assertEquals(500, first.get("items").size());
        JsonNode item = first.get("items").get(0);
        assertEquals("Phone 0", item.get("product").asText());
        assertEquals("local", item.get("storeType").asText());
        assertTrue(!item.has("city") && !item.has("inStock"));           // null fields are omitted
        assertEquals(1, new ObjectMapper().readTree(bodies.get(1)).get("items").size());
    }

    @Test
    void ingestClientReportsApiErrorsAndMissingKey() {
        IngestItem one = new IngestItem("P1", "S1", "local", "India", null, 1, "INR", true, null);
        apiStatus.set(401);
        IOException e = assertThrows(IOException.class, () -> new IngestClient(base, "wrong").send(List.of(one)));
        assertTrue(e.getMessage().startsWith("API returned 401"));
        assertThrows(IllegalStateException.class, () -> new IngestClient(base, " ").send(List.of(one)));
    }
}
