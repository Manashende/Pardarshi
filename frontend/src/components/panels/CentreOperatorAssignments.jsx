import { useEffect, useMemo, useState } from 'react';
import { getMyCentreAssignments, unlockVariant, getPrintJobsSummaryForVariant, confirmPresence } from '../../api/client';
import { getOrCreateDeviceFingerprint } from '../../utils/deviceFingerprint';
import { getCurrentLocation } from '../../utils/geolocation';
import ConfirmModal from '../common/ConfirmModal';
import Tabs from '../common/Tabs';
import './CentreOperatorAssignments.css';

function formatCountdown(targetEpoch, nowMs, label) {
  const remaining = targetEpoch - nowMs / 1000;
  if (remaining <= 0) return `${label} window is open`;
  const hrs = Math.floor(remaining / 3600);
  const mins = Math.floor((remaining % 3600) / 60);
  const secs = Math.floor(remaining % 60);
  if (hrs > 0) return `${hrs}h ${mins}m ${secs}s until ${label}`;
  if (mins > 0) return `${mins}m ${secs}s until ${label}`;
  return `${secs}s until ${label}`;
}

function formatClockTime(epochSeconds) {
  return new Date(epochSeconds * 1000).toLocaleString();
}

function unlockGate(a, nowMs) {
  const isPrintMode = a.delivery_mode === 'PRINT';
  const timeGateEpoch = isPrintMode ? a.print_release_epoch : a.exam_start_epoch;
  const timeGateLabel = isPrintMode ? 'print release' : 'exam start';
  const timeGateOpen = nowMs / 1000 >= timeGateEpoch;

  const officialsSatisfied = !isPrintMode || a.officials_confirmed_count >= a.required_officials_count;

  const overrideWindowOpen = nowMs / 1000 >= a.override_window_end_epoch;
  const standardSharesOk = a.shares_submitted >= a.threshold_required;
  const overrideSharesOk = overrideWindowOpen && a.override_shares_submitted >= a.override_threshold_required;
  const sharesSatisfied = standardSharesOk || overrideSharesOk;

  // already_delivered comes from the backend (DeliveredPaper for CBT,
  // any PrintJob row for PRINT) — real DB truth, so this survives a
  // refresh, unlike checking row.result from in-memory session state.
  const canUnlock = !a.already_delivered && timeGateOpen && officialsSatisfied && sharesSatisfied;

  let unlockDisabledReason;
  if (a.already_delivered) {
    unlockDisabledReason = 'This variant has already been unlocked for your centre';
  } else if (!timeGateOpen) {
    unlockDisabledReason = `Opens at ${formatClockTime(timeGateEpoch)}`;
  } else if (!officialsSatisfied) {
    unlockDisabledReason = `Needs ${a.required_officials_count - a.officials_confirmed_count} more official(s) to confirm presence`;
  } else if (!sharesSatisfied) {
    unlockDisabledReason = overrideWindowOpen
      ? `Waiting on shares — ${a.shares_submitted}/${a.threshold_required} standard, ${a.override_shares_submitted}/${a.override_threshold_required} override`
      : `Waiting on custodian shares (${a.shares_submitted}/${a.threshold_required} submitted)`;
  }

  return { isPrintMode, timeGateEpoch, timeGateLabel, timeGateOpen, officialsSatisfied, sharesSatisfied, canUnlock, unlockDisabledReason };
}

