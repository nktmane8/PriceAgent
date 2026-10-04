package com.priceagent.collector.core;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.List;
import java.util.Map;

/** Sends items to the Node API (POST /api/ingest, header x-ingest-key), at most 500 per request. */
public final class IngestClient {
    static final int BATCH = 500;
    private static final ObjectMapper MAPPER = new ObjectMapper();
    private final HttpClient client = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(10)).build();
    private final String apiUrl;
    private final String key;

    public IngestClient(String apiUrl, String key) {
        this.apiUrl = apiUrl.endsWith("/") ? apiUrl.substring(0, apiUrl.length() - 1) : apiUrl;
        this.key = key;
    }

    public int send(List<IngestItem> items) throws IOException, InterruptedException {
        if (key == null || key.isBlank()) throw new IllegalStateException("INGEST_KEY is not set");
        int sent = 0;
        for (int i = 0; i < items.size(); i += BATCH) {
            List<IngestItem> batch = items.subList(i, Math.min(items.size(), i + BATCH));
            HttpRequest request = HttpRequest.newBuilder(URI.create(apiUrl + "/api/ingest")).timeout(Duration.ofSeconds(30))
                    .header("Content-Type", "application/json").header("x-ingest-key", key)
                    .POST(HttpRequest.BodyPublishers.ofString(MAPPER.writeValueAsString(Map.of("items", batch)))).build();
            HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString());
            if (response.statusCode() / 100 != 2) {
                String body = response.body() == null ? "" : response.body();
                throw new IOException("API returned " + response.statusCode() + ": " + (body.length() > 200 ? body.substring(0, 200) : body));
            }
            sent += batch.size();
        }
        return sent;
    }
}
