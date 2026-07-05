interface ConfirmDialogProps {
  title: string;
  description: string;
  confirmText?: string;
  cancelText?: string;
  danger?: boolean;
  busy?: boolean;
  details?: string[];
  noteLabel?: string;
  noteValue?: string;
  notePlaceholder?: string;
  noteRequired?: boolean;
  onNoteChange?: (value: string) => void;
  onCancel: () => void;
  onConfirm: () => void;
}

export function ConfirmDialog({
  title,
  description,
  confirmText = "确认",
  cancelText = "取消",
  danger = false,
  busy = false,
  details = [],
  noteLabel,
  noteValue = "",
  notePlaceholder = "",
  noteRequired = false,
  onNoteChange,
  onCancel,
  onConfirm,
}: ConfirmDialogProps) {
  const confirmDisabled = busy || (noteRequired && !noteValue.trim());
  return (
    <section className="governance-modal-backdrop" role="dialog" aria-modal="true" aria-label={title}>
      <div className="panel governance-modal small confirm-dialog">
        <div className="modal-head">
          <div>
            <h2>{title}</h2>
            <p className="muted">{description}</p>
          </div>
        </div>
        {details.length ? (
          <ul className="confirm-detail-list">
            {details.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        ) : null}
        {noteLabel && onNoteChange ? (
          <label className="confirm-note">
            {noteLabel}
            <textarea
              rows={3}
              value={noteValue}
              placeholder={notePlaceholder}
              onChange={(event) => onNoteChange(event.target.value)}
              disabled={busy}
            />
          </label>
        ) : null}
        <div className="header-actions">
          <button type="button" className={`button ${danger ? "danger" : ""}`} onClick={onConfirm} disabled={confirmDisabled}>
            {busy ? "处理中..." : confirmText}
          </button>
          <button type="button" className="button secondary" onClick={onCancel} disabled={busy}>
            {cancelText}
          </button>
        </div>
      </div>
    </section>
  );
}
