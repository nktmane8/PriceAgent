package com.priceagent.collector.core;

import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.regex.Pattern;

/** A small robots.txt interpreter (RFC 9309 style): group selection, wildcards, $ anchors, longest match wins, allow wins ties. */
public final class RobotsRules {
    private record Rule(boolean allow, Pattern pattern, boolean anchored, int length) { }
    private record Group(Set<String> agents, List<Rule> rules) { }

    private final List<Rule> rules;

    private RobotsRules(List<Rule> rules) {
        this.rules = rules;
    }

    public static RobotsRules allowAll() {
        return new RobotsRules(List.of());
    }

    public static RobotsRules disallowAll() {
        return new RobotsRules(List.of(rule(false, "/")));
    }

    public static RobotsRules parse(String txt, String agentToken) {
        List<Group> groups = new ArrayList<>();
        Set<String> agents = new LinkedHashSet<>();
        List<Rule> current = new ArrayList<>();
        boolean inRules = false;
        for (String raw : (txt == null ? "" : txt).split("\\R")) {
            String line = raw.contains("#") ? raw.substring(0, raw.indexOf('#')) : raw;
            int colon = line.indexOf(':');
            if (colon < 0) continue;
            String key = line.substring(0, colon).trim().toLowerCase(Locale.ROOT);
            String value = line.substring(colon + 1).trim();
            if (key.equals("user-agent")) {
                if (inRules) {                                  // a new group starts after rules were seen
                    groups.add(new Group(agents, current));
                    agents = new LinkedHashSet<>();
                    current = new ArrayList<>();
                    inRules = false;
                }
                agents.add(value.toLowerCase(Locale.ROOT));
            } else if ((key.equals("allow") || key.equals("disallow")) && !agents.isEmpty()) {
                inRules = true;
                if (!value.isEmpty()) current.add(rule(key.equals("allow"), value));   // empty Disallow = allow all
            }
        }
        if (!agents.isEmpty()) groups.add(new Group(agents, current));

        String me = agentToken.toLowerCase(Locale.ROOT);
        List<Rule> specific = new ArrayList<>(), star = new ArrayList<>();
        for (Group g : groups) {
            for (String a : g.agents()) {
                if (a.equals("*")) star.addAll(g.rules());
                else if (!a.isEmpty() && me.startsWith(a)) specific.addAll(g.rules());
            }
        }
        return new RobotsRules(specific.isEmpty() && !hasSpecificGroup(groups, me) ? star : specific);
    }

    private static boolean hasSpecificGroup(List<Group> groups, String me) {
        for (Group g : groups) for (String a : g.agents()) if (!a.equals("*") && !a.isEmpty() && me.startsWith(a)) return true;
        return false;
    }

    private static Rule rule(boolean allow, String pattern) {
        boolean anchored = pattern.endsWith("$");
        String p = anchored ? pattern.substring(0, pattern.length() - 1) : pattern;
        StringBuilder rx = new StringBuilder();
        String[] parts = p.split("\\*", -1);
        for (int i = 0; i < parts.length; i++) {
            if (i > 0) rx.append(".*");
            if (!parts[i].isEmpty()) rx.append(Pattern.quote(parts[i]));
        }
        return new Rule(allow, Pattern.compile(rx.toString()), anchored, p.length());
    }

    /** pathAndQuery looks like "/products/phone?color=red". */
    public boolean isAllowed(String pathAndQuery) {
        Rule best = null;
        for (Rule r : rules) {
            boolean hit = r.anchored() ? r.pattern().matcher(pathAndQuery).matches() : r.pattern().matcher(pathAndQuery).lookingAt();
            if (!hit) continue;
            if (best == null || r.length() > best.length() || (r.length() == best.length() && r.allow())) best = r;
        }
        return best == null || best.allow();
    }
}
