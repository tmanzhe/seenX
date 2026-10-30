# Library archives

Run from the repository root; restore requires a new destination path.

```sh
uv run --no-sync --project python seenx-memory --library /path/to/library export /path/to/library.zip --mode complete  # or context-only
uv run --no-sync --project python seenx-memory verify /path/to/library.zip
uv run --no-sync --project python seenx-memory --library /path/to/new-library restore /path/to/library.zip  # optionally: --original-folder /path/to/originals
uv run --no-sync --project python seenx-memory --library /path/to/library verify
```
