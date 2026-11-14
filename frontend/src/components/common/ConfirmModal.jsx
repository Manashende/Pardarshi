import { useState } from 'react';
import './ConfirmModal.css';

/**
 * Generic confirm dialog. When `requireCheckbox` is set, the confirm button
 * stays disabled until the user ticks it — used here so a contributor can't
 * fat-finger the final "lock these questions forever" action.
 */
export default function ConfirmModal({
  title,
  message,
  checkboxLabel,
  requireCheckbox = false,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  danger = false,
  onConfirm,
  onCancel,
}) {
  const [checked, setChecked] = useState(false);

  const confirmDisabled = requireCheckbox && !checked;

  return (
    <div className="confirm-modal-backdrop" role="dialog" aria-modal="true">
      <div className="confirm-modal">
        <h3 className="confirm-modal-title">{title}</h3>
        <p className="confirm-modal-message">{message}</p>

        {requireCheckbox && (
          <label className="confirm-modal-checkbox-row">
            <input
              type="checkbox"
              checked={checked}
              onChange={(e) => setChecked(e.target.checked)}
            />
            <span>{checkboxLabel}</span>
          </label>
        )}

        <div className="confirm-modal-actions">
          <button type="button" className="confirm-modal-cancel" onClick={onCancel}>
            {cancelLabel}
          </button>
          <button
            type="button"
            className={danger ? 'confirm-modal-confirm-danger' : 'confirm-modal-confirm'}
            disabled={confirmDisabled}
            onClick={onConfirm}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}