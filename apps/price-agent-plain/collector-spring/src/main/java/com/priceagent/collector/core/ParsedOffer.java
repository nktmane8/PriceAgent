package com.priceagent.collector.core;

/** A price found on a page. inStock is null when the page does not say. */
public record ParsedOffer(String name, double price, String currency, Boolean inStock, String url) { }
