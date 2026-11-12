const catalog = new Map<string, unknown>();

export function rememberCatalog<T>(key: string, value: T[]): void {
  catalog.set(key, value);
}

export function recallCatalog<T>(key: string): T[] | undefined {
  const value = catalog.get(key);
  return Array.isArray(value) ? (value as T[]) : undefined;
}