function PrintJobProgress({ variantId }) {
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState(null);
  const [nowTick, setNowTick] = useState(() => Date.now());

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const data = await getPrintJobsSummaryForVariant(variantId);
        if (!cancelled) setSummary(data);
      } catch (err) {
        if (!cancelled) setError(err.message);
      }
    }
    load();
    return () => { cancelled = true; };
  }, [variantId]);

  useEffect(() => {
    const interval = setInterval(() => setNowTick(Date.now()), 1000);
    return () => clearInterval(interval);
  }, []);

  if (error) return <p className="login-error">{error}</p>;
  if (!summary) return <p className="empty-state">Loading print dispatch…</p>;
  if (summary.jobs.length === 0) return <p className="empty-state">No print jobs found for this variant.</p>;

  return (
    <div className="print-progress">
      <p className="login-hint">
        {summary.num_printers_used} printer{summary.num_printers_used !== 1 ? 's' : ''} · {summary.total_copies} total copies
      </p>
      {summary.jobs.map((job) => {
        const remaining = job.completed_at ? Math.max(0, job.completed_at - nowTick / 1000) : null;
        const pct = job.elapsed_seconds
          ? Math.min(100, Math.round(((job.elapsed_seconds - (remaining ?? 0)) / job.elapsed_seconds) * 100))
          : 100;
        return (
          <div className="print-job-row" key={job.printer_id}>
            <span className="print-job-label">Printer {job.printer_id} · {job.copies} copies</span>
            <div className="print-job-bar-track">
              <div className="print-job-bar-fill" style={{ width: `${pct}%` }} />
            </div>
            <span className="print-job-time">
              {remaining !== null ? (remaining > 0 ? `${Math.ceil(remaining)}s left` : 'Done') : '—'}
            </span>
          </div>
        );
      })}
    </div>
  );
}

function AssignmentCard({ a, centreId, nowTick, rowState, presenceState, onRequestUnlock, onConfirmPresence }) {
  const row = rowState[a.variant_id] || {};
  const busy = row.phase === 'locating' || row.phase === 'unlocking';
  const gate = unlockGate(a, nowTick);
  const presence = presenceState[a.exam_event_id] || {};

  const actionLabel = row.phase === 'locating'
    ? 'Getting location…'
    : row.phase === 'unlocking'
      ? 'Requesting unlock…'
      : 'Request Unlock';

  return (
    <div className="assignment-card">
      <div className="assignment-card-header">
        <div>
          <p className="assignment-exam-name">
            {a.exam_name} <span className="login-hint">({a.exam_status})</span>
          </p>
          <span className="assignment-meta">{a.delivery_mode} · Variant #{a.variant_index + 1}</span>
        </div>
        <span className={`co-badge ${gate.canUnlock ? 'co-badge-ready' : 'co-badge-waiting'}`}>
          {gate.canUnlock ? '✓ Ready' : 'Waiting'}
        </span>
      </div>

      <div className="assignment-stats-row">
        <div className="assignment-stat">
          <span className="assignment-stat-label">Standard Shares</span>
          <span className="assignment-stat-value">{a.shares_submitted}/{a.threshold_required}</span>
        </div>
        <div className="assignment-stat">
          <span className="assignment-stat-label">Override Shares</span>
          <span className="assignment-stat-value">{a.override_shares_submitted}/{a.override_threshold_required}</span>
        </div>
        <div className="assignment-stat">
          <span className="assignment-stat-label">Time</span>
          <span className="assignment-stat-value assignment-stat-time">
            {formatCountdown(gate.timeGateEpoch, nowTick, gate.timeGateLabel)}
          </span>
        </div>
      </div>

      {gate.isPrintMode && (
        <div className="presence-panel">
          <span className="login-hint">
            On-site officials confirmed: {a.officials_confirmed_count}/{a.required_officials_count}
          </span>
          <button
            type="button"
            disabled={presence.busy || a.i_have_confirmed_presence}
            onClick={() => onConfirmPresence(a.exam_event_id, centreId)}
          >
            {presence.busy
              ? 'Confirming…'
              : a.i_have_confirmed_presence
                ? '✓ You confirmed presence'
                : 'Confirm My Presence'}
          </button>
          {presence.error && <span className="login-error">{presence.error}</span>}
        </div>
      )}

      {a.already_delivered ? (
        <div className="assignment-card-footer">
          <span className="already-unlocked-label">✓ Already unlocked</span>
        </div>
      ) : (
        <div className="assignment-card-footer">
          <button
            type="button"
            className="login-submit"
            disabled={busy || !gate.canUnlock}
            title={gate.unlockDisabledReason}
            onClick={() => onRequestUnlock(a.variant_id, centreId)}
          >
            {actionLabel}
          </button>
        </div>
      )}

      {row.error && <p className="login-error assignment-inline-message">{row.error}</p>}
      {row.result && row.result.status === 'denied' && (
        <p className="login-error assignment-inline-message">Denied: {row.result.reason}</p>
      )}
      {a.already_delivered && (
        gate.isPrintMode ? (
          <div className="assignment-inline-message">
            <div className="unlocked-banner">Unlocked — print dispatch in progress</div>
            <PrintJobProgress variantId={a.variant_id} />
          </div>
        ) : (
          <div className="assignment-inline-message">
            <div className="unlocked-banner">Paper Unlocked</div>
          </div>
        )
      )}
    </div>
  );
}

