/**
 * Pure functions only — no React, no DOM. Kept separate from components
 * specifically so they can be unit tested directly in Node without a
 * browser environment.
 */

export function formatCountdown(secondsRemaining) {
  if (secondsRemaining <= 0) return 'Started';
  const h = Math.floor(secondsRemaining / 3600);
  const m = Math.floor((secondsRemaining % 3600) / 60);
  const s = Math.floor(secondsRemaining % 60);
  const parts = [];
  if (h > 0) parts.push(`${h}h`);
  if (h > 0 || m > 0) parts.push(`${m}m`);
  parts.push(`${s}s`);
  return parts.join(' ');
}

export function sharesProgressPercent(submitted, required) {
  if (required <= 0) return 0;
  const pct = (submitted / required) * 100;
  return Math.min(100, Math.max(0, Math.round(pct)));
}

export function formatTimestamp(epochSeconds) {
  if (epochSeconds === null || epochSeconds === undefined) return '—';
  return new Date(epochSeconds * 1000).toLocaleString();
}

/**
 * Turns a raw AccessAttempt record into a short, human-readable summary
 * of which specific check(s) failed — used by the flagged-attempts
 * panel so evaluators immediately see WHY something was blocked.
 */
export function summarizeFailedChecks(attempt) {
  const failed = [];
  if (!attempt.role_check_passed) failed.push('role');
  if (!attempt.device_check_passed) failed.push('device');
  if (!attempt.location_check_passed) failed.push('location');
  if (!attempt.time_window_check_passed) failed.push('time window');
  if (failed.length === 0) return 'all checks passed';
  return `failed: ${failed.join(', ')}`;
}

export function makespanToHuman(seconds) {
  if (seconds === null || seconds === undefined) return '—';
  const minutes = seconds / 60;
  if (minutes < 60) return `${minutes.toFixed(1)} min`;
  return `${(minutes / 60).toFixed(2)} hr`;
}