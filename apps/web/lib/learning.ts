// Keep the shared build journal here. Personal reflections stay in the browser.
export const learningUpdated = "2026-10-25";

export const buildJournal = [
  {
    id: "purpose",
    kind: "The idea",
    title: "Find the image I remember seeing.",
    detail: "seenX is a local-first Mac app for finding screenshots and saved images through visible text, visual descriptions, and available metadata. Selected folders stay under the user’s control.",
    takeaway: "Text in a screenshot, what an image looks like, and where it was taken are different kinds of evidence.",
  },
  {
    id: "boundaries",
    kind: "Architecture decision",
    title: "Give each part one clear responsibility.",
    detail: "SwiftUI is the intended native interface and owns macOS permissions and platform APIs. A shared contract will connect the native app to proven catalog and retrieval behavior. This Next.js website explains the project. Python is for experiments, not a required app runtime.",
    takeaway: "The website’s sample search is an interaction preview. It does not run an embedding model or search personal files.",
  },
  {
    id: "experiment-first",
    kind: "Implemented baseline",
    title: "Try semantic search in Python first.",
    detail: "Python now has file readers, OCR, cached extraction, and a pinned CLIP baseline. One command supports text, visual, and hybrid search. Visual candidates must pass a configurable similarity cutoff. Native integration follows measured retrieval results.",
    takeaway: "A useful experiment answers a specific question. It does not need the desktop app, a database, or an engine bridge.",
  },
  {
    id: "real-images",
    kind: "Evaluation decision",
    title: "Use my own images, starting with ten.",
    detail: "The ignored practice-images folder contains our own images and a PDF. There is no need to generate sample images. The initial collection checks the pipeline; a larger labeled collection is still needed to measure retrieval quality.",
    takeaway: "Write descriptions and acceptable matches before inspecting search results. Include difficult screenshot queries that may need OCR.",
  },
  {
    id: "learning-pace",
    kind: "Working agreement",
    title: "Understand one step before adding the next.",
    detail: "The full plan felt like too much at once. The agreed pace is to explain the next idea, make one small change, inspect it together, and pause for review and approval before continuing.",
    takeaway: "Understanding the change is part of finishing the step. The Python README explains the current commands, caching, logging, and accuracy limits; the walkthrough follows each implementation step.",
  },
];

export const experimentSteps = [
  {
    title: "Set up the Python project",
    summary: "A separate place for the experiment and its dependencies.",
    explanation: "The Python project lives in python/, with source in src/seenx and separate tests. Run uv sync --project python --all-extras from the repository root. uv creates the isolated environment and installs the versions recorded in uv.lock. No manual activation is needed.",
    done: "Implemented: Python 3.13.7, package entry points, and a locked uv environment. The Python README has the commands and folder map.",
  },
  {
    title: "Load ten of my images",
    summary: "See the inputs before asking a model to interpret them.",
    explanation: "seenx-inspect reads supported images and PDFs from the ignored practice-images folder. It prints dimensions, PDF page counts, and text availability without creating thumbnails. Unreadable files are reported and skipped.",
    done: "Implemented and checked with eight images and a two-page PDF. Original files are only read.",
  },
  {
    title: "Load one pretrained model",
    summary: "Use a model that already knows how to relate images and text.",
    explanation: "The baseline is openai/clip-vit-base-patch32 with its matching image processor and text tokenizer at a pinned revision. Assets live in ignored models/. The current baseline runs on CPU and was checked offline after download. This is inference, not training.",
    done: "The model loads locally and we know which revision and device we are using.",
  },
  {
    title: "Create the image embeddings",
    summary: "Represent each image as a list of numbers.",
    explanation: "The image encoder produces a normalized vector for each image. Optional SQLite caching saves vectors between runs, checking file timestamps, size, and reader identity before reuse. Cached extraction does not change the model weights.",
    done: "Each readable image has a normalized embedding connected to the correct file path.",
  },
  {
    title: "Search with a description",
    summary: "Compare the query vector with every image vector.",
    explanation: "The matching text encoder embeds the description. Cosine similarity ranks images, then a configurable cutoff rejects weaker suggestions. --top-k is a maximum rather than a requirement to fill five slots. The command prints paths and scores; a score is not confidence.",
    done: "Implemented: text, visual, and hybrid modes with source-method explanations. Cached image vectors can be reused while each query is encoded again.",
  },
  {
    title: "Measure the results",
    summary: "Check usefulness across queries, not just one good example.",
    explanation: "Expand to 50–200 mixed images. Label 10–15 descriptions and acceptable matches before running them. Record the percentage of queries with an acceptable result in the top five, indexing time, and warm query latency. Include objects, colors, scenery, screenshot appearance, and exact-text cases.",
    done: "We have recorded successes, failures, and timings on the same labeled collection.",
  },
  {
    title: "Rerun offline and write the findings",
    summary: "Leave evidence that another run can reproduce.",
    explanation: "After the initial downloads, rerun with networking disabled. Record hardware, device, dependency versions, the exact model revision, collection size, successful queries, and failures. Keep personal images, model assets, and notebook outputs out of commits.",
    done: "A short report explains what worked, what did not, and which retrieval step to improve next before native integration.",
  },
];

export const learningConcepts = [
  { term: "Ontology", meaning: "Explicit concepts and relationships, such as Receipt, Trip, and associated-with. Facts populate this model; evidence establishes whether an association is justified." },
  { term: "Model-assisted learning", meaning: "A pretrained model proposes facts and people correct them. Stored knowledge changes without retraining model weights. Keep source evidence and confirmation status." },
  { term: "Prototype-to-production parity", meaning: "Check the production implementation against the prototype using the same inputs, preprocessing, model revision, and labeled queries." },
  { term: "Virtual environment", meaning: "A separate set of Python packages for one project, so its dependencies do not interfere with other projects." },
  { term: "Notebook", meaning: "A document with explanations and runnable code cells. Run a small piece, inspect its output, then continue. Restarting and running all cells checks that it works in order." },
  { term: "Embedding", meaning: "A vector: a list of numbers representing information extracted from an image or text. It is not a written caption. Compatible encoders let us compare the two." },
  { term: "Preprocessing", meaning: "Preparing inputs in the format the model expects, such as resizing and normalizing image pixels or turning query text into tokens." },
  { term: "Inference", meaning: "Running an already trained model on a new input. Training changes model weights; this experiment only uses the existing weights." },
  { term: "Cosine similarity", meaning: "A comparison of vector directions. Once both vectors have length one, their dot product gives this score. It helps rank matches; it is not a probability." },
  { term: "Exact search", meaning: "Compare the query with every image embedding. It is a straightforward baseline for this small collection, with no vector database needed." },
  { term: "OCR vs. semantic search", meaning: "OCR extracts visible words. Semantic search compares learned image and text representations. An image can match a description without containing those words; exact screenshot text may still need OCR." },
  { term: "Metadata", meaning: "Recorded details such as a date, filename, or GPS location. Missing metadata stays unknown. A model’s visual guess is different from a recorded fact." },
  { term: "Top-five hit rate", meaning: "The percentage of labeled queries with at least one acceptable image in the first five results. Expected matches are chosen before inspecting the ranking." },
];
