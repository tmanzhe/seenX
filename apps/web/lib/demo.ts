export type DemoItem = {
  id: string;
  title: string;
  file: string;
  image?: string;
  kind: "photo" | "screenshot";
  location: string;
  tags: string;
};

// These are authored demonstration records, not metadata extracted from the photos.
export const demoItems: DemoItem[] = [
  { id: "lake", title: "The lake from that trip", file: "alpine-lake.jpg", image: "/images/alpine-lake.jpg", kind: "photo", location: "Alpine trip", tags: "blue sky green mountain mountains lake water cabin travel outdoors summer" },
  { id: "ridge", title: "One more hour outside", file: "mountain-light.jpg", image: "/images/mountain-light.jpg", kind: "photo", location: "Alpine trip", tags: "blue sky green mountain mountains hiking landscape sunlight forest outdoors travel" },
  { id: "terminal", title: "That terminal error", file: "connection-refused.png", kind: "screenshot", location: "Work", tags: "connection refused terminal error localhost postgres database code screenshot" },
  { id: "coast", title: "Somewhere with no signal", file: "coastline.jpg", image: "/images/coastline.jpg", kind: "photo", location: "Coastal trip", tags: "blue ocean sea water waves coast beach sky travel" },
  { id: "peak", title: "The long way up", file: "mountain-peak.jpg", image: "/images/mountain-peak.jpg", kind: "photo", location: "Alpine trip", tags: "mountain mountains snow rock peak blue sky hiking outdoors travel" },
  { id: "menu", title: "The little café menu", file: "cafe-menu.png", kind: "screenshot", location: "City trip", tags: "japan japanese kyoto cafe menu matcha coffee restaurant food screenshot" },
];

export function searchDemo(query: string, collection: string, kind: string) {
  const words = query.toLowerCase().split(/\s+/).filter((word) => word && !["a", "the", "of", "in", "at", "and", "with", "that"].includes(word));
  return demoItems
    .filter((item) => (collection === "all" || item.location === collection) && (kind === "all" || item.kind === kind))
    .map((item, index) => ({ item, index, score: words.reduce((score, word) => score + (`${item.tags} ${item.title} ${item.file} ${item.location}`.toLowerCase().includes(word) ? 1 : 0), 0) }))
    .filter(({ score }) => !words.length || score > 0)
    .sort((a, b) => b.score - a.score || a.index - b.index)
    .map(({ item }) => item);
}
