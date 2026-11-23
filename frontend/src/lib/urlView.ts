export type ViewParser<T extends string> = (raw: string | null) => T;

export function oneOf<T extends string>(allowed: readonly T[], fallback: T): ViewParser<T> {
  return (raw) => (raw !== null && (allowed as readonly string[]).includes(raw) ? (raw as T) : fallback);
}

export function readUrlView<T extends string>(search: string, param: string, parse: ViewParser<T>): T {
  return parse(new URLSearchParams(search).get(param));
}

export function withUrlView(search: string, param: string, value: string, fallback: string): string {
  const params = new URLSearchParams(search);
  if (value === fallback) params.delete(param);
  else params.set(param, value);
  const query = params.toString();
  return query ? `?${query}` : "";
}
