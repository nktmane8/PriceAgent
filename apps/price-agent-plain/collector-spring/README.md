# Spring Boot collector (Java 21, Spring Boot 4.1)

Same job as `../collector/` (Python), for teams that prefer the JVM: read product pages, extract prices **without AI** from schema.org JSON-LD (or product meta tags), and send them to the Node API (`POST /api/ingest`). The two collectors share one HTTP contract, so you can run either or both.

## Design: a thin Spring shell around a plain-Java core
```
com.priceagent.collector            Spring layer (4 small classes)
  CollectorApplication              @SpringBootApplication, scheduling on
  CollectorProperties               typed settings (collector.*)
  CollectorConfig                   wires the core into beans
  CollectionJob                     runs on start-up and/or on a cron; exit codes 0 ok, 1 nothing collected, 2 config/API error
com.priceagent.collector.core       Plain Java (no Spring): easy to test
  SourceLoader   sources.json -> validated Source records
  HttpPageFetcher + UrlGuard        JDK HttpClient, no redirects, size/time limits, SSRF guard (public IPs only, ports 80/443)
  RobotsChecker + RobotsRules       robots.txt (RFC 9309 style), cached per site
  JsonLdExtractor + PriceParser     JSON-LD / meta parsing, tolerant price formats, rejects ranges and negatives
  CollectorService                  orchestration, politeness delay, per-page report
  IngestClient                      POST /api/ingest in batches of 500 with x-ingest-key
```
Spring Boot 3.5 reached the end of open-source support in June 2026, so this project targets Boot 4.1 (Java 17+; built for Java 21). Use the latest 4.1.x patch in `pom.xml`. The core uses Jackson 2 explicitly (pinned with the Jackson BOM) so it does not depend on Boot's own JSON choice.

## Build and run (needs JDK 21 and Maven)
```bash
cd collector-spring
mvn -B verify                                     # compiles, runs all tests, builds target/collector-spring-1.0.0.jar
cp sources.example.json sources.json              # list pages you are allowed to read
export API_URL=http://localhost:3000 INGEST_KEY=your-key
DRY_RUN=true java -jar target/collector-spring-1.0.0.jar      # preview only
java -jar target/collector-spring-1.0.0.jar                   # collect once, send, exit
# stay running on a schedule (02:30 daily):
COLLECTOR_CRON="0 30 2 * * *" RUN_ON_STARTUP=false EXIT_AFTER_RUN=false java -jar target/collector-spring-1.0.0.jar
```
| Variable | Default | Meaning |
|---|---|---|
| `API_URL` | http://localhost:3000 | Node API |
| `INGEST_KEY` | none | Secret; required unless `DRY_RUN=true` |
| `SOURCES_FILE` | sources.json | Pages to read |
| `DELAY_MILLIS` | 2000 | Wait between page requests |
| `RUN_ON_STARTUP` / `EXIT_AFTER_RUN` | true / true | One-shot mode |
| `COLLECTOR_CRON` | `-` (off) | Spring cron expression (seconds first) |
| `DRY_RUN` | false | Log items instead of sending |

## Python and Java collectors: same contract, a few intentional differences
| | Python (`collector/`) | Java (`collector-spring/`) |
|---|---|---|
| Parsing rules (prices, JSON-LD, meta tags, stock mapping) | same | same |
| HTML handling | `html.parser` | regular expressions (enough for `<script>` and `<meta>`) |
| robots.txt unreadable | treated as allowed | RFC 9309: 4xx = allowed; 5xx/network/redirect = skip the site |
| Scheduling | external (cron, GitHub Actions) | built in (`COLLECTOR_CRON`) |
| Tests | 7 (pytest) | 22 JUnit tests + 1 Spring context test |

## What I verified, and what I did not
- **Verified here:** the whole `core` package compiles with JDK 21 and its 22 JUnit tests pass (including a local in-process HTTP server for fetching and ingest, and the SSRF guard against private, loopback, link-local, carrier-grade NAT and IPv6 unique-local addresses).
- **Type-checked only:** the four Spring classes were compiled against small stubs of the Spring APIs they use, which proves they are consistent with the core but **not** that they match the real Spring Boot 4.1 API.
- **Not run:** `mvn verify`, the `@SpringBootTest` context test, and the packaged jar. Maven Central is not reachable from my sandbox. Run `mvn -B verify` first and fix anything it reports.

## Limits
Works only on pages that publish JSON-LD or product meta tags; many shops block bots or render prices with JavaScript (they are skipped and reported). Check each site's terms before collecting. DNS rebinding between the address check and the connection is a residual SSRF risk.
