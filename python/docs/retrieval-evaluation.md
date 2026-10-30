# Labeled folder retrieval evaluation

`seenx-eval` compares **lexical**, **visual**, and **hybrid** modes by calling the
existing `search_files()` function for each judged query. Lexical maps to folder
`--mode text`: normalized literal phrases in PDF text and, with `--ocr`, image
OCR. It does not call catalog FTS5, retrieve notes, or embed note paraphrases.
Visual uses the current CLIP cosine cutoff; hybrid uses the existing rank fusion.
The evaluator does not change scores, thresholds, ties, ordering, or fusion.

From the repository root, after installing the existing dependencies and model:

```sh
uv run --project python seenx-eval practice-images --labels python/eval/practice-images.starter.json --k 1 5 10 --ocr --cache
```

This is the exact comparison command for a Mac with the practice collection and
the pinned model already installed. All three modes run by default. JSON goes to
stdout; reader/model progress and skipped-file/OCR diagnostics go to stderr.
Redirect stdout to retain a report. The evaluator itself does not configure
persistent diagnostic logs. `--cache` uses the existing local extraction and
embedding cache; omit it to avoid writing cache records.

For a lexical-only run without visual dependencies/model files:

```sh
uv run --project python seenx-eval practice-images --labels python/eval/practice-images.starter.json --modes lexical --k 1 5 10
```

