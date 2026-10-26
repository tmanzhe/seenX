# Security review — 2026-10-26

Scope: repository history, website dependencies and deployment configuration, the local Python dependency environment, catalog query construction/model loading, and the new static web container. This is a focused engineering review, not a penetration test or a security certification of the unfinished native app or future assistant service.

## Findings addressed

| Area | Finding | Change and verification |
| --- | --- | --- |
| Python image handling | Installed Pillow 12.3.0 had 37 reported audit entries; the dependency range excluded its patched major version. | Require Pillow 13.x and lock 13.0.0. Python tests pass. |
| Optional visual retrieval | Installed Transformers 4.57.6 had 9 reported audit entries; the dependency range excluded patched 5.x releases. Some entries refer to model/training/conversion paths this app does not use. | Require Transformers >=5.10,<6 and lock 5.20.2. Adapt CLIP to structured projected outputs and explicitly disable remote code. Cached image/text encoding was checked offline. |
| Initial container base | The full Nginx image reported three high-severity findings in Brotli/cURL packages. | Select the digest-pinned slim unprivileged variant. The final runtime image scan reports zero high/critical findings. |
| Website response headers | No shared deployment header policy was configured. | Add matching Nginx/Vercel policies for MIME sniffing, framing, referrers, device permissions, embedded objects, base URLs, and form submissions. Automated parity checks and HTTP smoke checks cover successful routes, assets, and 404s. |
| Build/runtime exposure | A broad Docker context could include local libraries, models, and environments. | Use a default-deny build context and multi-stage static export. Exported context inspection found no personal-data directories or credential files. Runtime inspection confirmed UID 101, a read-only filesystem, dropped capabilities, no privilege escalation, and no application source/dependency tree. |

Pillow's [13.0.0 release notes](https://pillow.readthedocs.io/en/stable/releasenotes/13.0.0.html) document the security fixes. The Transformers [security guidance](https://github.com/huggingface/transformers/security) recommends safetensors; this project already requires safetensors, pins the model revision, and defaults to local files. The upgrade preserves those constraints. See also the [Transformers path-traversal advisory](https://github.com/advisories/GHSA-xrqw-3rrv-vx5w).

## Checks and results

- `npm audit` and `npm audit --omit=dev`: no known vulnerabilities reported.
- `pip-audit` 2.10.1 against the updated installed macOS environment: no known vulnerabilities reported. The editable seenX package is excluded from package-advisory matching; its code was reviewed separately.
- Exported, hashed uv requirements with all extras, audited without installing them: no known vulnerabilities reported for this host's environment markers.
- Gitleaks 8.30.1, redacted, across the available Git history: no leaks detected. The pinned scanner container was also exercised with network disabled and a read-only checkout.
- Trivy 0.76.1 against the final web runtime image with the refreshed advisory database: no high/critical findings.
- 90 Python tests; 19 web unit tests; 3 security-configuration tests; website type checking and production build: passed.
- Docker Compose startup and health check, clean nested routes, hydration-script delivery/cache headers, 404s, and response-header checks: passed. Browser interaction confirmed the static page hydrated and the sample search responded.
- GitHub Actions workflow validation with Actionlint 1.7.12: passed.

The [checks workflow](../.github/workflows/checks.yml) repeats package audits, tests, container build/smoke/image checks, and secret scanning on changes and weekly. It uses read-only permissions, full commit pins for actions, timeouts, and no persisted checkout credentials. [Dependabot](../.github/dependabot.yml) proposes dependency and base-image updates. Findings are not hidden with audit ignores or `continue-on-error`.

## Code boundaries checked

Catalog search binds query/filter values as SQL parameters and quotes FTS fragments rather than exposing raw SQL/FTS syntax. Existing tests cover operator escaping, bounded queries/results, cross-asset isolation, and orphan index records. Snapshot filenames require a 64-character lowercase hash and fetched objects are hash-verified. Image targets are validated against normalized coordinates. These local query filters are not an authorization system for a future network service.

The website renders notes as React text and has no upload endpoint, assistant endpoint, arbitrary command execution, or model loader. The runtime container serves static exports only; Python, originals, model files, and memory databases are not present or mounted.

## Remaining limits

- Local memory libraries and browser notes are not encrypted application vaults. OS account/device protections and deliberate backups still matter. This work does not implement assistant grants, portable encrypted archives, native signing, or notarization.
- The CSP restricts embedding, objects, base URLs, and forms; it is not a strict script allowlist. Static Next.js pages contain inline hydration scripts. Strict script enforcement requires tested per-page hashes or a move to dynamic rendering with nonces. No permissive `unsafe-eval` policy was added.
- Docker is bound to localhost over HTTP. Public hosting needs an HTTPS terminator and its TLS/HSTS policy. Vercel header changes take effect when that configuration is deployed; they were verified here in the container rather than claimed to be live.
- Linux CI does not exercise actual Apple Vision, global shortcuts, screen capture, GPU inference, or the interactive native app. Model relevance and untrusted-file resource exhaustion require further workload-specific evaluation.
- Audits reflect known advisory data at scan time and can miss unknown vulnerabilities or compromised releases. Image digest pinning and lockfile hashes fix artifact identity; scheduled scanning and reviewed updates remain necessary.

See [development instructions](development.md) for repeatable commands.
