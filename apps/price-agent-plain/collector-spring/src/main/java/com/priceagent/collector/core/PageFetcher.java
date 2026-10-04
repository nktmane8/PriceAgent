package com.priceagent.collector.core;

/** Port for fetching a page body. Tests supply fakes; production uses HttpPageFetcher. */
public interface PageFetcher {
    String fetch(String url) throws FetchException;
}
