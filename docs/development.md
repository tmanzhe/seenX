# Development and automated checks

The repository has three separate parts: a static Next.js website, a Python retrieval reference, and a native Mac app. Docker builds and serves the website. Xcode builds the native app on macOS; Linux containers cannot replace Apple's SDKs or screen-capture permissions.

## Website with Docker

From the repository root, with Docker Desktop or Docker Engine and Compose running:

```sh
docker compose up --build
```

Open <http://127.0.0.1:8080>. Stop with Ctrl+C, then remove the stopped container and network with `docker compose down`. To choose another local port, run `SEENX_PORT=8081 docker compose up --build`. The host port binds only to the local machine.

The multi-stage [Dockerfile](../Dockerfile) installs the npm lockfile, checks TypeScript, runs the unit tests, and exports the website. Its final image contains Nginx and static pages; Node.js, npm packages, and source code stay in the builder. Both base images are pinned by digest. The slim unprivileged Nginx image avoids unnecessary modules and the vulnerable packages found in the initial full image.

[.dockerignore](../.dockerignore) allows only website sources and necessary configuration into the build context. Python environments, image collections, model downloads, memory libraries, Git metadata, and environment files are excluded. No personal-data volume is mounted. Browser sample notes live in the browser's storage for this origin; changing ports or hosts creates a different browser origin.

Run `node scripts/check-docker-context.mjs` to inspect an exported build context using Docker's actual ignore rules. CI repeats this check so a future parent-directory allow rule cannot silently include native sources or personal data.

[Compose](../compose.yaml) runs UID/GID 101 with a read-only root filesystem, all Linux capabilities dropped, no privilege escalation, a small temporary filesystem, and CPU/memory/process limits. The health check uses `/healthz`. This is a local HTTP preview; use an HTTPS reverse proxy and appropriate TLS/HSTS settings before exposing the container publicly.

After starting it:

```sh
node scripts/smoke-web.mjs
```

This checks clean documentation routes, static JavaScript and its cache policy, missing-file responses, and security headers on success and error responses.

## Without Docker

Use Node.js 24, matching [.node-version](../.node-version):

```sh
npm ci
npm run dev
npm run check
npm audit --audit-level=moderate
```

`check` verifies shared security configuration, checks TypeScript, runs the 19 web regression tests, and produces the static export. Docker performs the TypeScript, unit-test, and export steps inside its Linux builder. Development mode uses the Next.js dev server; HTTP security headers are supplied by Nginx or Vercel when serving the static export.

## Python

The single project environment remains `python/.venv`:

```sh
uv sync --project python --locked --all-extras
uv run --project python python -B -m unittest discover -s python/tests -v
```

OCR support is macOS-only. CI installs base dependencies on Linux and tests OCR/model interfaces with mocks, without personal inputs, model downloads, or GPU packages. The local security upgrade was additionally exercised with the cached CLIP model and an existing image, offline. Transformers 5 returns projected features through `pooler_output`; tests protect the image/text encoding boundary.

To audit the locked dependency set, including optional visual support, without installing those extras:

```sh
uv export --project python --locked --all-extras --no-emit-project --output-file /tmp/seenx-requirements.txt > /dev/null
uvx --from pip-audit==2.10.1 pip-audit --requirement /tmp/seenx-requirements.txt --disable-pip --require-hashes
```

The audit evaluates environment markers for its host OS. The installed macOS environment was separately audited to cover its platform packages.

## CI and updates

[GitHub Actions](../.github/workflows/checks.yml) runs on pushes to main, pull requests, manual dispatch, and weekly:

- Website checks and npm audit, including development dependencies.
- Python tests and a hashed-lockfile audit, including optional packages.
- Docker build, restricted startup, HTTP smoke checks, and a Trivy high/critical vulnerability gate.
- Redacted full-history secret scanning with Gitleaks in an offline container with a read-only checkout.

Actions are pinned to full commit hashes. Tokens have read-only repository access and are not persisted in the checkout. Jobs have timeouts; older runs for the same ref are canceled. There is no automatic deployment, package publication, or merge step.

[Dependabot](../.github/dependabot.yml) proposes weekly npm, uv, Docker-base, and Actions updates. Review the generated changes and CI results; digest pinning fixes an image's identity but does not make future vulnerability checks unnecessary. The scanner CLI versions and Gitleaks image digest in the workflow should also be reviewed during tooling updates.

For native development, follow [the Mac app instructions](../apps/macos/README.md).
