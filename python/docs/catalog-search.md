# Search the thoughts and text you've saved

Until this step, the catalog could save and fetch memories by ID, but the folder-search command didn't search those notes. We now have a dedicated catalog search backed by SQLite FTS5. It runs locally without loading CLIP or rerunning OCR.

## Try the complete loop

From the repository root, use a real image path and the IDs printed by the commands:

```sh
uv run --project python seenx-memory import "practice-images/my-screenshot.png"
uv run --project python seenx-memory note REVISION_ID \
  --note "Keep this spacing" --region 0.1 0.2 0.3 0.1
uv run --project python seenx-memory search --query "keep this spacing"
```

Search runs in a new process and still finds the saved note. The result includes its asset, revision, annotation, and region IDs; the matched field; an excerpt; provenance; and the normalized target. You can fetch the evidence afterward:

```sh
uv run --project python seenx-memory get ASSET_ID --revision REVISION_ID
```

To index visible words from the saved image, run the existing OCR command:

```sh
uv run --project python seenx-memory ocr REVISION_ID
uv run --project python seenx-memory search --query "words recognized in your screenshot"
```

OCR is explicit. Search doesn't automatically import a folder, infer a note, or run recognition. The older `seenx-search` command still searches a folder using its text/visual experiments. `seenx-memory search` searches the library's saved notes, selected text, and OCR observations. The two commands aren't fused yet.

## What is an index?

Think of an index at the back of a book: instead of reading every page to find a word, you look up the word and jump to the relevant pages.

Our authoritative records are the annotation and observation tables. We derive one searchable document for each nonempty note body, selected-text field, and OCR observation. FTS5 maintains a word-to-document index over those documents. We use its external-content mode: the searchable text lives in a normal table, while the FTS virtual table maintains the text-search structure.

```text
Saved notes / selections / OCR observations
                  ↓ database triggers
          Derived search documents
                  ↓ FTS5 index
       Matching source IDs and excerpts
```

This uses SQLite's built-in FTS5 module, not another server or a vector database. The project's current uv-managed Python has FTS5 available; an interpreter built without it gets an explicit migration error without losing existing catalog data. See [SQLite's FTS5 documentation](https://www.sqlite.org/fts5.html).

## Phrase versus all-terms search

Default search matches an adjacent token phrase, ignoring case and ordinary diacritics:

```sh
uv run --project python seenx-memory search --query "keep this spacing"
```

To require all supplied terms without requiring their order:

```sh
uv run --project python seenx-memory search --query "spacing keep" --match all
```

`Keep this spacing` matches the first phrase and the second all-terms query. The phrase `keep spacing` doesn't match because `this` is between the words.

FTS5 uses Unicode word tokens. Punctuation can separate tokens, so `connection-refused` can match `connection refused`. `test` doesn't match the longer token `testing`; this differs from our earlier folder substring search. The default tokenizer is not byte-exact identifier comparison, stemming, synonym expansion, or a semantic note encoder. These limits matter for technical identifiers and paraphrases.

We quote and escape the user's query fragments and bind them as SQL parameters. Words such as `OR`, wildcard characters, and quotes aren't exposed as an advanced query language. Punctuation follows tokenizer behavior rather than becoming executable SQL or FTS syntax.

Queries are limited to 512 characters, all-terms queries to 32 whitespace-separated fragments, and result limits to 1–100. No matching evidence normally returns an empty list.

## Results are evidence hits, not a file count

One screenshot can produce multiple matches: a note, a selected quote, and an OCR line. Those are distinct evidence records. Each result labels `matched_field` as `note`, `selected_text`, or `ocr`; the stable IDs tell you what actually matched.

OCR-derived text remains unverified. Matching a model's transcription doesn't confirm it is correct. A user's note is identified as user-authored; that is provenance, not proof of every statement in it. Quote corrections retain the distinction between old model output and a new user-authored selection.

The excerpt is plain text with square brackets around matches. It isn't trusted HTML or an instruction for an assistant to execute. Search returns compact evidence references, while `get` verifies the snapshot and returns the requested memory context.

Results use FTS5's BM25 ranking. Its numbers are ordered **lower first** and aren't probabilities. `score_kind` is `fts5-bm25` and `score_direction` is `lower_is_better`. Don't compare these scores with CLIP cosine similarity, the visual `0.25` cutoff, or rank-fusion scores. All returned evidence passed a text match; `--limit` doesn't fill the result list with unrelated suggestions.

## History and filtering

Historical revisions are included by default, so changing an original image doesn't make its saved thoughts disappear from search. Every result identifies the exact revision and says whether it is current.

```sh
uv run --project python seenx-memory search --query "spacing" --current-only
uv run --project python seenx-memory search --query "spacing" --asset ASSET_ID
uv run --project python seenx-memory search --query "spacing" --revision REVISION_ID --limit 5
```

These are local query filters, not assistant-access grants. The authorization boundary for a future service/MCP adapter remains separate work. Filenames, source paths, unimported files, and PDF contents aren't added to this catalog index in this step.

## Keeping results fresh

SQLite triggers update the derived documents and FTS index inside the same transaction as source writes. Editing a note removes its old terms. Changing selected text replaces its search document. Deleting a note removes its hits while retaining independent OCR evidence. Removing a memory removes its catalog search hits, including OCR, without changing other assets.

An indexing error rolls back the source edit too. That prevents a successful-looking edit from leaving mismatched search results. The tests inject a failure after the old index entry is removed and verify that both the old note and old search result survive rollback.

For an explicit rebuild of the derived text data:

```sh
uv run --project python seenx-memory reindex
```

This reconstructs search documents from the saved annotations and observations and refreshes FTS through the same triggers. Stable memory, revision, annotation, and observation IDs don't change. It isn't a recovery tool for a damaged SQLite file. The index can be rebuilt; your own notes can't be inferred again if the library itself is lost.

## Migration and engineering checks

Catalog version 3 adds the derived tables and triggers and backfills existing notes/selections/OCR observations. All pending migrations run under one write lock and commit together. Failure rolls back to the original version; retrying doesn't silently drop source data or change IDs. Existing version-1 and version-2 catalogs are covered by tests.

The tests cover restart retrieval, field provenance, Unicode and phrase behavior, operator escaping, bounds, history filters, edits, deletion, cross-asset isolation, index integrity, rebuilding, and migration failure. Search also verifies that derived hits still join to actual source records on the same revision; an orphan index entry isn't returned as evidence.

We additionally exercised import → note → search → edit → search → delete using existing images across separate CLI processes. Native OCR observations were searchable, reindex preserved results, and memory removal cleared the hits. Demo records were isolated in a temporary library and recognized contents weren't printed.

Logs include query length, matching mode, stage time, and result count, not raw queries or excerpts. The command's JSON response intentionally includes the requested excerpt and IDs.

## What to learn alongside this step

- `SQLite FTS5`: the full-text index and `MATCH` operator.
- `inverted index`: looking up words to find matching documents.
- `SQLite triggers`: automatically updating derived records when source rows change.
- `database transactions rollback`: why source edits and index updates succeed or fail together.
- `SQL joins`: combining matched documents with their original notes, revisions, and coordinates.
- `BM25 ranking`: ordering lexical matches without treating a score as confidence.
- `parameterized SQL queries`: keeping values separate from SQL syntax.

Next: define and evaluate the shared local engine search/fetch contract, then connect an interface. Visual catalog retrieval, semantic note paraphrases, word-level selection, and source/collection grants remain unfinished. This step adds lexical catalog retrieval, not proof of broad retrieval accuracy.
