# Marketing-copy templates (Feature 4)

A **template layer**, not new model code: versioned prompt configs executed
through the existing `write` service. **Adding a YAML file makes the template
appear in the API, CLI, and UI with no code change** — the `fields` schema drives
dynamic forms.

Three categories ship today: **26 marketing**, **16 everyday-life** (cover
letter, complaint, condolence, resignation, …), and the **creative** set. The
char-limited assets (Google RSA, app-store listing) declare their platform limits
in-prompt and pair with the `strict_limit` guarantee (`max_chars` / `max_words`).

## Template files

`src/write_better/templates/<category>/*.yaml` (shipped as package data):

```yaml
id: cold-email-b2b
name: Cold email (B2B)
category: marketing
description: Short, personalized cold outreach with one CTA.
fields:
  - { key: product, label: "What you're selling", type: text, required: true }
  - { key: cta, label: "Call to action", type: text, required: true }
  - { key: tone, label: "Tone", type: select, options: [direct, warm, playful], default: direct }
defaults: { service: write, format: email, length: short }
variants: 3
prompt: |
  Write a {tone} cold B2B email selling {product}.
  {{#pain}}Anchor on: {pain}.{{/pain}}   # section: rendered only if `pain` is set
  End with exactly one CTA: {cta}.
```

Stdlib-only — the loader parses this constrained YAML shape (no `pyyaml`
dependency). Prompts support `{field}` substitution and `{{#field}}…{{/field}}` /
`{{^field}}…{{/field}}` (conditional / inverted) sections.

## API

```bash
GET  /v1/templates?category=marketing      # list with fields schema (drives forms)
POST /v1/improve { "template": "cold-email-b2b",
                   "template_fields": { "product": "…", "audience": "…", "cta": "…" } }
```

The response carries `variants: [...]` (N from the template, clamped to the plan's
remaining generations) plus the usual `text`/`model`/`usage`/`quota`.

- **Unknown template** → 422 `unknown_template` (+ available ids).
- **Missing required field** → 422 `missing_fields` with the field schema echoed
  back (so the UI can render the form with errors).

## SDK

```js
const forms = await client.listTemplates("marketing");
const { variants } = await client.useTemplate("cold-email-b2b",
  { product: "Acme CRM", audience: "ops teams", cta: "Book a demo" });
```

## Launch set

Shipped this PR (10): `cold-email-b2b`, `aida-ad`, `pas-ad`, `landing-hero`,
`product-description`, `feature-benefit`, `linkedin-post`, `seo-meta`,
`blog-outline`, `tagline-batch`. The remaining launch templates (RSA ads, press
release, App Store listing, webinar invite, …) are **pure content additions** — a
new YAML file appears everywhere automatically, with no code change. Teams-tier
note: a follow-up applies the team style guide to template runs (the gateway
already injects it on `/v1/improve`).
