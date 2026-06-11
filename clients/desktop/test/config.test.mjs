import { test } from "node:test";
import assert from "node:assert/strict";
import { isValidUrl, resolveAppUrl, windowOptions } from "../src/config.js";

test("isValidUrl accepts http(s) only", () => {
  assert.equal(isValidUrl("https://app.example"), true);
  assert.equal(isValidUrl("http://localhost:8000"), true);
  assert.equal(isValidUrl("ftp://x"), false);
  assert.equal(isValidUrl("not a url"), false);
});

test("resolveAppUrl prefers env, falls back, and rejects bad URLs", () => {
  assert.equal(resolveAppUrl({ WB_APP_URL: "https://app.example" }), "https://app.example");
  assert.equal(resolveAppUrl({}), "http://localhost:8000");
  assert.throws(() => resolveAppUrl({ WB_APP_URL: "garbage" }));
});

test("windowOptions are secure by default", () => {
  const o = windowOptions();
  assert.equal(o.webPreferences.contextIsolation, true);
  assert.equal(o.webPreferences.nodeIntegration, false);
});
