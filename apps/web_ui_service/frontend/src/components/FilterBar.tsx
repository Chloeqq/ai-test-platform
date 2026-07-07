import type { ReactNode } from "react";

interface FilterBarProps {
  children: ReactNode;
  className?: string;
}

export function FilterBar({ children, className = "" }: FilterBarProps) {
  const classes = ["panel", "filters", className].filter(Boolean).join(" ");
  return <section className={classes}>{children}</section>;
}
