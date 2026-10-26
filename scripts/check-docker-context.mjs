import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { existsSync, mkdtempSync, readdirSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, relative } from "node:path";

const target = mkdtempSync(join(tmpdir(), "seenx-context-check-"));
try {
  // Exercise Docker's actual ignore semantics; re-including a parent directory
  // can otherwise silently re-include its children.
  execFileSync("docker", ["build", "--file", "-", "--output", `type=local,dest=${target}`, "."], {
    input: "FROM scratch\nCOPY . /\n",
    stdio: ["pipe", "ignore", "pipe"],
    timeout: 60_000,
  });
  for (const path of [".git", ".venv", "python", "models", "practice-images", "apps/macos", "apps/web/out", "apps/web/.next"]) {
    assert.equal(existsSync(join(target, path)), false, `${path} must not enter the Docker build context`);
  }
  const forbidden = [];
  function inspect(directory) {
    for (const entry of readdirSync(directory, { withFileTypes: true })) {
      const path = join(directory, entry.name);
      if (/^(?:\.env(?:\..*)?|\.venv|venv|node_modules|__pycache__)$/.test(entry.name) || /\.(?:key|pem)$/.test(entry.name)) {
        forbidden.push(relative(target, path));
      }
      if (entry.isDirectory()) inspect(path);
    }
  }
  inspect(target);
  assert.deepEqual(forbidden, [], "credential files and local environments must stay out of the context");
  console.log("Docker context passed: no personal data, credentials, native app, or local build output.");
} finally {
  rmSync(target, { recursive: true, force: true });
}
