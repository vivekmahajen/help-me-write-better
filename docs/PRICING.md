# Pricing & Margins — All-in-One AI Content Suite

What to charge end users, and why. The numbers below come from the unit-cost and
cap assumptions in [`src/write_better/plans.py`](../src/write_better/plans.py),
which is the live (testable) form of the pricing spreadsheet — edit the unit
costs or caps there and every margin recalculates. Run `write-better --pricing`
to print the current table.

## Recommended end-user pricing

| Plan | Monthly | Annual (billed yearly) | Seats | Gross margin (typical) | Floor (max use) |
|---|---|---|---|---|---|
| **Free** | $0 | — | 1 | loss-leader | — |
| **Starter** | **$16/mo** | **$13/mo** ($156/yr) | 1 | 79.0% | 50.6% |
| **Pro** | **$39/mo** | **$32/mo** ($384/yr) | 1 | 75.9% | 38.6% |
| **Business** | **$99/mo** | **$82/mo** ($984/yr) | 5 | 77.4% | 42.7% |

"Typical" margins use the **35% cap-utilization** assumption — what a real user
actually consumes. "Floor" margins assume a user maxes every cap at once (rare).

## Why these clear

- **Typical-usage gross margins land at 76–79% across all paid tiers** — squarely
  in the healthy SaaS band (70–80%+). At 35% utilization, every paid plan returns
  roughly 3–4× its cost to serve.
- **The free tier is self-funding.** 10,000 free users cost **$2,340/mo**; at the
  3% conversion rate that's 300 upgrades × $16 = **$4,800/mo**, netting **+$2,460**.
  Break-even conversion is only **1.5%** — about 2× headroom before free drags.
- **Annual pricing** at ~$13 / $32 / $82 is an ~18% discount: trade a discount for
  cash up front and lower churn. Margins compress slightly but stay >70% at typical
  use.

## The one risk to watch — Pro's floor

The recommendation is safe at *typical* use. The exposure is **max-use** (every
cap maxed at once):

- **Pro is the thinnest at 38.6%.** Its caps (300 generations / 250 images / 300
  transcription min) are generous relative to its $39 price, so a power user who
  maxes out still leaves you positive but under 40% margin. Starter holds 50.6%
  and Business 42.7%, so Pro concentrates the margin risk.
- Fine as long as max-users are rare. If Pro power-users cluster, pull these
  levers (in order of impact):
  1. **Cheaper image model** (~$0.005 vs $0.030) — images are the single biggest
     variable cost. In `plans.py`: `UnitCosts(ai_image=0.005)`.
  2. **Trim Pro's image / generation caps.**
  3. **Route more work to the cheap model.** Already built into the engine —
     routine cleanup (`correct`/`clarify`/`tighten`/`summarize`) routes to Haiku;
     only generative/rewrite work (`write`/`paraphrase`) hits Opus. A premium-
     routed request is what counts against a plan's `premium_generations` cap
     (see `plans.cap_consumed_by`).

## Bottom line

**Charge $16 / $39 / $99 monthly (or $13 / $32 / $82 annual-equivalent), free at
$0.** Healthy ~77% typical margins, a sustainable free tier with ~2× conversion
headroom, and a worst-case floor that stays profitable on every tier. Monitor Pro
power-users; if max-utilization on Pro creeps up, pull the image-cost or cap
levers before discounting.

These are **gross** margins (cost-to-serve only). They exclude marketing,
salaries, and other fixed costs — don't read 77% as net.

## Assumptions (edit these as prices move)

Unit costs are current mid-2026 API estimates and fall over time. Update them in
`UnitCosts` / `PLANS` in [`plans.py`](../src/write_better/plans.py):

| Cost item | Cost | Unit |
|---|---|---|
| Premium AI generation | $0.030 | per generation |
| AI image (standard) | $0.030 | per image |
| Voice / TTS | $0.015 | per minute |
| Transcription | $0.006 | per minute |
| Plagiarism / AI check | $0.015 | per check |
| Infrastructure / storage | $0.150 | per user / month |
| Stripe — variable | 2.9% | of price |
| Stripe — fixed | $0.300 | per transaction |

Behavior: 35% typical cap utilization · 10,000 free users · 3% free→paid
conversion. Text writing/editing is treated as effectively free and unlimited
(~$0.002/piece, folded into infrastructure).

## Scan credits (plagiarism + AI detection)

Plagiarism and AI-detection scans are the only features with real marginal cost
(external vendor — see `docs/decisions/ADR-001-plagiarism-vendor.md`). They are
metered as **scan credits**, separate from the model-generation caps:

- 1 credit per **500 words** of plagiarism scan (`ceil(words/500)`); 1 credit per
  AI-detection scan. A combined scan sums them.
- Monthly included credits per tier (`scans.SCAN_CAPS`):

  | Plan | Scan credits / month |
  |---|---|
  | Free | 0 |
  | Starter | 20 |
  | Pro | 100 |
  | Business | 300 |

- **Cached re-scans cost 0** — identical content (by `sha256(normalized_text)`)
  returns the prior result and never re-bills.
- Over the cap → `402 scan_cap_reached` **before** the vendor is called.

At the ADR's vendor pricing (~$0.10–$0.20 / 1k words), one credit ≈ 500 words sits
comfortably inside the per-tier subscription margins; heavy users buy credit packs
(overage), which the `scans` metering already supports.

Everything else added in the Trust/Template layers — citations, marketing
templates, creative tools, the style fingerprint, real-time checks — has **no
external marginal cost** and is not credit-metered (templates consume the normal
model-generation cap; the rest are free/uncapped).
