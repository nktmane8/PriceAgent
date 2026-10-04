package com.priceagent.collector.core;

import java.io.IOException;
import java.io.InputStream;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.function.Predicate;

/** Fetches pages with the JDK HttpClient: no redirects, timeouts, size cap, and a URL allow-check (UrlGuard) first. */
public final class HttpPageFetcher implements PageFetcher {
    private final HttpClient client = HttpClient.newBuilder()
            .followRedirects(HttpClient.Redirect.NEVER).connectTimeout(Duration.ofSeconds(10)).build();
    private final Predicate<String> urlAllowed;
    private final String userAgent;
    private final int maxBytes;

    public HttpPageFetcher(Predicate<String> urlAllowed, String userAgent, int maxBytes) {
        this.urlAllowed = urlAllowed;
        this.userAgent = userAgent;
        this.maxBytes = maxBytes;
    }

    @Override
    public String fetch(String url) throws FetchException {
        if (!urlAllowed.test(url)) throw new FetchException("not a public http(s) address", 0);
        HttpRequest request = HttpRequest.newBuilder(URI.create(url)).timeout(Duration.ofSeconds(15))
                .header("User-Agent", userAgent).header("Accept", "text/html,application/xhtml+xml,*/*;q=0.8").GET().build();
        try {
            HttpResponse<InputStream> response = client.send(request, HttpResponse.BodyHandlers.ofInputStream());
            try (InputStream in = response.body()) {
                int status = response.statusCode();
                if (status / 100 != 2) {
                    throw new FetchException(status / 100 == 3 ? "redirects are not followed (HTTP " + status + ")" : "HTTP " + status, status);
                }
                byte[] data = in.readNBytes(maxBytes + 1);
                if (data.length > maxBytes) throw new FetchException("response too large", 0);
                return new String(data, StandardCharsets.UTF_8);
            }
        } catch (IOException e) {
            throw new FetchException("fetch failed: " + e.getMessage(), 0);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new FetchException("interrupted", 0);
        }
    }
}
