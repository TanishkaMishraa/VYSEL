'use client';

import { useEffect, useId, useRef, type ReactNode } from 'react';
import { cx } from '../cx';
import { Button } from './Button';
import { Icon } from './Icon';

export interface ModalProps {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  description?: ReactNode;
  children?: ReactNode;
  footer?: ReactNode;
  /** Close when the backdrop is clicked. Default true. Disable for destructive confirmations. */
  dismissible?: boolean;
  className?: string;
}

/**
 * Built on native <dialog>.showModal(): focus trapping, Esc-to-close, inert
 * background and top-layer stacking come from the browser. Focus returns to the
 * opener on close. Renders as a bottom sheet below 640px.
 */
export function Modal({ open, onClose, title, description, children, footer, dismissible = true, className }: ModalProps) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const descId = useId();

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      className={cx('vy-modal', className)}
      aria-labelledby={titleId}
      aria-describedby={description ? descId : undefined}
      onClose={onClose}
      onCancel={(e) => {
        if (!dismissible) e.preventDefault();
      }}
      onClick={(e) => {
        // Clicks on the ::backdrop target the dialog element itself.
        if (dismissible && e.target === e.currentTarget) onClose();
      }}
    >
      <div className="vy-modal__header">
        <h2 className="vy-modal__title" id={titleId}>
          {title}
        </h2>
        <Button variant="ghost" size="sm" iconOnly aria-label="Close" onClick={onClose}>
          <Icon name="close" />
        </Button>
      </div>
      <div className="vy-modal__body">
        {description && <p id={descId}>{description}</p>}
        {children}
      </div>
      {footer && <div className="vy-modal__footer">{footer}</div>}
    </dialog>
  );
}
