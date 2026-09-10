const BASE_URL = import.meta.env.VITE_API_BASE_URL;

let authToken = null;

export function setAuthToken(token) {
  authToken = token;
}

export function getAuthToken() {
  return authToken;
}

export function clearAuthToken() {
  authToken = null;
}

/**
 * Central request wrapper. Every API call goes through this so token
 * attachment, error parsing, and base-URL handling live in exactly one
 * place. Throws an Error with a readable message on any non-2xx
 * response, so callers can just try/catch instead of checking
 * response.ok everywhere.
 */
async function request(path, { method = 'GET', body, requiresAuth = true } = {}) {
  const headers = { 'Content-Type': 'application/json' };
  if (requiresAuth) {
    if (!authToken) {
      throw new Error('Not authenticated — no token set. Call login() first.');
    }
    headers['Authorization'] = `Bearer ${authToken}`;
  }

  const response = await fetch(`${BASE_URL}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  let data = null;
  const text = await response.text();
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = text;
    }
  }

  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    if (data && typeof data === 'object' && data.detail) {
      message = Array.isArray(data.detail)
        ? data.detail.map((d) => d.msg).join('; ')
        : data.detail;
    }
    const error = new Error(message);
    error.status = response.status;
    error.data = data;
    throw error;
  }

  return data;
}

// ---- Auth ----
export async function login(email, password, deviceFingerprint) {
  const data = await request('/auth/login', {
    method: 'POST',
    requiresAuth: false,
    body: { email, password, device_fingerprint: deviceFingerprint },
  });
  setAuthToken(data.access_token);
  return data;
}

export async function register(email, password, fullName, requestedRole) {
  return request('/auth/register', {
    method: 'POST',
    requiresAuth: false,
    body: { email, password, full_name: fullName, requested_role: requestedRole },
  });
}

// ---- Users (admin approval) ----
export async function listPendingUsers() {
  return request('/users/pending');
}

export async function approveUser(userId) {
  return request(`/users/${userId}/approve`, { method: 'POST' });
}

// ---- Devices ----
export async function registerDevice(fingerprint) {
  return request('/devices/register', { method: 'POST', body: { fingerprint } });
}

export async function listPendingDevices() {
  return request('/devices/pending');
}

export async function approveDevice(deviceId) {
  return request(`/devices/${deviceId}/approve`, { method: 'POST' });
}

// ---- Questions (item bank, Module 1) ----
export async function submitQuestion(payload) {
  return request('/questions', { method: 'POST', body: payload });
}

export async function listMyQuestions() {
  return request('/questions/mine');
}

// ---- Exam centres ----
export async function createExamCentre(payload) {
  return request('/exam-centres', { method: 'POST', body: payload });
}

export async function listExamCentres() {
  return request('/exam-centres');
}

// ---- Users (admin listing/lookup) ----
export async function listUsersByRole(role) {
  return request(`/users?role=${encodeURIComponent(role)}`);
}

// ---- Exam events ----
export async function createExamEvent(payload) {
  return request('/exam-events', { method: 'POST', body: payload });
}

export async function compileExamEvent(examEventId, payload) {
  return request(`/exam-events/${examEventId}/compile`, { method: 'POST', body: payload });
}

export async function listExamEvents() {
  return request('/exam-events');
}

export async function listVariantsForExamEvent(examEventId) {
  return request(`/exam-events/${examEventId}/variants`);
}

// ---- Variants ----
export async function getVariantStatus(variantId) {
  return request(`/variants/${variantId}/status`);
}

export async function submitShare(variantId, share) {
  return request(`/variants/${variantId}/submit-share`, { method: 'POST', body: share });
}

export async function getMyAssignments() {
  return request('/custodians/me/assignments');
}

export async function getMyShare(variantId) {
  return request(`/custodians/me/share/${variantId}`);
}

export async function unlockVariant(variantId, unlockRequest) {
  return request(`/variants/${variantId}/unlock`, { method: 'POST', body: unlockRequest });
}

export async function requestOverride(variantId, reason) {
  return request(`/variants/${variantId}/override-request`, { method: 'POST', body: { reason } });
}

// ---- Print jobs (Module 7) ----
export async function getPrintJobStatus(printJobId) {
  return request(`/print-jobs/${printJobId}/status`);
}

export async function getPrintJobsSummaryForVariant(variantId) {
  return request(`/print-jobs/by-variant/${variantId}/summary`);
}

// ---- Dashboard (Module 9) ----
export async function getDashboardSummary(examEventId) {
  return request(`/dashboard/summary?exam_event_id=${examEventId}`);
}

export async function getSystemFlaggedAttempts() {
  return request('/dashboard/flagged');
}

// ---- Ledger (Module 8) ----
export async function getLedger() {
  return request('/ledger');
}

export async function verifyLedger() {
  return request('/ledger/verify');
}