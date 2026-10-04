package com.priceagent.collector.core;

import com.fasterxml.jackson.annotation.JsonInclude;

/** One item of POST /api/ingest. JSON field names match the Node API (camelCase). */
@JsonInclude(JsonInclude.Include.NON_NULL)
public record IngestItem(String product, String store, String storeType, String country, String city,
                         double price, String currency, Boolean inStock, String url) { }
