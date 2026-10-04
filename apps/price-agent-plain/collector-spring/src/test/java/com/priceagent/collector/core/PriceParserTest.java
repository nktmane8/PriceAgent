package com.priceagent.collector.core;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

class PriceParserTest {
    private double p(String s) { return PriceParser.parse(s).getAsDouble(); }

    @Test
    void parsesCommonFormats() {
        assertEquals(1299.0, p("₹ 1,299"));
        assertEquals(1299.0, p("1,299.00"));
        assertEquals(12.5, p("12,50"));
        assertEquals(1299.0, p("1.299,00"));          // European: last separator is the decimal one
        assertEquals(1299000.0, p("1.299.000"));
        assertEquals(1299000.0, p("1,299,000"));
        assertEquals(499.5, p("499.50"));
        assertEquals(1299.0, p("Rs. 1,299."));                               // trailing punctuation
        assertEquals(1299.0, p("1299 INR"));
    }

    @Test
    void rejectsNonPrices() throws Exception {
        assertTrue(PriceParser.parse("free").isEmpty());
        assertTrue(PriceParser.parse("0").isEmpty());
        assertTrue(PriceParser.parse("-5").isEmpty());                       // negative
        assertTrue(PriceParser.parse("1,299 - 1,499").isEmpty());            // a range is ambiguous
        assertTrue(PriceParser.parse("from 100 to 200").isEmpty());
        assertTrue(PriceParser.parse((String) null).isEmpty());
        ObjectMapper m = new ObjectMapper();
        assertTrue(PriceParser.parse(m.readTree("true")).isEmpty());
        assertTrue(PriceParser.parse(m.readTree("null")).isEmpty());
        assertEquals(10.0, PriceParser.parse(m.readTree("10")).getAsDouble());
        assertTrue(PriceParser.parse(m.readTree("0")).isEmpty());
    }
}
