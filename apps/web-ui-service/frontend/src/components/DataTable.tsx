import type { ReactNode } from "react";

interface DataTableProps {
  title?: ReactNode;
  actions?: ReactNode;
  loading?: boolean;
  loadingText?: string;
  errorText?: string;
  children: ReactNode;
}

export function DataTable({
  title,
  actions,
  loading = false,
  loadingText = "正在加载...",
  errorText = "",
  children,
}: DataTableProps) {
  return (
    <section className="panel table-panel">
      {title || actions ? (
        <div className="table-head">
          {title ? <strong>{title}</strong> : <span />}
          {actions ? <div className="header-actions">{actions}</div> : null}
        </div>
      ) : null}
      {loading ? <p>{loadingText}</p> : null}
      {errorText ? <p className="error">{errorText}</p> : null}
      {!loading && !errorText ? children : null}
    </section>
  );
}
