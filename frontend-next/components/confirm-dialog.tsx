"use client";

import { useEffect } from "react";

type ConfirmDialogProps = {
  open: boolean;
  title: string;
  description: string;
  confirmLabel: string;
  confirmTone?: "default" | "danger";
  isPending?: boolean;
  onCancel: () => void;
  onConfirm: () => void;
};

export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel,
  confirmTone = "default",
  isPending = false,
  onCancel,
  onConfirm,
}: ConfirmDialogProps) {
  useEffect(() => {
    if (!open) {
      return;
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onCancel();
      }
    }

    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", handleKeyDown);

    return () => {
      document.body.style.overflow = "";
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [onCancel, open]);

  if (!open) {
    return null;
  }

  return (
    <div className="overlay-backdrop" onClick={onCancel} role="presentation">
      <div aria-modal="true" className="dialog-card surface-card" onClick={(event) => event.stopPropagation()} role="dialog">
        <div className="stack">
          <div className="stack" style={{ gap: 8 }}>
            <p className="eyebrow">Confirm</p>
            <h2 style={{ margin: 0 }}>{title}</h2>
            <p className="status-text" style={{ margin: 0 }}>{description}</p>
          </div>
          <div className="dialog-actions">
            <button className="button-secondary" onClick={onCancel} type="button">
              Cancel
            </button>
            <button
              className={confirmTone === "danger" ? "button-secondary danger-button" : "button-primary"}
              disabled={isPending}
              onClick={onConfirm}
              type="button"
            >
              {isPending ? "Working..." : confirmLabel}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
