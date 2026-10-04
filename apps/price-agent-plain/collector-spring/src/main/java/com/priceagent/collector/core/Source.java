package com.priceagent.collector.core;

/** One product page to read. Field names in sources.json: product, store, store_type, country, city, url. */
public record Source(String product, String store, String storeType, String country, String city, String url) { }
