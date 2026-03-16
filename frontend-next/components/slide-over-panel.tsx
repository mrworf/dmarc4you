"use client";

import { useEffect } from "react";

type SlideOverPanelProps = {
  open: boolean;
  title: string;
  description?: string;
  onClose: () => void;
  children: React.ReactNode;
  footer?: React.ReactNode;
};

export function SlideOverPanel({ open, title, description, onClose, children, footer }: SlideOverPanelProps) {
  useEffect(() => {
    if (!open) {
      return;
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onClose();
      }
    }

    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", handleKeyDown);

    return () => {
      document.body.style.overflow = "";
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [onClose, open]);

  if (!open) {
    return null;
  }

  return (
    <div className="overlay-backdrop" onClick={onClose} role="presentation">
      <aside
        aria-modal="true"
        className="slideover-panel"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
      >
        <header className="slideover-header">
          <div className="stack" style={{ gap: 8 }}>
            <p className="eyebrow">Action</p>
            <h2 style={{ margin: 0 }}>{title}</h2>
            {description ? <p className="status-text" style={{ margin: 0 }}>{description}</p> : null}
          </div>
          <button aria-label="Close panel" className="icon-button" onClick={onClose} type="button">
            ×
          </button>
        </header>
        <div className="slideover-body">{children}</div>
        {footer ? <footer className="slideover-footer">{footer}</footer> : null}
      </aside>
    </div>
  );
}
