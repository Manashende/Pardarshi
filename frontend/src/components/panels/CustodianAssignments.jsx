import { useEffect, useMemo, useState } from "react";
import { getMyAssignments, getMyShare, submitShare } from "../../api/client";
import { getOrCreateDeviceFingerprint } from "../../utils/deviceFingerprint";
import { getCurrentLocation } from "../../utils/geolocation";
import ConfirmModal from "../common/ConfirmModal";
import Tabs from "../common/Tabs";
import "./CustodianAssignments.css";

function formatCountdown(seconds) {
  if (seconds <= 0) return "Exam window is open";
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
  // Which exam event's bulk submission is currently in flight (or null).
  // Scoped per-event rather than one shared boolean — a shared boolean
  // visually disabled every OTHER exam card's row buttons too, even ones
  // with completely unrelated variants not part of this submission.
  const [bulkSubmittingEventId, setBulkSubmittingEventId] = useState(null);
  const [bulkProgress, setBulkProgress] = useState(null); // { done, total }
  const [bulkErrors, setBulkErrors] = useState({});

  // A slow-ticking clock, purely so the override button can enable itself
  // automatically once its window opens, without needing a page refresh.
  const [nowTick, setNowTick] = useState(() => Date.now());

  // Which tab is active. Defaults are resolved once data loads (see the
  // effect below) so a custodian with nothing pending lands on "All"
  // instead of an empty "Needs Action" tab.
  const [activeTab, setActiveTab] = useState("action");
  const [tabInitialized, setTabInitialized] = useState(false);

  const [searchQuery, setSearchQuery] = useState("");

  // Explicit expand/collapse overrides, keyed by exam_event_id. An event
  // not in this map falls back to its computed default (expanded if it
  // needs action, collapsed if fully submitted) — see isExpanded().
  const [expandedOverrides, setExpandedOverrides] = useState({});

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
    setRowState((prev) => ({
      ...prev,
      [variantId]: { ...prev[variantId], ...patch },
    }));
  }

  function isOverrideWindowOpen(variant) {
    return nowTick / 1000 >= variant.override_window_end_epoch;
  }

  function classifyVariant(v) {
    const pastDeadline = isOverrideWindowOpen(v);
    const thresholdMet = v.shares_submitted >= v.threshold_required;

    // Standard can only be submitted before the deadline; override only
    // after it, and only if the standard threshold wasn't reached.
    const canStillSubmitStandard = !pastDeadline && !v.has_submitted_standard;
    const canStillSubmitOverride = pastDeadline && !thresholdMet && !v.has_submitted_override;
    if (canStillSubmitStandard || canStillSubmitOverride) return "pending";

    // Nothing left this custodian can do: "done" if they took part,
    // "blocked" if the window closed without them.
    return v.has_submitted_standard || v.has_submitted_override ? "done" : "blocked";
  }

  async function performSubmit(variantId, submissionType) {
    setRow(variantId, { phase: "locating", error: null });
    try {
      const deviceFingerprint = getOrCreateDeviceFingerprint();
      const [share, location] = await Promise.all([
        getMyShare(variantId),
        getCurrentLocation(),
      ]);
      setRow(variantId, { phase: "submitting" });
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
      setRow(variantId, { phase: "idle" });
    }
  }

  function handleStandardClick(variantId) {
    performSubmit(variantId, "STANDARD");
  }

  function handleOverrideClick(variantId) {
    setOverrideConfirmVariant(variantId);
  }

  function confirmOverride() {
    const variantId = overrideConfirmVariant;
    setOverrideConfirmVariant(null);
    performSubmit(variantId, "OVERRIDE");
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

  async function handleSubmitSelected(eventVariantIds, examEventId) {
    const targets = eventVariantIds.filter((id) => selectedIds.has(id));
    if (targets.length === 0) return;

    setBulkSubmittingEventId(examEventId);
    setBulkProgress({ done: 0, total: targets.length });
    setBulkErrors({});

    const deviceFingerprint = getOrCreateDeviceFingerprint();
    let location;
    try {
      location = await getCurrentLocation();
    } catch (err) {
      setBulkErrors({ _location: err.message });
      setBulkSubmittingEventId(null);
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
          submission_type: "STANDARD",
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
    setBulkSubmittingEventId(null);
    setBulkProgress(null);
    await refresh();
  }

  function isExpanded(examEventId, needsAction) {
    if (Object.prototype.hasOwnProperty.call(expandedOverrides, examEventId)) {
      return expandedOverrides[examEventId];
    }
    return needsAction;
  }

  function toggleExpanded(examEventId, currentlyExpanded) {
    setExpandedOverrides((prev) => ({
      ...prev,
      [examEventId]: !currentlyExpanded,
    }));
  }

  // One pass over assignments to compute, per event: how many of its
  // variants still need this custodian's action, and its earliest exam
  // start (used to sort urgent things to the top). Recomputed whenever
  // the data or the clock ticks, since override windows open over time.
  const eventsWithMeta = useMemo(() => {
    return assignments.map((event) => {
      let pending = 0,
        blocked = 0;
      event.variants.forEach((v) => {
        const status = classifyVariant(v);
        if (status === "pending") pending++;
        else if (status === "blocked") blocked++;
      });
      const earliest = event.variants.length
        ? Math.min(...event.variants.map((v) => v.exam_start_epoch))
        : Infinity;
      return { event, pending, blocked, earliest };
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [assignments, nowTick]);

  const totalPendingVariants = eventsWithMeta.reduce(
    (sum, m) => sum + m.pending,
    0,
  );
  const totalPendingEvents = eventsWithMeta.filter((m) => m.pending > 0).length;

  // Default to the Needs Action tab only once, the first time we know
  // whether there's anything on it — avoids yanking a custodian back to
  // "All" every time refresh() runs after they've already picked a tab.
  useEffect(() => {
    if (tabInitialized || loading) return;
    setActiveTab(totalPendingEvents > 0 ? "action" : "all");
    setTabInitialized(true);
  }, [loading, totalPendingEvents, tabInitialized]);

  const query = searchQuery.trim().toLowerCase();
  const matchesSearch = (event) =>
    !query || event.exam_name.toLowerCase().includes(query);

  const actionList = eventsWithMeta
    .filter((m) => m.pending > 0 && matchesSearch(m.event))
    .sort((a, b) => a.earliest - b.earliest);

  const blockedList = eventsWithMeta
    .filter((m) => m.pending === 0 && m.blocked > 0 && matchesSearch(m.event))
    .sort((a, b) => a.earliest - b.earliest);

  const sortedAll = eventsWithMeta
    .filter((m) => matchesSearch(m.event))
    .sort((a, b) => a.earliest - b.earliest);

  const visibleList =
    activeTab === "action"
      ? actionList
      : activeTab === "blocked"
        ? blockedList
        : sortedAll;

  if (loading) return <p className="empty-state">Loading your assignments…</p>;
  if (error) return <p className="login-error">{error}</p>;

  return (
    <div className="custodian-workspace">
      {assignments.length === 0 && (
        <p className="empty-state">
          You are not currently assigned as a custodian on any exam event.
        </p>
      )}

      {assignments.length > 0 && (
        <>
          <div
            className={`custodian-summary-bar ${totalPendingVariants === 0 ? "summary-all-done" : "summary-pending"}`}
          >
            {totalPendingVariants === 0
              ? "✓ All caught up — no shares are awaiting your action"
              : `${totalPendingVariants} share${totalPendingVariants === 1 ? "" : "s"} across ${totalPendingEvents} exam event${totalPendingEvents === 1 ? "" : "s"} need your action`}
          </div>

          {bulkErrors._location && (
            <p className="login-error custodian-location-error">
              Location: {bulkErrors._location}
            </p>
          )}

          <div className="custodian-toolbar">
            <Tabs
              tabs={[
                { id: "action", label: `Needs Action (${actionList.length})` },
                {
                  id: "blocked",
                  label: `Outside Window (${blockedList.length})`,
                },
                { id: "all", label: `All Assignments (${assignments.length})` },
              ]}
              activeTab={activeTab}
              onChange={setActiveTab}
            />
            <input
              type="text"
              className="custodian-search-input"
              placeholder="Search by exam name…"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>

          {visibleList.length === 0 && (
            <p className="empty-state">
              {query
                ? "No exam events match your search."
                : "Nothing here — check the other tab."}
            </p>
          )}
        </>
      )}

      {visibleList.map(({ event, pending, blocked }) => {
        const variantIds = event.variants.map((v) => v.variant_id);
        const allSelected = variantIds.length > 0 && variantIds.every((id) => selectedIds.has(id));
        const selectedCountThisEvent = variantIds.filter((id) => selectedIds.has(id)).length;
        const expanded = isExpanded(event.exam_event_id, pending > 0);
        const isBulkSubmittingThisEvent = bulkSubmittingEventId === event.exam_event_id;

        return (
          <div className="panel custodian-event-card" key={event.exam_event_id}>
            <button
              type="button"
              className="custodian-event-header custodian-event-header-clickable"
              onClick={() => toggleExpanded(event.exam_event_id, expanded)}
              aria-expanded={expanded}
            >
              <div className="custodian-event-header-left">
                <span
                  className={`custodian-chevron ${expanded ? "custodian-chevron-open" : ""}`}
                >
                  ▸
                </span>
                <div>
                  <p className="panel-eyebrow">{event.exam_name}</p>
                  <span className="login-hint">
                    Your role: {event.custodian_type.replaceAll("_", " ")} ·
                    Status: {event.status}
                  </span>
                </div>
              </div>
              {pending > 0 ? (
                <span className="event-badge event-badge-pending">{pending} pending</span>
              ) : blocked > 0 ? (
                <span className="event-badge event-badge-blocked">{blocked} outside window</span>
              ) : (
                <span className="event-badge event-badge-done">✓ All submitted</span>
              )}
            </button>

            {expanded && (
              <>
                <table className="item-bank-table">
                  <thead>
                    <tr>
                      <th>
                        <input
                          type="checkbox"
                          checked={allSelected}
                          onChange={(e) =>
                            toggleSelectAllForEvent(
                              variantIds,
                              e.target.checked,
                            )
                          }
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
                      const busy =
                        row.phase === "locating" || row.phase === "submitting";
                      const overrideOpen = isOverrideWindowOpen(v);
                      const actionLabel =
                        row.phase === "locating"
                          ? "Getting location…"
                          : row.phase === "submitting"
                            ? "Submitting…"
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
                          <td>
                            {v.shares_submitted}/{v.threshold_required}
                          </td>
                          <td>
                            {v.override_shares_submitted}/
                            {v.override_threshold_required}
                          </td>
                          <td className="countdown-cell">
                            {formatCountdown(v.seconds_until_exam)}
                          </td>
                          <td className="row-actions">
                            {classifyVariant(v) === 'blocked' ? (
                              <span className="window-closed-note">Outside the permitted submission window</span>
                            ) : (
                              <>
                                <div className="action-with-badge">
                                  <button
                                    type="button"
                                    className="btn-ghost-small"
                                    disabled={busy || isBulkSubmittingThisEvent || overrideOpen}
                                    title={overrideOpen ? "The standard submission window has closed" : undefined}
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
                                    disabled={busy || isBulkSubmittingThisEvent || !overrideOpen || v.shares_submitted >= v.threshold_required}
                                    title={
                                      !overrideOpen
                                        ? `Opens at ${formatClockTime(v.override_window_end_epoch)}`
                                        : v.shares_submitted >= v.threshold_required
                                          ? "Not needed — the standard threshold was already reached"
                                          : undefined
                                    }
                                    onClick={() => handleOverrideClick(v.variant_id)}
                                  >
                                    {v.has_submitted_override ? 'Resubmit Override Share' : 'Submit Override Share'}
                                  </button>
                                  {v.has_submitted_override && !busy && (
                                    <span className="submitted-badge" title="You have already submitted an override share for this variant">✓ Submitted</span>
                                  )}
                                </div>
                              </>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                    {event.variants.map((v) => {
                      const row = rowState[v.variant_id] || {};
                      if (!row.error) return null;
                      return (
                        <tr
                          key={`err_${v.variant_id}`}
                          className="draft-error-row"
                        >
                          <td colSpan={6}>
                            Variant #{v.variant_index + 1}: {row.error}
                          </td>
                        </tr>
                      );
                    })}
                    {Object.entries(bulkErrors).map(([variantId, msg]) => {
                      if (
                        variantId === "_location" ||
                        !variantIds.includes(variantId)
                      )
                        return null;
                      const variant = event.variants.find(
                        (v) => v.variant_id === variantId,
                      );
                      return (
                        <tr
                          key={`bulkerr_${variantId}`}
                          className="draft-error-row"
                        >
                          <td colSpan={6}>
                            Variant #
                            {variant ? variant.variant_index + 1 : variantId}:{" "}
                            {msg}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>

                <button
                  type="button"
                  className="login-submit submit-all-btn"
                  disabled={selectedCountThisEvent === 0 || isBulkSubmittingThisEvent}
                  onClick={() => handleSubmitSelected(variantIds, event.exam_event_id)}
                >
                  {isBulkSubmittingThisEvent
                    ? `Submitting ${bulkProgress ? bulkProgress.done + 1 : 1} of ${bulkProgress?.total ?? selectedCountThisEvent}…`
                    : `Submit Standard Share for Selected (${selectedCountThisEvent})`}
                </button>
              </>
            )}
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
