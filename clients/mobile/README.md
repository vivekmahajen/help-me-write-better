# Help Me Write Better — mobile app + keyboard (#4)

iOS + Android apps and a **custom keyboard** (iOS keyboard extension / Android
IME) that offer check / rewrite as you type in any app — the mobile equivalent of
the browser extension. All surfaces authenticate to the same accounts and call
the same gateway, so plan caps are enforced server-side.

## What's here

- `src/core.js` — the **portable core shared by the app and the keyboard**:
  `CheckController` (debounced check + `previous`-text tracking + a `rewrite`
  action), `applyReplacement`, `severityColor`, `debounce`. Pure JS with the
  gateway calls injected, so it's testable and reusable from a JS bridge.

This is the cross-surface logic; the native shells consume it.

## Architecture (to build on top of `core.js`)

- **App** (React Native or native) — sign in (the app can use a session or paste
  an API key), an editor screen that drives `CheckController`, and account/usage
  screens hitting `/v1/account`, `/v1/usage`, `/v1/analytics`.
- **iOS keyboard extension** — a `UIInputViewController` that, on text change,
  calls `CheckController.onInput` (via a JS bridge or a native port of the same
  logic) and offers fix/rewrite chips above the keys. Requires **"Allow Full
  Access"** to make network calls.
- **Android IME** — an `InputMethodService` doing the same.

## Test

```bash
cd clients/mobile && npm test   # node --test: the shared core
```

## Privacy & store review — read before shipping the keyboard (flagged)

Keyboards that send typed text off-device get **extra App Store / Play Store
scrutiny** and must justify the "Full Access" / network permission:

- **Design for on-device where possible.** The platform's real-time check is
  already a **local rules pass** (no model round-trip) — port those rules into the
  keyboard so basic checking works **without sending text off-device**, and only
  call the gateway for explicit "rewrite" actions the user invokes.
- **Be explicit about data handling** in the app's privacy disclosure and the
  store listing: what is sent, when, and to where. The platform stores no
  document bodies (see `docs/PLATFORM.md`).
- **Never log keystrokes**; gate any network send behind an explicit user action
  or a clear, revocable setting.
- Get the data policy + keyboard permission justification reviewed by counsel
  before submission. This is engineering scaffolding, not legal advice.
