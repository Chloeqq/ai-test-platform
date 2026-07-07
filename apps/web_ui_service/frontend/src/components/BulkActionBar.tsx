import type { ReactNode } from "react";

interface BulkActionBarProps {
  selectedCount: number;
  children: ReactNode;
  label?: string;
}

export function BulkActionBar({ selectedCount, children, label = "已选" }: BulkActionBarProps) {
  return (
    <div className="bulk-action-bar">
      <span className="muted">{label} {selectedCount} 条</span>
      <div className="header-actions">{children}</div>
    </div>
  );
}
