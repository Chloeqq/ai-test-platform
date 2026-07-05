interface TablePaginationProps {
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
  pageSizeOptions?: number[];
  className?: string;
}

function clampPage(page: number, totalPages: number): number {
  return Math.min(Math.max(1, page), Math.max(1, totalPages));
}

export function TablePagination({
  page,
  pageSize,
  total,
  onPageChange,
  onPageSizeChange,
  pageSizeOptions = [10, 20, 50],
  className = "",
}: TablePaginationProps) {
  const normalizedTotal = Math.max(0, total);
  const normalizedPageSize = Math.max(1, pageSize);
  const totalPages = Math.max(1, Math.ceil(normalizedTotal / normalizedPageSize));
  const currentPage = clampPage(page, totalPages);
  const start = normalizedTotal ? (currentPage - 1) * normalizedPageSize + 1 : 0;
  const end = Math.min(normalizedTotal, currentPage * normalizedPageSize);
  const classes = ["table-pagination", className].filter(Boolean).join(" ");

  return (
    <footer className={classes}>
      <div className="table-pagination-meta">
        <span>共 {normalizedTotal} 条</span>
        <span>第 {start}-{end} 条</span>
        <span>
          第 {currentPage} / {totalPages} 页
        </span>
      </div>
      <div className="table-pagination-actions">
        <button type="button" className="button secondary" disabled={currentPage <= 1} onClick={() => onPageChange(currentPage - 1)}>
          上一页
        </button>
        <button type="button" className="button secondary" disabled={currentPage >= totalPages} onClick={() => onPageChange(currentPage + 1)}>
          下一页
        </button>
        <label className="table-page-size">
          每页
          <select value={normalizedPageSize} onChange={(event) => onPageSizeChange(Number(event.target.value) || normalizedPageSize)}>
            {pageSizeOptions.map((option) => (
              <option key={option} value={option}>
                {option} 条
              </option>
            ))}
          </select>
        </label>
      </div>
    </footer>
  );
}
