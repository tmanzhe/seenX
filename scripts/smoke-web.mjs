import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const origin = new URL(process.env.SEENX_URL ?? "http://127.0.0.1:8080");
const config = JSON.parse(readFileSync(new URL("../vercel.json", import.meta.url), "utf8"));
const headers = config.headers.find((rule) => rule.source === "/(.*)").headers;

async function request(path, status) {
  const response = await fetch(new URL(path, origin), { signal: AbortSignal.timeout(5000) });
  assert.equal(response.status, status, `${path}: status`);
  for (const { key, value } of headers) assert.equal(response.headers.get(key), value, `${path}: ${key}`);
  return response;
}

const home = await request("/", 200);
assert.match(home.headers.get("content-type"), /text\/html/);
const html = await home.text();
assert.match(html, /seenX/);
for (const path of ["/docs", "/docs/architecture", "/learning", "/healthz"]) await request(path, 200);
for (const path of ["/does-not-exist", "/.env", "/python/library/catalog.sqlite3"]) await request(path, 404);

const script = html.match(/<script[^>]+src="([^"]+)"/);
assert.ok(script, "home page includes a hydration script");
const asset = await request(script[1], 200);
assert.match(asset.headers.get("content-type"), /javascript/);
assert.match(asset.headers.get("cache-control"), /max-age=31536000/);
console.log("Container smoke checks passed: clean routes, static assets, 404s, and security headers.");
