// A device fingerprint here just needs to be a STABLE identifier for this
// browser/device across sessions — not something derived from browser
// characteristics (those drift and aren't reliable identifiers anyway).
// Simplest correct approach: generate a random ID once, persist it, reuse
// it forever after.
//
// IMPORTANT: if the app already generates a device fingerprint elsewhere
// (e.g. during device registration in devices.py's flow), use THAT
// function instead of this one — the value submitted here must match
// whatever fingerprint was actually approved for this device, or every
// access-control check that checks device approval will fail.

const DEVICE_FINGERPRINT_KEY = 'pardarshi_device_fingerprint';

export function getOrCreateDeviceFingerprint() {
  let fingerprint = localStorage.getItem(DEVICE_FINGERPRINT_KEY);
  if (!fingerprint) {
    fingerprint = crypto.randomUUID();
    localStorage.setItem(DEVICE_FINGERPRINT_KEY, fingerprint);
  }
  return fingerprint;
}