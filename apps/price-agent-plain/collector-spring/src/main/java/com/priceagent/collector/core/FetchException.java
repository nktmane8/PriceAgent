package com.priceagent.collector.core;

/** A page could not be fetched. status is the HTTP status, or 0 for refusals and network errors. */
public final class FetchException extends Exception {
    private final int status;

    public FetchException(String message, int status) {
        super(message);
        this.status = status;
    }

    public int status() {
        return status;
    }
}
