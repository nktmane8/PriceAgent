package com.priceagent.collector.core;

import java.net.InetAddress;
import java.net.URI;
import java.net.URISyntaxException;
import java.net.UnknownHostException;

/**
 * SSRF protection: only http(s) on ports 80/443 whose host resolves ONLY to public addresses
 * (blocks localhost, private networks, link-local and cloud-metadata addresses).
 * Residual risk: DNS rebinding between this check and the actual connection.
 */
public final class UrlGuard {
    @FunctionalInterface
    public interface Resolver {
        InetAddress[] resolve(String host) throws UnknownHostException;
    }

    private final Resolver resolver;

    public UrlGuard() {
        this(InetAddress::getAllByName);
    }

    public UrlGuard(Resolver resolver) {
        this.resolver = resolver;
    }

    public boolean isPublicUrl(String url) {
        final URI u;
        try {
            u = new URI(url);
        } catch (URISyntaxException e) {
            return false;
        }
        String scheme = u.getScheme();
        if (scheme == null || !(scheme.equalsIgnoreCase("http") || scheme.equalsIgnoreCase("https"))) return false;
        if (u.getHost() == null || u.getUserInfo() != null) return false;
        int port = u.getPort();
        if (port != -1 && port != 80 && port != 443) return false;
        try {
            InetAddress[] addresses = resolver.resolve(u.getHost());
            if (addresses.length == 0) return false;
            for (InetAddress a : addresses) if (!isPublic(a)) return false;
            return true;
        } catch (UnknownHostException e) {
            return false;
        }
    }

    static boolean isPublic(InetAddress a) {
        if (a.isAnyLocalAddress() || a.isLoopbackAddress() || a.isLinkLocalAddress()
                || a.isSiteLocalAddress() || a.isMulticastAddress()) return false;
        byte[] b = a.getAddress();
        if (b.length == 4) {
            int b0 = b[0] & 0xff, b1 = b[1] & 0xff, b2 = b[2] & 0xff;
            if (b0 == 0) return false;                                   // 0.0.0.0/8
            if (b0 == 100 && b1 >= 64 && b1 <= 127) return false;        // carrier-grade NAT 100.64.0.0/10
            if (b0 == 192 && b1 == 0 && b2 == 0) return false;           // 192.0.0.0/24
            if (b0 == 198 && (b1 == 18 || b1 == 19)) return false;       // benchmarking 198.18.0.0/15
            return b0 < 240;                                              // reserved / broadcast
        }
        if ((b[0] & 0xfe) == 0xfc) return false;                          // IPv6 unique local fc00::/7
        return !((b[0] & 0xff) == 0x20 && (b[1] & 0xff) == 0x01 && b[2] == 0x0d && (b[3] & 0xff) == 0xb8); // 2001:db8::/32
    }
}