export default function CentreOperatorAssignments() {
  const [assignments, setAssignments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [rowState, setRowState] = useState({});
  const [confirmVariant, setConfirmVariant] = useState(null);

  const [presenceState, setPresenceState] = useState({});

  const [nowTick, setNowTick] = useState(() => Date.now());

  const [activeTab, setActiveTab] = useState('ready');
  const [tabInitialized, setTabInitialized] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    refresh();
  }, []);

  useEffect(() => {
    const interval = setInterval(() => setNowTick(Date.now()), 1000);
    return () => clearInterval(interval);
  }, []);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      const data = await getMyCentreAssignments();
      setAssignments(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  function setRow(variantId, patch) {
    setRowState((prev) => ({ ...prev, [variantId]: { ...prev[variantId], ...patch } }));
  }

  function setPresence(examEventId, patch) {
    setPresenceState((prev) => ({ ...prev, [examEventId]: { ...prev[examEventId], ...patch } }));
  }

  async function handleConfirmPresence(examEventId, centreId) {
    setPresence(examEventId, { busy: true, error: null });
    try {
      const deviceFingerprint = getOrCreateDeviceFingerprint();
      const location = await getCurrentLocation();
      await confirmPresence(examEventId, centreId, location.latitude, location.longitude, deviceFingerprint);
      await refresh();
    } catch (err) {
      setPresence(examEventId, { error: err.message });
    } finally {
      setPresence(examEventId, { busy: false });
    }
  }

  function handleRequestUnlock(variantId, centreId) {
    setConfirmVariant({ variantId, centreId });
  }

  async function confirmUnlock() {
    const { variantId, centreId } = confirmVariant;
    setConfirmVariant(null);
    setRow(variantId, { phase: 'locating', error: null, result: null });
    try {
      const deviceFingerprint = getOrCreateDeviceFingerprint();
      const location = await getCurrentLocation();
      setRow(variantId, { phase: 'unlocking' });
      const result = await unlockVariant(variantId, {
        centre_id: centreId,
        declared_latitude: location.latitude,
        declared_longitude: location.longitude,
        device_fingerprint: deviceFingerprint,
      });
      setRow(variantId, { result });
      await refresh();
    } catch (err) {
      setRow(variantId, { error: err.message });
    } finally {
      setRow(variantId, { phase: 'idle' });
    }
  }

  const allAssignments = useMemo(
    () => assignments.flatMap((c) => c.assignments),
    [assignments]
  );

  const readyCount = useMemo(
    () => allAssignments.filter((a) => unlockGate(a, nowTick).canUnlock).length,
    [allAssignments, nowTick]
  );
  const deliveredCount = allAssignments.filter((a) => a.already_delivered).length;
  const totalCount = allAssignments.length;
  // Waiting is deliberately just "not ready and not already delivered" —
  // a delivered variant will never move out of a plain "not ready" bucket
  // on its own, so leaving it lumped into Waiting would make that count
  // permanently overstate how much is genuinely still pending action.
  const waitingCount = totalCount - readyCount - deliveredCount;
  const printCount = allAssignments.filter((a) => a.delivery_mode === 'PRINT').length;

  useEffect(() => {
    if (tabInitialized || loading) return;
    setActiveTab(readyCount > 0 ? 'ready' : 'all');
    setTabInitialized(true);
  }, [loading, readyCount, tabInitialized]);

  const query = searchQuery.trim().toLowerCase();
  const matchesSearch = (a) => !query || a.exam_name.toLowerCase().includes(query);
  const matchesTab = (a) => {
    if (activeTab === 'all') return true;
    if (activeTab === 'print') return a.delivery_mode === 'PRINT';
    if (activeTab === 'delivered') return a.already_delivered;
    const ready = unlockGate(a, nowTick).canUnlock;
    if (activeTab === 'ready') return ready;
    // 'waiting' — explicitly excludes delivered variants, same reasoning
    // as deliveredCount above.
    return !ready && !a.already_delivered;
  };

  if (loading) return <p className="empty-state">Loading your assignments…</p>;
  if (error) return <p className="login-error">{error}</p>;

  return (
    <div className="centre-operator-workspace">
      {assignments.length === 0 && (
        <p className="empty-state">You are not currently assigned to operate any exam centre.</p>
      )}

      {assignments.length > 0 && (
        <>
          <div className={`centre-operator-summary-bar ${readyCount === 0 ? 'summary-all-waiting' : 'summary-ready'}`}>
            {readyCount === 0
              ? totalCount === 0
                ? 'No exams assigned to your centre yet'
                : '⏳ Nothing is ready to unlock right now'
              : `✓ ${readyCount} exam${readyCount === 1 ? '' : 's'} ready to unlock now`}
          </div>

          <div className="centre-operator-toolbar">
            <Tabs
              tabs={[
                { id: 'ready', label: `Ready to Unlock (${readyCount})` },
                { id: 'waiting', label: `Waiting (${waitingCount})` },
                { id: 'delivered', label: `Delivered (${deliveredCount})` },
                { id: 'print', label: `PRINT Exams (${printCount})` },
                { id: 'all', label: `All (${totalCount})` },
              ]}
              activeTab={activeTab}
              onChange={setActiveTab}
            />
            <input
              type="text"
              className="centre-operator-search-input"
              placeholder="Search by exam name…"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
        </>
      )}

      {assignments.map((centre) => {
        const filtered = centre.assignments
          .filter((a) => matchesTab(a) && matchesSearch(a))
          .sort((x, y) => {
            const gx = unlockGate(x, nowTick);
            const gy = unlockGate(y, nowTick);
            if (gx.canUnlock !== gy.canUnlock) return gx.canUnlock ? -1 : 1;
            return gx.timeGateEpoch - gy.timeGateEpoch;
          });

        return (
          <div className="panel centre-card" key={centre.centre_id}>
            <div className="centre-card-header">
              <p className="panel-eyebrow">{centre.centre_code} — {centre.centre_name}</p>
              <span className="login-hint">
                Geofence: {centre.acceptable_radius_m}m radius
              </span>
            </div>

            {centre.assignments.length === 0 ? (
              <p className="empty-state">No exam variants have been assigned to this centre yet.</p>
            ) : filtered.length === 0 ? (
              <p className="empty-state">
                {query ? 'No exams match your search.' : 'Nothing here — check the other tab.'}
              </p>
            ) : (
              <div className="assignment-card-list">
                {filtered.map((a) => (
                  <AssignmentCard
                    key={a.variant_id}
                    a={a}
                    centreId={centre.centre_id}
                    nowTick={nowTick}
                    rowState={rowState}
                    presenceState={presenceState}
                    onRequestUnlock={handleRequestUnlock}
                    onConfirmPresence={handleConfirmPresence}
                  />
                ))}
              </div>
            )}
          </div>
        );
      })}

      {confirmVariant && (
        <ConfirmModal
          title="Request unlock?"
          message="This will attempt to reconstruct and print the exam paper at your centre using submitted custodian shares. Only proceed if you are physically at the centre and it is genuinely time to unlock."
          confirmLabel="Request Unlock"
          onConfirm={confirmUnlock}
          onCancel={() => setConfirmVariant(null)}
        />
      )}
    </div>
  );
}