Without `--ocr`, images supply no lexical text; filenames are never searched.
Image OCR needs macOS Vision and the `ocr` extra. Visual/hybrid image retrieval
needs the `visual` extra (PyTorch and Transformers), plus the separately downloaded
`openai/clip-vit-base-patch32` model and processor at revision
`c7244be81152024ce0e99ac8d2e373a8953d9f9a`. Those assets are not committed; the
existing encoder stores them in ignored `models/huggingface/`. Model loading is
offline by default. Add `--download-model` to explicitly allow its download.
See the [setup instructions](../README.md#start-here-uv-manages-the-environment).

`--min-score` forwards the existing visual cutoff (default `0.25`). Record any
override when comparing reports. It is a cosine threshold, not a probability.

## Version-1 label format

A UTF-8 JSON object contains `version: 1`, a nonblank `name`, a `status` of
`starter` or `reviewed`, and a nonempty `queries` array. Each judged query requires:

| Field | Meaning |
| --- | --- |
| `id` | Unique, nonblank query ID |
| `query` | Nonblank text passed unchanged to retrieval |
| `relevant_ids` | Array of all judged relevant image/page IDs; `[]` explicitly asserts no match |
| `evidence` | Nonblank explanation of the file inspection or metadata supporting the judgment |

An image ID is its exact, case-sensitive filename relative to the input folder,
for example `capture.png`. A PDF-page ID is `document.pdf#page=2`, using a
canonical one-based integer. These are portable folder evidence IDs, not catalog
UUIDs. Subdirectories, absolute paths, `..`, and filenames containing `#page=`
are unsupported. Missing labeled files fail evaluation before model loading;
annotators must verify PDF page numbers against the document.

For illustration only, **not labels for files known to be in this repository**:

```json
{
  "version": 1,
  "name": "Example independently reviewed collection",
  "status": "reviewed",
  "queries": [
    {
      "id": "booking-phrase",
      "query": "train booking",
      "relevant_ids": ["capture.png", "tickets.pdf#page=2"],
      "evidence": "An annotator verified this phrase in these two files."
    },
    {
      "id": "absent-object",
      "query": "a purple submarine",
      "relevant_ids": [],
      "evidence": "An annotator reviewed the full collection and found no relevant item."
    }
  ]
}
```

Optional `description` and `pending_queries` metadata describe limitations and
unjudged work. Pending entries are never searched or scored; a missing judgment
must not be represented by `relevant_ids: []`. Extra query metadata such as a
category is allowed. Empty evidence, duplicate query IDs, duplicate relevant IDs,
and malformed IDs are rejected.

This initial format evaluates **whole images and PDF pages**. The existing folder
ranker has no region or annotation results. Do not credit a parent image as a hit
for a saved-region ID; catalog region UUIDs are rejected. Region intent and note
paraphrases require verified catalog labels and a later evaluator over those
retrieval surfaces.

## What the starter set establishes

[`practice-images.starter.json`](../eval/practice-images.starter.json) is a
**metadata-only, provisional starter**, not a benchmark. `practice-images/` is
ignored by Git and absent from the implementation checkout. No real filenames,
region IDs, OCR transcriptions, or note labels could be inspected.

The only scored query is `a submarine underwater`, with no relevant IDs. The
existing README calls it unrelated to the practice collection; walkthrough
section 9 records that exact query and zero accepted results. Its judgment rests
on the documented collection context, not an inference that every below-cutoff
result is irrelevant. Revalidate it against the actual folder before relying on
it as ground truth.

The same walkthrough says the basketball and laptop positives were visually
checked, but records no file identities. They are retained as **pending** queries
until the actual image filenames and complete relevant sets can be verified.
The starter therefore reports `null` recall and MRR, alongside meaningful
no-match counts. It cannot support a positive retrieval-quality claim or a
fusion/embedding choice. Populate positive labels from the real files before
using those metrics to compare modes. No synthetic images or guessed labels were
added.

## Metrics and comparison assumptions

For a query with relevant ID set `R` and accepted ranked results `L`:

- **Recall@k** is `|set(L[:k]) intersect R| / |R|`. Repeated IDs cannot inflate
  hits. A relevant item not retrieved contributes a miss, including when fewer
  than `k` results pass the existing cutoff.
- **Reciprocal rank** is `1 / rank` of the first relevant result, or zero if none
  is retrieved. **MRR** is its mean across positive queries. It uses the full
  accepted ranking, not just the largest requested `k`.
- Aggregate recall is a macro mean: each positive query has equal weight,
  regardless of the size of its relevant set.
- No-match queries have undefined recall/reciprocal rank and are excluded from
  those means. Their report counts correct empty responses and false-positive
  responses (any nonempty result), plus the false-positive query rate. Undefined
  means/rates are JSON `null`, never a fabricated zero or perfect score.

The dependency-free `seenx.statistics.wilson_interval(hits, total, confidence=0.95)`
returns two-sided Wilson score bounds, or `None` for zero trials. Per-query
`recall_at_k_estimates[k]` puts `value`, distinct `hits`, `total`, and the 95%
`interval: [lower, upper]` together next to the existing numeric `recall_at_k`.
Summary `micro_recall_at_k[k]` uses the same shape after pooling query hit/total
counts. Existing macro `recall_at_k` and MRR remain unchanged; neither is a
binomial proportion, so no Wilson interval is attached to those macro means.
No-match queries have null recall/interval and do not enter the pooled counts.
These are descriptive intervals under independent relevant-item trials, not
dataset-wide quality guarantees: repeated items and correlated queries can make
them optimistic. `confidence_intervals` records the method, confidence, and scope.

Evaluation scans **all supported files at the top level** of the selected folder,
instead of inheriting the interactive ten-file default. It requests the full
accepted ranking from the existing search function. Visual mode searches images
only; lexical/hybrid can additionally retrieve PDF pages. PDF relevance judgments
remain in the denominator for visual mode and count as misses there. A visual
comparison requires at least one supported image. The same model instance is
reused across image queries and modes; this is not a latency benchmark.

Reports include query judgments and returned IDs, scores and method evidence,
the input filename list, OCR/cache/cutoff settings, runtime/platform, and model
revision/encoder cache key when a model is used. Keep reports local if labels or
filenames are sensitive. They do not snapshot input bytes; keep the corpus
unchanged across comparisons and re-review labels when it changes. Inspect stderr
for skipped files and OCR failures, which the existing readers report while
continuing with readable inputs. A run that cannot read any selected input fails.

Expand this starter with independently reviewed exact phrases, visual
descriptions, and genuine no-match cases. Add catalog note/region evaluations
when their candidate surfaces exist. Compare errors and coverage before choosing
catalog fusion or a semantic note encoder; indexing cost, warm latency, resource
use, and a larger held-out collection remain separate follow-up measurements.

Metric arithmetic tests are in `tests/test_retrieval_metrics.py`; orchestration
and format checks are in `tests/test_retrieval_eval.py`. They use explicit IDs and
mocked retrieval, with no private images or model downloads.
