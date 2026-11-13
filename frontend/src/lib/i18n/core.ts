export type Language = "fr" | "en";

export type Dict = { [key: string]: string | string[] | Dict };


function lookup(dict: Dict, path: string[]): string | string[] | undefined {
  let node: Dict | string | string[] = dict;
  for (const part of path) {
    if (typeof node === "string" || Array.isArray(node) || node === undefined) return undefined;
    node = node[part];
  }
  return typeof node === "string" || Array.isArray(node) ? node : undefined;
}

export function lookupPath(dict: Dict, key: string): string | string[] | undefined {
  return lookup(dict, key.split("."));
}

export function translateIn(dict: Dict, key: string, params?: Record<string, string | number>): string {
  const value = lookupPath(dict, key);
  if (value === undefined || Array.isArray(value)) return key;
  if (!params) return value;
  return value.replace(/\{\{(\w+)\}\}/g, (_, name) => String(params[name] ?? ""));
}

export function translateListIn(dict: Dict, key: string): string[] {
  const value = lookupPath(dict, key);
  return Array.isArray(value) ? value : [];
}
