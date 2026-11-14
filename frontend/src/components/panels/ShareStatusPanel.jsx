import { useEffect, useState } from 'react';
import { getVariantStatus } from '../../api/client';
import { formatCountdown, sharesProgressPercent } from '../../utils/formatters';
import './ShareStatusPanel.css';

export default function ShareStatusPanel({ variantId }) {
  const [status, setStatus] = useState(null);
  const [error, setError] = useState(null);
  const [localSeconds, setLocalSeconds] = useState(null); // New state for local 1s tick

  async function refresh() {
    try {
      const data = await getVariantStatus(variantId);
      setStatus(data);
      setLocalSeconds(data.seconds_until_exam); // Sync local timer with true backend time
      setError(null);
    } catch (e) {
      setError(e.message);
    }
  }

  // Effect 1: Fetch from backend every 5 seconds
  useEffect(() => {
    if (!variantId) return;
    refresh();
    const interval = setInterval(refresh, 5000);
    return () => clearInterval(interval);
  }, [variantId]);

  // Effect 2: Tick down the local seconds every 1 second
  useEffect(() => {
    const tick = setInterval(() => {
      setLocalSeconds((prev) => {
        if (prev === null) return null;
        return prev > 0 ? prev - 1 : 0;
      });
    }, 1000);
    return () => clearInterval(tick);
  }, []);

  if (!variantId) {
    return <div className="panel"><p className="panel-empty">No variant selected.</p></div>;
  }
  if (error) {
    return <div className="panel"><p className="panel-error">{error}</p></div>;
  }
  if (!status || localSeconds === null) {
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
        <span>
          {localSeconds > 0 ? (
            <>Starts in: <strong>{formatCountdown(localSeconds)}</strong></>
          ) : (
            <>Exam window: <strong>Open</strong></>
          )}
        </span>
        <span className={status.can_unlock_standard ? 'status-ready' : 'status-waiting'}>
          {status.can_unlock_standard ? 'Ready to unlock' : 'Not yet unlockable'}
        </span>
      </div>
    </div>
  );
}