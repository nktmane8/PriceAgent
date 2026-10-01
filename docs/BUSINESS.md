# Downsides and ways to earn money

## Downsides (be honest with yourself first)
1. **Unit economics.** Web search costs $10 per 1,000 searches (Anthropic's published price when I checked), so 15 searches is about $0.15 per uncached comparison before token costs. Free tools users already have (store apps, Google Shopping, established comparison sites) cost them nothing.
2. **Accuracy and liability.** The model can read a page wrong or match the wrong variant. A wrong "best deal" costs a user money and costs you trust.
3. **Terms of service.** Many retailers restrict automated access and reuse of their prices, and affiliate programs often forbid showing prices that did not come from their own API. Read each program's terms before monetising.
4. **Slow and non-deterministic.** 30-60 s and slightly different answers each run. Comparison users expect seconds.
5. **No price history, no alerts, no coverage guarantee.** Established players have these.
6. **Platform dependence.** Pricing, model names, tool versions and directory rules are set by others and change.
7. **Privacy law.** Location is personal data (India's DPDP Act 2023, GDPR and others). You need consent text, a privacy policy, and a no-retention stance.
8. **Incentive conflict.** If affiliate payout influences ranking, say so and keep ranking by price.

## Making it cheaper first (do this before charging)
- Log `usage` tokens and search counts per request to learn the real cost.
- Longer cache for popular products; pre-compute the top few hundred.
- Fewer searches for cheap items; a smaller model for extraction.
- Replace search with official retailer or aggregator APIs where they exist.

## Revenue options (best fit first)
| Model | How | Watch out for |
|---|---|---|
| Affiliate links | Amazon Associates India, Flipkart Affiliate, aggregators like Cuelinks / EarnKaro | Disclose clearly; check price-data rules; never let commission change ranking |
| Freemium + credits | Free: 3 comparisons/day. Paid: packs or monthly plan via Razorpay (India) or Stripe | Price above your measured cost per comparison |
| B2B API | Sell `/api/v1/compare` keys to deal sites, procurement teams, resellers; list on RapidAPI | Needs SLA, async jobs, usage billing |
| Price alerts (new feature) | Watch a product, notify when it drops. Subscription or affiliate on click | Needs scheduler, storage, notification channel |
| Sponsored placement | Brands pay to be featured, clearly labelled | Erodes trust fast; keep separate from "best deal" |
| Consulting / white-label | Build region-specific versions for retailers or banks | Services income, not product income |

Suggested order: measure cost -> add alerts and history (the real moat) -> affiliate + freemium -> B2B API.
