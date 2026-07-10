import type { ReactNode } from "react";

interface EmptyStateProps {
  title?: string;
  description?: string;
  message?: string;  // backward-compat alias for description
  action?: ReactNode;
}

export function EmptyState({ title, description, message, action }: EmptyStateProps) {
  const desc = description || message || "";
  return (
    <div className="empty-state">
      {title ? <strong>{title}</strong> : null}
      <span>{desc}</span>
      {action ? <div className="empty-state-action">{action}</div> : null}
    </div>
  );
}
