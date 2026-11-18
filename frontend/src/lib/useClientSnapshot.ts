import { useState, useSyncExternalStore } from "react";

const subscribeNever = () => () => {};

export function useClientSnapshot<T>(read: () => T, serverValue: T): T {
  return useSyncExternalStore(subscribeNever, read, () => serverValue);
}

export function useClientChoice<T>(read: () => T | null, fallback: T): [T, (next: T) => void] {
  const stored = useClientSnapshot<T | null>(read, null);
  const [chosen, setChosen] = useState<T | null>(null);
  return [chosen ?? stored ?? fallback, setChosen];
}
