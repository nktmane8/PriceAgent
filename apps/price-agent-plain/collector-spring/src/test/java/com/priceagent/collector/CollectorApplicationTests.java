package com.priceagent.collector;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

/** Checks that the Spring context starts and settings bind. Not run in my sandbox (needs the Spring jars). */
@SpringBootTest(properties = {"collector.run-on-startup=false", "collector.api-url=http://localhost:9999", "collector.delay-millis=1"})
class CollectorApplicationTests {
    @Autowired
    CollectorProperties props;

    @Autowired
    CollectionJob job;

    @Test
    void contextLoadsAndPropertiesBind() {
        assertEquals("http://localhost:9999", props.apiUrl());
        assertEquals(1, props.delayMillis());
        assertTrue(props.userAgent().startsWith("PriceAgentCollector"));
    }
}
