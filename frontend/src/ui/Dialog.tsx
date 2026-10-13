import { type ReactNode, useEffect, useRef } from "react";

interface DialogProps {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
  actions?: ReactNode;
}

/** Модальное окно на нативном <dialog>: фокус, Esc и затемнение обеспечивает браузер, въезд — CSS. */
export function Dialog({ open, title, onClose, children, actions }: DialogProps) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (open && !el.open) el.showModal?.();
    if (!open && el.open) el.close?.();
  }, [open]);

  return (
    <dialog ref={ref} className="dialog" aria-labelledby="dialog-title" onClose={onClose} onClick={(e) => e.target === ref.current && onClose()}>
      {open && (
        <div className="dialog-body">
          <h2 id="dialog-title">{title}</h2>
          <div className="dialog-content">{children}</div>
          <div className="dialog-actions">
            {actions}
            <button type="button" className="btn" onClick={onClose}>
              Закрыть
            </button>
          </div>
        </div>
      )}
    </dialog>
  );
}

interface ConfirmProps {
  open: boolean;
  title: string;
  message: string;
  confirmLabel: string;
  danger?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmDialog({ open, title, message, confirmLabel, danger, onConfirm, onCancel }: ConfirmProps) {
  return (
    <Dialog
      open={open}
      title={title}
      onClose={onCancel}
      actions={
        <button type="button" className={`btn ${danger ? "danger" : "primary"}`} onClick={onConfirm}>
          {confirmLabel}
        </button>
      }
    >
      <p>{message}</p>
    </Dialog>
  );
}
