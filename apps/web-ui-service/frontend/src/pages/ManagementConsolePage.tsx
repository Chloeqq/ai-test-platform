import { Link } from "react-router-dom";

interface ManagementConsolePageProps {
  title: string;
  description: string;
  primaryLabel?: string;
  primaryHref?: string;
  secondaryLabel?: string;
  secondaryHref?: string;
}

export function ManagementConsolePage(props: ManagementConsolePageProps) {
  const primaryLabel = props.primaryLabel || "返回仪表盘";
  const primaryHref = props.primaryHref || "/dashboard";

  return (
    <main className="page shell">
      <header className="header panel">
        <div>
          <h1>{props.title}</h1>
          <p className="muted">{props.description}</p>
        </div>
      </header>

      <section className="panel">
        <p>该模块已统一迁移到 React 主入口，后续能力将继续在此页面迭代。</p>
        <div className="header-actions">
          <Link className="button" to={primaryHref}>
            {primaryLabel}
          </Link>
          {props.secondaryLabel && props.secondaryHref ? (
            <Link className="button secondary" to={props.secondaryHref}>
              {props.secondaryLabel}
            </Link>
          ) : null}
        </div>
      </section>
    </main>
  );
}
