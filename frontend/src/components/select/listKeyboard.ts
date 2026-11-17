import type React from "react";

interface ListKeyboard {
  count: number;
  setActive: (update: (current: number) => number) => void;
  chooseActive: () => void;
  dismiss: () => void;
  close: () => void;
}

export function listKeyHandler({ count, setActive, chooseActive, dismiss, close }: ListKeyboard) {
  return (event: React.KeyboardEvent) => {
    const moves: Record<string, (current: number) => number> = {
      ArrowDown: (current) => Math.min(count - 1, current + 1),
      ArrowUp: (current) => Math.max(0, current - 1),
      Home: () => 0,
      End: () => Math.max(0, count - 1),
    };
    const move = moves[event.key];
    if (move) {
      event.preventDefault();
      setActive(move);
    } else if (event.key === "Enter") {
      event.preventDefault();
      chooseActive();
    } else if (event.key === "Escape") {
      event.preventDefault();
      dismiss();
    } else if (event.key === "Tab") {
      close();
    }
  };
}
