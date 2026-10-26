import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const root = new URL("../", import.meta.url);
const read = (path) => readFileSync(new URL(path, root), "utf8");
const vercel = JSON.parse(read("vercel.json"));
const headers = Object.fromEntries(vercel.headers.find((rule) => rule.source === "/(.*)").headers.map(({ key, value }) => [key, value]));

test("Docker and Vercel enforce the same security headers, including errors", () => {
  const nginx = Object.fromEntries([...read("docker/security-headers.conf").matchAll(/add_header\s+([\w-]+)\s+"([^"]+)"\s+always;/g)].map((match) => [match[1], match[2]]));
  assert.deepEqual(nginx, headers);
  assert.equal(headers["X-Content-Type-Options"], "nosniff");
  assert.equal(headers["X-Frame-Options"], "DENY");
  assert.match(headers["Content-Security-Policy"], /frame-ancestors 'none'/);
  assert.match(headers["Content-Security-Policy"], /object-src 'none'/);
  assert.match(read("docker/nginx.conf"), /include \/etc\/nginx\/security-headers\.conf;/);
});

test("container runtime uses pinned bases and a non-root static server", () => {
  const dockerfile = read("Dockerfile");
  const bases = [...dockerfile.matchAll(/^FROM (\S+)/gm)].map((match) => match[1]);
  assert.equal(bases.length, 3);
  for (const base of bases.filter((base) => base !== "dependencies")) assert.match(base, /@sha256:[a-f0-9]{64}$/);
  const runtime = dockerfile.split(/AS runtime\n/)[1];
  assert.match(runtime, /USER 101:101/);
  assert.match(runtime, /COPY --from=builder \/app\/apps\/web\/out/);
  assert.doesNotMatch(runtime, /COPY (?:\. |apps\/web |python)/);
});

test("personal data and credentials are excluded from the Docker build context", () => {
  const rules = read(".dockerignore").split(/\r?\n/).filter((line) => line && !line.startsWith("#"));
  assert.equal(rules[0], "**");
  assert.ok(!rules.some((rule) => /^!(?:python|models|practice-images|\.git|\.venv)(?:\/|$)/.test(rule)));
  for (const rule of ["**/.env", "**/.env.*", "**/.venv", "**/node_modules", "**/*.pem", "**/*.key"]) assert.ok(rules.includes(rule), rule);
});
