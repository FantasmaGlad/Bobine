export function toggledSet(prev: Set<number>, id: number): Set<number> {
  const next = new Set(prev);
  if (next.has(id)) next.delete(id);
  else next.add(id);
  return next;
}

export function toggledAll(prev: Set<number>, ids: number[], all: boolean): Set<number> {
  const next = new Set(prev);
  ids.forEach((id) => (all ? next.delete(id) : next.add(id)));
  return next;
}

export function tagStateOf(chosen: { tags: string[] }[], name: string): "all" | "some" | "none" {
  const withTag = chosen.filter((tr) => tr.tags.includes(name)).length;
  if (chosen.length === 0 || withTag === 0) return "none";
  return withTag === chosen.length ? "all" : "some";
}

export function mergedIds(existing: number[], selected: Iterable<number>): number[] {
  const merged = [...existing];
  for (const id of selected) if (!merged.includes(id)) merged.push(id);
  return merged;
}
