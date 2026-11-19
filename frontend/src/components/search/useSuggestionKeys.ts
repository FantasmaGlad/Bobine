import { useState } from "react";

interface Options {
  value: string;
  list: string[];
  focused: boolean;
  onChange: (value: string) => void;
  onSubmit?: (value: string) => void;
}

export function useSuggestionKeys({ value, list, focused, onChange, onSubmit }: Options) {
  const [active, setActive] = useState(-1);
  const [dismissedFor, setDismissedFor] = useState<string | null>(null);
  const open = focused && list.length > 0 && dismissedFor !== value;
  const activeIndex = active >= 0 && active < list.length ? active : -1;

  const pick = (text: string) => {
    onChange(text);
    setDismissedFor(text);
    setActive(-1);
  };
  const step = (event: React.KeyboardEvent, next: (current: number) => number) => {
    event.preventDefault();
    setDismissedFor(null);
    setActive(next);
  };
  const handleKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "ArrowDown" && list.length > 0) {
      step(event, (current) => (current + 1) % list.length);
    } else if (event.key === "ArrowUp" && list.length > 0) {
      step(event, (current) => (current <= 0 ? list.length - 1 : current - 1));
    } else if (event.key === "Enter") {
      if (open && activeIndex >= 0) {
        event.preventDefault();
        pick(list[activeIndex]);
      } else {
        onSubmit?.(value);
      }
    } else if (event.key === "Escape" && open) {
      event.preventDefault();
      setDismissedFor(value);
      setActive(-1);
    }
  };
  const typed = () => {
    setDismissedFor(null);
    setActive(-1);
  };

  return { open, activeIndex, setActive, pick, handleKeyDown, typed };
}
