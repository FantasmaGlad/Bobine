export interface SelectOption {
  value: string;
  label: string;
  sublabel?: string;
  thumbnail?: string | null;
  square?: boolean;
  meta?: string;
  group?: string;
}

export function searchTextOf(option: SelectOption): string {
  return `${option.label} ${option.sublabel ?? ""} ${option.group ?? ""} ${option.meta ?? ""}`;
}

export function groupOptions(options: SelectOption[]): [string, SelectOption[]][] {
  const map = new Map<string, SelectOption[]>();
  for (const option of options) {
    const key = option.group ?? "";
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(option);
  }
  return [...map.entries()];
}
