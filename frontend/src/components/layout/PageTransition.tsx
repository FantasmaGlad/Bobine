import { ViewTransition, type ReactNode } from "react";

export default function PageTransition({ pathname, children }: { pathname: string; children: ReactNode }) {
  return (
    <ViewTransition key={pathname} enter="page-enter" exit="page-exit" default="none">
      {children}
    </ViewTransition>
  );
}
