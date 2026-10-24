import { Children, cloneElement, isValidElement, type ReactNode } from "react";

export function plainText(node: ReactNode): string {
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(plainText).join(" ");
  if (isValidElement<{ children?: ReactNode }>(node)) return plainText(node.props.children);
  return "";
}

export function prepareArticle(content: ReactNode) {
  const nodes = Children.toArray(isValidElement<{ children?: ReactNode }>(content) ? content.props.children : content);
  const headings: { id: string; title: string }[] = [];
  const used = new Map<string, number>();
  const body = nodes.map((node) => {
    if (!isValidElement<{ id?: string; children?: ReactNode }>(node) || node.type !== "h2") return node;
    const title = plainText(node.props.children);
    const base = title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
    const count = used.get(base) ?? 0;
    used.set(base, count + 1);
    const id = count ? `${base}-${count + 1}` : base;
    headings.push({ id, title });
    return cloneElement(node, { id });
  });
  return { body, headings };
}
