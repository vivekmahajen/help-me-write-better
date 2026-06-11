# @help-me-write-better/sdk

JS/TS client for the help-me-write-better API. Ships as ESM JavaScript with
TypeScript declarations — works from both JS and TS with no build step. Targets
the OpenAPI contract served at `GET /v1/openapi.json`.

## Install

```bash
npm install @help-me-write-better/sdk
```

Requires Node 18+ (uses the global `fetch`). In other environments, pass a
`fetch` implementation.

## Usage

```ts
import { WriteBetterClient } from "@help-me-write-better/sdk";

const client = new WriteBetterClient({
  apiKey: process.env.WB_API_KEY!,
  baseUrl: "https://your-deployment.example",
});

// Improve text (metered + capped server-side)
const res = await client.improve({ text: "their going to the store", services: "correct" });
console.log(res.text, res.quota.premium_remaining);

// Saved documents
const doc = await client.createDocument("first draft", "My note");
await client.addVersion(doc.id, "second draft");
const versions = await client.listVersions(doc.id);

// Preferences + usage
await client.setPreferences({ default_tone: "friendly" });
const usage = await client.getUsage();
```

Errors throw `WriteBetterError` with `.status`, `.code`, and `.body` (e.g. a
`402` with `code: "cap_reached"` when the plan cap is hit).

## API

`improve`, `getAccount`, `getUsage`, `getHistory`, `getPreferences`,
`setPreferences`, `listDocuments`, `createDocument`, `getDocument`,
`renameDocument`, `deleteDocument`, `listVersions`, `addVersion`.

## Test

```bash
npm test   # node --test, dependency-free, uses a mock fetch (no network)
```
