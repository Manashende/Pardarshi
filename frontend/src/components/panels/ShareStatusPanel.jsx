import { useEffect, useState } from 'react';
import { getVariantStatus } from '../../api/client';
import { formatCountdown, sharesProgressPercent } from '../../utils/formatters';
import './ShareStatusPanel.css';

export default function ShareStatusPanel({ variantId }) {
  const [status, setStatus] = useState(null);
  const [error, setError] = useState(null);

  async function refresh() {
    try {
      const data = await getVariantStatus(variantId);
      setStatus(data);
      setError(null);
    } catch (e) {
      setError(e.message);
    }
  }

  useEffect(() => {
    if (!variantId) return;
    refresh();
    const interval = setInterval(refresh, 5000);
    return () => clearInterval(interval);
  }, [variantId]);

  if (!variantId) {
    return <div className="panel"><p className="panel-empty">No variant selected.</p></div>;
  }
  if (error) {
    return <div className="panel"><p className="panel-error">{error}</p></div>;
  }
  if (!status) {
    return <div className="panel"><p className="panel-empty">Loading…</p></div>;
  }

  const pct = sharesProgressPercent(status.shares_submitted, status.threshold_required);
  const overridePct = sharesProgressPercent(status.override_shares_submitted, status.override_threshold_required);

  return (
    <div className="panel">
      <p className="panel-eyebrow">Share Submission — Standard Path</p>
      <div className="share-progress-row">
        <span>{status.shares_submitted} / {status.threshold_required} custodians</span>
        <span>{pct}%</span>
      </div>
      <div className="share-progress-bar">
        <div className="share-progress-fill" style={{ width: `${pct}%` }} />
      </div>

      {status.override_threshold_required > 0 && (
        <>
          <p className="panel-eyebrow" style={{ marginTop: 18 }}>Override Path</p>
          <div className="share-progress-row">
            <span>{status.override_shares_submitted} / {status.override_threshold_required} custodians</span>
            <span>{overridePct}%</span>
          </div>
          <div className="share-progress-bar share-progress-bar-override">
            <div className="share-progress-fill share-progress-fill-override" style={{ width: `${overridePct}%` }} />
          </div>
        </>
      )}

      <div className="share-status-footer">
        <span>Exam starts in: <strong>{formatCountdown(status.seconds_until_exam)}</strong></span>
        <span className={status.can_unlock_standard ? 'status-ready' : 'status-waiting'}>
          {status.can_unlock_standard ? 'Ready to unlock' : 'Not yet unlockable'}
        </span>
      </div>
    </div>
  );
}