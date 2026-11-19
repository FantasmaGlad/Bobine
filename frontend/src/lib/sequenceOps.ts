export function moveItem<Item>(items: Item[], index: number, offset: -1 | 1): Item[] {
  const target = index + offset;
  if (target < 0 || target >= items.length) return items;
  const copy = [...items];
  [copy[index], copy[target]] = [copy[target], copy[index]];
  return copy;
}

export function reorderItem<Item>(items: Item[], from: number, to: number): Item[] {
  const copy = [...items];
  const [moved] = copy.splice(from, 1);
  copy.splice(to, 0, moved);
  return copy;
}

export function insertItem<Item>(items: Item[], item: Item, at: number | null): Item[] {
  const copy = [...items];
  copy.splice(at ?? copy.length, 0, item);
  return copy;
}
