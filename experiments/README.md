# seenX experiments

**Status:** implementation has not started. This directory contains documentation only.

This is the current development focus: learn in Python and build a proof of concept before implementing proven behavior in Rust. SwiftUI follows later. Experiments include:

- Comparing local image and text embedding models.
- Checking preprocessing and image/text encoder compatibility.
- Evaluating retrieval quality with labeled example queries.
- Measuring inference costs on representative inputs.
- OCR, metadata, and hybrid retrieval.
- Ontology relationships with provenance, model proposals, and user corrections.

Python is initially a development tool, not a required application runtime. An experiment's results may inform the native implementation without making its Python dependencies part of the shipped app.

Create an isolated Python environment and select dependencies when the first experiment is defined. Record the inputs, model version, procedure, and results so an experiment can be repeated. Personal image collections and downloaded model assets must stay outside version control; add specific ignore rules when their locations are chosen.

See the [architecture](../docs/architecture.md) and [implementation plan](../plan.md).
