// Keep the shared build journal here. Personal reflections stay in the browser.
export const learningUpdated = "2026-10-24";

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
    detail: "SwiftUI is the intended native interface and owns macOS permissions and platform APIs. Rust is the reusable catalog and retrieval engine. This Next.js website explains the project. Python is for experiments, not a required app runtime.",
    takeaway: "The website’s sample search is an interaction preview. It does not run an embedding model or search personal files.",
  },
  {
    id: "experiment-first",
    kind: "Next milestone",
    title: "Try semantic search in Python first.",
    detail: "Python is the learning and proof-of-concept stage for retrieval, OCR, metadata, and ontology. Rust implementation follows measured results; SwiftUI comes later. Start with one pretrained CLIP baseline and a notebook showing the top five matches.",
    takeaway: "A useful experiment answers a specific question. It does not need the desktop app, a database, or a Rust bridge.",
  },
  {
    id: "real-images",
    kind: "Evaluation decision",
    title: "Use my own images, starting with ten.",
    detail: "A real image collection is available; its folder path has not been selected yet. There is no need to generate sample images. Start with ten files to check the pipeline, then use 50–200 mixed images for evaluation.",
    takeaway: "Write descriptions and acceptable matches before inspecting search results. Include difficult screenshot queries that may need OCR.",
  },
  {
    id: "learning-pace",
    kind: "Working agreement",
    title: "Understand one step before adding the next.",
    detail: "The full plan felt like too much at once. The agreed pace is to explain the next idea, make one small change, inspect it together, and pause for review and approval before continuing.",
    takeaway: "Understanding the change is part of finishing the step. The isolated Python environment is configured; image loading and retrieval are still pending.",
  },
];

export const experimentSteps = [
  {
    title: "Set up the Python project",
    summary: "A separate place for the experiment and its dependencies.",
    explanation: "A Python 3.13 virtual environment is configured inside experiments/. pyproject.toml records the project requirements. No third-party packages are installed yet. Add image loading first, then notebook and model dependencies in separate steps.",
    done: "Completed: the environment runs Python and isolation is verified. Image and model dependencies follow later.",
  },
  {
    title: "Load ten of my images",
    summary: "See the inputs before asking a model to interpret them.",
    explanation: "The notebook will find supported images and display thumbnails with filenames. practice-images/ is the ignored default folder. An empty folder should be explained clearly, and a corrupt file should be reported and skipped.",
    done: "Ten readable images appear in the notebook, and we understand how their file paths become pixels.",
  },
  {
    title: "Load one pretrained model",
    summary: "Use a model that already knows how to relate images and text.",
    explanation: "The baseline is openai/clip-vit-base-patch32 with its matching image processor and text tokenizer. We will download its assets into ignored models/, record the exact revision, and use Apple GPU acceleration when supported or CPU otherwise. This is inference, not training.",
    done: "The model loads locally and we know which revision and device we are using.",
  },
  {
    title: "Create the image embeddings",
    summary: "Represent each image as a list of numbers.",
    explanation: "The image encoder produces a vector for each image. We will inspect one vector before processing the collection, normalize the vectors to length one, and keep them in memory for reuse across queries.",
    done: "Each readable image has a normalized embedding connected to the correct file path.",
  },
  {
    title: "Search with a description",
    summary: "Compare the query vector with every image vector.",
    explanation: "The matching text encoder embeds the description. For normalized vectors, the dot product gives cosine similarity. We will sort the scores and show the top five thumbnails, filenames, and scores. A similarity score is not a confidence percentage.",
    done: "Changing the description changes the results without recomputing the image embeddings.",
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
    done: "A short report explains what worked, what did not, and which retrieval step to improve next before porting proven behavior to Rust.",
  },
];

export const learningConcepts = [
  { term: "Ontology", meaning: "Explicit concepts and relationships, such as Receipt, Trip, and associated-with. Facts populate this model; evidence establishes whether an association is justified." },
  { term: "Model-assisted learning", meaning: "A pretrained model proposes facts and people correct them. Stored knowledge changes without retraining model weights. Keep source evidence and confirmation status." },
  { term: "Python-to-Rust parity", meaning: "Check the production implementation against the prototype using the same inputs, preprocessing, model revision, and labeled queries." },
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
