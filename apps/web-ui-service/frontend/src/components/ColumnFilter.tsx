interface ColumnFilterOption {
  value: string;
  label: string;
  count?: number;
}

interface ColumnFilterProps {
  label: string;
  value: string;
  options: ColumnFilterOption[];
  onChange: (value: string) => void;
  allLabel?: string;
}

export function ColumnFilter({
  label,
  value,
  options,
  onChange,
  allLabel = "全部",
}: ColumnFilterProps) {
  const active = Boolean(value);
  return (
    <div className={`column-filter ${active ? "is-active" : ""}`}>
      <span>{label}</span>
      <select value={value} aria-label={`${label}筛选`} onChange={(event) => onChange(event.target.value)}>
        <option value="">{allLabel}</option>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {typeof option.count === "number" ? `${option.label} (${option.count})` : option.label}
          </option>
        ))}
      </select>
    </div>
  );
}
