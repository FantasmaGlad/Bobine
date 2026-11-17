import type { BrowseEntry, TransferKind } from "./types.ts";

export interface Crumb {
  label: string | null;
  path: string;
}

export function breadcrumbs(path: string): Crumb[] {
  const crumbs: Crumb[] = [{ label: null, path: "" }];
  let current = "";
  for (const segment of path.split("/").filter(Boolean)) {
    current = current ? `${current}/${segment}` : segment;
    crumbs.push({ label: segment, path: current });
  }
  return crumbs;
}

export function joinPath(parent: string, name: string): string {
  return parent ? `${parent}/${name}` : name;
}

export function suggestKind(selected: Array<Pick<BrowseEntry, "type" | "media">>): TransferKind {
  if (selected.some((e) => e.media === "video")) return "video";
  const files = selected.filter((e) => e.type === "file");
  if (files.length > 0 && files.every((e) => e.media === "audio")) return "radio";
  return "video";
}

export function selectionBytes(selected: Array<Pick<BrowseEntry, "size">>): number {
  return selected.reduce((sum, e) => sum + (e.size ?? 0), 0);
}

export function isSelectable(entry: Pick<BrowseEntry, "type" | "media">): boolean {
  return entry.type === "dir" || (entry.media !== null && entry.media !== "subtitle");
}

export function selectableEntries(entries: BrowseEntry[]): BrowseEntry[] {
  return entries.filter(isSelectable);
}

export function toggleSelection(selected: string[], path: string): string[] {
  return selected.includes(path) ? selected.filter((p) => p !== path) : [...selected, path];
}
