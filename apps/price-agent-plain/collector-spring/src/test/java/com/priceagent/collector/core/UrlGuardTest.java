package com.priceagent.collector.core;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.net.InetAddress;
import java.net.UnknownHostException;
import org.junit.jupiter.api.Test;

class UrlGuardTest {
    private static UrlGuard resolvingTo(String... ips) {
        return new UrlGuard(host -> {
            InetAddress[] out = new InetAddress[ips.length];
            for (int i = 0; i < ips.length; i++) out[i] = InetAddress.getByName(ips[i]);
            return out;
        });
    }

    @Test
    void rejectsBadSchemesPortsAndCredentials() {
        UrlGuard g = resolvingTo("93.184.216.34");
        for (String bad : new String[]{"file:///etc/passwd", "ftp://shop.example/", "https://shop.example:8443/", "https://user:pw@shop.example/", "not a url", "http:///x"}) {
            assertFalse(g.isPublicUrl(bad), bad);
        }
        assertTrue(g.isPublicUrl("https://shop.example/p"));
        assertTrue(g.isPublicUrl("http://shop.example:80/p"));
    }

    @Test
    void rejectsPrivateLoopbackLinkLocalAndMetadataAddresses() {
        for (String ip : new String[]{"127.0.0.1", "10.1.2.3", "172.16.0.9", "192.168.1.1", "169.254.169.254", "100.64.0.1",
                "0.0.0.0", "224.0.0.1", "::1", "fd00::1", "fe80::1", "2001:db8::1", "198.18.0.5", "255.255.255.255"}) {
            assertFalse(resolvingTo(ip).isPublicUrl("https://sneaky.example/"), ip);
        }
        assertTrue(resolvingTo("8.8.8.8").isPublicUrl("https://ok.example/"));
        assertTrue(resolvingTo("2606:4700:4700::1111").isPublicUrl("https://ok6.example/"));
    }

    @Test
    void oneBadAddressAmongPublicOnesRejectsTheHost() {
        assertFalse(resolvingTo("8.8.8.8", "10.0.0.1").isPublicUrl("https://mixed.example/"));
    }

    @Test
    void unresolvableHostIsRejectedAndRealLocalhostIsBlocked() {
        assertFalse(new UrlGuard(h -> { throw new UnknownHostException(h); }).isPublicUrl("https://nope.example/"));
        assertFalse(new UrlGuard().isPublicUrl("http://localhost/"));
        assertFalse(new UrlGuard().isPublicUrl("http://127.0.0.1/"));
    }
}
