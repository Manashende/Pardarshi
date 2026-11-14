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

// Registered once by App.jsx on mount — lets this file trigger a real
// logout (clearing user state, the stored session, routing back to
// login) without importing App.jsx itself, which would be circular.
let onSessionExpired = null;

export function setSessionExpiredHandler(handler) {
  onSessionExpired = handler;
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
        ? data.detail.map((d) => {
            // d.loc is like ["body", "declared_latitude"] — drop the
            // leading "body"/"query"/etc. and show just the field path,
            // so "Field required" becomes "declared_latitude: Field
            // required" instead of an unhelpful mystery message.
            const fieldPath = Array.isArray(d.loc) ? d.loc.slice(1).join('.') : null;
            return fieldPath ? `${fieldPath}: ${d.msg}` : d.msg;
          }).join('; ')
        : data.detail;
    }

    // A 401 on an authenticated call means the token itself is no longer
    // valid (expired or revoked) — not a per-request permission issue.
    // requiresAuth guards this so a wrong-password 401 on /auth/login
    // (which sends requiresAuth: false) never triggers this path.
    if (response.status === 401 && requiresAuth) {
      clearAuthToken();
      onSessionExpired?.();
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

export async function listVariantQuestions(variantId) {
  return request(`/variants/${variantId}/questions`);
}

// ---- Exam centres ----
export async function createExamCentre(payload) {
  return request('/exam-centres', { method: 'POST', body: payload });
}

export async function listExamCentres() {
  return request('/exam-centres');
}

export async function assignCentreOperator(userId, centreId) {
  return request('/centre-operators/assign', { method: 'POST', body: { user_id: userId, centre_id: centreId } });
}

export async function listCentreOperatorAssignments() {
  return request('/centre-operators/assignments');
}

// ---- Centre Operator ----
export async function confirmPresence(examEventId, centreId, declaredLatitude, declaredLongitude, deviceFingerprint) {
  return request('/officials/confirm-presence', {
    method: 'POST',
    body: {
      exam_event_id: examEventId,
      centre_id: centreId,
      declared_latitude: declaredLatitude,
      declared_longitude: declaredLongitude,
      device_fingerprint: deviceFingerprint,
    },
  });
}

export async function getMyCentreAssignments() {
  return request('/centre-operators/me/assignments');
}

// ---- Users (admin listing/lookup) ----
export async function listUsersByRole(role) {
  return request(`/users?role=${encodeURIComponent(role)}`);
}

// ---- Students ----
export async function applyForExam(examEventId, preferredCentreIds, declaredLatitude, declaredLongitude) {
  return request('/candidates/apply', {
    method: 'POST',
    body: {
      exam_event_id: examEventId,
      preferred_centre_ids: preferredCentreIds,
      declared_latitude: declaredLatitude,
      declared_longitude: declaredLongitude,
    },
  });
}

export async function getMyApplication(examEventId) {
  return request(`/candidates/me/application/${examEventId}`);
}

export async function runAllocation(examEventId) {
  return request(`/candidates/allocate/${examEventId}`, { method: 'POST' });
}

export async function getMyApplications() {
  return request('/candidates/me/applications');
}

export async function getMyExamAssignments() {
  return request('/candidates/me/assignments');
}

export async function getMyPaper(variantId) {
  return request(`/candidates/me/paper/${variantId}`);
}

export async function submitExamAnswers(variantId, answers) {
  return request('/candidates/me/submit', { method: 'POST', body: { variant_id: variantId, answers } });
}

export async function listCandidateAssignments() {
  return request('/candidates/assignments');
}

// ---- Auditor Governance ----
export async function listPendingAuditors() {
  return request('/auditor-governance/pending');
}

export async function voteToApproveAuditor(userId) {
  return request(`/auditor-governance/${userId}/vote`, { method: 'POST' });
}

// ---- Question Reveal (forensic contributor identity, dual-control) ----
export async function requestQuestionReveal(questionId, reason) {
  return request(`/question-reveal/${questionId}/request`, { method: 'POST', body: { reason } });
}

export async function listMyRevealRequests() {
  return request('/question-reveal/mine');
}

export async function listPendingRevealRequests() {
  return request('/question-reveal/pending');
}

export async function voteToApproveReveal(requestId) {
  return request(`/question-reveal/${requestId}/vote`, { method: 'POST' });
}

// ---- Topics (item bank taxonomy, Admin-managed) ----
export async function listTopics() {
  return request('/topics');
}

export async function createTopic(name) {
  return request('/topics', { method: 'POST', body: { name } });
}

export async function viewRevealedIdentity(requestId) {
  return request(`/question-reveal/${requestId}`);
}

// ---- Exam events ----
export async function createExamEvent(payload) {
  return request('/exam-events', { method: 'POST', body: payload });
}

export async function listExamEvents() {
  return request('/exam-events');
}

export async function editExamEvent(examEventId, payload) {
  return request(`/exam-events/${examEventId}`, { method: 'PUT', body: payload });
}

export async function cancelExamEvent(examEventId) {
  return request(`/exam-events/${examEventId}/cancel`, { method: 'POST' });
}

export async function listVariantsForExamEvent(examEventId) {
  return request(`/exam-events/${examEventId}/variants`);
}

export async function proposeCompile(examEventId, payload) {
  return request(`/exam-events/${examEventId}/propose-compile`, { method: 'POST', body: payload });
}

export async function listCompileProposals() {
  return request('/exam-events/compile-proposals');
}

export async function confirmCompile(examEventId, assignmentSecret) {
  return request(`/exam-events/${examEventId}/confirm-compile`, { method: 'POST', body: { assignment_secret: assignmentSecret } });
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