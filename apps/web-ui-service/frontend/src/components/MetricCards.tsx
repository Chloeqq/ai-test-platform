import type { ReactNode } from "react";

interface MetricCardItem {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  tone?: "good" | "warn" | "bad" | "";
}

interface MetricCardsProps {
  items: MetricCardItem[];
  className?: string;
  cardClassName?: string;
}

export function MetricCards({ items, className = "governance-metrics", cardClassName = "governance-metric-card" }: MetricCardsProps) {
  return (
    <section className={className}>
      {items.map((item) => (
        <article className={[cardClassName, item.tone ? `metric-tone-${item.tone}` : ""].filter(Boolean).join(" ")} key={item.label}>
          <span>{item.label}</span>
          <strong className={item.tone ? `tone-${item.tone}` : ""}>{item.value}</strong>
          {item.hint ? <em>{item.hint}</em> : null}
        </article>
      ))}
    </section>
  );
}
