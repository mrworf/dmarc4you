"use client";

type CredentialDialogProps = {
  open: boolean;
  title: string;
  description: string;
  label: string;
  value: string;
  onClose: () => void;
};

export function CredentialDialog({ open, title, description, label, value, onClose }: CredentialDialogProps) {
  if (!open) {
    return null;
  }

  return (
    <div className="overlay-backdrop" onClick={onClose} role="presentation">
      <div aria-modal="true" className="dialog-card surface-card" onClick={(event) => event.stopPropagation()} role="dialog">
        <div className="stack">
          <div className="stack" style={{ gap: 8 }}>
            <p className="eyebrow">Copy once</p>
            <h2 style={{ margin: 0 }}>{title}</h2>
            <p className="status-text" style={{ margin: 0 }}>{description}</p>
          </div>
          <div className="detail-card">
            <span className="stat-label">{label}</span>
            <span className="monospace" style={{ wordBreak: "break-all" }}>
              {value}
            </span>
          </div>
          <div className="dialog-actions">
            <button className="button-primary" onClick={onClose} type="button">
              Done
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
