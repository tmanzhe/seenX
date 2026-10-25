export type DemoItem = {
  id: string;
  title: string;
  file: string;
  image?: string;
  width: number;
  height: number;
  kind: "photo" | "screenshot";
  location: string;
  tags: string;
  note: string;
  text: string;
  source: string;
};

// Authored sample records. Source labels, notes, and extracted text are illustrative.
export const demoItems: DemoItem[] = [
  { id: "layout", width: 640, height: 480, title: "A checkout worth remembering", file: "checkout-reference.png", kind: "screenshot", location: "Inspiration", tags: "website ui design checkout flow navigation layout blue reference", note: "Love this checkout flow. Keep the generous spacing, but try a softer palette for our prototype.", text: "Your everyday essentials. Thoughtfully made. Your bag · Everyday tote · Continue to checkout", source: "Browser · example.com/shop" },
  { id: "lake", width: 1000, height: 667, title: "The lake with the little cabin", file: "alpine-lake.jpg", image: "/images/alpine-lake.jpg", kind: "photo", location: "Little adventures", tags: "blue sky green mountain mountains lake water cabin travel outdoors summer", note: "Our next long weekend. Look for a cabin near the water, somewhere quiet.", text: "No sample text recorded.", source: "Imported photo · Alpine trip" },
  { id: "menu", width: 640, height: 480, title: "The little café menu", file: "cafe-menu.png", kind: "screenshot", location: "Everyday", tags: "japan japanese kyoto cafe menu matcha coffee restaurant food", note: "Try the matcha when we go back to Kyoto. This is the café near the station.", text: "GOOD THINGS, SLOWLY. Matcha latte ¥550 · Pour-over coffee ¥480", source: "Screenshot · Travel ideas" },
  { id: "terminal", width: 640, height: 480, title: "What fixed that connection error", file: "connection-refused.png", kind: "screenshot", location: "Work", tags: "connection refused terminal error localhost postgres database code", note: "The database was stopped. Starting the local service fixed it. Check that first next time.", text: "Error: connection refused · ECONNREFUSED 127.0.0.1:5432", source: "Terminal · Local project" },
  { id: "ridge", width: 1000, height: 664, title: "One more hour outside", file: "mountain-light.jpg", image: "/images/mountain-light.jpg", kind: "photo", location: "Little adventures", tags: "blue sky green mountain mountains hiking landscape sunlight forest outdoors travel", note: "This light. Save it as a color reference for the next little project.", text: "No sample text recorded.", source: "Imported photo · Alpine trip" },
  { id: "coast", width: 900, height: 600, title: "Somewhere with no signal", file: "coastline.jpg", image: "/images/coastline.jpg", kind: "photo", location: "Little adventures", tags: "blue ocean sea water waves coast beach sky travel", note: "A place to switch off. Bring a book and leave the itinerary open.", text: "No sample text recorded.", source: "Imported photo · Coastal trip" },
];

export type DemoNotes = Record<string, string>;
const normalize = (value: string) => value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();

export function searchDemo(query: string, collection = "all", kind = "all", notes: DemoNotes = {}, items: DemoItem[] = demoItems) {
  const words = normalize(query).split(/\s+/).filter((word) => word && !["a", "the", "of", "in", "at", "and", "with", "that", "my", "i", "for", "from", "it", "to"].includes(word));
  return items
    .filter((item) => (collection === "all" || item.location === collection) && (kind === "all" || item.kind === kind))
    .map((item, index) => {
      const note = normalize(notes[item.id] ?? item.note);
      const text = normalize(`${item.tags} ${item.title} ${item.file} ${item.location} ${item.text}`);
      return { item, index, score: words.reduce((score, word) => score + (note.includes(word) ? 3 : 0) + (text.includes(word) ? 1 : 0), 0) };
    })
    .filter(({ score }) => !words.length || score > 0)
    .sort((a, b) => b.score - a.score || a.index - b.index)
    .map(({ item }) => item);
}
