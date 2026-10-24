# seenX experiments

**Status:** Python project configuration is available. Image loading, model setup, and retrieval are not implemented yet.

This is the current development focus: learn in Python and build a proof of concept before implementing proven behavior in Rust. SwiftUI follows later. Experiments include:

- Comparing local image and text embedding models.
- Checking preprocessing and image/text encoder compatibility.
- Evaluating retrieval quality with labeled example queries.
- Measuring inference costs on representative inputs.
- OCR, metadata, and hybrid retrieval.
- Ontology relationships with provenance, model proposals, and user corrections.

Python is initially a development tool, not a required application runtime. An experiment's results may inform the native implementation without making its Python dependencies part of the shipped app.

## First step: an isolated environment

From this directory, use Python 3.13 or newer:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -c "import sys; print(sys.executable); print('Isolated:', sys.prefix != sys.base_prefix)"
```

The executable should be inside `experiments/.venv/` and `Isolated` should be `True`. A virtual environment gives this experiment its own packages without changing the base Python installation. The environment is ignored by Git; `pyproject.toml` records the project requirements. No third-party packages or models are required for this setup step.

Next, choose a folder of ten images. We will add image loading and thumbnails as a separate change, introducing the needed dependency then. Do not install the full model stack yet.

Record the inputs, model version, procedure, and results so an experiment can be repeated. Personal image collections, downloaded model assets, and generated outputs must stay outside version control. The repository-root `practice-images/` folder is an ignored option for inputs.

See the [architecture](../docs/architecture.md) and [implementation plan](../plan.md).
