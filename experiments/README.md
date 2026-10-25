# seenX experiments

**Status:** The first Python script reads existing images and PDFs. Model setup and retrieval are not implemented yet.

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

## Inspect your first ten files

Install the project dependencies in the activated environment:

```sh
python -m pip install -e .
python load_images.py ../practice-images
```

Put PNG, JPEG, or PDF files in the repository-root `practice-images/` folder first, or pass the path to another folder. The script reads the immediate folder, processes up to ten supported files in filename order, and skips unreadable files. The limit counts successfully processed files, not PDF pages. Use `--limit 5` to try fewer files. It also supports WebP, BMP, and TIFF; HEIC is not supported yet.

Read the terminal output: each image's filename, stored pixel dimensions, and format are printed. Dimensions describe the stored pixels before any orientation metadata is applied. For PDFs, pypdf reports page count and the number of extracted text characters per page, without printing the text itself. Pages with no extracted text may need OCR, which is not implemented. Encrypted PDFs are skipped. The script only reads files; it does not create images, thumbnails, or a manifest.

Python topics to learn alongside this step: **functions and parameters**, **if/elif branching**, **with statements**, **enumerate**, and **exception handling**. The two reader functions keep image and PDF handling separate; the command-line loop chooses a reader by file extension. `enumerate(..., start=1)` supplies human-readable page numbers. No model is involved yet.

Record the inputs, model version, procedure, and results so an experiment can be repeated. Personal image collections, downloaded model assets, and generated outputs must stay outside version control. The repository-root `practice-images/` folder is an ignored option for inputs.

See the [architecture](../docs/architecture.md) and [implementation plan](../plan.md).
