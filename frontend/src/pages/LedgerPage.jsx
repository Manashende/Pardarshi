import { useEffect, useState } from 'react';
import { getLedger, verifyLedger } from '../api/client';
import { formatTimestamp } from '../utils/formatters';
import PageHeader from '../components/common/PageHeader';
import './LedgerPage.css';

const DANGER_EVENTS = new Set([
  'UNLOCK_DENIED_THRESHOLD', 'UNLOCK_DENIED_TIME', 'ACCESS_DENIED', 'SHARE_VERIFICATION_FAILED',
]);
const SUCCESS_EVENTS = new Set([
  'VARIANTS_COMPILED', 'VARIANT_DECRYPTED', 'PRINT_JOB_COMPLETED', 'OFFICIAL_PRESENCE_CONFIRMED',
  'CANDIDATE_ALLOCATED', 'EXAM_SUBMITTED', 'AUDITOR_APPROVED', 'AUDITOR_BOOTSTRAP_APPROVED',
  'OVERRIDE_APPROVED', 'QUESTION_REVEAL_APPROVED',
]);

function eventBadgeClass(eventType) {
  if (DANGER_EVENTS.has(eventType)) return 'status-badge status-badge-danger';
  if (SUCCESS_EVENTS.has(eventType)) return 'status-badge status-badge-success';
  return 'status-badge status-badge-pending';
}

function humanizeKey(key) {
  return key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatValue(value) {
  if (value === null || value === undefined) return '—';
  if (Array.isArray(value)) {
    if (value.length === 0) return 'none';
    const looksLikeIds = value.every((v) => typeof v === 'string' && /^[0-9a-f-]{20,}$/i.test(v));
    return looksLikeIds ? `${value.length} item(s)` : value.join(', ');
  }
  if (typeof value === 'string' && /^[0-9a-f-]{20,}$/i.test(value)) {
    return value.slice(0, 8) + '…'; // an ID with no readable pair — shorten, don't hide
  }
  return String(value);
}

// Generic on purpose: no knowledge of specific event types here at all.
// Convention: a "<thing>_id" field is hidden from the summary ONLY if a
// paired readable field ("<thing>_email" / "_name" / "_reason" / "_code")
// exists alongside it — that pairing is on the BACKEND to provide when an
// event is written (see ledger_service.append() call sites). New event
// types automatically render sensibly without touching this file.
const READABLE_SUFFIXES = ['_email', '_name', '_reason', '_code'];
const READABLE_PLURAL_SUFFIXES = ['_emails', '_names'];

function summarizeDetails(details) {
  if (!details || Object.keys(details).length === 0) return '—';

  const keys = Object.keys(details);
  const idKeysToHide = new Set();
  keys.forEach((key) => {
    if (key.endsWith('_ids')) {
      const prefix = key.slice(0, -4);
      if (READABLE_PLURAL_SUFFIXES.some((suffix) => keys.includes(prefix + suffix))) {
        idKeysToHide.add(key);
      }
      return;
    }
    if (!key.endsWith('_id')) return;
    const prefix = key.slice(0, -3);
    if (READABLE_SUFFIXES.some((suffix) => keys.includes(prefix + suffix))) {
      idKeysToHide.add(key);
    }
  });

  const visibleKeys = keys.filter((k) => !idKeysToHide.has(k));
  if (visibleKeys.length === 0) return '—';
  return visibleKeys.map((k) => `${humanizeKey(k)}: ${formatValue(details[k])}`).join(' · ');
}

export default function LedgerPage() {
  const [entries, setEntries] = useState([]);
  const [verifyResult, setVerifyResult] = useState(null);
  const [error, setError] = useState(null);
  const [eventTypeFilter, setEventTypeFilter] = useState('All');
  const [search, setSearch] = useState('');

  async function refresh() {
    try {
      const [ledgerData, verifyData] = await Promise.all([getLedger(), verifyLedger()]);
      setEntries(ledgerData);
      setVerifyResult(verifyData);
      setError(null);
    } catch (e) {
      setError(e.message);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  return (
    <div className="dashboard">
      <PageHeader
        title="Audit Ledger"
        subtitle={verifyResult ? `${verifyResult.chain_intact ? 'Chain intact' : 'CHAIN BROKEN'} — ${verifyResult.entries_checked} entries` : ''}
      />

      {error && <p className="panel-error">{error}</p>}

      {verifyResult && !verifyResult.chain_intact && (
        <div className="ledger-tamper-banner">
          Integrity check failed at entry #{verifyResult.first_broken_index}. This indicates the audit
          trail has been altered — investigate immediately.
        </div>
      )}

      <div className="form-row" style={{ marginBottom: 16 }}>
        <div className="form-field">
          <label>Search</label>
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search event type or details…" />
        </div>
        <div className="form-field">
          <label>Event Type</label>
          <select value={eventTypeFilter} onChange={(e) => setEventTypeFilter(e.target.value)} className="form-select">
            <option value="All">All Events</option>
            {[...new Set(entries.map((e) => e.event_type))].sort().map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="panel ledger-table-wrap">
        <table className="ledger-table">
          <thead>
            <tr>
              <th>#</th>
              <th>Event</th>
              <th>Time</th>
              <th>Details</th>
              <th>Hash</th>
            </tr>
          </thead>
          <tbody>
            {entries
              .filter((e) => eventTypeFilter === 'All' || e.event_type === eventTypeFilter)
              .filter((e) => {
                if (!search.trim()) return true;
                const term = search.toLowerCase();
                return (
                  e.event_type.toLowerCase().includes(term) ||
                  summarizeDetails(e.details).toLowerCase().includes(term)
                );
              })
              .map((e) => (
              <tr key={e.index}>
                <td className="ledger-cell-mono">{e.index}</td>
                <td><span className={eventBadgeClass(e.event_type)}>{e.event_type}</span></td>
                <td className="ledger-cell-mono">{formatTimestamp(e.timestamp)}</td>
                <td className="ledger-cell-details">{summarizeDetails(e.details)}</td>
                <td className="ledger-cell-mono ledger-cell-hash" title={e.entry_hash}>
                  {e.entry_hash.slice(0, 10)}…
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {entries.length === 0 && !error && <p className="panel-empty" style={{ padding: 20 }}>No ledger entries yet.</p>}
      </div>
    </div>
  );
}