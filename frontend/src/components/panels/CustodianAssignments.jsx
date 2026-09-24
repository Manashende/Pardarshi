import { useEffect, useState } from 'react';
import { getMyAssignments, getMyShare, submitShare } from '../../api/client';
import { getOrCreateDeviceFingerprint } from '../../utils/deviceFingerprint';
import { getCurrentLocation } from '../../utils/geolocation';
import ConfirmModal from '../common/ConfirmModal';
import './CustodianAssignments.css';

function formatCountdown(seconds) {
  if (seconds <= 0) return 'Exam window is open';
  const hrs = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  if (hrs > 0) return `${hrs}h ${mins}m until exam start`;
  return `${mins}m until exam start`;
}

function formatClockTime(epochSeconds) {
  return new Date(epochSeconds * 1000).toLocaleString();
}

export default function CustodianAssignments() {
  const [assignments, setAssignments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Per-variant transient UI state, keyed by variant_id: { phase, error }
  // phase is 'idle' | 'locating' | 'submitting'.
  const [rowState, setRowState] = useState({});
  const [overrideConfirmVariant, setOverrideConfirmVariant] = useState(null);

  // Checkbox selection for bulk submission, shared across all event cards.
  const [selectedIds, setSelectedIds] = useState(() => new Set());
  const [bulkSubmitting, setBulkSubmitting] = useState(false);
  const [bulkProgress, setBulkProgress] = useState(null); // { done, total }
  const [bulkErrors, setBulkErrors] = useState({});

  // A slow-ticking clock, purely so the override button can enable itself
  // automatically once its window opens, without needing a page refresh.
  const [nowTick, setNowTick] = useState(() => Date.now());

  useEffect(() => {
    refresh();
  }, []);

  useEffect(() => {
    const interval = setInterval(() => setNowTick(Date.now()), 30000);
    return () => clearInterval(interval);
  }, []);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      const data = await getMyAssignments();
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

  function isOverrideWindowOpen(variant) {
    return nowTick / 1000 >= variant.override_window_end_epoch;
  }

  async function performSubmit(variantId, submissionType) {
    setRow(variantId, { phase: 'locating', error: null });
    try {
      const deviceFingerprint = getOrCreateDeviceFingerprint();
      const [share, location] = await Promise.all([
        getMyShare(variantId),
        getCurrentLocation(),
      ]);
      setRow(variantId, { phase: 'submitting' });
      await submitShare(variantId, {
        x: share.x,
        y: share.y,
        submission_type: submissionType,
        declared_latitude: location.latitude,
        declared_longitude: location.longitude,
        device_fingerprint: deviceFingerprint,
      });
      await refresh();
    } catch (err) {
      setRow(variantId, { error: err.message });
    } finally {
      setRow(variantId, { phase: 'idle' });
    }
  }

  function handleStandardClick(variantId) {
    performSubmit(variantId, 'STANDARD');
  }

  function handleOverrideClick(variantId) {
    setOverrideConfirmVariant(variantId);
  }

  function confirmOverride() {
    const variantId = overrideConfirmVariant;
    setOverrideConfirmVariant(null);
    performSubmit(variantId, 'OVERRIDE');
  }

  function toggleSelected(variantId) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(variantId)) next.delete(variantId);
      else next.add(variantId);
      return next;
    });
  }

  function toggleSelectAllForEvent(variantIds, checked) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      variantIds.forEach((id) => (checked ? next.add(id) : next.delete(id)));
      return next;
    });
  }

  async function handleSubmitSelected(eventVariantIds) {
    const targets = eventVariantIds.filter((id) => selectedIds.has(id));
    if (targets.length === 0) return;

    setBulkSubmitting(true);
    setBulkProgress({ done: 0, total: targets.length });
    setBulkErrors({});

    const deviceFingerprint = getOrCreateDeviceFingerprint();
    let location;
    try {
      location = await getCurrentLocation();
    } catch (err) {
      setBulkErrors({ _location: err.message });
      setBulkSubmitting(false);
      setBulkProgress(null);
      return;
    }

    const errors = {};
    const succeededIds = [];
    for (let i = 0; i < targets.length; i++) {
      const variantId = targets[i];
      setBulkProgress({ done: i, total: targets.length });
      try {
        const share = await getMyShare(variantId);
        await submitShare(variantId, {
          x: share.x,
          y: share.y,
          submission_type: 'STANDARD',
          declared_latitude: location.latitude,
          declared_longitude: location.longitude,
          device_fingerprint: deviceFingerprint,
        });
        succeededIds.push(variantId);
      } catch (err) {
        errors[variantId] = err.message;
      }
    }

    setBulkProgress({ done: targets.length, total: targets.length });
    setBulkErrors(errors);
    setSelectedIds((prev) => {
      const next = new Set(prev);
      succeededIds.forEach((id) => next.delete(id));
      return next;
    });
    setBulkSubmitting(false);
    setBulkProgress(null);
    await refresh();
  }

  if (loading) return <p className="empty-state">Loading your assignments…</p>;
  if (error) return <p className="login-error">{error}</p>;

  return (
    <div className="custodian-workspace">
      {assignments.length === 0 && (
        <p className="empty-state">You are not currently assigned as a custodian on any exam event.</p>
      )}

      {assignments.map((event) => {
        const variantIds = event.variants.map((v) => v.variant_id);
        const allSelected = variantIds.length > 0 && variantIds.every((id) => selectedIds.has(id));
        const selectedCountThisEvent = variantIds.filter((id) => selectedIds.has(id)).length;

        return (
          <div className="panel custodian-event-card" key={event.exam_event_id}>
            <div className="custodian-event-header">
              <div>
                <p className="panel-eyebrow">{event.exam_name}</p>
                <span className="login-hint">
                  Your role: {event.custodian_type.replaceAll('_', ' ')} · Status: {event.status}
                </span>
              </div>
            </div>

            <table className="item-bank-table">
              <thead>
                <tr>
                  <th>
                    <input
                      type="checkbox"
                      checked={allSelected}
                      onChange={(e) => toggleSelectAllForEvent(variantIds, e.target.checked)}
                      aria-label="Select all variants"
                    />
                  </th>
                  <th>Variant</th>
                  <th>Standard Shares</th>
                  <th>Override Shares</th>
                  <th>Time</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {event.variants.map((v) => {
                  const row = rowState[v.variant_id] || {};
                  const busy = row.phase === 'locating' || row.phase === 'submitting';
                  const overrideOpen = isOverrideWindowOpen(v);
                  const actionLabel = row.phase === 'locating'
                    ? 'Getting location…'
                    : row.phase === 'submitting'
                      ? 'Submitting…'
                      : null;
                  return (
                    <tr key={v.variant_id}>
                      <td>
                        <input
                          type="checkbox"
                          checked={selectedIds.has(v.variant_id)}
                          onChange={() => toggleSelected(v.variant_id)}
                        />
                      </td>
                      <td>#{v.variant_index + 1}</td>
                      <td>{v.shares_submitted}/{v.threshold_required}</td>
                      <td>{v.override_shares_submitted}/{v.override_threshold_required}</td>
                      <td className="countdown-cell">{formatCountdown(v.seconds_until_exam)}</td>
                      <td className="row-actions">
                        <div className="action-with-badge">
                          <button
                            type="button"
                            disabled={busy || bulkSubmitting}
                            onClick={() => handleStandardClick(v.variant_id)}
                          >
                            {actionLabel || (v.has_submitted_standard ? 'Resubmit Standard Share' : 'Submit Standard Share')}
                          </button>
                          {v.has_submitted_standard && !busy && (
                            <span className="submitted-badge" title="You have already submitted a standard share for this variant">✓ Submitted</span>
                          )}
                        </div>
                        <div className="action-with-badge">
                          <button
                            type="button"
                            disabled={busy || bulkSubmitting || !overrideOpen}
                            title={overrideOpen ? undefined : `Opens at ${formatClockTime(v.override_window_end_epoch)}`}
                            onClick={() => handleOverrideClick(v.variant_id)}
                          >
                            {v.has_submitted_override ? 'Resubmit Override Share' : 'Submit Override Share'}
                          </button>
                          {v.has_submitted_override && !busy && (
                            <span className="submitted-badge" title="You have already submitted an override share for this variant">✓ Submitted</span>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
                {event.variants.map((v) => {
                  const row = rowState[v.variant_id] || {};
                  if (!row.error) return null;
                  return (
                    <tr key={`err_${v.variant_id}`} className="draft-error-row">
                      <td colSpan={6}>Variant #{v.variant_index + 1}: {row.error}</td>
                    </tr>
                  );
                })}
                {Object.entries(bulkErrors).map(([variantId, msg]) => {
                  if (!variantIds.includes(variantId) && variantId !== '_location') return null;
                  const variant = event.variants.find((v) => v.variant_id === variantId);
                  const label = variantId === '_location' ? 'Location' : `Variant #${variant ? variant.variant_index + 1 : variantId}`;
                  return (
                    <tr key={`bulkerr_${variantId}`} className="draft-error-row">
                      <td colSpan={6}>{label}: {msg}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>

            <button
              type="button"
              className="login-submit submit-all-btn"
              disabled={selectedCountThisEvent === 0 || bulkSubmitting}
              onClick={() => handleSubmitSelected(variantIds)}
            >
              {bulkSubmitting
                ? `Submitting ${bulkProgress ? bulkProgress.done + 1 : 1} of ${bulkProgress?.total ?? selectedCountThisEvent}…`
                : `Submit Standard Share for Selected (${selectedCountThisEvent})`}
            </button>
          </div>
        );
      })}

      {overrideConfirmVariant && (
        <ConfirmModal
          title="Submit via override path?"
          message="The override path is for exceptional circumstances where standard consensus could not be reached in time. Only proceed if an override has genuinely been called for this exam event."
          confirmLabel="Submit Override Share"
          danger
          onConfirm={confirmOverride}
          onCancel={() => setOverrideConfirmVariant(null)}
        />
      )}
    </div>
  );
}